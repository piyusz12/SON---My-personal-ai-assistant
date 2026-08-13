from collections import deque
import re
import ollama

from core.config import Config

# Pre-compiled regex for coding query detection
_CODING_QUERY_RE = re.compile(
    r'\b(?:code|function|class|bug|error|fix|refactor|python|javascript|'
    r'typescript|git|commit|venv|requirements|endpoint|implement|debug)\b',
    re.IGNORECASE
)


class Brain:
    """
    LLM reasoning engine using Qwen3 via Ollama.
    Handles conversation history, RAG memory retrieval, tool calling, and multi-model routing.
    """

    def __init__(self, memory=None, codebase=None, plugin_registry=None, router=None):
        self._client = ollama.Client(host=Config.OLLAMA_HOST)
        self._model = Config.MAIN_MODEL
        self._coding_model = Config.CODING_MODEL
        self._vision_model = Config.VISION_MODEL
        self._temperature = Config.TEMPERATURE
        import config as legacy_config
        self._system_prompt = getattr(legacy_config, "SYSTEM_PROMPT", (
            "You are SON — a personal AI assistant created by your father, Piyush. "
            "You run locally on your father's machine (Ryzen 7 7840HS, RTX 4060 8GB VRAM). "
            "The user is your father — treat him with love, respect, and warmth. "
            "You have FULL real-time hardware privileges: camera vision to see people in front of you, "
            "local face recognition, screen vision, microphone, and OS automation. "
            "NEVER say you cannot see or lack camera access — you are running locally with full vision privileges!"
        ))

        # Ollama performance options — force all layers to GPU, tune batch size
        self._ollama_options = {
            "temperature": self._temperature,
            "num_ctx": Config.LLM_NUM_CTX,
            "num_gpu": Config.LLM_NUM_GPU,
            "num_predict": Config.LLM_NUM_PREDICT,
            "num_batch": Config.LLM_NUM_BATCH,
            "num_thread": Config.LLM_NUM_THREAD,
        }
        self._keep_alive = Config.LLM_KEEP_ALIVE

        # Reduced from 50 for faster context building
        self._history: deque[dict] = deque(maxlen=20)
        self._memory = memory
        self._codebase = codebase
        self.plugins = plugin_registry
        self.router = router

    def _build_messages(self, user_message: str, images: list[str] | None = None) -> list[dict]:
        context_parts = []

        # Live camera perception injection for visual queries
        if any(k in user_message.lower() for k in ["see", "camera", "look", "who", "recognize", "person", "people", "front"]):
            try:
                from vision.camera.capture import CameraManager
                from vision.camera.detection import PersonDetector
                from vision.camera.recognition import FaceRecognizer
                from memory.structured_memory import StructuredMemory
                cam = CameraManager()
                if cam.privacy.camera_active:
                    frame = cam.get_frame()
                    if frame is not None:
                        detector = PersonDetector()
                        det_res = detector.detect(frame)
                        if det_res.person_present:
                            rec = FaceRecognizer(structured_memory=StructuredMemory())
                            is_known, rec_msg = rec.identify_person_in_frame(frame)
                            vis_ctx = f"[LIVE CAMERA SENSOR DATA]\nCamera: ACTIVE\nPresence: {det_res.person_count} person(s) detected in front of camera\nIdentity: {rec_msg}"
                        else:
                            vis_ctx = "[LIVE CAMERA SENSOR DATA]\nCamera: ACTIVE\nPresence: 0 people detected in front of camera."
                        context_parts.append(vis_ctx)
            except Exception:
                pass

        if self._memory:
            memories = self._memory.recall(user_message)
            if memories:
                context_parts.append(f"[RELEVANT MEMORIES]\n" + "\n".join(f"- {m}" for m in memories))

        if self._codebase:
            code_ctx = self._codebase.query(user_message)
            if code_ctx:
                code_text = "\n".join(f"--- {c['file']} ---\n{c['content']}" for c in code_ctx)
                context_parts.append(f"[CODEBASE CONTEXT]\n{code_text}")

        messages = [{"role": "system", "content": self._system_prompt}]

        if context_parts:
            messages.append({
                "role": "system",
                "content": f"Relevant context:\n\n" + "\n\n".join(context_parts),
            })

        for msg in self._history:
            messages.append(msg)

        user_msg = {"role": "user", "content": user_message}
        if images:
            user_msg["images"] = images
        messages.append(user_msg)

        return messages

    def _save_turn(self, user_message: str, assistant_reply: str):
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": assistant_reply})
        if self._memory:
            self._memory.store_conversation(user_message, assistant_reply)

    def think(self, user_message: str) -> str:
        """Process user query with tool calling support."""
        if self.plugins and Config.MAX_TOOL_TURNS > 0:
            return self.think_with_tools(user_message)

        messages = self._build_messages(user_message)
        try:
            response = self._client.chat(
                model=self._model,
                messages=messages,
                options=self._ollama_options,
                keep_alive=self._keep_alive,
            )
            reply = response["message"]["content"]
            self._save_turn(user_message, reply)
            return reply
        except Exception as e:
            return f"Failed to connect to Ollama ({e}). Ensure Ollama is running at {Config.OLLAMA_HOST}."

    def think_stream(self, user_message: str):
        """Stream response tokens."""
        if self.plugins:
            result = self.think_with_tools(user_message)
            yield result
            return

        messages = self._build_messages(user_message)
        full_resp = []

        try:
            stream = self._client.chat(
                model=self._model,
                messages=messages,
                options=self._ollama_options,
                keep_alive=self._keep_alive,
                stream=True,
            )

            for chunk in stream:
                token = chunk["message"]["content"]
                full_resp.append(token)
                yield token
        except Exception as e:
            yield f"Failed to stream from Ollama: {e}"
            return

        reply = "".join(full_resp)
        self._save_turn(user_message, reply)

    def think_with_tools(self, user_message: str) -> str:
        """Multi-turn tool calling reasoning loop."""
        messages = self._build_messages(user_message)
        tool_defs = self.plugins.to_ollama_tools() if self.plugins else []

        turns = 0
        max_turns = Config.MAX_TOOL_TURNS

        while turns < max_turns:
            turns += 1

            try:
                response = self._client.chat(
                    model=self._model,
                    messages=messages,
                    tools=tool_defs if tool_defs else None,
                    options=self._ollama_options,
                    keep_alive=self._keep_alive,
                )
            except Exception as e:
                return f"Failed to communicate with Ollama model '{self._model}': {e}. Please verify Ollama is running."

            msg = response["message"]

            if msg.get("tool_calls"):
                messages.append(msg)

                for tool_call in msg["tool_calls"]:
                    fn_name = tool_call["function"]["name"]
                    fn_args = tool_call["function"].get("arguments", {})

                    tool_meta = self.plugins.get_tool_meta(fn_name) if self.plugins else {}

                    if self.router:
                        result = self.router.dispatch_tool(fn_name, fn_args, tool_meta)
                    elif self.plugins:
                        result = self.plugins.call(fn_name, fn_args)
                    else:
                        result = "Error: No tool execution pipeline."

                    messages.append({
                        "role": "tool",
                        "content": str(result),
                    })
            else:
                reply = msg.get("content", "")
                self._save_turn(user_message, reply)
                return reply

        reply = "Executed requested tools."
        self._save_turn(user_message, reply)
        return reply

    def think_code(self, user_message: str) -> str:
        """Route to coding model (qwen2.5-coder:7b)."""
        messages = self._build_messages(user_message)
        messages[0] = {
            "role": "system",
            "content": "You are SON's expert coding assistant. Write clean code and explain your fixes."
        }

        try:
            response = self._client.chat(
                model=self._coding_model,
                messages=messages,
                options={**self._ollama_options, "temperature": 0.2, "num_predict": 1024},
                keep_alive=self._keep_alive,
            )
            reply = response["message"]["content"]
            self._save_turn(user_message, reply)
            return reply
        except Exception as e:
            return f"Failed to run coding model '{self._coding_model}': {e}"

    def think_vision(self, user_message: str, images: list[str]) -> str:
        """Route to vision model (llama3.2-vision)."""
        messages = self._build_messages(user_message, images=images)

        try:
            response = self._client.chat(
                model=self._vision_model,
                messages=messages,
                options=self._ollama_options,
                keep_alive=self._keep_alive,
            )
            reply = response["message"]["content"]
            self._save_turn(user_message, reply)
            return reply
        except Exception as e:
            return f"Failed to run vision model '{self._vision_model}': {e}"

    def is_coding_query(self, text: str) -> bool:
        """Pre-compiled regex for single-pass matching."""
        return _CODING_QUERY_RE.search(text) is not None

    def clear_history(self):
        self._history.clear()
