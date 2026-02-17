"""
NeoLoad HTML Report Parser: Parses NeoLoad HTML summary reports into structured JSON.

Supports NeoLoad's generated HTML reports (summary/index_files/*.html) and produces
the same JSON schema as neoload_parser.py for compatibility with performance_analyzer.py.

Usage:
    python tools/neoload_html_parser.py <html_dir> --project "Project Name" --date "2025-10-13"
    python tools/neoload_html_parser.py <html_dir> --project "UJ" --date "2025-10-13" --label "No background"
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TableParser(HTMLParser):
    """Extract table data from NeoLoad HTML reports."""

    def __init__(self):
        super().__init__()
        self.tables = []
        self._current_table = None
        self._current_row = None
        self._current_cell = None
        self._in_cell = False
        self._in_div = False
        self._div_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "table":
            self._current_table = {"class": attrs_dict.get("class", ""), "rows": []}
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []
        elif tag in ("td", "th") and self._current_row is not None:
            self._current_cell = ""
            self._in_cell = True
        elif tag == "div" and self._in_cell:
            self._in_div = True
            self._div_text = ""

    def handle_endtag(self, tag):
        if tag == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            self._current_table["rows"].append(self._current_row)
            self._current_row = None
        elif tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            if self._current_row is not None:
                text = self._current_cell.strip()
                text = re.sub(r'\s+', ' ', text)
                self._current_row.append(text)
            self._current_cell = None
        elif tag == "div" and self._in_div:
            self._in_div = False
            if self._in_cell and self._current_cell is not None:
                self._current_cell += self._div_text

    def handle_data(self, data):
        if self._in_div and self._in_cell:
            self._div_text += data
        elif self._in_cell and self._current_cell is not None:
            self._current_cell += data


def safe_float(value, default=0.0):
    """Safely convert a string to float, handling commas as thousands separators."""
    if not value or value.strip() in ("-", ""):
        return default
    try:
        cleaned = value.strip().replace(",", "").replace("%", "").replace("\xa0", "")
        return float(cleaned) if cleaned else default
    except (ValueError, TypeError):
        return default


def parse_summary_html(html_content):
    """Parse summary.html to extract test metadata and overall statistics."""
    parser = TableParser()
    parser.feed(html_content)

    result = {
        "name": "",
        "project": "",
        "scenario": "",
        "status": "Unknown",
        "start_date": "",
        "end_date": "",
        "duration": "",
        "load_policy": "",
        "lg_hosts": "",
        "statistics": {},
        "general_stats": {},
        "transaction_stats": {},
        "errors": [],
        "alerts": [],
        "hotspots": {},
    }

    for table in parser.tables:
        table_class = table.get("class", "")

        # Results summary table
        if "simpleResultSummary" in table_class:
            for row in table["rows"]:
                for i, cell in enumerate(row):
                    if cell == "Name" and i + 1 < len(row):
                        result["name"] = row[i + 1]
                    elif cell == "Project" and i + 1 < len(row):
                        result["project"] = row[i + 1]
                    elif cell == "Scenario" and i + 1 < len(row):
                        result["scenario"] = row[i + 1]
                    elif cell == "Start date" and i + 1 < len(row):
                        result["start_date"] = row[i + 1]
                    elif cell == "End date" and i + 1 < len(row):
                        result["end_date"] = row[i + 1]
                    elif cell == "Duration" and i + 1 < len(row):
                        result["duration"] = row[i + 1]
                    elif cell == "LG Hosts" and i + 1 < len(row):
                        result["lg_hosts"] = row[i + 1]
                    elif cell == "Status" and i + 1 < len(row):
                        status_text = row[i + 1]
                        if "Passed" in status_text or "PASS" in status_text:
                            result["status"] = "Passed"
                        elif "Failed" in status_text or "FAIL" in status_text:
                            result["status"] = "Failed"

        # Statistics summary table
        if "statistics_summary" in table_class:
            for row in table["rows"]:
                for i, cell in enumerate(row):
                    if "Total pages" in cell and i + 1 < len(row):
                        result["statistics"]["total_pages"] = safe_float(row[i + 1])
                    elif "Total requests" in cell and i + 1 < len(row):
                        result["statistics"]["total_requests"] = safe_float(row[i + 1])
                    elif "Total users launched" in cell and i + 1 < len(row):
                        result["statistics"]["total_users"] = safe_float(row[i + 1])
                    elif "Total iterations" in cell and i + 1 < len(row):
                        result["statistics"]["total_iterations"] = safe_float(row[i + 1])
                    elif "Total throughput" in cell and i + 1 < len(row):
                        result["statistics"]["total_throughput"] = row[i + 1].strip()
                    elif "Total request errors" in cell and i + 1 < len(row):
                        result["statistics"]["total_errors"] = safe_float(row[i + 1])
                    elif "Average pages/s" in cell and i + 1 < len(row):
                        result["statistics"]["avg_pages_per_sec"] = safe_float(row[i + 1])
                    elif "Average requests/s" in cell and i + 1 < len(row):
                        result["statistics"]["avg_requests_per_sec"] = safe_float(row[i + 1])
                    elif "Average Request response" in cell and i + 1 < len(row):
                        val = row[i + 1].replace("s", "").strip().replace("\xa0", "")
                        result["statistics"]["avg_request_response_time_s"] = safe_float(val)
                    elif "Average Page response" in cell and i + 1 < len(row):
                        val = row[i + 1].replace("s", "").strip().replace("\xa0", "")
                        result["statistics"]["avg_page_response_time_s"] = safe_float(val)
                    elif "Error rate" in cell and i + 1 < len(row):
                        result["statistics"]["error_rate_pct"] = safe_float(row[i + 1])
                    elif "Average throughput" in cell and i + 1 < len(row):
                        result["statistics"]["avg_throughput"] = row[i + 1].strip()

        # General statistics (All User Paths, All pages, All requests)
        if "all_statistics_content" in table_class:
            current_label = None
            headers = []
            for row in table["rows"]:
                if not row:
                    continue
                # Header row
                if row[0] in ("Min", ""):
                    headers = row
                    continue
                # Label row (single cell spanning columns)
                if len(row) == 1 or (len(row) >= 1 and any(kw in row[0] for kw in ["All User Paths", "All pages", "All requests", "All Transactions"])):
                    current_label = row[0].strip()
                    continue
                # Data row
                if current_label and len(row) >= 6:
                    stats = {
                        "min": safe_float(row[0]),
                        "avg": safe_float(row[1]),
                        "max": safe_float(row[2]),
                        "count": safe_float(row[3]),
                        "errors": safe_float(row[4]),
                        "error_pct": safe_float(row[5]),
                    }
                    # Transaction stats have extra percentile columns
                    if len(row) >= 11:
                        stats.update({
                            "perc_50": safe_float(row[6]),
                            "perc_95": safe_float(row[7]),
                            "perc_99": safe_float(row[8]),
                            "std_dev": safe_float(row[9]),
                            "avg_90": safe_float(row[10]),
                        })

                    if "Transaction" in current_label:
                        result["transaction_stats"] = stats
                    else:
                        result["general_stats"][current_label] = stats
                    current_label = None

        # Error table
        if "errors_summary" in table_class:
            for row in table["rows"]:
                if len(row) >= 3 and row[0] not in ("Error Type", "No errors", ""):
                    result["errors"].append({
                        "type": row[0],
                        "count": safe_float(row[1]),
                        "description": row[2],
                    })

        # Alerts table
        if "alerts_summary" in table_class and "top" not in table_class:
            for row in table["rows"]:
                if len(row) >= 4 and row[0] not in ("Element", ""):
                    result["alerts"].append({
                        "element": row[0],
                        "critical": safe_float(row[1]),
                        "warning": safe_float(row[2]),
                        "monitored": safe_float(row[3]),
                    })

    return result


def parse_transactions_html(html_content):
    """Parse transactions.html to extract per-transaction metrics."""
    parser = TableParser()
    parser.feed(html_content)

    transactions = []
    current_user_path = None

    for table in parser.tables:
        table_class = table.get("class", "")
        if "hierarchical" not in table_class or "shared" in table_class:
            continue

        for row in table["rows"]:
            if not row or len(row) < 7:
                continue

            # Skip header rows
            if row[0] in ("", "Min") or (len(row) > 1 and row[1] in ("Min",)):
                continue

            name = row[0].strip()
            if not name:
                continue

            # Skip Init/End/Actions containers
            if name in ("Init", "End", "Actions"):
                continue

            # Detect user path row (virtualuser class detected by high Min values or the pattern)
            min_val = safe_float(row[1])
            avg_val = safe_float(row[2])
            max_val = safe_float(row[3])
            count_val = safe_float(row[4])

            # User path rows have very high min/avg/max (iteration durations in seconds)
            # and typically no percentile data
            has_percentiles = len(row) >= 10 and row[7].strip() not in ("-", "")

            if not has_percentiles and min_val > 500:
                current_user_path = name
                continue

            # Transaction row
            txn = {
                "element": name,
                "user_path": current_user_path or "",
                "min": min_val,
                "avg": avg_val,
                "max": max_val,
                "count": count_val,
                "failure": safe_float(row[5]) if len(row) > 5 else 0,
                "failure_rate": safe_float(row[6]) if len(row) > 6 else 0,
            }

            if len(row) >= 12:
                txn["perc_50"] = safe_float(row[7])
                txn["perc_95"] = safe_float(row[8])
                txn["perc_99"] = safe_float(row[9])
                txn["std_dev"] = safe_float(row[10])

            # Calculate success from count - failure
            txn["success"] = txn["count"] - txn["failure"]
            txn["success_rate"] = round((txn["success"] / txn["count"] * 100), 1) if txn["count"] > 0 else 100

            transactions.append(txn)

    return transactions


def build_output(summary, transactions, project_name, test_date, source_path, label=None):
    """Build structured output JSON compatible with neoload_parser.py schema."""
    total_executions = sum(t.get("count", 0) for t in transactions)
    total_success = sum(t.get("success", 0) for t in transactions)
    total_failure = sum(t.get("failure", 0) for t in transactions)
    overall_error_rate = (total_failure / total_executions * 100) if total_executions > 0 else 0

    avg_response_times = [t["avg"] for t in transactions if t.get("avg", 0) > 0]
    p95_values = [t["perc_95"] for t in transactions if t.get("perc_95", 0) > 0]
    max_values = [t["max"] for t in transactions if t.get("max", 0) > 0]

    output = {
        "project_name": project_name,
        "test_date": test_date,
        "test_label": label or summary.get("name", ""),
        "parsed_at": datetime.now().isoformat(),
        "source_path": str(source_path),
        "source_format": "neoload_html",
        "test_metadata": {
            "name": summary.get("name", ""),
            "scenario": summary.get("scenario", ""),
            "status": summary.get("status", ""),
            "start_date": summary.get("start_date", ""),
            "end_date": summary.get("end_date", ""),
            "duration": summary.get("duration", ""),
            "lg_hosts": summary.get("lg_hosts", ""),
            "total_users": summary.get("statistics", {}).get("total_users", 0),
            "load_policy": summary.get("load_policy", ""),
        },
        "summary": {
            "total_transaction_types": len(transactions),
            "total_executions": total_executions,
            "total_success": total_success,
            "total_failure": total_failure,
            "overall_error_rate": round(overall_error_rate, 2),
            "avg_response_time": round(sum(avg_response_times) / len(avg_response_times), 2) if avg_response_times else 0,
            "max_response_time": round(max(max_values), 2) if max_values else 0,
            "p95_response_time": round(max(p95_values), 2) if p95_values else 0,
            "total_pages": summary.get("statistics", {}).get("total_pages", 0),
            "total_requests": summary.get("statistics", {}).get("total_requests", 0),
            "avg_pages_per_sec": summary.get("statistics", {}).get("avg_pages_per_sec", 0),
            "avg_requests_per_sec": summary.get("statistics", {}).get("avg_requests_per_sec", 0),
            "avg_page_response_time_s": summary.get("statistics", {}).get("avg_page_response_time_s", 0),
            "avg_request_response_time_s": summary.get("statistics", {}).get("avg_request_response_time_s", 0),
            "error_rate_pct": summary.get("statistics", {}).get("error_rate_pct", 0),
            "total_throughput": summary.get("statistics", {}).get("total_throughput", ""),
            "avg_throughput": summary.get("statistics", {}).get("avg_throughput", ""),
        },
        "transactions": sorted(transactions, key=lambda t: t.get("avg", 0), reverse=True),
        "infrastructure": {},
        "errors": summary.get("errors", []),
        "alerts": summary.get("alerts", []),
        "general_stats": summary.get("general_stats", {}),
        "transaction_stats": summary.get("transaction_stats", {}),
        "files_processed": [],
        "files_skipped": [],
    }

    return output


def main():
    parser = argparse.ArgumentParser(description="Parse NeoLoad HTML summary reports")
    parser.add_argument("html_dir", help="Path to directory containing HTML files (summary.html, transactions.html, etc.)")
    parser.add_argument("--project", required=True, help="Project/application name")
    parser.add_argument("--date", required=True, help="Test execution date (YYYY-MM-DD)")
    parser.add_argument("--label", default=None, help="Label for this test run (e.g., 'No background processes')")
    parser.add_argument("--output-dir", default=".tmp", help="Output directory (default: .tmp)")
    parser.add_argument("--output-file", default=None, help="Specific output filename (without directory)")
    args = parser.parse_args()

    html_dir = Path(args.html_dir)
    if not html_dir.exists():
        print(f"Error: HTML directory not found: {html_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing NeoLoad HTML reports from: {html_dir}")
    print(f"Project: {args.project}, Date: {args.date}")

    # Parse summary
    summary_file = html_dir / "summary.html"
    if summary_file.exists():
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = parse_summary_html(f.read())
        print(f"  Parsed summary: {summary['name']}")
    else:
        print("Warning: summary.html not found", file=sys.stderr)
        summary = {}

    # Parse transactions
    txn_file = html_dir / "transactions.html"
    if txn_file.exists():
        with open(txn_file, "r", encoding="utf-8") as f:
            transactions = parse_transactions_html(f.read())
        print(f"  Parsed {len(transactions)} transactions")
    else:
        print("Warning: transactions.html not found", file=sys.stderr)
        transactions = []

    if not transactions:
        print("Error: No transaction data found.", file=sys.stderr)
        sys.exit(1)

    # Build output
    output = build_output(summary, transactions, args.project, args.date, html_dir, args.label)

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    if args.output_file:
        output_file = output_dir / args.output_file
    else:
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
            "source_path": str(html_dir),
            "transaction_count": len(output["transactions"]),
            "total_records": output["summary"]["total_executions"],
        }
    })

    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print(f"\nParsing complete:")
    print(f"  Test: {output['test_metadata']['name']}")
    print(f"  Scenario: {output['test_metadata']['scenario']}")
    print(f"  Duration: {output['test_metadata']['duration']}")
    print(f"  VUs: {output['test_metadata']['total_users']:.0f}")
    print(f"  Transaction types: {len(output['transactions'])}")
    print(f"  Total executions: {output['summary']['total_executions']:.0f}")
    print(f"  Error rate: {output['summary']['overall_error_rate']:.2f}%")
    print(f"  Output: {output_file}")

    return {"status": "success", "data": {"output_file": str(output_file), "summary": output["summary"]}}


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result["status"] == "success" else 1)
