"""
Project structure analysis: which runnable components a generated project contains,
which essential files are missing, and which build steps verify each component.

Pure functions over {path: content}; no filesystem, network or LLM access.

A component is a folder holding a dependency manifest (package.json, requirements.txt or
pyproject.toml). A project of loose .py files with no manifest is one Python component at
its top folder. A full-stack project ("frontend/package.json" + "backend/requirements.txt")
has two components, built independently.

Build steps are *kinds* from a fixed allow-list (STEP_KINDS); the sandbox runner maps each
kind to a fixed command. Generated content never becomes a shell command.
"""
import json
import posixpath
import re
from dataclasses import dataclass, field
from typing import Optional

# kind -> (label shown to users, display command, needs network)
STEP_KINDS: dict[str, tuple[str, str, bool]] = {
    "pip_install": ("Install Python dependencies", "pip install -r requirements.txt", True),
    "pip_install_pytest": ("Install pytest", "pip install pytest", True),
    "py_compile": ("Check Python syntax", "python -m compileall -q .", False),
    "py_import": ("Import the application", "python -c 'import {module}'", False),
    "pytest": ("Run Python tests", "python -m pytest -q", False),
    "npm_install": ("Install Node dependencies", "npm install", True),
    "npm_build": ("Build", "npm run build", False),
    "npm_test": ("Run tests", "npm test", False),
}

_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_NPM_PLACEHOLDER_TEST = "no test specified"
_PY_ENTRYPOINTS = ("main.py", "app.py", "app/main.py", "src/main.py", "server.py")
_IGNORED_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


@dataclass
class BuildStep:
    kind: str
    cwd: str  # component folder, relative to the project root ("" = root)
    module: Optional[str] = None  # py_import only

    @property
    def label(self) -> str:
        return STEP_KINDS[self.kind][0]

    @property
    def command(self) -> str:
        return STEP_KINDS[self.kind][1].format(module=self.module or "")


@dataclass
class Component:
    root: str  # "" for the project root
    runtime: str  # "python" | "node"
    kind: str  # "python" | "fastapi" | "node" | "react"
    steps: list[BuildStep] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.root or "(root)"


@dataclass
class ProjectStructure:
    components: list[Component]
    warnings: list[str]

    @property
    def project_type(self) -> str:
        kinds = sorted({c.kind for c in self.components})
        if not kinds:
            return "unknown"
        if len(self.components) > 1 and {c.runtime for c in self.components} == {"python", "node"}:
            return "fullstack"
        return kinds[0] if len(kinds) == 1 else "+".join(kinds)


def _visible(path: str) -> bool:
    return not any(part in _IGNORED_DIRS for part in path.split("/")[:-1])


def _dir(path: str) -> str:
    return posixpath.dirname(path)


def _within(path: str, root: str) -> bool:
    return root == "" or path == root or path.startswith(root + "/")


def _relative(path: str, root: str) -> str:
    return path if root == "" else path[len(root) + 1:]


def _python_component(root: str, files: dict[str, str]) -> Component:
    inside = {_relative(p, root): c for p, c in files.items() if _within(p, root)}
    manifest = inside.get("requirements.txt", "") + inside.get("pyproject.toml", "")
    kind = "fastapi" if re.search(r"(?im)^\s*fastapi\b|[\"']fastapi", manifest) else "python"
    has_tests = any(
        posixpath.basename(p).startswith("test_") and p.endswith(".py") or p.startswith("tests/")
        for p in inside
    )
    # Install steps first: the sandbox cuts network access before any project code runs
    steps: list[BuildStep] = []
    if "requirements.txt" in inside:
        steps.append(BuildStep("pip_install", root))
    if has_tests and not re.search(r"(?im)^\s*pytest\b", manifest):
        steps.append(BuildStep("pip_install_pytest", root))
    steps.append(BuildStep("py_compile", root))
    entry = next((e for e in _PY_ENTRYPOINTS if e in inside), None)
    if entry:
        module = entry[:-3].replace("/", ".")
        if _MODULE.match(module):
            steps.append(BuildStep("py_import", root, module=module))
    if has_tests:
        steps.append(BuildStep("pytest", root))
    return Component(root=root, runtime="python", kind=kind, steps=steps)


def _node_component(root: str, files: dict[str, str]) -> tuple[Component, list[str]]:
    warnings: list[str] = []
    manifest_path = posixpath.join(root, "package.json") if root else "package.json"
    try:
        manifest = json.loads(files[manifest_path])
        if not isinstance(manifest, dict):
            raise ValueError("not an object")
    except (ValueError, KeyError) as e:
        warnings.append(f"{manifest_path} is not valid JSON ({e}); install will likely fail")
        manifest = {}
    deps = {**(manifest.get("dependencies") or {}), **(manifest.get("devDependencies") or {})}
    scripts = manifest.get("scripts") or {}
    kind = "react" if "react" in deps else "node"
    steps = [BuildStep("npm_install", root)]
    if isinstance(scripts, dict) and scripts.get("build"):
        steps.append(BuildStep("npm_build", root))
    test_script = scripts.get("test") if isinstance(scripts, dict) else None
    if test_script and _NPM_PLACEHOLDER_TEST not in str(test_script):
        steps.append(BuildStep("npm_test", root))
    if kind == "react" and "build" not in scripts:
        warnings.append(f"{manifest_path} has no \"build\" script, so the app cannot be built")
    return Component(root=root, runtime="node", kind=kind, steps=steps), warnings


def analyze_structure(files: dict[str, str]) -> ProjectStructure:
    """Components, build steps and missing-file warnings for a project given as {path: content}."""
    files = {p: c for p, c in files.items() if _visible(p)}
    warnings: list[str] = []
    components: list[Component] = []

    node_roots = sorted({_dir(p) for p in files if posixpath.basename(p) == "package.json"})
    python_roots = sorted({_dir(p) for p in files
                           if posixpath.basename(p) in ("requirements.txt", "pyproject.toml")})
    for root in node_roots:
        component, more = _node_component(root, files)
        components.append(component)
        warnings += more
    for root in python_roots:
        components.append(_python_component(root, files))

    # Python code outside every Python component (e.g. a manifest-less script project)
    covered = python_roots + node_roots
    loose_py = [p for p in files if p.endswith(".py") and not any(_within(p, r) for r in covered)]
    if loose_py:
        root = posixpath.commonpath([_dir(p) for p in loose_py]) if len(loose_py) > 1 else _dir(loose_py[0])
        components.append(_python_component(root, files))
        imports_third_party = any(re.search(r"(?m)^\s*(from|import)\s+(fastapi|flask|django|requests|pydantic|sqlalchemy|numpy|pandas)\b",
                                            files[p]) for p in loose_py)
        if imports_third_party:
            where = f"{root}/requirements.txt" if root else "requirements.txt"
            warnings.append(f"Python code imports third-party packages but {where} is missing")

    if not any(posixpath.basename(p).lower() == "readme.md" and _dir(p) == "" for p in files):
        warnings.append("README.md with setup and run instructions is missing")
    if not components:
        warnings.append("No runnable component found (no package.json, requirements.txt, pyproject.toml or .py files)")
    if components and ".gitignore" not in files:
        warnings.append(".gitignore is missing")

    return ProjectStructure(components=components, warnings=warnings)
