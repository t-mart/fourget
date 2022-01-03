"""Set up for console related things."""
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

PROGRESS = Progress(
    SpinnerColumn(),
    "[progress.description]{task.description}",
    BarColumn(),
    "[progress.percentage]{task.percentage:>3.0f}%",
    DownloadColumn(),
    TransferSpeedColumn(),
    "Remaining:",
    TimeRemainingColumn(),
    console=Console(stderr=True),
)
PROGRESS.start()
PROGRESS_TASK = PROGRESS.add_task(description="Downloading")
