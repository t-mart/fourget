"""Logging setup."""

import arrow

from fourget.console import PROGRESS

# all are 5 characters long for easier reading/alignment
DEBUG_LABEL = "[bold steel_blue]DEBUG[/bold steel_blue]"
INFO_LABEL = "[bold blue]INFO [/bold blue]"
WARN_LABEL = "[bold yellow]WARN [/bold yellow]"
ERROR_LABEL = "[bold red]ERROR[/bold red]"


def _log(*, label: str, msg: str) -> None:
    timestr = arrow.now().isoformat()
    out = f"[bright_black]{timestr}[/bright_black] {label}  {msg}"
    PROGRESS.console.print(out)


def debug(msg: str) -> None:
    """Write a log message at DEBUG level."""
    _log(label=DEBUG_LABEL, msg=msg)


def info(msg: str) -> None:
    """Write a log message at INFO level."""
    _log(label=INFO_LABEL, msg=msg)


def warn(msg: str) -> None:
    """Write a log message at WARN level."""
    _log(label=WARN_LABEL, msg=msg)


def error(msg: str) -> None:
    """Write a log message at ERROR level."""
    _log(label=ERROR_LABEL, msg=msg)
