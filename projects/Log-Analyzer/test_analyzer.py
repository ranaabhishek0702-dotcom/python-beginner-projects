"""test_analyzer.py - Comprehensive test suite for Log Analyzer.

Tests parsing logic, statistics aggregation, timestamp validation,
file error handling, CLI execution, and output formatting.
"""

from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ensure local imports work regardless of current working directory
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from analyzer import (
    ERROR_LEVELS,
    VALID_LEVELS,
    FileAccessError,
    LogAnalyzerError,
    LogEntry,
    analyze_lines,
    analyze_log_file,
    is_blank_line,
    parse_line,
)
from main import build_parser, format_text_report, main


class TestLineParsing(unittest.TestCase):
    """Unit tests for single-line parsing and validation."""

    def test_parse_valid_lines_all_levels(self):
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for lvl in levels:
            raw = f"2026-10-27 12:30:45 {lvl} Service state changed to {lvl}"
            entry = parse_line(raw)
            self.assertIsNotNone(entry, f"Failed to parse valid level {lvl}")
            self.assertEqual(entry.level, lvl)
            self.assertEqual(entry.timestamp.year, 2026)
            self.assertEqual(entry.timestamp.month, 10)
            self.assertEqual(entry.timestamp.day, 27)
            self.assertEqual(entry.timestamp.hour, 12)
            self.assertEqual(entry.timestamp.minute, 30)
            self.assertEqual(entry.timestamp.second, 45)
            self.assertEqual(entry.message, f"Service state changed to {lvl}")

    def test_parse_message_with_spaces_and_special_characters(self):
        raw = (
            "2026-01-15 08:00:00 INFO User 'admin' logged in from "
            "192.168.1.100 [port=8080]: session=ok"
        )
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        self.assertEqual(
            entry.message,
            "User 'admin' logged in from 192.168.1.100 [port=8080]: session=ok",
        )

    def test_parse_empty_message(self):
        raw = "2026-10-27 10:00:00 INFO"
        entry = parse_line(raw)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.message, "")

    def test_parse_invalid_calendar_dates(self):
        # Non-leap year February 29
        self.assertIsNone(parse_line("2025-02-29 10:00:00 ERROR Non-leap day"))
        # February 30
        self.assertIsNone(parse_line("2026-02-30 10:00:00 ERROR Bad Feb day"))
        # Month 13
        self.assertIsNone(parse_line("2026-13-01 10:00:00 ERROR Invalid month"))
        # Day 32
        self.assertIsNone(parse_line("2026-01-32 10:00:00 ERROR Invalid day"))

    def test_parse_invalid_clock_times(self):
        # Hour 24
        self.assertIsNone(parse_line("2026-10-27 24:00:00 ERROR Bad hour"))
        # Minute 60
        self.assertIsNone(parse_line("2026-10-27 10:60:00 ERROR Bad minute"))
        # Second 60
        self.assertIsNone(parse_line("2026-10-27 10:00:60 ERROR Bad second"))

    def test_parse_malformed_timestamp_formats(self):
        # Missing seconds
        self.assertIsNone(parse_line("2026-10-27 10:00 ERROR Missing seconds"))
        # Slash instead of hyphen
        self.assertIsNone(parse_line("2026/10/27 10:00:00 ERROR Slashes in date"))
        # Non-numeric
        self.assertIsNone(parse_line("2026-XX-YY 10:00:00 ERROR Letters in date"))

    def test_parse_unknown_log_levels(self):
        # Lowercase / mixed case
        self.assertIsNone(parse_line("2026-10-27 10:00:00 info Lowercase level"))
        self.assertIsNone(parse_line("2026-10-27 10:00:00 Info Capitalized level"))
        # Unrecognized severity names
        self.assertIsNone(parse_line("2026-10-27 10:00:00 TRACE Trace message"))
        self.assertIsNone(parse_line("2026-10-27 10:00:00 FATAL Fatal message"))
        self.assertIsNone(parse_line("2026-10-27 10:00:00 NOTICE Notice message"))

    def test_parse_arbitrary_unstructured_text(self):
        self.assertIsNone(parse_line("Traceback (most recent call last):"))
        self.assertIsNone(parse_line('  File "app.py", line 42, in <module>'))
        self.assertIsNone(parse_line("Some random log without timestamp"))

    def test_is_blank_line(self):
        self.assertTrue(is_blank_line(""))
        self.assertTrue(is_blank_line("   "))
        self.assertTrue(is_blank_line("\t\n"))
        self.assertFalse(is_blank_line("2026-10-27 10:00:00 INFO Start"))


