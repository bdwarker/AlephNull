"""Digital trail writer for risk scoring decisions."""

from pathlib import Path


def write_audit_log(path: str, entry: str) -> None:
    """Append an audit entry to the configured log file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a", encoding="utf-8") as file:
        file.write(f"{entry}\n")
