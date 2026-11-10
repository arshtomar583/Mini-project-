"""Bound request bodies before multipart parsing; accept one analysis per process."""

import asyncio
from collections import deque
import math
import time

from starlette.responses import JSONResponse


MAX_BODY_BYTES = 6 * 1024 * 1024  # 5 MiB ZIP plus multipart overhead
INPUT_PATHS = {'/api/analyses/zip', '/api/analyses/github'}


class InputRequestLimits:
    def __init__(self, app, max_requests=20, window_seconds=60, clock=time.monotonic):
        self.app = app
        self.lock = asyncio.Lock()
        self.starts = deque()
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] not in INPUT_PATHS or scope['method'] != 'POST':
            await self.app(scope, receive, send)
            return

        async def fail(code, message, status, headers=None):
            response = JSONResponse({'error': {'code': code, 'message': message}}, status_code=status, headers=headers)
            await response(scope, receive, send)

        if self.lock.locked():
            await fail('SERVER_BUSY', 'Another project is being analyzed. Please try again shortly.', 503)
            return
        async with self.lock:
            now = self.clock()
            while self.starts and now - self.starts[0] >= self.window_seconds:
                self.starts.popleft()
            if len(self.starts) >= self.max_requests:
                retry = max(1, math.ceil(self.window_seconds - (now - self.starts[0])))
                await fail('RATE_LIMITED', f'The demo is receiving too many requests. Try again in {retry} seconds.',
                           429, {'Retry-After': str(retry)})
                return
            # Count rejected/invalid admitted requests too, before buffering any
            # body. This is a service-wide demo cap, not an IP identity system.
            self.starts.append(now)
            maximum = 4096 if scope['path'].endswith('/github') else MAX_BODY_BYTES
            headers = dict(scope['headers'])
            try:
                declared = int(headers.get(b'content-length', b'0'))
            except ValueError:
                await fail('INVALID_REQUEST', 'Invalid request length.', 400)
                return
            if declared < 0 or declared > maximum:
                await fail('REQUEST_TOO_LARGE', 'The request exceeds the input size limit.', 413)
                return
            data = bytearray()
            try:
                async with asyncio.timeout(20):
                    while True:
                        message = await receive()
                        if message['type'] == 'http.disconnect':
                            return
                        data.extend(message.get('body', b''))
                        if len(data) > maximum:
                            await fail('REQUEST_TOO_LARGE', 'The request exceeds the input size limit.', 413)
                            return
                        if not message.get('more_body', False):
                            break
            except TimeoutError:
                await fail('UPLOAD_TIMEOUT', 'The upload timed out. Please try again.', 408)
                return
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': bytes(data), 'more_body': False}
                return await receive()

            await self.app(scope, replay, send)
