# core/intent_router.py — Intelligent Intent Router for SON V3
"""
Classifies user input into intent categories BEFORE hitting the LLM.
This is the single biggest performance optimization — "Open Chrome"
should never touch an 8B parameter model.

Architecture:
                    User Input
                        │
                        ▼
                  IntentRouter
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
      COMMAND          CHAT          COMPLEX
         │              │              │
         ▼              ▼              ▼
     Execute        Small LLM      Full LLM
     directly       (lite ctx)     (full RAG)

Intent Types:
    COMMAND  — Direct execution, no LLM needed (open app, volume, etc.)
    CHAT     — Simple conversation, minimal context needed
    COMPLEX  — Needs full RAG, tools, code context, reasoning
"""
import re
from enum import Enum
from dataclasses import dataclass

from core.config import Config

logger = Config.get_logger(__name__)


class IntentType(Enum):
    """Classification of user input intent."""
    COMMAND = "command"      # Direct execution, no LLM
    CHAT = "chat"            # Simple conversation, lite context
    COMPLEX = "complex"      # Full LLM with RAG + tools


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: IntentType
    confidence: float          # 0.0 - 1.0
    needs_memory: bool         # Should we query ChromaDB?
    needs_codebase: bool       # Should we query code context?
    needs_tools: bool          # Should we enable tool calling?
    matched_pattern: str | None = None  # Which pattern matched (for debugging)
    subcategory: str | None = None      # e.g., "app_control", "system_query", "calculator"


