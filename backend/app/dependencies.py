"""Match imports against local files, without consulting or running Python imports."""

from collections import defaultdict
from pathlib import PurePosixPath


def resolve_dependencies(files: list[dict]) -> dict:
    """Treat the analyzed folder as the import root.

    Edges are possible static imports, not proof of execution. Names not found
    locally remain unresolved; we cannot distinguish missing code from libraries.
    """
    modules: dict[str, list[str]] = defaultdict(list)
    module_for_file = {}
    namespaces = set()
    for file in files:
        path = PurePosixPath(file['path'])
        parts = list(path.with_suffix('').parts)
        if parts[-1] == '__init__':
            parts.pop()
        # A dot inside a filename/directory is not a package separator. Such
        # files can still be parsed, but ordinary import syntax cannot name
        # that path. Do not invent edges by joining invalid path components.
        if any(not part.isidentifier() for part in parts):
            module_for_file[file['path']] = None
            continue
        module = '.'.join(parts)
        module_for_file[file['path']] = module
        if module:
            modules[module].append(file['path'])
        # Directories can be implicit namespace packages without __init__.py.
        for length in range(1, len(path.parts)):
            namespaces.add('.'.join(path.parts[:length]))

    def match(module):
        """Return candidate files, including package initializers on the path."""
        parts = module.split('.')
        targets = set()
        for length in range(1, len(parts) + 1):
            prefix = '.'.join(parts[:length])
            candidates = modules.get(prefix, [])
            if len(candidates) > 1:
                return set(), 'ambiguous'
            if length < len(parts):
                if not candidates and prefix not in namespaces:
                    return set(), 'unresolved'
                if candidates and not candidates[0].endswith('/__init__.py'):
                    return set(), 'unresolved'
                targets.update(candidates)
            elif candidates:
                targets.update(candidates)
            elif prefix not in namespaces:
                return set(), 'unresolved'
        return targets, 'local'

    resolutions = []
    edges = set()
    for file in files:
        source = file['path']
        own_module = module_for_file[source]
        package = (
            own_module if source.endswith('/__init__.py')
            else (own_module or '').rpartition('.')[0]
        )
        for statement in file['imports']:
            for binding in statement['names']:
                base = statement['module'] or ''
                level = statement['level']
                invalid_relative = False
                if level:
                    parts = package.split('.') if package else []
                    if level > len(parts):
                        invalid_relative = True
                    else:
                        parts = parts[:len(parts) - level + 1]
                        base = '.'.join([*parts, *([base] if base else [])])

                name = binding['name']
                requested = (
                    'import ' + name if statement['kind'] == 'import'
                    else 'from ' + '.' * level + (statement['module'] or '') + ' import ' + name
                )
                targets = set()
                status = 'invalid_relative' if invalid_relative else 'unresolved'
                if not invalid_relative:
                    if statement['kind'] == 'import':
                        targets, status = match(name)
                    else:
                        targets, status = match(base)
                        # `from pkg import child` can refer to a child module.
                        # It can also be a re-exported attribute; these are potential edges.
                        if status == 'local' and name != '*' and base in namespaces:
                            child_targets, child_status = match(base + '.' + name)
                            if child_status == 'ambiguous':
                                targets, status = set(), 'ambiguous'
                            elif child_status == 'local':
                                targets.update(child_targets)
                            elif base not in modules:
                                # A bare namespace has no __init__ to define
                                # attributes. A missing child is not a match.
                                targets = set()
                                status = 'unresolved'
                resolutions.append({
                    'source': source,
                    'line': statement['line'],
                    'scope': statement['scope'],
                    'requested': requested,
                    'alias': binding['alias'],
                    'status': status,
                    'targets': sorted(targets),
                })
                # The file graph represents relationships between different files.
                edges.update((source, target) for target in targets if target != source)

    return {
        'edges': [{'source': source, 'target': target} for source, target in sorted(edges)],
        'imports': resolutions,
    }
