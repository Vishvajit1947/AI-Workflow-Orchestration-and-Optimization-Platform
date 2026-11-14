"""Code/project artifacts: unlabeled single-file fallback, exact content, ZIP packaging, stage prompts."""
import io
import zipfile

import pytest

from backend.app.artifacts import Artifact, ArtifactFile, build_stage_artifact
from backend.app.artifacts.document import ExportError
from backend.app.artifacts.prompts import stage_system_prompt
from backend.app.artifacts.service import extension_for_language
from backend.app.artifacts.zip_generator import build_zip, safe_filename

FENCE = "```"


class TestSingleFileCode:
    def test_path_fence_gives_named_file(self):
        a = build_stage_artifact(f"Here:\n\n{FENCE}cpp path=src/bsearch.cpp\nint main() {{}}\n{FENCE}", "code", "Binary Search")
        assert (a.artifact_type, a.name, a.files[0].path, a.files[0].language) == ("code", "bsearch.cpp", "src/bsearch.cpp", "cpp")

    @pytest.mark.parametrize("language, extension", [
        ("python", "py"), ("cpp", "cpp"), ("javascript", "js"), ("tsx", "tsx"), ("sql", "sql"), ("java", "java"),
    ])
    def test_single_unlabeled_block_becomes_a_file_named_after_the_stage(self, language, extension):
        text = f"Implementation:\n\n{FENCE}{language}\nbody\n{FENCE}\n\nIt runs in O(log n)."
        a = build_stage_artifact(text, "code", "Binary Search Implementation")
        assert a.artifact_type == "code"
        assert a.files[0].path == f"binary_search_implementation.{extension}"
        assert a.files[0].content == "body\n" and a.files[0].language == language

    @pytest.mark.parametrize("text", [
        f"{FENCE}python\na\n{FENCE}\n{FENCE}python\nb\n{FENCE}",   # several blocks: ambiguous
        f"{FENCE}\nno language\n{FENCE}",                          # unknown extension
        f"{FENCE}brainfuck\n+++\n{FENCE}",                         # unknown language
        f"{FENCE}python\ntruncated",                               # never closed
        f"{FENCE}python\n\n{FENCE}",                               # empty
    ])
    def test_ambiguous_or_unusable_unlabeled_blocks_give_no_artifact(self, text):
        assert build_stage_artifact(text, "code", "S") is None

    def test_unlabeled_fallback_is_not_used_for_projects_or_text_modes(self):
        text = f"{FENCE}python\nx = 1\n{FENCE}"
        assert build_stage_artifact(text, "project", "S") is None
        assert build_stage_artifact(text, "explanation", "S").files == []
        assert build_stage_artifact(text, None, "S") is None

    def test_path_fences_take_precedence_over_unlabeled_blocks(self):
        text = f"{FENCE}bash\npython main.py\n{FENCE}\n{FENCE}python path=main.py\nprint(1)\n{FENCE}"
        a = build_stage_artifact(text, "code", "S")
        assert [f.path for f in a.files] == ["main.py"]

    def test_extension_lookup(self):
        assert extension_for_language("Python") == "py" and extension_for_language("c++") == "cpp"
        assert extension_for_language(None) is None and extension_for_language("klingon") is None


class TestProjectContent:
    def test_nested_fences_and_exact_content_are_preserved(self):
        readme = f"# App\n\n{FENCE}bash\npip install -r requirements.txt\n{FENCE}\n\n  indented line\n"
        main = "from fastapi import FastAPI\n\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n\treturn {'ok': True}\n"
        text = (
            "Project below.\n\n"
            f"````markdown path=README.md\n{readme}````\n\n"
            f"{FENCE}python path=backend/main.py\n{main}{FENCE}\n\n"
            f"{FENCE}text path=requirements.txt\nfastapi\n{FENCE}\n"
        )
        a = build_stage_artifact(text, "project", "FastAPI CRUD")
        files = {f.path: f for f in a.files}
        assert list(files) == ["README.md", "backend/main.py", "requirements.txt"]
        assert files["README.md"].content == readme
        assert files["backend/main.py"].content == main
        assert "````" not in files["README.md"].content  # the outer fence is not part of the file


def _artifact(*paths: str, name: str = "FastAPI CRUD") -> Artifact:
    return Artifact(artifact_type="project", name=name,
                    files=[{"path": p, "content": f"content of {p}\n"} for p in paths])


class TestZip:
    def test_preserves_structure_under_one_root_folder(self):
        data = build_zip(_artifact("backend/main.py", "backend/routes/users.py", "tests/test_main.py", "README.md"))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert z.testzip() is None
            assert z.namelist() == [
                "fastapi-crud/backend/main.py", "fastapi-crud/backend/routes/users.py",
                "fastapi-crud/tests/test_main.py", "fastapi-crud/README.md",
            ]
            assert z.read("fastapi-crud/backend/routes/users.py") == b"content of backend/routes/users.py\n"

    def test_unicode_content_round_trips(self):
        a = Artifact(artifact_type="code", name="x.py", files=[{"path": "x.py", "content": "print('漢字 ✓ 😀')\n"}])
        with zipfile.ZipFile(io.BytesIO(build_zip(a))) as z:
            assert z.read("x.py/x.py").decode("utf-8") == "print('漢字 ✓ 😀')\n"

    def test_is_deterministic(self):
        assert build_zip(_artifact("a.py", "b/c.py")) == build_zip(_artifact("a.py", "b/c.py"))

    @pytest.mark.parametrize("bad", ["../evil.py", "/etc/passwd", "C:\\x.py", "\\\\srv\\share\\x.py", "a\x00.py"])
    def test_revalidates_paths_even_without_schema_validation(self, bad):
        unsafe = Artifact.model_construct(
            artifact_type="project", name="p", conflicts=[],
            files=[ArtifactFile.model_construct(path=bad, content="x", language="text")],
        )
        with pytest.raises(ExportError, match="Unsafe file path"):
            build_zip(unsafe)

    def test_rejects_duplicates_and_empty_artifacts(self):
        dup = Artifact.model_construct(
            artifact_type="project", name="p", conflicts=[],
            files=[ArtifactFile.model_construct(path=p, content="", language="text") for p in ("a.py", "A.py")],
        )
        with pytest.raises(ExportError, match="Duplicate"):
            build_zip(dup)
        with pytest.raises(ExportError, match="no files"):
            build_zip(Artifact(artifact_type="explanation", name="e"))

    @pytest.mark.parametrize("name, expected", [
        ("FastAPI CRUD!", "fastapi-crud"), ("../../etc", "etc"), ("漢字", "artifact"), ("binary_search.py", "binary_search.py"),
    ])
    def test_safe_filename(self, name, expected):
        assert safe_filename(name) == expected


class TestStagePrompt:
    BASE = "You are an AI assistant."

    @pytest.mark.parametrize("mode", [None, "", "explanation", "document", "unknown"])
    def test_other_stages_keep_the_exact_prompt(self, mode):
        assert stage_system_prompt(self.BASE, mode) == self.BASE

    @pytest.mark.parametrize("mode", ["code", "project", "structured"])
    def test_file_stages_get_the_fence_convention(self, mode):
        prompt = stage_system_prompt(self.BASE, mode)
        assert prompt.startswith(self.BASE) and "path=src/main.py" in prompt and "four-backtick" in prompt
