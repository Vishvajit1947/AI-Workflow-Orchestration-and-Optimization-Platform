"""
Lenient file extraction for project builds, using the two shapes seen in real model output:
answers cut off by the output limit, and files labelled by a heading above a plain fence.
"""
from backend.app.artifacts.service import build_stage_artifact
from backend.app.services.project_builder.extraction import extract_project_files, merge_stage_files

FENCE = "```"


def test_truncated_answer_keeps_complete_files_and_reports_the_cut_one():
    text = (f"{FENCE}json path=frontend/package.json\n{{}}\n{FENCE}\n"
            f"{FENCE}ts path=frontend/src/api.ts\nexport const a = 1;\n{FENCE}\n"
            f"{FENCE}ts path=frontend/src/courses.ts\nexport async function list() {{\n  return fetch(")
    files, warnings = extract_project_files(text)
    assert [f["path"] for f in files] == ["frontend/package.json", "frontend/src/api.ts"]
    assert warnings == ["frontend/src/courses.ts: the output was cut off before this file ended, so it was left out"]
    # Artifact mode stays all-or-nothing for the same text
    assert build_stage_artifact(text, "project", "x") is None


def test_heading_labelled_files_are_recognised():
    text = ("The backend uses FastAPI.\n\n---\n\n## `backend/requirements.txt`\n\n"
            f"{FENCE}txt\nfastapi\nuvicorn\n{FENCE}\n\n---\n\n**backend/main.py**\n"
            f"{FENCE}python\nfrom fastapi import FastAPI\napp = FastAPI()\n{FENCE}\n\n"
            f"File: .gitignore\n{FENCE}\n__pycache__/\n{FENCE}\n")
    files, warnings = extract_project_files(text)
    assert {f["path"]: f["content"] for f in files} == {
        "backend/requirements.txt": "fastapi\nuvicorn\n",
        "backend/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
        ".gitignore": "__pycache__/\n",
    }
    assert warnings == []


def test_bare_path_after_the_language_is_recognised():
    text = (f"{FENCE}python app/main.py\nfrom fastapi import FastAPI\n{FENCE}\n"
            f"{FENCE}requirements.txt\nfastapi\n{FENCE}\n"
            f"{FENCE}python\nprint('example, not a file')\n{FENCE}\n")
    files, warnings = extract_project_files(text)
    assert [f["path"] for f in files] == ["app/main.py", "requirements.txt"] and warnings == []


def test_ordinary_code_examples_and_prose_mentions_are_not_files():
    text = ("To run it, use the snippet below (see main.py for details, this sentence is long enough "
            "to be prose rather than a label, describing what happens when you start the server).\n"
            f"{FENCE}bash\nuvicorn main:app --reload\n{FENCE}\n")
    assert extract_project_files(text) == ([], [])


def test_unsafe_and_duplicate_paths_are_reported_not_written():
    text = (f"{FENCE}text path=../escape.txt\nx\n{FENCE}\n"
            f"{FENCE}text path=a.py\nv1\n{FENCE}\n{FENCE}text path=a.py\nv2\n{FENCE}\n")
    files, warnings = extract_project_files(text)
    assert files == [{"path": "a.py", "content": "v2\n"}]
    assert any("unsafe path" in w for w in warnings) and any("written twice" in w for w in warnings)


def test_four_backtick_readme_with_nested_fences():
    text = f"````markdown path=README.md\n# Run\n{FENCE}bash\nnpm start\n{FENCE}\n````\n"
    (readme,), _ = extract_project_files(text)
    assert readme["content"] == f"# Run\n{FENCE}bash\nnpm start\n{FENCE}\n"


def test_later_stage_wins_on_the_same_path():
    files, warnings = merge_stage_files([
        ("Backend", [{"path": "README.md", "content": "a"}, {"path": "main.py", "content": "x"}]),
        ("Docs", [{"path": "README.md", "content": "b"}]),
    ])
    assert {f["path"]: f["content"] for f in files} == {"README.md": "b", "main.py": "x"}
    assert warnings == ["README.md: written by both Backend and Docs; Docs's version is used"]
