"""Promote only a verified candidate into the checkout. This command never pushes."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def promote(root, candidate):
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    expected = set(json.loads((root / "rule-sources/sources.json").read_text(encoding="utf-8"))["outputs"])
    receipt = json.loads((candidate / "sources.lock.json").read_text(encoding="utf-8"))
    if set(receipt["outputs"]) != expected:
        raise ValueError("candidate output inventory differs from reviewed source definition")
    expected_files = {name + ".yaml" for name in expected} | {"sources.lock.json"}
    if {path.name for path in candidate.iterdir()} != expected_files:
        raise ValueError("candidate contains unexpected or missing files")
    for name in expected:
        path = candidate / (name + ".yaml")
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != receipt["outputs"][name]["sha256"]:
            raise ValueError(f"candidate content changed: {name}")
    dirty = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True)
    if dirty.strip():
        raise ValueError("publication checkout must be clean")
    destination = root / "rules/generated"
    for name in expected_files:
        shutil.copyfile(candidate / name, destination / name)
    subprocess.run(["git", "-C", str(root), "add", "--", "rules/generated"], check=True)
    staged = subprocess.check_output(["git", "-C", str(root), "diff", "--cached", "--name-only"], text=True).splitlines()
    allowed = {"rules/generated/" + name for name in expected_files}
    if set(staged) - allowed:
        raise ValueError("publication diff exceeds allowed data paths")
    return staged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"staged":promote(args.root, args.candidate)}))
