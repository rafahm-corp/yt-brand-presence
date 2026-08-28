import streamlit as st
import os
import sys
import glob
import pandas as pd
import configparser
import subprocess
import re
from dotenv import set_key, load_dotenv

# Page Configuration
st.set_page_config(
    page_title="YouTube Brand Presence & Share of Voice Tracker",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed"
)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from briefing_planner import BriefingPlanner

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.ini")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

load_dotenv(ENV_PATH)

config = configparser.ConfigParser(interpolation=None)
if os.path.exists(CONFIG_PATH):
    config.read(CONFIG_PATH)

def get_config_val(section, key, fallback=""):
    return config.get(section, key, fallback=fallback)

# Custom Styling
st.markdown("""
    <style>
        .main-header { font-size: 2.2rem; font-weight: 700; color: #0f172a; margin-bottom: 0.2rem; }
        .sub-header { font-size: 1.1rem; color: #475569; margin-bottom: 1.5rem; }
        .reasoning-box { background-color: #eff6ff; border-left: 5px solid #2563eb; padding: 1.2rem; border-radius: 8px; margin-bottom: 1.5rem; }
        .info-card { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🔴 YouTube Brand Presence & Share of Voice Tracker</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-Powered Brand Intelligence: Share of Voice %, YouTube Creators Leaderboard & Blue Ocean Opportunities</div>', unsafe_allow_html=True)

# Initialize Session State
if "config_initialized" not in st.session_state:
    st.session_state.strategy_version = 0
    st.session_state.briefing_input = ""
    st.session_state.target_brand = get_config_val("Target", "target_brand", "")
    st.session_state.competitors = get_config_val("Target", "competitors", "")
    st.session_state.category_theme = get_config_val("Category", "category_theme", "")
    st.session_state.search_queries = get_config_val("Category", "search_queries", "")
    st.session_state.search_modifiers = get_config_val("Crawler", "search_modifiers", "review, opiniao, comparativo, dicas, vale a pena, passo a passo")
    st.session_state.exclude_keywords = get_config_val("Crawler", "exclude_keywords", "gameplay, ao vivo, live, futebol, musica, gta")
    st.session_state.min_view_count = int(get_config_val("Crawler", "min_view_count", "1000"))
    st.session_state.sort_by = get_config_val("Crawler", "sort_by", "relevance")
    st.session_state.video_type = get_config_val("Crawler", "video_type", "both")
    st.session_state.max_results = int(get_config_val("Category", "max_results", "20"))
    st.session_state.max_comments = int(get_config_val("Category", "max_comments_per_video", "30"))
    st.session_state.max_video_duration = int(get_config_val("Crawler", "max_video_duration_minutes", "30"))
    st.session_state.region_code = get_config_val("Category", "region_code", "BR")
    st.session_state.output_language = get_config_val("Analysis", "output_language", "Portuguese")
    raw_outputs = get_config_val("Analysis", "requested_outputs", "pdf,html,markdown")
    st.session_state.requested_outputs = [o.strip() for o in raw_outputs.split(',') if o.strip()]
    st.session_state.additional_context = get_config_val("Analysis", "additional_context", "")
    st.session_state.deep_thinking_reasoning = ""
    st.session_state.config_initialized = True

def save_settings_to_config():
    save_config = configparser.ConfigParser(interpolation=None)
    for sec in ["Target", "Category", "Crawler", "Analysis", "Drive", "General"]:
        save_config.add_section(sec)
        
    save_config.set("Target", "target_brand", st.session_state.target_brand)
    save_config.set("Target", "competitors", st.session_state.competitors)
    save_config.set("Category", "category_theme", st.session_state.category_theme)
    save_config.set("Category", "search_queries", st.session_state.search_queries)
    save_config.set("Category", "search_terms", st.session_state.category_theme)
    save_config.set("Category", "max_results", str(st.session_state.max_results))
    save_config.set("Category", "max_comments_per_video", str(st.session_state.max_comments))
    save_config.set("Category", "region_code", st.session_state.region_code)
    
    save_config.set("Crawler", "search_terms", st.session_state.category_theme)
    save_config.set("Crawler", "search_queries", st.session_state.search_queries)
    save_config.set("Crawler", "search_modifiers", st.session_state.search_modifiers)
    save_config.set("Crawler", "exclude_keywords", st.session_state.exclude_keywords)
    save_config.set("Crawler", "min_view_count", str(st.session_state.min_view_count))
    save_config.set("Crawler", "sort_by", st.session_state.sort_by)
    save_config.set("Crawler", "video_type", st.session_state.video_type)
    save_config.set("Crawler", "max_results", str(st.session_state.max_results))
    save_config.set("Crawler", "max_comments_per_video", str(st.session_state.max_comments))
    save_config.set("Crawler", "max_video_duration_minutes", str(st.session_state.max_video_duration))
    save_config.set("Crawler", "region_code", st.session_state.region_code)
    
    save_config.set("Analysis", "output_language", st.session_state.output_language)
    save_config.set("Analysis", "requested_outputs", ",".join(st.session_state.requested_outputs))
    save_config.set("Analysis", "additional_context", st.session_state.additional_context)
    
    save_config.set("Drive", "folder_id", "1Q1oDloZ3pVboA384DNU4g9vL02ERqThL")
    save_config.set("Drive", "resource_key", "0-UEy66XMGR6YJCtE4ho850A")
    
    safe_theme = re.sub(r'\W+', '', st.session_state.category_theme.replace(' ', '_'))
    safe_brand = re.sub(r'\W+', '', st.session_state.target_brand.replace(' ', '_'))
    save_config.set("General", "run_id", f"{safe_brand}_{safe_theme}")
    
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        save_config.write(f)

# Clean Tabs Workflow
tab1, tab2, tab3 = st.tabs([
    "🎯 Campaign Setup & AI Briefing",
    "📊 Final Analysis",
    "📁 Google Drive Backup"
])

# UNIFIED TAB 1: AI Briefing + Pipeline Configuration
with tab1:
    st.subheader("1. 🧠 AI Deep Thinking Briefing Generator")
    st.markdown("Enter your campaign briefing or research objective below. Gemini 3.6 Flash will **deep-think** to formulate your search strategy, identify target brands, competitors, and high-intent search terms.")
    
    briefing_text_input = st.text_area(
        "Campaign Briefing / Research Objective",
        height=130,
        value=st.session_state.briefing_input,
        placeholder="e.g. Teremos um workshop com Nestlé nesta quarta pela manhã, e há uma demanda de melhoria criativa..."
    )
    st.session_state.briefing_input = briefing_text_input
    
    col_think1, col_think2 = st.columns([3, 1])
    with col_think2:
        enable_search = st.checkbox("Enable Google Search Grounding", value=True)
        
    if st.button("🧠 Generate Strategy with Gemini Deep Thinking", type="primary", use_container_width=True):
        if not st.session_state.briefing_input.strip():
            st.warning("Please enter a briefing description first!")
        else:
            with st.spinner("Gemini Deep Thinking in progress... Analyzing search strategy and market context..."):
                try:
                    planner = BriefingPlanner(config_path=CONFIG_PATH)
                    strategy = planner.plan_campaign(
                        campaign_briefing=st.session_state.briefing_input,
                        output_language=st.session_state.output_language,
                        region_code=st.session_state.region_code,
                        additional_context=st.session_state.additional_context,
                        enable_google_search=enable_search
                    )
                    
                    if isinstance(strategy, dict):
                        # Extract Target Brand
                        t_brand = strategy.get("target_brand", st.session_state.target_brand)
                        st.session_state.target_brand = t_brand
                        
                        # Extract Competitors
                        comps = strategy.get("competitors", [])
                        comps_str = ", ".join(comps) if isinstance(comps, list) else str(comps)
                        st.session_state.competitors = comps_str
                        
                        # Extract Category Theme
                        cat_t = strategy.get("category_theme", st.session_state.category_theme)
                        st.session_state.category_theme = cat_t
                        
                        # Extract Search Queries
                        queries = strategy.get("search_queries", [])
                        queries_str = "; ".join(queries) if isinstance(queries, list) else str(queries)
                        st.session_state.search_queries = queries_str
                        
                        # Extract Search Modifiers
                        mods = strategy.get("search_modifiers", [])
                        st.session_state.search_modifiers = ", ".join(mods) if isinstance(mods, list) else str(mods)
                        
                        # Extract Exclude Keywords
                        excl = strategy.get("exclude_keywords", [])
                        excl_str = ", ".join(excl) if isinstance(excl, list) else str(excl)
                        st.session_state.exclude_keywords = excl_str
                        
                        st.session_state.deep_thinking_reasoning = strategy.get("strategic_reasoning", "")
                        st.session_state.additional_context = strategy.get("additional_context_for_analysis", "")
                        
                        # Increment strategy version to force widget key invalidation & re-render input boxes with new AI strategy values!
                        st.session_state.strategy_version += 1
                        
                        save_settings_to_config()
                        st.success(f"✨ Gemini Deep Thinking Strategy Formulated for '{t_brand}' & Applied to Pipeline Configuration!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error during Gemini Deep Thinking: {e}")

    if st.session_state.deep_thinking_reasoning:
        st.markdown(f"""
        <div class="reasoning-box">
            <h4>💡 Gemini Strategic Reasoning & Deep Thinking</h4>
            <p>{st.session_state.deep_thinking_reasoning}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("2. ⚙️ Pipeline Configuration & AI Parameter Review")
    st.caption("All parameters below are automatically populated by Gemini Deep Thinking. You can fine-tune them before executing the pipeline.")
    
    v = st.session_state.strategy_version
    
    col1, col2 = st.columns(2)
    with col1:
        target_brand_val = st.text_input("Target Brand Name", value=st.session_state.target_brand, key=f"tb_{v}")
        competitors_val = st.text_input("Competitors (comma separated)", value=st.session_state.competitors, key=f"comp_{v}")
        category_theme_val = st.text_input("Category Theme / Topic", value=st.session_state.category_theme, key=f"cat_{v}")
        search_queries_val = st.text_area("Search Queries (semi-colon separated)", value=st.session_state.search_queries, key=f"sq_{v}")
        
    with col2:
        max_results_val = st.slider("Max Videos to Discover", min_value=5, max_value=100, step=5, key=f"mr_v2_{v}", help="Select between 5 and 100 videos for full Share of Voice analysis.")
        max_duration_val = st.slider("Max Video Duration (Minutes)", min_value=5, max_value=120, step=5, key=f"mvd_v2_{v}", help="Token Saver: Skip videos longer than this limit (e.g. 3-hour podcasts/live streams).")
        max_comments_val = st.slider("Max Comments per Video", min_value=10, max_value=50, step=10, key=f"mc_v2_{v}")
        
        rc_opts = ["BR", "US", "ES", "MX", "AR", "CL"]
        rc_idx = rc_opts.index(st.session_state.region_code) if st.session_state.region_code in rc_opts else 0
        region_code_val = st.selectbox("Region Code", rc_opts, index=rc_idx, key=f"rc_{v}")
        
        ol_opts = ["Portuguese", "English", "Spanish"]
        ol_idx = ol_opts.index(st.session_state.output_language) if st.session_state.output_language in ol_opts else 0
        output_language_val = st.selectbox("Report Language", ol_opts, index=ol_idx, key=f"ol_{v}")

    # Quality Pre-Filtering Section
    with st.expander("🛡️ Quality Pre-Filtering & Noise Control (Exclusions, Thresholds & Sorting)", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            min_view_count_val = st.number_input(
                "Minimum View Count Threshold", 
                min_value=0, 
                max_value=100000, 
                value=st.session_state.min_view_count, 
                step=500,
                key=f"mvc_{v}",
                help="Videos with fewer views than this threshold will be automatically filtered out."
            )
            sort_by_opts = ["viewCount", "relevance", "engagement", "date"]
            sort_by_idx = sort_by_opts.index(st.session_state.sort_by) if st.session_state.sort_by in sort_by_opts else 0
            sort_by_val = st.selectbox(
                "Video Ranking & Selection Order",
                sort_by_opts,
                index=sort_by_idx,
                key=f"sb_{v}",
                help="viewCount = Highest Views First (Recommended); engagement = Likes+Comments; relevance = YouTube Relevance."
            )
        with col_f2:
            video_type_opts = ["videos", "both", "shorts"]
            video_type_idx = video_type_opts.index(st.session_state.video_type) if st.session_state.video_type in video_type_opts else 0
            video_type_val = st.selectbox(
                "Video Format Filter",
                video_type_opts,
                index=video_type_idx,
                key=f"vt_{v}",
                help="videos = Standard Long-Form Videos Only (Recommended); shorts = Shorts Only; both = All Formats."
            )
            exclude_keywords_val = st.text_input(
                "Exclude Negative Keywords (comma separated)",
                value=st.session_state.exclude_keywords,
                key=f"excl_{v}",
                help="Videos containing these words in their title will be automatically excluded."
            )

    requested_outputs_val = st.multiselect(
        "Select Output Formats to Generate", 
        ["pdf", "html", "markdown"], 
        default=st.session_state.requested_outputs if st.session_state.requested_outputs else ["pdf", "html", "markdown"], 
        key=f"out_{v}",
        help="Unchecking formats skips their generation to save time and API costs (e.g. unchecking 'pdf' skips slide image rendering)."
    )
    
    if st.button("🚀 Execute Brand Presence Pipeline", type="primary", use_container_width=True):
        # Sync widget values to session state
        st.session_state.target_brand = target_brand_val
        st.session_state.competitors = competitors_val
        st.session_state.category_theme = category_theme_val
        st.session_state.search_queries = search_queries_val
        st.session_state.max_results = max_results_val
        st.session_state.max_comments = max_comments_val
        st.session_state.max_video_duration = max_duration_val
        st.session_state.region_code = region_code_val
        st.session_state.output_language = output_language_val
        st.session_state.min_view_count = min_view_count_val
        st.session_state.sort_by = sort_by_val
        st.session_state.video_type = video_type_val
        st.session_state.exclude_keywords = exclude_keywords_val
        st.session_state.requested_outputs = requested_outputs_val
        
        save_settings_to_config()
        
        # Clean previous cached CSV artifacts for this run to force 100% fresh video discovery & extraction
        safe_brand = re.sub(r'\W+', '', st.session_state.target_brand.replace(' ', '_'))
        run_out_dir = os.path.join(PROJECT_ROOT, 'outputs', safe_brand)
        if os.path.exists(run_out_dir):
            for old_file in os.listdir(run_out_dir):
                if old_file.endswith(".csv"):
                    try:
                        os.remove(os.path.join(run_out_dir, old_file))
                    except Exception as e:
                        pass

        status_container = st.status(f"Executing Brand Presence Pipeline for '{st.session_state.target_brand}'...", expanded=True)
        log_expander = st.expander("Live Process Terminal Log", expanded=False)
        log_text = log_expander.empty()
        
        cmd = [sys.executable, "main.py", "all", "--config", CONFIG_PATH]
        process = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        stdout_lines = []
        for line in iter(process.stdout.readline, ''):
            stdout_lines.append(line)
            log_text.code("".join(stdout_lines[-30:]))
            if "STEP 1: CATEGORY THEME VIDEO SEARCH" in line:
                status_container.write("Step 1/5: Discovering Category YouTube Videos...")
            elif "STEP 2: AUDIENCE COMMENTS EXTRACTION" in line:
                status_container.write("Step 2/5: Harvesting Customer Comments...")
            elif "STEP 3" in line or "SHARE OF VOICE" in line:
                status_container.write("Step 3/5: Share of Voice & Brand Presence Analysis...")
            elif "Stage 1/2" in line or "PARALLEL MULTIMODAL" in line:
                status_container.write("Step 3/5 [Stage 1/2]: Processing Video Frames & Transcripts (Gemini Multimodal)...")
            elif "Stage 2/2" in line or "Strategic Macro Synthesis" in line:
                status_container.write("Step 3/5 [Stage 2/2]: Synthesizing Brand Share of Voice & Executive Report...")
            elif "Processing video" in line:
                status_container.write(f"Step 3/5: AI Multimodal Processing - {line.strip()}")
            elif "STEP 4: EXECUTIVE PDF PRESENTATION DECK GENERATION" in line:
                status_container.write("Step 4/5: Generating Executive Presentation Slides & PDF Deck...")
            elif "Processando Slide" in line:
                status_container.write(f"Step 4/5: Designing Slide Deck - {line.strip()}")
            elif "STEP 5: GOOGLE DRIVE BACKUP" in line:
                status_container.write("Step 5/5: Uploading Output Files & Verifying Google Drive Backups...")
            elif "SUCCESS: Verification passed" in line:
                status_container.write("✅ Google Drive Backups Verified Successfully!")

        process.stdout.close()
        return_code = process.wait()
        
        if return_code == 0:
            status_container.update(label=f"✨ Final Analysis Pipeline for '{st.session_state.target_brand}' Completed Successfully!", state="complete")
            st.balloons()
        else:
            status_container.update(label="❌ Pipeline Failed. Check Terminal Log.", state="error")

# TAB 2: Final Analysis
with tab2:
    st.subheader(f"📊 Final Analysis & Findings: {st.session_state.target_brand}")
    
    safe_theme = re.sub(r'\W+', '', st.session_state.category_theme.replace(' ', '_'))
    safe_brand = re.sub(r'\W+', '', st.session_state.target_brand.replace(' ', '_'))
    run_id_cfg = config.get("General", "run_id", fallback="")
    
    # Resolve run directory
    possible_dirs = [
        os.path.join(PROJECT_ROOT, "outputs", run_id_cfg) if run_id_cfg else None,
        os.path.join(PROJECT_ROOT, "outputs", f"{safe_brand}_{safe_theme}"),
        os.path.join(PROJECT_ROOT, "outputs", f"{safe_brand}_{safe_theme}".strip('_')),
    ]
    run_dir = next((d for d in possible_dirs if d and os.path.exists(d)), os.path.join(PROJECT_ROOT, "outputs", f"{safe_brand}_{safe_theme}"))
    
    def find_file(filenames):
        if not os.path.exists(run_dir):
            return None
        for fn in filenames:
            direct = os.path.join(run_dir, fn)
            if os.path.exists(direct):
                return direct
            matches = glob.glob(os.path.join(run_dir, fn))
            if matches:
                return matches[0]
        return None

    presentation_pdf = find_file([f"{st.session_state.target_brand}_presentation.pdf", f"{safe_brand}_presentation.pdf", "*_presentation.pdf"])
    final_report_html = find_file([f"{st.session_state.target_brand}_final_analysis_report.html", f"{safe_brand}_final_analysis_report.html", "*_final_analysis_report.html", "*_brand_presence_report.html"])
    final_report_md = find_file([f"{st.session_state.target_brand}_final_analysis_report.md", f"{safe_brand}_final_analysis_report.md", "*_final_analysis_report.md", "*_brand_presence_report.md"])
    
    multimodal_csv = find_file([f"{st.session_state.target_brand}_multimodal_analysis.csv", f"{safe_brand}_multimodal_analysis.csv", "*_multimodal_analysis.csv"])
    appearances_csv = find_file([f"{st.session_state.target_brand}_brand_appearances_timeline.csv", f"{safe_brand}_brand_appearances_timeline.csv", "*_brand_appearances_timeline.csv"])
    sov_csv = find_file([f"{st.session_state.target_brand}_share_of_voice.csv", f"{safe_brand}_share_of_voice.csv", "*_share_of_voice.csv"])
    creators_csv = find_file([f"{st.session_state.target_brand}_creator_mapping.csv", f"{safe_brand}_creator_mapping.csv", "*_creator_mapping.csv"])
    video_content_csv = find_file([f"{st.session_state.target_brand}_video_content_breakdown.csv", f"{safe_brand}_video_content_breakdown.csv", "*_video_content_breakdown.csv"])
    drivers_csv = find_file([f"{st.session_state.target_brand}_high_engagement_drivers.csv", f"{safe_brand}_high_engagement_drivers.csv", "*_high_engagement_drivers.csv"])

    # Interactive Multimodal KPIs
    if multimodal_csv or appearances_csv or sov_csv:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_vids = 0
        vis_count = 0
        spk_count = 0
        top_sov = "N/A"
        
        if multimodal_csv and os.path.exists(multimodal_csv):
            m_df = pd.read_csv(multimodal_csv)
            total_vids = len(m_df)
            if "visual_appearances_count" in m_df.columns:
                vis_count = int(m_df["visual_appearances_count"].sum())
            if "spoken_appearances_count" in m_df.columns:
                spk_count = int(m_df["spoken_appearances_count"].sum())
                
        if appearances_csv and os.path.exists(appearances_csv):
            app_df_kpi = pd.read_csv(appearances_csv)
            if vis_count == 0:
                vis_count = sum(1 for _, r in app_df_kpi.iterrows() if str(r.get("modality", "")).lower() in ("visual", "both") or "visual" in str(r.get("appearance_type", "")).lower())
            if spk_count == 0:
                spk_count = sum(1 for _, r in app_df_kpi.iterrows() if str(r.get("modality", "")).lower() in ("spoken", "both") or "spoken" in str(r.get("appearance_type", "")).lower())
                
        if sov_csv and os.path.exists(sov_csv):
            s_df = pd.read_csv(sov_csv)
            if not s_df.empty:
                target_row = s_df[s_df["Brand"].astype(str).str.lower() == st.session_state.target_brand.lower()]
                if not target_row.empty:
                    top_sov = str(target_row.iloc[0].get("Share of Voice (%)", "N/A"))
                else:
                    top_sov = str(s_df.iloc[0].get("Share of Voice (%)", "N/A"))
                    
        with kpi1:
            st.metric("🎥 Vídeos Analisados", f"{total_vids}" if total_vids else "N/A")
        with kpi2:
            st.metric("👁️ Exposições Visuais (Logos)", f"{vis_count}")
        with kpi3:
            st.metric("🎙️ Menções Faladas", f"{spk_count}")
        with kpi4:
            st.metric("📈 Share of Voice", f"{top_sov}")
            
        st.markdown("---")

    # 1. Executive PDF Presentation Deck
    if presentation_pdf and os.path.exists(presentation_pdf):
        st.subheader(f"1. 📊 Executive PDF Presentation Deck: {st.session_state.target_brand}")
        import base64
        with open(presentation_pdf, "rb") as f:
            pdf_bytes = f.read()
            
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        st.download_button(
            "📥 Download Executive Presentation Deck (PDF)",
            data=pdf_bytes,
            file_name=f"{st.session_state.target_brand}_presentation.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        st.markdown("---")

    # 2. Comprehensive Final Analysis Strategic Report (HTML / Markdown)
    if final_report_html and os.path.exists(final_report_html):
        st.subheader(f"2. 📄 Comprehensive Final Analysis Strategic Report: {st.session_state.target_brand}")
        with open(final_report_html, 'r', encoding='utf-8') as f:
            html_code = f.read()
            
        st.components.v1.html(html_code, height=750, scrolling=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 Download Final Analysis Report (HTML)",
                data=html_code,
                file_name=f"{st.session_state.target_brand}_final_analysis_report.html",
                mime="text/html",
                use_container_width=True
            )
        with col2:
            if final_report_md and os.path.exists(final_report_md):
                with open(final_report_md, 'r', encoding='utf-8') as f:
                    md_code = f.read()
                st.download_button(
                    "📄 Download Final Analysis Report (.md)",
                    data=md_code,
                    file_name=f"{st.session_state.target_brand}_final_analysis_report.md",
                    mime="text/markdown",
                    use_container_width=True
                )
        st.markdown("---")

    # 3. Multimodal Video Intelligence (Visual Logos, Spoken Claims, Value Matrix & Whitespace)
    if (appearances_csv and os.path.exists(appearances_csv)) or (multimodal_csv and os.path.exists(multimodal_csv)):
        st.subheader("3. 👁️🎥 Inteligência Multimodal de Vídeo (Visual, Áudio & Postura)")
        
        # Visual Brand Appearances Timeline with Timestamps
        if appearances_csv and os.path.exists(appearances_csv):
            app_df = pd.read_csv(appearances_csv)
            st.markdown("#### 👁️ Aparições Visuais de Logos & Produtos com Timestamps")
            st.caption("Detecção de logos em grade, volante, embalagens, overlays gráficos e menções faladas mapeadas minuto a minuto via Gemini 3.7 Flash.")
            st.dataframe(app_df, use_container_width=True)
            st.download_button(
                "📥 Download Linha do Tempo de Aparições (CSV)",
                data=app_df.to_csv(index=False),
                file_name=f"{st.session_state.target_brand}_brand_appearances_timeline.csv",
                mime="text/csv",
                key="dl_appearances_csv"
            )
            st.markdown("---")
            
        # Spoken Claims, Creator Stance, Value Matrix, Whitespace Signals
        if multimodal_csv and os.path.exists(multimodal_csv):
            mm_df = pd.read_csv(multimodal_csv)
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("#### 🎙️ Declarações Faladas & Postura do Criador")
                claims_cols = [c for c in ["video_title", "channel_name", "creator_stance", "spoken_key_claims"] if c in mm_df.columns]
                st.dataframe(mm_df[claims_cols] if claims_cols else mm_df, use_container_width=True)
            
            with col_m2:
                st.markdown("#### 💡 Sinais de Oceano Azul & Whitespace")
                ws_cols = [c for c in ["video_title", "investment_whitespace_signals", "brand_co_occurrences"] if c in mm_df.columns]
                st.dataframe(mm_df[ws_cols] if ws_cols else mm_df, use_container_width=True)
                
            st.markdown("#### ⚖️ Matriz de Valor vs. Ruído (Atributos Mais Valorizados vs. Críticas)")
            matrix_cols = [c for c in ["video_title", "features_valued_most", "features_criticized_or_irrelevant", "creator_stance"] if c in mm_df.columns]
            st.dataframe(mm_df[matrix_cols] if matrix_cols else mm_df, use_container_width=True)
            
            st.download_button(
                "📥 Download Análise Multimodal Completa (CSV)",
                data=mm_df.to_csv(index=False),
                file_name=f"{st.session_state.target_brand}_multimodal_analysis.csv",
                mime="text/csv",
                key="dl_multimodal_csv"
            )
            st.markdown("---")

    # 4. All Tables & Quantitative Datasets
    if (sov_csv and os.path.exists(sov_csv)) or (creators_csv and os.path.exists(creators_csv)) or (drivers_csv and os.path.exists(drivers_csv)) or (video_content_csv and os.path.exists(video_content_csv)):
        st.subheader("4. 📈 Tabelas Quantitativas & Inteligência de Mercado")
        col_a, col_b = st.columns(2)
        with col_a:
            if sov_csv and os.path.exists(sov_csv):
                sov_df = pd.read_csv(sov_csv)
                st.subheader("📈 Share of Voice (SOV) % Breakdown")
                st.dataframe(sov_df, use_container_width=True)
                st.download_button(
                    "📥 Download Share of Voice (CSV)",
                    data=sov_df.to_csv(index=False),
                    file_name=f"{st.session_state.target_brand}_share_of_voice.csv",
                    mime="text/csv",
                    key="dl_sov_csv"
                )
                
        with col_b:
            if creators_csv and os.path.exists(creators_csv):
                creators_df = pd.read_csv(creators_csv)
                st.subheader("🎬 Top YouTube Creators Mapeados")
                st.dataframe(creators_df, use_container_width=True)
                st.download_button(
                    "📥 Download Creator Mapping (CSV)",
                    data=creators_df.to_csv(index=False),
                    file_name=f"{st.session_state.target_brand}_creator_mapping.csv",
                    mime="text/csv",
                    key="dl_creators_csv"
                )

        if drivers_csv and os.path.exists(drivers_csv):
            st.markdown("---")
            st.subheader("🔥 Comparativo de Engajamento: Campeões vs. Baixo Desempenho")
            drivers_df = pd.read_csv(drivers_csv)
            st.dataframe(drivers_df, use_container_width=True)
            st.download_button(
                "📥 Download High Engagement Drivers (CSV)",
                data=drivers_df.to_csv(index=False),
                file_name=f"{st.session_state.target_brand}_high_engagement_drivers.csv",
                mime="text/csv",
                key="dl_drivers_csv"
            )

        if video_content_csv and os.path.exists(video_content_csv):
            st.markdown("---")
            st.subheader("🎥 Análise Detalhada do Conteúdo dos Vídeos (Titles, Descriptions & Views)")
            video_content_df = pd.read_csv(video_content_csv)
            st.dataframe(video_content_df, use_container_width=True)
            st.download_button(
                "📥 Download Video Content Breakdown (CSV)",
                data=video_content_df.to_csv(index=False),
                file_name=f"{st.session_state.target_brand}_video_content_breakdown.csv",
                mime="text/csv",
                key="dl_video_content_csv"
            )
    elif not ((appearances_csv and os.path.exists(appearances_csv)) or (multimodal_csv and os.path.exists(multimodal_csv))):
        st.info("No analysis generated yet. Formulate your strategy and run the pipeline in Tab 1!")

# TAB 3: Google Drive Backup
with tab3:
    st.subheader("📁 Google Drive Output Storage")
    st.markdown("All pipeline outputs (Share of Voice CSV, Creator Mapping CSV, Raw Comments CSV, HTML & Markdown Final Reports) are automatically saved to your shared Google Drive folder:")
    
    st.markdown("🔗 **[Open Shared Google Drive Folder](https://drive.google.com/corp/drive/folders/1Q1oDloZ3pVboA384DNU4g9vL02ERqThL)**")
    st.code("Folder ID: 1Q1oDloZ3pVboA384DNU4g9vL02ERqThL\nResource Key: 0-UEy66XMGR6YJCtE4ho850A")
