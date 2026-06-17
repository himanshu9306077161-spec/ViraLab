"""
make_video.py — ViraLab Studio Video Pipeline
==============================================
Runs on GitHub Actions. Completely free.

Pipeline:
  1. Read pending topic from topics.json
  2. Generate script with Claude AI
  3. Fetch HD video clips from Pexels API
  4. Generate voiceover with Microsoft Edge TTS
  5. Assemble video with MoviePy + FFmpeg
  6. Create thumbnail with Pillow
  7. Upload to YouTube with YouTube Data API v3
  8. Mark topic as done in topics.json

Environment variables (set as GitHub Secrets):
  PEXELS_API_KEY       — from pexels.com/api (free)
  YOUTUBE_CLIENT_ID    — from Google Cloud Console
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN
  ANTHROPIC_API_KEY    — from console.anthropic.com (optional)
"""

import os, json, sys, time, asyncio, requests, textwrap, random
from datetime import datetime
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────
PEXELS_KEY     = os.environ.get("PEXELS_API_KEY","")
YT_CLIENT_ID   = os.environ.get("YOUTUBE_CLIENT_ID","")
YT_CLIENT_SEC  = os.environ.get("YOUTUBE_CLIENT_SECRET","")
YT_REFRESH     = os.environ.get("YOUTUBE_REFRESH_TOKEN","")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY","")

TOPICS_FILE = "topics.json"
OUT_DIR     = Path("videos")
OUT_DIR.mkdir(exist_ok=True)

IST_OFFSET  = 5.5 * 3600  # IST = UTC+5:30

# ── AUDIENCE CONFIGS ─────────────────────────────────────────────
AUDIENCE_CONFIG = {
    "toddler": {
        "duration":    180,   # 3 minutes
        "clip_count":  6,
        "font_size":   48,
        "music_vol":   0.3,
        "search_tags": ["colorful cartoon animals", "cute animals children", "bright colors kids"],
    },
    "kids": {
        "duration":    360,   # 6 minutes
        "clip_count":  10,
        "font_size":   40,
        "music_vol":   0.2,
        "search_tags": ["children education", "kids learning", "fun science"],
    },
    "adult": {
        "duration":    600,   # 10 minutes
        "clip_count":  15,
        "font_size":   34,
        "music_vol":   0.15,
        "search_tags": ["professional business", "nature documentary", "technology"],
    },
}

# ── EPISODE TITLE GENERATOR ──────────────────────────────────────
def plan_episodes(topic, audience, count):
    templates = {
        "toddler": [
            f"Hello {topic}! 🌟", f"{topic} and Colours 🎨",
            f"{topic}'s Friends 🤝", f"{topic} Eats Healthy 🍎",
            f"{topic} Plays Outside 🌳", f"{topic} Goes to Bed 🌙",
            f"{topic} Sings a Song 🎵", f"{topic} Loves Family 👨‍👩‍👧",
            f"{topic} Says Goodbye 👋", f"{topic} and Numbers 🔢",
        ],
        "kids": [
            f"What is {topic}?", f"The Story of {topic}",
            f"How {topic} Works", f"{topic} in Daily Life",
            f"Amazing Facts: {topic}", f"{topic} Around the World",
            f"{topic} Experiments", f"{topic} Heroes",
            f"{topic} and the Future", f"{topic} Quiz!",
        ],
        "adult": [
            f"{topic} — Introduction", f"{topic} — Core Concepts",
            f"{topic} — Intermediate", f"{topic} — Advanced",
            f"{topic} — Real World Use", f"{topic} — Common Mistakes",
            f"{topic} — Pro Tips", f"{topic} — Case Studies",
            f"{topic} — Expert Level", f"{topic} — Final Mastery",
        ],
    }
    titles = templates.get(audience, templates["kids"])
    return titles[:count]


