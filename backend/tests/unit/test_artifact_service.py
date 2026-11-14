"""Unit tests for the artifact service: fence parsing, stage artifacts, aggregation."""
import pytest

from backend.app.artifacts import Artifact, aggregate_artifacts, build_stage_artifact
from backend.app.artifacts.limits import MAX_FILE_BYTES, MAX_FILES, MAX_TOTAL_BYTES
from backend.app.artifacts.service import ArtifactParseError, language_for_path, parse_file_fences

FENCE = "```"


def fence(path: str, body: str, lang: str = "python", marker: str = FENCE) -> str:
    return f"{marker}{lang} path={path}\n{body}\n{marker}"


PROJECT_OUTPUT = "\n\n".join([
    "# FastAPI CRUD\n\nHere is the project.",
    fence("backend/main.py", "from fastapi import FastAPI\napp = FastAPI()"),
    fence("backend/routes/users.py", "router = None"),
    fence("requirements.txt", "fastapi==0.115.6", lang="text"),
    "Run it with `uvicorn backend.main:app`.",
])


class TestParseFileFences:
    def test_extracts_path_fences_in_order_with_content(self):
        files = parse_file_fences(PROJECT_OUTPUT)
        assert [f.path for f in files] == ["backend/main.py", "backend/routes/users.py", "requirements.txt"]
        assert files[0].content == "from fastapi import FastAPI\napp = FastAPI()\n"
        assert files[0].language == "python"
        assert files[2].language == "text"

    def test_ignores_fences_without_path(self):
        text = f"Example:\n\n{FENCE}python\nprint('demo')\n{FENCE}\n\n" + fence("main.py", "print(1)")
        assert [f.path for f in parse_file_fences(text)] == ["main.py"]
        assert parse_file_fences(f"{FENCE}python\nx = 1\n{FENCE}") == []

    def test_ignores_path_fences_shown_inside_another_fence(self):
        inner = fence("evil.py", "boom")
        nested = f"````markdown\nWrite files like this:\n{inner}\n````"
        assert parse_file_fences(nested) == []
        # With a ``` wrapper the inner opening line is just body text (a closing fence has no
        # info string); its closing ``` ends the wrapper and the wrapper's ``` opens a stray block
        same_length = f"{FENCE}markdown\nWrite files like this:\n{inner}\n{FENCE}"
        assert parse_file_fences(same_length) == []

    def test_longer_fence_allows_nested_code_blocks(self):
        readme = f"# Demo\n\n{FENCE}bash\npip install demo\n{FENCE}"
        files = parse_file_fences(fence("README.md", readme, lang="markdown", marker="````"))
        assert files[0].content == readme + "\n"

    def test_tilde_fences_and_quoted_paths(self):
        text = '~~~python path="src/my module.py"\nx = 1\n~~~\n' + f"{FENCE}json path='config/app.json'\n{{}}\n{FENCE}"
        files = parse_file_fences(text)
        assert [f.path for f in files] == ["src/my module.py", "config/app.json"]
        assert files[1].language == "json"

    def test_path_without_language_and_extra_attributes(self):
        text = f'{FENCE}path=src/util.ts title="Utils"\nexport {{}}\n{FENCE}'
        (f,) = parse_file_fences(text)
        assert f.path == "src/util.ts" and f.language is None

    def test_preserves_content_exactly_including_blank_lines_and_crlf(self):
        body = "def f():\r\n\r\n    return  1\t\r\n"
        (f,) = parse_file_fences(f"{FENCE}python path=a.py\r\n{body}{FENCE}\r\n")
        assert f.content == "def f():\n\n    return  1\t\n"

    def test_indented_fence_strips_only_the_fence_indent(self):
        text = "  ```python path=a.py\n  x = 1\n      y = 2\n  ```"
        (f,) = parse_file_fences(text)
        assert f.content == "x = 1\n    y = 2\n"

    def test_empty_file(self):
        (f,) = parse_file_fences(f"{FENCE}text path=empty.txt\n{FENCE}")
        assert f.content == ""

    @pytest.mark.parametrize("text", [
        f"{FENCE}python path=main.py\nprint(1)\n",                     # never closed (truncated)
        f"{FENCE}python path=\nx\n{FENCE}",                             # empty path
        f'{FENCE}python path=""\nx\n{FENCE}',                           # empty quoted path
        f'{FENCE}python path="main.py\nx\n{FENCE}',                     # unterminated quote
        f"{FENCE}python path=a.py path=b.py\nx\n{FENCE}",               # two paths
    ])
    def test_malformed_file_fences_raise(self, text):
        with pytest.raises(ArtifactParseError):
            parse_file_fences(text)

    def test_unclosed_ordinary_fence_is_not_an_error(self):
        assert parse_file_fences(f"{FENCE}python\nprint(1)\n") == []


