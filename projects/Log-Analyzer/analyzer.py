"""analyzer.py - Core log parsing and statistics analysis module.

This module provides functions to parse line-by-line log records formatted as:
    YYYY-MM-DD HH:MM:SS LEVEL Message

It calculates summary metrics including parsed lines, malformed lines,
blank lines, log-level counts and percentages, top frequent error messages,
and timestamp ranges.
"""

from collections import Counter
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, Iterable, NamedTuple, Optional, Tuple, Union

# Supported log severity levels
VALID_LEVELS: Tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
VALID_LEVELS_SET = set(VALID_LEVELS)

# Severity levels considered for error ranking
ERROR_LEVELS = {"ERROR", "CRITICAL"}

# Regex pattern matching YYYY-MM-DD HH:MM:SS LEVEL [Message]
# Group 1: Date (YYYY-MM-DD)
# Group 2: Time (HH:MM:SS)
# Group 3: Log level ([A-Za-z]+)
# Group 4: Message (optional remainder of the line)
LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+([A-Za-z]+)(?:\s(.*))?$"
)


class LogAnalyzerError(Exception):
    """Base exception for log analysis domain errors."""


class FileAccessError(LogAnalyzerError):
    """Raised when a log file cannot be found, opened, or read."""


class LogEntry(NamedTuple):
    """Represents a validated, parsed log record."""

    timestamp: datetime
    level: str
    message: str


def is_blank_line(line: str) -> bool:
    """Return True if the line is empty or contains only whitespace."""
    return len(line.strip()) == 0


def parse_line(line: str) -> Optional[LogEntry]:
    """Parse a single raw log line into a LogEntry.

    The expected format is:
        YYYY-MM-DD HH:MM:SS LEVEL Message

    Returns:
        LogEntry if the line is valid and matches all format requirements,
        or None if the line is blank, malformed, contains an invalid date,
        or specifies an unrecognized log level.
    """
    stripped_end = line.rstrip("\r\n")
    if is_blank_line(stripped_end):
        return None

    match = LOG_PATTERN.match(stripped_end)
    if not match:
        return None

    date_str, time_str, level_str, message_part = match.groups()

    # Validate log level (must match known uppercase levels)
    if level_str not in VALID_LEVELS_SET:
        return None

    # Validate timestamp using datetime facilities
    # (checks leap years, valid days, hours, etc.)
    ts_str = f"{date_str} {time_str}"
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    message = message_part if message_part is not None else ""
    return LogEntry(timestamp=dt, level=level_str, message=message)


def analyze_lines(lines: Iterable[str], top_n: int = 5) -> Dict[str, Any]:
    """Analyze an iterable of log lines incrementally and compute summary statistics.

    Args:
        lines: Iterable of string lines (e.g. open file handle or list of strings).
        top_n: Number of most frequent ERROR and CRITICAL messages to return.
               Must be a non-negative integer.

    Returns:
        Dictionary containing summary statistics:
        - total_lines (int)
        - parsed_lines (int)
        - malformed_lines (int)
        - blank_lines (int)
        - earliest_timestamp (str or None)
        - latest_timestamp (str or None)
        - level_counts (dict of level -> int)
        - level_percentages (dict of level -> float)
        - frequent_errors (list of dicts with 'message' and 'count')

    Raises:
        TypeError: If top_n is not an integer.
        ValueError: If top_n is negative.
    """
    if not isinstance(top_n, int) or isinstance(top_n, bool):
        raise TypeError("top_n must be an integer")
    if top_n < 0:
        raise ValueError("top_n must be a non-negative integer")

    total_lines = 0
    parsed_lines = 0
    malformed_lines = 0
    blank_lines = 0

    level_counts: Dict[str, int] = {lvl: 0 for lvl in VALID_LEVELS}
    error_counter: Counter = Counter()

    earliest_dt: Optional[datetime] = None
    latest_dt: Optional[datetime] = None

    for raw_line in lines:
        total_lines += 1
        line = raw_line.rstrip("\r\n")

        if is_blank_line(line):
            blank_lines += 1
            continue

        entry = parse_line(line)
        if entry is None:
            malformed_lines += 1
            continue

        parsed_lines += 1
        level_counts[entry.level] += 1

        if entry.level in ERROR_LEVELS:
            error_counter[entry.message] += 1

        if earliest_dt is None or entry.timestamp < earliest_dt:
            earliest_dt = entry.timestamp
        if latest_dt is None or entry.timestamp > latest_dt:
            latest_dt = entry.timestamp

    # Compute percentage breakdown relative to successfully parsed lines
    level_percentages: Dict[str, float] = {}
    for lvl in VALID_LEVELS:
        if parsed_lines > 0:
            pct = (level_counts[lvl] / parsed_lines) * 100.0
            level_percentages[lvl] = round(pct, 2)
        else:
            level_percentages[lvl] = 0.0

    # Extract top N frequent errors
    frequent_errors = [
        {"message": msg, "count": count}
        for msg, count in error_counter.most_common(top_n)
    ]

    return {
        "total_lines": total_lines,
        "parsed_lines": parsed_lines,
        "malformed_lines": malformed_lines,
        "blank_lines": blank_lines,
        "earliest_timestamp": (
            earliest_dt.strftime("%Y-%m-%d %H:%M:%S") if earliest_dt else None
        ),
        "latest_timestamp": (
            latest_dt.strftime("%Y-%m-%d %H:%M:%S") if latest_dt else None
        ),
        "level_counts": level_counts,
        "level_percentages": level_percentages,
        "frequent_errors": frequent_errors,
    }


def analyze_log_file(file_path: Union[str, Path], top_n: int = 5) -> Dict[str, Any]:
    """Read and analyze a log file incrementally from disk.

    Args:
        file_path: Path to the log file (str or pathlib.Path).
        top_n: Number of top frequent error messages to retrieve.

    Returns:
        Dictionary containing summary statistics.

    Raises:
        FileAccessError: If the file does not exist, is a directory, cannot be read,
                         or contains non-UTF-8 decoding errors.
        TypeError: If top_n is not an integer.
        ValueError: If top_n is negative.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileAccessError(f"Log file does not exist: '{path}'")
    if path.is_dir():
        raise FileAccessError(f"Path is a directory, not a file: '{path}'")

    try:
        with path.open("r", encoding="utf-8") as f:
            return analyze_lines(f, top_n=top_n)
    except UnicodeDecodeError as err:
        raise FileAccessError(f"Failed to decode '{path}' as UTF-8: {err}") from err
    except PermissionError as err:
        raise FileAccessError(f"Permission denied reading '{path}': {err}") from err
    except OSError as err:
        raise FileAccessError(f"Error accessing file '{path}': {err}") from err
