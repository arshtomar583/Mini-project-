"""Bounded ZIP extraction into a fresh workspace; no uploaded code is run."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
import zlib

from app.input_errors import InputError


MIB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    archive_bytes: int = 5 * MIB
    extracted_bytes: int = 25 * MIB
    entries: int = 2000
    python_files: int = 200
    python_file_bytes: int = MIB
    depth: int = 10


LIMITS = Limits()
RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)
NESTED_ARCHIVES = {'.zip', '.tar', '.tgz', '.gz', '.bz2', '.xz', '.7z', '.rar'}


def path_parts(name: str) -> tuple[str, ...]:
    # Reject ambiguous paths on both Windows and Unix rather than normalize
    # potentially hostile archive names into a different destination.
    parts = name.split('/')
    if (
        not name or name.startswith('/') or '\\' in name or len(name) > 220
        or any(ord(character) < 32 for character in name)
        or any(character in name for character in '<>:"|?*')
        or any(part in {'', '.', '..'} or part.endswith((' ', '.')) or RESERVED.match(part) for part in parts)
    ):
        raise InputError('UNSAFE_PATH', 'The ZIP contains an unsupported or unsafe file path.')
    return tuple(parts)


def extract_archive(archive: Path, destination: Path, limits: Limits = LIMITS) -> Path:
    if archive.stat().st_size > limits.archive_bytes:
        raise InputError('ARCHIVE_TOO_LARGE', 'The ZIP exceeds the 5 MiB download/upload limit.', 413)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            if len(entries) > limits.entries:
                raise InputError('TOO_MANY_ENTRIES', 'The ZIP contains too many entries.', 413)
            seen = set()
            spellings = {}
            planned = []
            python_files = 0
            declared_total = 0
            for info in entries:
                # ZipInfo.filename can truncate at NUL; inspect the original too.
                if '\x00' in info.orig_filename:
                    raise InputError('UNSAFE_PATH', 'The ZIP contains an unsafe file path.')
                parts = path_parts(info.orig_filename[:-1] if info.is_dir() else info.orig_filename)
                if len(parts) > limits.depth:
                    raise InputError('TOO_DEEP', 'The ZIP exceeds the directory-depth limit.', 413)
                folded = '/'.join(parts).casefold()
                if folded in seen:
                    raise InputError('DUPLICATE_PATH', 'The ZIP contains duplicate or case-conflicting paths.')
                seen.add(folded)
                for length in range(1, len(parts) + 1):
                    original = '/'.join(parts[:length])
                    folded_prefix = original.casefold()
                    if folded_prefix in spellings and spellings[folded_prefix] != original:
                        raise InputError('DUPLICATE_PATH', 'The ZIP contains case-conflicting folder or file names.')
                    spellings[folded_prefix] = original
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if file_type not in {0, stat.S_IFREG, stat.S_IFDIR} or (info.flag_bits & 1):
                    raise InputError('UNSUPPORTED_ENTRY', 'Links, special files, and encrypted ZIP entries are not supported.')
                path = destination.joinpath(*parts)
                if not path.resolve().is_relative_to(destination.resolve()):
                    raise InputError('UNSAFE_PATH', 'The ZIP contains an unsafe file path.')
                if not info.is_dir():
                    if path.suffix.lower() in NESTED_ARCHIVES:
                        raise InputError('NESTED_ARCHIVE', 'ZIPs containing other archives are not supported. Remove nested archives and retry.')
                    declared_total += info.file_size
                    if path.suffix == '.py':
                        python_files += 1
                        if info.file_size > limits.python_file_bytes:
                            raise InputError('SOURCE_TOO_LARGE', 'An individual Python file exceeds 1 MiB.', 413)
                planned.append((info, path))
            if declared_total > limits.extracted_bytes or python_files > limits.python_files:
                raise InputError('PROJECT_TOO_LARGE', 'The project exceeds 25 MiB extracted or 200 Python files.', 413)

            # No extractall: stream each entry and count bytes as they are read.
            actual_total = 0
            for info, path in planned:
                if info.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                actual_file = 0
                with zipped.open(info) as source, path.open('xb') as target:
                    while chunk := source.read(64 * 1024):
                        actual_file += len(chunk)
                        actual_total += len(chunk)
                        if actual_total > limits.extracted_bytes or (
                            path.suffix == '.py' and actual_file > limits.python_file_bytes
                        ):
                            raise InputError('PROJECT_TOO_LARGE', 'The extracted project exceeds the configured limits.', 413)
                        target.write(chunk)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, RuntimeError, OSError, zlib.error) as error:
        raise InputError('INVALID_ZIP', 'The ZIP is corrupt, unsupported, or has conflicting file paths.') from error
    return destination


def select_source_root(extracted: Path, source_root: str = '', *, strip_wrapper: bool = False) -> tuple[Path, str]:
    # GitHub archives and many user ZIPs have a single outer folder. Retain a
    # sole actual package, however: stripping its name breaks absolute imports.
    children = list(extracted.iterdir())
    project = extracted
    if len(children) == 1 and children[0].is_dir() and (strip_wrapper or not (children[0] / '__init__.py').exists()):
        project = children[0]
    relative = source_root.strip()
    if relative:
        parts = path_parts(relative)
        chosen = project.joinpath(*parts)
        if not chosen.resolve().is_relative_to(project.resolve()) or not chosen.is_dir():
            raise InputError('INVALID_SOURCE_ROOT', 'The source folder does not exist inside this project.')
        return chosen, PurePosixPath(*parts).as_posix()
    return project, '.'
