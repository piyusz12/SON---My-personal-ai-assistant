# brain.py — SON V3 LLM Reasoning Engine (Optimized)
"""
LLM reasoning engine using Ollama with:
- Resilient Ollama client (retry, health check, reconnection)
- Request tracing (performance profiling every stage)
- Dynamic context management (skip memory/codebase when not needed)
- Streaming with tool calling support
- Parallel tool execution for independent tools
- Model routing (coding, vision, reasoning)
"""
import time
import re
import logging
import json
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from core.config import Config
from core.ollama_client import ResilientOllamaClient, OllamaConnectionError
from core.profiler import RequestTracer, global_stats

logger = Config.get_logger(__name__)
tools_logger = Config.get_logger("son.tools")

# Pre-compiled regex for coding query detection
_CODING_QUERY_RE = re.compile(
    r'\b(?:code|function|class|bug|error|fix|implement|refactor|debug|'
    r'write a|create a|python|javascript|typescript|html|css|'
    r'api|endpoint|database|sql|query|algorithm|data structure|'
    r'import|module|compile|runtime|exception|traceback|'
    r'git|commit|merge|branch)\b',
    re.IGNORECASE
)

# Pre-compiled regex for vision query detection
_VISION_QUERY_RE = re.compile(
    r'\b(?:screen|screenshot|image|picture|photo|look at|see|visual|'
    r'show me|what do you see|analyze the|what\'?s on)\b',
    re.IGNORECASE
)

# Tool execution timeout (seconds)
TOOL_TIMEOUT = 10


