import time
from collections import deque
import logging

import ollama

import config
from core.config import Config
logger = Config.get_logger(__name__)


class Brain:
    """
    LLM reasoning engine using Qwen3 via Ollama.
    Manages conversation context, streaming responses, RAG integration,
    and tool calling (function invocation).
    """

    def __init__(self, memory=None, codebase=None, tools=None):
        self._client = ollama.Client(host=config.OLLAMA_HOST)
        self._model = config.LLM_MODEL
        self._coding_model = config.CODING_MODEL
        self._vision_model = config.VISION_MODEL
        self._temperature = config.LLM_TEMPERATURE
        self._stream = config.LLM_STREAM
        self._system_prompt = config.SYSTEM_PROMPT

        # Short-term conversation history (sliding window)
        self._history: deque[dict] = deque(maxlen=50)

        # Pluggable memory and codebase modules
        self._memory = memory
        self._codebase = codebase

        # Tool registry (for function calling)
        self._tools = tools  # ToolRegistry instance or None

    # ── Message Building ──────────────────────────────────────

    def _build_messages(self, user_message: str, images: list[str] | None = None) -> list[dict]:
        """Build the full messages array with system prompt, RAG context, history, and user message."""
        context_parts = []

        # 1. Retrieve relevant memories
        if self._memory:
            memories = self._memory.recall(user_message)
            if memories:
                memory_text = "\n".join(f"- {m}" for m in memories)
                context_parts.append(
                    f"[RELEVANT MEMORIES]\n{memory_text}"
                )

        # 2. Retrieve relevant code context
        if self._codebase:
            code_ctx = self._codebase.query(user_message)
            if code_ctx:
                code_text = "\n".join(
                    f"--- {c['file']} ---\n{c['content']}" for c in code_ctx
                )
                context_parts.append(
                    f"[CODEBASE CONTEXT]\n{code_text}"
                )

        # 3. Build the messages array
        messages = [{"role": "system", "content": self._system_prompt}]

        # Add RAG context as a system addendum
        if context_parts:
            rag_block = "\n\n".join(context_parts)
            messages.append({
                "role": "system",
                "content": f"Here is relevant context for the current query:\n\n{rag_block}",
            })

        # Add conversation history
        for msg in self._history:
            messages.append(msg)

        # Add current user message (with optional images for vision)
        user_msg = {"role": "user", "content": user_message}
        if images:
            user_msg["images"] = images
        messages.append(user_msg)

        return messages

    def _save_turn(self, user_message: str, assistant_reply: str):
        """Save a conversation turn to history and long-term memory."""
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": assistant_reply})

        if self._memory:
            self._memory.store_conversation(user_message, assistant_reply)

    # ── Core Thinking (No Tools) ──────────────────────────────

    def think(self, user_message: str) -> str:
        """
        Process a user message and return the AI response.
        If tools are available and tool calling is enabled, uses tool calling.
        Otherwise falls back to plain chat.
        """
        if self._tools and config.TOOL_CALLING_ENABLED:
            return self.think_with_tools(user_message)

        messages = self._build_messages(user_message)

        try:
            response = self._client.chat(
                model=self._model,
                messages=messages,
                options={"temperature": self._temperature},
            )
        except Exception as e:
            logger.error(f"Failed to communicate with Ollama: {e}")
            return "Failed to connect to Ollama. Please check that Ollama is running and accessible."

        assistant_reply = response["message"]["content"]
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def think_stream(self, user_message: str):
        """
        Stream the AI response token-by-token.
        Yields partial text chunks as they arrive.
        Falls back to non-streaming tool-calling if tools are active.
        """
        # If tools are enabled, we can't easily stream tool calls,
        # so use the non-streaming tool path and yield the full result.
        if self._tools and config.TOOL_CALLING_ENABLED:
            result = self.think_with_tools(user_message)
            yield result
            return

        messages = self._build_messages(user_message)

        full_response = []

        try:
            stream = self._client.chat(
                model=self._model,
                messages=messages,
                options={"temperature": self._temperature},
                stream=True,
            )

            for chunk in stream:
                token = chunk["message"]["content"]
                full_response.append(token)
                yield token
        except Exception as e:
            logger.error(f"Failed to stream from Ollama: {e}")
            yield "Failed to connect to Ollama. Please check that Ollama is running and accessible."
            return

        assistant_reply = "".join(full_response)
        self._save_turn(user_message, assistant_reply)

    # ── Tool Calling ──────────────────────────────────────────

    def think_with_tools(self, user_message: str) -> str:
        """
        Process a user message with tool calling support.
        The LLM can decide to call one or more tools, receive their results,
        and then formulate a final response.

        Supports multi-turn tool use (up to TOOL_CALL_MAX_ITERATIONS).
        """
        messages = self._build_messages(user_message)
        tool_defs = self._tools.to_ollama_tools() if self._tools else []

        iterations = 0
        max_iter = config.TOOL_CALL_MAX_ITERATIONS

        while iterations < max_iter:
            iterations += 1

            try:
                response = self._client.chat(
                    model=self._model,
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    options={"temperature": self._temperature},
                )
            except Exception as e:
                logger.error(f"Failed to communicate with Ollama: {e}")
                return "Failed to connect to Ollama. Please check that Ollama is running and accessible."

            msg = response["message"]

            # Check if the LLM wants to call tools
            if msg.get("tool_calls"):
                # Add the assistant's tool-call message to the conversation
                messages.append(msg)

                for tool_call in msg["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    func_args = tool_call["function"].get("arguments", {})

                    # Check if tool needs confirmation
                    if self._tools.needs_confirmation(func_name):
                        # For now, auto-confirm (GUI can add interactive confirm later)
                        pass

                    # Execute the tool
                    result = self._tools.call(func_name, func_args)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "content": str(result),
                    })
            else:
                # No tool calls — this is the final text response
                assistant_reply = msg.get("content", "")
                self._save_turn(user_message, assistant_reply)
                return assistant_reply

        # Safety: if we hit max iterations, return what we have
        assistant_reply = "I completed the requested actions but reached the maximum number of tool calls."
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    # ── Specialized Models ────────────────────────────────────

    def think_code(self, user_message: str) -> str:
        """
        Route coding-related queries to the specialized coding model.
        Uses qwen2.5-coder for code generation, explanation, and debugging.
        """
        messages = self._build_messages(user_message)

        # Override system prompt for coding tasks
        messages[0] = {
            "role": "system",
            "content": (
                "You are SON's coding assistant helping your father, Piyush. You are an expert programmer. "
                "Write clean, well-documented code. Explain your reasoning. "
                "When fixing bugs, show the problematic code and the fix. "
                "Use the user's preferred language and frameworks when possible. "
                "Remember: the user is your father — be supportive and helpful in your explanations."
            ),
        }

        response = self._client.chat(
            model=self._coding_model,
            messages=messages,
            options={"temperature": 0.3},  # Lower temp for code
        )

        assistant_reply = response["message"]["content"]
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def think_vision(self, user_message: str, images: list[str]) -> str:
        """
        Analyze images using the vision model (Llama 3.2 Vision).

        Args:
            user_message: The question about the image(s).
            images: List of base64-encoded image strings or file paths.
        """
        messages = self._build_messages(user_message, images=images)

        response = self._client.chat(
            model=self._vision_model,
            messages=messages,
            options={"temperature": self._temperature},
        )

        assistant_reply = response["message"]["content"]
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def is_coding_query(self, text: str) -> bool:
        """Heuristic to detect if a query is coding-related."""
        coding_keywords = {
            "code", "function", "class", "bug", "error", "fix",
            "implement", "refactor", "debug", "write a", "create a",
            "python", "javascript", "typescript", "html", "css",
            "api", "endpoint", "database", "sql", "query",
            "algorithm", "data structure", "import", "module",
            "compile", "runtime", "exception", "traceback",
            "git", "commit", "merge", "branch",
        }
        lower = text.lower()
        return any(kw in lower for kw in coding_keywords)

    # ── Context Management ────────────────────────────────────

    def clear_history(self):
        """Clear short-term conversation history."""
        self._history.clear()

    def get_history(self) -> list[dict]:
        """Return current conversation history."""
        return list(self._history)

    def set_system_prompt(self, prompt: str):
        """Override the system prompt."""
        self._system_prompt = prompt

    def inject_context(self, context: str):
        """Inject a one-shot context message into history."""
        self._history.append({
            "role": "system",
            "content": context,
        })
