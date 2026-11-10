"""Behavior checks using Python's built-in test framework."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.analyzer import analyze_project


class AnalyzerTests(unittest.TestCase):
    def test_demo_project(self):
        root = Path(__file__).resolve().parents[2] / 'examples' / 'demo_project'
        result = analyze_project(root)
        self.assertEqual(result['summary'], {
            'files_found': 3, 'files_analyzed': 3, 'functions': 3,
            'classes': 0, 'import_statements': 2, 'errors': 0,
            'local_dependencies': 2, 'unresolved_imports': 0,
            'circular_dependency_groups': 0, 'files_in_circular_groups': 0,
        })
        auth = next(file for file in result['files'] if file['path'] == 'auth.py')
        self.assertEqual(auth['imports'][0]['module'], 'database')
        self.assertEqual(auth['functions'][0]['name'], 'login')
        self.assertEqual(result['schema_version'], 3)
        self.assertEqual(result['analysis_status'], 'complete')
        self.assertEqual(result['impact']['database.py'], {
            'direct_dependents': ['auth.py'], 'indirect_dependents': ['main.py'], 'affected_count': 2,
        })

    def test_scopes_async_aliases_and_relative_imports(self):
        with TemporaryDirectory() as folder:
            Path(folder, 'sample.py').write_text(
                'import os as operating_system\n'
                'from . import helpers\n'
                'class User:\n'
                '    """A user."""\n'
                '    async def save(self):\n'
                '        from ..database import query as lookup\n'
                '        def nested():\n'
                '            pass\n', encoding='utf-8')
            result = analyze_project(folder)['files'][0]
            self.assertEqual(result['classes'][0]['docstring'], 'A user.')
            self.assertEqual(result['functions'][0]['qualified_name'], 'User.save')
            self.assertTrue(result['functions'][0]['is_async'])
            self.assertEqual(result['functions'][1]['qualified_name'], 'User.save.nested')
            self.assertEqual(result['functions'][0]['line'], 5)
            self.assertEqual(result['imports'][0]['names'][0]['alias'], 'operating_system')
            self.assertEqual(result['imports'][1]['level'], 1)
            self.assertIsNone(result['imports'][1]['module'])
            self.assertEqual(result['imports'][2]['level'], 2)
            self.assertEqual(result['imports'][2]['scope'], 'User.save')

    def test_invalid_files_do_not_stop_valid_files_and_code_is_not_executed(self):
        with TemporaryDirectory() as folder:
            Path(folder, 'valid.py').write_text('raise RuntimeError("Do not run me")\ndef safe(): pass\n')
            Path(folder, 'broken.py').write_text('def broken(:\n')
            Path(folder, 'bad_encoding.py').write_bytes(b'\xff')
            result = analyze_project(folder)
            self.assertEqual(result['summary']['files_found'], 3)
            self.assertEqual(result['summary']['files_analyzed'], 1)
            self.assertEqual(result['summary']['errors'], 2)
            self.assertEqual(result['analysis_status'], 'partial')
            self.assertEqual(result['files'][0]['functions'][0]['name'], 'safe')

    def test_ignored_folders_and_non_python_files(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.venv').mkdir()
            (root / '.venv' / 'ignored.py').write_text('def ignored(): pass\n')
            (root / 'package').mkdir()
            (root / 'package' / 'module.py').write_text('def included(): pass\n')
            (root / 'notes.txt').write_text('not python')
            result = analyze_project(root)
            self.assertEqual([file['path'] for file in result['files']], ['package/module.py'])

    def test_encoding_cookie_empty_folder_and_missing_directory(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(analyze_project(root)['summary']['files_found'], 0)
            (root / 'encoded.py').write_bytes('# coding: latin-1\n# café\ndef hello(): pass\n'.encode('latin-1'))
            self.assertEqual(analyze_project(root)['summary']['functions'], 1)
            with self.assertRaises(ValueError):
                analyze_project(root / 'missing')


if __name__ == '__main__':
    unittest.main()
