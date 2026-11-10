from itertools import product
import random
import unittest

from app.graph import analyze_graph, circular_groups


def edges(*pairs):
    return [{'source': source, 'target': target} for source, target in pairs]


class GraphTests(unittest.TestCase):
    def test_seeded_larger_graphs_against_transitive_closure(self):
        randomizer = random.Random(583)
        names = [str(number) for number in range(8)]
        for _ in range(200):
            pairs = [(a, b) for a in names for b in names if randomizer.random() < .18]
            reachable = set(pairs)
            for middle in names:
                for source in names:
                    for target in names:
                        if (source, middle) in reachable and (middle, target) in reachable:
                            reachable.add((source, target))
            result = analyze_graph(names, edges(*pairs))
            for target in names:
                impact = result['impact'][target]
                actual = set(impact['direct_dependents'] + impact['indirect_dependents'])
                expected = {source for source in names if source != target and (source, target) in reachable}
                self.assertEqual(actual, expected)
                self.assertEqual(impact['affected_count'], len(expected))
            expected_groups = set()
            for node in names:
                mutual = frozenset(other for other in names if (node, other) in reachable and (other, node) in reachable)
                if mutual:
                    expected_groups.add(mutual)
            self.assertEqual({frozenset(group) for group in result['circular_dependency_groups']}, expected_groups)

    def test_chain_impact_follows_importers_not_imports(self):
        result = analyze_graph(['main.py', 'auth.py', 'database.py', 'alone.py'], edges(
            ('main.py', 'auth.py'), ('auth.py', 'database.py'),
        ))
        self.assertEqual(result['impact']['database.py'], {
            'direct_dependents': ['auth.py'], 'indirect_dependents': ['main.py'], 'affected_count': 2,
        })
        self.assertEqual(result['impact']['main.py']['affected_count'], 0)
        self.assertEqual(result['impact']['alone.py']['affected_count'], 0)
        self.assertEqual(len(result['graph']['nodes']), 4)
        auth = next(node for node in result['graph']['nodes'] if node['id'] == 'auth.py')
        self.assertEqual(auth['dependencies'], ['database.py'])
        self.assertEqual(auth['imported_by'], ['main.py'])

    def test_diamond_deduplicates_and_direct_wins_over_indirect(self):
        result = analyze_graph(['a', 'b', 'c', 'd'], edges(
            ('a', 'b'), ('a', 'c'), ('b', 'd'), ('c', 'd'), ('a', 'd'), ('a', 'd'),
        ))
        self.assertEqual(result['impact']['d'], {
            'direct_dependents': ['a', 'b', 'c'], 'indirect_dependents': [], 'affected_count': 3,
        })
        self.assertEqual(len(result['graph']['edges']), 5)

    def test_cycles_group_members_without_incoming_or_outgoing_neighbors(self):
        result = analyze_graph(['a', 'b', 'c', 'outside', 'leaf', 'x', 'y'], edges(
            ('a', 'b'), ('b', 'c'), ('c', 'a'), ('outside', 'a'), ('c', 'leaf'), ('x', 'y'), ('y', 'x'),
        ))
        self.assertEqual(result['circular_dependency_groups'], [['a', 'b', 'c'], ['x', 'y']])
        self.assertEqual(result['impact']['a'], {
            'direct_dependents': ['c', 'outside'], 'indirect_dependents': ['b'], 'affected_count': 3,
        })
        self.assertNotIn('a', result['impact']['a']['indirect_dependents'])

    def test_empty_self_loop_and_unknown_endpoint(self):
        self.assertEqual(analyze_graph([], [])['graph'], {'nodes': [], 'edges': []})
        result = analyze_graph(['a'], edges(('a', 'a')))
        self.assertEqual(result['circular_dependency_groups'], [['a']])
        self.assertEqual(result['impact']['a']['affected_count'], 0)
        with self.assertRaises(ValueError):
            analyze_graph(['a'], edges(('a', 'missing')))

    def test_deterministic_results(self):
        links = edges(('c', 'a'), ('b', 'c'), ('a', 'b'))
        self.assertEqual(analyze_graph(['a', 'b', 'c'], links), analyze_graph(['c', 'b', 'a'], links[::-1]))

    def test_large_circular_group_avoids_recursion_limit(self):
        names = [str(index) for index in range(1500)]
        forward = {name: {names[(index + 1) % len(names)]} for index, name in enumerate(names)}
        reverse = {name: {names[(index - 1) % len(names)]} for index, name in enumerate(names)}
        self.assertEqual(circular_groups(forward, reverse), [sorted(names)])

    def test_all_three_node_graphs_against_reachability_reference(self):
        # Independent transitive-closure oracle checks all 64 directed graphs
        # without self edges, including disconnected and overlapping cycles.
        names = ['a', 'b', 'c']
        possible = [(a, b) for a in names for b in names if a != b]
        for flags in product([False, True], repeat=len(possible)):
            selected = [pair for pair, enabled in zip(possible, flags) if enabled]
            reachable = set(selected)
            for middle in names:
                for source in names:
                    for target in names:
                        if (source, middle) in reachable and (middle, target) in reachable:
                            reachable.add((source, target))
            result = analyze_graph(names, edges(*selected))
            for target in names:
                expected = {source for source in names if source != target and (source, target) in reachable}
                impact = result['impact'][target]
                self.assertEqual(set(impact['direct_dependents'] + impact['indirect_dependents']), expected)
            for a in names:
                for b in names:
                    if a == b:
                        continue
                    same_group = any(a in group and b in group for group in result['circular_dependency_groups'])
                    self.assertEqual(same_group, (a, b) in reachable and (b, a) in reachable)


if __name__ == '__main__':
    unittest.main()
