from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.analyzer import analyze_project


class DependencyTests(unittest.TestCase):
    def analyze_sources(self, sources):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            return analyze_project(root)

    def edge_pairs(self, report):
        return {(edge['source'], edge['target']) for edge in report['dependencies']['edges']}

    def test_demo_edges(self):
        root = Path(__file__).resolve().parents[2] / 'examples/demo_project'
        self.assertEqual(self.edge_pairs(analyze_project(root)), {
            ('main.py', 'auth.py'), ('auth.py', 'database.py'),
        })

    def test_aliases_duplicate_imports_and_unresolved_names(self):
        report = self.analyze_sources({
            'main.py': 'import database as db\nfrom database import query\nimport os\nimport missing\n',
            'database.py': 'def query(): pass\n',
        })
        self.assertEqual(self.edge_pairs(report), {('main.py', 'database.py')})
        imports = report['dependencies']['imports']
        self.assertEqual([item['status'] for item in imports], ['local', 'local', 'unresolved', 'unresolved'])
        self.assertEqual(imports[0]['alias'], 'db')
        self.assertEqual(report['summary']['unresolved_imports'], 2)

    def test_relative_imports_and_package_initializers(self):
        report = self.analyze_sources({
            'pkg/__init__.py': 'from . import service\n',
            'pkg/service.py': 'from .database import query\nfrom . import database\n',
            'pkg/database.py': 'def query(): pass\n',
            'main.py': 'import pkg.service\n',
        })
        edges = self.edge_pairs(report)
        self.assertIn(('main.py', 'pkg/__init__.py'), edges)
        self.assertIn(('main.py', 'pkg/service.py'), edges)
        self.assertIn(('pkg/service.py', 'pkg/database.py'), edges)
        self.assertIn(('pkg/__init__.py', 'pkg/service.py'), edges)
        self.assertNotIn(('pkg/__init__.py', 'pkg/__init__.py'), edges)
        self.assertEqual(report['summary']['unresolved_imports'], 0)

    def test_parent_relative_and_invalid_relative_do_not_match_top_level(self):
        report = self.analyze_sources({
            'pkg/sub/service.py': 'from .. import database\nfrom ... import database\n',
            'pkg/database.py': '',
            'database.py': '',
            'main.py': 'from . import database\n',
        })
        self.assertEqual(self.edge_pairs(report), {('pkg/sub/service.py', 'pkg/database.py')})
        statuses = [item['status'] for item in report['dependencies']['imports']]
        self.assertEqual(statuses.count('invalid_relative'), 2)

    def test_absolute_import_does_not_guess_sibling(self):
        report = self.analyze_sources({
            'pkg/service.py': 'import database\n',
            'pkg/database.py': '',
        })
        self.assertEqual(self.edge_pairs(report), set())
        self.assertEqual(report['dependencies']['imports'][0]['status'], 'unresolved')

    def test_namespace_package_and_wildcard(self):
        report = self.analyze_sources({
            'main.py': 'from pkg import database\nfrom pkg.database import *\nimport pkg\n',
            'pkg/database.py': 'value = 1\n',
        })
        self.assertEqual(self.edge_pairs(report), {('main.py', 'pkg/database.py')})
        self.assertEqual(report['dependencies']['imports'][2]['targets'], [])
        self.assertEqual(report['dependencies']['imports'][2]['status'], 'local')

    def test_module_package_collision_is_ambiguous(self):
        report = self.analyze_sources({
            'main.py': 'import data\nfrom data import child\nimport data.child\n',
            'data.py': '', 'data/__init__.py': '', 'data/child.py': '',
        })
        self.assertEqual(self.edge_pairs(report), set())
        self.assertTrue(all(item['status'] == 'ambiguous' for item in report['dependencies']['imports']))

    def test_unreadable_target_is_not_invented_and_dynamic_import_is_ignored(self):
        report = self.analyze_sources({
            'main.py': 'import broken\n__import__("other")\n',
            'broken.py': 'def (: pass\n',
            'other.py': '',
        })
        self.assertEqual(self.edge_pairs(report), set())
        self.assertEqual(report['summary']['errors'], 1)


if __name__ == '__main__':
    unittest.main()
