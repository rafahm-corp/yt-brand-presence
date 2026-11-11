"""30-day retention for YouTube API data (YouTube API Services policy).

Deletes per-video / per-comment data files older than RETENTION_DAYS from the outputs folder and
removes the commenter-name column from comment files that are still inside the window.
Aggregated reports (markdown/HTML/slides) are kept."""
import glob
import os
import time

import pandas as pd

RETENTION_DAYS = 30
RAW_PATTERNS = (
    "*_raw_comments.csv",
    "*_discovered_videos.csv",
    "*_multimodal_analysis.csv",
    "*_brand_appearances_timeline.csv",
    "*_trending_videos.csv",
    "*_video_content_breakdown.csv",
    "*_high_engagement_drivers.csv",
)


def enforce_retention(outputs_dir: str = "outputs", days: int = RETENTION_DAYS) -> tuple:
    cutoff = time.time() - days * 86400
    removed = stripped = 0
    for pattern in RAW_PATTERNS:
        for path in glob.glob(os.path.join(outputs_dir, "**", pattern), recursive=True):
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
    for path in glob.glob(os.path.join(outputs_dir, "**", "*_raw_comments.csv"), recursive=True):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "autor" in df.columns:
            st = os.stat(path)
            df.drop(columns=["autor"]).to_csv(path, index=False)
            os.utime(path, (st.st_atime, st.st_mtime))  # keep the original age for the retention clock
            stripped += 1
    if removed or stripped:
        print(f"[retention] removed {removed} files older than {days} days; dropped author column from {stripped} files")
    return removed, stripped
