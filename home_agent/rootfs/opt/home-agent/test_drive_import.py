"""Local unit tests for Drive folder authorization (no Google credentials)."""
import unittest
from unittest.mock import patch
import drive_import


class DriveAuthorizationTests(unittest.TestCase):
    def test_child_of_root(self):
        entries = {"file": {"id": "file", "parents": ["folder"]},
                   "folder": {"id": "folder", "parents": ["root"]}}
        with patch.object(drive_import, "metadata", side_effect=lambda file_id, token: entries[file_id]):
            self.assertTrue(drive_import.assert_under_shared_root("file", "root", "test-token"))

    def test_outside_root(self):
        entries = {"file": {"id": "file", "parents": ["other"]},
                   "other": {"id": "other", "parents": []}}
        with patch.object(drive_import, "metadata", side_effect=lambda file_id, token: entries[file_id]):
            with self.assertRaises(drive_import.DriveImportError):
                drive_import.assert_under_shared_root("file", "root", "test-token"))

    def test_parent_cycle(self):
        entries = {"file": {"id": "file", "parents": ["other"]},
                   "other": {"id": "other", "parents": ["file"]}}
        with patch.object(drive_import, "metadata", side_effect=lambda file_id, token: entries[file_id]):
            with self.assertRaises(drive_import.DriveImportError):
                drive_import.assert_under_shared_root("file", "root", "test-token")

    def test_root_not_file(self):
        with self.assertRaises(drive_import.DriveImportError):
            drive_import.assert_under_shared_root("root", "root", "test-token")


if __name__ == "__main__":
    unittest.main()
