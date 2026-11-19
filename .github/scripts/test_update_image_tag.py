import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("update_image_tag.py")
OLD = "1" * 40
NEW = "2" * 40
FIXTURE = f'''images:
  - name: backend-blue-image
    newName: harbor.skala-us.com/u3-2/backend
    newTag: "{OLD}"
  - name: backend-green-image
    newName: harbor.skala-us.com/u3-2/backend
    # Preserve this comment and the dormant slot.
    newTag: "{OLD}"
'''


class UpdateImageTagTests(unittest.TestCase):
    def run_editor(self, text, alias="backend-green-image", tag=NEW):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "kustomization.yaml"
            manifest.write_text(text)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(manifest), alias, tag],
                capture_output=True, text=True,
            )
            return result, manifest.read_text()

    def test_changes_only_the_named_image_and_preserves_formatting(self):
        result, actual = self.run_editor(FIXTURE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(actual, FIXTURE.rsplit(OLD, 1)[0] + NEW + FIXTURE.rsplit(OLD, 1)[1])

    def test_missing_or_duplicate_image_leaves_file_unchanged(self):
        for text, alias in [(FIXTURE, "missing-image"), (FIXTURE + FIXTURE, "backend-green-image")]:
            with self.subTest(alias=alias, duplicate=text != FIXTURE):
                result, actual = self.run_editor(text, alias)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(actual, text)

    def test_rejects_tags_that_are_not_full_commit_shas_without_writing(self):
        for tag in ["", "latest", "abc123", "2" * 39, "2" * 41, "$(touch unexpected)"]:
            with self.subTest(tag=tag):
                result, actual = self.run_editor(FIXTURE, tag=tag)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(actual, FIXTURE)

    def test_rejects_ambiguous_alias_variations_without_writing(self):
        for name in ['"backend-green-image"', 'backend-green-image # duplicate']:
            with self.subTest(name=name):
                duplicate = f'  - name: {name}\n    newTag: "{OLD}"\n'
                text = FIXTURE.replace("images:\n", "images:\n" + duplicate)
                result, actual = self.run_editor(text)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(actual, text)

    def test_ignores_similarly_named_entries_outside_images(self):
        prefix = f'other:\n  - name: backend-green-image\n    newTag: "{OLD}"\n'
        result, actual = self.run_editor(prefix + FIXTURE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(actual, prefix + FIXTURE.rsplit(OLD, 1)[0] + NEW + FIXTURE.rsplit(OLD, 1)[1])


if __name__ == "__main__":
    unittest.main()
