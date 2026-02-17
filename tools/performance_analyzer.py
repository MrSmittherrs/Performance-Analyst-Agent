"""
Performance Analyzer: Analyzes parsed NeoLoad data to identify bottlenecks and generate insights.

Reads from the manifest at .tmp/performance_latest.json, processes the parsed data,
and outputs a structured insights JSON for the report generator.

Usage:
    python tools/performance_analyzer.py
    python tools/performance_analyzer.py --sla-response 3000 --sla-error 1.0
    python tools/performance_analyzer.py --parsed-file .tmp/neoload_parsed_20260216.json
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv


# Default SLA thresholds (can be overridden via CLI)
DEFAULT_SLA = {
    "response_time_95th_ms": 3000,  # 3 seconds
    "response_time_max_ms": 10000,  # 10 seconds
    "error_rate_percent": 1.0,      # 1%
}

# Severity thresholds for bottleneck classification
SEVERITY_THRESHOLDS = {
    "critical": {"response_time_factor": 3.0, "error_rate": 5.0},
    "high": {"response_time_factor": 2.0, "error_rate": 2.0},
    "medium": {"response_time_factor": 1.5, "error_rate": 1.0},
    "low": {"response_time_factor": 1.0, "error_rate": 0.5},
}


def load_parsed_data(parsed_file=None):
    """Load parsed NeoLoad data from file or manifest."""
    if parsed_file:
        with open(parsed_file, "r", encoding="utf-8") as f:
            return json.load(f)

    manifest_path = Path(".tmp/performance_latest.json")
    if not manifest_path.exists():
        raise FileNotFoundError("Manifest not found at .tmp/performance_latest.json. Run neoload_parser.py first.")

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    parsed_path = manifest.get("latest_parsed", {}).get("parsed_file")
    if not parsed_path or not Path(parsed_path).exists():
        raise FileNotFoundError(f"Parsed data file not found: {parsed_path}")

    with open(parsed_path, "r", encoding="utf-8") as f:
        return json.load(f)


def identify_bottlenecks(transactions, sla):
    """Identify transactions that are performance bottlenecks."""
    bottlenecks = []

    for txn in transactions:
        issues = []
        severity = "low"

        # Check 95th percentile against SLA
        p95 = txn.get("perc_95", 0)
        if p95 > sla["response_time_95th_ms"]:
            factor = p95 / sla["response_time_95th_ms"]
            issues.append({
                "type": "sla_breach_p95",
                "message": f"95th percentile ({p95:.0f}ms) exceeds SLA ({sla['response_time_95th_ms']}ms) by {factor:.1f}x",
                "actual": p95,
                "threshold": sla["response_time_95th_ms"],
            })
            if factor >= SEVERITY_THRESHOLDS["critical"]["response_time_factor"]:
                severity = "critical"
            elif factor >= SEVERITY_THRESHOLDS["high"]["response_time_factor"]:
                severity = "high"
            elif factor >= SEVERITY_THRESHOLDS["medium"]["response_time_factor"]:
                severity = "medium"

        # Check max response time
        max_rt = txn.get("max", 0)
        if max_rt > sla["response_time_max_ms"]:
            issues.append({
                "type": "sla_breach_max",
                "message": f"Max response time ({max_rt:.0f}ms) exceeds threshold ({sla['response_time_max_ms']}ms)",
                "actual": max_rt,
                "threshold": sla["response_time_max_ms"],
            })

        # Check error rate
        error_rate = txn.get("failure_rate", 0)
        if error_rate > sla["error_rate_percent"]:
            issues.append({
                "type": "high_error_rate",
                "message": f"Error rate ({error_rate:.1f}%) exceeds SLA ({sla['error_rate_percent']}%)",
                "actual": error_rate,
                "threshold": sla["error_rate_percent"],
            })
            if error_rate >= SEVERITY_THRESHOLDS["critical"]["error_rate"]:
                severity = "critical"
            elif error_rate >= SEVERITY_THRESHOLDS["high"]["error_rate"] and severity != "critical":
                severity = "high"

        # Check response time variance (max/avg ratio indicates instability)
        avg_rt = txn.get("avg", 0)
        if avg_rt > 0 and max_rt > 0:
            variance_ratio = max_rt / avg_rt
            if variance_ratio > 10:
                issues.append({
                    "type": "high_variance",
                    "message": f"Response time highly unstable (max/avg ratio: {variance_ratio:.1f}x)",
                    "actual": variance_ratio,
                    "threshold": 10,
                })

        if issues:
            bottlenecks.append({
                "transaction": txn.get("element", "Unknown"),
                "user_path": txn.get("user_path", ""),
                "severity": severity,
                "issues": issues,
                "metrics": {
                    "avg": txn.get("avg", 0),
                    "p95": txn.get("perc_95", 0),
                    "max": txn.get("max", 0),
                    "count": txn.get("count", 0),
                    "error_rate": txn.get("failure_rate", 0),
                },
            })

    # Sort by severity (critical first) then by p95 descending
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    bottlenecks.sort(key=lambda b: (severity_order.get(b["severity"], 4), -b["metrics"]["p95"]))

    return bottlenecks


def analyze_sla_compliance(transactions, sla):
    """Assess overall SLA compliance."""
    total = len(transactions)
    if total == 0:
        return {"compliant": True, "compliance_rate": 100, "violations": []}

    violations = []
    for txn in transactions:
        p95 = txn.get("perc_95", 0)
        error_rate = txn.get("failure_rate", 0)
        if p95 > sla["response_time_95th_ms"] or error_rate > sla["error_rate_percent"]:
            violations.append({
                "transaction": txn.get("element", "Unknown"),
                "p95": p95,
                "error_rate": error_rate,
            })

    compliance_rate = round((1 - len(violations) / total) * 100, 1) if total > 0 else 100

    return {
        "compliant": len(violations) == 0,
        "compliance_rate": compliance_rate,
        "total_transactions": total,
        "passing": total - len(violations),
        "failing": len(violations),
        "violations": violations,
        "sla_thresholds": sla,
    }


def analyze_transactions(transactions):
    """Produce per-transaction analysis rankings."""
    if not transactions:
        return {}

    # Top slowest by average
    slowest_avg = sorted(transactions, key=lambda t: t.get("avg", 0), reverse=True)[:10]

    # Top slowest by 95th percentile
    slowest_p95 = sorted(transactions, key=lambda t: t.get("perc_95", 0), reverse=True)[:10]

    # Highest error rates
    highest_errors = sorted(
        [t for t in transactions if t.get("failure_rate", 0) > 0],
        key=lambda t: t.get("failure_rate", 0),
        reverse=True,
    )[:10]

    # Most executed
    most_executed = sorted(transactions, key=lambda t: t.get("count", 0), reverse=True)[:10]

    return {
        "slowest_by_avg": [
            {"transaction": t.get("element"), "avg_ms": t.get("avg", 0), "count": t.get("count", 0)}
            for t in slowest_avg
        ],
        "slowest_by_p95": [
            {"transaction": t.get("element"), "p95_ms": t.get("perc_95", 0), "count": t.get("count", 0)}
            for t in slowest_p95
        ],
        "highest_error_rate": [
            {"transaction": t.get("element"), "error_rate": t.get("failure_rate", 0), "failures": t.get("failure", 0)}
            for t in highest_errors
        ],
        "most_executed": [
            {"transaction": t.get("element"), "count": t.get("count", 0), "avg_ms": t.get("avg", 0)}
            for t in most_executed
        ],
    }


def analyze_infrastructure(infrastructure):
    """Analyze infrastructure/monitor data for resource concerns."""
    if not infrastructure:
        return {"available": False, "hosts": []}

    host_analysis = []
    for host, metrics in infrastructure.items():
        host_info = {"host": host, "metrics": {}, "concerns": []}

        for metric_name, data in metrics.items():
            host_info["metrics"][metric_name] = {
                "avg": data.get("avg", 0),
                "max": data.get("max", 0),
            }

            # Flag high resource usage
            metric_lower = metric_name.lower()
            if "cpu" in metric_lower and data.get("max", 0) > 80:
                host_info["concerns"].append(f"High CPU usage: max {data['max']}%")
            elif "memory" in metric_lower and data.get("max", 0) > 85:
                host_info["concerns"].append(f"High memory usage: max {data['max']}%")
            elif "disk" in metric_lower and data.get("max", 0) > 90:
                host_info["concerns"].append(f"High disk usage: max {data['max']}%")

        host_analysis.append(host_info)

    return {
        "available": True,
        "host_count": len(host_analysis),
        "hosts": host_analysis,
        "hosts_with_concerns": [h["host"] for h in host_analysis if h["concerns"]],
    }


def generate_executive_summary(parsed_data, bottlenecks, sla_compliance, infrastructure):
    """Generate executive summary bullets."""
    summary = parsed_data.get("summary", {})
    bullets = []

    # Overall result
    if sla_compliance["compliant"]:
        bullets.append(f"All {sla_compliance['total_transactions']} transactions met SLA requirements.")
    else:
        bullets.append(
            f"{sla_compliance['failing']} of {sla_compliance['total_transactions']} transactions "
            f"violated SLA thresholds ({sla_compliance['compliance_rate']}% compliance rate)."
        )

    # Response time headline
    bullets.append(
        f"Overall 95th percentile response time: {summary.get('p95_response_time', 0):.0f}ms, "
        f"maximum: {summary.get('max_response_time', 0):.0f}ms."
    )

    # Error rate
    error_rate = summary.get("overall_error_rate", 0)
    if error_rate > 0:
        bullets.append(f"Overall error rate: {error_rate:.2f}% across {summary.get('total_executions', 0):,} total executions.")
    else:
        bullets.append(f"Zero errors recorded across {summary.get('total_executions', 0):,} total executions.")

    # Bottlenecks
    critical_count = sum(1 for b in bottlenecks if b["severity"] == "critical")
    high_count = sum(1 for b in bottlenecks if b["severity"] == "high")
    if critical_count > 0:
        bullets.append(f"{critical_count} critical bottleneck(s) identified requiring immediate attention.")
    if high_count > 0:
        bullets.append(f"{high_count} high-severity issue(s) detected that should be addressed before production.")

    # Top bottleneck
    if bottlenecks:
        top = bottlenecks[0]
        bullets.append(
            f"Primary bottleneck: '{top['transaction']}' with {top['metrics']['p95']:.0f}ms "
            f"at 95th percentile and {top['metrics']['error_rate']:.1f}% error rate."
        )

    # Infrastructure
    if infrastructure.get("available"):
        if infrastructure["hosts_with_concerns"]:
            bullets.append(
                f"Infrastructure concerns on {len(infrastructure['hosts_with_concerns'])} host(s): "
                f"{', '.join(infrastructure['hosts_with_concerns'])}."
            )
        else:
            bullets.append(f"Infrastructure metrics within acceptable limits across {infrastructure['host_count']} monitored host(s).")

    return bullets


def generate_recommendations(bottlenecks, sla_compliance, infrastructure):
    """Generate actionable recommendations based on analysis."""
    recommendations = []

    # Critical bottleneck recommendations
    critical_bottlenecks = [b for b in bottlenecks if b["severity"] == "critical"]
    if critical_bottlenecks:
        txn_names = ", ".join(b["transaction"] for b in critical_bottlenecks[:3])
        recommendations.append({
            "priority": "Critical",
            "title": "Address Critical Performance Bottlenecks",
            "description": f"Transactions [{txn_names}] have response times significantly exceeding SLA. "
                           f"Investigate database queries, API calls, and resource contention in these paths.",
        })

    # Error rate recommendations
    high_error_txns = [b for b in bottlenecks if any(i["type"] == "high_error_rate" for i in b["issues"])]
    if high_error_txns:
        recommendations.append({
            "priority": "High",
            "title": "Resolve High Error Rates",
            "description": f"{len(high_error_txns)} transaction(s) have error rates above the SLA threshold. "
                           f"Review application logs for exceptions, timeouts, and connection failures.",
        })

    # Response time variance
    high_variance = [b for b in bottlenecks if any(i["type"] == "high_variance" for i in b["issues"])]
    if high_variance:
        recommendations.append({
            "priority": "Medium",
            "title": "Investigate Response Time Instability",
            "description": f"{len(high_variance)} transaction(s) show highly variable response times. "
                           f"This may indicate garbage collection pauses, connection pool exhaustion, or intermittent resource contention.",
        })

    # Infrastructure recommendations
    if infrastructure.get("hosts_with_concerns"):
        recommendations.append({
            "priority": "High",
            "title": "Scale Infrastructure Resources",
            "description": f"Resource utilization concerns detected on {len(infrastructure['hosts_with_concerns'])} host(s). "
                           f"Consider scaling CPU/memory or optimizing application resource usage.",
        })

    # General recommendations
    if sla_compliance["compliance_rate"] < 100:
        recommendations.append({
            "priority": "Medium",
            "title": "Re-test After Optimizations",
            "description": "Schedule a follow-up performance test after addressing the identified bottlenecks "
                           "to verify improvements and confirm SLA compliance.",
        })

    if not bottlenecks:
        recommendations.append({
            "priority": "Low",
            "title": "Continue Monitoring",
            "description": "No significant bottlenecks detected. Continue monitoring performance in production "
                           "and establish baseline metrics for future regression testing.",
        })

    return recommendations


def main():
    parser = argparse.ArgumentParser(description="Analyze parsed NeoLoad performance data")
    parser.add_argument("--parsed-file", default=None, help="Path to parsed JSON file (reads from manifest if not specified)")
    parser.add_argument("--sla-response", type=float, default=None, help="SLA threshold for 95th percentile response time (ms)")
    parser.add_argument("--sla-error", type=float, default=None, help="SLA threshold for error rate (%%)")
    parser.add_argument("--sla-max-response", type=float, default=None, help="SLA threshold for max response time (ms)")
    parser.add_argument("--output-dir", default=".tmp", help="Output directory (default: .tmp)")
    args = parser.parse_args()

    load_dotenv()

    # Build SLA thresholds
    sla = DEFAULT_SLA.copy()
    if args.sla_response is not None:
        sla["response_time_95th_ms"] = args.sla_response
    if args.sla_error is not None:
        sla["error_rate_percent"] = args.sla_error
    if args.sla_max_response is not None:
        sla["response_time_max_ms"] = args.sla_max_response

    print(f"SLA Thresholds: P95 < {sla['response_time_95th_ms']}ms, Max < {sla['response_time_max_ms']}ms, Error Rate < {sla['error_rate_percent']}%")

    # Load data
    parsed_data = load_parsed_data(args.parsed_file)
    transactions = parsed_data.get("transactions", [])
    infrastructure_data = parsed_data.get("infrastructure", {})

    print(f"Analyzing {len(transactions)} transaction types...")

    # Run analyses
    bottlenecks = identify_bottlenecks(transactions, sla)
    sla_compliance = analyze_sla_compliance(transactions, sla)
    transaction_analysis = analyze_transactions(transactions)
    infrastructure = analyze_infrastructure(infrastructure_data)
    executive_summary = generate_executive_summary(parsed_data, bottlenecks, sla_compliance, infrastructure)
    recommendations = generate_recommendations(bottlenecks, sla_compliance, infrastructure)

    # Build output
    insights = {
        "project_name": parsed_data.get("project_name", "Unknown"),
        "test_date": parsed_data.get("test_date", "Unknown"),
        "analyzed_at": datetime.now().isoformat(),
        "sla_thresholds": sla,
        "executive_summary": executive_summary,
        "overall_metrics": parsed_data.get("summary", {}),
        "sla_compliance": sla_compliance,
        "bottlenecks": bottlenecks,
        "transaction_analysis": transaction_analysis,
        "infrastructure": infrastructure,
        "recommendations": recommendations,
    }

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"performance_insights_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)

    # Update manifest
    manifest_file = output_dir / "performance_latest.json"
    manifest = {}
    if manifest_file.exists():
        with open(manifest_file, "r") as f:
            manifest = json.load(f)

    manifest["latest_insights"] = {
        "insights_file": str(output_file),
        "bottleneck_count": len(bottlenecks),
        "sla_violations": sla_compliance["failing"],
        "compliance_rate": sla_compliance["compliance_rate"],
    }

    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print(f"\nAnalysis complete:")
    print(f"  SLA Compliance: {sla_compliance['compliance_rate']}%")
    print(f"  Bottlenecks found: {len(bottlenecks)}")
    critical = sum(1 for b in bottlenecks if b["severity"] == "critical")
    high = sum(1 for b in bottlenecks if b["severity"] == "high")
    medium = sum(1 for b in bottlenecks if b["severity"] == "medium")
    print(f"    Critical: {critical}, High: {high}, Medium: {medium}")
    print(f"  Recommendations: {len(recommendations)}")
    print(f"  Output: {output_file}")

    print("\nExecutive Summary:")
    for i, bullet in enumerate(executive_summary, 1):
        print(f"  {i}. {bullet}")

    return {"status": "success", "data": {"output_file": str(output_file), "bottlenecks": len(bottlenecks)}}


if __name__ == "__main__":
    result = main()
    if result["status"] == "success":
        sys.exit(0)
    else:
        sys.exit(1)
