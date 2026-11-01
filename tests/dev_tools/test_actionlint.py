import pytest

from dev_tools.actionlint import SHA256, asset_suffix


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Windows", "AMD64", "windows_amd64.zip"),
        ("Linux", "x86_64", "linux_amd64.tar.gz"),
        ("Linux", "aarch64", "linux_arm64.tar.gz"),
        ("Darwin", "arm64", "darwin_arm64.tar.gz"),
    ],
)
def test_asset_suffix(system: str, machine: str, expected: str) -> None:
    assert asset_suffix(system, machine) == expected
    assert expected in SHA256


def test_unsupported_platform() -> None:
    with pytest.raises(SystemExit, match="unsupported platform"):
        asset_suffix("FreeBSD", "x86_64")
