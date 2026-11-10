"""Anonymous public GitHub snapshots downloaded from fixed trusted hosts."""

import asyncio
import json
from pathlib import Path
import re
from urllib.parse import quote

import httpx

from app.archive import LIMITS
from app.input_errors import InputError


def parse_github_url(url: str) -> tuple[str, str]:
    match = re.fullmatch(r'https://github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9_.-]{1,100})/?', url.strip())
    if not match:
        raise InputError('INVALID_GITHUB_URL', 'Use a public repository URL such as https://github.com/owner/repo. Branch, file, and other website URLs are not supported.')
    owner, repo = match.groups()
    if repo.endswith('.git'):
        repo = repo[:-4]
    if repo in {'', '.', '..'}:
        raise InputError('INVALID_GITHUB_URL', 'Enter a valid public GitHub repository URL.')
    return owner, repo


def check_status(status: int):
    if status == 404:
        raise InputError('REPOSITORY_NOT_FOUND', 'The public repository or its default branch was not found. Private repositories are not supported.', 404)
    if status in {403, 429}:
        raise InputError('GITHUB_RATE_LIMIT', 'GitHub is limiting anonymous requests. Please try again later.', 503)
    if status != 200:
        raise InputError('GITHUB_UNAVAILABLE', 'GitHub could not provide this repository. Check the current repository URL and try again.', 502)


async def read_small_json(client: httpx.AsyncClient, url: str) -> dict:
    body = bytearray()
    async with client.stream('GET', url) as response:
        check_status(response.status_code)
        async for chunk in response.aiter_bytes(16 * 1024):
            body.extend(chunk)
            if len(body) > 64 * 1024:
                raise InputError('GITHUB_RESPONSE', 'GitHub returned an unexpectedly large metadata response.', 502)
    try:
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError('Expected an object')
        return result
    except (ValueError, UnicodeError) as error:
        raise InputError('GITHUB_RESPONSE', 'GitHub returned invalid repository information.', 502) from error


async def download_github(url: str, destination: Path, *, transport=None) -> dict:
    owner, repo = parse_github_url(url)
    try:
        async with asyncio.timeout(30):
            # Ignore proxy credentials/environment config; never send a token.
            # Redirects are refused so a URL cannot escape the fixed hosts.
            async with httpx.AsyncClient(
                follow_redirects=False, trust_env=False, transport=transport,
                timeout=httpx.Timeout(10, connect=5),
                headers={'User-Agent': 'Explain-This-Codebase/0.1', 'Accept': 'application/vnd.github+json'},
            ) as client:
                api = f'https://api.github.com/repos/{owner}/{repo}'
                metadata = await read_small_json(client, api)
                branch = metadata.get('default_branch')
                if metadata.get('private') is not False or not isinstance(branch, str) or not branch:
                    raise InputError('REPOSITORY_NOT_PUBLIC', 'Only public repositories with a default branch are supported.')
                reference = await read_small_json(client, api + '/git/ref/heads/' + quote(branch, safe=''))
                commit_object = reference.get('object')
                sha = commit_object.get('sha') if isinstance(commit_object, dict) else None
                if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', sha):
                    raise InputError('GITHUB_RESPONSE', 'GitHub did not return a valid default-branch snapshot.', 502)
                archive_url = f'https://codeload.github.com/{owner}/{repo}/zip/{sha}'
                total = 0
                async with client.stream('GET', archive_url) as response:
                    check_status(response.status_code)
                    with destination.open('xb') as target:
                        async for chunk in response.aiter_bytes(64 * 1024):
                            total += len(chunk)
                            if total > LIMITS.archive_bytes:
                                raise InputError('ARCHIVE_TOO_LARGE', 'The repository ZIP exceeds 5 MiB. Use a smaller project or a ZIP containing only the relevant Python source.', 413)
                            target.write(chunk)
                return {'kind': 'github', 'repository_url': f'https://github.com/{owner}/{repo}', 'branch': branch, 'commit': sha}
    except (TimeoutError, httpx.TimeoutException) as error:
        raise InputError('GITHUB_TIMEOUT', 'The GitHub download timed out. Please try again.', 504) from error
    except httpx.HTTPError as error:
        raise InputError('GITHUB_UNAVAILABLE', 'The server could not reach GitHub. Please try again.', 502) from error
