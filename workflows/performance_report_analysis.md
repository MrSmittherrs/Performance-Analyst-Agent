# NeoLoad Performance Test Report Analysis

## Objective
Read NeoLoad performance test results from the user's Documents folder, analyze them for bottlenecks and performance issues using the load-testing-specialist agent, and generate a professional branded PDF closeout report using the canvas-design skill. The report follows the layout and design of the `Performance Closeout Report.pdf` reference document.

## Startup Prompt (Required Before Every Run)

Before doing anything else, ask the user:
> "Which NeoLoad project should I generate the report for?"

Use the answer to construct the results path:
```
C:\Users\ksmith2\Documents\NeoLoad Projects\{ProjectName}\results
```
Via MCP filesystem this maps to:
```
/documents/NeoLoad Projects/{ProjectName}/results
```
All subsequent steps use this path as the source of NeoLoad export files.

---

## Required Inputs

### Essential Inputs
- **NeoLoad Project Name**: Name of the project folder under `C:\Users\ksmith2\Documents\NeoLoad Projects\` — **always prompt the user for this at startup**
- **NeoLoad Results Path**: `C:\Users\ksmith2\Documents\NeoLoad Projects\{ProjectName}\results` (derived from project name, not manually entered)
- **Client/Project Name**: Full client and project name (e.g., "University of Johannesburg - Student Registration System")
- **Test Date**: Date the performance test was executed
- **Test Scenario Type**: Load Test, Stress Test, Spike Test, or Endurance Test

### Test Configuration Details
- **Test Duration**: Total runtime (e.g., "1 hour 1 minute")
- **Maximum Virtual Users**: Peak concurrent users (e.g., "250 VUs")
- **Ramp-up Strategy**: How users were added (e.g., "Start with 2 users, add 4 every 15 seconds")
- **Peak Load Timing**: When peak load was reached (e.g., "Peak at 15:30, 15 minutes into test")
- **User Journeys/Workflows**: List of user paths tested with descriptions

### Test Purpose & Objectives
- **Primary Objective**: Main goal of the performance test (e.g., "Validate system performance under stress conditions with 250 concurrent users")
- **Workflows Under Test**: Specific business workflows being validated (e.g., "Student Registration", "Course Application Submission")
- **Testing Tools**: NeoLoad version, load generator details, monitoring tools used

### Optional Inputs
- **SLA Thresholds**: Target response times, error rate limits, throughput requirements (defaults: P95 < 3000ms, Max < 10000ms, Error Rate < 1%)
- **Infrastructure Details**: Server specs, environment configuration
- **Known Issues**: Any environmental factors or constraints during testing

## Tools Used
1. `tools/neoload_parser.py` — Parses NeoLoad export files into structured JSON
2. `tools/performance_analyzer.py` — Analyzes parsed data, identifies bottlenecks, generates insights
3. **load-testing-specialist agent** — Provides expert-level analysis and recommendations
4. **canvas-design skill** — Creates the branded multi-page PDF report

## Process Steps

### Step 0: Update Test Metadata Configuration (Before Each Test)
**What to do**: Update `test_metadata_template.json` in the project root with the current test details.
**File**: `test_metadata_template.json` (single file, updated for each test)

**Required information to update**:
- **Test Metadata**: Client name, test date, scenario type, NeoLoad project/result IDs
- **Test Purpose**: Primary objective, business context, success criteria
- **Workflows Under Test**: User path descriptions and business criticality
- **Test Configuration**: Duration, VUs, ramp-up strategy, peak timing
- **Testing Tools**: NeoLoad version, load generators, monitoring tools
- **SLA Thresholds**: P95, Max response times, error rates (or use defaults)
- **Infrastructure**: Server details (optional)
- **Known Issues**: Environmental factors, constraints, anomalies (optional)
- **Document Control**: Version, status, author, reviewer, approver

**Why this matters**: The HTML parser extracts technical metrics from NeoLoad, but business context (client name, objectives, workflow descriptions) must be provided manually. This config file bridges that gap.

### Step 1: Locate and Parse NeoLoad Results
**What to do**: Find the NeoLoad result files and parse them into structured data.
**Tool**: `tools/neoload_parser.py`
**Command**: `python tools/neoload_parser.py "C:\Users\ksmith2\Documents\NeoLoad Projects\{ProjectName}\results" --project "Project Name" --date "2026-02-16"`
**Inputs**: Results path derived from the project name provided at startup, project name, test date
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
**Inputs**:
- Test metadata config (`test_metadata_template.json` in project root)
- Insights JSON (from manifest `.tmp/performance_latest.json`)
- Inspired Testing logo (`Inspired Testing Logo.png` in project root)
- Reference layout (`Performance Closeout Report.pdf`)

**How to execute**:
1. Read the test metadata config from `test_metadata_template.json`
2. Read the insights JSON from the path in `.tmp/performance_latest.json`
3. Read `Performance Closeout Report.pdf` to reference the layout and design
4. Invoke the canvas-design skill with combined data (metadata + insights) to create the multi-page PDF

**Brand Guidelines**:
- **Logo**: `Inspired Testing Logo.png` on every page (header area)
- **Primary accent**: Gold (#C2A269)
- **Secondary accent**: Charcoal (#2D2E31)
- **Background dark**: (#262626)
- **Typography**: Clean sans-serif (Helvetica/Arial family)
- **Footer**: "CONFIDENTIAL — Inspired Testing" + page number on every page

**Report Pages** (matching Performance Closeout Report layout):

**Page 1: Cover Page**
- Use EXACT layout from `Performance Closeout Report.pdf` in project root
- Update client/project name for each report
- Update test date to match the test execution date
- Dark background, Inspired Testing logo, gold/charcoal branding

**Page 2: Document Control**
- Version history table
- Reviewer information
- Approval signatures section
- Document metadata (creation date, version number, status)

**Page 3: Executive Summary**
- **Section 2.1 - Purpose**
  - Primary objective of the performance test
  - Workflows being tested (e.g., "Student Registration workflow", "Application Submission workflow")
  - Tools used for testing (e.g., "NeoLoad Enterprise 9.x", "Load Generator: localhost:7100")

- **Section 2.2 - The Approach**
  - Table listing all user journeys/user paths tested
  - Columns: User Journey Name, Description, Transaction Count
  - Example: "Student Registration - 2025", "Web Application - 2025"

- **Section 2.3 - Load Profiling**
  - Test scenario type (Load Test, Stress Test, Spike Test, Endurance Test)
  - Test configuration table with:
    - Test Duration (e.g., "1 hour 1 minute")
    - Maximum Virtual Users (e.g., "250 VUs")
    - Ramp-up Strategy (e.g., "Start with 2 users, add 4 every 15 seconds")
    - Peak Load Timing (e.g., "Peak reached at 15:30 after 15 minutes")
    - Load Profile Description

**Page 4: Performance Metrics Summary**
- High-level findings table: 95th percentile, max response time, avg response time, transaction count, error rate
- Overall system performance verdict

**Page 5-6: Detailed Test Results**
- Per-scenario/transaction breakdown with response time data
- Min, Avg, Max, P50, P90, P95, P99 percentiles
- Error counts and rates per transaction

**Page 7-8: Performance Graphs** (if time-series data available)
- Response time over test duration
- Throughput over test duration
- Error rate trends
- Virtual user ramp-up visualization

**Page 9: Infrastructure Monitoring** (if available)
- Server resource utilization (CPU, memory, network) per monitored host
- Correlation with performance bottlenecks

**Page 10: Challenges & Observations**
- Issues encountered during testing
- Environmental factors affecting results
- Data quality notes
- Any anomalies or unexpected behavior

**Page 11: Conclusion**
- Key findings summary
- SLA achievement status
- Bottleneck summary
- Recommendations
- Sign-off section

**Page 12: Appendix** (optional)
- Methodology details
- Test environment specifications
- Execution timeline
- Raw data summary tables

**Output path**: `C:\Users\ksmith2\OneDrive - Inspired Testing (Pty) Ltd\Documents\Neoload Reports\`
**File naming**: `{ClientName}_{MaxVUs}VU_{TestDuration}.pdf`
- `ClientName`: Shortened client name with no spaces (e.g., `UniversityOfJohannesburg`)
- `MaxVUs`: Peak virtual users (e.g., `250VU`)
- `TestDuration`: Duration in compact form (e.g., `1h01m`)
- Example: `UniversityOfJohannesburg_250VU_1h01m.pdf`

**Expected output**:
- `C:\Users\ksmith2\OneDrive - Inspired Testing (Pty) Ltd\Documents\Neoload Reports\{ClientName}_{MaxVUs}VU_{TestDuration}.pdf`
- Manifest updated with report file path
**Validation**: PDF exists at the output path, is > 50KB, opens correctly with all pages and branding.

### Step 4: Cleanup (Required)
**What to do**: Automatically remove all intermediate files from `.tmp/` after the PDF report is saved to the output folder.
**What to keep**: The final PDF report is saved to `C:\Users\ksmith2\OneDrive - Inspired Testing (Pty) Ltd\Documents\Neoload Reports\` — nothing needs to be kept in `.tmp/`
**What to delete**: ALL files in `.tmp/` — parsed JSON, insights JSON, manifest files, HTML files, analysis files, temporary scripts, build scripts, and any PDFs
**Command**: `cd .tmp && find . -type f -delete && find . -type d -empty -delete`
**Validation**: Confirm the PDF exists in the Documents output folder and `.tmp/` is empty
**Why**: The deliverable lives in Documents where the user can access it directly. `.tmp/` is purely for intermediate processing and should be fully cleared each run.

## Expected Outputs
- **Final Deliverable**: Branded PDF saved to `C:\Users\ksmith2\OneDrive - Inspired Testing (Pty) Ltd\Documents\Neoload Reports\{ClientName}_{MaxVUs}VU_{TestDuration}.pdf`
- **During Processing**: Parsed JSON, insights JSON, and manifest files are created in `.tmp/` but deleted after PDF generation
- **After Cleanup**: `.tmp/` folder is completely empty

## Edge Cases & Error Handling

### Case: NeoLoad Results Not Found
**Symptoms**: FileNotFoundError or empty directory at `C:\Users\ksmith2\Documents\NeoLoad Projects\{ProjectName}\results`
**Solution**: Verify the project name is spelled correctly (check against the actual folder names in `C:\Users\ksmith2\Documents\NeoLoad Projects\`). Confirm that NeoLoad exports have been completed and saved to the `results` subfolder.

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
    "report_file": "C:\\Users\\ksmith2\\OneDrive - Inspired Testing (Pty) Ltd\\Documents\\Neoload Reports\\ClientName_250VU_1h01m.pdf",
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
- [ ] PDF saved to `C:\Users\ksmith2\OneDrive - Inspired Testing (Pty) Ltd\Documents\Neoload Reports\` with correct `ClientName_MaxVUsVU_Duration.pdf` filename
- [ ] `.tmp/` folder is completely empty after cleanup

## Lessons Learned

### Report Structure Requirements (Feb 17, 2026)
**What we learned**: The PDF report must match the exact structure of the reference `Performance Closeout Report.pdf`:
- Cover page layout must be identical (just update client name and date)
- Document Control section is mandatory
- Executive Summary needs three distinct subsections:
  - 2.1 Purpose (objectives, workflows, tools)
  - 2.2 The Approach (user journeys table)
  - 2.3 Load Profiling (test scenario details, configuration)
- All test configuration details (duration, VUs, ramp-up, peak timing) must be extracted from NeoLoad HTML reports

**Why it matters**: Consistency across all client reports. The reference layout is proven and professional.

**How to implement**:
- The HTML parser (`tools/neoload_html_parser.py`) must extract test configuration from NeoLoad summary reports
- When invoking canvas-design skill, provide complete structured data including all test configuration details
- Always reference `Performance Closeout Report.pdf` as the layout template
