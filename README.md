# TikTok Content Engine

Automated pipeline for generating faceless TikTok videos about hair restoration and anti-aging education.

**What it does:** You provide a monthly list of content topics. The engine generates scripts, voiceovers, subtitled vertical videos, captions, hashtags, and optionally posts to TikTok.

## Quick Start

```bash
cp .env.example .env        # Add your API keys
pip install -r requirements.txt
python main.py test          # Generate one test video
python main.py status        # Check results
```

## Stack

- **Scripts:** Claude API (Anthropic)
- **Voiceover:** OpenAI TTS (or ElevenLabs)
- **Video:** MoviePy (local rendering)
- **Posting:** TikTok Content Posting API
- **Database:** CSV (local, portable)

## Pipeline Stages

```
Topic → Script → Compliance Check → Voiceover → Video → Captions → Ready → Post
```

Every stage is idempotent. If something fails, fix it and re-run — the pipeline picks up where it left off.

## Full Documentation

See [docs/SETUP.md](docs/SETUP.md) for installation, API setup, and usage instructions.
