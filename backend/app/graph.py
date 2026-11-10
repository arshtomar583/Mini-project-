"""Analyze a directed file map: A -> B means A imports B."""

from collections import deque


def circular_groups(dependencies: dict[str, set[str]], importers: dict[str, set[str]]) -> list[list[str]]:
    """Find strongly connected groups with two iterative graph walks.

    A group is circular when every member can reach every other member. We
    report groups rather than enumerate every circular route within a group.
    Iterative walks avoid Python's recursion limit on long import chains.
    """
    visited = set()
    finished = []
    for start in sorted(dependencies):
        if start in visited:
            continue
        visited.add(start)
        stack = [(start, iter(sorted(dependencies[start])))]
        while stack:
            node, neighbors = stack[-1]
            following = next(neighbors, None)
            if following is None:
                finished.append(node)
                stack.pop()
            elif following not in visited:
                visited.add(following)
                stack.append((following, iter(sorted(dependencies[following]))))

    visited = set()
    groups = []
    for start in reversed(finished):
        if start in visited:
            continue
        members = []
        visited.add(start)
        pending = [start]
        while pending:
            node = pending.pop()
            members.append(node)
            for following in sorted(importers[node]):
                if following not in visited:
                    visited.add(following)
                    pending.append(following)
        if len(members) > 1 or start in dependencies[start]:
            groups.append(sorted(members))
    return sorted(groups)


def analyze_graph(paths: list[str], edges: list[dict]) -> dict:
    """Build file details, potential impact for each file, and circular groups.

    Isolated files remain nodes. Unknown edge endpoints are rejected instead of
    inventing files. Results are sorted so repeated analysis is reproducible.
    """
    dependencies = {path: set() for path in sorted(set(paths))}
    importers = {path: set() for path in dependencies}
    for edge in edges:
        source, target = edge['source'], edge['target']
        if source not in dependencies or target not in dependencies:
            raise ValueError('Dependency edge references a file outside the analyzed file list.')
        dependencies[source].add(target)
        importers[target].add(source)

    nodes = []
    impact = {}
    for path in dependencies:
        nodes.append({
            'id': path,
            'dependencies': sorted(dependencies[path]),
            'imported_by': sorted(importers[path]),
        })
        # Walk incoming arrows, not outgoing imports. Start with the selected
        # file already visited so a cycle cannot add it to its own impact list.
        visited = {path}
        pending = deque([path])
        while pending:
            node = pending.popleft()
            for importer in sorted(importers[node]):
                if importer not in visited:
                    visited.add(importer)
                    pending.append(importer)
        affected = visited - {path}
        direct = importers[path] - {path}
        impact[path] = {
            'direct_dependents': sorted(direct),
            'indirect_dependents': sorted(affected - direct),
            'affected_count': len(affected),
        }

    return {
        'graph': {
            'nodes': nodes,
            'edges': [
                {'source': source, 'target': target}
                for source in dependencies for target in sorted(dependencies[source])
            ],
        },
        'impact': impact,
        'circular_dependency_groups': circular_groups(dependencies, importers),
    }
