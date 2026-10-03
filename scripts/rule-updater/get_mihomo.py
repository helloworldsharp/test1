"""Fetch the fixed test kernel and verify the release asset digest before extracting."""
import argparse
import gzip
import hashlib
import io
import os
import platform
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v1.19.32"
ASSETS = {
    "Windows": ("mihomo-windows-amd64-compatible-v1.19.32.zip", "974a4d7ad69aed27aa2e8f91d61113573c14dadb14562c63e58effabf59816f0"),
    "Linux": ("mihomo-linux-amd64-compatible-v1.19.32.gz", "ba3ce607747a07f948fc35780e108a4a7c7f552a38b9bd4d115f313ebcb89c20"),
}


def fetch(output):
    asset, expected = ASSETS[platform.system()]
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("this pinned kernel fixture supports amd64 only")
    request = urllib.request.Request("https://github.com/MetaCubeX/mihomo/releases/download/" + VERSION + "/" + asset,
                                     headers={"User-Agent":"routing-kernel-tests"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read(128 * 1024 * 1024 + 1)
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError("kernel release digest mismatch")
    if asset.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            binary = archive.read("mihomo-windows-amd64-compatible.exe")
    else:
        binary = gzip.decompress(body)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(binary)
    if os.name != "nt":
        output.chmod(0o700)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    fetch(parser.parse_args().output)
