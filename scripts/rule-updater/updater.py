"""Build a validated, unpublished rule candidate from public sources."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path

import yaml


class UniqueLoader(yaml.CSafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
MAX_BYTES = 16 * 1024 * 1024
TEXT_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX", "PROCESS-NAME"}
IP_TYPES = {"IP-CIDR", "IP-CIDR6", "SRC-IP-CIDR"}


def sha(body):
    return hashlib.sha256(body).hexdigest()


def download(url):
    if not url.startswith("https://"):
        raise ValueError("public sources must use HTTPS")
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "proxy-rule-updater/1"})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(MAX_BYTES + 1)
            if not body or len(body) > MAX_BYTES:
                raise ValueError("empty or oversized source")
            if body.lstrip().lower().startswith((b"<html", b"<!doctype")):
                raise ValueError("HTML response instead of rules")
            return body
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def parse(body, fmt, behavior, *, no_resolve=True):
    if not isinstance(no_resolve, bool) or (not no_resolve and behavior != "ipcidr"):
        raise ValueError("no_resolve=false is only supported for an ipcidr source")
    text = body.decode("utf-8-sig")
    if fmt == "yaml":
        data = yaml.load(text, Loader=UniqueLoader)
        if not isinstance(data, dict) or set(data) != {"payload"}:
            raise ValueError("source must contain only a payload mapping")
        values = data["payload"]
    elif fmt == "text":
        values = [line.strip() for line in text.splitlines()
                  if line.strip() and not line.lstrip().startswith(("#", ";", "//"))]
    else:
        raise ValueError(f"unsupported input format: {fmt}")
    if not isinstance(values, list) or not values:
        raise ValueError("source payload must be a non-empty list")
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip() or "\n" in value:
            raise ValueError("invalid rule value")
        value = value.strip()
        if behavior == "ipcidr":
            net = ipaddress.ip_network(value, strict=False)
            if net.version == 4:
                result.append("IP-CIDR," + str(net) + (",no-resolve" if no_resolve else ""))
        elif behavior == "domain":
            if "," in value or any(char.isspace() for char in value) or "/" in value:
                raise ValueError(f"invalid domain pattern: {value}")
            result.append(value)
        elif behavior == "classical":
            fields = value.split(",")
            kind = fields[0]
            if kind in IP_TYPES:
                if len(fields) not in (2, 3) or (len(fields) == 3 and fields[2] != "no-resolve"):
                    raise ValueError(f"invalid CIDR rule: {value}")
                net = ipaddress.ip_network(fields[1], strict=False)
                if kind == "IP-CIDR6" and net.version != 6:
                    raise ValueError(f"invalid IPv6 rule: {value}")
                if net.version == 4:
                    result.append(",".join([kind, str(net), *fields[2:]]))
            elif kind in TEXT_TYPES:
                payload = value.partition(",")[2]
                if not payload or (kind != "DOMAIN-REGEX" and len(fields) != 2):
                    raise ValueError(f"invalid text rule: {value}")
                if kind == "DOMAIN-REGEX":
                    re.compile(payload)  # The kernel is the authoritative compatibility check.
                result.append(value)
            else:
                raise ValueError(f"unsupported rule type (not skipped): {kind}")
        else:
            raise ValueError(f"unsupported behavior: {behavior}")
    if not result:
        raise ValueError("no rules remain after IPv6 filtering")
    return list(dict.fromkeys(result))


def safe_child(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path escapes rule root")
    return path


def build(root, output, fetch=download):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("candidate output must not already exist; last-good data is never overwritten")
    manifest = json.loads((root / "rule-sources/sources.json").read_text(encoding="utf-8"))
    overlays = json.loads((root / "rule-sources/overrides.json").read_text(encoding="utf-8"))
    revisions = {}
    raw_rules, receipts = {}, {}
    for name, source in manifest["sources"].items():
        if "local" in source:
            body = safe_child(root, source["local"]).read_bytes()
            url = source["local"]
        elif "repo" in source:
            key = source["repo"] + "@" + source["ref"]
            if key not in revisions:
                data = json.loads(fetch("https://api.github.com/repos/" + source["repo"] + "/commits/" + source["ref"]))
                revision = data["sha"]
                if not re.fullmatch("[0-9a-f]{40}", revision):
                    raise ValueError("invalid repository revision")
                revisions[key] = revision
            url = "https://raw.githubusercontent.com/" + source["repo"] + "/" + revisions[key] + "/" + source["path"]
            body = fetch(url)
        else:
            url = source["url"]
            body = fetch(url)
        rules = parse(body, source["format"], source["behavior"], no_resolve=source.get("no_resolve", True))
        raw_rules[name] = rules
        receipts[name] = {"url": url, "sha256": sha(body), "rules": len(rules)}

    generated, stats = {}, {}
    for name, spec in manifest["outputs"].items():
        if not re.fullmatch("[a-z0-9_]+", name):
            raise ValueError("invalid output name")
        rules = []
        for part in spec["parts"]:
            values = raw_rules[part["source"]]
            if "types" in part:
                values = [v for v in values if v.split(",", 1)[0] in part["types"]]
            rules.extend(values)
        changes = overlays.get(name, {})
        remove = set(changes.get("remove", []))
        if remove - set(rules):
            raise ValueError(f"{name}: stale removal no longer exists upstream; review it")
        rules = [r for r in rules if r not in remove] + changes.get("add", [])
        behavior = spec.get("behavior", "classical")
        rules = parse(yaml.safe_dump({"payload": rules}).encode(), "yaml", behavior)
        rules = sorted(set(rules))
        if len(rules) < spec.get("min_rules", 1) or len(rules) > spec.get("max_rules", 300000):
            raise ValueError(f"{name}: rule count outside reviewed limits")
        baseline_path = root / "rules/generated" / (name + ".yaml")
        if baseline_path.exists():
            old = yaml.load(baseline_path.read_text(encoding="utf-8"), Loader=UniqueLoader)["payload"]
            deleted = len(set(old) - set(rules))
            if deleted > max(5, int(len(old) * spec.get("max_delete_fraction", .2))):
                raise ValueError(f"{name}: abnormal deletion ({deleted}/{len(old)}); review source changes")
            if len(rules) > max(len(old) + 100, int(len(old) * spec.get("max_growth_factor", 1.5))):
                raise ValueError(f"{name}: abnormal growth; review source changes")
        content = "# Generated; edit rule-sources/overrides.json instead. Sources: sources.lock.json\n"
        content += yaml.safe_dump({"payload": rules}, allow_unicode=True, sort_keys=False, width=120)
        generated[name + ".yaml"] = content.encode()
        stats[name] = {"rules": len(rules), "sha256": sha(content.encode()),
                       "types": dict(Counter(r.split(",", 1)[0] for r in rules)) if behavior == "classical" else {"domain": len(rules)}}
    receipt = {"sources": receipts, "outputs": stats}
    old_lock = root / "rules/generated/sources.lock.json"
    if old_lock.exists():
        old = json.loads(old_lock.read_text(encoding="utf-8"))
        if old.get("outputs") == stats:
            receipt = old  # Preserve last content-changing receipt, not a daily timestamp commit.
    generated["sources.lock.json"] = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode()
    # All downloads and semantic transforms finish before any candidate directory is created.
    output.mkdir(parents=True)
    for name, body in generated.items():
        (output / name).write_bytes(body)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.root, args.output)
        print(json.dumps({"candidate": str(args.output), "providers": len(result), "rules": sum(s["rules"] for s in result.values())}))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
