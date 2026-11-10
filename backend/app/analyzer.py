"""Extract Python structure without importing or executing the analyzed project.

Run from backend: python -m app.analyzer ../examples/demo_project
"""

import argparse
import ast
import json
import os
from pathlib import Path
import tokenize

from app.dependencies import resolve_dependencies


IGNORED_DIRECTORIES = {
    '.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules',
    'dist', 'build', '.pytest_cache', '.mypy_cache', '.tox',
}


class StructureVisitor(ast.NodeVisitor):
    """Visit definitions and imports while remembering their enclosing scope."""

    def __init__(self):
        self.scope: list[str] = []
        self.functions: list[dict] = []
        self.classes: list[dict] = []
        self.imports: list[dict] = []

    def _definition(self, node, destination, **extra):
        destination.append({
            'name': node.name,
            'qualified_name': '.'.join([*self.scope, node.name]),
            'line': node.lineno,
            'end_line': node.end_lineno,
            'docstring': ast.get_docstring(node),
            **extra,
        })
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._definition(node, self.functions, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._definition(node, self.functions, is_async=True)

    def visit_ClassDef(self, node: ast.ClassDef):
        self._definition(node, self.classes)

    def visit_Import(self, node: ast.Import):
        self.imports.append({
            'kind': 'import',
            'module': None,
            'level': 0,
            'names': [{'name': item.name, 'alias': item.asname} for item in node.names],
            'line': node.lineno,
            'scope': '.'.join(self.scope) or None,
        })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        self.imports.append({
            'kind': 'from',
            'module': node.module,
            'level': node.level,
            'names': [{'name': item.name, 'alias': item.asname} for item in node.names],
            'line': node.lineno,
            'scope': '.'.join(self.scope) or None,
        })


def analyze_file(path: Path, root: Path) -> dict:
    """Parse one file; tokenize.open respects Python encoding declarations."""
    with tokenize.open(path) as source_file:
        tree = ast.parse(source_file.read(), filename=path.relative_to(root).as_posix())
    visitor = StructureVisitor()
    visitor.visit(tree)
    return {
        'path': path.relative_to(root).as_posix(),
        'functions': visitor.functions,
        'classes': visitor.classes,
        'imports': visitor.imports,
    }


def analyze_project(project_path: str | Path) -> dict:
    """Analyze a local directory, reporting unreadable or invalid files separately.

    This is a local development tool. Resource limits must be added before using
    the analyzer with public uploads. The input folder is the import root.
    """
    root = Path(project_path).resolve()
    if not root.is_dir():
        raise ValueError('Project path must be an existing directory.')

    files: list[dict] = []
    errors: list[dict] = []

    def traversal_error(error: OSError):
        # Report a relative path without exposing the machine's absolute paths.
        path = Path(error.filename).relative_to(root).as_posix() if error.filename else '.'
        errors.append({'path': path, 'type': type(error).__name__, 'message': 'Cannot read directory.', 'line': None})

    for directory, subdirectories, filenames in os.walk(root, onerror=traversal_error, followlinks=False):
        subdirectories[:] = sorted(
            name for name in subdirectories
            if name not in IGNORED_DIRECTORIES and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(filenames):
            path = Path(directory) / name
            if path.suffix != '.py' or path.is_symlink():
                continue
            try:
                files.append(analyze_file(path, root))
            except (SyntaxError, UnicodeError, OSError) as error:
                errors.append({
                    'path': path.relative_to(root).as_posix(),
                    'type': type(error).__name__,
                    'message': error.msg if isinstance(error, SyntaxError) else 'Cannot read Python source.',
                    'line': getattr(error, 'lineno', None),
                })

    files.sort(key=lambda item: item['path'])
    errors.sort(key=lambda item: item['path'])
    dependencies = resolve_dependencies(files)
    return {
        'schema_version': 2,
        'summary': {
            'files_found': len(files) + sum(error['path'].endswith('.py') for error in errors),
            'files_analyzed': len(files),
            'functions': sum(len(file['functions']) for file in files),
            'classes': sum(len(file['classes']) for file in files),
            'import_statements': sum(len(file['imports']) for file in files),
            'errors': len(errors),
            'local_dependencies': len(dependencies['edges']),
            'unresolved_imports': sum(item['status'] != 'local' for item in dependencies['imports']),
        },
        'files': files,
        'errors': errors,
        'dependencies': dependencies,
    }


def main():
    parser = argparse.ArgumentParser(description='Inspect Python source without running it.')
    parser.add_argument('project', type=Path, help='Folder containing Python source files')
    args = parser.parse_args()
    try:
        report = analyze_project(args.project)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
