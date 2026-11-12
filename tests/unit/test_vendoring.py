"""Vendored official files: byte for byte and traceable to a release (ADR-008), with their
licences named in the package (ADR-009)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENDORED = ("src/haflinger/artefacts", "tests/data")
PROVENANCE_ROWS = ("Source", "Release", "Commit", "Licence")


def sources() -> list[Path]:
    return sorted(
        path
        for base in VENDORED
        if (ROOT / base).is_dir()
        for path in (ROOT / base).iterdir()
        if path.is_dir() and path.name != "__pycache__"
    )


def test_vendored_files_are_not_normalised_by_git() -> None:
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    for base in VENDORED:
        assert f"{base}/** -text" in lines


def test_every_source_has_its_provenance() -> None:
    for source in sources():
        readme = source / "README.md"
        assert readme.is_file(), f"{source.relative_to(ROOT)} has no README.md"
        text = readme.read_text(encoding="utf-8")
        for row in PROVENANCE_ROWS:
            assert re.search(rf"^\| \*\*{row}\*\* \| \S", text, re.MULTILINE), (
                f"{readme.relative_to(ROOT)} has no {row} row"
            )


def test_the_package_names_the_licences_of_what_it_ships() -> None:
    """Each runtime source has its licence file and a block in THIRD-PARTY-NOTICES, whose
    "Licence" lines, with Apache-2.0 for Haflinger's code, make exactly the package's licence
    expression; each LicenseRef has its text there, and the file is among the licence files."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    notices = (ROOT / "THIRD-PARTY-NOTICES").read_text(encoding="utf-8")
    licence_files = {path for pattern in project["license-files"] for path in ROOT.glob(pattern)}
    assert ROOT / "THIRD-PARTY-NOTICES" in licence_files
    blocks = dict(re.findall(r"^([\w-]+)/\n(?:  .*\n)*?  Licence: (.+)$", notices, re.MULTILINE))
    runtime = {
        path.name
        for path in (ROOT / VENDORED[0]).iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert set(blocks) == runtime
    for name in runtime:
        assert any((ROOT / VENDORED[0] / name).glob("LICENSE*")), f"{name} has no licence file"
    named = {"Apache-2.0"} | {term for line in blocks.values() for term in line.split(" AND ")}
    assert named == set(project["license"].split(" AND "))
    for reference in (term for term in named if term.startswith("LicenseRef-")):
        heading = rf"^.*\({re.escape(reference)}\)\n-+$"
        assert re.search(heading, notices, re.MULTILINE), reference


def test_kosit_validator_runs_with_the_vendored_configuration() -> None:
    """KoSIT's validator in CI runs with the whole ZIP of the configuration release Haflinger
    vendors, checked against the same SHA-256 (REQ-002-PRS-F007, development guide)."""
    readme = (ROOT / "src/haflinger/artefacts/kosit-validator-xrechnung/README.md").read_text(
        encoding="utf-8"
    )
    release = re.search(r"^\| \*\*Release\*\* \| `([^`]+)`", readme, re.MULTILINE)
    asset = re.search(r"release asset `([^`]+\.zip)`", readme)
    digest = re.search(r"^\| \*\*SHA-256 of the ZIP\*\* \| `([0-9a-f]{64})`", readme, re.MULTILINE)
    assert release, readme
    assert asset, readme
    assert digest, readme
    url = (
        "https://github.com/itplr-kosit/validator-configuration-xrechnung/releases/download/"
        f"{release[1]}/{asset[1]}"
    )
    dockerfile = (ROOT / ".github/kosit-validator/Dockerfile").read_text(encoding="utf-8")
    assert re.search(rf"^ADD --checksum=sha256:{digest[1]} {re.escape(url)} ", dockerfile, re.M)
