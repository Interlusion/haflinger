"""The release's checks, the links to its tag and its notes: `scripts/prepare_release.py`, which
`release.yml` runs before building and for the GitHub Release; and the uv that builds it
(ADR-013, releasing guide)."""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = "https://github.com/Interlusion/haflinger"
MAIN = re.compile(rf"{re.escape(REPOSITORY)}/(?:blob|tree)/main/")

README = f"""# Example

See the [guide]({REPOSITORY}/blob/main/docs/guides/development.md), the
[folder]({REPOSITORY}/tree/main/docs/specs/), the [issues]({REPOSITORY}/issues)
and [another project](https://github.com/example/other/blob/main/README.md).
"""
URLS = f"""[project.urls]
Repository = "{REPOSITORY}"
Documentation = "{REPOSITORY}/blob/main/docs/README.md"
Issues = "{REPOSITORY}/issues"
"""
CHANGELOG = """# Changelog

## [Unreleased]

## [0.1.0] - 2026-11-12

### Added

- Reading invoices.

[unreleased]: https://github.com/Interlusion/haflinger/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Interlusion/haflinger/releases/tag/v0.1.0
"""


def project(
    path: Path, version: str = "0.1.0", changelog: str = CHANGELOG, readme: str = README
) -> Path:
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "haflinger"\nversion = "{version}"\n\n{URLS}', encoding="utf-8"
    )
    (path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (path / "README.md").write_text(readme, encoding="utf-8")
    return path


def prepare(path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / "scripts/prepare_release.py"), *arguments]
    return subprocess.run(command, cwd=path, capture_output=True, text=True, check=False)  # noqa: S603


def unchanged(path: Path) -> bool:
    readme = (path / "README.md").read_text(encoding="utf-8")
    return readme == README and URLS in (path / "pyproject.toml").read_text(encoding="utf-8")


