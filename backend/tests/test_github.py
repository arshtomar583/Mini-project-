from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
import unittest
from unittest.mock import patch

import httpx

from app.github import download_github, parse_github_url
from app.input_errors import InputError
from app.archive import LIMITS


SHA = 'a' * 40


class GithubTests(unittest.IsolatedAsyncioTestCase):
    def test_url_validation(self):
        self.assertEqual(parse_github_url('https://github.com/nikhilbajantri/AltF4.git'), ('nikhilbajantri', 'AltF4'))
        for url in ['http://github.com/a/b', 'https://example.com/a/b', 'https://github.com.evil/a/b',
                    'https://github.com@localhost/a/b', 'https://github.com:443/a/b',
                    'https://github.com/a/b/tree/main', 'https://github.com/a/b?x=1',
                    'https://github.com/a/%2e%2e', 'file:///etc/passwd', 'https://github.com/a/..']:
            with self.subTest(url=url), self.assertRaises(InputError):
                parse_github_url(url)

    async def test_default_branch_snapshot_only_uses_fixed_hosts(self):
        requests = []

        def respond(request):
            requests.append(request)
            self.assertNotIn('authorization', request.headers)
            if request.url.host == 'codeload.github.com':
                self.assertEqual(request.url.path, '/owner/project/zip/' + SHA)
                return httpx.Response(200, content=b'zip content')
            if '/git/ref/' in request.url.path:
                return httpx.Response(200, json={'object': {'sha': SHA}})
            return httpx.Response(200, json={'private': False, 'default_branch': 'main'})

        with TemporaryDirectory() as folder:
            path = Path(folder) / 'download.zip'
            result = await download_github('https://github.com/owner/project.git', path, transport=httpx.MockTransport(respond))
            self.assertEqual(result['commit'], SHA)
            self.assertEqual(path.read_bytes(), b'zip content')
        self.assertEqual([request.url.host for request in requests], ['api.github.com', 'api.github.com', 'codeload.github.com'])

    async def test_missing_rate_limited_redirect_and_network_failures(self):
        for status, expected in [(404, 'REPOSITORY_NOT_FOUND'), (403, 'GITHUB_RATE_LIMIT'),
                                 (429, 'GITHUB_RATE_LIMIT'), (302, 'GITHUB_UNAVAILABLE'), (500, 'GITHUB_UNAVAILABLE')]:
            with TemporaryDirectory() as folder, self.assertRaises(InputError) as caught:
                await download_github('https://github.com/a/b', Path(folder) / 'input.zip',
                                      transport=httpx.MockTransport(lambda request: httpx.Response(status)))
            self.assertEqual(caught.exception.code, expected)

        def offline(request):
            raise httpx.ConnectError('offline', request=request)

        with TemporaryDirectory() as folder, self.assertRaises(InputError) as caught:
            await download_github('https://github.com/a/b', Path(folder) / 'input.zip', transport=httpx.MockTransport(offline))
        self.assertEqual(caught.exception.code, 'GITHUB_UNAVAILABLE')

    async def test_invalid_metadata_and_private_repository_rejected(self):
        for metadata in [{'private': True, 'default_branch': 'main'}, {'private': False}, ['unexpected']]:
            with TemporaryDirectory() as folder, self.assertRaises(InputError):
                await download_github('https://github.com/a/b', Path(folder) / 'input.zip',
                                      transport=httpx.MockTransport(lambda request: httpx.Response(200, json=metadata)))

    async def test_archive_download_cap_and_timeout(self):
        def respond(request):
            if request.url.host == 'codeload.github.com':
                return httpx.Response(200, content=b'too large')
            if '/git/ref/' in request.url.path:
                return httpx.Response(200, json={'object': {'sha': SHA}})
            return httpx.Response(200, json={'private': False, 'default_branch': 'main'})

        with TemporaryDirectory() as folder, patch('app.github.LIMITS', replace(LIMITS, archive_bytes=3)):
            with self.assertRaises(InputError) as caught:
                await download_github('https://github.com/a/b', Path(folder) / 'input.zip', transport=httpx.MockTransport(respond))
            self.assertEqual(caught.exception.status, 413)

        def timeout(request):
            raise httpx.ReadTimeout('timed out', request=request)

        with TemporaryDirectory() as folder, self.assertRaises(InputError) as caught:
            await download_github('https://github.com/a/b', Path(folder) / 'input.zip', transport=httpx.MockTransport(timeout))
        self.assertEqual(caught.exception.status, 504)
