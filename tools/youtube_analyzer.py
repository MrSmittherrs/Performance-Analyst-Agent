"""
YouTube Data Analyzer: Processes collected YouTube data to identify trends,
patterns, and insights in the AI content niche.

Reads CSV data from .tmp/ (produced by youtube_collector.py), performs
engagement analysis, topic clustering, velocity trends, content pattern
detection, and generates actionable recommendations.

Usage:
    python tools/youtube_analyzer.py
    python tools/youtube_analyzer.py --data-dir .tmp --top-n 20
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone
from collections import Counter
from dotenv import load_dotenv
import pandas as pd


# ---------------------------------------------------------------------------
# Topic categories for keyword-based clustering
# ---------------------------------------------------------------------------

TOPIC_CATEGORIES = {
    "AI Agents": [
        "agent", "agentic", "autonomous", "crew ai", "crewai", "autogen",
        "multi-agent", "multi agent", "langchain", "langgraph", "openai agents",
    ],
    "LLMs & Chatbots": [
        "chatgpt", "gpt", "llm", "language model", "claude", "gemini",
        "copilot", "llama", "mistral", "deepseek", "openai", "anthropic",
        "chatbot", "conversational ai",
    ],
    "AI Coding": [
        "cursor", "coding", "programming", "developer", "code generation",
        "github copilot", "devin", "software engineer", "vscode", "ide",
        "windsurf", "bolt", "replit",
    ],
    "AI Automation": [
        "automation", "automate", "workflow", "n8n", "zapier", "make.com",
        "no code", "no-code", "low code", "low-code", "integration",
    ],
    "AI Image & Video": [
        "midjourney", "dall-e", "dalle", "stable diffusion", "sora",
        "video generation", "image generation", "ai art", "flux",
        "runway", "kling", "text to image", "text to video",
    ],
    "AI Business & Money": [
        "business", "startup", "money", "income", "saas", "freelance",
        "side hustle", "make money", "passive income", "entrepreneur",
        "ai agency", "client",
    ],
    "AI News & Updates": [
        "news", "update", "announced", "released", "launch", "just dropped",
        "breaking", "new feature", "keynote", "conference",
    ],
    "AI Tutorials": [
        "tutorial", "how to", "beginner", "guide", "step by step",
        "crash course", "learn", "for beginners", "walkthrough", "explained",
    ],
    "AI Ethics & Safety": [
        "safety", "alignment", "regulation", "risk", "agi", "superintelligence",
        "ethics", "bias", "responsible ai", "governance",
    ],
}

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "and", "but", "or", "nor", "not", "so", "yet", "both",
    "each", "every", "all", "any", "few", "more", "most", "other",
    "some", "such", "no", "only", "own", "same", "than", "too", "very",
    "just", "don", "now", "this", "that", "these", "those", "i", "me",
    "my", "you", "your", "he", "him", "his", "she", "her", "it", "its",
    "we", "our", "they", "them", "their", "what", "which", "who", "whom",
    "when", "where", "why", "how", "up", "about", "if", "here", "there",
    "new", "get", "use", "using", "used", "|", "-", "&", "vs", "vs.",
}


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def analyze_top_videos(df: pd.DataFrame, top_n: int) -> dict:
    """Rank videos by views, engagement, and velocity."""
    cols = ["video_id", "title", "channel_title", "view_count", "like_count",
            "comment_count", "engagement_ratio", "views_per_day", "published_at",
            "thumbnail_url", "duration_seconds"]
    available_cols = [c for c in cols if c in df.columns]

    by_views = df.nlargest(top_n, "view_count")[available_cols].to_dict("records")
    by_engagement = df.nlargest(top_n, "engagement_ratio")[available_cols].to_dict("records")
    by_velocity = df.nlargest(top_n, "views_per_day")[available_cols].to_dict("records")

    return {"by_views": by_views, "by_engagement": by_engagement, "by_velocity": by_velocity}


def analyze_top_channels(videos_df: pd.DataFrame, channels_df: pd.DataFrame,
                         top_n: int) -> list[dict]:
    """Rank channels by subscriber count and average engagement of their videos."""
    if channels_df.empty:
        return []

    # Count videos per channel in our dataset and avg engagement
    channel_agg = videos_df.groupby("channel_id").agg(
        videos_in_dataset=("video_id", "count"),
        avg_engagement=("engagement_ratio", "mean"),
        avg_views=("view_count", "mean"),
        total_views_in_dataset=("view_count", "sum"),
    ).reset_index()

    merged = channels_df.merge(channel_agg, on="channel_id", how="left").fillna(0)
    merged = merged.sort_values("subscriber_count", ascending=False).head(top_n)

    cols = ["channel_id", "channel_title", "subscriber_count", "video_count",
            "total_view_count", "videos_in_dataset", "avg_engagement", "avg_views",
            "custom_url", "country"]
    available_cols = [c for c in cols if c in merged.columns]

    return merged[available_cols].to_dict("records")


def analyze_topic_clusters(df: pd.DataFrame) -> dict:
    """Categorize videos by topic using keyword matching on titles and tags."""
    category_counts = Counter()
    category_engagement = {cat: [] for cat in TOPIC_CATEGORIES}
    category_views = {cat: [] for cat in TOPIC_CATEGORIES}
    video_categories = []

    for _, row in df.iterrows():
        text = (str(row.get("title", "")) + " " +
                " ".join(row.get("tags", []) if isinstance(row.get("tags"), list) else [])
                ).lower()

        matched = []
        for category, keywords in TOPIC_CATEGORIES.items():
            if any(kw in text for kw in keywords):
                matched.append(category)
                category_counts[category] += 1
                category_engagement[category].append(row.get("engagement_ratio", 0))
                category_views[category].append(row.get("view_count", 0))

        if not matched:
            category_counts["Other"] += 1
        video_categories.append(matched if matched else ["Other"])

    # Calculate average engagement per category
    avg_engagement = {}
    avg_views = {}
    for cat in TOPIC_CATEGORIES:
        if category_engagement[cat]:
            avg_engagement[cat] = round(sum(category_engagement[cat]) / len(category_engagement[cat]), 6)
            avg_views[cat] = round(sum(category_views[cat]) / len(category_views[cat]), 1)
        else:
            avg_engagement[cat] = 0
            avg_views[cat] = 0

    return {
        "categories": dict(category_counts),
        "engagement_by_category": avg_engagement,
        "views_by_category": avg_views,
    }


def analyze_view_velocity(df: pd.DataFrame) -> dict:
    """Calculate weekly average views-per-day to spot momentum trends."""
    if "published_at" not in df.columns:
        return {"weekly_data": []}

    df_copy = df.copy()
    df_copy["publish_week"] = df_copy["published_at"].dt.isocalendar().week
    df_copy["publish_year"] = df_copy["published_at"].dt.isocalendar().year

    weekly = df_copy.groupby(["publish_year", "publish_week"]).agg(
        avg_views_per_day=("views_per_day", "mean"),
        avg_views=("view_count", "mean"),
        video_count=("video_id", "count"),
    ).reset_index()

    weekly = weekly.sort_values(["publish_year", "publish_week"])
    weekly["week_label"] = weekly.apply(
        lambda r: f"{int(r['publish_year'])}-W{int(r['publish_week']):02d}", axis=1
    )

    return {
        "weekly_data": weekly[["week_label", "avg_views_per_day", "avg_views", "video_count"]]
        .round(1).to_dict("records")
    }


def analyze_content_patterns(df: pd.DataFrame) -> dict:
    """Detect patterns in titles, durations, publish days, and tags."""
    patterns = {}

    # Title length vs views correlation
    if "title_length" in df.columns and len(df) > 5:
        corr = df[["title_length", "view_count"]].corr().iloc[0, 1]
        top_quartile = df.nlargest(len(df) // 4, "view_count")
        patterns["title_length"] = {
            "correlation_with_views": round(corr, 4) if pd.notna(corr) else 0,
            "avg_title_length_all": round(df["title_length"].mean(), 1),
            "avg_title_length_top25pct": round(top_quartile["title_length"].mean(), 1),
        }

    # Duration sweet spots
    if "duration_bucket" in df.columns:
        duration_perf = df.groupby("duration_bucket", observed=True).agg(
            avg_views=("view_count", "mean"),
            avg_engagement=("engagement_ratio", "mean"),
            count=("video_id", "count"),
        ).round(1).to_dict("index")
        patterns["duration_performance"] = {
            str(k): v for k, v in duration_perf.items()
        }

    # Publish day performance
    if "publish_day" in df.columns:
        day_perf = df.groupby("publish_day").agg(
            avg_views=("view_count", "mean"),
            count=("video_id", "count"),
        ).round(1)
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_perf = day_perf.reindex([d for d in day_order if d in day_perf.index])
        patterns["publish_day_performance"] = day_perf.to_dict("index")

    # Top title words (in high-performing videos vs all)
    top_quartile = df.nlargest(len(df) // 4, "view_count") if len(df) > 4 else df
    all_words = Counter()
    top_words = Counter()

    for title in df["title"].dropna():
        words = [w.lower() for w in re.findall(r"\b\w+\b", title) if w.lower() not in STOPWORDS and len(w) > 2]
        all_words.update(words)

    for title in top_quartile["title"].dropna():
        words = [w.lower() for w in re.findall(r"\b\w+\b", title) if w.lower() not in STOPWORDS and len(w) > 2]
        top_words.update(words)

    patterns["top_title_words_all"] = [{"word": w, "count": c} for w, c in all_words.most_common(20)]
    patterns["top_title_words_top25pct"] = [{"word": w, "count": c} for w, c in top_words.most_common(20)]

    # Title pattern flags
    if "has_number_in_title" in df.columns:
        with_number = df[df["has_number_in_title"] == True]
        without_number = df[df["has_number_in_title"] == False]
        patterns["number_in_title"] = {
            "pct_with_number": round(len(with_number) / max(len(df), 1) * 100, 1),
            "avg_views_with": round(with_number["view_count"].mean(), 1) if len(with_number) > 0 else 0,
            "avg_views_without": round(without_number["view_count"].mean(), 1) if len(without_number) > 0 else 0,
        }

    return patterns


def analyze_trending_vs_declining(df: pd.DataFrame) -> dict:
    """Compare topic performance in first half vs second half of the date range."""
    if "published_at" not in df.columns or len(df) < 10:
        return {"trending": [], "declining": []}

    midpoint = df["published_at"].min() + (df["published_at"].max() - df["published_at"].min()) / 2

    first_half = df[df["published_at"] <= midpoint]
    second_half = df[df["published_at"] > midpoint]

    def count_topics(subset):
        counts = Counter()
        for _, row in subset.iterrows():
            text = (str(row.get("title", "")) + " " +
                    " ".join(row.get("tags", []) if isinstance(row.get("tags"), list) else [])
                    ).lower()
            for category, keywords in TOPIC_CATEGORIES.items():
                if any(kw in text for kw in keywords):
                    counts[category] += 1
        return counts

    first_counts = count_topics(first_half)
    second_counts = count_topics(second_half)

    all_topics = set(first_counts.keys()) | set(second_counts.keys())

    trending = []
    declining = []

    for topic in all_topics:
        first = first_counts.get(topic, 0)
        second = second_counts.get(topic, 0)
        if first == 0 and second == 0:
            continue
        if first == 0:
            change_pct = 100.0
        else:
            change_pct = round(((second - first) / first) * 100, 1)

        entry = {"topic": topic, "first_half": first, "second_half": second, "change_pct": change_pct}
        if change_pct > 10:
            trending.append(entry)
        elif change_pct < -10:
            declining.append(entry)

    trending.sort(key=lambda x: x["change_pct"], reverse=True)
    declining.sort(key=lambda x: x["change_pct"])

    return {"trending": trending, "declining": declining}


def generate_executive_summary(top_videos: dict, top_channels: list,
                                topic_dist: dict, velocity: dict,
                                patterns: dict, trends: dict) -> list[str]:
    """Distill key findings into 5-7 bullet points."""
    summary = []

    # Top video
    if top_videos.get("by_views"):
        top = top_videos["by_views"][0]
        summary.append(
            f"Most viewed video: \"{top['title'][:60]}\" by {top['channel_title']} "
            f"with {top['view_count']:,} views"
        )

    # Top topic
    cats = topic_dist.get("categories", {})
    if cats:
        top_cat = max(cats, key=cats.get)
        summary.append(f"Most popular topic: {top_cat} ({cats[top_cat]} videos)")

    # Highest engagement topic
    eng = topic_dist.get("engagement_by_category", {})
    if eng:
        top_eng = max(eng, key=eng.get)
        summary.append(
            f"Highest engagement topic: {top_eng} "
            f"({eng[top_eng]:.2%} avg engagement ratio)"
        )

    # Trending topics
    if trends.get("trending"):
        rising = [t["topic"] for t in trends["trending"][:3]]
        summary.append(f"Rising topics: {', '.join(rising)}")

    # Duration sweet spot
    dur = patterns.get("duration_performance", {})
    if dur:
        best_dur = max(dur, key=lambda k: dur[k].get("avg_views", 0))
        summary.append(f"Best performing video length: {best_dur}")

    # Title insight
    num_data = patterns.get("number_in_title", {})
    if num_data and num_data.get("avg_views_with", 0) > num_data.get("avg_views_without", 0):
        summary.append("Videos with numbers in titles average more views")

    # Top channel
    if top_channels:
        ch = top_channels[0]
        summary.append(
            f"Top channel: {ch['channel_title']} "
            f"({ch['subscriber_count']:,} subscribers)"
        )

    return summary[:7]


def generate_recommendations(topic_dist: dict, patterns: dict,
                              trends: dict) -> list[str]:
    """Generate data-driven content creation recommendations."""
    recs = []

    # Topic recommendation
    eng = topic_dist.get("engagement_by_category", {})
    if eng:
        top_eng = max(eng, key=eng.get)
        recs.append(
            f"Focus on {top_eng} content — it has the highest engagement ratio "
            f"({eng[top_eng]:.2%}), meaning viewers are more likely to interact"
        )

    # Trending topic
    if trends.get("trending"):
        rising = trends["trending"][0]
        recs.append(
            f"Ride the wave on '{rising['topic']}' — it's up {rising['change_pct']}% "
            f"in recent weeks, signaling growing audience interest"
        )

    # Duration recommendation
    dur = patterns.get("duration_performance", {})
    if dur:
        best_dur = max(dur, key=lambda k: dur[k].get("avg_views", 0))
        recs.append(f"Aim for {best_dur} video length — this range gets the most average views")

    # Title patterns
    title_words = patterns.get("top_title_words_top25pct", [])
    if title_words:
        top_3 = [w["word"] for w in title_words[:5]]
        recs.append(
            f"Use high-performing title keywords: {', '.join(top_3)} — "
            f"these appear frequently in top 25% videos"
        )

    # Publish day
    day_perf = patterns.get("publish_day_performance", {})
    if day_perf:
        best_day = max(day_perf, key=lambda k: day_perf[k].get("avg_views", 0))
        recs.append(f"Publish on {best_day}s for maximum reach — best average views on that day")

    # Declining topics to avoid
    if trends.get("declining"):
        dec = trends["declining"][0]
        recs.append(
            f"Consider pivoting away from '{dec['topic']}' as standalone content — "
            f"it's down {abs(dec['change_pct'])}%. Combine it with trending topics instead"
        )

    return recs[:6]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(data_dir: str = None, top_n: int = 20) -> dict:
    """
    Analyze collected YouTube data and produce trend insights.

    Args:
        data_dir: Directory containing collection data. Defaults to .tmp/.
        top_n: Number of top items to include in rankings.

    Returns:
        dict with status and path to analysis output file.
    """
    load_dotenv()

    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp")

    manifest_path = os.path.join(data_dir, "youtube_latest.json")

    try:
        # Load manifest
        if not os.path.exists(manifest_path):
            return {"status": "error", "error": f"Manifest not found at {manifest_path}. Run youtube_collector.py first."}

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        collection = manifest.get("latest_collection", {})
        videos_file = collection.get("videos_file")
        channels_file = collection.get("channels_file")

        if not videos_file or not os.path.exists(videos_file):
            return {"status": "error", "error": f"Videos data file not found: {videos_file}"}

        # Load data
        print("  Loading collected data ...")
        videos_df = pd.read_csv(videos_file)
        videos_df["published_at"] = pd.to_datetime(videos_df["published_at"], utc=True)

        # Reconstruct tags from JSON strings
        if "tags" in videos_df.columns:
            videos_df["tags"] = videos_df["tags"].apply(
                lambda t: json.loads(t) if isinstance(t, str) and t.startswith("[") else []
            )

        channels_df = pd.DataFrame()
        if channels_file and os.path.exists(channels_file):
            channels_df = pd.read_csv(channels_file)

        print(f"  Loaded {len(videos_df)} videos, {len(channels_df)} channels")

        # Run analyses
        print("  Analyzing top videos ...")
        top_videos = analyze_top_videos(videos_df, top_n)

        print("  Analyzing top channels ...")
        top_channels = analyze_top_channels(videos_df, channels_df, top_n)

        print("  Analyzing topic distribution ...")
        topic_dist = analyze_topic_clusters(videos_df)

        print("  Analyzing view velocity ...")
        velocity = analyze_view_velocity(videos_df)

        print("  Analyzing content patterns ...")
        patterns = analyze_content_patterns(videos_df)

        print("  Analyzing trending vs declining topics ...")
        trends = analyze_trending_vs_declining(videos_df)

        print("  Generating executive summary ...")
        summary = generate_executive_summary(top_videos, top_channels, topic_dist, velocity, patterns, trends)

        print("  Generating recommendations ...")
        recommendations = generate_recommendations(topic_dist, patterns, trends)

        # Compile analysis
        date_range_from = videos_df["published_at"].min().strftime("%Y-%m-%d")
        date_range_to = videos_df["published_at"].max().strftime("%Y-%m-%d")

        analysis = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_period": {"from": date_range_from, "to": date_range_to},
            "total_videos_analyzed": len(videos_df),
            "total_channels_analyzed": len(channels_df),
            "executive_summary": summary,
            "top_videos": top_videos,
            "top_channels": top_channels,
            "topic_distribution": topic_dist,
            "view_velocity": velocity,
            "content_patterns": patterns,
            "trending_topics": trends,
            "recommendations": recommendations,
        }

        # Save
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        analysis_path = os.path.join(data_dir, f"youtube_analysis_{ts}.json")

        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, default=str)

        # Update manifest
        manifest["latest_analysis"] = {"analysis_file": analysis_path, "timestamp": ts}
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"  Analysis saved to {analysis_path}")

        return {
            "status": "success",
            "data": {
                "analysis_file": analysis_path,
                "total_videos_analyzed": len(videos_df),
                "total_channels_analyzed": len(channels_df),
                "summary_points": len(summary),
                "recommendations": len(recommendations),
            },
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube AI Niche Data Analyzer")
    parser.add_argument("--data-dir", type=str, help="Directory containing collection data")
    parser.add_argument("--top-n", type=int, default=20, help="Number of top items in rankings")
    args = parser.parse_args()

    result = main(data_dir=args.data_dir, top_n=args.top_n)

    if result["status"] == "success":
        print(f"\nSuccess: Analyzed {result['data']['total_videos_analyzed']} videos")
        print(f"  Analysis: {result['data']['analysis_file']}")
        sys.exit(0)
    else:
        print(f"\nError: {result['error']}", file=sys.stderr)
        sys.exit(1)
