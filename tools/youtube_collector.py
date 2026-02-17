"""
YouTube Data Collector: Searches YouTube for AI content and collects metrics.

Searches YouTube Data API v3 for videos matching configurable queries,
collects video statistics (views, likes, comments, duration) and channel
statistics (subscribers, total views), calculates derived engagement metrics,
and saves structured data to .tmp/ for downstream analysis.

Usage:
    python tools/youtube_collector.py
    python tools/youtube_collector.py --queries "AI automation,AI agents" --max-results 25 --days 14
"""

import os
import sys
import json
import time
import re
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ---------------------------------------------------------------------------
# Quota tracker
# ---------------------------------------------------------------------------

class QuotaBudget:
    """Tracks estimated YouTube API quota usage during a run."""

    def __init__(self, daily_limit=10_000):
        self.daily_limit = daily_limit
        self.used = 0
        self.log = []

    def spend(self, units: int, operation: str):
        self.used += units
        self.log.append({"operation": operation, "units": units, "cumulative": self.used})
        if self.used > self.daily_limit * 0.8:
            print(f"  WARNING: Quota usage at {self.used}/{self.daily_limit} after '{operation}'")

    def can_afford(self, units: int) -> bool:
        return (self.used + units) <= self.daily_limit

    def summary(self) -> dict:
        return {"total_used": self.used, "daily_limit": self.daily_limit, "details": self.log}


# ---------------------------------------------------------------------------
# ISO 8601 duration parser
# ---------------------------------------------------------------------------

def parse_duration(duration_str: str) -> int:
    """Convert ISO 8601 duration (e.g. PT1H2M34S) to total seconds."""
    if not duration_str:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


# ---------------------------------------------------------------------------
# YouTube API helpers
# ---------------------------------------------------------------------------

def build_youtube_service(api_key: str):
    """Create the YouTube Data API v3 service object."""
    return build("youtube", "v3", developerKey=api_key)


def search_videos(youtube, query: str, max_results: int, published_after: str,
                  quota: QuotaBudget) -> list[dict]:
    """
    Search YouTube for videos matching a query.

    Runs two passes: one sorted by relevance, one by viewCount, then deduplicates.
    """
    all_videos = {}

    for order in ("relevance", "viewCount"):
        if not quota.can_afford(100):
            print(f"  Skipping '{order}' search for '{query}' — quota budget exceeded")
            break

        remaining = max_results
        page_token = None

        while remaining > 0:
            if not quota.can_afford(100):
                break

            per_page = min(remaining, 50)
            try:
                request = youtube.search().list(
                    part="snippet",
                    q=query,
                    type="video",
                    order=order,
                    maxResults=per_page,
                    publishedAfter=published_after,
                    relevanceLanguage="en",
                    pageToken=page_token,
                )
                response = request.execute()
                quota.spend(100, f"search.list({order}, '{query}')")
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    print(f"  Quota exceeded during search for '{query}'")
                    return list(all_videos.values())
                raise

            for item in response.get("items", []):
                vid_id = item["id"]["videoId"]
                if vid_id not in all_videos:
                    snippet = item["snippet"]
                    all_videos[vid_id] = {
                        "video_id": vid_id,
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "channel_id": snippet.get("channelId", ""),
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    }

            page_token = response.get("nextPageToken")
            remaining -= per_page
            if not page_token:
                break

            time.sleep(0.1)  # rate-limit courtesy

    return list(all_videos.values())


def get_video_statistics(youtube, video_ids: list[str], quota: QuotaBudget) -> dict:
    """Fetch detailed statistics for a list of video IDs (batched in groups of 50)."""
    stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        if not quota.can_afford(1):
            print("  Quota budget exceeded — skipping remaining video stats")
            break

        retries = 0
        while retries < 3:
            try:
                response = youtube.videos().list(
                    part="statistics,contentDetails,snippet",
                    id=",".join(batch),
                ).execute()
                quota.spend(1, f"videos.list(batch {i // 50 + 1})")
                break
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    print("  Quota exceeded during video stats fetch")
                    return stats
                retries += 1
                if retries >= 3:
                    print(f"  Failed to fetch video stats for batch after 3 retries: {e}")
                    break
                time.sleep(2 ** retries)

        for item in response.get("items", []):
            vid_id = item["id"]
            s = item.get("statistics", {})
            cd = item.get("contentDetails", {})
            snip = item.get("snippet", {})
            stats[vid_id] = {
                "view_count": int(s.get("viewCount", 0)),
                "like_count": int(s.get("likeCount", 0)),
                "comment_count": int(s.get("commentCount", 0)),
                "duration_seconds": parse_duration(cd.get("duration", "")),
                "tags": snip.get("tags", []),
                "category_id": snip.get("categoryId", ""),
            }

        time.sleep(0.1)

    return stats


