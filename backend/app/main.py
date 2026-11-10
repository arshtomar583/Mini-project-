"""HTTP entry point for bounded ZIP uploads and public GitHub snapshots."""

from pathlib import Path
import os
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.archive import LIMITS
from app.github import download_github
from app.input_errors import InputError
from app.pipeline import analyze_archive
from app.request_limits import InputRequestLimits

class GitHubInput(BaseModel):
    repository_url: str = Field(max_length=300)
    source_root: str = Field(default='', max_length=220)


def create_app(workspace_parent: Path | None = None):
    app = FastAPI(title='Explain This Codebase', version='0.2.0')
    app.add_middleware(InputRequestLimits)
    # Outer CORS middleware also covers early size/busy responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in os.getenv('FRONTEND_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip()],
        allow_methods=['GET', 'POST'], allow_headers=['Content-Type'],
    )

    @app.exception_handler(InputError)
    async def input_error(request, error):
        return JSONResponse(error.payload(), status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse({'error': {'code': 'INVALID_REQUEST', 'message': 'Check the required file, repository URL, and source-folder fields.'}}, status_code=422)

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.post('/api/analyses/zip')
    async def zip_analysis(
        file: Annotated[UploadFile, File()],
        source_root: Annotated[str, Form(max_length=220)] = '',
    ):
        try:
            if not file.filename or not file.filename.lower().endswith('.zip'):
                raise InputError('ZIP_REQUIRED', 'Choose a .zip file containing a Python project.')
            with TemporaryDirectory(prefix='codebase-', dir=workspace_parent) as folder:
                workspace = Path(folder)
                archive = workspace / 'input.zip'
                total = 0
                with archive.open('xb') as target:
                    while chunk := await file.read(64 * 1024):
                        total += len(chunk)
                        if total > LIMITS.archive_bytes:
                            raise InputError('ARCHIVE_TOO_LARGE', 'The ZIP exceeds the 5 MiB upload limit.', 413)
                        target.write(chunk)
                result = await analyze_archive(archive, workspace, source_root)
                return {**result['report'], 'input': {'kind': 'zip', 'source_root': result['source_root']}}
        finally:
            await file.close()

    @app.post('/api/analyses/github')
    async def github_analysis(body: GitHubInput):
        with TemporaryDirectory(prefix='codebase-', dir=workspace_parent) as folder:
            workspace = Path(folder)
            metadata = await download_github(body.repository_url, workspace / 'input.zip')
            result = await analyze_archive(workspace / 'input.zip', workspace, body.source_root, strip_wrapper=True)
            return {**result['report'], 'input': {**metadata, 'source_root': result['source_root']}}

    return app


app = create_app()