class IntentRouter:
    """
    Fast intent classification using keyword matching and heuristics.

    Design principles:
    - Speed over accuracy: a fast wrong classification is better than a slow LLM call
    - Conservative fallthrough: if unsure, default to CHAT (not COMPLEX)
    - No LLM calls in the router itself
    """

    def __init__(self):
        # ── COMMAND patterns (direct execution, no LLM) ──────────
        # These patterns match inputs that can be handled immediately
        self._command_patterns: list[tuple[re.Pattern, str]] = [
            # Website opening & platform search
            (re.compile(r"^(?:open|go\s+to|visit|launch)\s+(?:website\s+|site\s+)?(https?://\S+|www\.\S+|\w+\.(?:com|org|io|net|edu|ai|gov|dev|app|co|in)\S*|youtube|github|reddit|chatgpt|google|gmail|twitter|x|amazon|netflix|spotify|wikipedia|stackoverflow|linkedin|huggingface|twitch|discord|whatsapp)$", re.I), "open_website"),
            (re.compile(r"^(?:search|look\s+up|find)\s+(?:google|youtube|github|reddit|wikipedia|amazon|stackoverflow|twitter|x|duckduckgo)\s+(?:for\s+)?.+$", re.I), "search_platform"),

            # App control
            (re.compile(r"^(?:open|launch|start|run)\s+\w+", re.I), "app_open"),
            (re.compile(r"^(?:close|kill|stop|quit|exit)\s+\w+", re.I), "app_close"),

            # Volume / brightness
            (re.compile(r"^(?:set\s+)?(?:volume|brightness)\s+(?:to\s+)?\d+", re.I), "system_control"),
            (re.compile(r"^(?:mute|unmute)(?:\s+.*)?$", re.I), "system_control"),
            (re.compile(r"^(?:volume|brightness)\s+(?:up|down)", re.I), "system_control"),

            # Screenshot
            (re.compile(r"^(?:take\s+(?:a\s+)?)?screenshot$", re.I), "screenshot"),
            (re.compile(r"^(?:capture|snap)\s+(?:my\s+)?screen", re.I), "screenshot"),

            # System info
            (re.compile(r"^(?:system\s+)?(?:info|status|stats)$", re.I), "system_info"),
            (re.compile(r"^(?:what'?s?\s+(?:my\s+)?)?(?:cpu|gpu|ram|memory|disk)\s*(?:usage|status)?$", re.I), "system_info"),

            # Vision (Screen)
            (re.compile(r"^(?:what'?s?\s+on\s+my\s+screen|look\s+at\s+(?:my\s+)?screen|analyze\s+(?:my\s+)?screen)", re.I), "vision_screen"),

            # Vision (Camera & Person Detection / Face Recognition)
            (re.compile(r"^(?:can\s+you\s+see\s+me|can\s+you\s+see|do\s+you\s+see\s+me|look\s+at\s+me|see\s+me)\??$", re.I), "camera_see_me"),
            (re.compile(r"^(?:is\s+(?:anyone|anybody|someone)\s+in\s+the\s+room|is\s+someone\s+here|anyone\s+there|is\s+anybody\s+there)\??$", re.I), "camera_presence"),
            (re.compile(r"^(?:how\s+many\s+people\s+(?:are\s+there|in\s+the\s+room|do\s+you\s+see)|count\s+people|what\s+do\s+you\s+see)\??$", re.I), "camera_count"),
            (re.compile(r"^(?:do\s+you\s+recognize\s+(?:this\s+person|me)|who\s+am\s+i|who\s+is\s+(?:this|here|in\s+front\s+of\s+(?:you|the\s+camera))|who\s+do\s+you\s+see)\??$", re.I), "camera_recognize"),
            (re.compile(r"^(?:enroll|add|register)\s+person\s+(.+)$", re.I), "camera_enroll"),
            (re.compile(r"^(?:pause|disable|turn\s+off|stop)\s+camera$", re.I), "camera_pause"),
            (re.compile(r"^(?:resume|enable|turn\s+on|start)\s+camera$", re.I), "camera_resume"),
            (re.compile(r"^camera\s+(?:status|info)$", re.I), "camera_status"),

            # Docker
            (re.compile(r"^(?:docker|containers?)\s+(?:list|ps|status)$", re.I), "docker"),
            (re.compile(r"^(?:docker\s+)?(?:start|stop|restart)\s+container\s+", re.I), "docker"),

            # Web / website opening / platform search / weather / news
            (re.compile(r"^(?:open|go\s+to|visit|launch)\s+(?:website\s+|site\s+)?(https?://\S+|www\.\S+|\w+\.(?:com|org|io|net|edu|ai|gov|dev|app|co|in)\S*|youtube|github|reddit|chatgpt|google|gmail|twitter|x|amazon|netflix|spotify|wikipedia|stackoverflow|linkedin|huggingface|twitch|discord|whatsapp)$", re.I), "open_website"),
            (re.compile(r"^(?:search|look\s+up|find)\s+(?:google|youtube|github|reddit|wikipedia|amazon|stackoverflow|twitter|x|duckduckgo)\s+(?:for\s+)?.+$", re.I), "search_platform"),
            (re.compile(r"^(?:google|search\s+(?:the\s+web\s+for|the\s+internet\s+for|for)?)\s*.+$", re.I), "web_search"),
            (re.compile(r"^weather\s*", re.I), "weather"),
            (re.compile(r"^news\s*", re.I), "news"),

            # Memory management
            (re.compile(r"^remember\s+(?:that\s+)?.+$", re.I), "memory_store"),
            (re.compile(r"^forget\s+(?:about\s+)?.+$", re.I), "memory_forget"),
            (re.compile(r"^memory\s+stats?$", re.I), "memory_stats"),
            (re.compile(r"^clear\s+history$", re.I), "memory_clear"),

            # Codebase
            (re.compile(r"^(?:scan|index)\s+", re.I), "codebase_scan"),
            (re.compile(r"^(?:what\s+changed|diff|changes)", re.I), "codebase_diff"),
            (re.compile(r"^(?:progress\s+report|git\s+log)", re.I), "codebase_report"),
            (re.compile(r"^(?:recent\s+)?commits", re.I), "codebase_commits"),
            (re.compile(r"^(?:list\s+)?(?:project\s+)?files", re.I), "codebase_files"),

            # Automation routines
            (re.compile(r"^(?:morning|coding|goodnight)\s+routine$", re.I), "routine"),
            (re.compile(r"^(?:run\s+routine|list\s+routines?)\s*", re.I), "routine"),

            # System commands
            (re.compile(r"^(?:list\s+)?tools$", re.I), "list_tools"),
            (re.compile(r"^help$", re.I), "help"),
            (re.compile(r"^(?:exit|quit|bye|goodbye)$", re.I), "exit"),

            # Timer / calculator (simple utility)
            (re.compile(r"^(?:what'?s?\s+)?(?:\d+\s*[\+\-\*\/\%\^]\s*\d+)", re.I), "calculator"),
            (re.compile(r"^(?:calculate|compute|math)\s+", re.I), "calculator"),
            (re.compile(r"^(?:set\s+(?:a\s+)?)?(?:timer|alarm|reminder)\s+", re.I), "timer"),

            # Date/time queries
            (re.compile(r"^(?:what\s+(?:time|day|date)\s+is\s+it|current\s+(?:time|date))", re.I), "datetime"),

            # Shutdown / restart / sleep
            (re.compile(r"^(?:shutdown|restart|reboot|sleep|hibernate|lock)\s*(?:the\s+)?(?:pc|computer|system)?$", re.I), "system_power"),
        ]

        # ── COMPLEX patterns (needs full LLM + RAG + tools) ──────
        self._complex_indicators: list[re.Pattern] = [
            # Coding keywords
            re.compile(r"\b(?:code|function|class|bug|error|fix|implement|refactor|debug|"
                       r"write\s+(?:a|me|some)|create\s+(?:a|me)|compile|runtime|exception|"
                       r"traceback|import|module|library)\b", re.I),

            # Multi-step / deep research
            re.compile(r"\b(?:explain\s+in\s+detail|deep\s+dive|analyze|research|compare\s+and\s+contrast|"
                       r"step\s+by\s+step|pros?\s+(?:and|&)\s+cons?|how\s+does\s+.+\s+work\s+internally)\b", re.I),

            # Project-specific questions
            re.compile(r"\b(?:my\s+project|codebase|repository|git\s+history|"
                       r"architecture|design\s+pattern|refactor)\b", re.I),

            # Long inputs (>50 chars usually need reasoning)
            re.compile(r"^.{100,}$", re.S),

            # Questions with complex structure
            re.compile(r"\b(?:step\s+by\s+step|plan|strategy|approach|best\s+way|"
                       r"pros?\s+(?:and|&)\s+cons?|trade.?offs?)\b", re.I),

            # File operations that need reasoning
            re.compile(r"\b(?:find\s+(?:all|every)|search\s+(?:through|in|across)\s+(?:my\s+)?(?:code|files|project))\b", re.I),
        ]

        # ── Keywords that indicate simple chat ──────────────────
        self._chat_indicators: list[re.Pattern] = [
            re.compile(r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening|night)|thanks|thank\s+you|"
                       r"ok|okay|sure|yes|no|bye|see\s+you|sup|what'?s?\s+up)", re.I),
            re.compile(r"^(?:how\s+are\s+you|how'?s?\s+it\s+going|how\s+do\s+you\s+feel)", re.I),
            re.compile(r"^(?:tell\s+me\s+a\s+joke|make\s+me\s+laugh|sing)", re.I),
            re.compile(r"^(?:who\s+are\s+you|what\s+are\s+you|what'?s?\s+your\s+name)", re.I),
        ]

    def classify(self, text: str) -> IntentResult:
        """
        Classify user input into an intent category.

        The classification hierarchy is:
        1. Check COMMAND patterns (fastest path)
        2. Check CHAT indicators (simple greetings/small talk)
        3. Check COMPLEX indicators (needs reasoning)
        4. Default to CHAT (conservative — don't over-trigger expensive paths)

        Args:
            text: Raw user input text.

        Returns:
            IntentResult with classification and routing hints.
        """
        cleaned = text.strip()
        if not cleaned:
            return IntentResult(
                intent=IntentType.CHAT,
                confidence=1.0,
                needs_memory=False,
                needs_codebase=False,
                needs_tools=False,
            )

        # 1. Check COMMAND patterns first (highest priority, fastest path)
        for pattern, subcategory in self._command_patterns:
            if pattern.search(cleaned):
                return IntentResult(
                    intent=IntentType.COMMAND,
                    confidence=0.95,
                    needs_memory=False,
                    needs_codebase=subcategory in ("codebase_scan", "codebase_diff", "codebase_report", "codebase_commits", "codebase_files"),
                    needs_tools=False,
                    matched_pattern=pattern.pattern,
                    subcategory=subcategory,
                )

        # 2. Check simple CHAT indicators (greetings, small talk)
        for pattern in self._chat_indicators:
            if pattern.search(cleaned):
                return IntentResult(
                    intent=IntentType.CHAT,
                    confidence=0.9,
                    needs_memory=False,  # No need to search ChromaDB for "hi"
                    needs_codebase=False,
                    needs_tools=False,
                    matched_pattern=pattern.pattern,
                    subcategory="small_talk",
                )

        # 3. Check COMPLEX indicators (needs full RAG)
        complex_score = 0
        matched_complex = None
        for pattern in self._complex_indicators:
            if pattern.search(cleaned):
                complex_score += 1
                if matched_complex is None:
                    matched_complex = pattern.pattern

        if complex_score >= 2:
            # Multiple complex indicators → definitely complex
            return IntentResult(
                intent=IntentType.COMPLEX,
                confidence=0.9,
                needs_memory=True,
                needs_codebase=True,
                needs_tools=True,
                matched_pattern=matched_complex,
                subcategory="multi_indicator",
            )
        elif complex_score == 1:
            # Single complex indicator → probably complex
            return IntentResult(
                intent=IntentType.COMPLEX,
                confidence=0.7,
                needs_memory=True,
                needs_codebase=self._looks_like_code_question(cleaned),
                needs_tools=True,
                matched_pattern=matched_complex,
                subcategory="single_indicator",
            )

        # 4. Default: CHAT with recent memory only
        # If the input is short and conversational, treat as chat
        # but include recent memory in case it's a follow-up question
        is_question = cleaned.endswith("?") or cleaned.lower().startswith(
            ("what", "where", "when", "who", "how", "why", "can", "could", "would", "should", "is", "are", "do", "does")
        )

        return IntentResult(
            intent=IntentType.CHAT,
            confidence=0.6,
            needs_memory=is_question,  # Questions might need memory context
            needs_codebase=False,
            needs_tools=is_question,   # Questions might need tools
            matched_pattern=None,
            subcategory="general_chat",
        )

    def _looks_like_code_question(self, text: str) -> bool:
        """Check if text looks like it's about code/programming."""
        code_words = {
            "code", "function", "class", "method", "variable", "bug", "error",
            "python", "javascript", "typescript", "html", "css", "api",
            "database", "sql", "git", "docker", "file", "module", "package",
            "import", "library", "framework", "algorithm", "data structure",
        }
        words = set(text.lower().split())
        return bool(words & code_words)

    def should_skip_memory(self, intent: IntentResult) -> bool:
        """Helper: should we skip ChromaDB memory retrieval?"""
        return not intent.needs_memory

    def should_skip_codebase(self, intent: IntentResult) -> bool:
        """Helper: should we skip codebase context retrieval?"""
        return not intent.needs_codebase

    def should_use_tools(self, intent: IntentResult) -> bool:
        """Helper: should we enable tool calling for the LLM?"""
        return intent.needs_tools
