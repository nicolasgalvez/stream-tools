"""Global CLI state shared across commands."""

import inspect
import sys
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Callable, TypeVar

import typer
from loguru import logger

F = TypeVar("F", bound=Callable)


class OutputFormat(str, Enum):
    table = "table"
    json = "json"
    csv = "csv"
    ids = "ids"


@dataclass
class OutputConfig:
    format: OutputFormat = OutputFormat.table
    verbose: bool = False


config = OutputConfig()


def _process_common_options(
    verbose: bool = False, format: OutputFormat = OutputFormat.table
) -> None:
    """Configure global state from CLI options."""
    config.format = format
    config.verbose = verbose
    logger.remove()
    if verbose:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<dim>{time:HH:mm:ss}</dim> | <level>{message}</level>",
        )


def common_options(f: F) -> F:
    """Decorator that adds --format and --verbose options to any command.

    Uses signature manipulation so Typer discovers the injected parameters.
    No need to add parameters to the wrapped function - they're added automatically.
    """
    sig = inspect.signature(f)

    # Define the new parameters to inject (must include annotation for Typer to parse correctly)
    new_params = [
        inspect.Parameter(
            "verbose",
            inspect.Parameter.KEYWORD_ONLY,
            default=typer.Option(False, "--verbose", "-v", help="Verbose output"),
            annotation=bool,
        ),
        inspect.Parameter(
            "format",
            inspect.Parameter.KEYWORD_ONLY,
            default=typer.Option(
                OutputFormat.table, "--format", help="Output format: table, json, csv, ids"
            ),
            annotation=OutputFormat,
        ),
    ]

    # Combine original params with new ones
    all_params = list(sig.parameters.values()) + new_params
    new_sig = sig.replace(parameters=all_params)

    @wraps(f)
    def wrapper(
        *args, verbose: bool = False, format: OutputFormat = OutputFormat.table, **kwargs
    ):
        _process_common_options(verbose, format)
        return f(*args, **kwargs)

    # Set the new signature - this is what Typer inspects
    wrapper.__signature__ = new_sig  # type: ignore
    return wrapper  # type: ignore