class TestLanguageForPath:
    @pytest.mark.parametrize("path, language", [
        ("a.py", "python"), ("src/App.tsx", "tsx"), ("x.JS", "javascript"), ("q.sql", "sql"),
        ("c.yml", "yaml"), ("README.md", "markdown"), ("Main.java", "java"), ("m.cpp", "cpp"),
        ("Dockerfile", "text"), (".gitignore", "text"), ("weird.zzz", "text"),
    ])
    def test_maps_extensions(self, path, language):
        assert language_for_path(path) == language


class TestBuildStageArtifact:
    @pytest.mark.parametrize("mode", [None, "", "unknown", "PROJECT"])
    def test_no_or_unknown_mode_keeps_text_output(self, mode):
        assert build_stage_artifact(PROJECT_OUTPUT, mode, "Stage") is None

    @pytest.mark.parametrize("mode", ["explanation", "document"])
    def test_text_modes_give_file_less_artifacts(self, mode):
        a = build_stage_artifact("# Binary Trees\n\nA tree...", mode, "Explain binary trees")
        assert a.artifact_type == mode and a.files == [] and a.name == "Explain binary trees"

    def test_text_mode_does_not_extract_files(self):
        a = build_stage_artifact(PROJECT_OUTPUT, "explanation", "Explain")
        assert a.files == []

    @pytest.mark.parametrize("result", [None, "", "   \n"])
    def test_empty_result_gives_none(self, result):
        assert build_stage_artifact(result, "project", "Stage") is None

    def test_single_code_file(self):
        text = "Here you go:\n\n" + fence("algorithms/binary_search.py", "def search(xs, x):\n    ...")
        a = build_stage_artifact(text, "code", "Binary Search")
        assert a.artifact_type == "code"
        assert a.name == "binary_search.py"
        assert a.files[0].path == "algorithms/binary_search.py"
        assert a.files[0].content == "def search(xs, x):\n    ...\n"
        assert a.files[0].language == "python"

    def test_structured_single_file(self):
        a = build_stage_artifact(fence("config.yaml", "a: 1", lang="yaml"), "structured", "Config")
        assert a.artifact_type == "structured" and a.files[0].language == "yaml"

    def test_code_mode_with_several_files_becomes_project_keeping_all_files(self):
        a = build_stage_artifact(PROJECT_OUTPUT, "code", "FastAPI CRUD")
        assert a.artifact_type == "project"
        assert a.name == "FastAPI CRUD"
        assert [f.path for f in a.files] == ["backend/main.py", "backend/routes/users.py", "requirements.txt"]
        assert a.files[1].content == "router = None\n"

    def test_project_with_nested_folders_and_inferred_languages(self):
        text = "\n".join([
            f"{FENCE}path=src/app/main.py\nx\n{FENCE}",
            f"{FENCE}path=web/src/App.tsx\nx\n{FENCE}",
            f"{FENCE}path=README.md\n# hi\n{FENCE}",
        ])
        a = build_stage_artifact(text, "project", "Full stack")
        assert [(f.path, f.language) for f in a.files] == [
            ("src/app/main.py", "python"), ("web/src/App.tsx", "tsx"), ("README.md", "markdown"),
        ]

    def test_project_with_one_file_is_still_a_project(self):
        a = build_stage_artifact(fence("main.py", "x"), "project", "Tiny")
        assert a.artifact_type == "project" and len(a.files) == 1

    def test_paths_are_normalized(self):
        a = build_stage_artifact(fence(".\\src\\main.py", "x"), "code", "S")
        assert a.files[0].path == "src/main.py"

    def test_project_mode_without_file_fences_keeps_text_output(self):
        assert build_stage_artifact(f"Explanation\n\n{FENCE}python\nx = 1\n{FENCE}", "project", "S") is None

    @pytest.mark.parametrize("mode", ["code", "structured", "project"])
    def test_file_mode_with_only_prose_keeps_text_output(self, mode):
        assert build_stage_artifact("Just an explanation, no code.", mode, "S") is None

    # ---- all-or-nothing: one bad file rejects the whole artifact ----

    @pytest.mark.parametrize("bad_path", [
        "../../main.py", "/etc/passwd", "C:\\Users\\me\\x.py", "\\\\server\\share\\x.py", "src/../../x.py",
    ])
    def test_unsafe_path_rejects_whole_artifact(self, bad_path):
        text = fence("good.py", "ok") + "\n" + fence(bad_path, "evil")
        assert build_stage_artifact(text, "project", "S") is None

    def test_null_byte_in_path_rejects_whole_artifact(self):
        text = fence("good.py", "ok") + "\n" + fence("bad\x00.py", "evil")
        assert build_stage_artifact(text, "project", "S") is None

    @pytest.mark.parametrize("second", ["src/main.py", "./src/main.py", "SRC/Main.py", "src\\main.py"])
    def test_duplicate_paths_in_one_stage_reject_whole_artifact(self, second):
        text = fence("src/main.py", "v1") + "\n" + fence(second, "v2")
        assert build_stage_artifact(text, "project", "S") is None

    def test_file_and_directory_clash_rejects_whole_artifact(self):
        text = fence("src", "x", lang="text") + "\n" + fence("src/main.py", "y")
        assert build_stage_artifact(text, "project", "S") is None

    def test_truncated_output_rejects_whole_artifact(self):
        text = fence("a.py", "ok") + "\n" + f"{FENCE}python path=b.py\nhalf a fi"
        assert build_stage_artifact(text, "project", "S") is None

    def test_malformed_fence_rejects_whole_artifact(self):
        text = fence("a.py", "ok") + "\n" + f"{FENCE}python path=\nx\n{FENCE}"
        assert build_stage_artifact(text, "project", "S") is None

    def test_invalid_language_tag_rejects_whole_artifact(self):
        text = fence("a.py", "ok") + "\n" + fence("b.py", "x", lang="{python}")
        assert build_stage_artifact(text, "project", "S") is None

    def test_file_over_size_limit_rejects_whole_artifact(self):
        text = fence("small.py", "ok") + "\n" + fence("big.txt", "x" * MAX_FILE_BYTES, lang="text")
        assert build_stage_artifact(text, "project", "S") is None

    def test_file_exactly_at_size_limit_is_accepted(self):
        body = "x" * (MAX_FILE_BYTES - 1)  # parser adds the trailing newline
        a = build_stage_artifact(fence("big.txt", body, lang="text"), "project", "S")
        assert a is not None and len(a.files[0].content) == MAX_FILE_BYTES

    def test_total_over_size_limit_rejects_whole_artifact(self):
        chunk = "x" * (MAX_FILE_BYTES - 1)
        count = MAX_TOTAL_BYTES // MAX_FILE_BYTES + 1
        text = "\n".join(fence(f"f{i}.txt", chunk, lang="text") for i in range(count))
        assert build_stage_artifact(text, "project", "S") is None

    def test_too_many_files_rejects_whole_artifact(self):
        text = "\n".join(fence(f"f{i}.py", "x") for i in range(MAX_FILES + 1))
        assert build_stage_artifact(text, "project", "S") is None
        ok = "\n".join(fence(f"f{i}.py", "x") for i in range(MAX_FILES))
        assert len(build_stage_artifact(ok, "project", "S").files) == MAX_FILES

    def test_result_text_is_never_modified(self):
        original = PROJECT_OUTPUT
        snapshot = str(original)
        build_stage_artifact(original, "project", "S")
        build_stage_artifact(original + "\n" + fence("../x.py", "y"), "project", "S")
        assert original == snapshot

    def test_unexpected_errors_fall_back_to_none(self, monkeypatch):
        from backend.app.artifacts import service

        def explode(_text):
            raise RuntimeError("parser bug")
        monkeypatch.setattr(service, "_scan_fences", explode)
        assert build_stage_artifact(PROJECT_OUTPUT, "project", "S") is None

    def test_blank_name_gets_a_default(self):
        assert build_stage_artifact(PROJECT_OUTPUT, "project", "  ").name == "artifact"


