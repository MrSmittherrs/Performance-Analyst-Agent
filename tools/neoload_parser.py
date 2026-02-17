"""
NeoLoad Results Parser: Parses NeoLoad CSV/XML export files into structured JSON.

Supports:
- NeoLoad statistics CSV (semicolon-separated by default)
- NeoLoad raw values CSV
- NeoLoad monitor/infrastructure CSV exports

Usage:
    python tools/neoload_parser.py <results_path> --project "Project Name" --date "2026-02-16"
    python tools/neoload_parser.py <results_path> --project "Project Name" --date "2026-02-16" --separator ";"
"""

import os
import sys
import json
import csv
import glob
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path for .env loading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv


# NeoLoad column name mappings (handles variations across NeoLoad versions)
TRANSACTION_COLUMN_ALIASES = {
    "element": ["element", "transaction", "name", "transaction name", "element name"],
    "user_path": ["user path", "userpath", "virtual user", "population"],
    "parent": ["parent", "parent element", "container"],
    "count": ["count", "executions", "iteration", "total"],
    "min": ["min", "minimum", "min response time", "min (ms)"],
    "avg": ["avg", "average", "mean", "avg response time", "avg (ms)"],
    "max": ["max", "maximum", "max response time", "max (ms)"],
    "perc_50": ["perc 50", "p50", "50th percentile", "median", "percentile 50"],
    "perc_90": ["perc 90", "p90", "90th percentile", "percentile 90"],
    "perc_95": ["perc 95", "p95", "95th percentile", "percentile 95"],
    "perc_99": ["perc 99", "p99", "99th percentile", "percentile 99"],
    "success": ["success", "passed", "success count"],
    "success_rate": ["success rate", "success rate (%)", "pass rate", "success %"],
    "failure": ["failure", "failed", "failure count", "errors"],
    "failure_rate": ["failure rate", "failure rate (%)", "fail rate", "error rate", "failure %"],
}

MONITOR_COLUMN_ALIASES = {
    "timestamp": ["timestamp", "time", "date", "datetime"],
    "host": ["host", "server", "machine", "hostname", "monitored machine"],
    "metric": ["metric", "counter", "monitor", "counter name"],
    "value": ["value", "avg", "average", "result"],
}


