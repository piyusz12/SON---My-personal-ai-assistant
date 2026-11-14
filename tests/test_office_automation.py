# tests/test_office_automation.py — Tests for Microsoft Office Automation and Compound Routing
import os
import pytest
from pathlib import Path

from commands import CommandHandler
from core.intent_router import IntentRouter, IntentType
from tools.windows_control import APP_REGISTRY, create_office_document
from plugins.windows import WindowsPlugin
from core.security.tool_registry import defensive_tool_registry
from core.security.pydantic_agent import DefensivePydanticAgent


def test_compound_action_bypasses_commands_handler():
    """Verify that compound multi-step actions are not swallowed by simple command regexes."""
    cmd = CommandHandler()
    handled, res = cmd.handle("open microsoft office and write a letter for me for next 3 days leave")
    assert not handled
    assert res is None

    handled2, res2 = cmd.handle("open word then draft a resignation letter")
    assert not handled2
    assert res2 is None


def test_compound_action_classified_as_complex():
    """Verify that compound multi-step actions are classified as COMPLEX with tools enabled."""
    router = IntentRouter()
    result = router.classify("open microsoft office and write a letter for me for next 3 days leave")
    assert result.intent == IntentType.COMPLEX
    assert result.needs_tools is True
    assert result.subcategory == "compound_action"

    result2 = router.classify("launch word and type hello world")
    assert result2.intent == IntentType.COMPLEX
    assert result2.needs_tools is True


def test_office_app_registry_and_fallbacks():
    """Verify Microsoft Office suite is registered in APP_REGISTRY with fallback paths."""
    assert "word" in APP_REGISTRY
    assert "microsoft word" in APP_REGISTRY
    assert "ms word" in APP_REGISTRY
    assert "winword" in APP_REGISTRY
    assert "office" in APP_REGISTRY
    assert "microsoft office" in APP_REGISTRY
    assert "excel" in APP_REGISTRY
    assert "powerpoint" in APP_REGISTRY

    word_entry = APP_REGISTRY["microsoft office"]
    assert "fallbacks" in word_entry
    assert any("WINWORD.EXE" in fb for fb in word_entry["fallbacks"])


def test_create_office_document_creates_valid_docx():
    """Verify create_office_document creates a valid .docx document on disk."""
    import docx

    test_filename = "test_pytest_leave_letter.docx"
    content = "Dear Manager,\n\nI am writing to request leave for the next 3 days.\n\nThank you."
    title = "Leave Application - Test"

    res = create_office_document(
        filename=test_filename,
        content=content,
        title=title,
        open_after=False
    )
    assert "Created document" in res

    target_path = Path.home() / "Documents" / test_filename
    try:
        assert target_path.exists()
        doc = docx.Document(str(target_path))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Leave Application - Test" in full_text
        assert "Dear Manager," in full_text
        assert "request leave for the next 3 days" in full_text
    finally:
        target_path.unlink(missing_ok=True)


def test_defensive_tool_registry_has_office_tools():
    """Verify create_office_document and type_message are in defensive tool registry."""
    tool1 = defensive_tool_registry.get_tool("create_office_document")
    assert tool1 is not None
    assert tool1.name == "create_office_document"

    tool2 = defensive_tool_registry.get_tool("type_message")
    assert tool2 is not None
    assert tool2.name == "type_message"


def test_pydantic_agent_has_office_tools():
    """Verify DefensivePydanticAgent exposes create_office_document and type_message."""
    agent = DefensivePydanticAgent(model="test")
    tool_names = [t.name for t in agent.tools]
    assert "create_office_document" in tool_names
    assert "type_message" in tool_names
    assert "open_application" in tool_names


def test_windows_plugin_exposes_create_office_document():
    """Verify WindowsPlugin exposes create_office_document tool."""
    plugin = WindowsPlugin()
    plugin.initialize()
    assert "create_office_document" in plugin.tools
    tool = plugin.tools["create_office_document"]
    assert callable(tool["func"])