class Brain:
    """
    LLM reasoning engine using Qwen3 via Ollama.
    Manages conversation context, streaming responses, RAG integration,
    tool calling (function invocation), and performance profiling.
    """

    def __init__(self, memory=None, codebase=None, tools=None):
        # Resilient Ollama client (replaces direct ollama.Client)
        self._client = ResilientOllamaClient(host=config.OLLAMA_HOST)
        self._model = config.LLM_MODEL
        self._coding_model = config.CODING_MODEL
        self._vision_model = config.VISION_MODEL
        self._temperature = config.LLM_TEMPERATURE
        self._stream = config.LLM_STREAM
        self._system_prompt = config.SYSTEM_PROMPT

        # Ollama performance options
        self._ollama_options = {
            "temperature": self._temperature,
            "num_ctx": getattr(config, 'LLM_NUM_CTX', 4096),
            "num_gpu": getattr(config, 'LLM_NUM_GPU', 99),
            "num_predict": getattr(config, 'LLM_NUM_PREDICT', 512),
            "num_batch": getattr(config, 'LLM_NUM_BATCH', 1024),
            "num_thread": getattr(config, 'LLM_NUM_THREAD', 8),
        }
        self._keep_alive = getattr(config, 'LLM_KEEP_ALIVE', '30m')

        # Dynamic conversation history (6 recent turns + summarized context)
        self._history: deque[dict] = deque(maxlen=12)  # 6 turns = 12 messages

        # Pluggable memory and codebase modules
        self._memory = memory
        self._codebase = codebase

        # Tool registry (for function calling)
        self._tools = tools

        # Current request tracer (set per-request)
        self._tracer: RequestTracer | None = None

        # Tool execution thread pool
        self._tool_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="son-tool")

    # ── Message Building (Dynamic Context) ────────────────────

    def _build_messages(self, user_message: str,
                        images: list[str] | None = None,
                        skip_memory: bool = False,
                        skip_codebase: bool = False) -> list[dict]:
        """
        Build the full messages array with dynamic context.

        Context is loaded only when needed:
        - skip_memory=True: Don't query ChromaDB (for commands, simple chat)
        - skip_codebase=True: Don't query code context (for non-code questions)
        """
        context_parts = []

        # 1. Retrieve relevant memories (only if needed)
        if not skip_memory and self._memory:
            if self._tracer:
                with self._tracer.trace("memory_retrieval"):
                    memories = self._memory.recall(user_message)
            else:
                memories = self._memory.recall(user_message)

            if memories:
                memory_text = "\n".join(f"- {m}" for m in memories)
                context_parts.append(
                    f"[RELEVANT MEMORIES]\n{memory_text}"
                )

        # 2. Retrieve relevant code context (only if needed)
        if not skip_codebase and self._codebase:
            if self._tracer:
                with self._tracer.trace("codebase_retrieval"):
                    code_ctx = self._codebase.query(user_message)
            else:
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
            # Store asynchronously to avoid blocking the response
            try:
                self._memory.store_conversation(user_message, assistant_reply)
            except Exception as e:
                logger.warning(f"Failed to store conversation: {e}")

    # ── Core Thinking ─────────────────────────────────────────

    def think(self, user_message: str,
              skip_memory: bool = False,
              skip_codebase: bool = False,
              tracer: RequestTracer | None = None) -> str:
        """
        Process a user message and return the AI response.

        Args:
            user_message: The user's input text.
            skip_memory: If True, don't query ChromaDB for relevant memories.
            skip_codebase: If True, don't query codebase context.
            tracer: Optional RequestTracer for performance profiling.

        Returns:
            AI response string.
        """
        self._tracer = tracer

        if self._tools and config.TOOL_CALLING_ENABLED:
            return self.think_with_tools(user_message, skip_memory=skip_memory,
                                          skip_codebase=skip_codebase)

        messages = self._build_messages(user_message,
                                         skip_memory=skip_memory,
                                         skip_codebase=skip_codebase)

        try:
            if self._tracer:
                with self._tracer.trace("llm_inference", model=self._model):
                    response = self._client.chat(
                        model=self._model,
                        messages=messages,
                        options=self._ollama_options,
                        keep_alive=self._keep_alive,
                    )
            else:
                response = self._client.chat(
                    model=self._model,
                    messages=messages,
                    options=self._ollama_options,
                    keep_alive=self._keep_alive,
                )
        except OllamaConnectionError as e:
            logger.error(f"Ollama connection failed: {e}")
            return ResilientOllamaClient.fallback_response(e)
        except Exception as e:
            logger.error(f"LLM inference error: {e}")
            return ResilientOllamaClient.fallback_response(e)

        assistant_reply = response["message"]["content"]

        # Log TTFT if available
        ttft = response.get("_ttft_ms")
        if ttft and self._tracer:
            self._tracer.set_metadata("ttft_ms", ttft)

        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def think_stream(self, user_message: str,
                     skip_memory: bool = False,
                     skip_codebase: bool = False,
                     tracer: RequestTracer | None = None):
        """
        Stream the AI response token-by-token.
        Now supports tool calling — falls back to non-streaming for tool calls.

        Yields partial text chunks as they arrive.
        """
        self._tracer = tracer

        # For tool calling, use non-streaming tool path and yield result
        if self._tools and config.TOOL_CALLING_ENABLED:
            result = self.think_with_tools(user_message,
                                            skip_memory=skip_memory,
                                            skip_codebase=skip_codebase)
            yield result
            return

        messages = self._build_messages(user_message,
                                         skip_memory=skip_memory,
                                         skip_codebase=skip_codebase)

        full_response = []
        ttft_recorded = False

        try:
            stream_start = time.perf_counter()

            stream = self._client.chat_stream(
                model=self._model,
                messages=messages,
                options=self._ollama_options,
                keep_alive=self._keep_alive,
            )

            for chunk in stream:
                token = chunk["message"]["content"]
                full_response.append(token)

                # Record TTFT from first token
                if not ttft_recorded:
                    ttft_ms = chunk.get("_ttft_ms")
                    if ttft_ms and self._tracer:
                        self._tracer.set_metadata("ttft_ms", ttft_ms)
                    ttft_recorded = True

                yield token

        except OllamaConnectionError as e:
            logger.error(f"Stream connection failed: {e}")
            yield ResilientOllamaClient.fallback_response(e)
            return
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield ResilientOllamaClient.fallback_response(e)
            return

        assistant_reply = "".join(full_response)
        self._save_turn(user_message, assistant_reply)

    # ── Tool Calling (with timeout & parallel execution) ──────

    def think_with_tools(self, user_message: str,
                         skip_memory: bool = False,
                         skip_codebase: bool = False) -> str:
        """
        Process a user message with tool calling support.

        Improvements over V2:
        - Tool timeout: tools can't hang SON indefinitely
        - Parallel execution: independent tools run concurrently
        - Structured logging: every tool call logged to tools.log
        - Error recovery: tool failures don't crash the conversation
        """
        messages = self._build_messages(user_message,
                                         skip_memory=skip_memory,
                                         skip_codebase=skip_codebase)
        tool_defs = self._tools.to_ollama_tools() if self._tools else []

        iterations = 0
        max_iter = config.TOOL_CALL_MAX_ITERATIONS

        while iterations < max_iter:
            iterations += 1

            try:
                if self._tracer:
                    stage_name = f"llm_tool_turn_{iterations}"
                    with self._tracer.trace(stage_name, model=self._model):
                        response = self._client.chat(
                            model=self._model,
                            messages=messages,
                            tools=tool_defs if tool_defs else None,
                            options=self._ollama_options,
                            keep_alive=self._keep_alive,
                        )
                else:
                    response = self._client.chat(
                        model=self._model,
                        messages=messages,
                        tools=tool_defs if tool_defs else None,
                        options=self._ollama_options,
                        keep_alive=self._keep_alive,
                    )
            except OllamaConnectionError as e:
                logger.error(f"Ollama connection failed during tool call: {e}")
                return ResilientOllamaClient.fallback_response(e)
            except Exception as e:
                logger.error(f"Tool calling LLM error: {e}")
                return ResilientOllamaClient.fallback_response(e)

            msg = response["message"]

            # Check if the LLM wants to call tools
            if msg.get("tool_calls"):
                messages.append(msg)
                tool_calls = msg["tool_calls"]

                # Execute tools (parallel when multiple independent tools)
                if len(tool_calls) > 1:
                    results = self._execute_tools_parallel(tool_calls)
                else:
                    results = self._execute_tools_sequential(tool_calls)

                # Add all tool results to messages
                for result_str in results:
                    messages.append({
                        "role": "tool",
                        "content": result_str,
                    })
            else:
                # No tool calls — final text response
                assistant_reply = msg.get("content", "")
                self._save_turn(user_message, assistant_reply)
                return assistant_reply

        # Safety: max iterations reached
        assistant_reply = "I completed the requested actions but reached the maximum number of tool calls."
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def _execute_tools_sequential(self, tool_calls: list[dict]) -> list[str]:
        """Execute tool calls one at a time with timeout."""
        results = []
        for tool_call in tool_calls:
            result = self._execute_single_tool(tool_call)
            results.append(result)
        return results

    def _execute_tools_parallel(self, tool_calls: list[dict]) -> list[str]:
        """Execute multiple tool calls in parallel with timeout."""
        futures = {}
        for i, tool_call in enumerate(tool_calls):
            future = self._tool_pool.submit(self._execute_single_tool, tool_call)
            futures[future] = i

        results = [""] * len(tool_calls)
        for future in as_completed(futures, timeout=TOOL_TIMEOUT + 2):
            idx = futures[future]
            try:
                results[idx] = future.result(timeout=1)
            except Exception as e:
                func_name = tool_calls[idx]["function"]["name"]
                results[idx] = f"Error: Tool '{func_name}' failed: {e}"
                logger.error(f"Parallel tool '{func_name}' failed: {e}")

        return results

    def _execute_single_tool(self, tool_call: dict) -> str:
        """Execute a single tool call with timeout and logging."""
        func_name = tool_call["function"]["name"]
        func_args = tool_call["function"].get("arguments", {})

        # Log tool call
        tools_logger.info(json.dumps({
            "action": "tool_call",
            "tool": func_name,
            "args": func_args,
            "request_id": self._tracer.request_id if self._tracer else None,
        }, default=str))

        # Check confirmation requirement
        if self._tools.needs_confirmation(func_name):
            # For now, auto-confirm (GUI can add interactive confirm later)
            tools_logger.info(f"Tool '{func_name}' requires confirmation — auto-confirmed")

        # Execute with timeout
        start = time.perf_counter()
        try:
            future = self._tool_pool.submit(self._tools.call, func_name, func_args)
            result = future.result(timeout=TOOL_TIMEOUT)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Log result
            tools_logger.info(json.dumps({
                "action": "tool_result",
                "tool": func_name,
                "duration_ms": round(elapsed_ms, 2),
                "result_length": len(str(result)),
                "success": True,
            }, default=str))

            # Record in tracer
            if self._tracer:
                self._tracer.record_stage(f"tool:{func_name}", elapsed_ms)

            return result

        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start) * 1000
            error_msg = f"Tool '{func_name}' timed out after {TOOL_TIMEOUT}s"
            logger.error(error_msg)
            tools_logger.info(json.dumps({
                "action": "tool_timeout",
                "tool": func_name,
                "timeout_s": TOOL_TIMEOUT,
            }))
            return error_msg

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            error_msg = f"Tool '{func_name}' failed: {e}"
            logger.error(error_msg)
            tools_logger.info(json.dumps({
                "action": "tool_error",
                "tool": func_name,
                "error": str(e),
                "duration_ms": round(elapsed_ms, 2),
            }, default=str))
            return error_msg

    # ── Specialized Models ────────────────────────────────────

    def think_code(self, user_message: str,
                   tracer: RequestTracer | None = None) -> str:
        """
        Route coding-related queries to the specialized coding model.
        Uses qwen2.5-coder for code generation, explanation, and debugging.
        """
        self._tracer = tracer
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

        try:
            if self._tracer:
                with self._tracer.trace("llm_inference", model=self._coding_model):
                    response = self._client.chat(
                        model=self._coding_model,
                        messages=messages,
                        options={**self._ollama_options, "temperature": 0.3, "num_predict": 1024},
                        keep_alive=self._keep_alive,
                    )
            else:
                response = self._client.chat(
                    model=self._coding_model,
                    messages=messages,
                    options={**self._ollama_options, "temperature": 0.3, "num_predict": 1024},
                    keep_alive=self._keep_alive,
                )
        except OllamaConnectionError as e:
            logger.error(f"Coding model connection failed: {e}")
            return ResilientOllamaClient.fallback_response(e)

        assistant_reply = response["message"]["content"]
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def think_vision(self, user_message: str, images: list[str],
                     tracer: RequestTracer | None = None) -> str:
        """
        Analyze images using the vision model (Llama 3.2 Vision).

        Args:
            user_message: The question about the image(s).
            images: List of base64-encoded image strings or file paths.
        """
        self._tracer = tracer
        messages = self._build_messages(user_message, images=images)

        try:
            if self._tracer:
                with self._tracer.trace("llm_inference", model=self._vision_model):
                    response = self._client.chat(
                        model=self._vision_model,
                        messages=messages,
                        options=self._ollama_options,
                        keep_alive=self._keep_alive,
                    )
            else:
                response = self._client.chat(
                    model=self._vision_model,
                    messages=messages,
                    options=self._ollama_options,
                    keep_alive=self._keep_alive,
                )
        except OllamaConnectionError as e:
            logger.error(f"Vision model connection failed: {e}")
            return ResilientOllamaClient.fallback_response(e)

        assistant_reply = response["message"]["content"]
        self._save_turn(user_message, assistant_reply)
        return assistant_reply

    def is_coding_query(self, text: str) -> bool:
        """Heuristic to detect if a query is coding-related.
        Uses pre-compiled regex for single-pass matching (faster than set iteration)."""
        return _CODING_QUERY_RE.search(text) is not None

    def is_vision_query(self, text: str) -> bool:
        """Heuristic to detect if a query requires vision."""
        return _VISION_QUERY_RE.search(text) is not None

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

    # ── Ollama Client Access ──────────────────────────────────

    @property
    def ollama_client(self) -> ResilientOllamaClient:
        """Expose the resilient Ollama client for health checks."""
        return self._client
