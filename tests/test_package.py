"""Package-level invariants: version sync and public exports."""

import re
from pathlib import Path

import autarkia


def test_version_matches_pyproject():
    """``__version__`` drifting from pyproject is how PyPI gets a wrong release."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = re.search(r'^version = "([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
    assert declared is not None
    assert autarkia.__version__ == declared.group(1)


def test_public_exports_are_importable():
    for name in autarkia.__all__:
        assert hasattr(autarkia, name)


def test_tool_host_protocol_is_exported():
    from autarkia import ToolHost

    class Host:
        tool_registry = object()

    assert isinstance(Host(), ToolHost)


def test_submodules_export_matches_root():
    from autarkia import tools

    assert set(tools.__all__) <= set(autarkia.__all__)
