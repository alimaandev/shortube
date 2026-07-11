<div align="center">
  <h1>🎥 Shortube </h1>
  <p><strong>AI-Powered YouTube Shorts & Video Generation Studio</strong></p>
  <p>Discover trends → Write scripts → Generate voiceovers → Assemble videos → Upload — fully automated.</p>

  <p>
    <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
    <img src="https://img.shields.io/badge/status-production--ready-brightgreen" alt="Production Ready">
  </p>

  <br>
</div>

---

## ✨ Features

### 🧠 Script Generation
- **LLM-powered scripts** — hook, body points, CTA, keywords, title, and tags generated in a single prompt
- **Retry with error recovery** — malformed LLM output is detected and automatically retried (up to 3 times)
- **HTML tag stripping** — all generated text is sanitized at every layer (LLM output, DB load, TTS, captions)
- **Multi-provider LLM support** — Groq, OpenRouter, or Ollama (local, no API key needed)

### 🌐 Trend Discovery Engine
Scans **3 sources** for trending content in your niche:
| Source | Method | Status |
|--------|--------|--------|
| Hacker News | Algolia API | ✅ |
| RSS Feeds (5) | feedparser (NYT, BBC, The Verge, Wired, Ars Technica) | ✅ |
| YouTube Search | YouTube Data API (optional) | ✅ |

- **Source diversity** — caps per-source results for a balanced mix
- **Scoring** — weighted by source authority and popularity (points / views)
- **Used-topic tracking** — topics marked `done` / `uploaded` are automatically skipped

### 🎬 Video Assembly (FFmpeg)
- **Plain text voiceovers** — edge-tts with natural punctuation, no SSML, clean word-boundary timestamps
- **Word-synced captions** — burned into video via FFmpeg `subtitles` filter, timed to TTS word boundaries
- **Background music with ducking** — pydub mixing with volume ducking during speech
- **Ken Burns effect** — slow zoompan on static images via FFmpeg
- **AI-generated scene images** — Pollinations.ai (free, no API key), Flux model, 1080×1920
- **Intro/outro bumpers** — PIL-rendered title and CTA cards with fade transitions
- **Scene caching** — per-image clip caching so re-runs with same images skip FFmpeg encoding

### ☁️ YouTube Upload & SEO
- **OAuth 2.0** — authenticated upload with token persistence and auto-refresh
- **SEO-optimized descriptions** — hook + bullet points + hashtags, truncated to YouTube limits
- **Thumbnail generation** — branded title cards via Pillow
- **Scheduled publishing** — `publishAt` ISO 8601 support
- **Playlist assignment** — auto-add to specified playlists
- **Channel selection** — upload to specific YouTube channels
- **Default public uploads** — no manual privacy toggle needed

### 🖥️ Desktop UI (CustomTkinter)
- **4 tabs** — Dashboard, Topics, Jobs, Settings
- **Dashboard** — Generate by topic, Auto-scan trends, live job/video tables
- **Settings tab** — LLM provider/model, voice name/speed, video dimensions, upload defaults, niche — all saved to `.env`
- **Auto-refresh** — jobs and videos refresh every 3 seconds
- **Threaded execution** — generation runs in background threads, UI stays responsive

### ⚡ Automation & CLI
- **Single command** — `python -m shortube.main` shows trends by default
- **Generate** — `generate -t "topic"` runs the full pipeline (script → voiceover → storyboard → assemble → upload)
- **Auto mode** — discovers topics, picks the best unused one, generates and uploads
- **Desktop mode** — `desktop` launches the GUI
- **Channel management** — `set-channel` to configure the upload channel

---

## 🚀 Quick Start

### Prerequisites
```bash
# Python 3.11+
# FFmpeg + FFprobe (on PATH)
# Ollama (optional, for local LLM)
```

### Installation
```bash
git clone https://github.com/alimaandev/shortube.git
cd shortube
pip install -r requirements.txt
```

### Configuration
Create a `.env` file in the project root:

```env
# At minimum, pick an LLM provider:
GROQ_API_KEY=your_groq_api_key
# or
OPENROUTER_API_KEY=your_openrouter_key
# or (no key needed)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434

# YouTube upload (required for upload)
YOUTUBE_CLIENT_SECRETS=client_secrets.json
UPLOAD_CHANNEL_ID=your_channel_id

# Optional
NICHE=general_facts
BACKGROUND_MUSIC_PATH=assets/music/loop.mp3
VOICE_NAME=en-US-AriaNeural
UPLOAD_PUBLISH_AT=2026-07-10T15:00:00Z
UPLOAD_PLAYLIST_ID=your_playlist_id
```

### Usage
```bash
# Show trending topics
python -m shortube.main

# Generate a Short for a specific topic
python -m shortube.main generate -t "Mind-blowing facts about the universe"

# Auto mode: pick the best undiscovered topic, generate, upload
python -m shortube.main auto

# Launch desktop GUI
python -m shortube.main desktop

# Set upload channel
python -m shortube.main set-channel UC_your_channel_id
```

