# ui.py — Rich Terminal Interface for SON
import sys
import time

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
        self.console = Console()
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

    # ── Messages ──────────────────────────────────────────────

    def show_user_message(self, text: str):
        """Display what the user said."""
        self.console.print()
        self.console.print(
            Panel(
                Text(text, style="white"),
                title=f"[bold {USER_COLOR}]You[/]",
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

            style = PTStyle.from_dict({
                "prompt": f"{USER_COLOR} bold",
            })

            text = prompt(
                [("class:prompt", " ❯ ")],
                style=style,
            )
            return text.strip()

        except (ImportError, EOFError, KeyboardInterrupt):
            # Fallback to basic input
            try:
                return input(" ❯ ").strip()
            except (EOFError, KeyboardInterrupt):
                return "exit"

    def show_input_prompt(self):
        """Show the input mode prompt."""
        self.console.print(
            f"  [{DIM_COLOR}]Type a message or press[/] "
            f"[bold {ACCENT}]V[/] [{DIM_COLOR}]for voice[/]",
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