class TestAnalyzeLines(unittest.TestCase):
    """Unit tests for log line stream aggregation and statistics."""

    def test_normal_log_stream(self):
        lines = [
            "2026-10-27 08:00:00 DEBUG Cache initialized",
            "2026-10-27 08:05:00 INFO User logged in",
            "2026-10-27 08:10:00 WARNING Disk usage high",
            "2026-10-27 08:15:00 ERROR Connection lost",
            "2026-10-27 08:20:00 CRITICAL Kernel panic",
        ]
        stats = analyze_lines(lines, top_n=5)

        self.assertEqual(stats["total_lines"], 5)
        self.assertEqual(stats["parsed_lines"], 5)
        self.assertEqual(stats["malformed_lines"], 0)
        self.assertEqual(stats["blank_lines"], 0)
        self.assertEqual(stats["earliest_timestamp"], "2026-10-27 08:00:00")
        self.assertEqual(stats["latest_timestamp"], "2026-10-27 08:20:00")

        for lvl in VALID_LEVELS:
            self.assertEqual(stats["level_counts"][lvl], 1)
            self.assertAlmostEqual(stats["level_percentages"][lvl], 20.0, places=2)

        self.assertEqual(len(stats["frequent_errors"]), 2)
        error_msgs = {item["message"] for item in stats["frequent_errors"]}
        self.assertEqual(error_msgs, {"Connection lost", "Kernel panic"})

    def test_empty_stream(self):
        stats = analyze_lines([], top_n=5)
        self.assertEqual(stats["total_lines"], 0)
        self.assertEqual(stats["parsed_lines"], 0)
        self.assertEqual(stats["malformed_lines"], 0)
        self.assertEqual(stats["blank_lines"], 0)
        self.assertIsNone(stats["earliest_timestamp"])
        self.assertIsNone(stats["latest_timestamp"])
        self.assertEqual(stats["frequent_errors"], [])
        for lvl in VALID_LEVELS:
            self.assertEqual(stats["level_counts"][lvl], 0)
            self.assertEqual(stats["level_percentages"][lvl], 0.0)

    def test_stream_with_only_blank_lines(self):
        lines = ["\n", "   \n", "\t\t\n"]
        stats = analyze_lines(lines)
        self.assertEqual(stats["total_lines"], 3)
        self.assertEqual(stats["parsed_lines"], 0)
        self.assertEqual(stats["malformed_lines"], 0)
        self.assertEqual(stats["blank_lines"], 3)
        self.assertIsNone(stats["earliest_timestamp"])

    def test_stream_with_only_malformed_lines(self):
        lines = [
            "Random unformatted error line\n",
            "2026-99-99 12:00:00 ERROR Out of range date\n",
            "2026-10-27 12:00:00 UNKNOWN Unknown level\n",
        ]
        stats = analyze_lines(lines)
        self.assertEqual(stats["total_lines"], 3)
        self.assertEqual(stats["parsed_lines"], 0)
        self.assertEqual(stats["malformed_lines"], 3)
        self.assertEqual(stats["blank_lines"], 0)
        self.assertIsNone(stats["earliest_timestamp"])
        for lvl in VALID_LEVELS:
            self.assertEqual(stats["level_counts"][lvl], 0)
            self.assertEqual(stats["level_percentages"][lvl], 0.0)

    def test_mixed_stream_accounting_invariants(self):
        lines = [
            "2026-10-27 10:00:00 INFO System started",
            "",
            "2026-10-27 10:05:00 ERROR DB failure",
            "   ",
            "Not a valid line",
            "2026-10-27 10:10:00 WARNING High load",
            "Another invalid line",
        ]
        stats = analyze_lines(lines)
        self.assertEqual(stats["total_lines"], 7)
        self.assertEqual(stats["parsed_lines"], 3)
        self.assertEqual(stats["malformed_lines"], 2)
        self.assertEqual(stats["blank_lines"], 2)
        # Total invariant verification
        self.assertEqual(
            stats["total_lines"],
            stats["parsed_lines"] + stats["malformed_lines"] + stats["blank_lines"],
        )

    def test_frequent_error_ranking_and_top_n(self):
        lines = [
            "2026-10-27 09:00:00 ERROR Timeout connecting to db",
            "2026-10-27 09:01:00 ERROR Timeout connecting to db",
            "2026-10-27 09:02:00 CRITICAL Out of memory",
            "2026-10-27 09:03:00 ERROR Disk full",
            "2026-10-27 09:04:00 ERROR Timeout connecting to db",
            "2026-10-27 09:05:00 CRITICAL Out of memory",
            # Lines below should NOT be counted as errors
            "2026-10-27 09:06:00 WARNING Disk usage high",
            "2026-10-27 09:07:00 INFO Heartbeat ok",
        ]
        # Request top 2
        stats = analyze_lines(lines, top_n=2)
        frequent = stats["frequent_errors"]
        self.assertEqual(len(frequent), 2)
        self.assertEqual(frequent[0]["message"], "Timeout connecting to db")
        self.assertEqual(frequent[0]["count"], 3)
        self.assertEqual(frequent[1]["message"], "Out of memory")
        self.assertEqual(frequent[1]["count"], 2)

        # Request top 0
        stats_top0 = analyze_lines(lines, top_n=0)
        self.assertEqual(stats_top0["frequent_errors"], [])

        # Request top 10 (greater than distinct errors count of 3)
        stats_top10 = analyze_lines(lines, top_n=10)
        self.assertEqual(len(stats_top10["frequent_errors"]), 3)

    def test_invalid_top_n_parameters(self):
        lines = ["2026-10-27 10:00:00 INFO Test"]
        with self.assertRaises(ValueError):
            analyze_lines(lines, top_n=-1)
        with self.assertRaises(TypeError):
            analyze_lines(lines, top_n="five")  # type: ignore
        with self.assertRaises(TypeError):
            analyze_lines(lines, top_n=3.5)  # type: ignore
        with self.assertRaises(TypeError):
            analyze_lines(lines, top_n=True)  # type: ignore

    def test_out_of_order_timestamps(self):
        lines = [
            "2026-10-27 15:00:00 INFO Middle",
            "2026-10-27 18:00:00 INFO Latest",
            "2026-10-27 09:00:00 INFO Earliest",
        ]
        stats = analyze_lines(lines)
        self.assertEqual(stats["earliest_timestamp"], "2026-10-27 09:00:00")
        self.assertEqual(stats["latest_timestamp"], "2026-10-27 18:00:00")


