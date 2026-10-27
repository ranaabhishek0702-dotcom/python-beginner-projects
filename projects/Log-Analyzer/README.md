# Log Analyzer

A lightweight, robust command-line tool built with Python's standard library to inspect, parse, and summarize application and system log files. It aggregates event counts across standard log severity levels, extracts timestamp boundaries, identifies frequent error patterns, and exports results as formatted terminal text or structured JSON.

---

## Features

- **Standard Library Only**: Requires no external dependencies or third-party packages.
- **Incremental Streaming**: Processes log files line-by-line using generators, minimizing memory consumption even on large files.
- **Strict Timestamp Validation**: Verifies date and time validity using standard-library `datetime` facilities (detects invalid leap days, non-existent calendar dates, out-of-range hours/minutes/seconds).
- **Severity Breakdown**: Categorizes entries across standard levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`), reporting counts and percentage distributions.
- **Error Frequency Ranking**: Identifies and counts the most frequent `ERROR` and `CRITICAL` messages to pinpoint application issues.
- **Dual Output Formats**: Supports clean, aligned terminal summaries or machine-readable JSON for integration into automation pipelines.
- **Flexible File Output**: Writes analysis reports directly to a specified destination file, creating parent directories when needed.
- **Transparent Accounting**: Distinguishes parsed entries, malformed records, and blank lines without silently discarding data.
- **Graceful Error Handling**: Translates missing files, permission issues, directory targets, and UTF-8 decode errors into clear user diagnostics without exposing stack traces.

---

## Prerequisites

- **Python Version**: Python 3.8 or newer.
- **Operating System**: Cross-platform (Linux, macOS, Windows).
- **Dependencies**: None (pure Python standard library).

---

## Installation & Setup

1. Clone or navigate to your local copy of the repository:
   ```bash
   git clone https://github.com/Mrinank-Bhowmick/python-beginner-projects.git
   cd python-beginner-projects
   ```

2. Switch to the project directory:
   ```bash
   cd projects/Log-Analyzer
   ```

3. Verify your Python version:
   ```bash
   python3 --version
   ```

No virtual environment or `pip install` step is required.

---

## Expected Log Format

The analyzer parses standard log records matching the format:

```text
YYYY-MM-DD HH:MM:SS LEVEL Message
```

### Components

- `YYYY-MM-DD`: 4-digit year, 2-digit month, 2-digit day.
- `HH:MM:SS`: 2-digit hour (00–23), 2-digit minute (00–59), 2-digit second (00–59).
- `LEVEL`: One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (uppercase).
- `Message`: Free-form message text (may contain spaces, punctuation, numbers, or special symbols).

### Sample Log File (`sample.log`)

```text
2026-10-27 08:15:20 INFO System initialized successfully
2026-10-27 08:16:05 DEBUG Configuration loaded from /etc/app.conf
2026-10-27 08:20:11 WARNING Memory usage above 75%
2026-10-27 08:22:45 ERROR Database connection failed: timeout after 30s
2026-10-27 08:23:10 ERROR Database connection failed: timeout after 30s
2026-10-27 08:25:00 INFO Retrying database connection
2026-10-27 08:25:05 ERROR Database connection failed: timeout after 30s
2026-10-27 08:28:30 CRITICAL Out of disk space on /var/log
2026-10-27 08:30:00 WARNING High latency detected in worker pool
2026-10-27 08:35:12 INFO Scheduled health check passed
```

---

## Usage

### 1. Basic Analysis (Human-Readable Summary)

Run the analyzer with the target log file:

```bash
python3 main.py sample.log
```

### 2. Custom Top-N Error Ranking

Display the top N most frequent `ERROR` and `CRITICAL` messages (default is 5):

```bash
python3 main.py sample.log --top 10
```

### 3. JSON Output Mode

Emit raw, machine-readable JSON to standard output:

```bash
python3 main.py sample.log --format json
```

### 4. Save Report to File

Write the analysis report to a destination file:

```bash
# Save human-readable text report
python3 main.py sample.log --output report.txt

# Save JSON report
python3 main.py sample.log --output report.json --format json
```

---

## Command-Line Options

```text
usage: log-analyzer [-h] [--top N] [--format {text,json}] [-o FILE] log_file

positional arguments:
  log_file              Path to the log file to analyze.

options:
  -h, --help            Show this help message and exit.
  --top N               Number of most frequent ERROR and CRITICAL messages to
                        display (default: 5).
  --format {text,json}  Output format: 'text' (human-readable) or 'json'
                        (default: text).
  -o, --output FILE     Optional destination file path to save the generated
                        report.
```

---

## Example Output

### Human-Readable Output

```text
============================================================
LOG ANALYSIS REPORT
============================================================
Source File: sample.log

Line Overview:
  Total lines:               10
  Parsed lines:              10
  Malformed lines:            0
  Blank lines:                0

