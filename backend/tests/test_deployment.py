from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx

from app.main import create_app
from app.request_limits import InputRequestLimits


class DeploymentTests(unittest.IsolatedAsyncioTestCase):
    async def test_compiled_website_assets_api_and_source_boundary(self):
        with TemporaryDirectory() as folder:
            parent = Path(folder)
            public = parent / 'dist'
            (public / 'assets').mkdir(parents=True)
            (public / 'index.html').write_text('<html>Compiled site</html>')
            (public / 'assets' / 'app-hash.js').write_text('console.log("site")')
            (parent / 'secret.txt').write_text('not-public')
            with patch.dict('os.environ', {'FRONTEND_DIST': str(public)}):
                app = create_app()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
                index = await client.get('/')
                self.assertEqual(index.status_code, 200)
                self.assertIn('Compiled site', index.text)
                self.assertEqual(index.headers['cache-control'], 'no-cache')
                asset = await client.get('/assets/app-hash.js')
                self.assertEqual(asset.status_code, 200)
                self.assertIn('immutable', asset.headers['cache-control'])
                self.assertEqual((await client.get('/health')).json(), {'status': 'ok'})
                for path in ['/api/unknown', '/assets/missing.js', '/secret.txt', '/%2e%2e/secret.txt', '/app/main.py']:
                    self.assertEqual((await client.get(path)).status_code, 404, path)
                error = await client.post('/api/analyses/github', json={})
                self.assertEqual(error.status_code, 422)
                self.assertEqual(error.headers['cache-control'], 'no-store')
                self.assertEqual(error.headers['x-content-type-options'], 'nosniff')
                self.assertEqual(index.headers['x-frame-options'], 'DENY')

    async def test_invalid_build_directory_fails_early_and_api_only_mode_still_works(self):
        with TemporaryDirectory() as folder:
            with patch.dict('os.environ', {'FRONTEND_DIST': folder}):
                with self.assertRaisesRegex(RuntimeError, 'index.html'):
                    create_app()
        with patch.dict('os.environ', {'FRONTEND_DIST': ''}):
            app = create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            self.assertEqual((await client.get('/')).status_code, 404)
            self.assertEqual((await client.get('/health')).status_code, 200)

    async def test_rate_window_rejects_before_reading_and_recovers(self):
        now = [100.0]
        reached = []

        async def endpoint(scope, receive, send):
            reached.append(scope['path'])
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b'ok'})

        app = InputRequestLimits(endpoint, max_requests=2, window_seconds=60, clock=lambda: now[0])
        scope = {'type': 'http', 'path': '/api/analyses/github', 'method': 'POST', 'headers': []}
        reads = []

        async def receive():
            reads.append(True)
            return {'type': 'http.request', 'body': b'{}', 'more_body': False}

        async def call():
            messages = []

            async def send(message):
                messages.append(message)

            await app(scope, receive, send)
            return messages

        self.assertEqual((await call())[0]['status'], 200)
        self.assertEqual((await call())[0]['status'], 200)
        now[0] = 110.0
        limited = await call()
        self.assertEqual(limited[0]['status'], 429)
        self.assertEqual(dict(limited[0]['headers'])[b'retry-after'], b'50')
        self.assertEqual(len(reads), 2, 'Rate-limited bodies must not be buffered')
        self.assertEqual(len(reached), 2)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            self.assertEqual((await client.get('/health')).status_code, 200)
        now[0] = 160.0
        self.assertEqual((await call())[0]['status'], 200)

    async def test_rate_limit_has_json_headers_and_cors_in_real_app(self):
        with patch.dict('os.environ', {'FRONTEND_DIST': ''}):
            app = create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            for _ in range(20):
                self.assertEqual((await client.post('/api/analyses/github', json={})).status_code, 422)
            response = await client.post('/api/analyses/github', json={}, headers={'Origin': 'http://localhost:5173'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json()['error']['code'], 'RATE_LIMITED')
            self.assertIn('retry-after', response.headers)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
            self.assertEqual((await client.get('/health')).status_code, 200)


if __name__ == '__main__':
    unittest.main()
