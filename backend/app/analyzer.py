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
from app.graph import analyze_graph


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
    files_found = 0

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
            files_found += 1
            try:
                files.append(analyze_file(path, root))
            except (SyntaxError, UnicodeError, OSError, RecursionError) as error:
                errors.append({
                    'path': path.relative_to(root).as_posix(),
                    'type': type(error).__name__,
                    'message': (
                        error.msg if isinstance(error, SyntaxError)
                        else 'Python source nesting is too deep.' if isinstance(error, RecursionError)
                        else 'Cannot read Python source.'
                    ),
                    'line': getattr(error, 'lineno', None),
                })

    files.sort(key=lambda item: item['path'])
    errors.sort(key=lambda item: item['path'])
    dependencies = resolve_dependencies(files)
    graph_analysis = analyze_graph([file['path'] for file in files], dependencies['edges'])
    groups = graph_analysis['circular_dependency_groups']
    return {
        'schema_version': 3,
        'analysis_status': 'partial' if errors else 'complete',
        'summary': {
            'files_found': files_found,
            'files_analyzed': len(files),
            'functions': sum(len(file['functions']) for file in files),
            'classes': sum(len(file['classes']) for file in files),
            'import_statements': sum(len(file['imports']) for file in files),
            'errors': len(errors),
            'local_dependencies': len(dependencies['edges']),
            'unresolved_imports': sum(item['status'] != 'local' for item in dependencies['imports']),
            'circular_dependency_groups': len(groups),
            'files_in_circular_groups': sum(len(group) for group in groups),
        },
        'files': files,
        'errors': errors,
        'dependencies': dependencies,
        **graph_analysis,
    }


def text_report(report: dict, selected_file: str | None = None) -> str:
    """A readable local view of the same data the website will consume."""
    summary = report['summary']
    lines = [
        'Explain This Codebase - analysis engine v1',
        f"Analysis: {report['analysis_status']}",
        f"Python files analyzed: {summary['files_analyzed']} of {summary['files_found']}",
        f"Functions: {summary['functions']} | Classes: {summary['classes']}",
        f"Local file connections: {summary['local_dependencies']}",
        f"Unresolved import names: {summary['unresolved_imports']}",
        '', 'File connections (A -> B means A imports B):',
    ]
    lines.extend(f"  {edge['source']} -> {edge['target']}" for edge in report['graph']['edges'])
    if not report['graph']['edges']:
        lines.append('  No connections found. Files are still included in the graph.')
    if selected_file is not None:
        result = report['impact'][selected_file]
        lines.extend([
            '', f'Potential impact of changing {selected_file}:',
            '  Direct dependents: ' + (', '.join(result['direct_dependents']) or 'none'),
            '  Indirect dependents: ' + (', '.join(result['indirect_dependents']) or 'none'),
            f"  Other files potentially affected: {result['affected_count']}",
        ])
    lines.extend(['', f"Circular dependency groups: {summary['circular_dependency_groups']}"])
    lines.extend('  ' + ', '.join(group) for group in report['circular_dependency_groups'])
    if report['errors']:
        lines.append('\nFiles or folders that could not be analyzed:')
        lines.extend(f"  {error['path']}: {error['message']}" for error in report['errors'])
    lines.append('\nThese are possible import relationships, not guaranteed breakages or execution order.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Inspect Python source without running it.')
    parser.add_argument('project', type=Path, help='Folder containing Python source files')
    parser.add_argument('--format', choices=['json', 'text'], default='json', help='Output format (default: json)')
    parser.add_argument('--impact', help='Relative Python file path to inspect, e.g. database.py')
    args = parser.parse_args()
    try:
        report = analyze_project(args.project)
    except ValueError as error:
        parser.error(str(error))
    selected_file = args.impact.replace('\\', '/') if args.impact is not None else None
    if selected_file is not None and selected_file not in report['impact']:
        parser.error('Selected file was not successfully analyzed. Use a relative path from the report.')
    if args.format == 'text':
        print(text_report(report, selected_file))
    else:
        output = report if selected_file is None else {
            'schema_version': report['schema_version'],
            'analysis_status': report['analysis_status'],
            'file': selected_file,
            'impact': report['impact'][selected_file],
            'errors': report['errors'],
        }
        print(json.dumps(output, indent=2, ensure_ascii=True))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