# ── SCRIPT GENERATOR ─────────────────────────────────────────────
def generate_script(title, topic, audience, language, ep_num, total_eps):
    """Generate episode script — uses Claude API if key available, else template."""
    if ANTHROPIC_KEY:
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 800,
                    "messages": [{
                        "role": "user",
                        "content": f"""Write a short YouTube video script for:
Title: {title}
Topic series: {topic}
Audience: {audience}
Language: {language}
Episode: {ep_num} of {total_eps}

Rules:
- Keep it simple and engaging for the audience
- 150-200 words maximum
- Natural speaking tone
- Start with a hook
- End with 'See you in the next episode!'
- Write ONLY the spoken narration, no stage directions
- Write in the same language as: {language}

Script:"""
                    }]
                },
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json()["content"][0]["text"].strip()
        except Exception as e:
            print(f"  Claude API error: {e} — using template")

    # Template fallback (no API key needed)
    scripts = {
        "toddler": f"""Hello friends! Welcome to {title}!
Today we are going to learn something wonderful together.
Are you ready? Let's go!

{topic} is so much fun to learn about.
Look at all these beautiful colours and shapes!
Can you see them? Yellow, red, blue, green!

Let us count together — one, two, three!
Very good! You are so smart!

Remember, learning is fun when we do it together.
I love you all so much!
See you in the next episode!""",

        "kids": f"""Hey everyone! Welcome back to our {topic} series!
I'm so excited to share Episode {ep_num} with you today — {title}!

Have you ever wondered about this? Well today we find out!

{topic} is one of the most interesting things in the world.
Here are the most amazing facts you need to know.
First — it is much bigger than you think!
Second — it affects your daily life in surprising ways!
Third — scientists are still discovering new things about it!

Now you know the basics. Pretty cool, right?
Keep being curious and never stop learning!
See you in the next episode!""",

        "adult": f"""Welcome back! In today's episode — {title}.

If you've been following our {topic} series, you know we've been building
from the ground up. Today we take it to the next level.

Here's what we're covering today:
First, the core concept you absolutely must understand.
Second, how to apply this in real situations.
Third, the most common mistakes and how to avoid them.

Let's dive straight in.

The key insight is that {topic} follows a clear pattern once you know what to look for.
Most people miss this because they focus on the wrong things.
But once you see it — you can't unsee it.

Apply this today and you'll immediately notice the difference.

I'll see you in the next episode where we go even deeper.
Don't forget to subscribe so you never miss an upload!""",
    }
    return scripts.get(audience, scripts["kids"])


# ── PEXELS VIDEO FETCH ───────────────────────────────────────────
def fetch_pexels_videos(query, count=3, min_duration=5):
    """Fetch free HD video clips from Pexels."""
    if not PEXELS_KEY:
        print("  ⚠ No Pexels key — using placeholder clips")
        return []

    videos = []
    page = 1
    while len(videos) < count and page <= 3:
        try:
            r = requests.get(
                "https://api.pexels.com/v1/videos/search",
                headers={"Authorization": PEXELS_KEY},
                params={"query": query, "per_page": 15, "page": page,
                        "size": "medium", "orientation": "landscape"},
                timeout=15
            )
            if r.status_code != 200:
                print(f"  Pexels error: {r.status_code}")
                break
            data = r.json()
            for v in data.get("videos", []):
                if v.get("duration", 0) >= min_duration:
                    # Get best quality file (HD)
                    files = sorted(
                        [f for f in v.get("video_files", []) if f.get("quality") in ["hd","sd"]],
                        key=lambda x: x.get("width", 0), reverse=True
                    )
                    if files:
                        videos.append({
                            "url": files[0]["link"],
                            "width": files[0].get("width", 1920),
                            "height": files[0].get("height", 1080),
                            "duration": v["duration"],
                        })
                if len(videos) >= count:
                    break
            page += 1
            time.sleep(0.5)
        except Exception as e:
            print(f"  Pexels fetch error: {e}")
            break

    print(f"  Fetched {len(videos)} video clips from Pexels ✅")
    return videos


def download_video(url, path):
    """Download a video file."""
    try:
        r = requests.get(url, stream=True, timeout=60)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        return False


