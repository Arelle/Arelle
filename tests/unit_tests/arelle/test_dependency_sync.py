from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def parse_requirements_file(path: Path) -> dict[str, Requirement]:
    deps: dict[str, Requirement] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        req = Requirement(line)
        deps[canonicalize_name(req.name)] = req
    return deps


def parse_pyproject_deps(path: Path) -> dict[str, Requirement]:
    data = tomllib.loads(path.read_bytes().decode())
    deps: dict[str, Requirement] = {}
    for dep in data.get("project", {}).get("dependencies", []):
        req = Requirement(dep)
        deps[canonicalize_name(req.name)] = req
    for group_deps in data.get("project", {}).get("optional-dependencies", {}).values():
        for dep in group_deps:
            req = Requirement(dep)
            name = canonicalize_name(req.name)
            if name not in deps:
                deps[name] = req
    return deps


class TestDependencySync:
    pyprojectDeps: dict[str, Requirement]
    requirementsDeps: dict[str, Requirement]

    @classmethod
    def setup_class(cls) -> None:
        cls.pyprojectDeps = parse_pyproject_deps(PROJECT_ROOT / "pyproject.toml")
        cls.requirementsDeps = {
            name: req
            for path in [PROJECT_ROOT / "requirements.txt", PROJECT_ROOT / "requirements-plugins.txt"]
            for name, req in parse_requirements_file(path).items()
        }

    def test_pyproject_deps_in_requirements(self):
        """Every pyproject.toml dependency should be in requirements files."""
        missing = [name for name in self.pyprojectDeps if name not in self.requirementsDeps]
        assert not missing, f"pyproject.toml deps missing from requirements: {sorted(missing)}"

    def test_requirements_deps_in_pyproject(self):
        """Every requirements dependency should be in pyproject.toml."""
        missing = [name for name in self.requirementsDeps if name not in self.pyprojectDeps]
        assert not missing, f"Requirements deps missing from pyproject.toml: {sorted(missing)}"

    def test_version_compatibility(self):
        """Pinned versions in requirements should satisfy pyproject.toml specifiers."""
        incompatible = []
        for name, pyprojectReq in self.pyprojectDeps.items():
            if name in self.requirementsDeps:
                reqSpecifier = self.requirementsDeps[name].specifier
                for spec in reqSpecifier:
                    if spec.operator == "==":
                        if spec.version not in pyprojectReq.specifier:
                            incompatible.append(f"{name}: =={spec.version} does not satisfy {pyprojectReq.specifier}")
                        break
        assert not incompatible, "Version incompatibilities:\n" + "\n".join(sorted(incompatible))
