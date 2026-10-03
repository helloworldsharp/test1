import json
import tempfile
import unittest
from pathlib import Path

import updater


class UpdaterTests(unittest.TestCase):
    def test_only_explicit_ip_source_can_request_resolution(self):
        body = b"1.2.4.0/24\n2001:db8::/32\n"
        self.assertEqual(updater.parse(body, "text", "ipcidr"), ["IP-CIDR,1.2.4.0/24,no-resolve"])
        self.assertEqual(updater.parse(body, "text", "ipcidr", no_resolve=False), ["IP-CIDR,1.2.4.0/24"])

    def test_preserves_regex_commas_and_rejects_unknown_types(self):
        rules = updater.parse(b"payload:\n - 'DOMAIN-REGEX,^x[0-9]{1,3}\\.com$'\n", "yaml", "classical")
        self.assertEqual(rules, [r"DOMAIN-REGEX,^x[0-9]{1,3}\.com$"])
        with self.assertRaisesRegex(ValueError, "unsupported rule type"):
            updater.parse(b"payload: ['UNKNOWN,example.com']", "yaml", "classical")

    def test_filters_address_family_preserving_source_and_no_resolve(self):
        rules = updater.parse(b"payload: ['IP-CIDR6,::/0', 'SRC-IP-CIDR,192.0.2.1/32', 'IP-CIDR,1.2.3.4/32,no-resolve']", "yaml", "classical")
        self.assertEqual(rules, ["SRC-IP-CIDR,192.0.2.1/32", "IP-CIDR,1.2.3.4/32,no-resolve"])
        with self.assertRaises(ValueError):
            updater.parse(b"payload: ['IP-CIDR,not-an-ip']", "yaml", "classical")

    def test_duplicate_keys_empty_and_html_fail(self):
        for body in [b"payload: []", b"payload: [x]\npayload: [y]", b"<html>error</html>"]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                updater.parse(body, "yaml", "classical")

    def fixture(self, root):
        (root / "rule-sources").mkdir()
        source = {"repo":"example/rules", "ref":"main", "path":"a.list", "format":"text", "behavior":"classical"}
        (root / "rule-sources/sources.json").write_text(json.dumps({"sources":{"a":source, "b":{**source, "path":"b.list"}},
            "outputs":{"combined":{"parts":[{"source":"a"},{"source":"b"}]}}}))
        (root / "rule-sources/overrides.json").write_text("{}")
        def fetch(url):
            if "/commits/" in url:
                return json.dumps({"sha":"a" * 40}).encode()
            return b"DOMAIN-SUFFIX,example.com\nIP-CIDR,1.2.3.4/32,no-resolve"
        return fetch

    def test_one_revision_per_repository_reproducible_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delegate = self.fixture(root)
            urls = []
            def fetch(url):
                urls.append(url)
                return delegate(url)
            updater.build(root, root / "first", fetch)
            self.assertEqual(sum("/commits/" in url for url in urls), 1)
            updater.build(root, root / "second", delegate)
            self.assertEqual((root / "first/combined.yaml").read_bytes(), (root / "second/combined.yaml").read_bytes())
            with self.assertRaisesRegex(ValueError, "must not already exist"):
                updater.build(root, root / "first", delegate)

    def test_failed_source_cannot_publish_partial_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delegate = self.fixture(root)
            def fetch(url):
                if url.endswith("b.list"):
                    raise TimeoutError("controlled download failure")
                return delegate(url)
            with self.assertRaises(TimeoutError):
                updater.build(root, root / "candidate", fetch)
            self.assertFalse((root / "candidate").exists())

    def test_large_deletion_is_rejected_without_changing_baseline(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fetch = self.fixture(root)
            baseline = root / "rules/generated/combined.yaml"
            baseline.parent.mkdir(parents=True)
            body = ("payload:\n" + "".join(f" - DOMAIN,old{i}.example\n" for i in range(100))).encode()
            baseline.write_bytes(body)
            with self.assertRaisesRegex(ValueError, "abnormal deletion"):
                updater.build(root, root / "candidate", fetch)
            self.assertEqual(baseline.read_bytes(), body)
            self.assertFalse((root / "candidate").exists())


if __name__ == "__main__":
    unittest.main()