---

## 🏗️ Architecture

```
shortube/
├── main.py          # CLI entry point (Click commands)
├── pipeline.py      # 4-stage orchestrator (script → voiceover → storyboard → assemble)
├── script.py        # LLM script generation (Groq / OpenRouter / Ollama)
├── voice.py         # edge-tts voiceover with word-boundary timestamps
├── storyboard.py    # Scene builder + Pollinations.ai image download
├── assemble.py      # FFmpeg video assembly (bumpers, zoompan, music, captions)
├── upload.py        # YouTube Data API v3 upload + Pillow thumbnail
├── discover.py      # Trend discovery (Hacker News, RSS, YouTube)
├── llm.py           # LLM abstraction layer (3 providers)
├── config.py        # Pydantic settings (.env)
├── db.py            # SQLite database (topics, videos, jobs)
├── types.py         # Data classes (Script, Scene, Storyboard, etc.)
├── desktop.py       # CustomTkinter desktop GUI
└── __init__.py
```

### Pipeline Flow
```
Topic → Script (LLM) → Voiceover (edge-tts) → Storyboard (Pollinations images)
     → Assembly (FFmpeg bumpers + zoompan + music + captions)
     → Thumbnail (Pillow) → YouTube Upload (OAuth 2.0)
```

### Full 4-Stage Pipeline

| Stage | Input | Output | Tech |
|-------|-------|--------|------|
| 1. Script | Topic string | `Script` object (hook, points, CTA, title, tags) | LLM (Groq/OpenRouter/Ollama) |
| 2. Voiceover | Script parts | `voiceover.mp3` + `voiceover.timestamps.json` | edge-tts (plain text) |
| 3. Storyboard | Script + voice path | `Storyboard` with scenes + downloaded AI images | Pollinations.ai + FFprobe |
| 4. Assembly | Storyboard + voice | `final.mp4` with bumpers, music, captions | FFmpeg + pydub |

---

## 🎯 Quality Features

| Feature | What It Does |
|---------|-------------|
| **Plain Text TTS** | No SSML HTML remnants — clean audio and captions |
| **Word-Synced Captions** | Timed to edge-tts `WordBoundary` events |
| **Audio Ducking** | Background music automatically quiets during speech |
| **Ken Burns** | Subtle zoom/pan on static images |
| **AI Scene Images** | Pollinations.ai Flux — free, unique per scene |
| **Retry Logic** | LLM output retried up to 3x on parse failure |
| **Caption Sanitization** | HTML tags stripped at 4 layers (script, DB, TTS, captions) |
| **Per-Image Caching** | Scene clips cached by media hash — fast re-runs |
| **Source Diversity** | Caps per-source results for mixed trend output |
| **Used-Topic Tracking** | Already-processed topics are automatically skipped |

---

## ⚙️ Configuration Reference

All settings are configurable via `.env`:

| Setting | Default | Description |
|--------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `openrouter`, or `ollama` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name for the selected provider |
| `GROQ_API_KEY` | — | Groq API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `NICHE` | `general_facts` | Default content niche |
| `VOICE_NAME` | `en-US-AriaNeural` | edge-tts voice |
| `VOICE_SPEED` | `1.15` | Playback speed multiplier |
| `VIDEO_WIDTH` | `1080` | Video width (px) |
| `VIDEO_HEIGHT` | `1920` | Video height (px) — portrait for Shorts |
| `VIDEO_FPS` | `30` | Frames per second |
| `BUMPER_DURATION` | `1.5` | Intro/outro bumper length (seconds) |
| `TRANSITION_DURATION` | `0.3` | Fade transition (seconds) |
| `BACKGROUND_MUSIC_PATH` | — | Path to royalty-free music loop |
| `MUSIC_VOLUME` | `15.0` | Music volume (1-20) |
| `DUCK_THRESHOLD` | `6.0` | Audio ducking intensity |
| `UPLOAD_PRIVACY` | `public` | `private`, `unlisted`, or `public` |
| `UPLOAD_CHANNEL_ID` | — | Default YouTube channel ID |
| `UPLOAD_PUBLISH_AT` | — | ISO 8601 scheduled publish time |
| `UPLOAD_PLAYLIST_ID` | — | YouTube playlist to auto-assign |
| `YOUTUBE_CLIENT_SECRETS` | `client_secrets.json` | OAuth client secrets file |

---

## 🧪 Roadmap

- [ ] Reddit trend source (PRAW OAuth)
- [ ] Multi-voice narration (switch voices per scene)
- [ ] AI-generated background music (Bark / AudioCraft)
- [ ] End screens and info cards on upload
- [ ] Analytics callback after upload
- [ ] Web dashboard for monitoring and review
- [ ] A/B title testing

---

## 📄 License

MIT

---

<div align="center">
  <p>Built with ❤️ by <a href="https://github.com/alimaandev">alimaandev</a></p>
</div>
