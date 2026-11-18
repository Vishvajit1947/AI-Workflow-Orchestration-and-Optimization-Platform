"""Project structure analysis: components, build steps and missing-file warnings."""
import json

from backend.app.artifacts.service import build_stage_artifact
from backend.app.services.project_builder.structure import STEP_KINDS, analyze_structure

FENCE = "```"


def kinds(component):
    return [s.kind for s in component.steps]


def test_fullstack_project_has_two_components_with_their_own_steps():
    files = {
        "README.md": "# App",
        ".gitignore": "node_modules/",
        "frontend/package.json": json.dumps({"dependencies": {"react": "^18"}, "scripts": {"build": "vite build"}}),
        "frontend/src/main.tsx": "",
        "backend/requirements.txt": "fastapi==0.115.6\nuvicorn\n",
        "backend/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        "backend/tests/test_api.py": "def test_ok(): assert True\n",
    }
    structure = analyze_structure(files)
    by_root = {c.root: c for c in structure.components}
    assert set(by_root) == {"frontend", "backend"}
    assert by_root["frontend"].kind == "react" and kinds(by_root["frontend"]) == ["npm_install", "npm_build"]
    assert by_root["backend"].kind == "fastapi"
    # every install step comes before any step that runs project code (network is cut there)
    assert kinds(by_root["backend"]) == ["pip_install", "pip_install_pytest", "py_compile", "py_import", "pytest"]
    assert by_root["backend"].steps[3].module == "main"
    assert structure.project_type == "fullstack"
    assert structure.warnings == []


def test_node_placeholder_test_script_is_not_run():
    files = {"package.json": json.dumps({"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}),
             "index.js": "console.log(1)", "README.md": "", ".gitignore": ""}
    (component,) = analyze_structure(files).components
    assert kinds(component) == ["npm_install"]


def test_loose_python_files_without_manifest_are_one_component_and_flagged():
    files = {"src/app.py": "import requests\n", "src/util.py": "x = 1\n"}
    structure = analyze_structure(files)
    (component,) = structure.components
    assert component.root == "src" and component.runtime == "python"
    assert any("requirements.txt is missing" in w for w in structure.warnings)
    assert any("README.md" in w for w in structure.warnings)


def test_no_runnable_component_is_reported():
    structure = analyze_structure({"README.md": "# Notes"})
    assert structure.components == [] and structure.project_type == "unknown"
    assert any("No runnable component" in w for w in structure.warnings)


def test_invalid_package_json_is_a_warning_not_a_crash():
    structure = analyze_structure({"package.json": "{not json", "README.md": "", ".gitignore": ""})
    assert any("not valid JSON" in w for w in structure.warnings)
    assert kinds(structure.components[0]) == ["npm_install"]


def test_dependency_folders_are_ignored():
    files = {"requirements.txt": "", "main.py": "", "node_modules/x/package.json": "{}", "README.md": "", ".gitignore": ""}
    assert [c.runtime for c in analyze_structure(files).components] == ["python"]


def test_install_steps_always_precede_code_steps():
    files = {"a/package.json": json.dumps({"scripts": {"build": "x", "test": "jest"}}),
             "b/requirements.txt": "", "b/app.py": "", "b/test_x.py": ""}
    for component in analyze_structure(files).components:
        needs_network = [STEP_KINDS[s.kind][2] for s in component.steps]
        assert needs_network == sorted(needs_network, reverse=True), [s.kind for s in component.steps]


def test_every_step_kind_is_allow_listed():
    files = {"a/package.json": json.dumps({"scripts": {"build": "x", "test": "jest"}}),
             "b/requirements.txt": "pytest\n", "b/app.py": "", "b/test_x.py": ""}
    for component in analyze_structure(files).components:
        assert all(step.kind in STEP_KINDS for step in component.steps)


def test_multi_file_generation_keeps_hierarchy_and_content():
    """Phase 1: a project stage result becomes many files with their folders and exact contents."""
    result = (
        f"Here is the project.\n\n{FENCE}python path=backend/main.py\nprint('hi')\n{FENCE}\n"
        f"{FENCE}text path=backend/requirements.txt\nfastapi\n{FENCE}\n"
        f"{FENCE}json path=frontend/package.json\n{{\"name\": \"ui\"}}\n{FENCE}\n"
        f"````markdown path=README.md\n# Setup\n```bash\nnpm install\n```\n````\n"
    )
    artifact = build_stage_artifact(result, "project", "Student app")
    files = {f.path: f.content for f in artifact.files}
    assert set(files) == {"backend/main.py", "backend/requirements.txt", "frontend/package.json", "README.md"}
    assert files["backend/main.py"] == "print('hi')\n"
    assert "```bash" in files["README.md"]  # nested fences preserved
    assert analyze_structure(files).project_type == "fullstack"
