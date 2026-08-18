# Shortube

AI-Powered YouTube Shorts & Video Generation Studio — desktop app.

Discover trends -> Write scripts -> Generate voiceovers -> Assemble videos (via Remotion) -> Upload. Fully automated, powered by a native **PyQt6** desktop app.

## Features

### Desktop App (PyQt6)
- **Dashboard** — generate by topic or one-click Auto mode, live progress bar with stage-by-stage log, cancel any running job, queued jobs
- **Trends** — refresh trending topics in your niche (LLM-refined), click to generate
- **Videos** — gallery with thumbnail previews, open the local file or its YouTube link, retry failed videos (resumes from cache)
- **Settings** — tabbed configuration: LLM, voice, video & quality, upload, advanced. Includes a "Test connection" button and a YouTube channel picker
- **Schedule** — automatic generation on an interval with a daily limit (survives app restarts)
- **Analytics** — views/likes/comments for your uploaded videos
- **First-run setup wizard** — pick your LLM provider, connect YouTube, choose a template
- **Startup dependency check** — friendly warnings for missing Node.js/Remotion/ffmpeg
- **Quality presets** — Fast / Standard / Pro control fps, CRF, render concurrency and audio bitrate

### LLM Providers
- **Groq** (default), **OpenRouter**, or **Ollama** (local, free, no API key) — all configurable from the app
- Scripts pass a strict validation gate: hook/points/CTA length, keyword density ≥ 60%, spoken duration ≤ 55s, duplicate and junk detection — with up to 3 automatic retries

### Trend Discovery
- Hacker News (Algolia API), RSS feeds (NYT, BBC, The Verge, Wired, Ars Technica), YouTube Search (Data API)
- LLM refinement converts headlines into Shorts-optimized topics

### Video Assembly (Remotion)
- Word-synced karaoke captions timed to TTS word boundaries
- Config-driven visual templates (`templates/*.json`): colors, transitions (zoomBlur/fade/slide/wipe), Ken Burns, caption style
- Intro/outro bumpers with progress ring, whoosh/pop/riser sound effects, background music with ducking
- Loudness normalized to YouTube's -14 LUFS
- YouTube Shorts 60s cap enforced at script and voiceover level

### YouTube Upload & SEO
- OAuth 2.0 with token persistence (browser flow)
- SEO descriptions (hook + bullet points + hashtags), branded thumbnail generation, scheduled publishing, playlist assignment, multi-channel selection
- **Tags & keywords** — the LLM generates 3-8 keywords and 4-12 YouTube tags per script (validated before upload); the description auto-appends the first 8 tags as `#hashtags` and tags are truncated at YouTube's 500-char limit
- **Fallback tags** — if a script has no tags, `TAGS_DEFAULT` is used (`shorts, youtubeshorts` by default)

### CLI (power users)
- `python -m shortube.main` — show trends
- `python -m shortube.main generate -t "topic"` — full pipeline
- `python -m shortube.main auto` — auto-discover, generate, upload

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (Remotion rendering)
- ffmpeg on PATH (recommended, for loudness normalization)

### Installation
```bash
pip install -r requirements.txt
cd remotion
npm install
```

### Run
```bash
python -m shortube.desktop
```

On first launch a wizard guides you through the LLM provider, visual template, quality preset, and YouTube connection. Everything else is configurable in Settings.

### Configuration (.env, optional)
Most settings are managed from the app. For scripting or defaults:

```env
GROQ_API_KEY=your_groq_api_key
# or
OPENROUTER_API_KEY=your_openrouter_key
# or (no key needed)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434

YOUTUBE_CLIENT_SECRETS=client_secrets.json
UPLOAD_CHANNEL_ID=your_channel_id
NICHE=general_facts
QUALITY=standard
TAGS_DEFAULT=shorts, youtubeshorts
```

## Quality Presets

| Preset | fps | Concurrency | CRF | Audio bitrate |
|--------|-----|-------------|-----|---------------|
| fast | 24 | 2 | 22 | 160k |
| standard | 30 | auto | 18 | 192k |
| pro | 30 | cores/2 | 14 | 256k |

## Architecture

```
shortube/
├── desktop/            # PyQt6 desktop app
│   ├── app.py          # Entry point (python -m shortube.desktop)
│   ├── main_window.py  # Sidebar navigation + job manager wiring
│   ├── workers.py      # Background job thread, signals, cancel support
│   ├── setup_wizard.py # First-run configuration wizard
│   ├── theme.py        # Dark theme, template-aware accent color
│   └── pages/          # dashboard, trends, videos, settings, schedule, analytics
├── main.py             # CLI entry point (Click commands)
├── pipeline.py         # 5-stage orchestrator (script/voice/storyboard/assemble/upload)
├── script.py           # LLM script generation with validation + retries
├── voice.py            # edge-tts voiceover with word timestamps
├── storyboard.py       # Scene builder + media providers (Pexels/Pixabay/Pollinations)
├── assemble.py         # Remotion assembly + loudness normalization
├── remotion_bridge.py  # Python-to-Remotion CLI integration
├── quality.py          # Fast/Standard/Pro render presets
├── template_loader.py  # Visual template loading (templates/*.json)
├── scheduler.py        # Automatic generation (APScheduler, persisted daily limit)
├── upload.py           # YouTube Data API v3 upload + thumbnails
├── analytics.py        # Video statistics
├── discover.py         # Trend discovery engine
├── llm.py              # LLM abstraction (Groq/OpenRouter/Ollama)
├── settings_env.py     # .env persistence for the settings UI
├── config.py           # Pydantic settings (.env)
├── db.py               # SQLite database
└── types.py            # Data classes

remotion/
└── src/                # Remotion components: ShortubeVideo, Captions, SceneClip,
                        # IntroBumper, OutroBumper, Transitions, SoundEffects,
                        # template.tsx, types.ts
templates/
├── premium.json        # Premium Bold (dark, zoomBlur, green accent)
└── clean.json          # Clean Minimal (light, slide transitions, blue accent)
```

