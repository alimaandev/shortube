<div align="center">

# 🎬 Shortube

### AI-Powered YouTube Shorts Studio — from topic to upload, fully automated

**Discover trends → Write scripts → Generate voiceovers → Assemble videos → Upload to YouTube**

<br>

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![Rendering](https://img.shields.io/badge/Rendering-Remotion-00C7B7?style=for-the-badge)
![TTS](https://img.shields.io/badge/TTS-edge--tts-00838F?style=for-the-badge)
![YouTube](https://img.shields.io/badge/YouTube-API%20v3-FF0000?style=for-the-badge&logo=youtube&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-4C9F38?style=for-the-badge&logo=open-source-initiative&logoColor=white)

**⭐ From idea to published Short in minutes — no video editing skills required.**

</div>

---

## 📚 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [🧠 LLM Providers](#-llm-providers)
- [🎚️ Quality Presets](#️-quality-presets)
- [🖼️ Visual Templates](#️-visual-templates)
- [🏗️ Architecture](#️-architecture)
- [⚙️ Configuration Reference](#️-configuration-reference)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Features

### 🖥️ Desktop App (PyQt6)

| | Feature | What it does |
|---|---------|--------------|
| 🏠 | **Dashboard** | Generate by topic or one-click Auto mode with live progress bar, stage-by-stage log, and job cancellation |
| 🔥 | **Trends** | Refresh trending topics in your niche (LLM-refined), click to generate |
| 🎞️ | **Videos** | Thumbnail gallery, open local files or YouTube links, retry failed videos with cache resume |
| ⚙️ | **Settings** | Tabbed config — LLM, voice, video & quality, upload, advanced — with *Test Connection* and YouTube channel picker |
| 🕒 | **Schedule** | Automatic generation on an interval with a daily limit (survives restarts) |
| 📊 | **Analytics** | Views, likes and comments for your uploaded videos |
| 🧙 | **Setup Wizard** | First-run guide: LLM provider → template → quality → YouTube connection |
| 🛡️ | **Dependency Check** | Friendly startup warnings for missing Node.js / Remotion / ffmpeg |

### ✍️ Script Generation

- 🧠 **LLM-powered scripts** — hook, body points, CTA, keywords, title and tags in a single validated prompt
- ✅ **Strict quality gate** — hook/points/CTA length, keyword density ≥ 60%, spoken duration ≤ 55s, duplicate & junk detection with **up to 3 automatic retries**
- 🔄 **Self-healing** — malformed LLM output is detected and retried with the exact fix hints

### 🌐 Trend Discovery

- 📰 **3 sources** — Hacker News (Algolia), RSS (NYT, BBC, The Verge, Wired, Ars Technica), YouTube Search (Data API)
- 🎯 **LLM refinement** — headlines converted into Shorts-optimized topics for your niche
- 🚫 **Used-topic tracking** — never re-generates a topic you've already uploaded

### 🎬 Video Assembly (Remotion)

- 💬 **Word-synced karaoke captions** — timed to TTS word boundaries
- 🎨 **Config-driven templates** — colors, transitions (zoomBlur / fade / slide / wipe), Ken Burns, caption style
- 🎉 **Intro/outro bumpers** — progress ring, typewriter title, subscribe CTA
- 🔊 **Sound design** — whoosh/pop/riser SFX + background music with ducking
- 🎚️ **Loudness normalized** to YouTube's **-14 LUFS**
- ⏱️ **60s Shorts cap** enforced at both script and voiceover level

### 📤 YouTube Upload & SEO

- 🔐 **OAuth 2.0** with token persistence (browser flow)
- 🏷️ **Tags & keywords** — the LLM generates 3–8 keywords and 4–12 tags per script; the description auto-appends the first 8 tags as `#hashtags`, truncated at YouTube's 500-char limit
- 🪂 **Fallback tags** — `TAGS_DEFAULT` (`shorts, youtubeshorts`) when a script has none
- 🖼️ **Branded thumbnails**, 📅 **scheduled publishing**, ▶️ **playlist assignment**, 👥 **multi-channel selection**

---

## 🚀 Quick Start

### 📋 Prerequisites

| Requirement | Why |
|-------------|-----|
| 🐍 Python 3.11+ | Core engine |
| ⚡ Node.js 18+ | Remotion rendering |
| 🎬 ffmpeg (on PATH) | Loudness normalization (recommended) |
| 🦙 Ollama *or* API key | LLM for script writing |

### 📦 Installation

```bash
# Python dependencies
pip install -r requirements.txt

# Remotion renderer
cd remotion
npm install
cd ..
```

### ▶️ Run

```bash
python -m shortube.desktop
```

On first launch, the **setup wizard** walks you through everything — pick your LLM provider, connect your YouTube channel, choose a template and quality preset. All of it is editable later in **Settings**.

### 🧪 CLI (power users)

```bash
python -m shortube.main                # Show trending topics
python -m shortube.main generate -t "Mind-blowing facts about the universe"
python -m shortube.main auto           # Auto-discover, generate, upload
```

---

## 🧠 LLM Providers

Shortube works with **any** of these — switch anytime in Settings → LLM:

| Provider | Setup | Cost |
|----------|-------|------|
| ⚡ **Groq** *(default)* | `GROQ_API_KEY` | Fast & cheap |
| 🌐 **OpenRouter** | `OPENROUTER_API_KEY` | Many models |
| 🦙 **Ollama** | local install, no key | **Free**, runs on your machine |

```env
GROQ_API_KEY=gsk_xxx
# or
OPENROUTER_API_KEY=sk-or-xxx
# or (no key needed)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 🎚️ Quality Presets

Control render speed vs. output quality — pick in Settings → Video & Quality:

| Preset | 🎞️ fps | ⚙️ Concurrency | 🎨 CRF | 🔊 Audio bitrate | Best for |
|--------|:-----:|:----:|:----:|:-----------:|----------|
| ⚡ **fast** | 24 | 2 | 22 | 160k | Drafts, quick previews |
| ⚖️ **standard** | 30 | auto | 18 | 192k | Everyday uploads |
| 💎 **pro** | 30 | cores/2 | 14 | 256k | Maximum quality |

> 📌 **Tip:** CRF is the H.264 quality knob — lower = better quality, bigger file. YouTube re-encodes anyway, so `standard` is the sweet spot for Shorts.

---

## 🖼️ Visual Templates

Every render's look is defined by a JSON template in `templates/` — colors, fonts, transitions, Ken Burns, caption style and outro styling. Templates are hot-swappable without touching code.

| Template | Vibe |
|----------|------|
| 🟢 **premium** (default) | Premium Bold — dark, zoomBlur transitions, green accent |
| 🔵 **clean** | Clean Minimal — light, slide transitions, blue accent |

Create your own by copying one and picking new colors — the app lists it automatically.

---

## 🏗️ Architecture

```
shortube/
├── 🖥️ desktop/                # PyQt6 desktop app
│   ├── app.py                 # Entry point (python -m shortube.desktop)
│   ├── main_window.py         # Sidebar navigation + job manager wiring
│   ├── workers.py             # Background job thread, signals, cancel
│   ├── setup_wizard.py        # First-run configuration wizard
│   ├── theme.py               # Dark theme, template-aware accent color
│   └── pages/                 # dashboard · trends · videos · settings · schedule · analytics
├── main.py                    # CLI entry point (Click)
├── pipeline.py                # 5-stage orchestrator
├── script.py                  # LLM script generation + validation + retries
├── voice.py                   # edge-tts voiceover with word timestamps
├── storyboard.py              # Scene builder + media providers
├── assemble.py                # Remotion assembly + loudness normalization
├── remotion_bridge.py         # Python ⇄ Remotion CLI integration
├── quality.py                 # Fast/Standard/Pro render presets
├── template_loader.py         # Visual templates (templates/*.json)
├── scheduler.py               # Auto-generation (APScheduler, persisted daily limit)
├── upload.py                  # YouTube Data API v3 upload + thumbnails
├── analytics.py               # Video statistics
├── discover.py                # Trend discovery engine
├── llm.py                     # LLM abstraction (Groq / OpenRouter / Ollama)
├── settings_env.py            # .env persistence for the settings UI
├── config.py                  # Pydantic settings (.env)
├── db.py                      # SQLite database
└── types.py                   # Data classes

remotion/                      # Renderer (TypeScript)
└── src/                       # ShortubeVideo, Captions, SceneClip, bumpers,
                               # Transitions, SoundEffects, template.tsx
templates/                     # premium.json · clean.json
```

### 🔄 Pipeline Flow

```
┌────────┐   ┌────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
│ Topic  │ → │ Script │ → │Voiceover │ → │Storyboard│ → │Assembly │
└────────┘   │  (LLM) │   │ (edge-  │   │ (media + │   │(Remotion│
             └────────┘   │   tts)  │   │  AI img) │   │  + SFX) │
                          └──────────┘   └──────────┘   └────┬────┘
                                                             ▼
                       ┌──────────┐   ┌──────────┐   ┌──────────────┐
                       │ YouTube  │ ← │Thumbnail │ ← │  loudnorm -14│
                       │  Upload  │   │ (Pillow) │   │     LUFS     │
                       └──────────┘   └──────────┘   └──────────────┘
```

---

## ⚙️ Configuration Reference

All settings live in the desktop app (Settings tab) or `.env`. Most work with either.

### 🧠 LLM & Discovery

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `openrouter`, or `ollama` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Script model |
| `DISCOVERY_MODEL` | *(inherits `LLM_MODEL`)* | Trend refinement model |
| `LLM_TEMPERATURE` | `0.8` | Creativity (0.0 – 1.5) |
| `LLM_MAX_TOKENS` | `800` | Max tokens per LLM call |
| `GROQ_API_KEY` | — | Groq key *(required for groq)* |
| `OPENROUTER_API_KEY` | — | OpenRouter key *(required for openrouter)* |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |

### 📝 Content & Niche

| Setting | Default | Description |
|---------|---------|-------------|
| `NICHE` | `general_facts` | Default content niche |
| `TAGS_DEFAULT` | `shorts, youtubeshorts` | Fallback YouTube tags when a script has none |
| `QUALITY` | `standard` | `fast`, `standard`, or `pro` |

### 🎙️ Voiceover

| Setting | Default | Description |
|---------|---------|-------------|
| `VOICE_NAME` | `en-US-AriaNeural` | edge-tts voice |
| `VOICE_SPEED` | `1.15` | Playback speed |
| `VOICE_VOLUME` | `1.0` | Voiceover gain |

### 🎞️ Video & Rendering

| Setting | Default | Description |
|---------|---------|-------------|
| `VIDEO_WIDTH` / `VIDEO_HEIGHT` | `1080` / `1920` | Canvas size (px) |
| `VIDEO_FPS` | `30` | Baseline fps *(presets may override)* |
| `BUMPER_DURATION` | `1.5` | Intro/outro bumper length (s) |
| `TRANSITION_DURATION` | `0.3` | Scene transition length (s) |
| `TEMPLATE` | `premium` | Visual template from `templates/*.json` |
| `REMOTION_PROJECT_DIR` | `remotion` | Path to Remotion project |
| `REMOTION_CONCURRENCY` | `0` | Render threads (`0` = preset default) |
| `CAPTION_FONT_SIZE` | `48` | Caption size (px) |
| `CAPTION_FONT` / `CAPTION_FONT_COLOR` | — / `white` | Caption font & color |
| `CAPTION_STROKE_COLOR` / `WIDTH` | `black` / `3` | Caption outline |

### 🖼️ Media & Audio

| Setting | Default | Description |
|---------|---------|-------------|
| `IMAGE_PROVIDER` | `auto` | `auto`, `pexels`, `pixabay`, or `pollinations` |
| `IMAGE_PROVIDER_FALLBACK` | `true` | Allow fallback providers |
| `MEDIA_PREFER_VIDEOS` | `true` | Prefer stock videos over images |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | — | Stock media keys (optional) |
| `BACKGROUND_MUSIC_PATH` | — | Path to a music loop (optional) |
| `MUSIC_VOLUME` | `15.0` | Music level (0–100) |
| `DUCK_THRESHOLD` | `6.0` | Music ducking intensity |
| `SFX_ENABLED` | `true` | whoosh/pop/riser sound effects |
| `SFX_DIR` | `resources/sfx` | SFX folder |

### 📤 YouTube Upload

| Setting | Default | Description |
|---------|---------|-------------|
| `YOUTUBE_CLIENT_SECRETS` | `client_secrets.json` | OAuth client file |
| `UPLOAD_PRIVACY` | `public` | `private`, `unlisted`, or `public` |
| `UPLOAD_CATEGORY` | `22` | YouTube category ID |
| `UPLOAD_LANGUAGE` | `en` | Video language |
| `UPLOAD_CHANNEL_ID` | — | Default upload channel |
| `UPLOAD_PUBLISH_AT` | — | ISO 8601 scheduled publish time |
| `UPLOAD_PLAYLIST_ID` | — | Auto-add videos to a playlist |

---

## 🤝 Contributing

Found a bug or have an idea? Open an [issue](https://github.com/alimaandev/shortube/issues) or submit a PR. Please run the test suite before pushing:

```bash
python -m py_compile shortube/*.py
```

---

## 📄 License

[MIT](LICENSE)

---

<div align="center">

**Made with ❤️ by [alimaandev](https://github.com/alimaandev)**

🎥 **Shortube** — turn ideas into viral Shorts, automatically.

</div>
