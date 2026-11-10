import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch
from dataclasses import replace

import httpx

from app.input_errors import InputError
from app.main import create_app
from app.archive import LIMITS
from app.pipeline import analyze_archive
from test_archive import zip_bytes


class InputApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = TemporaryDirectory()
        self.parent = Path(self.temporary.name)
        self.app = create_app(self.parent)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        self.assertEqual(list(self.parent.iterdir()), [], 'Request workspaces must be cleaned up')
        self.temporary.cleanup()

    async def upload(self, sources, **fields):
        return await self.client.post('/api/analyses/zip', files={'file': ('project.zip', zip_bytes(sources), 'application/zip')}, data=fields)

    async def test_zip_real_worker_and_no_source_execution(self):
        marker = self.parent / 'SHOULD_NOT_EXIST'
        response = await self.upload({
            'project/main.py': f'from pathlib import Path\nPath({str(marker)!r}).write_text("executed")\nimport database\n',
            'project/database.py': 'def query(): pass\n',
        })
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['summary']['files_analyzed'], 2)
        self.assertIn({'source': 'main.py', 'target': 'database.py'}, result['graph']['edges'])
        self.assertEqual(result['input'], {'kind': 'zip', 'source_root': '.'})
        self.assertFalse(marker.exists())

    async def test_invalid_empty_no_python_and_unsafe_inputs(self):
        for sources, code in [({'README.md': 'hello'}, 'NO_PYTHON_FILES'),
                              ({'../escape.py': ''}, 'UNSAFE_PATH'), ({'inner.zip': ''}, 'NESTED_ARCHIVE')]:
            response = await self.upload(sources)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(response.json()['error']['code'], code)
        response = await self.client.post('/api/analyses/zip', files={'file': ('bad.zip', b'not a zip')})
        self.assertEqual(response.status_code, 422)
        response = await self.client.post('/api/analyses/zip', files={'file': ('bad.txt', b'not a zip')})
        self.assertEqual(response.json()['error']['code'], 'ZIP_REQUIRED')

    async def test_source_root_partial_results_and_missing_root(self):
        sources = {'project/src/valid.py': 'def hello(): pass\n', 'project/src/broken.py': 'def (: pass\n', 'project/README.md': ''}
        response = await self.upload(sources, source_root='src')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['analysis_status'], 'partial')
        self.assertEqual(response.json()['input']['source_root'], 'src')
        response = await self.upload(sources, source_root='../../outside')
        self.assertEqual(response.status_code, 422)
        response = await self.upload(sources, source_root='missing')
        self.assertEqual(response.json()['error']['code'], 'INVALID_SOURCE_ROOT')

    async def test_github_endpoint_shares_real_worker_and_cleanup(self):
        async def download(url, path):
            path.write_bytes(zip_bytes({'snapshot/main.py': 'def hello(): pass\n'}))
            return {'kind': 'github', 'repository_url': url, 'branch': 'main', 'commit': 'a' * 40}

        with patch('app.main.download_github', side_effect=download):
            response = await self.client.post('/api/analyses/github', json={'repository_url': 'https://github.com/a/b'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['summary']['functions'], 1)
        self.assertEqual(response.json()['input']['commit'], 'a' * 40)
        with patch('app.main.download_github', side_effect=InputError('GITHUB_TIMEOUT', 'Try again.', 504)):
            response = await self.client.post('/api/analyses/github', json={'repository_url': 'https://github.com/a/b'})
        self.assertEqual(response.status_code, 504)

    async def test_bad_request_body_limit_and_cors_errors(self):
        response = await self.client.post('/api/analyses/github', json={})
        self.assertEqual(response.status_code, 422)
        response = await self.client.post('/api/analyses/github', content='x' * 4097,
                                          headers={'Origin': 'http://localhost:5173'})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
        response = await self.client.post('/api/analyses/github', json={'repository_url': 'http://localhost/private'})
        self.assertEqual(response.json()['error']['code'], 'INVALID_GITHUB_URL')

    async def test_busy_rejection_leaves_health_available(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def wait(url, path):
            entered.set()
            await release.wait()
            raise InputError('TEST_FAILURE', 'Intentional test failure.')

        with patch('app.main.download_github', side_effect=wait):
            task = asyncio.create_task(self.client.post('/api/analyses/github', json={'repository_url': 'https://github.com/a/b'}))
            await asyncio.wait_for(entered.wait(), 3)
            try:
                response = await self.client.post('/api/analyses/github', json={'repository_url': 'https://github.com/a/b'})
                self.assertEqual(response.status_code, 503)
                self.assertEqual((await self.client.get('/health')).status_code, 200)
            finally:
                release.set()
                await task

    async def test_timeout_terminates_worker_before_cleanup(self):
        process = AsyncMock()
        process.returncode = None
        calls = 0

        async def wait():
            nonlocal calls
            calls += 1
            if calls == 1:
                await asyncio.sleep(10)
            return 0

        process.wait.side_effect = wait
        process.kill = lambda: setattr(process, 'returncode', -1)
        with patch('app.pipeline.asyncio.create_subprocess_exec', return_value=process), patch('app.pipeline.WORKER_SECONDS', .01):
            with self.assertRaises(InputError) as caught:
                await analyze_archive(self.parent / 'input.zip', self.parent, '')
        self.assertEqual(caught.exception.code, 'ANALYSIS_TIMEOUT')
        self.assertEqual(process.returncode, -1)

    async def test_streamed_body_limit_and_upload_byte_limit(self):
        async def chunks():
            yield b'x' * 3000
            yield b'x' * 3000

        response = await self.client.post('/api/analyses/github', content=chunks())
        self.assertEqual(response.status_code, 413)
        with patch('app.main.LIMITS', replace(LIMITS, archive_bytes=3)):
            response = await self.upload({'main.py': ''})
        self.assertEqual(response.status_code, 413)

    async def test_oversized_report_is_rejected_and_cleaned(self):
        # These small compressed sources expand to a report larger than 4 MiB
        # because JSON escapes non-ASCII docstring characters.
        sources = {f'file_{index}.py': 'def hello():\n    """' + 'é' * 100000 + '"""\n' for index in range(8)}
        response = await self.upload(sources)
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json()['error']['code'], 'REPORT_TOO_LARGE')

    async def test_real_worker_timeout_cleans_workspace(self):
        with patch('app.pipeline.WORKER_SECONDS', .0001):
            response = await self.upload({'main.py': 'def hello(): pass\n'})
        self.assertEqual(response.status_code, 504, response.text)
        self.assertEqual(response.json()['error']['code'], 'ANALYSIS_TIMEOUT')