def detect_separator(file_path, candidates=[";", ",", "\t", "|"]):
    """Auto-detect CSV separator by checking which produces the most consistent column count."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        sample_lines = [f.readline() for _ in range(5)]
    sample_lines = [line for line in sample_lines if line.strip()]

    best_sep = ";"
    best_consistency = 0

    for sep in candidates:
        counts = [len(line.split(sep)) for line in sample_lines]
        if counts and counts[0] > 1:
            consistency = counts.count(counts[0])
            if consistency > best_consistency or (consistency == best_consistency and counts[0] > best_consistency):
                best_consistency = consistency
                best_sep = sep

    return best_sep


def normalize_column_name(col_name):
    """Normalize a column name for matching against aliases."""
    return col_name.strip().lower().replace("_", " ").replace("-", " ")


def map_columns(headers, alias_map):
    """Map detected CSV headers to standardized field names using alias matching."""
    mapping = {}
    normalized_headers = [normalize_column_name(h) for h in headers]

    for standard_name, aliases in alias_map.items():
        for i, norm_header in enumerate(normalized_headers):
            if norm_header in aliases:
                mapping[standard_name] = i
                break

    return mapping


def safe_float(value, default=0.0):
    """Safely convert a string to float."""
    if value is None:
        return default
    try:
        cleaned = str(value).strip().replace(",", ".").replace("%", "")
        return float(cleaned) if cleaned else default
    except (ValueError, TypeError):
        return default


def parse_transaction_csv(file_path, separator=None):
    """Parse a NeoLoad transaction statistics CSV file."""
    if separator is None:
        separator = detect_separator(file_path)

    transactions = []

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=separator)
        headers = next(reader)
        col_map = map_columns(headers, TRANSACTION_COLUMN_ALIASES)

        if "element" not in col_map and "avg" not in col_map:
            return None  # Not a transaction file

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue

            transaction = {}
            for field, idx in col_map.items():
                if idx < len(row):
                    if field in ("element", "user_path", "parent"):
                        transaction[field] = row[idx].strip()
                    else:
                        transaction[field] = safe_float(row[idx])

            if transaction.get("element"):
                transactions.append(transaction)

    return transactions


def parse_monitor_csv(file_path, separator=None):
    """Parse a NeoLoad monitor/infrastructure CSV file."""
    if separator is None:
        separator = detect_separator(file_path)

    monitors = []

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=separator)
        headers = next(reader)
        col_map = map_columns(headers, MONITOR_COLUMN_ALIASES)

        if "host" not in col_map and "metric" not in col_map:
            return None  # Not a monitor file

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue

            entry = {}
            for field, idx in col_map.items():
                if idx < len(row):
                    if field in ("host", "metric", "timestamp"):
                        entry[field] = row[idx].strip()
                    else:
                        entry[field] = safe_float(row[idx])

            if entry.get("host") or entry.get("metric"):
                monitors.append(entry)

    return monitors


def parse_raw_values_csv(file_path, separator=None):
    """Parse NeoLoad raw values CSV (individual request timings)."""
    if separator is None:
        separator = detect_separator(file_path)

    raw_values = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=separator)
        headers = next(reader)
        normalized = [normalize_column_name(h) for h in headers]

        # Raw values typically have: timestamp, element, response time, status
        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue
            entry = {headers[i]: row[i].strip() for i in range(min(len(headers), len(row)))}
            raw_values.append(entry)

    return raw_values if raw_values else None


def discover_files(results_path):
    """Discover NeoLoad export files in the given directory."""
    results_path = Path(results_path)
    discovered = {
        "transaction_files": [],
        "monitor_files": [],
        "raw_files": [],
        "other_files": [],
    }

    if results_path.is_file():
        search_patterns = [str(results_path)]
    else:
        search_patterns = [
            str(results_path / "**" / "*.csv"),
            str(results_path / "**" / "*.CSV"),
            str(results_path / "*.csv"),
        ]

    csv_files = set()
    for pattern in search_patterns:
        csv_files.update(glob.glob(pattern, recursive=True))

    for file_path in sorted(csv_files):
        fname = os.path.basename(file_path).lower()
        if any(kw in fname for kw in ["monitor", "infra", "counter", "server", "resource"]):
            discovered["monitor_files"].append(file_path)
        elif any(kw in fname for kw in ["raw", "detail", "values", "request"]):
            discovered["raw_files"].append(file_path)
        elif any(kw in fname for kw in ["stat", "transaction", "result", "summary", "action", "page"]):
            discovered["transaction_files"].append(file_path)
        else:
            discovered["other_files"].append(file_path)

    return discovered


def parse_all(results_path, separator=None):
    """Parse all NeoLoad result files found in the given path."""
    discovered = discover_files(results_path)
    parsed = {
        "transactions": [],
        "monitors": [],
        "raw_values": [],
        "files_processed": [],
        "files_skipped": [],
    }

    # Parse transaction files
    for fpath in discovered["transaction_files"]:
        result = parse_transaction_csv(fpath, separator)
        if result:
            parsed["transactions"].extend(result)
            parsed["files_processed"].append({"file": fpath, "type": "transactions", "records": len(result)})
        else:
            parsed["files_skipped"].append({"file": fpath, "reason": "Unrecognized transaction format"})

    # Parse monitor files
    for fpath in discovered["monitor_files"]:
        result = parse_monitor_csv(fpath, separator)
        if result:
            parsed["monitors"].extend(result)
            parsed["files_processed"].append({"file": fpath, "type": "monitors", "records": len(result)})
        else:
            parsed["files_skipped"].append({"file": fpath, "reason": "Unrecognized monitor format"})

    # Try unclassified files as either transaction or monitor data
    for fpath in discovered["other_files"] + discovered["raw_files"]:
        result = parse_transaction_csv(fpath, separator)
        if result:
            parsed["transactions"].extend(result)
            parsed["files_processed"].append({"file": fpath, "type": "transactions", "records": len(result)})
            continue

        result = parse_monitor_csv(fpath, separator)
        if result:
            parsed["monitors"].extend(result)
            parsed["files_processed"].append({"file": fpath, "type": "monitors", "records": len(result)})
            continue

        parsed["files_skipped"].append({"file": fpath, "reason": "Could not determine format"})

    return parsed


def build_output(parsed_data, project_name, test_date, source_path):
    """Build the structured output JSON."""
    transactions = parsed_data["transactions"]

    # Compute aggregate metrics
    total_transactions = sum(t.get("count", 0) for t in transactions)
    total_success = sum(t.get("success", 0) for t in transactions)
    total_failure = sum(t.get("failure", 0) for t in transactions)
    overall_error_rate = (total_failure / total_transactions * 100) if total_transactions > 0 else 0

    avg_response_times = [t["avg"] for t in transactions if t.get("avg", 0) > 0]
    p95_values = [t["perc_95"] for t in transactions if t.get("perc_95", 0) > 0]
    max_values = [t["max"] for t in transactions if t.get("max", 0) > 0]

    # Build monitor summary (group by host)
    monitor_summary = {}
    for entry in parsed_data["monitors"]:
        host = entry.get("host", "Unknown")
        metric = entry.get("metric", "Unknown")
        value = entry.get("value", 0)
        if host not in monitor_summary:
            monitor_summary[host] = {}
        if metric not in monitor_summary[host]:
            monitor_summary[host][metric] = {"values": [], "avg": 0, "max": 0}
        monitor_summary[host][metric]["values"].append(value)

    # Compute monitor averages and maximums
    for host in monitor_summary:
        for metric in monitor_summary[host]:
            values = monitor_summary[host][metric]["values"]
            monitor_summary[host][metric]["avg"] = round(sum(values) / len(values), 2) if values else 0
            monitor_summary[host][metric]["max"] = round(max(values), 2) if values else 0
            del monitor_summary[host][metric]["values"]  # Remove raw values to save space

    output = {
        "project_name": project_name,
        "test_date": test_date,
        "parsed_at": datetime.now().isoformat(),
        "source_path": str(source_path),
        "summary": {
            "total_transaction_types": len(transactions),
            "total_executions": total_transactions,
            "total_success": total_success,
            "total_failure": total_failure,
            "overall_error_rate": round(overall_error_rate, 2),
            "avg_response_time": round(sum(avg_response_times) / len(avg_response_times), 2) if avg_response_times else 0,
            "max_response_time": round(max(max_values), 2) if max_values else 0,
            "p95_response_time": round(max(p95_values), 2) if p95_values else 0,
        },
        "transactions": sorted(transactions, key=lambda t: t.get("avg", 0), reverse=True),
        "infrastructure": monitor_summary,
        "files_processed": parsed_data["files_processed"],
        "files_skipped": parsed_data["files_skipped"],
    }

    return output


def main():
    parser = argparse.ArgumentParser(description="Parse NeoLoad performance test results")
    parser.add_argument("results_path", help="Path to NeoLoad results directory or CSV file")
    parser.add_argument("--project", required=True, help="Project/application name")
    parser.add_argument("--date", required=True, help="Test execution date (YYYY-MM-DD)")
    parser.add_argument("--separator", default=None, help="CSV separator (auto-detected if not specified)")
    parser.add_argument("--output-dir", default=".tmp", help="Output directory (default: .tmp)")
    args = parser.parse_args()

    load_dotenv()

    results_path = Path(args.results_path)
    if not results_path.exists():
        print(f"Error: Results path not found: {results_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing NeoLoad results from: {results_path}")
    print(f"Project: {args.project}")
    print(f"Test date: {args.date}")

    # Parse all files
    parsed_data = parse_all(results_path, args.separator)

    if not parsed_data["transactions"] and not parsed_data["monitors"]:
        print("Error: No parseable NeoLoad data found in the specified path.", file=sys.stderr)
        if parsed_data["files_skipped"]:
            print(f"Skipped files: {len(parsed_data['files_skipped'])}")
            for skipped in parsed_data["files_skipped"]:
                print(f"  - {skipped['file']}: {skipped['reason']}")
        sys.exit(1)

    # Build structured output
    output = build_output(parsed_data, args.project, args.date, results_path)

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"neoload_parsed_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Update manifest
    manifest_file = output_dir / "performance_latest.json"
    manifest = {}
    if manifest_file.exists():
        with open(manifest_file, "r") as f:
            manifest = json.load(f)

    manifest.update({
        "project_name": args.project,
        "test_date": args.date,
        "created_at": datetime.now().isoformat(),
        "latest_parsed": {
            "parsed_file": str(output_file),
            "source_path": str(results_path),
            "transaction_count": len(output["transactions"]),
            "total_records": output["summary"]["total_executions"],
        }
    })

    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print(f"\nParsing complete:")
    print(f"  Transaction types: {len(output['transactions'])}")
    print(f"  Total executions: {output['summary']['total_executions']}")
    print(f"  Infrastructure hosts: {len(output['infrastructure'])}")
    print(f"  Files processed: {len(output['files_processed'])}")
    print(f"  Files skipped: {len(output['files_skipped'])}")
    print(f"  Output: {output_file}")
    print(f"  Manifest: {manifest_file}")

    return {"status": "success", "data": {"output_file": str(output_file), "summary": output["summary"]}}


if __name__ == "__main__":
    result = main()
    if result["status"] == "success":
        sys.exit(0)
    else:
        sys.exit(1)