def get_channel_statistics(youtube, channel_ids: list[str], quota: QuotaBudget) -> list[dict]:
    """Fetch statistics for a list of channel IDs (batched in groups of 50)."""
    channels = []
    unique_ids = list(set(channel_ids))

    for i in range(0, len(unique_ids), 50):
        batch = unique_ids[i : i + 50]
        if not quota.can_afford(1):
            print("  Quota budget exceeded — skipping remaining channel stats")
            break

        retries = 0
        while retries < 3:
            try:
                response = youtube.channels().list(
                    part="statistics,snippet",
                    id=",".join(batch),
                ).execute()
                quota.spend(1, f"channels.list(batch {i // 50 + 1})")
                break
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    print("  Quota exceeded during channel stats fetch")
                    return channels
                retries += 1
                if retries >= 3:
                    print(f"  Failed to fetch channel stats after 3 retries: {e}")
                    break
                time.sleep(2 ** retries)

        for item in response.get("items", []):
            s = item.get("statistics", {})
            snip = item.get("snippet", {})
            channels.append({
                "channel_id": item["id"],
                "channel_title": snip.get("title", ""),
                "channel_description": snip.get("description", ""),
                "custom_url": snip.get("customUrl", ""),
                "country": snip.get("country", ""),
                "subscriber_count": int(s.get("subscriberCount", 0)),
                "video_count": int(s.get("videoCount", 0)),
                "total_view_count": int(s.get("viewCount", 0)),
                "channel_thumbnail": snip.get("thumbnails", {}).get("default", {}).get("url", ""),
            })

        time.sleep(0.1)

    return channels


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def calculate_derived_metrics(videos_df: pd.DataFrame) -> pd.DataFrame:
    """Add calculated engagement and content metrics to the videos dataframe."""
    now = datetime.now(timezone.utc)

    videos_df["published_at"] = pd.to_datetime(videos_df["published_at"], utc=True)
    videos_df["days_since_published"] = (now - videos_df["published_at"]).dt.days.clip(lower=1)
    videos_df["views_per_day"] = (videos_df["view_count"] / videos_df["days_since_published"]).round(1)

    # Engagement ratios (guard against division by zero)
    views = videos_df["view_count"].replace(0, 1)
    videos_df["engagement_ratio"] = ((videos_df["like_count"] + videos_df["comment_count"]) / views).round(6)
    videos_df["like_to_view_ratio"] = (videos_df["like_count"] / views).round(6)
    videos_df["comment_to_view_ratio"] = (videos_df["comment_count"] / views).round(6)

    # Content metrics
    videos_df["title_length"] = videos_df["title"].str.len()
    videos_df["title_word_count"] = videos_df["title"].str.split().str.len()
    videos_df["has_number_in_title"] = videos_df["title"].str.contains(r"\d", regex=True)
    videos_df["tag_count"] = videos_df["tags"].apply(lambda t: len(t) if isinstance(t, list) else 0)

    # Duration buckets
    videos_df["duration_bucket"] = pd.cut(
        videos_df["duration_seconds"],
        bins=[0, 300, 600, 1200, 3600, float("inf")],
        labels=["0-5min", "5-10min", "10-20min", "20-60min", "60+min"],
    )

    # Publish day of week
    videos_df["publish_day"] = videos_df["published_at"].dt.day_name()

    return videos_df


# ---------------------------------------------------------------------------
# Save results
# ---------------------------------------------------------------------------