def _project(*files: tuple[str, str]) -> Artifact:
    return Artifact(artifact_type="project", name="p",
                    files=[{"path": p, "content": c} for p, c in files])


class TestAggregateArtifacts:
    def test_merges_stage_files_in_order_preserving_structure(self):
        merged = aggregate_artifacts([
            ("Requirements", None),
            ("Architecture", Artifact(artifact_type="explanation", name="Arch")),
            ("Backend", _project(("backend/main.py", "app"))),
            ("Testing", _project(("tests/test_main.py", "def test(): ..."))),
            ("Docs", Artifact(artifact_type="code", name="README.md",
                              files=[{"path": "README.md", "content": "# P", "language": "markdown"}])),
        ], "My Project")
        assert merged.artifact_type == "project" and merged.name == "My Project"
        assert [f.path for f in merged.files] == ["backend/main.py", "tests/test_main.py", "README.md"]
        assert merged.files[2].language == "markdown"
        assert merged.conflicts == []

    @pytest.mark.parametrize("sources", [
        [],
        [("A", None), ("B", None)],
        [("A", _project(("a.py", "x")))],
        [("A", _project(("a.py", "x"))), ("B", Artifact(artifact_type="document", name="d"))],
    ])
    def test_needs_at_least_two_file_producing_stages(self, sources):
        assert aggregate_artifacts(sources, "P") is None

    def test_same_path_conflict_is_recorded_and_later_stage_wins(self):
        merged = aggregate_artifacts([
            ("Implementation", _project(("README.md", "v1"), ("main.py", "x"))),
            ("Documentation", _project(("README.md", "v2"))),
        ], "P")
        assert [f.path for f in merged.files] == ["README.md", "main.py"]
        assert merged.files[0].content == "v2"
        assert len(merged.conflicts) == 1
        c = merged.conflicts[0]
        assert (c.path, c.kept_from, c.overridden_from) == ("README.md", "Documentation", "Implementation")

    def test_case_only_conflict_is_recorded(self):
        merged = aggregate_artifacts([
            ("A", _project(("README.md", "v1"))),
            ("B", _project(("readme.md", "v2"))),
        ], "P")
        assert len(merged.files) == 1 and merged.files[0].path == "readme.md"
        assert merged.conflicts[0].overridden_from == "A"

    def test_identical_file_from_two_stages_is_not_a_conflict(self):
        merged = aggregate_artifacts([
            ("A", _project(("shared.py", "same"))),
            ("B", _project(("shared.py", "same"), ("b.py", "b"))),
        ], "P")
        assert [f.path for f in merged.files] == ["shared.py", "b.py"] and merged.conflicts == []

    def test_repeated_overrides_are_each_recorded(self):
        merged = aggregate_artifacts([
            ("A", _project(("x.py", "1"))), ("B", _project(("x.py", "2"))), ("C", _project(("x.py", "3"))),
        ], "P")
        assert merged.files[0].content == "3"
        assert [(c.kept_from, c.overridden_from) for c in merged.conflicts] == [("B", "A"), ("C", "B")]

    def test_file_directory_clash_across_stages_gives_none(self):
        assert aggregate_artifacts([
            ("A", _project(("src", "x"))), ("B", _project(("src/main.py", "y"))),
        ], "P") is None

    def test_combined_size_over_limit_gives_none(self):
        chunk = "x" * MAX_FILE_BYTES
        per_stage = MAX_TOTAL_BYTES // MAX_FILE_BYTES
        a = _project(*[(f"a{i}.txt", chunk) for i in range(per_stage)])
        b = _project(("b.txt", chunk))
        assert aggregate_artifacts([("A", a), ("B", b)], "P") is None

    def test_inputs_are_not_modified(self):
        a, b = _project(("x.py", "1")), _project(("x.py", "2"))
        before = (a.model_dump(), b.model_dump())
        aggregate_artifacts([("A", a), ("B", b)], "P")
        assert (a.model_dump(), b.model_dump()) == before
