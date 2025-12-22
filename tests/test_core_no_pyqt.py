"""Test that core package has no PyQt dependencies.

This test ensures the separation between core logic and visualization
is maintained, allowing the core package to be used with alternative frontends.
"""

import ast
import unittest
from pathlib import Path


PYQT_MODULES = {"PyQt5", "PyQt6", "PySide2", "PySide6", "pyqtgraph"}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor to collect all imported module names."""

    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            # Get the top-level module name
            module = alias.name.split(".")[0]
            self.imports.add(module)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            # Get the top-level module name
            module = node.module.split(".")[0]
            self.imports.add(module)
        self.generic_visit(node)


def get_imports_from_file(filepath: Path) -> set:
    """Extract all imported module names from a Python file."""
    try:
        with open(filepath, "r") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
    except SyntaxError:
        # Skip files with syntax errors
        return set()

    visitor = ImportVisitor()
    visitor.visit(tree)
    return visitor.imports


class TestCorePyQtFree(unittest.TestCase):
    """Test that core package has no PyQt/visualization dependencies."""

    def test_core_has_no_pyqt_imports(self):
        """No file in core/ should import PyQt or pyqtgraph."""
        core_dir = Path(__file__).parent.parent / "src" / "ephys_alignment_gui" / "core"

        violations = []
        for py_file in core_dir.glob("*.py"):
            imports = get_imports_from_file(py_file)
            pyqt_imports = imports & PYQT_MODULES
            if pyqt_imports:
                violations.append((py_file.name, pyqt_imports))

        if violations:
            msg_parts = ["PyQt imports found in core package:"]
            for filename, modules in violations:
                msg_parts.append(f"  {filename}: {', '.join(sorted(modules))}")
            self.fail("\n".join(msg_parts))

    def test_core_modules_importable(self):
        """Core modules should be importable without PyQt."""
        # These imports should succeed without PyQt being installed
        # (though in this test environment PyQt may be installed)
        from ephys_alignment_gui.core import (
            EphysAlignment,
            BrainAtlasAnatomical,
            interpolate_along_track
        )

        # Basic sanity checks
        self.assertTrue(callable(interpolate_along_track))



if __name__ == "__main__":
    unittest.main()
