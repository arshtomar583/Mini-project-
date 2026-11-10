"""Serve only the compiled website, never project source or uploaded files."""

from pathlib import Path

from starlette.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # index.html points to versioned assets: always check for a newer index.
        response.headers['Cache-Control'] = (
            'public, max-age=31536000, immutable'
            if path.replace('\\', '/').startswith('assets/') and response.status_code == 200
            else 'no-cache'
        )
        return response


def mount_frontend(app, directory: str):
    root = Path(directory).resolve()
    if not (root / 'index.html').is_file():
        raise RuntimeError('FRONTEND_DIST must contain the built frontend index.html. Run npm run build first.')
    # Mount last so /health and /api keep their own handlers. No catch-all SPA
    # fallback: unknown API paths and missing assets must remain real 404s.
    app.mount('/', FrontendFiles(directory=root, html=True), name='frontend')


class ResponseHeaders:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def with_headers(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.extend([
                    (b'x-content-type-options', b'nosniff'),
                    (b'x-frame-options', b'DENY'),
                    (b'referrer-policy', b'same-origin'),
                ])
                if scope['path'].startswith('/api/'):
                    headers.append((b'cache-control', b'no-store'))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, with_headers)
