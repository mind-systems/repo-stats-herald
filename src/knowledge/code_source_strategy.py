import fnmatch
import os

from src.knowledge.source_strategy import SourceStrategy


class CodeSourceStrategy(SourceStrategy):
    """The one concrete code profile: selects a code-only project's source
    files. Complements, never replaces, `AiFactorySourceStrategy` — the two
    can run over the same tree without erroring or conflicting. Per-language
    config, auto-detection, and a profile registry are explicitly deferred;
    this stays a single hardcoded concrete strategy.
    """

    _SOURCE_ROOTS = ("src/", "lib/", "app/", "internal/", "pkg/", "cmd/")

    _SOURCE_EXTENSIONS = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".php",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".swift",
        ".dart",
        ".scala",
        ".vue",
    }

    _EXCLUDED_DIRS = {
        # tests
        "tests",
        "test",
        "__tests__",
        # vendored
        "node_modules",
        "vendor",
        "venv",
        ".venv",
        "third_party",
        "bower_components",
        ".yarn",
        # generated
        "dist",
        "build",
        "out",
        "target",
        ".next",
        "coverage",
        "__pycache__",
    }

    _EXCLUDED_FILE_GLOBS = (
        # tests
        "test_*.py",
        "*_test.*",
        "*.test.*",
        "*.spec.*",
        "*_spec.rb",
        # generated
        "*.min.js",
        "*.min.css",
        "*.d.ts",
        "*_pb2.py",
        "*_pb2_grpc.py",
        "*.pb.go",
        "*.g.dart",
        "*.generated.*",
    )

    def selects(self, path: str) -> bool:
        segments = path.split("/")
        if any(segment in self._EXCLUDED_DIRS for segment in segments):
            return False

        basename = segments[-1]
        if any(
            fnmatch.fnmatch(basename, pattern)
            for pattern in self._EXCLUDED_FILE_GLOBS
        ):
            return False

        return (
            path.startswith(self._SOURCE_ROOTS)
            and os.path.splitext(path)[1] in self._SOURCE_EXTENSIONS
        )
