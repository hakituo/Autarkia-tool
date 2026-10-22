import asyncio

import pytest

from autarkia.tools import BaseTool
from tests.conftest import EchoTool


def test_base_tool_is_abstract():
    with pytest.raises(TypeError):
        BaseTool()


def test_run_returns_string_and_stringifies_result():
    tool = EchoTool()
    assert asyncio.run(tool.run(text="hi", times=2)) == "hihi"


def test_run_converts_exceptions_to_error_strings():
    class BrokenTool(EchoTool):
        name = "broken"

        async def _run(self, text: str, times: int = 1) -> str:
            raise RuntimeError("weather api timed out")

    result = asyncio.run(BrokenTool().run(text="hi"))
    assert "broken" in result
    assert "weather api timed out" in result


def test_is_master_via_flag():
    tool = EchoTool()
    tool.set_runtime_context({"is_master": True})
    assert tool.is_master() is True


def test_is_master_via_id_list():
    tool = EchoTool()
    tool.set_runtime_context({"user_id": "42", "master_ids": [42, "7"]})
    assert tool.is_master() is True

    tool.set_runtime_context({"user_id": "99", "master_ids": [42]})
    assert tool.is_master() is False


def test_is_master_defaults_false():
    tool = EchoTool()
    tool.set_runtime_context({"user_id": "someone"})
    assert tool.is_master() is False


def test_current_scope_prefers_scope_over_persona_filename():
    tool = EchoTool()
    tool.set_runtime_context({"scope": "ling", "persona_filename": "ye.json"})
    assert tool.current_scope() == "ling"

    tool.set_runtime_context({"persona_filename": "ye.json"})
    assert tool.current_scope() == "ye.json"


def test_current_scope_empty_without_context():
    tool = EchoTool()
    assert tool.current_scope() == ""
