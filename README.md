# Shortube

AI-Powered YouTube Shorts & Video Generation Studio

Discover trends -> Write scripts -> Generate voiceovers -> Assemble videos (via Remotion) -> Upload -- fully automated.

## Features

### Script Generation
- **LLM-powered scripts** -- hook, body points, CTA, keywords, title, and tags generated in a single prompt
- **Retry with error recovery** -- malformed LLM output is detected and automatically retried (up to 3 times)
- **Multi-provider LLM support** -- Groq, OpenRouter, or Ollama (local, no API key needed)

### Trend Discovery Engine
Scans 3 sources for trending content in your niche:
- Hacker News (Algolia API)
- RSS Feeds (NYT, BBC, The Verge, Wired, Ars Technica)
- YouTube Search (YouTube Data API)

### Video Assembly (Remotion)
- **Word-synced captions** -- overlaid via Remotion components, timed to TTS word boundaries
- **Background music** -- pydub mixing with volume ducking during speech
- **Ken Burns effect** -- slow zoom on static images via Remotion CSS transforms
- **AI-generated scene images** -- Pollinations.ai (free, no API key), Flux model, 1080x1920
- **Intro/outro bumpers** -- animated title and CTA cards with fade transitions

### YouTube Upload & SEO
- OAuth 2.0 -- authenticated upload with token persistence
- SEO-optimized descriptions -- hook + bullet points + hashtags
- Thumbnail generation -- branded title cards via Pillow
- Scheduled publishing -- publishAt ISO 8601 support
- Channel selection -- upload to specific YouTube channels

### Web UI (React + FastAPI)
- **Dashboard** -- Generate by topic, Auto-scan, live job/video tables
- **Topics** -- Trend discovery results with status tracking
- **Videos** -- Generated video gallery with download + YouTube links
- **Settings** -- LLM, voice, video, upload settings form

### CLI (Click)
- `python -m shortube.main` -- show trends by default
- `python -m shortube.main generate -t "topic"` -- full pipeline
- `python -m shortube.main auto` -- auto-discover, generate, upload
- `python -m shortube.main set-channel UC_id` -- set upload channel

## Quick Start

### Prerequisites
```bash
# Python 3.11+
# Node.js 18+ (for Remotion rendering)
```

### Installation
```bash
git clone <repo-url>
cd shortube

# Python dependencies
pip install -r requirements.txt

# Remotion project
cd remotion
npm install
cd ..

# Web frontend
cd web
npm install
cd ..
```

### Configuration
Create a `.env` file in the project root:

```env
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

# Remotion project path (relative or absolute)
REMOTION_PROJECT_DIR=remotion
```

### Usage
```bash
# Start the web UI
hypercorn shortube.web:app --reload --bind 0.0.0.0:8000

# Or use CLI
python -m shortube.main generate -t "Amazing facts about the universe"
```

## Architecture

```
shortube/
├── main.py              # CLI entry point (Click commands)
├── pipeline.py          # 4-stage orchestrator
├── script.py            # LLM script generation
├── voice.py             # edge-tts voiceover with timestamps
├── storyboard.py        # Scene builder + Pollinations images
├── assemble.py          # Remotion video assembly (bridge)
├── remotion_bridge.py   # Python-to-Remotion CLI integration
├── web.py               # FastAPI web server + REST API
├── upload.py            # YouTube Data API v3 upload
├── discover.py          # Trend discovery engine
├── llm.py               # LLM abstraction layer
├── config.py            # Pydantic settings (.env)
├── db.py                # SQLite database
├── types.py             # Data classes
└── __init__.py

remotion/
├── package.json
├── src/
│   ├── Root.tsx              # Composition registration
│   ├── ShortubeVideo.tsx     # Main composition
│   ├── IntroBumper.tsx       # Title card animation
│   ├── SceneClip.tsx         # Image + Ken Burns zoom
│   ├── OutroBumper.tsx       # CTA card animation
│   └── Captions.tsx          # Word-synced subtitle overlay

web/
├── package.json
├── src/
│   ├── App.tsx               # Router + layout
│   ├── pages/
│   │   ├── Dashboard.tsx     # Generate, trends, jobs, videos
│   │   ├── Topics.tsx        # Topic listing
│   │   ├── Videos.tsx        # Video gallery
│   │   └── Settings.tsx      # Settings form
│   └── api/client.ts         # FastAPI client
```

### Pipeline Flow
```
Topic -> Script (LLM) -> Voiceover (edge-tts) -> Storyboard (Pollinations images)
     -> Assembly (Remotion: bumpers + zoompan + music + captions)
     -> Thumbnail (Pillow) -> YouTube Upload (OAuth 2.0)
```

## Development

```bash
# Terminal 1: Python API
hypercorn shortube.web:app --reload --bind 0.0.0.0:8000

# Terminal 2: React dev server
cd web && npm run dev

# Terminal 3: Remotion preview (optional)
cd remotion && npx remotion studio
```

### Production Build
```bash
# Build React frontend
cd web && npm run build

# Run FastAPI (serves built React app)
hypercorn shortube.web:app --bind 0.0.0.0:8000
```

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq`, `openrouter`, or `ollama` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name |
| `NICHE` | `general_facts` | Default content niche |
| `VOICE_NAME` | `en-US-AriaNeural` | edge-tts voice |
| `VOICE_SPEED` | `1.15` | Playback speed |
| `VIDEO_WIDTH` | `1080` | Video width (px) |
| `VIDEO_HEIGHT` | `1920` | Video height (px) |
| `VIDEO_FPS` | `30` | Frames per second |
| `BUMPER_DURATION` | `1.5` | Intro/outro bumper length (s) |
| `REMOTION_PROJECT_DIR` | `remotion` | Path to Remotion project |
| `BACKGROUND_MUSIC_PATH` | -- | Path to music loop |
| `UPLOAD_PRIVACY` | `public` | `private`, `unlisted`, or `public` |
| `UPLOAD_CHANNEL_ID` | -- | YouTube channel ID |

## License

MIT
