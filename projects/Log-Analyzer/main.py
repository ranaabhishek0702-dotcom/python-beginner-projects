"""main.py - Command-line interface for the Log Analyzer tool.

Provides CLI functionality to parse log files, display human-readable
summaries or JSON output, and optionally write the report to an output file.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure local imports work when invoked from any working directory
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from analyzer import FileAccessError, analyze_log_file


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="log-analyzer",
        description=(
            "Analyze application and system log files for statistics, "
            "levels, and error trends."
        ),
    )
    parser.add_argument(
        "log_file",
        help="Path to the log file to analyze.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        metavar="N",
        help=(
            "Number of most frequent ERROR and CRITICAL messages to "
            "display (default: 5)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (human-readable) or 'json' (default: text).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Optional destination file path to save the generated report.",
    )
    return parser


def format_text_report(stats: Dict[str, Any], source_name: str) -> str:
    """Format log statistics into a structured, human-readable terminal report."""
    lines = [
        "=" * 60,
        "LOG ANALYSIS REPORT",
        "=" * 60,
        f"Source File: {source_name}",
        "",
        "Line Overview:",
        f"  Total lines:       {stats['total_lines']:>10}",
        f"  Parsed lines:      {stats['parsed_lines']:>10}",
        f"  Malformed lines:   {stats['malformed_lines']:>10}",
        f"  Blank lines:       {stats['blank_lines']:>10}",
        "",
        "Time Range:",
        f"  Earliest:          {stats['earliest_timestamp'] or 'N/A'}",
        f"  Latest:            {stats['latest_timestamp'] or 'N/A'}",
        "",
        "Log Level Breakdown:",
    ]

    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        count = stats["level_counts"].get(level, 0)
        pct = stats["level_percentages"].get(level, 0.0)
        lines.append(f"  {level:<10}: {count:>8} ({pct:>6.2f}%)")

    lines.append("")
    frequent_errors = stats.get("frequent_errors", [])
    if frequent_errors:
        lines.append(f"Top {len(frequent_errors)} Frequent Errors (ERROR / CRITICAL):")
        for idx, item in enumerate(frequent_errors, start=1):
            lines.append(f"  {idx}. [{item['count']}x] {item['message']}")
    else:
        lines.append("Top Frequent Errors:")
        lines.append("  No ERROR or CRITICAL messages recorded.")

    lines.append("=" * 60)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI application entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top < 0:
        sys.stderr.write("Error: --top must be a non-negative integer.\n")
        return 1

    try:
        stats = analyze_log_file(args.log_file, top_n=args.top)
    except FileAccessError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Unexpected error: {err}\n")
        return 1

    if args.format == "json":
        report_content = json.dumps(stats, indent=2)
    else:
        report_content = format_text_report(stats, source_name=str(args.log_file))

    if args.output:
        out_path = Path(args.output)
        try:
            if out_path.parent and not out_path.parent.exists():
                out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report_content + "\n", encoding="utf-8")
            print(f"Report successfully saved to {out_path}")
        except OSError as err:
            sys.stderr.write(f"Error: Unable to write report to '{out_path}': {err}\n")
            return 1
    else:
        print(report_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