### Pipeline Flow
```
Topic -> Script (LLM, validated) -> Voiceover (edge-tts + word timestamps)
     -> Storyboard (media search / AI images)
     -> Assembly (Remotion: templates, captions, SFX, music, bumpers; loudnorm)
     -> Thumbnail (Pillow) -> YouTube Upload (OAuth 2.0)
```

## Development

```bash
# Run the desktop app
python -m shortube.desktop

# Remotion preview (optional)
cd remotion && npx remotion studio

# CLI tools
python -m shortube.main auto
```

## Configuration Reference

All settings are managed from the desktop app (Settings tab) or via `.env`. Most values can be set with either.

### LLM & Discovery

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `openrouter`, or `ollama` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Script model |
| `DISCOVERY_MODEL` | (inherits `LLM_MODEL`) | Trend refinement model |
| `LLM_TEMPERATURE` | `0.8` | Creativity (0.0 - 1.5) |
| `LLM_MAX_TOKENS` | `800` | Max tokens per LLM call |
| `GROQ_API_KEY` | -- | Groq key (required for groq) |
| `OPENROUTER_API_KEY` | -- | OpenRouter key (required for openrouter) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |

### Content & Niche

| Setting | Default | Description |
|---------|---------|-------------|
| `NICHE` | `general_facts` | Default content niche |
| `TAGS_DEFAULT` | `shorts, youtubeshorts` | Fallback YouTube tags when a script has none |
| `QUALITY` | `standard` | `fast`, `standard`, or `pro` (see presets above) |

### Voiceover

| Setting | Default | Description |
|---------|---------|-------------|
| `VOICE_NAME` | `en-US-AriaNeural` | edge-tts voice |
| `VOICE_SPEED` | `1.15` | Playback speed |
| `VOICE_VOLUME` | `1.0` | Voiceover gain |

### Video & Rendering

| Setting | Default | Description |
|---------|---------|-------------|
| `VIDEO_WIDTH` | `1080` | Canvas width (px) |
| `VIDEO_HEIGHT` | `1920` | Canvas height (px) |
| `VIDEO_FPS` | `30` | Baseline fps (presets may override) |
| `BUMPER_DURATION` | `1.5` | Intro/outro bumper length (s) |
| `TRANSITION_DURATION` | `0.3` | Scene transition length (s) |
| `TEMPLATE` | `premium` | Visual template from `templates/*.json` |
| `REMOTION_PROJECT_DIR` | `remotion` | Path to Remotion project |
| `REMOTION_CONCURRENCY` | `0` | Render threads (`0` = preset default) |
| `CAPTION_FONT_SIZE` | `48` | Caption size (px) |
| `CAPTION_FONT` | -- | Caption font family |
| `CAPTION_FONT_COLOR` | `white` | Caption color |
| `CAPTION_STROKE_COLOR` | `black` | Caption outline color |
| `CAPTION_STROKE_WIDTH` | `3` | Caption outline width |

### Media & Audio

| Setting | Default | Description |
|---------|---------|-------------|
| `IMAGE_PROVIDER` | `auto` | `auto`, `pexels`, `pixabay`, or `pollinations` |
| `IMAGE_PROVIDER_FALLBACK` | `true` | Allow fallback providers |
| `MEDIA_PREFER_VIDEOS` | `true` | Prefer stock videos over images |
| `PEXELS_API_KEY` | -- | Pexels key (optional) |
| `PIXABAY_API_KEY` | -- | Pixabay key (optional) |
| `BACKGROUND_MUSIC_PATH` | -- | Path to a music loop (optional) |
| `MUSIC_VOLUME` | `15.0` | Music level (0-100) |
| `DUCK_THRESHOLD` | `6.0` | Music ducking intensity |
| `SFX_ENABLED` | `true` | whoosh/pop/riser sound effects |
| `SFX_DIR` | `resources/sfx` | SFX folder |

### YouTube Upload

| Setting | Default | Description |
|---------|---------|-------------|
| `YOUTUBE_CLIENT_SECRETS` | `client_secrets.json` | OAuth client file |
| `UPLOAD_PRIVACY` | `public` | `private`, `unlisted`, or `public` |
| `UPLOAD_CATEGORY` | `22` | YouTube category ID |
| `UPLOAD_LANGUAGE` | `en` | Video language |
| `UPLOAD_CHANNEL_ID` | -- | Default upload channel |
| `UPLOAD_PUBLISH_AT` | -- | ISO 8601 scheduled publish time |
| `UPLOAD_PLAYLIST_ID` | -- | Auto-add videos to a playlist |

## License

MIT
