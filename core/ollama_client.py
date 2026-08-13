# core/ollama_client.py — Resilient Ollama Client for SON V3
"""
Wraps ollama.Client with retry logic, health checking, and graceful degradation.

Instead of crashing when Ollama is unavailable:
    1. Health check on init
    2. Exponential backoff retry (3 attempts)
    3. Automatic reconnection
    4. Fallback responses
    5. TTFT tracking built into every call

Usage:
    from core.ollama_client import ResilientOllamaClient

    client = ResilientOllamaClient()
    if client.is_healthy():
        response = client.chat(model="qwen3:8b", messages=[...])
"""
import time
import threading
import logging
import json
from typing import Generator, Any

import ollama

from core.config import Config

logger = Config.get_logger(__name__)


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable after all retries."""
    pass


class ResilientOllamaClient:
    """
    Resilient wrapper around ollama.Client.

    Features:
    - Health checking with cached status
    - Exponential backoff retry (3 attempts: 0.5s, 1s, 2s)
    - Connection state tracking
    - TTFT (time to first token) measurement
    - Model availability caching
    - Graceful fallback responses
    """

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [0.5, 1.0, 2.0]  # seconds

    # Cache TTL
    HEALTH_CACHE_TTL = 30.0        # seconds — health check cache
    MODEL_CACHE_TTL = 300.0        # seconds — model availability cache (5 min)

    def __init__(self, host: str | None = None):
        self._host = host or Config.OLLAMA_HOST
        self._client = ollama.Client(host=self._host)
        self._lock = threading.Lock()

        # Connection state
        self._connected = False
        self._last_error: str | None = None
        self._consecutive_failures = 0

        # Health cache
        self._health_status: bool | None = None
        self._health_checked_at: float = 0.0

        # Model availability cache
        self._available_models: list[str] = []
        self._models_checked_at: float = 0.0

        # Performance tracking
        self._total_requests = 0
        self._failed_requests = 0
        self._total_retries = 0

        # Initial health check (non-blocking)
        self._check_health_async()

    # ── Health Checking ──────────────────────────────────────────

    def _check_health_async(self):
        """Run initial health check in background."""
        thread = threading.Thread(target=self._check_health, daemon=True, name="ollama-health")
        thread.start()

    def _check_health(self) -> bool:
        """
        Check if Ollama is reachable and responding.
        Result is cached for HEALTH_CACHE_TTL seconds.
        """
        now = time.time()

        # Return cached result if fresh
        if self._health_status is not None and (now - self._health_checked_at) < self.HEALTH_CACHE_TTL:
            return self._health_status

        try:
            import urllib.request
            req = urllib.request.Request(f"{self._host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    with self._lock:
                        self._connected = True
                        self._health_status = True
                        self._health_checked_at = now
                        self._consecutive_failures = 0
                        # Cache available models
                        self._available_models = [
                            m.get("name", "") for m in data.get("models", [])
                        ]
                        self._models_checked_at = now
                    return True
        except Exception as e:
            with self._lock:
                self._connected = False
                self._health_status = False
                self._health_checked_at = now
                self._last_error = str(e)
            logger.warning(f"Ollama health check failed: {e}")

        return False

    def is_healthy(self) -> bool:
        """Check if Ollama is currently healthy (uses cache)."""
        return self._check_health()

    def is_model_available(self, model: str) -> bool:
        """Check if a specific model is available (uses cache)."""
        now = time.time()
        if (now - self._models_checked_at) > self.MODEL_CACHE_TTL:
            self._check_health()  # Refreshes model list
        return model in self._available_models

    # ── Retry Logic ──────────────────────────────────────────────

    def _retry_operation(self, operation_name: str, fn, *args, **kwargs) -> Any:
        """
        Execute a function with exponential backoff retry.

        Args:
            operation_name: Human-readable name for logging.
            fn: Function to call.
            *args, **kwargs: Arguments to pass.

        Returns:
            Result of fn() on success.

        Raises:
            OllamaConnectionError: After all retries exhausted.
        """
        last_exception = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = fn(*args, **kwargs)
                # Success — reset failure counter
                with self._lock:
                    self._connected = True
                    self._consecutive_failures = 0
                    self._total_requests += 1
                return result

            except Exception as e:
                last_exception = e
                with self._lock:
                    self._consecutive_failures += 1
                    self._total_retries += 1

                delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]

                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        f"Ollama {operation_name} failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Ollama {operation_name} failed after {self.MAX_RETRIES} attempts: {e}"
                    )

        # All retries exhausted
        with self._lock:
            self._connected = False
            self._failed_requests += 1
            self._last_error = str(last_exception)
            # Invalidate health cache
            self._health_status = False
            self._health_checked_at = time.time()

        raise OllamaConnectionError(
            f"Ollama {operation_name} failed after {self.MAX_RETRIES} retries: {last_exception}"
        )

    # ── Chat (non-streaming) ─────────────────────────────────────

    def chat(self, model: str, messages: list[dict],
             tools: list[dict] | None = None,
             options: dict | None = None,
             keep_alive: str = "30m") -> dict:
        """
        Send a chat request with retry logic.

        Returns:
            Ollama response dict with added '_ttft_ms' field.
        """
        def _do_chat():
            start = time.perf_counter()
            response = self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options=options,
                keep_alive=keep_alive,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            # Attach timing metadata
            response["_ttft_ms"] = round(elapsed_ms, 2)
            response["_model"] = model
            return response

        return self._retry_operation("chat", _do_chat)

    # ── Chat (streaming) ─────────────────────────────────────────

    def chat_stream(self, model: str, messages: list[dict],
                    tools: list[dict] | None = None,
                    options: dict | None = None,
                    keep_alive: str = "30m") -> Generator[dict, None, None]:
        """
        Stream a chat response with retry on initial connection.

        Yields:
            Ollama stream chunks. First chunk includes '_ttft_ms'.
        """
        def _do_stream():
            return self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                options=options,
                keep_alive=keep_alive,
                stream=True,
            )

        stream = self._retry_operation("chat_stream", _do_stream)

        first_token = True
        start = time.perf_counter()

        try:
            for chunk in stream:
                if first_token:
                    ttft_ms = (time.perf_counter() - start) * 1000
                    chunk["_ttft_ms"] = round(ttft_ms, 2)
                    first_token = False
                yield chunk
        except Exception as e:
            logger.error(f"Stream interrupted: {e}")
            # Don't retry mid-stream — the partial response is already sent
            return

    # ── Embedding ─────────────────────────────────────────────────

    def embed(self, model: str, input: str | list[str]) -> dict:
        """Generate embeddings with retry logic."""
        def _do_embed():
            return self._client.embed(model=model, input=input)

        return self._retry_operation("embed", _do_embed)

    # ── Model Management ─────────────────────────────────────────

    def ensure_model_loaded(self, model: str, keep_alive: str = "30m") -> bool:
        """
        Pre-warm a model by sending a minimal request.

        Returns:
            True if model is loaded and responding.
        """
        try:
            self._client.chat(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                options={"num_predict": 1, "num_ctx": 32},
                keep_alive=keep_alive,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to pre-warm model '{model}': {e}")
            return False

    def get_running_models(self) -> list[dict]:
        """Get currently loaded models from Ollama."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self._host}/api/ps")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    return data.get("models", [])
        except Exception:
            return []

    # ── Fallback Responses ───────────────────────────────────────

    @staticmethod
    def fallback_response(error: Exception | None = None) -> str:
        """Generate a graceful fallback response when Ollama is unavailable."""
        if error and "connection" in str(error).lower():
            return (
                "I'm having trouble connecting to my brain right now. "
                "Ollama might not be running. Let me try to reconnect — "
                "you can also check if Ollama is started."
            )
        return (
            "I wasn't able to process that request. "
            "There might be a temporary issue with my language model. "
            "Please try again in a moment."
        )

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Get client health and performance statistics."""
        with self._lock:
            total = self._total_requests + self._failed_requests
            success_rate = (
                (self._total_requests / total * 100) if total > 0 else 0
            )
            return {
                "connected": self._connected,
                "host": self._host,
                "total_requests": self._total_requests,
                "failed_requests": self._failed_requests,
                "total_retries": self._total_retries,
                "consecutive_failures": self._consecutive_failures,
                "success_rate_pct": round(success_rate, 1),
                "last_error": self._last_error,
                "available_models": self._available_models,
            }
