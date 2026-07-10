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

### 🧠 Intelligent Script Generation
- **Multi-agent pipeline** — 8 specialized LLM agents collaborate: Topic Analyzer, Researcher, Outline Creator, Hook Generator, Script Writer, Editor, SEO Optimizer, Quality Reviewer
- **Hook scoring** — 5 hooks are LLM-evaluated on curiosity, specificity, surprise, and brevity; the best one wins
- **Quality gate with retry** — scripts scoring below threshold (default 7/10) are automatically revised up to 3 times
- **Fact-checking** — every claim in the script is verified against research sources
- **Readability enforcement** — Flesch-Kincaid grade ≤ 8 for Shorts-optimal comprehension

### 🌐 Trend Discovery Engine
Scans **10+ sources** for trending content in your niche:
| Source | Method | Status |
|--------|--------|--------|
| Hacker News | Algolia API | ✅ |
| Lobsters | JSON API | ✅ |
| GitHub Trending | HTML scrape | ✅ |
| Dev.to | REST API | ✅ |
| Hackaday | HTML scrape | ✅ |
| Wikipedia Current Events | HTML scrape | ✅ |
| Ars Technica | HTML scrape | ✅ |
| RSS Feeds (5) | feedparser | ✅ |
| YouTube Search | API (optional) | ✅ |
| Reddit | JSON API | ⛔ 403 (needs OAuth) |

- **Source diversity** — automatically caps per-source results so you get a balanced mix
- **Scoring** — weighted by source authority, momentum (rising/stable), and LLM-evaluated niche relevance
- **Used-topic tracking** — `--refresh` flag skips already-used topics; auto-resets when exhausted

### 🎬 Professional Video Assembly
- **SSML voiceovers** — natural-sounding speech with automatic pauses between sections, emphasis on numbers and impact words via Edge-TTS
- **Word-synced captions** — captions timed to sentence boundaries from TTS stream
- **Background music with ducking** — royalty-free music auto-mixed with sidechain compression (quiets during speech)
- **Sound effects** — whoosh/transition SFX on scene cuts (drop .mp3 files in `assets/sfx/`)
- **Ken Burns effect** — slow zoom/pan on static clips
- **Text animations** — smooth fade-in on all captions
- **Intro/outro bumpers** — branded title and CTA cards
- **Storyboard-based composition** — scenes split proportionally by word count, not fixed ratios
- **Semantic media relevance** — sentence-transformers score clip descriptions against scene visual descriptions for best-match footage
- **Multi-provider media search** — Pexels + Pixabay with automatic fallback

### ☁️ YouTube Upload & SEO
- **OAuth 2.0** — authenticated upload with token persistence
- **SEO-optimized descriptions** — description_hook, bullet points, hashtags, tag truncation (YouTube 500-char limit)
- **Thumbnail generation** — branded title cards via Pillow
- **Scheduled publishing** — `publishAt` support for timed releases
- **Playlist assignment** — auto-add to specified playlists
- **Channel selection** — upload to specific YouTube channels
- **Resumable uploads** — chunks for reliable large file transfers

### ⚡ Automation & CLI
- **Single unified command** — `python -m shortube.main` shows trends by default
- **Auto mode** — picks the best undiscovered topic, generates, and uploads in one command
- **Batch generation** — process multiple topics sequentially or in parallel with `--parallel N`
- **6 clean subcommands** — `show-trends`, `generate`, `auto`, `batch-gen`, `reset`, `channels`
- **Backward compatible** — all 8 legacy subcommands still work (hidden)

---

## 🚀 Quick Start

### Prerequisites
```bash
# Python 3.11+
# FFmpeg (for video processing)
```

### Installation
```bash
# Clone
git clone https://github.com/alimaandev/shortube.git
cd shortube

# Install dependencies
pip install -r requirements.txt

# Install optional but recommended
pip install sentence-transformers torch  # semantic media relevance
```

### Configuration
Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
PEXELS_API_KEY=your_pexels_api_key
NICHE=general_facts

# Optional
YOUTUBE_API_KEY=your_youtube_api_key
BACKGROUND_MUSIC_PATH=assets/music/loop.mp3
UPLOAD_PUBLISH_AT=2026-07-10T15:00:00Z
UPLOAD_PLAYLIST_ID=your_playlist_id
```

### Usage
```bash
# Show trending topics in your niche
python -m shortube.main

# Generate a Short for a specific topic
python -m shortube.main generate -t "Mind-blowing facts about the universe" --agents

# Auto mode: pick the best undiscovered topic, generate, upload
python -m shortube.main auto --agents

# Batch generate 5 topics with parallel workers
python -m shortube.main batch-gen --count 5 --parallel 3 --agents

# Show trends from a different niche
python -m shortube.main show-trends --niche technology

# List your YouTube channels
python -m shortube.main channels

