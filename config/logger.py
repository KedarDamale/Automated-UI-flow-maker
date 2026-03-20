import logging
from rich.console import Console
from rich.logging import RichHandler

console = Console()

def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=console,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
            )
        ],
    )
    for lib in ["playwright", "asyncio", "urllib3"]:
        logging.getLogger(lib).setLevel(logging.ERROR)

    return logging.getLogger(name)

logger=get_logger("logger")
