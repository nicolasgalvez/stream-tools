"""Rich formatting helpers for CLI output."""

import csv
import io
import json
from collections.abc import Callable
from typing import Any

from rich.console import Console
from rich.table import Table

from stream_tools_cli.state import OutputFormat, config

console = Console()


def output(items: list, columns: dict[str, Callable[[Any], str]], title: str = "") -> None:
    """Dispatch output based on global format setting."""
    if config.format == OutputFormat.json:
        # Use to_dict() if available for proper schema, otherwise fall back to columns
        if items and hasattr(items[0], "to_dict"):
            rows = [item.to_dict() for item in items]
        else:
            rows = [{name: accessor(item) for name, accessor in columns.items()} for item in items]
        print(json.dumps(rows, indent=2))
    elif config.format == OutputFormat.csv:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(columns.keys()))
        writer.writeheader()
        for item in items:
            writer.writerow({name: accessor(item) for name, accessor in columns.items()})
        print(buf.getvalue(), end="")
    else:
        table = Table(title=title or None, show_lines=True)
        for name in columns:
            table.add_column(name, overflow="fold", no_wrap=False)
        for item in items:
            table.add_row(*(str(accessor(item)) for accessor in columns.values()))
        console.print(table)