def test_a_matching_tag_points_the_links_to_main_at_it(tmp_path: Path) -> None:
    result = prepare(project(tmp_path), "v0.1.0")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == (
        README.replace("/blob/main/", "/blob/v0.1.0/", 1).replace("/tree/main/", "/tree/v0.1.0/")
    )
    pyproject = tomllib.loads((tmp_path / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["urls"] == {
        "Repository": REPOSITORY,
        "Documentation": f"{REPOSITORY}/blob/v0.1.0/docs/README.md",
        "Issues": f"{REPOSITORY}/issues",
    }
    assert "README.md: 2 links" in result.stdout
    assert "pyproject.toml: 1 links" in result.stdout


def test_check_only_changes_nothing(tmp_path: Path) -> None:
    result = prepare(project(tmp_path), "v0.1.0", "--check")
    assert result.returncode == 0, result.stderr
    assert unchanged(tmp_path)


def test_notes_are_the_versions_section(tmp_path: Path) -> None:
    """The GitHub Release's notes: the section's body, without its heading and the links."""
    result = prepare(project(tmp_path), "v0.1.0", "--notes")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "### Added\n\n- Reading invoices.\n"
    assert unchanged(tmp_path)


def test_notes_end_at_the_release_before(tmp_path: Path) -> None:
    older = "## [0.0.9] - 2026-11-01\n\n### Fixed\n\n- Older.\n\n"
    changelog = CHANGELOG.replace("[unreleased]:", older + "[unreleased]:")
    result = prepare(project(tmp_path, changelog=changelog), "v0.1.0", "--notes")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "### Added\n\n- Reading invoices.\n"


def test_no_notes_for_a_release_that_fails_its_checks(tmp_path: Path) -> None:
    result = prepare(project(tmp_path), "v0.1.1", "--notes")
    assert result.returncode == 1
    assert result.stdout == ""


@pytest.mark.parametrize(
    "arguments",
    [[], ["--check"], ["--check", "v0.1.0"], ["v0.1.0", "-x"], ["v0.1.0", "--check", "--notes"]],
)
def test_other_arguments_are_refused(tmp_path: Path, arguments: list[str]) -> None:
    result = prepare(project(tmp_path), *arguments)
    assert result.returncode == 2
    assert "prepare_release.py vX.Y.Z [--check | --notes]" in result.stderr
    assert unchanged(tmp_path)


@pytest.mark.parametrize("tag", ["v0.1.1", "0.1.0", "v0.1", "v0.1.0rc1"])
def test_a_tag_that_doesnt_name_the_version_is_refused(tmp_path: Path, tag: str) -> None:
    result = prepare(project(tmp_path), tag)
    assert result.returncode == 1
    assert "v0.1.0" in result.stderr
    assert unchanged(tmp_path)


@pytest.mark.parametrize("version", ["0.1", "0.1.0rc1", "0.1.0.post1", "0.01.0", "01.1.0"])
def test_a_version_other_than_x_y_z_is_refused(tmp_path: Path, version: str) -> None:
    changelog = CHANGELOG.replace("[0.1.0] -", f"[{version}] -")
    result = prepare(project(tmp_path, version=version, changelog=changelog), f"v{version}")
    assert result.returncode == 1
    assert "X.Y.Z" in result.stderr
    assert unchanged(tmp_path)


@pytest.mark.parametrize(
    "changelog",
    [
        pytest.param(CHANGELOG.replace("## [0.1.0] - 2026-11-12\n", ""), id="under Unreleased"),
        pytest.param(CHANGELOG.replace(" - 2026-11-12", ""), id="no date"),
        pytest.param(CHANGELOG.replace("- Reading invoices.\n", ""), id="no entries"),
        pytest.param(CHANGELOG.replace("[0.1.0] -", "[0.1.1] -"), id="another version"),
        pytest.param(
            CHANGELOG.replace("## [0.1.0]", "## [0.0.9] - 2026-11-01\n\n- Older.\n\n## [0.1.0]"),
            id="not right below Unreleased",
        ),
    ],
)
def test_a_version_without_its_changelog_section_is_refused(tmp_path: Path, changelog: str) -> None:
    result = prepare(project(tmp_path, changelog=changelog), "v0.1.0")
    assert result.returncode == 1
    assert "## [0.1.0] - YYYY-MM-DD" in result.stderr
    assert unchanged(tmp_path)


@pytest.mark.parametrize(
    "changelog",
    [
        pytest.param(
            CHANGELOG.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- Later.\n"),
            id="entries left",
        ),
        pytest.param(CHANGELOG.replace("## [Unreleased]\n\n", ""), id="missing"),
    ],
)
def test_a_changelog_whose_unreleased_isnt_empty_is_refused(tmp_path: Path, changelog: str) -> None:
    result = prepare(project(tmp_path, changelog=changelog), "v0.1.0")
    assert result.returncode == 1
    assert "Unreleased" in result.stderr
    assert unchanged(tmp_path)


def test_the_repositorys_links_to_main_all_point_at_the_tag(tmp_path: Path) -> None:
    """In a release's build, they already point at its tag: taken back to `main` here."""
    tagged = re.compile(rf"({re.escape(REPOSITORY)}/(?:blob|tree))/v\d+\.\d+\.\d+/")
    readme = tagged.sub(r"\1/main/", (ROOT / "README.md").read_text(encoding="utf-8"))
    pyproject = tagged.sub(r"\1/main/", (ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project(tmp_path, readme=readme)
    (tmp_path / "pyproject.toml").write_text(
        re.sub(r'(?m)^version = ".*"$', 'version = "0.1.0"', pyproject), encoding="utf-8"
    )
    result = prepare(tmp_path, "v0.1.0")
    assert result.returncode == 0, result.stderr
    for name, text in (("README.md", readme), ("pyproject.toml", pyproject)):
        links = len(MAIN.findall(text))
        assert links
        released = (tmp_path / name).read_text(encoding="utf-8")
        assert not MAIN.search(released)
        assert len(tagged.findall(released)) == links
        assert f"{name}: {links} links" in result.stdout


def test_the_changelog_starts_with_unreleased_and_names_the_version() -> None:
    """`pyproject.toml`'s version is the changelog's newest release, so the release's pull
    request sets both. A yanked release keeps its section, marked."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", changelog, re.M)
    assert headings[0] == "[Unreleased]"
    release = r"\[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}(?: \[YANKED\])?"
    releases = [re.fullmatch(release, heading) for heading in headings[1:]]
    assert releases, headings
    assert all(releases), headings
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert releases[0] is not None
    assert version == releases[0][1]


def test_uv_builds_with_the_backend_it_bundles() -> None:
    """uv uses the `uv_build` it bundles only when its own version lies within the range
    `[build-system]` names; otherwise `uv build` downloads a backend, unpinned and unchecked."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    uv = SpecifierSet(pyproject["tool"]["uv"]["required-version"])
    (pinned,) = (spec.version for spec in uv if spec.operator == "==")
    (backend,) = (
        Requirement(requirement)
        for requirement in pyproject["build-system"]["requires"]
        if Requirement(requirement).name == "uv_build"
    )
    assert backend.specifier.contains(pinned), (pinned, str(backend.specifier))