def save_results(videos_df: pd.DataFrame, channels_df: pd.DataFrame,
                 metadata: dict, tmp_dir: str) -> dict:
    """Save collected data to .tmp/ and update the manifest."""
    os.makedirs(tmp_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Convert tags list to JSON string for CSV storage
    videos_save = videos_df.copy()
    videos_save["tags"] = videos_save["tags"].apply(
        lambda t: json.dumps(t) if isinstance(t, list) else "[]"
    )

    videos_path = os.path.join(tmp_dir, f"youtube_videos_{ts}.csv")
    channels_path = os.path.join(tmp_dir, f"youtube_channels_{ts}.csv")
    meta_path = os.path.join(tmp_dir, f"youtube_collection_metadata_{ts}.json")
    manifest_path = os.path.join(tmp_dir, "youtube_latest.json")

    videos_save.to_csv(videos_path, index=False)
    channels_df.to_csv(channels_path, index=False)

    metadata["timestamp"] = ts
    metadata["videos_file"] = videos_path
    metadata["channels_file"] = channels_path
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)

    manifest = {
        "latest_collection": {
            "videos_file": videos_path,
            "channels_file": channels_path,
            "metadata_file": meta_path,
            "timestamp": ts,
        }
    }
    # Preserve any existing analysis pointer
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if "latest_analysis" in existing:
            manifest["latest_analysis"] = existing["latest_analysis"]

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {"videos_file": videos_path, "channels_file": channels_path, "metadata_file": meta_path}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(search_queries: list[str] = None, max_results: int = None,
         published_after_days: int = None) -> dict:
    """
    Collect YouTube data for AI niche analysis.

    Args:
        search_queries: List of search terms. Defaults to YOUTUBE_SEARCH_QUERIES from .env.
        max_results: Max results per query. Defaults to YOUTUBE_MAX_RESULTS_PER_QUERY from .env.
        published_after_days: Only include videos published within N days.

    Returns:
        dict with status and data (file paths to collected data).
    """
    load_dotenv()

    # Resolve parameters
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return {"status": "error", "error": "YOUTUBE_API_KEY not found in .env"}

    if search_queries is None:
        raw = os.getenv("YOUTUBE_SEARCH_QUERIES", "AI automation,AI agents")
        search_queries = [q.strip() for q in raw.split(",") if q.strip()]

    if max_results is None:
        max_results = int(os.getenv("YOUTUBE_MAX_RESULTS_PER_QUERY", "50"))

    if published_after_days is None:
        published_after_days = int(os.getenv("YOUTUBE_PUBLISHED_AFTER_DAYS", "30"))

    published_after = (datetime.now(timezone.utc) - timedelta(days=published_after_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp")

    try:
        youtube = build_youtube_service(api_key)
        quota = QuotaBudget()

        # --- Step 1: Search for videos ---
        all_videos = []
        for query in search_queries:
            print(f"  Searching: '{query}' ...")
            videos = search_videos(youtube, query, max_results, published_after, quota)
            all_videos.extend(videos)
            print(f"    Found {len(videos)} videos")

        if not all_videos:
            return {"status": "error", "error": "No videos found across all search queries"}

        # Deduplicate by video_id
        seen = set()
        unique_videos = []
        for v in all_videos:
            if v["video_id"] not in seen:
                seen.add(v["video_id"])
                unique_videos.append(v)
        print(f"  Total unique videos: {len(unique_videos)}")

        # --- Step 2: Get video statistics ---
        print("  Fetching video statistics ...")
        video_ids = [v["video_id"] for v in unique_videos]
        video_stats = get_video_statistics(youtube, video_ids, quota)

        # Merge stats into video records
        for v in unique_videos:
            stats = video_stats.get(v["video_id"], {})
            v.update(stats)

        videos_df = pd.DataFrame(unique_videos)

        # Fill missing stat columns with defaults
        for col in ["view_count", "like_count", "comment_count", "duration_seconds", "tag_count"]:
            if col not in videos_df.columns:
                videos_df[col] = 0
        if "tags" not in videos_df.columns:
            videos_df["tags"] = [[] for _ in range(len(videos_df))]

        # --- Step 3: Calculate derived metrics ---
        videos_df = calculate_derived_metrics(videos_df)

        # --- Step 4: Get channel statistics ---
        print("  Fetching channel statistics ...")
        channel_ids = videos_df["channel_id"].dropna().unique().tolist()
        channels_data = get_channel_statistics(youtube, channel_ids, quota)
        channels_df = pd.DataFrame(channels_data) if channels_data else pd.DataFrame()

        # --- Step 5: Save ---
        metadata = {
            "search_queries": search_queries,
            "max_results_per_query": max_results,
            "published_after_days": published_after_days,
            "published_after": published_after,
            "total_videos": len(videos_df),
            "total_channels": len(channels_df),
            "quota": quota.summary(),
        }

        file_paths = save_results(videos_df, channels_df, metadata, tmp_dir)
        print(f"  Data saved. Quota used: {quota.used}/{quota.daily_limit}")

        return {
            "status": "success",
            "data": {
                **file_paths,
                "total_videos": len(videos_df),
                "total_channels": len(channels_df),
                "quota_used": quota.used,
            },
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube AI Niche Data Collector")
    parser.add_argument("--queries", type=str, help="Comma-separated search queries")
    parser.add_argument("--max-results", type=int, help="Max results per query")
    parser.add_argument("--days", type=int, help="Published within N days")
    args = parser.parse_args()

    queries = [q.strip() for q in args.queries.split(",")] if args.queries else None
    result = main(search_queries=queries, max_results=args.max_results,
                  published_after_days=args.days)

    if result["status"] == "success":
        print(f"\nSuccess: Collected {result['data']['total_videos']} videos "
              f"from {result['data']['total_channels']} channels")
        print(f"  Videos: {result['data']['videos_file']}")
        print(f"  Channels: {result['data']['channels_file']}")
        sys.exit(0)
    else:
        print(f"\nError: {result['error']}", file=sys.stderr)
        sys.exit(1)