Time Range:
  Earliest:          2026-10-27 08:15:20
  Latest:            2026-10-27 08:35:12

Log Level Breakdown:
  DEBUG     :        1 ( 10.00%)
  INFO      :        3 ( 30.00%)
  WARNING   :        2 ( 20.00%)
  ERROR     :        3 ( 30.00%)
  CRITICAL  :        1 ( 10.00%)

Top 2 Frequent Errors (ERROR / CRITICAL):
  1. [3x] Database connection failed: timeout after 30s
  2. [1x] Out of disk space on /var/log
============================================================
```

### JSON Output

```json
{
  "total_lines": 10,
  "parsed_lines": 10,
  "malformed_lines": 0,
  "blank_lines": 0,
  "earliest_timestamp": "2026-10-27 08:15:20",
  "latest_timestamp": "2026-10-27 08:35:12",
  "level_counts": {
    "DEBUG": 1,
    "INFO": 3,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 1
  },
  "level_percentages": {
    "DEBUG": 10.0,
    "INFO": 30.0,
    "WARNING": 20.0,
    "ERROR": 30.0,
    "CRITICAL": 10.0
  },
  "frequent_errors": [
    {
      "message": "Database connection failed: timeout after 30s",
      "count": 3
    },
    {
      "message": "Out of disk space on /var/log",
      "count": 1
    }
  ]
}
```

---

## Line Accounting & Parsing Behavior

The analyzer maintains a strict accounting invariant:

$$\text{total\_lines} = \text{parsed\_lines} + \text{malformed\_lines} + \text{blank\_lines}$$

- **`total_lines`**: Every physical line read from the log file.
- **`parsed_lines`**: Records that successfully conform to `YYYY-MM-DD HH:MM:SS LEVEL Message` with a valid calendar timestamp and a recognized log level.
- **`malformed_lines`**: Non-empty lines that fail format parsing, contain invalid calendar dates (e.g. `2026-02-30`), out-of-range times (e.g. `25:00:00`), or specify unrecognized log levels (e.g. `TRACE`, `UNKNOWN`, or lowercase `info`).
- **`blank_lines`**: Empty lines or lines consisting solely of whitespace. Separating blank lines prevents harmless padding from being reported as corrupted log entries.
- **`level_percentages`**: Proportions computed relative to `parsed_lines` (rounded to 2 decimal places). If no lines were parsed, all percentages default to `0.0`.
- **`frequent_errors`**: Aggregates occurrences of unique messages having `ERROR` or `CRITICAL` severity, sorted in descending order of frequency.

---

## Error Handling & Exit Codes

The tool does not dump Python tracebacks for expected operational errors:

| Scenario | Behavior | Exit Code |
| :--- | :--- | :---: |
| Successful execution | Report printed or saved | `0` |
| File does not exist | `Error: Log file does not exist: '<path>'` printed to `stderr` | `1` |
| Path is a directory | `Error: Path is a directory, not a file: '<path>'` printed to `stderr` | `1` |
| Permission denied | `Error: Permission denied reading '<path>'` printed to `stderr` | `1` |
| Non-UTF-8 encoding error | `Error: Failed to decode '<path>' as UTF-8` printed to `stderr` | `1` |
| Negative `--top` value | `Error: --top must be a non-negative integer.` printed to `stderr` | `1` |
| Output file write error | `Error: Unable to write report to '<path>'` printed to `stderr` | `1` |
| Invalid CLI flags/syntax | Standard `argparse` usage message printed to `stderr` | `2` |

---

## Automated Tests

The project includes unit tests using Python's built-in `unittest` framework. Tests verify line parsing, calendar date validation, file access error handling, streaming invariants, and CLI argument parsing.

Run the tests from inside the project directory:

```bash
cd projects/Log-Analyzer
python3 -m unittest -v test_analyzer.py
```

Or from the repository root:

```bash
python3 -m unittest -v projects/Log-Analyzer/test_analyzer.py
```

---

## Project Structure

```text
projects/Log-Analyzer/
├── analyzer.py        # Core analysis logic, line parsing, streaming, and domain exceptions
├── main.py            # CLI entry point, argument parsing, report formatting, file output
├── test_analyzer.py   # Comprehensive automated unit test suite (built-in unittest)
└── README.md          # Project documentation, usage guide, and specifications
```

---

## Limitations

1. **Fixed Format**: Tailored for `YYYY-MM-DD HH:MM:SS LEVEL Message` logs. Log formats with brackets (e.g. `[INFO]`) or alternate date separators (`2026/10/27`) are treated as malformed lines.
2. **Single-line Log Records**: Multi-line stack traces following an exception are counted as malformed lines because they lack a leading timestamp and severity level.
3. **Local Text Files**: Designed for local UTF-8 encoded text files. Compressed archives (`.gz`), remote socket streams, or database logs should be unpacked or piped to text prior to analysis.