# Clear used-topic tracker
python -m shortube.main reset
```

---

## 🏗️ Architecture

```
shortube/
├── agents/          # 8 LLM agents for script writing pipeline
│   ├── pipeline.py  # Agent orchestrator
│   ├── script_writer.py
│   ├── hook_generator.py
│   ├── quality_reviewer.py
│   └── ...
├── config/          # Pydantic Settings + .env
├── core/            # Pipeline orchestration, types, interfaces
│   ├── pipeline.py  # Main Pipeline class (5-stage runner)
│   ├── types.py     # Script, Scene, Storyboard, ResearchNote, etc.
│   └── interfaces.py
├── discovery/       # Trend discovery engine
│   ├── engine.py    # Source registry, discover(), diversified ranking
│   ├── scorer.py    # Source weights + momentum + LLM relevance
│   └── sources/     # HackerNews, Reddit, RSS, WebScraper, YouTube
├── modules/         # Media processing & upload
│   ├── voice.py     # Edge-TTS with SSML + timestamp capture
│   ├── assemble.py  # MoviePy video assembly with FX
│   ├── thumbnail.py # Pillow thumbnail generation
│   └── upload.py    # YouTube Data API v3 upload
├── research/        # Wikipedia + LLM knowledge research
├── shared/          # LLM client, cache, prompts, retry, logging
├── storyboard/      # Scene splitting, media search, semantic ranking
│   ├── scene_splitter.py   # Word-count-proportional timing
│   ├── semantic_ranker.py  # sentence-transformers relevance
│   ├── query_ranker.py     # Semantic + keyword query ranking
│   └── providers/          # Pexels, Pixabay, fallback
└── main.py          # Unified CLI entry point
```

### Pipeline Flow
```
Topic → Discovery Engine (10 sources)
     → Script Pipeline (8 agents, up to 3 retries)
         → TopicAnalyzer → Research → Outline → HookGenerator
         → ScriptWriter → ScriptEditor (× retries) → SEOOptimizer
         → QualityReviewer (with readability check)
     → Voiceover (SSML + timestamps)
     → Storyboard (word-count-proportional scenes)
     → Media Search (semantically ranked, 3 providers)
     → Video Assembly (music, SFX, Ken Burns, animated captions, bumpers)
     → Thumbnail Generation
     → YouTube Upload (scheduled, playlisted, with SEO description)
```

---

## 🎯 Quality Features

| Feature | What It Does |
|---------|-------------|
| **SSML Voice** | Natural breaks between sections, emphasis on key numbers/words |
| **Hook Scoring** | LLM rates 5 hooks on 4 criteria, picks the best |
| **Quality Gate** | Scripts scored 1-10; <threshold auto-retries with revision notes |
| **Fact Check** | Every claim verified against research sources |
| **Readability** | Flesch-Kincaid grade ≤ 8 enforced |
| **Semantic Search** | sentence-transformers match clip content to scene description |
| **Audio Ducking** | Background music automatically quiets during speech |
| **Ken Burns** | Subtle zoom/pan on static clips |
| **Word-Synced Captions** | Timed to TTS sentence boundaries |
| **Source Diversity** | Caps top results per source for mixed trend output |

---

## ⚙️ Configuration Reference

All settings are configurable via `.env` or directly in `shortube/config/settings.py`:

| Setting | Default | Description |
|--------|---------|-------------|
| `GROQ_API_KEY` | — | Groq LLM API key |
| `PEXELS_API_KEY` | — | Pexels stock video API key |
| `NICHE` | `general_facts` | Default content niche |
| `VOICE_NAME` | `en-US-AriaNeural` | Edge-TTS voice |
| `VOICE_SPEED` | `1.15` | Playback speed multiplier |
| `BACKGROUND_MUSIC_PATH` | — | Path to royalty-free music loop |
| `MUSIC_VOLUME` | `15.0` | Music volume (1-20 scale) |
| `DUCK_THRESHOLD` | `6.0` | Audio ducking intensity |
| `QUALITY_PASS_THRESHOLD` | `7` | Script quality minimum (1-10) |
| `QUALITY_MAX_RETRIES` | `3` | Script revision attempts |
| `UPLOAD_PRIVACY` | `private` | `private`, `unlisted`, or `public` |
| `UPLOAD_PUBLISH_AT` | — | ISO 8601 scheduled publish time |
| `UPLOAD_PLAYLIST_ID` | — | YouTube playlist to auto-assign |

---

## 🧪 Roadmap

- [ ] Reddit OAuth (PRAW) for Reddit trend source
- [ ] Multi-voice narration (switch voices for quotes)
- [ ] AI-generated background music (Bark/AudioCraft)
- [ ] End screens and info cards on upload
- [ ] Analytics callback after upload
- [ ] Web dashboard for monitoring and manual review
- [ ] A/B title testing

---

## 📄 License

MIT

---

<div align="center">
  <p>Built with ❤️ by <a href="https://github.com/alimaandev">alimaandev</a></p>
</div>
