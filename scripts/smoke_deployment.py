"""Check a running deployment without executing any uploaded Python source."""

import argparse
import io
import json
import os
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile


def wait_for_health(request, wait_seconds: int):
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            status, _, body = request('/health')
            if status == 200 and json.loads(body) == {'status': 'ok'}:
                break
        except (OSError, ValueError):
            # Docker can accept a TCP connection before Uvicorn is listening,
            # then reset it. Retry readiness only, never a submitted analysis.
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('Health endpoint did not become ready.')
        time.sleep(1)


def check(base: str, wait_seconds: int, github: bool):
    def request(path, body=None, content_type=None):
        headers = {'Content-Type': content_type} if content_type else {}
        try:
            response = urlopen(Request(base + path, data=body, headers=headers), timeout=65)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    wait_for_health(request, wait_seconds)
    status, headers, body = request('/')
    assert status == 200 and b'<div id="root"></div>' in body, 'Compiled website is missing'
    assert headers.get('Cache-Control') == 'no-cache'
    asset = re.search(rb'src="(/assets/[^"]+\.js)"', body)
    assert asset, 'Compiled JavaScript reference is missing'
    status, headers, _ = request(asset[1].decode())
    assert status == 200 and 'immutable' in headers.get('Cache-Control', ''), 'Built asset is missing'
    assert request('/api/not-a-route')[0] == 404
    assert request('/assets/missing.js')[0] == 404

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as sample:
        sample.writestr('main.py', 'import auth\nraise RuntimeError("Source must never run")\n')
        sample.writestr('auth.py', 'import database\ndef login(): pass\n')
        sample.writestr('database.py', 'def query(): pass\n')
    boundary = 'CodebaseSmokeBoundary'
    multipart = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo.zip"\r\n'
                 'Content-Type: application/zip\r\n\r\n').encode() + archive.getvalue() + f'\r\n--{boundary}--\r\n'.encode()
    status, headers, body = request('/api/analyses/zip', multipart, f'multipart/form-data; boundary={boundary}')
    assert status == 200, f'ZIP failed: {status} {body[:300]!r}'
    report = json.loads(body)
    assert report['summary']['files_analyzed'] == 3
    assert report['graph']['edges'] == [
        {'source': 'auth.py', 'target': 'database.py'}, {'source': 'main.py', 'target': 'auth.py'}]
    assert report['impact']['database.py']['affected_count'] == 2
    assert headers.get('Cache-Control') == 'no-store'
    status, _, body = request('/api/analyses/github', b'{"repository_url":"https://example.com/a/b"}', 'application/json')
    assert status == 422 and json.loads(body)['error']['code'] == 'INVALID_GITHUB_URL'
    print('PASS: health, compiled website/assets, real ZIP worker, impact, API errors, cache headers.')
    if github:
        status, _, body = request('/api/analyses/github',
            b'{"repository_url":"https://github.com/nikhilbajantri/AltF4.git"}', 'application/json')
        assert status == 200, f'GitHub failed: {status} {body[:300]!r}'
        report = json.loads(body)
        assert report['summary']['files_analyzed'] > 0
        print(f"PASS: AltF4 snapshot {report['input']['commit']}; {report['summary']['files_analyzed']} files, "
              f"{report['summary']['local_dependencies']} connections.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url', help='A local or public deployment URL')
    parser.add_argument('--wait-seconds', type=int, default=0)
    parser.add_argument('--github', action='store_true', help='Also check the public AltF4 download (uses GitHub rate limits)')
    args = parser.parse_args()
    try:
        check(args.url.rstrip('/'), args.wait_seconds, args.github)
    except Exception as error:
        if os.getenv('GITHUB_ACTIONS') == 'true':
            message = str(error).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print(f'::error title=Deployment smoke check::{message}', flush=True)
        raise
