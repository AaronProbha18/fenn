import logging
import re
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style
from rich.console import Console
from rich.table import Table


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _flatten_dict(d: dict, parent_key: str = "", sep: str = "/") -> dict:
    """Recursively flattens a nested dictionary."""

    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))

    return dict(items)


def _get_colored_parts(key: str) -> list:
    colors = [
        Fore.LIGHTCYAN_EX,
        Fore.LIGHTBLUE_EX,
        Fore.LIGHTMAGENTA_EX,
        Fore.LIGHTGREEN_EX,
    ]
    parts = key.split("/")
    colored_parts = []

    for i, part in enumerate(parts):
        color = colors[i % len(colors)]
        colored_parts.append(f"{color}{part}{Style.RESET_ALL}")
    return colored_parts


def _write_config_fnxml(flat_config: dict, log_file: Path) -> None:
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("  <config>\n")
        for key, value in flat_config.items():
            f.write(
                f'    <item key="{_escape(str(key))}" '
                f'value="{_escape(str(value))}" />\n'
            )
        f.write("  </config>\n")


def _write_config_txt(log_file, message):
    message = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])").sub("", message)
    timestamp_dt = datetime.now().replace(microsecond=0)
    timestamp = timestamp_dt.isoformat(" ")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] INFO | {message}\n")


def _display_config(flat_config: dict, config_file: str, log_file: Path):
    table = Table(title="")
    table.add_column(f"Configuration file {config_file} loaded", style="", width=80)
    for k, v in flat_config.items():
        colored_parts = _get_colored_parts(key=k)
        table.add_row(f"{'/'.join(colored_parts)}: {v}")
        _write_config_txt(message=f"{'/'.join(colored_parts)}: {v}", log_file=log_file)
    Console().print(table)


def _form_log_paths(args: dict) -> dict[str | Path]:
    log_root = Path(args["logger"]["dir"]).expanduser()
    log_dir = log_root / Path(args["project"])
    log_dir.mkdir(parents=True, exist_ok=True)
    fn_filename = f"{args['session_id']}.fn"
    txt_filename = f"{args['session_id']}.log"
    fn_file = log_dir / fn_filename
    txt_file = log_dir / txt_filename
    return {"fn_dir": fn_file, "txt_dir": txt_file}


def write_config(
    args: dict,
    config_file: str,
) -> None:
    log_files = _form_log_paths(args)
    flat_config = _flatten_dict(args)
    _display_config(
        flat_config=flat_config,
        config_file=config_file,
        log_file=log_files.get("txt_dir"),
    )
    _write_config_fnxml(flat_config, log_files.get("fn_dir"))


logger = logging.getLogger("__name__")
logger.setLevel(logging.DEBUG)

console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
console.setFormatter(logging.Formatter("%(message)s"))

logger.addHandler(console)
