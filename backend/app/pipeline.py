"""Run extraction/analysis in a disposable process with a wall-clock deadline."""

import asyncio
import json
from pathlib import Path
import sys

from app.input_errors import InputError


WORKER_SECONDS = 15
BACKEND = Path(__file__).resolve().parents[1]


async def analyze_archive(archive: Path, workspace: Path, source_root: str, *, strip_wrapper: bool = False) -> dict:
    result_path = workspace / 'result.json'
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'app.input_worker', str(archive), str(workspace / 'source'),
        str(result_path), source_root, '1' if strip_wrapper else '0', cwd=BACKEND,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        try:
            await asyncio.wait_for(process.wait(), WORKER_SECONDS)
        except TimeoutError as error:
            raise InputError('ANALYSIS_TIMEOUT', 'Analysis exceeded 15 seconds. Choose a smaller source folder.', 504) from error
        if process.returncode != 0 or not result_path.is_file() or result_path.stat().st_size > 4 * 1024 * 1024:
            raise InputError('ANALYSIS_FAILED', 'The analysis worker could not process this project.', 422)
        payload = json.loads(result_path.read_text(encoding='utf-8'))
        if 'error' in payload:
            raise InputError(payload['error']['code'], payload['error']['message'], payload['status'])
        return payload
    finally:
        # Cancellation and timeouts must stop the actual work before the caller
        # deletes the request's temporary files.
        if process.returncode is None:
            process.kill()
        await process.wait()
