"""Trusted worker: safely extract and analyze; never execute uploaded source."""

import json
from pathlib import Path
import sys

from app.analyzer import analyze_project
from app.archive import extract_archive, select_source_root
from app.input_errors import InputError


MAX_REPORT_BYTES = 4 * 1024 * 1024


def run(archive: Path, extracted: Path, source_root: str, strip_wrapper: bool = False) -> dict:
    extract_archive(archive, extracted)
    chosen, selected = select_source_root(extracted, source_root, strip_wrapper=strip_wrapper)
    report = analyze_project(chosen)
    if report['summary']['files_found'] == 0:
        raise InputError('NO_PYTHON_FILES', 'No Python files were found. Check the selected source folder.')
    return {'report': report, 'source_root': selected}


def main():
    archive, extracted, result = map(Path, sys.argv[1:4])
    try:
        # Deployment on Linux also bounds address space. Windows must rely on
        # input/timeout limits locally and a hosting memory cap in production.
        if sys.platform.startswith('linux'):
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        payload = run(archive, extracted, sys.argv[4], sys.argv[5] == '1')
        serialized = json.dumps(payload, ensure_ascii=True)
        if len(serialized.encode()) > MAX_REPORT_BYTES:
            raise InputError('REPORT_TOO_LARGE', 'The analysis report exceeds 4 MiB. Select a smaller source folder.', 413)
    except InputError as error:
        serialized = json.dumps({**error.payload(), 'status': error.status})
    except (MemoryError, RecursionError):
        serialized = json.dumps({'error': {'code': 'ANALYSIS_LIMIT', 'message': 'This project exceeds the analysis resource limits.'}, 'status': 413})
    result.write_text(serialized, encoding='utf-8')


if __name__ == '__main__':
    main()
