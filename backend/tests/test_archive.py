from dataclasses import replace
import io
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
import zipfile

from app.archive import LIMITS, extract_archive, select_source_root
from app.input_errors import InputError


def zip_bytes(sources):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, source in sources.items():
            archive.writestr(name, source)
    return stream.getvalue()


class ArchiveTests(unittest.TestCase):
    def extract(self, data, root, limits=LIMITS):
        archive = root / 'input.zip'
        archive.write_bytes(data)
        return extract_archive(archive, root / 'source', limits)

    def test_safe_archive_and_wrapper_source_selection(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            extracted = self.extract(zip_bytes({'project/src/main.py': 'def hello(): pass\n', 'project/README.md': 'Hi'}), root)
            chosen, relative = select_source_root(extracted, 'src')
            self.assertEqual(chosen, extracted / 'project/src')
            self.assertEqual(relative, 'src')
            with self.assertRaises(InputError):
                select_source_root(extracted, '../outside')
            with self.assertRaises(InputError):
                select_source_root(extracted, 'missing')

    def test_user_package_is_kept_but_github_wrapper_is_removed(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            extracted = self.extract(zip_bytes({'pkg/__init__.py': '', 'pkg/child.py': ''}), root)
            self.assertEqual(select_source_root(extracted)[0], extracted)
            self.assertEqual(select_source_root(extracted, strip_wrapper=True)[0], extracted / 'pkg')

    def test_unsafe_names_are_rejected_without_writing_outside(self):
        for name in ['../escape.py', '/absolute.py', 'C:/drive.py', 'folder\\escape.py', 'folder/../escape.py',
                     'folder//file.py', 'CON.py', 'space /main.py', 'folder./main.py', 'x:stream.py']:
            with self.subTest(name=name), TemporaryDirectory() as folder:
                root = Path(folder)
                data = zip_bytes({name: ''})
                if '\\' in name:
                    # ZipInfo normalizes Windows separators on creation. Put
                    # the hostile bytes into both ZIP headers explicitly.
                    data = data.replace(name.replace('\\', '/').encode(), name.encode())
                with self.assertRaises(InputError):
                    self.extract(data, root)
                self.assertFalse((root / 'escape.py').exists())

    def test_symlinks_and_special_files_rejected(self):
        for mode in [stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o600]:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as zipped:
                info = zipfile.ZipInfo('link.py')
                info.create_system = 3
                info.external_attr = mode << 16
                zipped.writestr(info, '../outside.py')
            with TemporaryDirectory() as folder, self.assertRaises(InputError):
                self.extract(stream.getvalue(), Path(folder))

    def test_duplicates_conflicting_cases_and_nested_archives_rejected(self):
        for sources in [
            {'main.py': '', 'MAIN.py': ''}, {'Pkg/a.py': '', 'pkg/b.py': ''},
            {'inner.zip': 'not extracted'}, {'item': '', 'item/child.py': ''},
        ]:
            with TemporaryDirectory() as folder, self.assertRaises(InputError):
                self.extract(zip_bytes(sources), Path(folder))

    def test_all_input_limits(self):
        data = zip_bytes({'main.py': 'x' * 100})
        for limits in [replace(LIMITS, archive_bytes=1), replace(LIMITS, extracted_bytes=50),
                       replace(LIMITS, entries=0), replace(LIMITS, python_files=0),
                       replace(LIMITS, python_file_bytes=50), replace(LIMITS, depth=0)]:
            with TemporaryDirectory() as folder, self.assertRaises(InputError) as caught:
                self.extract(data, Path(folder), limits)
            self.assertEqual(caught.exception.status, 413)

    def test_corrupt_and_encrypted_zip(self):
        data = bytearray(zip_bytes({'main.py': ''}))
        # Mark the central directory entry encrypted without executing any input.
        central = data.index(b'PK\x01\x02')
        data[central + 8] |= 1
        for payload in [b'not a ZIP', bytes(data)]:
            with TemporaryDirectory() as folder, self.assertRaises(InputError):
                self.extract(payload, Path(folder))
