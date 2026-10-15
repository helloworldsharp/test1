import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import updater


class UpdaterTests(unittest.TestCase):
    def test_rate_limit_waits_for_server_deadline(self):
        url = "https://api.github.com/repos/example/rules/commits/main"
        for status in (403, 429):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(url, status, "rate limit exceeded",
                    {"Retry-After": "5", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1012"}, None)
                with patch.object(updater.urllib.request, "urlopen", side_effect=[error, io.BytesIO(b"rules")]) as request, \
                     patch.object(updater.time, "time", return_value=1000), \
                     patch.object(updater.time, "sleep") as sleep:
                    self.assertEqual(updater.download(url), b"rules")
                    sleep.assert_called_once_with(13)
                    self.assertEqual(request.call_count, 2)

    def test_rate_limit_without_deadline_backs_off_with_bounded_wait(self):
        url = "https://api.github.com/repos/example/rules/commits/main"
        for status, reason in ((403, "rate limit exceeded"), (429, "Too Many Requests")):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(url, status, reason, {}, None)
                with patch.object(updater.urllib.request, "urlopen", side_effect=error) as request, \
                     patch.object(updater.time, "sleep") as sleep:
                    with self.assertRaisesRegex(RuntimeError, "wait budget"):
                        updater.download(url)
                    sleep.assert_called_once_with(60)
                    self.assertEqual(request.call_count, 2)

    def test_long_rate_limit_fails_without_early_retry(self):
        url = "https://api.github.com/repos/example/rules/commits/main"
        error = urllib.error.HTTPError(url, 403, "Forbidden",
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "4600"}, None)
        with patch.object(updater.urllib.request, "urlopen", side_effect=error) as request, \
             patch.object(updater.time, "time", return_value=1000), \
             patch.object(updater.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "https://api.github.com/.*4600"):
                updater.download(url)
            request.assert_called_once()
            sleep.assert_not_called()

    def test_permanent_http_errors_are_not_retried(self):
        url = "https://raw.githubusercontent.com/example/rules/main/a.list"
        for status in (403, 404):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(url, status, "Forbidden", {}, None)
                with patch.object(updater.urllib.request, "urlopen", side_effect=error) as request, \
                     patch.object(updater.time, "sleep") as sleep:
                    with self.assertRaisesRegex(RuntimeError, str(status)):
                        updater.download(url)
                    request.assert_called_once()
                    sleep.assert_not_called()

    def test_transient_http_and_network_errors_can_recover(self):
        url = "https://raw.githubusercontent.com/example/rules/main/a.list"
        errors = [urllib.error.HTTPError(url, 503, "Unavailable", {}, None),
                  urllib.error.URLError("connection reset"), io.BytesIO(b"rules")]
        with patch.object(updater.urllib.request, "urlopen", side_effect=errors), \
             patch.object(updater.time, "sleep") as sleep:
            self.assertEqual(updater.download(url), b"rules")
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_official_voice_prefixes_are_ipv4_no_resolve_and_deduplicated(self):
        body = json.dumps({"creationTime": "2026-03-26", "prefixes": [
            {"ipv4Prefix": "102.37.57.54/32"}, {"ipv6Prefix": "2001:db8::/32"},
            {"ipv4Prefix": "102.37.57.54/32"}]}).encode()
        self.assertEqual(updater.parse(body, "json-prefixes", "ipcidr"),
                         ["IP-CIDR,102.37.57.54/32,no-resolve"])

    def test_malformed_official_voice_data_fails_closed(self):
        for data in [{}, {"prefixes": []}, {"prefixes": [{}]},
                     {"prefixes": [{"ipv4Prefix": "not-an-ip"}]},
                     {"prefixes": [{"ipv4Prefix": "2001:db8::/32"}]},
                     {"prefixes": [{"ipv6Prefix": "192.0.2.1/32"}]},
                     {"prefixes": [{"ipv4Prefix": "192.0.2.1"}]},
                     {"prefixes": [{"ipv4Prefix": "192.0.2.1/24"}]},
                     {"prefixes": [{"ipv4Prefix": "192.0.2.1/32", "unknown": True}]}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                updater.parse(json.dumps(data).encode(), "json-prefixes", "ipcidr")
        with self.assertRaises(ValueError):
            updater.parse(b'{"prefixes":[{"ipv4Prefix":"192.0.2.1/32"}]}', "json-prefixes", "classical")

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

    def test_malformed_voice_source_cannot_publish_partial_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delegate = self.fixture(root)
            path = root / "rule-sources/sources.json"
            manifest = json.loads(path.read_text())
            manifest["sources"]["b"].update(format="json-prefixes", behavior="ipcidr")
            path.write_text(json.dumps(manifest))
            def fetch(url):
                return b'{"prefixes":[{"ipv4Prefix":"bad"}]}' if url.endswith("b.list") else delegate(url)
            with self.assertRaises(ValueError):
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
