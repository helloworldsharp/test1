import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from publish import promote


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init")
        git(self.root, "config", "user.name", "Fixture")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        (self.root / "rule-sources").mkdir()
        (self.root / "rule-sources/sources.json").write_text(json.dumps({"outputs":{"example":{}}}))
        (self.root / "rules/generated").mkdir(parents=True)
        (self.root / "rules/generated/example.yaml").write_text("old")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "baseline")
        self.candidate = self.root.parent / "candidate"
        self.candidate.mkdir()
        body = b"payload: ['DOMAIN,example.com']\n"
        (self.candidate / "example.yaml").write_bytes(body)
        (self.candidate / "sources.lock.json").write_text(json.dumps({"outputs":{"example":{"sha256":hashlib.sha256(body).hexdigest()}}}))

    def tearDown(self):
        self.temp.cleanup()

    def test_bad_hash_and_extra_file_leave_last_good_unchanged(self):
        (self.candidate / "example.yaml").write_text("corruption")
        with self.assertRaises(ValueError):
            promote(self.root, self.candidate)
        self.assertEqual((self.root / "rules/generated/example.yaml").read_text(), "old")
        self.assertEqual(git(self.root, "status", "--porcelain"), "")

    def test_existing_staged_work_is_not_swallowed(self):
        (self.root / "unrelated.txt").write_text("unrelated")
        git(self.root, "add", "unrelated.txt")
        with self.assertRaisesRegex(ValueError, "must be clean"):
            promote(self.root, self.candidate)
        self.assertEqual(git(self.root, "diff", "--cached", "--name-only"), "unrelated.txt")
        self.assertEqual((self.root / "rules/generated/example.yaml").read_text(), "old")

    def test_promotion_only_stages_data_without_making_a_commit(self):
        before = git(self.root, "rev-parse", "HEAD")
        self.assertEqual(set(promote(self.root, self.candidate)), {"rules/generated/example.yaml", "rules/generated/sources.lock.json"})
        self.assertEqual(git(self.root, "rev-parse", "HEAD"), before)


if __name__ == "__main__":
    unittest.main()
