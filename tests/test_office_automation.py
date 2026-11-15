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


def test_document_authoring_handled_directly_by_command_handler():
    """Verify that document authoring commands are handled directly by CommandHandler."""
    cmd = CommandHandler()
    handled, res = cmd.handle("open microsoft office and write a letter for me for next 3 days leave")
    assert handled is True
    assert res is not None
    assert "leave" in res.lower()
    assert "microsoft word" in res.lower()


def test_compound_action_bypasses_commands_handler():
    """Verify that general compound multi-step actions (non-document) bypass command regexes."""
    cmd = CommandHandler()
    handled, res = cmd.handle("launch chrome and search for weather")
    assert not handled
    assert res is None


def test_document_action_classified_as_command():
    """Verify that document/letter authoring commands are classified as COMMAND."""
    router = IntentRouter()
    result = router.classify("open microsoft office and write a letter for me for next 3 days leave")
    assert result.intent == IntentType.COMMAND
    assert result.subcategory == "office_document"


def test_compound_action_classified_as_complex():
    """Verify that general compound multi-step actions are classified as COMPLEX with tools enabled."""
    router = IntentRouter()
    result = router.classify("launch chrome and search for python documentation")
    assert result.intent == IntentType.COMPLEX
    assert result.needs_tools is True
    assert result.subcategory == "compound_action"


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


def test_open_app_params_alias_remapping():
    """Verify OpenAppParams accepts 'filename', 'app_name', etc. as aliases for 'name'."""
    from core.security.schemas import OpenAppParams
    params = OpenAppParams.model_validate({"filename": "Microsoft Office (Word)"})
    assert params.name == "Microsoft Office (Word)"

    params2 = OpenAppParams.model_validate({"app_name": "chrome"})
    assert params2.name == "chrome"


def test_create_office_document_params_alias_remapping():
    """Verify CreateOfficeDocumentParams accepts 'text', 'message' for 'content' and 'name' for 'filename'."""
    from core.security.schemas import CreateOfficeDocumentParams
    params = CreateOfficeDocumentParams.model_validate({
        "name": "vacation_leave.docx",
        "text": "Taking 3 days of leave starting from today.",
    })
    assert params.filename == "vacation_leave.docx"
    assert params.content == "Taking 3 days of leave starting from today."


def test_extract_text_tool_calls_from_llm_response():
    """Verify SonOrchestrator._extract_text_tool_calls extracts multiple tools from raw LLM apology text."""
    from core.orchestrator import SonOrchestrator
    orch = SonOrchestrator()

    llm_raw_response = (
        'Apologies for the inconvenience. Here is a new attempt at creating a letter for a 3-day leave, '
        'using a different approach:\n\n'
        '1. Open Microsoft Office (Word) by calling the "open_application" tool.\n'
        '2. Create a new document by calling the "create_office_document" tool.\n'
        '3. Type the following content into the document:\n'
        '"I am writing to inform you that I will be taking 3 days of leave starting from today. '
        'I appreciate your understanding and support during this time."\n\n'
        'Here is the revised tool call:\n\n'
        '{"name": "open_application", "parameters": {"filename":"Microsoft Office (Word)"}}; '
        '{"name": "create_office_document", "parameters": {"content":"I am writing to inform you that '
        'I will be taking 3 days of leave starting from today. I appreciate your understanding and support during this time."}}'
    )

    extracted = orch._extract_text_tool_calls(llm_raw_response)
    assert len(extracted) == 2

    assert extracted[0]["tool"] == "open_application"
    assert extracted[0]["args"].get("name") == "Microsoft Office (Word)" or extracted[0]["args"].get("filename") == "Microsoft Office (Word)"

    assert extracted[1]["tool"] == "create_office_document"
    assert "taking 3 days of leave" in extracted[1]["args"]["content"]


def test_app_registry_supports_office_word_parenthetical():
    """Verify APP_REGISTRY handles 'microsoft office (word)' variant without error."""
    assert "microsoft office (word)" in APP_REGISTRY
    assert APP_REGISTRY["microsoft office (word)"]["target"] == "winword"


def test_normalize_tool_call_aliasing():
    """Verify normalize_tool_call maps save_file, open_word, etc. to canonical tools."""
    from core.security.tool_registry import normalize_tool_call

    t_name, t_args = normalize_tool_call("save_file", {"filename": "leave_request.docx", "type": "docx"})
    assert t_name == "create_office_document"
    assert t_args["filename"] == "leave_request.docx"
    assert "content" in t_args
    assert "Dear Manager" in t_args["content"]

    t_name2, t_args2 = normalize_tool_call("open_word", {})
    assert t_name2 == "open_application"
    assert t_args2["name"] == "Microsoft Office (Word)"


def test_orchestrator_process_request_leave_letter_end_to_end():
    """Verify SonOrchestrator processes leave letter prompt with SUCCESS status and Word document creation."""
    from core.orchestrator import SonOrchestrator, OrchestrationStatus
    from core.security.context import create_trusted_context
    from core.security.session_manager import session_manager

    sess = session_manager.create_session(user_id="usr_primary", interface_type="desktop")
    ctx = create_trusted_context(user_id="usr_primary", session_id=sess.session_id, interface_type="desktop")
    orch = SonOrchestrator()

    resp = orch.process_request("open microsoft office and write a letter for me for next 3 days leave", ctx)
    assert resp.status == OrchestrationStatus.SUCCESS
    assert "leave" in resp.response_text.lower()
    assert "microsoft word" in resp.response_text.lower()
    assert resp.execution_metadata.get("duration_ms", 9999) < 2000


def test_edit_document_handled_directly_by_command_handler():
    """Verify that 'edit it make for 2 days to the principle' is handled directly."""
    cmd = CommandHandler()
    handled, res = cmd.handle("edit it make for 2 days to the principle")
    assert handled is True
    assert res is not None
    assert "updated" in res.lower()
    assert "2 days" in res.lower()
    assert "principal" in res.lower()


def test_edit_document_classified_as_command():
    """Verify that 'edit it make for 2 days to the principle' is classified as COMMAND."""
    router = IntentRouter()
    result = router.classify("edit it make for 2 days to the principle")
    assert result.intent == IntentType.COMMAND
    assert result.subcategory == "office_document"


def test_close_app_params_filename_alias():
    """Verify CloseAppParams remapping from filename to name (winword)."""
    from core.security.schemas import CloseAppParams
    params = CloseAppParams.model_validate({"filename": "leave_application.docx"})
    assert params.name == "winword"

