import argparse
import sys
import os
import glob
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from crawler import YouTubeBrandCrawler
from comment_extractor import YouTubeCommentExtractor
from brand_presence_analyzer import BrandPresenceAnalyzer
from multimodal_extractor import VideoMultimodalExtractor
from generate_slides_final import run_slide_generation
from drive_uploader import upload_run_outputs_to_drive


def run_pipeline(step: str = 'all', config_path: str = 'config.ini'):
    """
    Executes YouTube Brand Presence & Share of Voice Tracker pipeline steps:
      - crawl: Search & filter category YouTube videos.
      - comments: Fetch audience comments.
      - multimodal / extract / transcribe: Stage 1 Parallel Multimodal Video Ingestion.
      - analyze: Stage 2 Strategic Macro Synthesis (also executes Stage 1 if needed).
      - slides: Executive Presentation Slide Deck Generation.
      - all: Full end-to-end orchestration.
    """
    config_path = os.path.abspath(config_path)

    if step in ['all', 'crawl']:
        print("\n" + "="*50)
        print(" STEP 1: CATEGORY THEME VIDEO SEARCH ")
        print("="*50)
        crawler = YouTubeBrandCrawler(config_path=config_path)
        crawler.run_crawler()

    if step in ['all', 'comments']:
        print("\n" + "="*50)
        print(" STEP 2: AUDIENCE COMMENTS EXTRACTION ")
        print("="*50)
        extractor = YouTubeCommentExtractor(config_path=config_path)
        extractor.extract_comments()

    if step in ['multimodal', 'extract', 'transcribe']:
        print("\n" + "="*50)
        print(" STEP 3 [Stage 1/2]: PARALLEL MULTIMODAL VIDEO EXTRACTION ")
        print("="*50)
        extractor = VideoMultimodalExtractor(config_path=config_path)
        output_dir = extractor.output_dir
        video_files = glob.glob(os.path.join(output_dir, "*_discovered_videos.csv"))
        if video_files and os.path.exists(video_files[0]):
            videos_df = pd.read_csv(video_files[0])
            print(f"Loaded {len(videos_df)} discovered videos from {video_files[0]}")
            extractor.process_videos_df(videos_df)
        else:
            print(f"Warning: No discovered videos CSV found in {output_dir}. Run 'crawl' step first.")

    if step in ['all', 'analyze']:
        print("\n" + "="*50)
        print(" STEP 3: SHARE OF VOICE & BRAND PRESENCE ANALYSIS ")
        print(" [Stage 1/2] Parallel Multimodal Video Extraction (gemini-3.7-flash)")
        print(" [Stage 2/2] Strategic Macro Synthesis & Executive Reporting")
        print("="*50)
        analyzer = BrandPresenceAnalyzer(config_path=config_path)
        analyzer.analyze_brand_presence()

    import configparser
    cfg = configparser.ConfigParser(interpolation=None)
    if os.path.exists(config_path):
        cfg.read(config_path)
    req_outputs = [r.strip().lower() for r in cfg.get('Analysis', 'requested_outputs', fallback='pdf,html,markdown').split(',') if r.strip()]

    if step == 'slides' or ('pdf' in req_outputs and step == 'all'):
        print("\n" + "="*50)
        print(" STEP 4: EXECUTIVE PDF PRESENTATION DECK GENERATION ")
        print("="*50)
        run_slide_generation(config_path=config_path)
    elif step == 'all':
        print("\n" + "="*50)
        print(" STEP 4: EXECUTIVE PDF PRESENTATION DECK GENERATION ")
        print("="*50)
        print("[SKIP] PDF presentation generation skipped per user request (not selected in output formats).")

    if step in ['all']:
        print("\n" + "="*50)
        print(" STEP 5: GOOGLE DRIVE BACKUP ")
        print("="*50)
        upload_run_outputs_to_drive(config_path=config_path)
        print("\n✨ BRAND PRESENCE TRACKING PIPELINE COMPLETED SUCCESSFULLY!")


def main():
    from retention import enforce_retention
    enforce_retention(os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs"))
    print("\n" + "="*60)
    print(" 🚀 YOUTUBE BRAND PRESENCE & SHARE OF VOICE TRACKER ")
    print(" Target Brand Presence & Category Theme Intelligence ")
    print(" Powered by Gemini 3.7 Flash 2-Stage Multimodal Engine ")
    print("="*60 + "\n")

    parser = argparse.ArgumentParser(description="YouTube Brand Presence & Share of Voice Tracker (Gemini 3.7 Flash Multimodal Pipeline)")
    parser.add_argument(
        'step',
        choices=['all', 'crawl', 'comments', 'multimodal', 'extract', 'transcribe', 'analyze', 'slides'],
        help="Pipeline step to execute: 'crawl', 'comments', 'multimodal'/'extract'/'transcribe' (Stage 1), 'analyze' (Stage 2), 'slides', or 'all'."
    )
    parser.add_argument('--config', default='config.ini', help="Path to config file.")

    args = parser.parse_args()
    try:
        run_pipeline(step=args.step, config_path=args.config)
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