# ── EDGE TTS VOICEOVER ───────────────────────────────────────────
async def generate_voiceover_async(text, voice, output_path):
    """Generate voiceover using Microsoft Edge TTS (completely free)."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def generate_voiceover(text, voice, output_path):
    asyncio.run(generate_voiceover_async(text, voice, output_path))
    size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    print(f"  Voiceover generated: {size//1024}KB ✅")


# ── THUMBNAIL GENERATOR ──────────────────────────────────────────
def create_thumbnail(title, topic, ep_num, audience, output_path):
    """Create YouTube thumbnail with Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # Dark gradient background
        W, H = 1280, 720
        img = Image.new("RGB", (W, H), color=(5, 8, 16))
        draw = ImageDraw.Draw(img)

        # Gradient overlay
        for y in range(H):
            r = int(5 + (30-5) * y/H)
            g = int(8 + (22-8) * y/H)
            b = int(16 + (40-16) * y/H)
            draw.line([(0,y),(W,y)], fill=(r,g,b))

        # Accent bar
        draw.rectangle([0, 0, W, 8], fill=(99, 102, 241))
        draw.rectangle([0, H-8, W, H], fill=(99, 102, 241))

        # Episode badge
        draw.rectangle([40, 40, 180, 90], fill=(99, 102, 241))
        draw.text((110, 65), f"EP {ep_num:02d}", fill="white", anchor="mm")

        # Topic text (top)
        draw.text((W//2, 140), topic.upper()[:40], fill=(100, 130, 200), anchor="mm")

        # Main title (large, centered, wrapped)
        words = title.split()
        lines = []
        line = ""
        for w in words:
            if len(line + w) < 25:
                line += w + " "
            else:
                lines.append(line.strip())
                line = w + " "
        if line: lines.append(line.strip())

        y_start = H//2 - len(lines)*45
        for i, l in enumerate(lines[:3]):
            draw.text((W//2, y_start + i*80), l,
                     fill="white", anchor="mm")

        # Save
        img.save(output_path, "JPEG", quality=95)
        print(f"  Thumbnail created: {W}x{H} ✅")
        return True
    except Exception as e:
        print(f"  Thumbnail error: {e}")
        return False


# ── VIDEO ASSEMBLY ───────────────────────────────────────────────
def assemble_video(clip_paths, audio_path, output_path, target_duration):
    """Assemble video clips + voiceover using MoviePy."""
    try:
        from moviepy.editor import (VideoFileClip, AudioFileClip,
                                    concatenate_videoclips, CompositeAudioClip)

        # Load audio to get actual duration
        audio = AudioFileClip(audio_path)
        audio_dur = audio.duration
        print(f"  Audio duration: {audio_dur:.1f}s")

        if not clip_paths:
            print("  No video clips — creating audio-only video")
            # Create black video with audio
            from moviepy.editor import ColorClip
            black = ColorClip(size=(1920, 1080), color=[0,0,0], duration=audio_dur)
            black = black.set_audio(audio)
            black.write_videofile(output_path, fps=24, codec="libx264",
                                  audio_codec="aac", logger=None)
            return True

        # Load and resize video clips
        clips = []
        for cp in clip_paths:
            try:
                vc = VideoFileClip(cp).resize((1920, 1080))
                clips.append(vc)
            except Exception as e:
                print(f"  Clip load error {cp}: {e}")

        if not clips:
            print("  No valid clips loaded")
            return False

        # Loop clips to match audio duration
        final_clips = []
        total = 0
        while total < audio_dur:
            for c in clips:
                needed = audio_dur - total
                if c.duration <= needed:
                    final_clips.append(c)
                    total += c.duration
                else:
                    final_clips.append(c.subclip(0, needed))
                    total += needed
                    break
            if total >= audio_dur:
                break

        # Concatenate video
        video = concatenate_videoclips(final_clips, method="compose")
        video = video.subclip(0, audio_dur)

        # Add voiceover
        video = video.set_audio(audio)

        # Export
        video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )
        print(f"  Video assembled: {output_path} ✅")

        # Cleanup
        audio.close()
        for c in clips: c.close()
        return True

    except Exception as e:
        print(f"  Assembly error: {e}")
        import traceback; traceback.print_exc()
        return False


# ── YOUTUBE UPLOAD ───────────────────────────────────────────────
def get_youtube_service():
    """Get authenticated YouTube service."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=YT_REFRESH,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SEC,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(video_path, thumbnail_path, title, description, tags, ep_num):
    """Upload video to YouTube."""
    if not YT_REFRESH:
        print("  ⚠ No YouTube credentials — skipping upload")
        return None

    try:
        from googleapiclient.http import MediaFileUpload

        youtube = get_youtube_service()

        # Upload video
        print(f"  Uploading to YouTube: {title}")
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:500],
                "categoryId": "27",  # Education
                "defaultLanguage": "hi",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024*1024*5  # 5MB chunks
        )

        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  Upload progress: {pct}%")

        video_id = response["id"]
        print(f"  ✅ Uploaded! https://youtube.com/watch?v={video_id}")

        # Set thumbnail
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
                ).execute()
                print("  ✅ Thumbnail set!")
            except Exception as e:
                print(f"  Thumbnail set error: {e}")

        return video_id

    except Exception as e:
        print(f"  YouTube upload error: {e}")
        import traceback; traceback.print_exc()
        return None


# ── MAIN PIPELINE ────────────────────────────────────────────────
def process_topic(topic_obj):
    topic    = topic_obj["topic"]
    audience = topic_obj.get("audience", "kids")
    language = topic_obj.get("language", "hi-IN")
    voice    = topic_obj.get("voice", "hi-IN-SwaraNeural")
    episodes = topic_obj.get("episodes", 3)
    series_name = topic_obj.get("series_name", topic)

    cfg      = AUDIENCE_CONFIG.get(audience, AUDIENCE_CONFIG["kids"])
    titles   = plan_episodes(topic, audience, episodes)

    print(f"\n{'='*60}")
    print(f"  PROCESSING: {topic}")
    print(f"  Audience: {audience} | Language: {language} | Episodes: {episodes}")
    print(f"{'='*60}")

    results = []
    for ep_num, title in enumerate(titles, 1):
        print(f"\n── Episode {ep_num}/{episodes}: {title}")

        ep_dir = OUT_DIR / f"ep_{ep_num:02d}"
        ep_dir.mkdir(exist_ok=True)

        # 1. Generate script
        print("  Step 1: Generating script...")
        script = generate_script(title, topic, audience, language, ep_num, episodes)
        script_path = ep_dir / "script.txt"
        script_path.write_text(script, encoding="utf-8")
        print(f"  Script: {len(script)} chars ✅")

        # 2. Fetch video clips from Pexels
        print("  Step 2: Fetching Pexels videos...")
        search_query = random.choice(cfg["search_tags"]) + " " + topic.split()[0]
        clips_info = fetch_pexels_videos(search_query, count=cfg["clip_count"])

        clip_paths = []
        for j, clip in enumerate(clips_info[:cfg["clip_count"]]):
            clip_path = ep_dir / f"clip_{j:02d}.mp4"
            print(f"  Downloading clip {j+1}/{len(clips_info)}...")
            if download_video(clip["url"], str(clip_path)):
                clip_paths.append(str(clip_path))
            time.sleep(0.3)

        # 3. Generate voiceover
        print("  Step 3: Generating voiceover (Edge TTS)...")
        audio_path = str(ep_dir / "voiceover.mp3")
        try:
            generate_voiceover(script, voice, audio_path)
        except Exception as e:
            print(f"  TTS error: {e}")
            # Fallback to English
            generate_voiceover(script, "en-IN-NeerjaNeural", audio_path)

        # 4. Assemble video
        print("  Step 4: Assembling video...")
        video_path = str(ep_dir / "final_video.mp4")
        ok = assemble_video(clip_paths, audio_path, video_path, cfg["duration"])
        if not ok:
            print(f"  ❌ Assembly failed for episode {ep_num}")
            continue

        # 5. Create thumbnail
        print("  Step 5: Creating thumbnail...")
        thumb_path = str(ep_dir / "thumbnail.jpg")
        create_thumbnail(title, topic, ep_num, audience, thumb_path)

        # 6. Upload to YouTube
        print("  Step 6: Uploading to YouTube...")
        description = f"""{title}

This is Episode {ep_num} of {episodes} in our {series_name} series.

{script[:500]}...

━━━━━━━━━━━━━━━━━━━━━━━━
Subscribe for more videos!
━━━━━━━━━━━━━━━━━━━━━━━━

#education #{audience} #{topic.replace(' ','').lower()} #learning #youtube"""

        tags = [topic, series_name, audience, "education", "learning",
                "youtube", title, f"episode{ep_num}"]

        video_id = upload_to_youtube(
            video_path, thumb_path, title, description, tags, ep_num
        )

        results.append({
            "ep": ep_num,
            "title": title,
            "video_id": video_id,
            "status": "published" if video_id else "assembled",
        })

        # Cleanup clip files to save space
        for cp in clip_paths:
            try: os.remove(cp)
            except: pass

        print(f"  ✅ Episode {ep_num} complete!")
        time.sleep(2)  # Rate limiting

    return results


def main():
    print("="*60)
    print("  VIRALAB STUDIO — VIDEO PIPELINE")
    now_ist = datetime.utcnow()
    print(f"  {now_ist.strftime('%d %b %Y %H:%M')} UTC")
    print("="*60)

    # Check credentials
    print(f"\nCredentials check:")
    print(f"  Pexels API:  {'✅' if PEXELS_KEY else '⚠ Missing — will skip Pexels'}")
    print(f"  YouTube:     {'✅' if YT_REFRESH else '⚠ Missing — will skip upload'}")
    print(f"  Claude AI:   {'✅ (better scripts)' if ANTHROPIC_KEY else '⚪ Using templates'}")

    # Load topics
    if not os.path.exists(TOPICS_FILE):
        print(f"\n❌ {TOPICS_FILE} not found!")
        sys.exit(1)

    with open(TOPICS_FILE, "r") as f:
        topics = json.load(f)

    pending = [t for t in topics if t.get("status") == "pending"]
    print(f"\nPending topics: {len(pending)}")

    if not pending:
        print("No pending topics. Add a topic to topics.json with status: 'pending'")
        sys.exit(0)

    # Process first pending topic
    topic_obj = pending[0]
    results = process_topic(topic_obj)

    # Mark as done
    for t in topics:
        if t == topic_obj:
            t["status"] = "done"
            t["completed"] = datetime.utcnow().isoformat()
            t["results"] = results

    with open(TOPICS_FILE, "w") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  ✅ PIPELINE COMPLETE")
    print(f"  Episodes processed: {len(results)}")
    published = [r for r in results if r.get("video_id")]
    print(f"  Uploaded to YouTube: {len(published)}")
    for r in published:
        print(f"    EP{r['ep']}: https://youtube.com/watch?v={r['video_id']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
