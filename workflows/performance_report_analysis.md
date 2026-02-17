# NeoLoad Performance Test Report Analysis

## Objective
Read NeoLoad performance test results from the user's Documents folder, analyze them for bottlenecks and performance issues using the load-testing-specialist agent, and generate a professional branded PDF closeout report using the canvas-design skill. The report follows the layout and design of the `Performance Closeout Report.pdf` reference document.

## Required Inputs
- **NeoLoad Results Path**: Directory containing NeoLoad export files (CSV/XML) — typically in `C:\Users\ksmith2\Documents\` or a subfolder
- **Project Name**: Name of the system/application under test (used in the report title)
- **Test Date**: Date the performance test was executed
- **SLA Thresholds** (optional): Target response times, error rate limits, throughput requirements

## Tools Used
1. `tools/neoload_parser.py` — Parses NeoLoad export files into structured JSON
2. `tools/performance_analyzer.py` — Analyzes parsed data, identifies bottlenecks, generates insights
3. **load-testing-specialist agent** — Provides expert-level analysis and recommendations
4. **canvas-design skill** — Creates the branded multi-page PDF report

## Process Steps

### Step 1: Locate and Parse NeoLoad Results
**What to do**: Find the NeoLoad result files and parse them into structured data.
**Tool**: `tools/neoload_parser.py`
**Command**: `python tools/neoload_parser.py <path_to_neoload_results> --project "Project Name" --date "2026-02-16"`
**Inputs**: Path to NeoLoad results directory, project name, test date
**Expected output**:
- `.tmp/neoload_parsed_{timestamp}.json` with structured metrics
- `.tmp/performance_latest.json` manifest created/updated
**Validation**: Check that the JSON contains transaction data with response times, throughput, and error counts.

**Supported NeoLoad export formats**:
- CSV transaction results (Actions, Pages, Requests)
- CSV monitor data (infrastructure metrics)
- XML result files
- JSON exports from NeoLoad Web

### Step 2: Analyze Performance Data
**What to do**: Process parsed data to identify bottlenecks, SLA violations, and patterns.
**Tool**: `tools/performance_analyzer.py`
**Command**: `python tools/performance_analyzer.py`
**Inputs**: Reads from manifest at `.tmp/performance_latest.json`
**Expected output**:
- `.tmp/performance_insights_{timestamp}.json` with analysis sections
- Manifest updated with insights file path
**Validation**: Check that insights JSON contains: executive_summary, bottlenecks, sla_compliance, transaction_analysis, infrastructure_metrics, recommendations.

**The load-testing-specialist agent should be invoked** to review the analysis output and add expert interpretation:
- Identify root causes behind bottlenecks
- Correlate infrastructure metrics with transaction performance
- Provide prioritized optimization recommendations
- Flag any concerning patterns that automated analysis might miss

### Step 3: Generate Branded PDF Report
**What to do**: Create a professional performance closeout report matching the reference PDF layout.
**Tool**: canvas-design skill (invoked via the skill)
**Inputs**: Insights JSON (from manifest), Inspired Testing logo (`Inspired Testing Logo.png` in project root), reference layout from `Performance Closeout Report.pdf`

**How to execute**:
1. Read the insights JSON from the path in `.tmp/performance_latest.json`
2. Read `Performance Closeout Report.pdf` to reference the layout and design
3. Invoke the canvas-design skill to create the multi-page PDF

**Brand Guidelines**:
- **Logo**: `Inspired Testing Logo.png` on every page (header area)
- **Primary accent**: Gold (#C2A269)
- **Secondary accent**: Charcoal (#2D2E31)
- **Background dark**: (#262626)
- **Typography**: Clean sans-serif (Helvetica/Arial family)
- **Footer**: "CONFIDENTIAL — Inspired Testing" + page number on every page

**Report Pages** (matching Performance Closeout Report layout):
1. **Cover Page** — Dark background, gold text, Inspired Testing logo, report title, project name, date
2. **Document Control** — Version history, reviewer, approval signatures table
3. **Executive Summary** — Purpose, approach, load profiling overview, key findings
4. **Performance Metrics Summary** — High-level findings table: 95th percentile, max response time, avg response time, transaction count, error rate
5. **Detailed Test Results** — Per-scenario/transaction breakdown with response time data
6. **Performance Graphs** — Time-series charts showing response times, throughput, errors over the test duration
7. **Infrastructure Monitoring** — Server resource utilization (CPU, memory, network) per monitored host
8. **Challenges & Observations** — Issues encountered, environmental factors, data quality notes
9. **Conclusion** — Key findings, SLA achievement, bottleneck summary, close-out comments
10. **Appendix** — Methodology, test environment details, execution timeline, raw data summary

**Expected output**:
- `.tmp/performance_report_{timestamp}.pdf`
- Manifest updated with report file path
**Validation**: PDF exists, is > 50KB, opens correctly with all pages and branding.

### Step 4: Cleanup (Optional)
**What to do**: Remove intermediate files from `.tmp/`.
**What to keep**: Latest PDF report and insights JSON
**What to delete**: Intermediate chart images, old parsed data files

## Expected Outputs
- **Primary**: Branded PDF closeout report in `.tmp/`
- **Secondary**: Parsed data JSON and insights JSON in `.tmp/` for reference
- **Manifest**: `.tmp/performance_latest.json` tracking all file paths

## Edge Cases & Error Handling

### Case: NeoLoad Results Not Found
**Symptoms**: FileNotFoundError or empty directory
**Solution**: Verify the path and check that NeoLoad exports were completed. Ask user to confirm the export directory.

### Case: Unrecognized NeoLoad Export Format
**Symptoms**: Parser fails to detect CSV columns or XML structure
**Solution**: The parser supports multiple NeoLoad versions. If format is unrecognized, log the detected columns and ask user which columns map to transaction name, response time, status, etc.

### Case: Missing Infrastructure/Monitor Data
**Symptoms**: No server metrics in the parsed data
**Solution**: Skip the Infrastructure Monitoring page in the report. Note in the report that monitoring data was unavailable.

### Case: Single Test Run vs Multiple Runs
**Symptoms**: Results directory contains data from multiple test executions
**Solution**: Parser groups by test run if timestamps differ significantly. Each run is analyzed separately and compared in the report.

### Case: No SLA Thresholds Provided
**Symptoms**: No targets to compare against
**Solution**: Use industry-standard defaults (e.g., 3s response time for web, 1% error rate) and note they are defaults, not project-specific SLAs.

## Manifest Structure
```json
{
  "project_name": "Project Name",
  "test_date": "2026-02-16",
  "created_at": "2026-02-16T14:30:00",
  "latest_parsed": {
    "parsed_file": ".tmp/neoload_parsed_20260216_143000.json",
    "source_path": "C:\\Users\\ksmith2\\Documents\\NeoLoad Results\\...",
    "transaction_count": 150,
    "total_records": 45000
  },
  "latest_insights": {
    "insights_file": ".tmp/performance_insights_20260216_143500.json",
    "bottleneck_count": 3,
    "sla_violations": 2
  },
  "latest_report": {
    "report_file": ".tmp/performance_report_20260216_144000.pdf",
    "page_count": 10,
    "file_size_kb": 2500
  }
}
```

## Success Criteria
- [ ] NeoLoad results parsed with all transactions and metrics extracted
- [ ] Analysis identifies bottlenecks with severity ranking
- [ ] PDF report has all 10 pages matching the reference layout
- [ ] Inspired Testing branding (logo, gold/charcoal colors) renders correctly
- [ ] Infrastructure metrics displayed per server (if available)
- [ ] Executive summary contains actionable findings
- [ ] Report file size < 25MB

## Lessons Learned
[This section grows over time as the system encounters and solves problems]
