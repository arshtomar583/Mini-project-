"""Run the command as a user would, including its output and exit codes."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


BACKEND = Path(__file__).resolve().parents[1]
EXAMPLES = BACKEND.parent / 'examples'


class CommandTests(unittest.TestCase):
    def run_command(self, *arguments):
        return subprocess.run(
            [sys.executable, '-m', 'app.analyzer', *map(str, arguments)],
            cwd=BACKEND, capture_output=True, text=True, timeout=15,
        )

    def test_focused_json_and_readable_output(self):
        result = self.run_command(EXAMPLES / 'demo_project', '--impact', 'database.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['file'], 'database.py')
        self.assertEqual(report['impact']['indirect_dependents'], ['main.py'])
        text = self.run_command(EXAMPLES / 'demo_project', '--format', 'text', '--impact', 'database.py')
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn('Direct dependents: auth.py', text.stdout)
        self.assertIn('Indirect dependents: main.py', text.stdout)

    def test_invalid_folder_or_selection_exits_with_friendly_error(self):
        for arguments in [
            [EXAMPLES / 'missing'],
            [EXAMPLES / 'demo_project', '--impact', 'missing.py'],
        ]:
            result = self.run_command(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertIn('error:', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_partial_and_empty_reports_have_correct_exit_status(self):
        with TemporaryDirectory() as directory:
            empty = self.run_command(directory)
            self.assertEqual(empty.returncode, 0, empty.stderr)
            self.assertEqual(json.loads(empty.stdout)['graph']['nodes'], [])
            Path(directory, 'broken.py').write_text('def broken(:\n')
            Path(directory, 'valid.py').write_text('def valid(): pass\n')
            partial = self.run_command(directory)
            self.assertEqual(partial.returncode, 1, partial.stderr)
            report = json.loads(partial.stdout)
            self.assertEqual(report['analysis_status'], 'partial')
            self.assertEqual(report['graph']['nodes'][0]['id'], 'valid.py')
            self.assertEqual(report['summary']['files_found'], 2)

    def test_circular_example_complete_report(self):
        result = self.run_command(EXAMPLES / 'circular_project')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['circular_dependency_groups'], [['alpha.py', 'beta.py']])
        self.assertEqual(report['summary']['circular_dependency_groups'], 1)
        self.assertEqual(report['summary']['files_in_circular_groups'], 2)
        self.assertEqual(len(report['graph']['nodes']), 4)


if __name__ == '__main__':
    unittest.main()
