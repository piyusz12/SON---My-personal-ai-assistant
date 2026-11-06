# ui.py — Rich Terminal Interface for SON
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.markdown import Markdown
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.rule import Rule
from rich.style import Style
from rich import box


# ── Theme Colors ──────────────────────────────────────────
ACCENT = "#a78bfa"       # Purple accent
USER_COLOR = "#60a5fa"   # Blue for user
SON_COLOR = "#34d399"    # Green for SON
SYSTEM_COLOR = "#fbbf24" # Yellow for system
DIM_COLOR = "#6b7280"    # Gray for dim text
ERROR_COLOR = "#f87171"  # Red for errors


class TerminalUI:
    """Rich terminal interface for SON assistant."""

    def __init__(self):
        self.console = Console(legacy_windows=False)
        self._status_text = ""

    # ── Branding ──────────────────────────────────────────────

    def show_banner(self):
        """Display the SON startup banner."""
        banner_text = Text()
        banner_text.append("╔═══════════════════════════════════════════════════╗\n", style=ACCENT)
        banner_text.append("║                                                   ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   ███████╗ ██████╗ ███╗   ██╗", style=f"bold {SON_COLOR}")
        banner_text.append("                  ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   ██╔════╝██╔═══██╗████╗  ██║", style=f"bold {SON_COLOR}")
        banner_text.append("                  ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   ███████╗██║   ██║██╔██╗ ██║", style=f"bold {SON_COLOR}")
        banner_text.append("                  ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   ╚════██║██║   ██║██║╚██╗██║", style=f"bold {SON_COLOR}")
        banner_text.append("                  ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   ███████║╚██████╔╝██║ ╚████║", style=f"bold {SON_COLOR}")
        banner_text.append("                  ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝", style=f"bold {SON_COLOR}")
        banner_text.append("                  ║\n", style=ACCENT)
        banner_text.append("║                                                   ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   Personal AI Assistant", style=f"italic {DIM_COLOR}")
        banner_text.append("                          ║\n", style=ACCENT)
        banner_text.append("║", style=ACCENT)
        banner_text.append("   Voice • Memory • Code Intelligence", style=f"{DIM_COLOR}")
        banner_text.append("             ║\n", style=ACCENT)
        banner_text.append("║                                                   ║\n", style=ACCENT)
        banner_text.append("╚═══════════════════════════════════════════════════╝", style=ACCENT)

        self.console.print()
        self.console.print(banner_text)
        self.console.print()

    def show_startup_info(self, memory_stats: dict):
        """Show system info after initialization."""
        table = Table(
            show_header=False,
            box=box.SIMPLE,
            padding=(0, 2),
            style=DIM_COLOR,
        )
        table.add_column("Key", style=f"bold {ACCENT}")
        table.add_column("Value")

        table.add_row("Mode", "Voice + Keyboard")
        table.add_row("Memories", str(memory_stats.get("conversations", 0)))
        table.add_row("Code Chunks", str(memory_stats.get("codebase_chunks", 0)))
        table.add_row("Facts", str(memory_stats.get("facts", 0)))

        self.console.print(Panel(
            table,
            title="[bold]System Ready[/bold]",
            border_style=SON_COLOR,
            padding=(0, 1),
        ))
        self.console.print()

    def show_startup_info_extended(self, memory_stats: dict, tool_count: int = 0):
        """Show extended system info with tool count."""
        table = Table(
            show_header=False,
            box=box.SIMPLE,
            padding=(0, 2),
            style=DIM_COLOR,
        )
        table.add_column("Key", style=f"bold {ACCENT}")
        table.add_column("Value")

        table.add_row("Mode", "Voice + Keyboard + Tools")
        table.add_row("Tools", str(tool_count))
        table.add_row("Memories", str(memory_stats.get("conversations", 0)))
        table.add_row("Code Chunks", str(memory_stats.get("codebase_chunks", 0)))
        table.add_row("Facts", str(memory_stats.get("facts", 0)))

        self.console.print(Panel(
            table,
            title="[bold]System Ready[/bold]",
            border_style=SON_COLOR,
            padding=(0, 1),
        ))
        self.console.print()

    # ── Wake Word Status ──────────────────────────────────────

    def show_wakeword_waiting(self):
        """Show that SON is waiting for the wake word."""
        self.console.print(
            f"  [{ACCENT}]◉[/] [{DIM_COLOR}]Listening for wake word... say [bold {SON_COLOR}]\"Hey SON\"[/bold {SON_COLOR}][/]"
        )

    def show_wake_detected(self):
        """Show that the wake word was detected."""
        self.console.print(
            f"  [{SON_COLOR}]✦ Wake word detected![/] [{DIM_COLOR}]Listening...[/dim]"
        )

    # ── Status Updates ────────────────────────────────────────

    def show_listening(self):
        """Show listening indicator."""
        self.console.print(
            f"  [bold {ERROR_COLOR}]● REC[/]  [dim]Listening... (speak now, silence to stop)[/dim]"
        )

    def show_seamless_mode_start(self):
        """Display banner when seamless hands-free voice mode is activated."""
        self.console.print()
        self.console.print(
            f"  [{ACCENT}]┌─ 🎙️ SEAMLESS CONVERSATION ACTIVE[/] [{DIM_COLOR}]━━━━━━━━━━━━━━━━━━━━━━[/]"
        )
        self.console.print(
            f"  [{ACCENT}]│[/]  [{SON_COLOR}]Speak naturally with SON — hands-free![/]"
        )
        self.console.print(
            f"  [{ACCENT}]│[/]  [{DIM_COLOR}]Say 'bye', 'stop', or pause to end conversation.[/]"
        )
        self.console.print(
            f"  [{ACCENT}]└────────────────────────────────────────────────────────[/]"
        )
        self.console.print()

    def show_seamless_listening(self):
        """Show continuous listening prompt in seamless mode."""
        self.console.print(
            f"  [bold {ERROR_COLOR}]● LIVE[/]  [{SON_COLOR}]I'm listening, Dad...[/] [{DIM_COLOR}](speak freely)[/]"
        )

    def show_seamless_mode_stop(self):
        """Show when seamless conversation ends."""
        self.console.print(
            f"  [{ACCENT}]◉[/] [{DIM_COLOR}]Seamless conversation paused. Standing by for Dad...[/]"
        )
        self.console.print()

    # ── WhatsApp Message Drafting UI ──────────────────────────

    def show_whatsapp_draft_card(self, recipient: str, masked_phone: str, message: str, remaining_seconds: int):
        """Render rich visual card for WhatsApp pending draft."""
        self.console.print()
        self.console.print(
            f"  [{ACCENT}]┌─ 💬 WHATSAPP MESSAGE DRAFT[/] [{DIM_COLOR}]━━━━━━━━━━━━━━━━━━━━━━━━━━[/]"
        )
        self.console.print(
            f"  [{ACCENT}]│[/]  Recipient: [bold {SON_COLOR}]{recipient}[/] [{DIM_COLOR}]({masked_phone})[/]"
        )
        self.console.print(
            f"  [{ACCENT}]│[/]  Message:   [italic]\"{message}\"[/]"
        )
        self.console.print(
            f"  [{ACCENT}]│[/]  Status:    [bold yellow]● AWAITING CONFIRMATION[/] [{DIM_COLOR}](expires in {remaining_seconds}s)[/]"
        )
        self.console.print(
            f"  [{ACCENT}]│[/]  [{DIM_COLOR}]Say 'yes' to open draft in WhatsApp Web, or 'cancel' to discard.[/]"
        )
        self.console.print(
            f"  [{ACCENT}]└────────────────────────────────────────────────────────[/]"
        )
        self.console.print()

    def show_whatsapp_confirmed(self, recipient: str, masked_phone: str):
        """Show visual feedback when user verbally confirms WhatsApp draft."""
        self.console.print(
            f"  [{SUCCESS_COLOR}]✓[/] [bold {SUCCESS_COLOR}]Confirmed:[/] Opening WhatsApp conversation for {recipient} ({masked_phone})..."
        )

    def show_whatsapp_cancelled(self, recipient: str):
        """Show visual feedback when user cancels WhatsApp draft."""
        self.console.print(
            f"  [{ERROR_COLOR}]✗[/] [bold {ERROR_COLOR}]Cancelled:[/] WhatsApp draft for {recipient} discarded."
        )

    def show_thinking(self):
        """Show thinking indicator."""
        self.console.print(f"  [{SYSTEM_COLOR}]⟳[/]  [dim]Thinking...[/dim]", end="\r")

    def show_speaking(self):
        """Show speaking indicator."""
        self.console.print(f"  [{SON_COLOR}]🔊[/] [dim]Speaking...[/dim]")

    def update_status(self, text: str):
        """Update inline status text."""
        self._status_text = text
        self.console.print(f"  [{DIM_COLOR}]↳ {text}[/]")

    # ── Real-Time Thinking Visibility ─────────────────────────

    def show_thinking_start(self, user_input: str):
        """Show the start of a thinking trace with the user's input."""
        self.console.print()
        self.console.print(
            f"  [{ACCENT}]┌─ 🧠 SON THINKING[/] [{DIM_COLOR}]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]"
        )

    def show_thinking_step(self, step_idx: int, icon: str, name: str,
                            status: str = "running", duration_ms: float | None = None,
                            detail: str | None = None):
        """
        Display a single thinking step with real-time status.

        Args:
            step_idx: Step number (1-based).
            icon: Emoji icon for this step.
            name: Description of what's happening.
            status: 'running', 'done', or 'error'.
            duration_ms: Time taken (shown on completion).
            detail: Optional detail text (shown on completion).
        """
        if status == "running":
            # Step is starting — show inline indicator if in interactive terminal
            if self.console.is_terminal:
                self.console.print(
                    f"  [{ACCENT}]│[/]  {icon}  [{DIM_COLOR}]{name}...[/]",
                    end="\r",
                )
        elif status == "done":
            # Clear line if terminal, then show completed with timing
            if self.console.is_terminal:
                self.console.print(" " * 65, end="\r")
            if duration_ms is not None:
                if duration_ms < 1000:
                    time_str = f"{duration_ms:.1f}ms"
                else:
                    time_str = f"{duration_ms / 1000:.2f}s"
                self.console.print(
                    f"  [{ACCENT}]│[/]  {icon}  {name}  [{SON_COLOR}]{time_str} ✓[/]"
                )
            else:
                self.console.print(
                    f"  [{ACCENT}]│[/]  {icon}  {name}  [{SON_COLOR}]✓[/]"
                )
        elif status == "error":
            if self.console.is_terminal:
                self.console.print(" " * 65, end="\r")
            if duration_ms is not None:
                time_str = f"{duration_ms:.1f}ms"
                self.console.print(
                    f"  [{ACCENT}]│[/]  {icon}  {name}  [{ERROR_COLOR}]{time_str} ✗[/]"
                )
            else:
                self.console.print(
                    f"  [{ACCENT}]│[/]  {icon}  {name}  [{ERROR_COLOR}]✗[/]"
                )

    def show_thinking_detail(self, text: str):
        """Show a sub-detail line indented under the current step."""
        self.console.print(
            f"  [{ACCENT}]│[/]     [{DIM_COLOR}]└─ {text}[/]"
        )

    def show_thinking_summary(self, total_ms: float, steps: list[dict]):
        """
        Show the final timing summary at the end of thinking.

        Args:
            total_ms: Total elapsed time in milliseconds.
            steps: List of step dicts with name, duration_ms, status.
        """
        if total_ms < 1000:
            total_str = f"{total_ms:.0f}ms"
        else:
            total_str = f"{total_ms / 1000:.2f}s"

        # Count successful vs failed
        done_count = sum(1 for s in steps if s.get("status") == "done")
        error_count = sum(1 for s in steps if s.get("status") == "error")

        status_parts = [f"[{SON_COLOR}]{done_count} steps[/]"]
        if error_count > 0:
            status_parts.append(f"[{ERROR_COLOR}]{error_count} errors[/]")

        status_text = ", ".join(status_parts)

        self.console.print(
            f"  [{ACCENT}]└─ ⏱️  Total: [bold]{total_str}[/bold][/]  "
            f"[{DIM_COLOR}]({status_text}[{DIM_COLOR}])[/]"
        )
        self.console.print()


    # ── Messages ──────────────────────────────────────────────

    def show_user_message(self, text: str):
        """Display what Dad said."""
        self.console.print()
        self.console.print(
            Panel(
                Text(text, style="white"),
                title=f"[bold {USER_COLOR}]Dad[/]",
                border_style=USER_COLOR,
                padding=(0, 1),
            )
        )

    def show_son_response(self, text: str):
        """Display SON's response."""
        self.console.print(
            Panel(
                Markdown(text),
                title=f"[bold {SON_COLOR}]SON[/]",
                border_style=SON_COLOR,
                padding=(0, 1),
            )
        )
        self.console.print()

    def show_son_response_stream(self, token_generator):
        """Display SON's response as it streams, token by token."""
        full_text = []

        with Live(
            Panel(
                Text("▌", style=f"dim {SON_COLOR}"),
                title=f"[bold {SON_COLOR}]SON[/]",
                border_style=SON_COLOR,
                padding=(0, 1),
            ),
            console=self.console,
            refresh_per_second=15,
        ) as live:
            for token in token_generator:
                full_text.append(token)
                current = "".join(full_text) + " ▌"
                live.update(
                    Panel(
                        Markdown(current),
                        title=f"[bold {SON_COLOR}]SON[/]",
                        border_style=SON_COLOR,
                        padding=(0, 1),
                    )
                )

        # Final render without cursor
        final = "".join(full_text)
        self.console.print()
        return final

    def show_command_result(self, text: str):
        """Display command execution results."""
        self.console.print(
            Panel(
                Text(text),
                title=f"[bold {SYSTEM_COLOR}]System[/]",
                border_style=SYSTEM_COLOR,
                padding=(0, 1),
            )
        )
        self.console.print()

    def show_error(self, text: str):
        """Display an error message."""
        self.console.print(
            f"  [{ERROR_COLOR}]✖ Error:[/] {text}"
        )

    def show_transcription(self, text: str):
        """Show live transcription result."""
        self.console.print(
            f"  [{DIM_COLOR}]📝 Heard:[/] \"{text}\""
        )

    # ── Input ─────────────────────────────────────────────────

    def get_text_input(self) -> str:
        """Get keyboard input from the user."""
        try:
            from prompt_toolkit import prompt
            from prompt_toolkit.styles import Style as PTStyle
            from prompt_toolkit.key_binding import KeyBindings

            style = PTStyle.from_dict({
                "prompt": f"{USER_COLOR} bold",
            })

            kb = KeyBindings()

            @kb.add("space")
            def _handle_space(event):
                # If prompt buffer is empty, pressing Space immediately triggers voice input
                if not event.current_buffer.text.strip():
                    event.current_buffer.text = "__VOICE_TRIGGER__"
                    event.current_buffer.validate_and_handle()
                else:
                    event.current_buffer.insert_text(" ")

            text = prompt(
                [("class:prompt", " ❯ ")],
                style=style,
                key_bindings=kb,
            )
            return text.strip()

        except (ImportError, EOFError, KeyboardInterrupt):
            # Fallback to basic input
            try:
                val = input(" ❯ ")
                # If user hit space or empty enter
                if val.strip() == "" and len(val) > 0:
                    return "__VOICE_TRIGGER__"
                return val.strip()
            except (EOFError, KeyboardInterrupt):
                return "exit"

    def show_input_prompt(self):
        """Show the input mode prompt."""
        self.console.print(
            f"  [{DIM_COLOR}]Type a message or press[/] "
            f"[bold {ACCENT}]Space[/] [{DIM_COLOR}]for voice[/]",
            end="",
        )

    # ── Progress ──────────────────────────────────────────────

    def progress_bar(self, description: str = "Processing"):
        """Return a Rich progress bar context manager."""
        return Progress(
            SpinnerColumn(style=ACCENT),
            TextColumn(f"[{DIM_COLOR}]{description}[/]"),
            BarColumn(bar_width=30, style=ACCENT, complete_style=SON_COLOR),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        )

    # ── Separators ────────────────────────────────────────────

    def divider(self, text: str = ""):
        """Print a divider line."""
        self.console.print(Rule(text, style=DIM_COLOR))

    def goodbye(self):
        """Show exit message."""
        self.console.print()
        self.console.print(
            f"  [{SON_COLOR}]👋 Goodbye! See you next time.[/]"
        )
        self.console.print()

    # ── Action Visibility (Antigravity-style) ────────────────

    # Security level → display config
    _SECURITY_STYLES = {
        "safe":      {"icon": "🟢", "border": SON_COLOR,     "label": "SAFE"},
        "medium":    {"icon": "🟡", "border": SYSTEM_COLOR,  "label": "MEDIUM"},
        "sensitive": {"icon": "🟠", "border": "#f97316",     "label": "SENSITIVE"},
        "critical":  {"icon": "🔴", "border": ERROR_COLOR,   "label": "CRITICAL"},
    }

    def show_action_start(self, tool_name: str, args: dict, security_level):
        """
        Display a live action panel showing what SON is about to do.
        Visible to Dad in real-time, like Antigravity IDE's tool panels.
        """
        level_key = security_level.value if hasattr(security_level, 'value') else str(security_level)
        style = self._SECURITY_STYLES.get(level_key, self._SECURITY_STYLES["safe"])

        # Format arguments nicely
        args_str = ", ".join(f'{k}="{v}"' for k, v in (args or {}).items())
        action_text = f"{tool_name}({args_str})" if args_str else f"{tool_name}()"

        # Truncate very long args
        if len(action_text) > 120:
            action_text = action_text[:117] + "..."

        self.console.print(
            Panel(
                Text.from_markup(
                    f"{style['icon']}  [bold]Executing:[/bold] [white]{action_text}[/white]\n"
                    f"   [dim]Security: {style['label']}[/dim]"
                ),
                title=f"[bold {style['border']}]⚡ SON Action[/]",
                border_style=style["border"],
                padding=(0, 1),
            )
        )

    def show_action_result(self, tool_name: str, result: str, duration_ms: float, success: bool = True):
        """
        Display the result of a completed action.
        Shows timing and truncated output.
        """
        if success:
            icon = "✓"
            color = SON_COLOR
            status = "completed"
        else:
            icon = "✖"
            color = ERROR_COLOR
            status = "failed"

        # Truncate very long results for display
        display_result = result
        if len(display_result) > 200:
            display_result = display_result[:197] + "..."

        timing = f"{duration_ms:.0f}ms" if duration_ms < 1000 else f"{duration_ms/1000:.1f}s"

        self.console.print(
            f"  [{color}]{icon} {tool_name}[/] {status} [{DIM_COLOR}]({timing})[/]"
        )
        if display_result and display_result != "Done.":
            # Show result in a subtle indented block
            for line in display_result.split("\n")[:5]:
                self.console.print(f"    [{DIM_COLOR}]│[/] {line}")
            if display_result.count("\n") > 5:
                self.console.print(f"    [{DIM_COLOR}]│ ... ({display_result.count(chr(10))-5} more lines)[/]")

    def show_action_denied(self, tool_name: str, reason: str = "Denied by user"):
        """Show that an action was denied by Dad."""
        self.console.print(
            Panel(
                Text.from_markup(
                    f"🚫  [bold]Action Denied:[/bold] [white]{tool_name}[/white]\n"
                    f"   [dim]{reason}[/dim]"
                ),
                title=f"[bold {ERROR_COLOR}]⛔ Blocked[/]",
                border_style=ERROR_COLOR,
                padding=(0, 1),
            )
        )

    def ask_permission(self, tool_name: str, args: dict, security_level) -> bool:
        """
        Prompt Dad for permission to execute a sensitive/critical action.
        Returns True if approved, False if denied.
        """
        level_key = security_level.value if hasattr(security_level, 'value') else str(security_level)
        style = self._SECURITY_STYLES.get(level_key, self._SECURITY_STYLES["sensitive"])

        args_str = ", ".join(f'{k}="{v}"' for k, v in (args or {}).items())
        action_text = f"{tool_name}({args_str})" if args_str else f"{tool_name}()"

        if len(action_text) > 100:
            action_text = action_text[:97] + "..."

        self.console.print()
        self.console.print(
            Panel(
                Text.from_markup(
                    f"{style['icon']}  [bold]SON wants to execute:[/bold]\n"
                    f"   [white]{action_text}[/white]\n\n"
                    f"   [dim]Security Level: [bold]{style['label']}[/bold] — This action requires your approval.[/dim]"
                ),
                title=f"[bold {style['border']}]🔐 Permission Required[/]",
                border_style=style["border"],
                padding=(0, 1),
            )
        )

        try:
            response = input(f"  Allow this action? [Y/n] ❯ ").strip().lower()
            approved = response in ("", "y", "yes", "yeah", "yep", "sure", "ok", "okay", "do it", "go ahead")
        except (EOFError, KeyboardInterrupt):
            approved = False

        if approved:
            self.console.print(f"  [{SON_COLOR}]✓ Approved — executing...[/]")
        else:
            self.console.print(f"  [{ERROR_COLOR}]✖ Denied by Dad[/]")

        return approved

