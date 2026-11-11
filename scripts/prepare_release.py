"""A release's checks before it is built, then the links to its tag, or its notes (ADR-013,
releasing guide).

Refuses unless the tag is `v` and `pyproject.toml`'s version, that version has the form X.Y.Z,
and `CHANGELOG.md` has its section, `## [X.Y.Z] - YYYY-MM-DD`, with entries, right below an empty
"Unreleased". Then the links to `main` of this repository in the README and in the project URLs,
which PyPI shows with every release, point at the tag, so that a release's page links the files
as they were released. Runs in the repository's root; `--check` only checks, and `--notes`
prints the version's section, the GitHub Release's notes, after the same checks.

    uv run python scripts/prepare_release.py vX.Y.Z [--check | --notes]
"""

import re
import sys
import tomllib
from pathlib import Path

VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
OPTIONS: tuple[list[str], ...] = ([], ["--check"], ["--notes"])


def sections(changelog: str) -> list[str]:
    """The changelog's `## ` sections, each from its heading's text on, "Unreleased" first."""
    return re.split(r"^## ", changelog, flags=re.M)[1:]


def problems(tag: str, version: str, changelog: str) -> list[str]:
    found: list[str] = []
    if not VERSION.fullmatch(version):
        found.append(f"pyproject.toml's version {version} doesn't have the form X.Y.Z")
    if tag != f"v{version}":
        found.append(f"the tag {tag} doesn't name pyproject.toml's version: v{version}")
    unreleased, release = [*sections(changelog), "", ""][:2]
    if not unreleased.startswith("[Unreleased]\n"):
        found.append("CHANGELOG.md doesn't start with ## [Unreleased]")
    elif re.search(r"^- ", unreleased, re.M):
        found.append("CHANGELOG.md's Unreleased still has entries")
    heading = rf"\[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n"
    if not re.match(heading, release) or not re.search(r"^- ", release, re.M):
        found.append(
            f"CHANGELOG.md has no section ## [{version}] - YYYY-MM-DD with entries"
            " right below Unreleased"
        )
    return found


def notes(changelog: str) -> str:
    """The body of the section right below "Unreleased", which `problems` checked is the
    version's, without its heading and the link definitions at the end."""
    body = sections(changelog)[1].split("\n", 1)[1]
    return re.split(r"^\[[^\]]+\]: ", body, maxsplit=1, flags=re.M)[0].strip()


def main(arguments: list[str]) -> int:
    if not arguments or arguments[0].startswith("-") or arguments[1:] not in OPTIONS:
        print(__doc__, file=sys.stderr)
        return 2
    tag = arguments[0]
    pyproject = Path("pyproject.toml")
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    found = problems(tag, project["version"], changelog)
    for problem in found:
        print(f"error: {problem}", file=sys.stderr)
    if found:
        return 1
    if arguments[1:] == ["--check"]:
        print(f"{tag}: ready")
        return 0
    if arguments[1:] == ["--notes"]:
        print(notes(changelog))
        return 0
    main_links = re.compile(rf"({re.escape(project['urls']['Repository'])}/(?:blob|tree))/main/")
    for path in (Path("README.md"), pyproject):
        text, links = main_links.subn(rf"\1/{tag}/", path.read_text(encoding="utf-8"))
        path.write_text(text, encoding="utf-8")
        print(f"{path}: {links} links point at {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