class TestAnalyzeLogFile(unittest.TestCase):
    """Unit tests for reading files from disk and exception handling."""

    def test_read_real_file(self):
        content = (
            "2026-10-27 10:00:00 INFO App started\n"
            "2026-10-27 10:05:00 ERROR DB connection failed\n"
            "\n"
            "Invalid line\n"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write(content)
            temp_path = Path(tf.name)

        try:
            stats = analyze_log_file(temp_path)
            self.assertEqual(stats["total_lines"], 4)
            self.assertEqual(stats["parsed_lines"], 2)
            self.assertEqual(stats["malformed_lines"], 1)
            self.assertEqual(stats["blank_lines"], 1)
            self.assertEqual(stats["level_counts"]["INFO"], 1)
            self.assertEqual(stats["level_counts"]["ERROR"], 1)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_missing_file_raises_file_access_error(self):
        missing_path = Path("non_existent_file_12345.log")
        with self.assertRaises(FileAccessError) as ctx:
            analyze_log_file(missing_path)
        self.assertIn("does not exist", str(ctx.exception))

    def test_directory_path_raises_file_access_error(self):
        with tempfile.TemporaryDirectory() as td:
            dir_path = Path(td)
            with self.assertRaises(FileAccessError) as ctx:
                analyze_log_file(dir_path)
            self.assertIn("is a directory", str(ctx.exception))

    def test_decoding_error_raises_file_access_error(self):
        # Write invalid UTF-8 bytes to temporary file
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
            tf.write(b"\xff\xfe\x99\x88\x77\xaa")
            temp_path = Path(tf.name)

        try:
            with self.assertRaises(FileAccessError) as ctx:
                analyze_log_file(temp_path)
            self.assertIn("Failed to decode", str(ctx.exception))
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestReportFormattingAndCLI(unittest.TestCase):
    """Unit tests for report rendering and CLI invocations."""

    def test_format_text_report_rendering(self):
        stats = {
            "total_lines": 10,
            "parsed_lines": 8,
            "malformed_lines": 1,
            "blank_lines": 1,
            "earliest_timestamp": "2026-10-27 10:00:00",
            "latest_timestamp": "2026-10-27 11:00:00",
            "level_counts": {
                "DEBUG": 0,
                "INFO": 5,
                "WARNING": 1,
                "ERROR": 2,
                "CRITICAL": 0,
            },
            "level_percentages": {
                "DEBUG": 0.0,
                "INFO": 62.5,
                "WARNING": 12.5,
                "ERROR": 25.0,
                "CRITICAL": 0.0,
            },
            "frequent_errors": [
                {"message": "Connection reset by peer", "count": 2}
            ],
        }
        report = format_text_report(stats, source_name="test.log")
        self.assertIn("LOG ANALYSIS REPORT", report)
        self.assertIn("Source File: test.log", report)
        self.assertIn("Total lines:               10", report)
        self.assertIn("Parsed lines:               8", report)
        self.assertIn("INFO      :        5 ( 62.50%)", report)
        self.assertIn("1. [2x] Connection reset by peer", report)

    def test_format_text_report_empty_state(self):
        stats = {
            "total_lines": 0,
            "parsed_lines": 0,
            "malformed_lines": 0,
            "blank_lines": 0,
            "earliest_timestamp": None,
            "latest_timestamp": None,
            "level_counts": {lvl: 0 for lvl in VALID_LEVELS},
            "level_percentages": {lvl: 0.0 for lvl in VALID_LEVELS},
            "frequent_errors": [],
        }
        report = format_text_report(stats, source_name="empty.log")
        self.assertIn("Earliest:          N/A", report)
        self.assertIn("Latest:            N/A", report)
        self.assertIn("No ERROR or CRITICAL messages recorded.", report)

    def test_cli_success_human_readable(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write("2026-10-27 10:00:00 ERROR Server boot failed\n")
            temp_path = tf.name

        try:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                code = main([temp_path])
                self.assertEqual(code, 0)
                output = mock_stdout.getvalue()
                self.assertIn("LOG ANALYSIS REPORT", output)
                self.assertIn("Server boot failed", output or "")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_cli_json_output(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write("2026-10-27 10:00:00 ERROR DB Timeout\n")
            temp_path = tf.name

        try:
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                code = main([temp_path, "--format", "json"])
                self.assertEqual(code, 0)
                output = mock_stdout.getvalue()
                # Must be 100% valid JSON
                data = json.loads(output)
                self.assertEqual(data["parsed_lines"], 1)
                self.assertEqual(data["level_counts"]["ERROR"], 1)
                self.assertEqual(data["frequent_errors"][0]["message"], "DB Timeout")
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_cli_output_to_file(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write("2026-10-27 10:00:00 INFO Hello\n")
            log_path = tf.name

        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "subdir" / "report.json"
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                code = main([log_path, "--format", "json", "--output", str(out_file)])
                self.assertEqual(code, 0)
                self.assertTrue(out_file.exists())
                # Verify written content is valid JSON
                content = json.loads(out_file.read_text(encoding="utf-8"))
                self.assertEqual(content["parsed_lines"], 1)

        Path(log_path).unlink(missing_ok=True)

    def test_cli_error_missing_file(self):
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            code = main(["non_existent_file.log"])
            self.assertEqual(code, 1)
            self.assertIn("Error: Log file does not exist", mock_stderr.getvalue())

    def test_cli_error_negative_top(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write("2026-10-27 10:00:00 INFO Hello\n")
            log_path = tf.name

        try:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                code = main([log_path, "--top", "-3"])
                self.assertEqual(code, 1)
                self.assertIn(
                    "Error: --top must be a non-negative integer.",
                    mock_stderr.getvalue(),
                )
        finally:
            Path(log_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
