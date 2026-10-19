import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import stem_organizer_app as app  # noqa: E402


class AppTest(unittest.TestCase):
    def test_finds_fl_folder_in_onedrive_first(self):
        home = tempfile.mkdtemp()
        onedrive = os.path.join(home, "OneDrive")
        os.makedirs(os.path.join(onedrive, "Documents", "Image-Line", "FL Studio"))
        os.makedirs(os.path.join(home, "Documents", "Image-Line", "FL Studio"))
        target = app.find_fl_hardware_dir(home, {"OneDrive": onedrive})
        self.assertEqual(target, os.path.join(onedrive, "Documents", app.FL_SUBPATH))

    def test_spanish_documents_folder_and_missing(self):
        home = tempfile.mkdtemp()
        self.assertIsNone(app.find_fl_hardware_dir(home, {}))
        os.makedirs(os.path.join(home, "Documentos", "Image-Line", "FL Studio"))
        self.assertTrue(app.find_fl_hardware_dir(home, {}).startswith(
            os.path.join(home, "Documentos")))

    def test_install_copies_bundled_script(self):
        target = os.path.join(tempfile.mkdtemp(), "Hardware", app.APP_NAME)
        dest = app.install_script(target)
        with open(dest) as f:
            self.assertIn("# name=Stem Organizer", f.read())


if __name__ == "__main__":
    unittest.main()
