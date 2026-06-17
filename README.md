# ViraLab Studio — GitHub Actions Video Pipeline

Auto-generates and uploads YouTube videos. 100% free.

## How It Works

1. Edit `topics.json` — add your video topic
2. Commit the file — GitHub Actions runs automatically
3. Videos upload directly to your YouTube channel
4. Check your YouTube Studio — videos appear within 30-60 minutes

## Add a New Topic

Edit `topics.json` and add an entry with `"status": "pending"`:

```json
[
  {
    "topic": "Your video series topic here",
    "audience": "kids",
    "language": "hi-IN",
    "voice": "hi-IN-SwaraNeural",
    "episodes": 3,
    "status": "pending"
  }
]
```

### Audience Options
| Value | For |
|---|---|
| `toddler` | Children 2–4 years (3 min videos) |
| `kids` | Children 4–8 years (6 min videos) |
| `preteen` | Children 8–12 years (10 min) |
| `adult` | Adults (10–15 min) |

### Language + Voice Options
| Language | Voice |
|---|---|
| Hindi | `hi-IN-SwaraNeural` or `hi-IN-MadhurNeural` |
| English India | `en-IN-NeerjaNeural` |
| English US | `en-US-AriaNeural` |
| Tamil | `ta-IN-PallaviNeural` |
| Telugu | `te-IN-ShrutiNeural` |

## Required GitHub Secrets

Go to: Settings → Secrets and variables → Actions → New repository secret

| Secret Name | Where to get it |
|---|---|
| `PEXELS_API_KEY` | pexels.com/api (free) |
| `YOUTUBE_CLIENT_ID` | Google Cloud Console |
| `YOUTUBE_CLIENT_SECRET` | Google Cloud Console |
| `YOUTUBE_REFRESH_TOKEN` | OAuth Playground |
| `ANTHROPIC_API_KEY` | console.anthropic.com (optional) |

## Free Stack

- 🎬 **Pexels** — HD video clips (free API)
- 🎙 **Microsoft Edge TTS** — voiceover in Hindi, English, Tamil (completely free)
- 🎞 **MoviePy + FFmpeg** — video assembly (open source)
- 📺 **YouTube Data API v3** — auto-upload (free)
- ⬡ **Claude AI** — script writing (optional, has fallback templates)

**Total cost: ₹0**
