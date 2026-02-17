# YouTube AI Niche Trend Analysis

## Objective
Collect YouTube data about AI and AI automation content, analyze engagement trends and content patterns, generate a professional branded PDF report using the canvas-design skill, and email it to the configured recipient. Designed to run weekly or monthly for ongoing insights.

## Required Inputs
- **YouTube API Key**: Set in `.env` as `YOUTUBE_API_KEY` (get from Google Cloud Console)
- **Search Queries**: Comma-separated list in `.env` as `YOUTUBE_SEARCH_QUERIES` (default: AI automation, AI agents, AI tools 2026, artificial intelligence trends, large language models, AI workflow)
- **Date Range**: Number of days to look back, set as `YOUTUBE_PUBLISHED_AFTER_DAYS` (default: 30)
- **Max Results Per Query**: Controls data volume and quota, set as `YOUTUBE_MAX_RESULTS_PER_QUERY` (default: 50)
- **Recipient Email**: Who receives the report, set as `GMAIL_RECIPIENT_EMAIL`
- **Google OAuth Credentials**: `credentials.json` in project root (from Google Cloud Console)

## Tools Used
1. `tools/youtube_collector.py` - Searches YouTube Data API v3, collects video and channel metrics
2. `tools/youtube_analyzer.py` - Analyzes collected data for trends, patterns, and insights
3. **canvas-design skill** - Creates a branded, multi-page PDF report with charts, tables, and visuals
4. `tools/gmail_sender.py` - Sends report via Gmail with .pdf attachment

## Process Steps

### Step 1: Collect YouTube Data
**What to do**: Run the YouTube collector to search for AI content and gather metrics.
**Tool**: `tools/youtube_collector.py`
**Command**: `python tools/youtube_collector.py`
**Inputs**: Search queries, max results, published-after days (all from .env or CLI overrides)
**Expected output**:
- `.tmp/youtube_videos_{timestamp}.csv` with video data and derived metrics
- `.tmp/youtube_channels_{timestamp}.csv` with channel statistics
- `.tmp/youtube_collection_metadata_{timestamp}.json` with run details
- `.tmp/youtube_latest.json` manifest updated
**Validation**: Check that `youtube_latest.json` exists and the tool reports > 0 videos collected.
**Quota note**: ~600 units per run with default settings (10,000 daily limit).

### Step 2: Analyze Data
**What to do**: Process collected data to identify trends, top performers, and patterns.
**Tool**: `tools/youtube_analyzer.py`
**Command**: `python tools/youtube_analyzer.py`
**Inputs**: Data directory (.tmp/) — reads from manifest automatically
**Expected output**:
- `.tmp/youtube_analysis_{timestamp}.json` with all trend data
- Manifest updated with analysis file path
**Validation**: Check that analysis JSON contains these sections: executive_summary, top_videos, top_channels, topic_distribution, view_velocity, content_patterns, trending_topics, recommendations.

### Step 3: Generate Branded PDF Report
**What to do**: Create a professional, aesthetically pleasing PDF report from the analysis results using the canvas-design skill. This replaces the previous PowerPoint generation step.
**Tool**: canvas-design skill (invoked via `/canvas-design`)
**Inputs**: Analysis JSON (found via manifest at `.tmp/youtube_latest.json`), Inspired Testing logo (`Inspired Testing Logo.png` in project root)

**How to execute**:
1. Read the analysis JSON from the path stored in `.tmp/youtube_latest.json` under `latest_analysis.analysis_file`
2. Read the analysis data to understand all sections: executive_summary, top_videos, top_channels, topic_distribution, view_velocity, content_patterns, trending_topics, recommendations
3. Invoke the canvas-design skill to create a multi-page branded PDF with the following specifications:

**Brand Guidelines**:
- **Logo**: Include `Inspired Testing Logo.png` from the project root on every page (header area, top-right or top-left)
- **Primary accent color**: Gold (#C2A269)
- **Secondary accent**: Charcoal (#2D2E31)
- **Text color**: Dark (#262626)
- **Typography**: Clean, modern sans-serif (Helvetica/Arial family)
- **Overall feel**: Professional but visually striking — clean layouts, good whitespace, modern data visualization

**Report Pages** (create as a cohesive, multi-page PDF):
1. **Cover Page** — Report title "AI YouTube Trend Analysis", date range, total videos analyzed, Inspired Testing logo prominently displayed, gold accent bar
2. **Executive Summary** — 5-7 key findings as styled bullet points with visual hierarchy
3. **Top Trending Videos** — Table showing top videos with views, engagement ratio, and views/day. Use alternating row colors for readability
4. **Top Channels** — Table showing top channels with subscriber count, average engagement, and average views
5. **Engagement Analysis** — Bar chart of top 15 videos by engagement ratio, using gold-themed color palette
6. **Topic Distribution** — Pie/donut chart showing video distribution across AI topic categories, with an accompanying engagement summary
7. **View Velocity Trends** — Line chart showing weekly average views-per-day momentum
8. **Content Patterns** — Visual summary of duration sweet spots, best publish days, top-performing keywords, and title insights
9. **Trending vs Declining Topics** — Two-column visual with upward/downward indicators showing which topics are gaining or losing traction
10. **Recommendations** — 6 actionable, data-driven content creation tips displayed as styled cards
11. **Appendix** — Methodology notes, metrics definitions, and data disclaimer

**Footer**: Include "CONFIDENTIAL — Inspired Testing" on each page with subtle styling

**Expected output**:
- `.tmp/youtube_trend_report_{timestamp}.pdf`
- After generating, update the manifest at `.tmp/youtube_latest.json` to set `latest_report.report_file` to the PDF path
**Validation**: Check .pdf exists and is > 10KB. Open to verify pages render correctly with branding.

### Step 4: Send Email
**What to do**: Email the PDF report to the configured recipient.
**Tool**: `tools/gmail_sender.py`
**Command**: `python tools/gmail_sender.py`
**Inputs**: Report path (from manifest), recipient email (from .env)
**Expected output**: Email sent confirmation with message ID
**Validation**: Check inbox for email with .pdf attachment. Verify attachment opens correctly.
**Note**: First run requires browser-based OAuth consent. Subsequent runs use saved token.

### Step 5: Cleanup (Optional)
**What to do**: Remove old temporary files from .tmp/ to save space.
**What to keep**: Latest .pdf, analysis JSON, and raw data CSVs (for historical comparison)
**What to delete**: `chart_*.png` files from previous runs

## Expected Outputs
- **Primary Output**: Email with .pdf attachment in recipient's inbox
- **Secondary Outputs**: Raw data CSVs and analysis JSON in `.tmp/` for reference
- **Temporary Files**: Any intermediate chart images (cleaned up after PDF generation)

## PDF Report Contents
1. Cover page with date range, stats, and Inspired Testing branding
2. Executive Summary (5-7 key findings)
3. Top Trending Videos (table with views, engagement, velocity)
4. Top Channels (table with subscribers, avg engagement)
5. Engagement Analysis (bar chart)
6. Topic Distribution (pie/donut chart + engagement summary)
7. View Velocity Trends (line chart)
8. Content Patterns (duration, publish day, keywords, title insights)
9. Trending vs Declining Topics (visual two-column layout)
10. Recommendations (6 data-driven content creation tips as styled cards)
11. Appendix (methodology, data sources, disclaimer)

## Edge Cases & Error Handling

### Case: YouTube API Quota Exceeded
**Symptoms**: HTTP 403 error with "quotaExceeded" reason
**Solution**: The collector handles this gracefully — it uses whatever data was gathered before the limit. If zero data was collected, it aborts with a clear error.
**Prevention**: Default settings use ~600 units per run. Don't run more than 16 times/day. Quota resets at midnight Pacific Time.

### Case: No Videos Found for a Query
**Symptoms**: Search returns zero results for one or more queries
**Solution**: The collector logs a warning and continues with other queries. If ALL queries return zero results, it aborts.
**Prevention**: Use broader search terms. Check that the date range isn't too narrow (e.g., 1 day might return very few results).

### Case: OAuth Token Expired
**Symptoms**: Authentication error when sending email via Gmail
**Solution**: Delete `token.json` and re-run. Browser will open for re-authorization.
**Prevention**: Tokens auto-refresh. This only happens after extended inactivity (weeks/months).

### Case: PDF Report Too Large for Email
**Symptoms**: Gmail API rejects attachment (>25MB limit)
**Solution**: Reduce the number of data points in charts, or reduce image quality in the canvas-design prompt. Alternatively, reduce search results to produce fewer data points.
**Prevention**: Default settings produce reports well within the 25MB limit.

### Case: Missing credentials.json
**Symptoms**: FileNotFoundError when running gmail_sender.py
**Solution**: Download OAuth credentials from Google Cloud Console > APIs & Services > Credentials. Save as `credentials.json` in the project root.
**Prevention**: One-time setup — see Phase 0 in the plan.

### Case: Rate Limiting on YouTube API
**Symptoms**: HTTP 429 or rapid consecutive failures
**Solution**: Built-in 100ms delay between API calls and exponential backoff (3 retries) handles this automatically.
**Prevention**: Already included in the collector tool by default.

## Quota Management Strategy
- Each run uses approximately **600 units** out of the 10,000 daily limit
- Breakdown: ~500 for search (5 queries × 100 units), ~10 for video stats, ~5 for channel stats
- **16 runs per day** is the safe maximum
- The collector tracks quota usage in real-time and warns at 80%
- Quota usage is logged in the collection metadata JSON for auditing
- Quota resets at **midnight Pacific Time** daily

## Recurring Schedule
- **Weekly runs**: Set `YOUTUBE_PUBLISHED_AFTER_DAYS=7` for weekly snapshots
- **Monthly runs**: Set `YOUTUBE_PUBLISHED_AFTER_DAYS=30` for monthly deep dives
- **Scheduling options**:
  - Windows Task Scheduler: Create a basic task that runs `python tools/youtube_collector.py && python tools/youtube_analyzer.py` then have the agent generate the PDF via canvas-design skill and run `python tools/gmail_sender.py`
  - Or ask the agent to run the full pipeline on demand

## First-Time Setup

1. Create a Google Cloud project at console.cloud.google.com
2. Enable **YouTube Data API v3** and **Gmail API**
3. Configure OAuth consent screen (External user type, add your Gmail as test user)
4. Create an **OAuth client ID** (Desktop app) → download as `credentials.json` into project root
5. Create an **API key** restricted to YouTube Data API v3 → add to `.env` as `YOUTUBE_API_KEY`
6. Copy `.env.example` to `.env` and fill in all values
7. Install dependencies: `pip install -r requirements.txt`
8. Run the collector first: `python tools/youtube_collector.py --queries "AI automation" --max-results 5 --days 7` (small test)
9. Run the full pipeline once manually to trigger the Gmail OAuth consent flow

## Lessons Learned
[This section grows over time as the system encounters and solves problems]

## Success Criteria
- [ ] At least 50 unique videos collected across all search queries
- [ ] Analysis JSON contains all 8 sections (summary, top videos, top channels, topics, velocity, patterns, trending/declining, recommendations)
- [ ] PDF report has all 11 pages with charts, tables, and Inspired Testing branding rendering correctly
- [ ] Email sent successfully with .pdf attachment
- [ ] Total quota usage < 1,000 units per run
- [ ] Report file size < 25MB (Gmail attachment limit)
