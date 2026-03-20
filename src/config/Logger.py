from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.theme import Theme
from datetime import datetime


class Logger:
    def __init__(self):
        custom_theme = Theme({
            "info": "cyan",
            "warning": "yellow",
            "error": "bold red",
            "success": "bold green",
            "path": "underline blue",
            "server_start":"bold green",
            "server_shutdown":"bold red"
        })
        self.console = Console(theme=custom_theme)

    def log(self, message: str, style: str = "info"):
        time_str = datetime.now().strftime("%H:%M:%S")

        if style == "error":
            prefix = "[error] ERROR[/error]"
        elif style == "success":
            prefix = "[success] SUCCESS[/success]"
        elif style == "warning":
            prefix = "[warning] WARNING[/warning]"
        elif style == "server_start":
            prefix = "[server_start] SERVER STARTED ![/server_start]"
        elif style == "server_shutdown":
            prefix = "[server_shutdown] SERVER SHUTDOWN ![/server_shutdown]"
        else:
            prefix = "[info] INFO[/info]"

        self.console.print(f"[{time_str}] {prefix} {message}")

    def banner(self, title: str):
        self.console.print(Panel(f"[bold white]{title}[/bold white]", expand=False))

logger=Logger()