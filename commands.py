# commands.py — Special Command Handlers for SON
"""
Parses and executes text/voice commands that bypass the LLM.
Pattern-matched commands are handled directly for speed.
Everything else goes to the Brain (LLM) which can use tool calling.
"""
import re
from pathlib import Path

import config
from services.whatsapp.service import WhatsAppVoiceService


class CommandHandler:
    """
    Parses and executes special voice/text commands.
    Returns (handled: bool, response: str | None).
    """

    def __init__(self, memory, codebase, brain, ui=None, tool_registry=None, orchestrator=None):
        self._memory = memory
        self._codebase = codebase
        self._brain = brain
        self._ui = ui
        self._tools = tool_registry
        self._orchestrator = orchestrator
        self.whatsapp = WhatsAppVoiceService.get_instance()


        # Command patterns (order matters — first match wins)
        self._commands = [
            # ── Codebase ──
            (r"^(scan|index)\s+(my\s+)?project\s*(.*)$", self._cmd_scan),
            (r"^(scan|index)\s+(.+)$", self._cmd_scan_path),
            (r"^what\s+changed\s*(today|recently|this week)?", self._cmd_what_changed),
            (r"^progress\s+report\s*(.*)$", self._cmd_progress),

            # ── Memory ──
            (r"^remember\s+that\s+(.+)$", self._cmd_remember),
            (r"^forget\s+(about\s+)?(.+)$", self._cmd_forget),

            # ── Codebase browsing ──
            (r"^(list|show)\s+(project\s+)?files\s*(.*)$", self._cmd_list_files),
            (r"^(recent\s+)?commits\s*(.*)$", self._cmd_commits),

            # ── PC Control (direct, no LLM needed) ──
            (r"^open\s+(.+)$", self._cmd_open_app),
            (r"^close\s+(.+)$", self._cmd_close_app),
            (r"^(?:type|write)\s+(?:in|into|to|on)\s+(?:the\s+)?(.+?)\s*:\s*(.+)$", self._cmd_type_colon),
            (r"^(?:type|write)\s+(?:a\s+)?(?:message\s+)?['\"](.+?)['\"]\s+(?:in|into|to|on)\s+(?:the\s+)?(.+)$", self._cmd_type_quoted_to),
            (r"^(?:type|write)\s+(?:a\s+)?(?:message\s+)?(.+?)\s+(?:in|into|to|on)\s+(?:the\s+)?(whatsapp|discord|slack|telegram|teams|chrome|opera|edge|firefox|browser|chatgpt)$", self._cmd_type_unquoted_to),
            (r"^send\s+(?:a\s+)?message\s+(?:to\s+(.+?)\s+)?(?:on|in)\s+(whatsapp|discord|slack|telegram|teams|chatgpt|browser|web)\s*:\s*(.+)$", self._cmd_send_web_colon),
            (r"^send\s+(?:a\s+)?(?:whatsapp|discord|slack|telegram)\s+message\s+(?:to\s+(.+?)\s+)?(?:saying|with)?\s*[:\"']?\s*(.+?)[\"']?$", self._cmd_send_web_saying),
            (r"^(?:type|write)\s+['\"](.+?)['\"]$", self._cmd_type_active),
            (r"^(?:list|show|what)\s+(?:open\s+)?(?:windows|apps|web\s*apps)$", self._cmd_list_windows),
            (r"^volume\s+(\d+)$", self._cmd_set_volume),
            (r"^brightness\s+(\d+)$", self._cmd_set_brightness),
            (r"^screenshot$", self._cmd_screenshot),
            (r"^(system\s+info|sysinfo|system\s+status)$", self._cmd_system_info),
            (r"^(what'?s?\s+on\s+my\s+screen|look\s+at\s+(my\s+)?screen)$", self._cmd_look_at_screen),

            # ── Camera Vision (direct, no LLM needed) ──
            (r"^(can\s+you\s+see\s+me|can\s+you\s+see|do\s+you\s+see\s+me|look\s+at\s+me|see\s+me)\??$", self._cmd_camera_see_me),
            (r"^(is\s+(anyone|anybody|someone)\s+in\s+the\s+room|is\s+someone\s+here|anyone\s+there|is\s+anybody\s+there)\??$", self._cmd_camera_presence),
            (r"^(how\s+many\s+people\s+(are\s+there|in\s+the\s+room|do\s+you\s+see)|count\s+people|what\s+do\s+you\s+see)\??$", self._cmd_camera_count),
            (r"^(do\s+you\s+recognize\s+(this\s+person|me)|who\s+am\s+i|who\s+is\s+(this|here|in\s+front\s+of\s+(you|the\s+camera))|who\s+do\s+you\s+see)\??$", self._cmd_camera_recognize),
            (r"^(enroll|add|register)\s+person\s+(.+)$", self._cmd_camera_enroll),
            (r"^(pause|disable|turn\s+off|stop|close|shut\s+down)\s+camera$", self._cmd_camera_pause),
            (r"^(resume|enable|turn\s+on|start|open|activate)\s+camera$", self._cmd_camera_resume),
            (r"^camera\s+(status|info)$", self._cmd_camera_status),

            # ── Web (direct) ──
            (r"^(?:open|go\s+to|visit|launch)\s+(?:website\s+|site\s+)?(https?://\S+|www\.\S+|\w+\.(?:com|org|io|net|edu|ai|gov|dev|app|co|in)\S*|youtube|github|reddit|chatgpt|google|gmail|twitter|x|amazon|netflix|spotify|wikipedia|stackoverflow|linkedin|huggingface|twitch|discord|whatsapp)$", self._cmd_open_website),
            (r"^(?:search|look\s+up|find)\s+(google|youtube|github|reddit|wikipedia|amazon|stackoverflow|twitter|x|duckduckgo)\s+(?:for\s+)?(.+)$", self._cmd_search_platform),
            (r"^(?:google|search\s+(?:the\s+web\s+for|the\s+internet\s+for|for)?)\s*(.+)$", self._cmd_web_search),
            (r"^weather\s*(.*)$", self._cmd_weather),
            (r"^news\s*(.*)$", self._cmd_news),

            # ── Automation ──
            (r"^(morning|coding|goodnight)\s+routine$", self._cmd_run_routine),
            (r"^run\s+routine\s+(.+)$", self._cmd_run_routine_named),
            (r"^list\s+routines?$", self._cmd_list_routines),

            # ── Docker ──
            (r"^(docker|containers?)\s+(list|ps|status)$", self._cmd_docker_list),
            (r"^(docker\s+)?(start|stop|restart)\s+container\s+(.+)$", self._cmd_docker_action),

            # ── Seamless Voice Conversation ──
            (r"^(?:talk\s+(?:with|to)\s+me|let'?s\s+talk|start\s+(?:a\s+)?(?:voice\s+)?conversation|hands\s*free|continuous\s+voice|voice\s+mode)$", self._cmd_start_seamless_voice),

            # ── WhatsApp Contact Management ──
            (r"^(?:add\s+contact|new\s+contact)\s+(.+?)\s+(?:with\s+number|number)\s+(.+)$", self._cmd_add_contact),
            (r"^(?:list\s+contacts|show\s+contacts)$", self._cmd_list_contacts),
            (r"^(?:remove\s+contact|delete\s+contact)\s+(.+)$", self._cmd_remove_contact),

            # ── System ──
            (r"^memory\s+stats?$", self._cmd_memory_stats),
            (r"^(list\s+)?tools$", self._cmd_list_tools),
            (r"^clear\s+history$", self._cmd_clear_history),
            (r"^(help|commands)$", self._cmd_help),
            (r"^(exit|quit|bye|goodbye)$", self._cmd_exit),
        ]

    def handle(self, text: str) -> tuple[bool, str | None]:
        """
        Check if text matches a special command.

        Returns:
            (True, response_string) if handled,
            (False, None) if not a command — pass to LLM.
        """
        # 0. WhatsApp Voice Messaging Workflow (Drafting, Confirmation, Editing, Cancellation)
        if getattr(config, "WHATSAPP_ENABLED", True) and hasattr(self, "whatsapp"):
            handled, wa_result = self.whatsapp.handle_voice_turn(text, brain_client=self._brain)
            if handled:
                active = self.whatsapp.state_machine.active_draft
                if active and self._ui and hasattr(self._ui, "show_whatsapp_draft_card"):
                    from services.whatsapp.models import DraftStatus
                    if active.status == DraftStatus.AWAITING_CONFIRMATION:
                        self._ui.show_whatsapp_draft_card(
                            recipient=active.recipient_name,
                            masked_phone=active.contact.masked_phone,
                            message=active.message_text,
                            remaining_seconds=active.remaining_seconds,
                        )
                    elif active.status == DraftStatus.WHATSAPP_DRAFT_OPENED:
                        self._ui.show_whatsapp_confirmed(active.recipient_name, active.contact.masked_phone)
                    elif active.status == DraftStatus.CANCELLED:
                        self._ui.show_whatsapp_cancelled(active.recipient_name)
                return (True, wa_result)

        cleaned = text.strip().lower()

        for pattern, handler in self._commands:
            match = re.match(pattern, cleaned, re.IGNORECASE)
            if match:
                try:
                    result = handler(match)
                    return (True, result)
                except Exception as e:
                    return (True, f"Command failed: {e}")

        return (False, None)

    # ══════════════════════════════════════════════════════════
    #  Codebase Commands
    # ══════════════════════════════════════════════════════════

    def _cmd_scan(self, match) -> str:
        """Scan default project paths."""
        path_hint = match.group(3).strip() if match.group(3) else None

        if path_hint:
            # Try to resolve the path
            for proj in config.DEFAULT_PROJECT_PATHS:
                if path_hint.lower() in proj.lower():
                    return self._do_scan(proj)
            return f"Project '{path_hint}' not found in configured paths."

        # Scan all configured projects
        results = []
        for proj in config.DEFAULT_PROJECT_PATHS:
            result = self._do_scan(proj)
            results.append(result)

        return "\n".join(results)

    def _cmd_scan_path(self, match) -> str:
        """Scan a specific path."""
        raw_path = match.group(2).strip().strip('"').strip("'")
        path = Path(raw_path)

        if not path.exists():
            return f"Path not found: {raw_path}"

        return self._do_scan(str(path))

    def _do_scan(self, project_path: str) -> str:
        """Execute the actual scan."""
        project_name = Path(project_path).name

        def on_progress(current, total, filename):
            if self._ui:
                self._ui.update_status(f"Scanning {filename}... ({current}/{total})")

        stats = self._codebase.scan(project_path, on_progress=on_progress)

        return (
            f"Scanned {project_name}: "
            f"{stats['files_scanned']} files, "
            f"{stats['chunks_embedded']} chunks embedded."
        )

    def _cmd_what_changed(self, match) -> str:
        """Show uncommitted changes."""
        parts = []
        for proj in config.DEFAULT_PROJECT_PATHS:
            name = Path(proj).name
            diff = self._codebase.get_diff_summary(proj)
            parts.append(f"[{name}]\n{diff}")

        return "\n\n".join(parts)

    def _cmd_progress(self, match) -> str:
        """Generate a progress report."""
        days_str = match.group(1).strip() if match.group(1) else ""
        days = 7

        day_match = re.search(r"(\d+)\s*days?", days_str)
        if day_match:
            days = int(day_match.group(1))

        parts = []
        for proj in config.DEFAULT_PROJECT_PATHS:
            report = self._codebase.get_progress_report(proj, days=days)
            parts.append(report)

        return "\n\n".join(parts)

    # ══════════════════════════════════════════════════════════
    #  Memory Commands
    # ══════════════════════════════════════════════════════════

    def _cmd_remember(self, match) -> str:
        """Store a fact in persistent memory."""
        fact = match.group(1).strip()
        self._memory.store_fact(fact)
        return f'Remembered: "{fact}"'

    def _cmd_forget(self, match) -> str:
        """Remove a fact from memory."""
        fact = match.group(2).strip()
        self._memory.forget_fact(fact)
        return f'Forgot about: "{fact}"'

    # ══════════════════════════════════════════════════════════
    #  File / Git Commands
    # ══════════════════════════════════════════════════════════

    def _cmd_list_files(self, match) -> str:
        """List project files."""
        results = []
        for proj in config.DEFAULT_PROJECT_PATHS:
            name = Path(proj).name
            files = self._codebase.list_project_files(proj)
            file_list = "\n".join(f"  {f}" for f in files[:30])
            if len(files) > 30:
                file_list += f"\n  ... and {len(files) - 30} more"
            results.append(f"[{name}] ({len(files)} files)\n{file_list}")

        return "\n\n".join(results)

    def _cmd_commits(self, match) -> str:
        """Show recent commits."""
        results = []
        for proj in config.DEFAULT_PROJECT_PATHS:
            name = Path(proj).name
            commits = self._codebase.get_recent_commits(proj, count=10)
            if not commits:
                results.append(f"[{name}] No git history found.")
                continue

            lines = [f"[{name}] Recent commits:"]
            for c in commits:
                lines.append(f"  {c['hash']} | {c['date'][:10]} | {c['message']}")
            results.append("\n".join(lines))

        return "\n\n".join(results)

    # ══════════════════════════════════════════════════════════
    #  PC Control Commands (Direct)
    # ══════════════════════════════════════════════════════════

    def _execute_tool_safe(self, tool_name: str, arguments: dict, tool_func=None) -> str:
        """
        Execute tool through central orchestrator.
        Never bypasses policy evaluation or approval gating.
        """
        from core.security.context import create_trusted_context
        ctx = create_trusted_context(user_id="primary_user", interface_type="cli", session_id="cli_command_session")
        if self._orchestrator:
            res = self._orchestrator.execute_action(tool_name, arguments, context=ctx, tool_func=tool_func)
            return res.output
        else:
            from core.orchestrator import orchestrator as global_orch
            res = global_orch.execute_action(tool_name, arguments, context=ctx, tool_func=tool_func)
            return res.output

    def _cmd_open_app(self, match) -> str:
        """Open an application or popular website."""
        from tools.windows_control import open_application
        from tools.web import POPULAR_SITES, open_website
        name = match.group(1).strip()
        cleaned = name.lower().replace(" ", "")
        if cleaned in POPULAR_SITES or name.startswith(("http://", "https://", "www.")) or ("." in name and " " not in name):
            return self._execute_tool_safe("open_website", {"url": name}, tool_func=open_website)
        return self._execute_tool_safe("open_application", {"name": name}, tool_func=open_application)

    def _cmd_close_app(self, match) -> str:
        """Close an application."""
        from tools.windows_control import close_application
        name = match.group(1).strip()
        return self._execute_tool_safe("close_application", {"name": name}, tool_func=close_application)

    def _cmd_type_colon(self, match) -> str:
        """Type message into app specified before colon: 'type into whatsapp: hello'"""
        from tools.windows_control import type_message
        app = match.group(1).strip()
        msg = match.group(2).strip()
        return self._execute_tool_safe("type_message", {"message": msg, "app_name_or_title": app, "press_enter": False}, tool_func=type_message)

    def _cmd_type_quoted_to(self, match) -> str:
        """Type quoted message to app: 'type \"hello\" in whatsapp'"""
        from tools.windows_control import type_message
        msg = match.group(1).strip()
        app = match.group(2).strip()
        return self._execute_tool_safe("type_message", {"message": msg, "app_name_or_title": app, "press_enter": False}, tool_func=type_message)

    def _cmd_type_unquoted_to(self, match) -> str:
        """Type unquoted message to known app: 'type hello in whatsapp'"""
        from tools.windows_control import type_message
        msg = match.group(1).strip()
        app = match.group(2).strip()
        return self._execute_tool_safe("type_message", {"message": msg, "app_name_or_title": app, "press_enter": False}, tool_func=type_message)

    def _cmd_send_web_colon(self, match) -> str:
        """Send message to web app with colon: 'send message to Dad on whatsapp: on my way'"""
        from tools.windows_control import send_web_message
        recipient = (match.group(1) or "").strip()
        platform = match.group(2).strip()
        msg = match.group(3).strip()
        return self._execute_tool_safe("send_web_message", {"platform": platform, "message": msg, "recipient": recipient, "press_enter": True}, tool_func=send_web_message)

    def _cmd_send_web_saying(self, match) -> str:
        """Send web message with saying: 'send whatsapp message to Mom saying I will be home soon'"""
        from tools.windows_control import send_web_message
        recipient = (match.group(1) or "").strip()
        msg = match.group(2).strip()
        return self._execute_tool_safe("send_web_message", {"platform": "whatsapp", "message": msg, "recipient": recipient, "press_enter": True}, tool_func=send_web_message)

    def _cmd_type_active(self, match) -> str:
        """Type message into currently active window: 'type \"hello\"'"""
        from tools.windows_control import type_message
        msg = match.group(1).strip()
        return self._execute_tool_safe("type_message", {"message": msg, "app_name_or_title": "", "press_enter": False}, tool_func=type_message)

    def _cmd_list_windows(self, match) -> str:
        """List open windows and web applications."""
        from tools.windows_control import list_open_windows
        return self._execute_tool_safe("list_open_windows", {}, tool_func=list_open_windows)

    def _cmd_set_volume(self, match) -> str:
        """Set volume level."""
        from tools.windows_control import set_volume
        level = int(match.group(1))
        return self._execute_tool_safe("set_volume", {"level": level}, tool_func=set_volume)

    def _cmd_set_brightness(self, match) -> str:
        """Set brightness level."""
        from tools.windows_control import set_brightness
        level = int(match.group(1))
        return self._execute_tool_safe("set_brightness", {"level": level}, tool_func=set_brightness)

    def _cmd_screenshot(self, match) -> str:
        """Take a screenshot."""
        from vision import take_screenshot
        return self._execute_tool_safe("take_screenshot", {}, tool_func=take_screenshot)

    def _cmd_system_info(self, match) -> str:
        """Get system info."""
        from tools.windows_control import get_system_info
        return self._execute_tool_safe("get_system_info", {}, tool_func=get_system_info)

    def _cmd_look_at_screen(self, match) -> str:
        """Analyze what's on screen."""
        from vision.screen.analysis import ScreenAnalyzer
        analyzer = ScreenAnalyzer(brain=self._brain)
        return analyzer.analyze_screen("Describe what you see on the screen.")

    # ══════════════════════════════════════════════════════════
    #  Camera Vision Commands (Direct)
    # ══════════════════════════════════════════════════════════

    def _cmd_camera_see_me(self, match) -> str:
        """Check if camera sees the user and identify them."""
        from vision.camera.capture import CameraManager
        from vision.camera.detection import PersonDetector
        from vision.camera.recognition import FaceRecognizer
        from memory.structured_memory import StructuredMemory

        cam = CameraManager()
        if not cam.privacy.camera_active:
            return "Camera is currently turned off for privacy, Dad. Say 'turn on camera' or 'resume camera' to activate it."

        frame = cam.get_frame()
        if frame is None:
            return "I am unable to capture a frame from the webcam right now, Dad."

        detector = PersonDetector()
        res = detector.detect(frame)
        if not res.person_present:
            return "My camera is active, but I don't see anyone in front of the lens right now, Dad."

        rec = FaceRecognizer(structured_memory=StructuredMemory())
        is_known, rec_msg = rec.identify_person_in_frame(frame)
        if is_known:
            return f"Yes Dad! I can see you clearly. {rec_msg}"
        return f"Yes Dad! I can see someone in front of the camera. {rec_msg}"

    def _cmd_camera_presence(self, match) -> str:
        """Detect whether a person is in the room."""
        from vision.camera.capture import CameraManager
        from vision.camera.detection import PersonDetector
        cam = CameraManager()
        if not cam.privacy.camera_active:
            return "Camera is currently turned off for privacy, Dad. Say 'turn on camera' to check the room."
        frame = cam.get_frame()
        detector = PersonDetector()
        _, message = detector.is_anyone_present(frame)
        return message

    def _cmd_camera_count(self, match) -> str:
        """Count people in the room."""
        from vision.camera.capture import CameraManager
        from vision.camera.detection import PersonDetector
        cam = CameraManager()
        if not cam.privacy.camera_active:
            return "Camera is currently turned off for privacy, Dad. Say 'turn on camera' to count people."
        frame = cam.get_frame()
        detector = PersonDetector()
        res = detector.detect(frame)
        if res.person_count == 0:
            return "I don't see anyone in the room right now, Dad."
        elif res.person_count == 1:
            return "I detect 1 person in the room, Dad."
        return f"I detect {res.person_count} people in the room, Dad."

    def _cmd_camera_recognize(self, match) -> str:
        """Recognize enrolled faces in front of the camera."""
        from vision.camera.capture import CameraManager
        from vision.camera.recognition import FaceRecognizer
        from memory.structured_memory import StructuredMemory
        cam = CameraManager()
        if not cam.privacy.camera_active:
            return "Camera is currently turned off for privacy, Dad. Say 'turn on camera' to recognize faces."
        frame = cam.get_frame()
        rec = FaceRecognizer(structured_memory=StructuredMemory())
        _, message = rec.identify_person_in_frame(frame)
        return message

    def _cmd_camera_enroll(self, match) -> str:
        """Enroll a new person locally for opt-in face recognition."""
        from vision.camera.capture import CameraManager
        from vision.camera.recognition import FaceRecognizer
        from memory.structured_memory import StructuredMemory
        name = match.group(2).strip()
        cam = CameraManager()
        if not cam.privacy.camera_active:
            return "Camera is currently turned off for privacy, Dad. Please say 'turn on camera' first before enrolling."
        frame = cam.get_frame()
        rec = FaceRecognizer(structured_memory=StructuredMemory())
        success, message = rec.enroll_face_from_frame(name, frame)
        return message

    def _cmd_camera_pause(self, match) -> str:
        """Pause camera for privacy."""
        from vision.camera.capture import CameraManager
        cam = CameraManager()
        cam.pause()
        return "Camera has been turned off and hardware released for your privacy, Dad."

    def _cmd_camera_resume(self, match) -> str:
        """Resume camera capture."""
        from vision.camera.capture import CameraManager
        cam = CameraManager()
        success = cam.resume()
        return "Camera activated, Dad! I can see you now." if success else "Failed to start camera hardware, Dad."

    def _cmd_camera_status(self, match) -> str:
        """Show camera privacy and hardware status."""
        from vision.camera.capture import CameraManager
        cam = CameraManager()
        status = cam.get_privacy_status()
        active = "ACTIVE [ON]" if status["camera_active"] else "PAUSED [OFF]"
        det = "ENABLED [ON]" if status["person_detection_enabled"] else "DISABLED [OFF]"
        rec = "ENABLED [ON]" if status["face_recognition_enabled"] else "DISABLED [OFF]"
        return f"Camera Status:\n  Camera: {active}\n  Person Detection: {det}\n  Face Recognition: {rec}"

    # ══════════════════════════════════════════════════════════
    #  Web Commands (Direct)
    # ══════════════════════════════════════════════════════════

    def _cmd_open_website(self, match) -> str:
        """Open a website directly in browser."""
        from tools.web import open_website
        site = match.group(1).strip()
        return open_website(site)

    def _cmd_search_platform(self, match) -> str:
        """Search a specific platform (YouTube, Google, Reddit, GitHub, etc.)."""
        from tools.web import search_website
        platform = match.group(1).strip()
        query = match.group(2).strip()
        return search_website(platform, query)

    def _cmd_web_search(self, match) -> str:
        """Search the web."""
        from tools.web import web_search
        query = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else match.group(0).strip()
        return web_search(query)

    def _cmd_weather(self, match) -> str:
        """Get weather."""
        from tools.web import get_weather
        city = match.group(1).strip() or "auto"
        return get_weather(city)

    def _cmd_news(self, match) -> str:
        """Get news."""
        from tools.web import get_news
        topic = match.group(1).strip() or "technology"
        return get_news(topic)

    # ══════════════════════════════════════════════════════════
    #  Automation Commands
    # ══════════════════════════════════════════════════════════

    def _cmd_run_routine(self, match) -> str:
        """Run a named routine (morning/coding/goodnight)."""
        from tools.automation import AutomationEngine
        name = match.group(1).strip()
        engine = AutomationEngine(tool_registry=self._tools)
        return engine.run_routine(name)

    def _cmd_run_routine_named(self, match) -> str:
        """Run a routine by custom name."""
        from tools.automation import AutomationEngine
        name = match.group(1).strip()
        engine = AutomationEngine(tool_registry=self._tools)
        return engine.run_routine(name)

    def _cmd_list_routines(self, match) -> str:
        """List routines."""
        from tools.automation import AutomationEngine
        engine = AutomationEngine(tool_registry=self._tools)
        return engine.list_routines()

    # ══════════════════════════════════════════════════════════
    #  Docker Commands (Direct)
    # ══════════════════════════════════════════════════════════

    def _cmd_docker_list(self, match) -> str:
        """List Docker containers."""
        from tools.docker_control import docker_list_containers
        return docker_list_containers()

    def _cmd_docker_action(self, match) -> str:
        """Start/stop/restart a Docker container."""
        from tools.docker_control import docker_start, docker_stop, docker_restart
        action = match.group(2).strip().lower()
        container = match.group(3).strip()

        actions = {
            "start": docker_start,
            "stop": docker_stop,
            "restart": docker_restart,
        }
        func = actions.get(action)
        if func:
            return func(container)
        return f"Unknown action: {action}"

    # ══════════════════════════════════════════════════════════
    #  System Commands
    # ══════════════════════════════════════════════════════════

    def _cmd_memory_stats(self, match) -> str:
        """Show memory statistics."""
        stats = self._memory.stats()
        return (
            f"Memory Stats:\n"
            f"  Conversations: {stats['conversations']}\n"
            f"  Codebase chunks: {stats['codebase_chunks']}\n"
            f"  Facts: {stats['facts']}"
        )

    def _cmd_list_tools(self, match) -> str:
        """List all available tools."""
        if not self._tools:
            return "No tools registered."

        tools = self._tools.list_tools()
        categories = {}
        for t in tools:
            cat = t["category"]
            categories.setdefault(cat, []).append(t)

        lines = [f"Available Tools ({len(tools)} total):\n"]
        for cat, cat_tools in sorted(categories.items()):
            lines.append(f"  [{cat.upper()}]")
            for t in cat_tools:
                lines.append(f"    • {t['name']} — {t['description'][:60]}")
            lines.append("")

        return "\n".join(lines)

    def _cmd_clear_history(self, match) -> str:
        """Clear conversation history."""
        self._brain.clear_history()
        return "Conversation history cleared."

    def _cmd_help(self, match) -> str:
        """Show available commands."""
        return """Available Commands:

  CODEBASE:
    scan my project          — Index all configured projects
    scan <path>              — Index a specific project path
    what changed             — Show uncommitted git changes
    progress report          — Git progress report (last 7 days)
    list files               — Show project files
    commits                  — Show recent git commits

  MEMORY:
    remember that <fact>     — Save a persistent fact
    forget about <fact>      — Remove a fact
    memory stats             — Show memory statistics
    clear history            — Clear conversation context

  PC CONTROL:
    open <app>               — Open an application
    close <app>              — Close an application
    volume <0-100>           — Set system volume
    brightness <0-100>       — Set screen brightness
    screenshot               — Take a screenshot
    system info              — Show CPU/RAM/GPU/disk usage

  VISION:
    what's on my screen      — Analyze screen with vision AI

  WEB:
    search <query>           — Search the web
    weather [city]           — Get current weather
    news [topic]             — Get latest news

  AUTOMATION:
    morning routine          — Run morning briefing
    coding routine           — Start coding session
    goodnight routine        — End of day routine
    run routine <name>       — Run a custom routine
    list routines            — Show all routines

  DOCKER:
    docker list              — List containers
    start container <name>   — Start a container
    stop container <name>    — Stop a container

  SYSTEM:
    tools                    — List all available tools
    help                     — Show this help
    exit / quit              — Exit SON

  Anything else is sent to the AI for conversation."""

    def _cmd_start_seamless_voice(self, match) -> str:
        """Trigger seamless hands-free conversation mode."""
        return "__START_SEAMLESS_VOICE__"

    def _cmd_add_contact(self, match) -> str:
        """Add a contact: add contact <name> with number <number>"""
        name = match.group(1).strip()
        phone = match.group(2).strip()
        try:
            contact = self.whatsapp.contacts.add_contact(display_name=name, phone_number=phone)
            return f"Contact '{contact.display_name}' added successfully ({contact.masked_phone})."
        except Exception as e:
            return f"Failed to add contact: {e}"

    def _cmd_list_contacts(self, match) -> str:
        """List registered contacts."""
        contacts = self.whatsapp.contacts.list_all_contacts()
        if not contacts:
            return "No contacts found in your local address book. Say: 'add contact Rahul with number +91 98765 41234'."
        lines = [f"Contacts ({len(contacts)}):"]
        for c in contacts:
            alias_str = f" [aliases: {', '.join(c.aliases)}]" if c.aliases else ""
            lines.append(f"  - {c.display_name} ({c.masked_phone}){alias_str}")
        return "\n".join(lines)

    def _cmd_remove_contact(self, match) -> str:
        """Remove a contact: remove contact <name>"""
        target = match.group(1).strip()
        removed = self.whatsapp.contacts.remove_contact(target)
        if removed:
            return f"Contact '{target}' has been removed from your local address book."
        return f"Contact '{target}' was not found in your local address book."

    def _cmd_exit(self, match) -> str:
        """Signal exit."""
        return "__EXIT__"
