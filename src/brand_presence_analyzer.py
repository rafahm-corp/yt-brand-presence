"""
Brand Presence & Share of Voice Analyzer (Stage 2 Macro Synthesis Engine).

Synthesizes 360-degree multimodal brand intelligence, quantitative Share of Voice metrics,
and creator mapping using Gemini 3.7 Flash.
"""

import os
import re
import glob
import logging
import configparser
from typing import List, Optional, Tuple, Dict, Any, Union

import pandas as pd
from dotenv import load_dotenv
from google.genai import types

from client_factory import (
    create_genai_client,
    get_model_names,
    get_multimodal_config,
    generate_content_with_retry,
)
from multimodal_extractor import VideoMultimodalExtractor

logger = logging.getLogger(__name__)


class BrandPresenceAnalyzer:
    """
    Stage 2 Strategic Macro Synthesis Engine.
    Combines Stage 1 multimodal video facts (visual appearances, spoken claims, creator stances)
    with quantitative SOV metrics and audience comments to produce executive intelligence reports.
    """

    def __init__(
        self,
        config_path: str = "config.ini",
        output_dir: Optional[str] = None,
        target_brand: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        category_theme: Optional[str] = None,
    ):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = config_path if os.path.isabs(config_path) else os.path.join(self.project_root, config_path)

        self._load_environment_variables()
        self._load_configuration(
            output_dir=output_dir,
            target_brand=target_brand,
            competitors=competitors,
            category_theme=category_theme,
        )

        print("Initializing Google GenAI Client for Brand Presence Analysis...")
        self.client = create_genai_client(config_path=self.config_path)
        print("SUCCESS: GenAI Client initialized.")

    @staticmethod
    def _df_to_markdown(df: pd.DataFrame, index: bool = False) -> str:
        if df is None or df.empty:
            return ""
        try:
            return df.to_markdown(index=index)
        except Exception:
            try:
                headers = list(df.columns)
                lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
                lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for _, row in df.iterrows():
                    lines.append("| " + " | ".join(str(v).replace("\n", " ") for v in row.values) + " |")
                return "\n".join(lines)
            except Exception:
                return df.to_string(index=index)


    def _load_environment_variables(self):
        load_dotenv(os.path.join(self.project_root, ".env"))
        self.google_api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("YOUTUBE_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )

    def _load_configuration(
        self,
        output_dir: Optional[str] = None,
        target_brand: Optional[str] = None,
        competitors: Optional[List[str]] = None,
        category_theme: Optional[str] = None,
    ):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found at {self.config_path}")

        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_path)
        self.config = config
        self.max_results = max(config.getint("Category", "max_results", fallback=config.getint("Crawler", "max_results", fallback=30)), 30)

        # Target Brand resolution
        target_cfg = config.get("Target", "target_brand", fallback="").strip()
        if not target_cfg:
            target_cfg = config.get("Crawler", "search_terms", fallback="").strip()
        self.target_brand = target_brand or (target_cfg if target_cfg else "Target Brand")

        # Competitors resolution
        if competitors is not None:
            self.competitors = competitors
        else:
            comp_raw = config.get("Target", "competitors", fallback="").strip()
            self.competitors = [c.strip() for c in comp_raw.split(",") if c.strip()]

        # Category Theme resolution
        cat_cfg = config.get("Category", "category_theme", fallback="").strip()
        self.category_theme = category_theme or (cat_cfg if cat_cfg else "Category Strategy")

        safe_brand = re.sub(r"\W+", "_", self.target_brand.strip())
        safe_theme = re.sub(r"\W+", "_", self.category_theme.strip())
        default_run_id = f"{safe_brand}_{safe_theme}" if safe_brand else "brand_presence_run"
        self.run_id = config.get("General", "run_id", fallback=default_run_id)

        self.output_language = config.get("Analysis", "output_language", fallback="Portuguese")
        outputs_str = config.get("Analysis", "requested_outputs", fallback="pdf,html,markdown")
        self.requested_outputs = [o.strip().lower() for o in outputs_str.split(",") if o.strip()]

        # Model Names with Gemini 3.7 Flash as primary
        models = get_model_names(self.config_path)
        self.model_name = config.get("Analysis", "pro_model_name", fallback=models.get("pro_model_name", "gemini-3.7-flash"))
        self.fallback_model = config.get("Analysis", "fallback_model_name", fallback=models.get("fallback_model_name", "gemini-3.6-flash"))

        prompt_rel = config.get("Analysis", "prompt_template_path", fallback="templates/prompts/brand_presence.txt")
        self.prompt_template_path = os.path.join(self.project_root, prompt_rel)

        # Output Directory
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        self.output_dir = output_dir or os.path.join(config_dir, "outputs", self.run_id)

    def calculate_share_of_voice(
        self,
        videos_df: pd.DataFrame,
        comments_df: pd.DataFrame,
        appearances_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.DataFrame, Dict[str, int]]:
        """Calculates Share of Voice (SOV) metrics for target brand vs competitors across text and appearances."""
        all_brands = [self.target_brand] + self.competitors
        brand_counts = {b: 0 for b in all_brands}

        text_corpus = []
        if not videos_df.empty:
            for _, row in videos_df.iterrows():
                title = str(row.get("title", ""))
                desc = str(row.get("description", ""))
                text_corpus.append(f"{title} {desc}")

        if not comments_df.empty:
            for comment in comments_df.get("comment_text", []):
                text_corpus.append(str(comment))

        full_text = " \n ".join(text_corpus).lower()

        for brand in all_brands:
            pattern = r"\b" + re.escape(brand.lower()) + r"\b"
            matches = len(re.findall(pattern, full_text))
            brand_counts[brand] = matches

        # Also incorporate brand detections from appearances timeline if available
        if appearances_df is not None and not appearances_df.empty and "brand_name" in appearances_df.columns:
            for _, app in appearances_df.iterrows():
                app_brand = str(app.get("brand_name", "")).strip()
                for b in all_brands:
                    if b.lower() == app_brand.lower():
                        brand_counts[b] += 1
                        break

        total_mentions = sum(brand_counts.values()) or 1
        sov_percentage = {brand: round((count / total_mentions) * 100, 2) for brand, count in brand_counts.items()}

        sov_df = pd.DataFrame([
            {"Brand": brand, "Mentions": count, "Share of Voice (%)": f"{sov_percentage[brand]}%"}
            for brand, count in brand_counts.items()
        ]).sort_values(by="Mentions", ascending=False)

        return sov_df, brand_counts

    def analyze_video_content(
        self,
        videos_df: pd.DataFrame,
        multimodal_df: Optional[pd.DataFrame] = None,
        appearances_df: Optional[pd.DataFrame] = None,
        transcripts_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Combines video metadata with rich multimodal intelligence (visual logos, spoken claims, creator stance,
        decision drivers, and whitespace signals) for the synthesis prompt.

        Returns:
            Tuple of (video_content_df, video_summary_prompt_string).
        """
        if videos_df.empty:
            return pd.DataFrame(), "Nenhum vídeo analisado."

        # Backward-compatibility fallback
        if multimodal_df is None and transcripts_df is not None:
            multimodal_df = transcripts_df

        all_brands = [self.target_brand] + self.competitors
        video_records = []
        summary_lines = []

        # Index multimodal records by video_id and title
        mm_by_id: Dict[str, Dict[str, Any]] = {}
        mm_by_title: Dict[str, Dict[str, Any]] = {}
        if multimodal_df is not None and not multimodal_df.empty:
            for _, mm_row in multimodal_df.iterrows():
                v_id = str(mm_row.get("video_id") or mm_row.get("videoId") or "").strip()
                v_title = str(mm_row.get("video_title") or mm_row.get("title") or "").strip().lower()
                row_dict = mm_row.to_dict()
                if v_id:
                    mm_by_id[v_id] = row_dict
                if v_title:
                    mm_by_title[v_title] = row_dict

        # Group appearances by video_id and title
        apps_by_id: Dict[str, List[Dict[str, Any]]] = {}
        apps_by_title: Dict[str, List[Dict[str, Any]]] = {}
        if appearances_df is not None and not appearances_df.empty:
            for _, app_row in appearances_df.iterrows():
                v_id = str(app_row.get("video_id") or app_row.get("videoId") or "").strip()
                v_title = str(app_row.get("video_title") or app_row.get("title") or "").strip().lower()
                app_dict = app_row.to_dict()
                if v_id:
                    apps_by_id.setdefault(v_id, []).append(app_dict)
                if v_title:
                    apps_by_title.setdefault(v_title, []).append(app_dict)

        channel_col = "channel" if "channel" in videos_df.columns else ("channelTitle" if "channelTitle" in videos_df.columns else "channel_title")
        views_col = "views" if "views" in videos_df.columns else "viewCount"
        likes_col = "likes" if "likes" in videos_df.columns else "likeCount"

        for idx, row in videos_df.iterrows():
            title = str(row.get("title", ""))
            desc = str(row.get("description", ""))[:300]
            channel = str(row.get(channel_col, "Unknown Channel"))
            video_id = str(row.get("videoId") or row.get("id") or row.get("video_id", "")).strip()

            raw_views = row.get(views_col, 0)
            try:
                views = int(raw_views) if pd.notna(raw_views) else 0
            except Exception:
                views = 0

            raw_likes = row.get(likes_col, 0)
            try:
                likes = int(raw_likes) if pd.notna(raw_likes) else 0
            except Exception:
                likes = 0

            url = str(row.get("url", f"https://www.youtube.com/watch?v={video_id}"))

            # Retrieve multimodal extraction record
            mm_data = mm_by_id.get(video_id) or mm_by_title.get(title.strip().lower(), {})
            video_apps = apps_by_id.get(video_id) or apps_by_title.get(title.strip().lower(), [])

            # Multimodal fields
            summary_content = mm_data.get("summary_of_content") or (desc[:180] + "...")
            creator_stance = mm_data.get("creator_stance") or mm_data.get("creator_editorial_stance") or "Criador Neutro de Categoria"
            features_valued = mm_data.get("features_valued_most") or "N/A"
            features_criticized = mm_data.get("features_criticized_or_irrelevant") or "N/A"
            whitespace_signals = mm_data.get("investment_whitespace_signals") or "N/A"
            spoken_claims = mm_data.get("spoken_key_claims") or mm_data.get("transcript_text") or "N/A"

            # Format visual appearances list
            visual_apps = [
                a for a in video_apps
                if str(a.get("modality", "")).lower() in ("visual", "both")
                or "visual" in str(a.get("appearance_type", "")).lower()
                or "logo" in str(a.get("appearance_type", "")).lower()
            ]
            if visual_apps:
                vis_items = []
                for va in visual_apps:
                    ts = va.get("timestamps") or va.get("timestamp") or "00:00"
                    b_name = va.get("brand_name", "")
                    app_t = va.get("appearance_type") or "Visual Logo"
                    ctx = va.get("context_summary") or va.get("context") or ""
                    vis_items.append(f"[{ts}] {b_name} ({app_t}{': ' + ctx if ctx else ''})")
                visual_appearances_str = "; ".join(vis_items)
            else:
                vis_count = mm_data.get("visual_appearances_count", 0)
                visual_appearances_str = f"{vis_count} aparições visuais detectadas" if vis_count else "Nenhuma aparição visual destacada"

            # Identify all mentioned brands
            mentioned_brands = []
            combined_text = f"{title} {desc} {summary_content} {spoken_claims}".lower()
            for brand in all_brands:
                if re.search(r"\b" + re.escape(brand.lower()) + r"\b", combined_text) or any(
                    brand.lower() == str(a.get("brand_name", "")).lower() for a in video_apps
                ):
                    mentioned_brands.append(brand)

            # Record for structured DataFrame
            video_records.append({
                "Video Title": title,
                "Channel": channel,
                "Views": views,
                "Likes": likes,
                "Brands Mentioned": ", ".join(mentioned_brands) if mentioned_brands else "None (Category Organic)",
                "Creator Stance": creator_stance,
                "Visual Brand Appearances": visual_appearances_str,
                "Spoken Claims / Transcripts": str(spoken_claims)[:300],
                "Features Valued": str(features_valued),
                "Features Criticized": str(features_criticized),
                "Whitespace Signals": str(whitespace_signals),
                "URL": url,
                "Spoken Transcript Excerpt": str(spoken_claims)[:250],
            })

            # Format Markdown Entry for Synthesis Prompt
            summary_lines.append(
                f"📹 **[{title}]({url})** | Canal: {channel} | Views: {views:,} | Likes: {likes:,}\n"
                f"   - **Resumo do Conteúdo**: {summary_content}\n"
                f"   - **Postura do Criador**: {creator_stance}\n"
                f"   - **👁️ Aparições Visuais**: {visual_appearances_str}\n"
                f"   - **🎙️ Declarações / Falas Relevantes**: {str(spoken_claims)[:350]}\n"
                f"   - **🌟 Atributos Mais Valorizados**: {features_valued}\n"
                f"   - **⚠️ Críticas & Desvantagens**: {features_criticized}\n"
                f"   - **💡 Sinais de Oportunidade / Whitespace**: {whitespace_signals}\n"
                f"   - **Marcas Detectadas**: {', '.join(mentioned_brands) if mentioned_brands else 'Nenhuma (Orgânico de Categoria)'}\n"
            )

        video_content_df = pd.DataFrame(video_records).sort_values(by="Views", ascending=False)
        video_summary_str = "\n".join(summary_lines)
        return video_content_df, video_summary_str

    def analyze_engagement_drivers(self, videos_df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
        """Identifies top vs bottom performing videos and analyzes engagement drivers."""
        if videos_df.empty:
            return pd.DataFrame(), "Insuficiente volume de vídeos para comparação de engajamento."

        views_col = "views" if "views" in videos_df.columns else "viewCount"
        likes_col = "likes" if "likes" in videos_df.columns else "likeCount"
        comments_col = "comments" if "comments" in videos_df.columns else "commentCount"
        channel_col = "channel" if "channel" in videos_df.columns else ("channelTitle" if "channelTitle" in videos_df.columns else "channel_title")

        df = videos_df.copy()
        df["views_num"] = pd.to_numeric(df.get(views_col, 0), errors="coerce").fillna(0)
        df["likes_num"] = pd.to_numeric(df.get(likes_col, 0), errors="coerce").fillna(0)
        df["comments_num"] = pd.to_numeric(df.get(comments_col, 0), errors="coerce").fillna(0)

        df["engagement_score"] = df["views_num"] + (df["likes_num"] * 10) + (df["comments_num"] * 5)
        df_sorted = df.sort_values(by="engagement_score", ascending=False).reset_index(drop=True)

        if len(df_sorted) == 1:
            top_quartile = df_sorted
            bottom_quartile = pd.DataFrame()
        else:
            q_size = max(1, len(df_sorted) // 4) if len(df_sorted) >= 4 else 1
            top_quartile = df_sorted.head(q_size)
            bottom_quartile = df_sorted.tail(q_size)

        driver_records = []
        for idx, row in top_quartile.iterrows():
            driver_records.append({
                "Performance Tier": "🔥 Top Performers (High Engagement)",
                "Video Title": row.get("title", ""),
                "Channel": row.get(channel_col, ""),
                "Views": int(row.get("views_num", 0)),
                "Likes": int(row.get("likes_num", 0)),
                "Comments": int(row.get("comments_num", 0)),
                "URL": row.get("url", ""),
            })

        for idx, row in bottom_quartile.iterrows():
            driver_records.append({
                "Performance Tier": "💤 Low Performers (Bottom Engagement)",
                "Video Title": row.get("title", ""),
                "Channel": row.get(channel_col, ""),
                "Views": int(row.get("views_num", 0)),
                "Likes": int(row.get("likes_num", 0)),
                "Comments": int(row.get("comments_num", 0)),
                "URL": row.get("url", ""),
            })

        drivers_df = pd.DataFrame(driver_records)

        summary = "### 🔥 VÍDEOS DE ALTO ENGAJAMENTO (TOP PERFORMERS):\n"
        for idx, row in top_quartile.iterrows():
            summary += (
                f"- **[{row.get('title', '')}]({row.get('url', '')})** | Canal: {row.get(channel_col, '')} | "
                f"Views: {int(row.get('views_num', 0)):,} | Likes: {int(row.get('likes_num', 0)):,}\n"
                f"  Descrição: {str(row.get('description', ''))[:150]}...\n\n"
            )

        if not bottom_quartile.empty:
            summary += "\n### 💤 VÍDEOS DE BAIXO ENGAJAMENTO (BOTTOM PERFORMERS):\n"
            for idx, row in bottom_quartile.iterrows():
                summary += (
                    f"- **[{row.get('title', '')}]({row.get('url', '')})** | Canal: {row.get(channel_col, '')} | "
                    f"Views: {int(row.get('views_num', 0)):,} | Likes: {int(row.get('likes_num', 0)):,}\n"
                    f"  Descrição: {str(row.get('description', ''))[:150]}...\n\n"
                )

        return drivers_df, summary

    def map_creators(
        self,
        videos_df: pd.DataFrame,
        multimodal_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Maps YouTube creators, their video counts, views, and brand alignment."""
        if videos_df.empty:
            return pd.DataFrame()

        all_brands = [self.target_brand] + self.competitors
        creator_records = []

        channel_col = "channel" if "channel" in videos_df.columns else ("channelTitle" if "channelTitle" in videos_df.columns else "channel_title")
        views_col = "views" if "views" in videos_df.columns else "viewCount"

        if channel_col not in videos_df.columns:
            return pd.DataFrame()

        # Build creator stances mapping from multimodal_df if available
        creator_stances: Dict[str, List[str]] = {}
        if multimodal_df is not None and not multimodal_df.empty and "channel_name" in multimodal_df.columns:
            for _, mm in multimodal_df.iterrows():
                ch = str(mm.get("channel_name", "")).strip()
                st = str(mm.get("creator_stance") or mm.get("creator_editorial_stance") or "").strip()
                if ch and st:
                    creator_stances.setdefault(ch.lower(), []).append(st)

        grouped = videos_df.groupby(channel_col)
        for channel_name, group in grouped:
            video_count = len(group)

            raw_views = group[views_col].sum() if views_col in group.columns else 0
            try:
                total_views = int(raw_views) if pd.notna(raw_views) else 0
            except Exception:
                total_views = 0

            # Find top video for this creator
            sorted_group = group.sort_values(by=views_col, ascending=False) if views_col in group.columns else group
            top_video_title = sorted_group.iloc[0]["title"] if "title" in sorted_group.columns and len(sorted_group) > 0 else "N/A"
            try:
                top_video_views = int(sorted_group.iloc[0][views_col]) if views_col in sorted_group.columns and len(sorted_group) > 0 else 0
            except Exception:
                top_video_views = 0

            titles = group["title"].fillna("").astype(str).tolist() if "title" in group.columns else []
            descriptions = group["description"].fillna("").astype(str).tolist() if "description" in group.columns else []
            channel_text = (" ".join(titles) + " " + " ".join(descriptions)).lower()

            mentioned_brands = []
            for brand in all_brands:
                if re.search(r"\b" + re.escape(brand.lower()) + r"\b", channel_text):
                    mentioned_brands.append(brand)

            # Check stances
            channel_stances = creator_stances.get(str(channel_name).strip().lower(), [])
            stance_summary = "; ".join(set(channel_stances)) if channel_stances else ""

            creator_type = "Criador Neutro de Categoria"
            collab_strategy = "Oceano Azul / Oportunidade Inexplorada: Oferecer patrocínio de produto e convite para teste de receitas/demos dedicados."

            if self.target_brand in mentioned_brands or any("promoter" in s.lower() for s in channel_stances):
                creator_type = f"Promotor da Marca ({self.target_brand})"
                collab_strategy = f"Embaixador de Marca: Patrocínio fixo de canal, cupom de desconto exclusivo e co-criação de conteúdo de alta conversão."
            elif mentioned_brands or any("competitor" in s.lower() for s in channel_stances):
                comps_detected = [b for b in mentioned_brands if b != self.target_brand] or self.competitors
                creator_type = f"Alinhado a Concorrente ({', '.join(comps_detected)})"
                collab_strategy = f"Conquista de Influenciador: Envio de press kit comparativo, teste cego e oferta de diferencial competitivo superior a {', '.join(comps_detected)}."

            creator_records.append({
                "Channel Name": channel_name,
                "Videos Discovered": video_count,
                "Total Views": total_views,
                "Top Video Title": top_video_title,
                "Top Video Views": top_video_views,
                "Mentioned Brands": ", ".join(mentioned_brands) if mentioned_brands else "None",
                "Creator Alignment": creator_type,
                "Multimodal Stance": stance_summary or creator_type,
                "Brand Collaboration Strategy": collab_strategy,
            })

        creators_df = pd.DataFrame(creator_records).sort_values(by="Total Views", ascending=False)
        return creators_df

    def analyze_brand_presence(
        self,
        videos_df: Optional[pd.DataFrame] = None,
        comments_df: Optional[pd.DataFrame] = None,
        multimodal_df: Optional[pd.DataFrame] = None,
        appearances_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[str, str, str]:
        """
        Executes the 2-Stage Analysis Pipeline:
          Stage 1: Parallel Multimodal Video Extraction via VideoMultimodalExtractor
          Stage 2: Macro Strategic Synthesis via Gemini 3.7 Flash (text-only prompt)

        Returns:
            Tuple of (final_md_path, final_html_path, sov_csv_path).
        """
        output_dir = self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        safe_brand = re.sub(r"\W+", "_", self.target_brand.strip()) or "brand"

        # Discover video and comment CSVs if not explicitly passed
        if videos_df is None:
            video_files = glob.glob(os.path.join(output_dir, "*_discovered_videos.csv"))
            videos_df = pd.read_csv(video_files[0]) if video_files else pd.DataFrame()

        if comments_df is None:
            comment_files = glob.glob(os.path.join(output_dir, "*_raw_comments.csv"))
            comments_df = pd.read_csv(comment_files[0]) if comment_files else pd.DataFrame()

        # -------------------------------------------------------------------
        # Stage 1: Multimodal Extraction (if not pre-provided)
        # -------------------------------------------------------------------
        if multimodal_df is None or multimodal_df.empty:
            # Check if multimodal analysis CSV already exists on disk
            mm_files = glob.glob(os.path.join(output_dir, "*_multimodal_analysis.csv"))
            app_files = glob.glob(os.path.join(output_dir, "*_brand_appearances_timeline.csv"))

            max_v = max(getattr(self, "max_results", 30), 30)
            if mm_files and os.path.exists(mm_files[0]):
                cached_df = pd.read_csv(mm_files[0])
                if len(cached_df) >= max_v and (videos_df is None or len(videos_df) <= len(cached_df)):
                    logger.info(f"Loading cached multimodal extraction ({len(cached_df)} videos) from {mm_files[0]}...")
                    multimodal_df = cached_df
                    if app_files and os.path.exists(app_files[0]):
                        appearances_df = pd.read_csv(app_files[0])
                    else:
                        appearances_df = pd.DataFrame()
                else:
                    logger.info(f"Cached multimodal file has {len(cached_df)} videos, but {max_v} requested. Invalidation triggered -> Running fresh extraction.")
                    multimodal_df = None
            
            if (multimodal_df is None or multimodal_df.empty) and not videos_df.empty:
                print(f"\n--- [Stage 1] Extração Multimodal em Paralelo ({min(len(videos_df), max_v)} vídeos) ---")
                extractor = VideoMultimodalExtractor(
                    config_path=self.config_path,
                    output_dir=output_dir,
                    target_brand=self.target_brand,
                    competitors=self.competitors,
                    category_theme=self.category_theme,
                )
                multimodal_df, appearances_df = extractor.process_videos_df(videos_df, max_videos=max_v)
            else:
                multimodal_df = pd.DataFrame()
                appearances_df = pd.DataFrame()

        # Save legacy transcripts file for backward compatibility if multimodal_df exists
        if not multimodal_df.empty and "transcript_text" in multimodal_df.columns:
            tr_csv_path = os.path.join(output_dir, f"{safe_brand}_video_transcripts.csv")
            multimodal_df.to_csv(tr_csv_path, index=False)
            logger.info(f"Saved Video Transcripts to '{tr_csv_path}'")

        # -------------------------------------------------------------------
        # Stage 2: Video Content Breakdown & Engagement Drivers
        # -------------------------------------------------------------------
        print(f"\n--- [Stage 2] Analisando Conteúdo dos Vídeos & Inteligência Multimodal ({len(videos_df)} vídeos) ---")
        video_content_df, video_summary_str = self.analyze_video_content(
            videos_df,
            multimodal_df=multimodal_df,
            appearances_df=appearances_df,
        )
        if not video_content_df.empty:
            video_csv_path = os.path.join(output_dir, f"{safe_brand}_video_content_breakdown.csv")
            video_content_df.to_csv(video_csv_path, index=False)
            print(f"SUCCESS: Saved Video Content Breakdown to '{video_csv_path}'")

        # Persist appearances timeline if available
        if appearances_df is not None and not appearances_df.empty:
            app_csv_path = os.path.join(output_dir, f"{safe_brand}_brand_appearances_timeline.csv")
            appearances_df.to_csv(app_csv_path, index=False)
            print(f"SUCCESS: Saved Brand Appearances Timeline to '{app_csv_path}'")

        print(f"\n--- Analisando Fatores de Engajamento (Top vs Bottom Performers) ---")
        drivers_df, engagement_summary_str = self.analyze_engagement_drivers(videos_df)
        if not drivers_df.empty:
            drivers_csv_path = os.path.join(output_dir, f"{safe_brand}_high_engagement_drivers.csv")
            drivers_df.to_csv(drivers_csv_path, index=False)
            print(f"SUCCESS: Saved High Engagement Drivers to '{drivers_csv_path}'")

        print(f"\n--- Calculando Share of Voice para '{self.target_brand}' vs {self.competitors} ---")
        sov_df, brand_counts = self.calculate_share_of_voice(videos_df, comments_df, appearances_df=appearances_df)
        print(sov_df.to_string(index=False))

        sov_csv_path = os.path.join(output_dir, f"{safe_brand}_share_of_voice.csv")
        sov_df.to_csv(sov_csv_path, index=False)

        print(f"\n--- Mapeando Criadores e Canais para Categoria '{self.category_theme}' ---")
        creators_df = self.map_creators(videos_df, multimodal_df=multimodal_df)
        if not creators_df.empty:
            print(creators_df.head(10).to_string(index=False))
            creators_csv_path = os.path.join(output_dir, f"{safe_brand}_creator_mapping.csv")
            creators_df.to_csv(creators_csv_path, index=False)

        # Smart Comment Pre-filtering & Token Budget Capping
        comments_sample_str = "Nenhum comentário extraído."
        if not comments_df.empty and "comment_text" in comments_df.columns:
            valid_comments = comments_df[comments_df["comment_text"].astype(str).str.len() > 12].copy()
            all_brands = [self.target_brand] + self.competitors
            brand_pattern = r"|".join([r"\b" + re.escape(b) + r"\b" for b in all_brands])

            brand_comments = valid_comments[valid_comments["comment_text"].astype(str).str.contains(brand_pattern, case=False, regex=True)]
            other_comments = valid_comments[~valid_comments.index.isin(brand_comments.index)]

            sample_brand = brand_comments.head(80)
            sample_other = other_comments.sample(min(40, len(other_comments)), random_state=42) if not other_comments.empty else pd.DataFrame()

            combined_sample = pd.concat([sample_brand, sample_other])["comment_text"].tolist()
            comments_sample_str = "\n- " + "\n- ".join(combined_sample)

        # Read Prompt Template
        with open(self.prompt_template_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()

        prompt = prompt_template.format(
            category_theme=self.category_theme,
            target_brand=self.target_brand,
            competitors=", ".join(self.competitors),
            total_videos=len(videos_df),
            total_comments=len(comments_df),
            videos_summary=video_summary_str[:16000],
            engagement_summary=engagement_summary_str[:12000],
            sov_summary=self._df_to_markdown(sov_df),
            creators_summary=self._df_to_markdown(creators_df.head(15)) if not creators_df.empty else "Nenhum criador mapeado.",
            comments_sample=comments_sample_str[:8000],
            output_language=self.output_language,
        )

        # -------------------------------------------------------------------
        # Stage 2: Master Text-Only Macro Strategic Synthesis
        # (Zero monolithic raw video URL streaming into the macro prompt)
        # -------------------------------------------------------------------
        print(f"\n--- [Stage 2] Macro Síntese Estratégica via Gemini ({self.model_name}) ---")
        try:
            response = generate_content_with_retry(
                client=self.client,
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3),
                fallback_model=self.fallback_model,
                max_retries=3,
                retry_delay_sec=2.0,
            )
            report_text = response.text or ""
        except Exception as e:
            logger.error(f"Macro synthesis failed: {e}")
            report_text = f"# Relatório de Presença de Marca ({self.target_brand})\n\nErro na geração de síntese: {e}"

        # Assemble Full Markdown Report with Data Appendices
        full_report_md = (
            report_text
            + "\n\n## 📈 Apêndice: Tabelas Quantitativas de Inteligência Multimodal & SOV\n\n"
            + "### Share of Voice Integrado (%)\n"
            + self._df_to_markdown(sov_df)
        )
        if not drivers_df.empty:
            full_report_md += "\n\n### Comparativo de Engajamento (Top vs Bottom Performers)\n" + self._df_to_markdown(drivers_df)
        if not video_content_df.empty:
            full_report_md += "\n\n### Vídeos Analisados na Categoria (Top 15)\n" + self._df_to_markdown(video_content_df.head(15))
        if not creators_df.empty:
            full_report_md += "\n\n### Top Criadores Mapeados na Categoria\n" + self._df_to_markdown(creators_df.head(15))
        if appearances_df is not None and not appearances_df.empty:
            full_report_md += "\n\n### Linha do Tempo de Aparições de Marcas (Amostra Visual & Falada)\n" + self._df_to_markdown(appearances_df.head(20))

        final_md_file = os.path.join(output_dir, f"{safe_brand}_final_analysis_report.md")
        md_file = os.path.join(output_dir, f"{safe_brand}_brand_presence_report.md")

        # Save Markdown if requested
        if "markdown" in self.requested_outputs or "pdf" in self.requested_outputs:
            with open(final_md_file, "w", encoding="utf-8") as f:
                f.write(full_report_md)
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(full_report_md)
            print(f"SUCCESS: Saved Final Analysis Report to '{final_md_file}'")

        final_html_file = os.path.join(output_dir, f"{safe_brand}_final_analysis_report.html")
        html_file = os.path.join(output_dir, f"{safe_brand}_brand_presence_report.html")

        if "html" in self.requested_outputs:
            import markdown

            html_body = markdown.markdown(full_report_md, extensions=["tables", "fenced_code"])
            html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Relatório Estratégico de Inteligência Multimodal: {self.target_brand} - {self.category_theme}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; max-width: 1050px; margin: 0 auto; padding: 25px; background-color: #f8f9fa; }}
        h1, h2, h3 {{ color: #0f172a; font-weight: 700; }}
        h1 {{ border-bottom: 3px solid #2563eb; padding-bottom: 12px; color: #1e3a8a; }}
        h2 {{ border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; margin-top: 30px; color: #1e40af; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ border: 1px solid #cbd5e1; padding: 12px; text-align: left; }}
        th {{ background-color: #2563eb; color: white; }}
        tr:nth-child(even) {{ background-color: #f1f5f9; }}
        code, pre {{ background-color: #e2e8f0; border-radius: 4px; padding: 2px 6px; font-size: 0.9em; }}
    </style>
</head>
<body>
    {html_body}
</body>
</html>"""
            with open(final_html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"SUCCESS: Saved Final Analysis HTML Report to '{final_html_file}'")
        else:
            print("[SKIP] HTML Report generation skipped (not selected in output formats).")

        return final_md_file, final_html_file, sov_csv_path

