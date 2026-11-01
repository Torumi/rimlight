"""Run a pinned actionlint, downloading and verifying it on first use.

actionlint has no binary wheels on PyPI, so the release archive is fetched from GitHub,
checked against the SHA-256 below, and cached in `.cache/tools/` at the repository root.
shellcheck comes from the `shellcheck-py` dev dependency and lints `run:` blocks.

Usage: uv run python scripts/dev_tools/actionlint.py [actionlint args...]
"""

import hashlib
import io
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.7.12"
# From https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_checksums.txt
SHA256 = {
    "linux_amd64.tar.gz": "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    "linux_arm64.tar.gz": "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    "darwin_amd64.tar.gz": "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
    "darwin_arm64.tar.gz": "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    "windows_amd64.zip": "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
    "windows_arm64.zip": "cadcf7ea4efe3a68728893813643cebe1185e5b1d4be5b96245f65c9a4d5ea41",
}

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "tools" / f"actionlint-{VERSION}"


def asset_suffix(system: str, machine: str) -> str:
    """Release asset suffix for `platform.system()` / `platform.machine()` values."""
    os_name = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(system)
    arch = {"x86_64": "amd64", "AMD64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine
    )
    if os_name is None or arch is None:
        raise SystemExit(f"actionlint: unsupported platform {system}/{machine}")
    return f"{os_name}_{arch}.{'zip' if os_name == 'windows' else 'tar.gz'}"


def extract_binary(archive: bytes, suffix: str, name: str) -> bytes:
    if suffix.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            return zf.read(name)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        member = tf.extractfile(name)
        if member is None:
            raise SystemExit(f"actionlint: {name} missing from archive")
        return member.read()


def ensure_binary() -> Path:
    suffix = asset_suffix(platform.system(), platform.machine())
    name = "actionlint.exe" if suffix.endswith(".zip") else "actionlint"
    binary = CACHE / name
    if binary.exists():
        return binary
    url = (
        f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/"
        f"actionlint_{VERSION}_{suffix}"
    )
    print(f"actionlint: downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=60) as response:
        archive: bytes = response.read()
    digest = hashlib.sha256(archive).hexdigest()
    if digest != SHA256[suffix]:
        raise SystemExit(f"actionlint: checksum mismatch for {url}: {digest}")
    CACHE.mkdir(parents=True, exist_ok=True)
    partial = binary.with_suffix(".part")
    partial.write_bytes(extract_binary(archive, suffix, name))
    partial.chmod(0o755)
    partial.replace(binary)
    return binary


def main(argv: list[str]) -> int:
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        print("actionlint: shellcheck not found; run via `uv run`", file=sys.stderr)
        return 1
    command = [str(ensure_binary()), "-shellcheck", shellcheck, *argv]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
