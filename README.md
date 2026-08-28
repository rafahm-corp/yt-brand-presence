# YouTube Brand Presence & Share of Voice Tracker

*(THIS IS NOT AN OFFICIAL GOOGLE TOOL)*

The **YouTube Brand Presence Tracker** is an end-to-end intelligence pipeline designed to quantify and analyze brand visibility, creator perceptions, competitor benchmarking, and organic Share of Voice (SOV) on YouTube using Google Gemini AI.

---

## 🌟 Key Features

- 🧠 **AI Deep Thinking Briefing Assistant**: Translates broad marketing briefings into targeted YouTube search queries, competitor maps, and negative exclusion keywords with real-time Google Search Grounding.
- ⚡ **Auto-Optimized Gemini Flash Pipeline**: Automatically probes and selects the most responsive Flash model (`gemini-flash-latest` → `gemini-3.6-flash` → `gemini-3.5-flash`) for low-latency batch processing.
- 🎯 **Organic Share of Voice (SOV) Analysis**: Measures spontaneous creator mentions, sentiment drivers, and competitor positioning across top relevant videos.
- 🎬 **Multimodal Video Understanding**: Ingests video audio, visuals, transcripts, and comments via Gemini without requiring heavy video downloads.
- 📊 **Multi-Format Strategic Outputs**: Automatically generates:
  - 🌐 **Interactive HTML Report** (Deep analytical dashboard)
  - 📝 **Markdown Executive Briefing**
  - 📑 **PDF Presentation Deck** (Formatted slides with visual summaries)
- 🖥️ **Streamlit Web Application**: An intuitive web UI for running and reviewing campaigns.

---

## 📁 Repository Structure

```
yt-brand-presence-tracker/
├── app.py                     # Streamlit web interface
├── main.py                    # CLI entry point for batch execution
├── src/                       # Core pipeline modules
│   ├── brand_presence_analyzer.py # SOV and competitive intelligence engine
│   ├── briefing_planner.py        # Gemini Deep Thinking strategy generator
│   ├── client_factory.py          # Google GenAI client factory & health probe
│   ├── crawler.py                 # YouTube API discovery & comment scraper
│   ├── drive_uploader.py          # Google Drive / Shared Drive export utility
│   ├── generate_slides_final.py   # PDF slide deck compiler
│   ├── multimodal_extractor.py    # Video audio/visual extraction pipeline
│   └── report_generator.py        # HTML & Markdown report synthesizer
├── templates/                 # Prompt templates and report layouts
├── config.ini.example         # Example configuration file
├── .env.example               # Example environment variables file
├── requirements.txt           # Python package dependencies
└── README.md                  # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+**
- **YouTube Data API v3 Key** (from Google Cloud Console)
- **Gemini API Key** (from Google AI Studio)

### 2. Installation

Clone the repository and install the required dependencies:

```bash
# Clone repository
git clone git@github.com:rafahm-google/yt-brand-presence-tracker.git
cd yt-brand-presence-tracker

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment & Configuration Setup

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   YOUTUBE_API_KEY=your_youtube_api_key
   GEMINI_API_KEY=your_gemini_api_key
   GOOGLE_API_KEY=your_gemini_api_key
   ```

2. (Optional) Copy `config.ini.example` to `config.ini` to customize default parameters:
   ```bash
   cp config.ini.example config.ini
   ```

---

## 💻 Usage

### Option A: Streamlit Web UI (Recommended)

Start the local Streamlit dashboard:

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

1. **AI Guided Mode**: Enter your campaign goal or research topic and click **Generate Strategy with Gemini Deep Thinking**.
2. **Review & Fine-Tune**: Review discovered competitors, search queries, and negative keywords.
3. **Launch Pipeline**: Click **Launch Brand Presence Analysis** to execute the pipeline and download reports/slides.

### Option B: Command Line Interface (CLI)

Run the full end-to-end pipeline via CLI:

```bash
python main.py --step all
```

Run specific pipeline stages independently:
- `python main.py --step crawl` (YouTube video & comment discovery)
- `python main.py --step analyze` (Multimodal analysis & SOV synthesis)
- `python main.py --step slides` (Slide deck generation)

---

## 🔒 Security & Privacy

- **Never commit `.env` or `config.ini` containing API keys or private tokens.**
- This project includes a pre-configured `.gitignore` that prevents private configs, secrets, caches, and test artifacts from being tracked in version control.

---

## 📄 License & Disclaimer

This is a personal research tool and is not an officially supported Google product. Users are responsible for complying with the [YouTube Terms of Service](https://www.youtube.com/t/terms).
