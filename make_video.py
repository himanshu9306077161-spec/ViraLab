"""
make_video.py  —  ViraLab Studio Pipeline v2
=============================================
Fixed issues from v1:
  - imageio-ffmpeg added (moviepy needs it for audio)
  - Better error handling at every step
  - Professional thumbnail with Pillow (gradients, shadow text, badges)
  - Pexels fallback when no clips found
  - YouTube token auto-refresh
  - Script saves to topics.json after each episode (not just at end)
  - Edge TTS with proper async handling
  - Disk cleanup after each episode

Runs on GitHub Actions (ubuntu-latest, free tier).
100% free. No paid APIs required.
"""

import os, sys, json, time, asyncio, requests, re
from datetime import datetime
from pathlib import Path

# ── CREDENTIALS ───────────────────────────────────────────────────
PEXELS_KEY    = os.environ.get("PEXELS_API_KEY", "")
YT_CLIENT_ID  = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SEC = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH    = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
CLAUDE_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

TOPICS_FILE = "topics.json"
OUT_DIR     = Path("output")
OUT_DIR.mkdir(exist_ok=True)

# ── AUDIENCE SETTINGS ─────────────────────────────────────────────
AUDIENCE = {
    "toddler": {
        "duration":  180,
        "clips":     5,
        "voice_hi":  "hi-IN-SwaraNeural",
        "voice_en":  "en-IN-NeerjaNeural",
        "pexels":    ["colorful cartoon", "cute animals children", "bright colors kids"],
        "category":  "27",
    },
    "kids": {
        "duration":  360,
        "clips":     8,
        "voice_hi":  "hi-IN-SwaraNeural",
        "voice_en":  "en-IN-NeerjaNeural",
        "pexels":    ["children learning", "school kids education", "fun science nature"],
        "category":  "27",
    },
    "preteen": {
        "duration":  480,
        "clips":     10,
        "voice_hi":  "hi-IN-MadhurNeural",
        "voice_en":  "en-IN-NeerjaNeural",
        "pexels":    ["science experiment", "space exploration", "technology innovation"],
        "category":  "27",
    },
    "adult": {
        "duration":  600,
        "clips":     12,
        "voice_hi":  "hi-IN-MadhurNeural",
        "voice_en":  "en-US-AriaNeural",
        "pexels":    ["professional business", "nature documentary", "city landscape"],
        "category":  "27",
    },
}

VOICE_MAP = {
    "hi-IN": "hi-IN-SwaraNeural",
    "hi-IN-M": "hi-IN-MadhurNeural",
    "en-IN": "en-IN-NeerjaNeural",
    "en-US": "en-US-AriaNeural",
    "ta-IN": "ta-IN-PallaviNeural",
    "te-IN": "te-IN-ShrutiNeural",
    "mr-IN": "mr-IN-AarohiNeural",
}

# ── EPISODE TITLES ────────────────────────────────────────────────
def plan_episodes(topic, aud, count):
    T = {
        "toddler": [
            f"Hello {topic}! 🌟 — Introduction",
            f"{topic} and Beautiful Colours 🎨",
            f"{topic} Makes New Friends 🤝",
            f"{topic} Eats Healthy Food 🍎",
            f"{topic} Plays in the Garden 🌳",
            f"{topic} Learns to Count 🔢",
            f"{topic} Sings a Happy Song 🎵",
            f"{topic} Loves Family 👨‍👩‍👧",
            f"{topic} Draws and Paints 🖌️",
            f"Goodbye from {topic}! See You Soon 👋",
        ],
        "kids": [
            f"What is {topic}? — Fun Introduction",
            f"The Amazing History of {topic}",
            f"How {topic} Works — Step by Step",
            f"{topic} in Our Daily Life",
            f"5 Amazing Facts About {topic}",
            f"{topic} Around the World 🌍",
            f"{topic} Experiments You Can Try",
            f"Famous {topic} Heroes and Champions",
            f"{topic} and the Future",
            f"{topic} — Final Quiz and Review!",
        ],
        "adult": [
            f"{topic} — Complete Beginner's Guide",
            f"{topic} — Core Fundamentals",
            f"{topic} — Intermediate Techniques",
            f"{topic} — Advanced Strategies",
            f"{topic} — Real World Applications",
            f"{topic} — Most Common Mistakes",
            f"{topic} — Expert Tips and Tricks",
            f"{topic} — Case Studies",
            f"{topic} — Future Trends",
            f"{topic} — Master Class Finale",
        ],
    }
    titles = T.get(aud, T["kids"])
    # Extend if needed
    while len(titles) < count:
        titles.append(f"{topic} — Part {len(titles)+1}")
    return titles[:count]


# ── SCRIPT GENERATION ─────────────────────────────────────────────
def generate_script(title, topic, aud, lang, ep_num, total):
    """Generate script via Claude API or template fallback."""
    if CLAUDE_KEY:
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 700,
                    "messages": [{
                        "role": "user",
                        "content": (
                            f"Write a YouTube video narration script.\n"
                            f"Title: {title}\n"
                            f"Series: {topic} ({total} episodes)\n"
                            f"Episode: {ep_num} of {total}\n"
                            f"Audience: {aud}\n"
                            f"Language: {lang}\n\n"
                            f"Rules:\n"
                            f"- 150 to 200 words only\n"
                            f"- Spoken words only — no stage directions, no brackets\n"
                            f"- Natural, warm, engaging tone\n"
                            f"- Start with an exciting hook\n"
                            f"- End with: See you in the next episode!\n"
                            f"- Match language: {lang}\n\n"
                            f"Write ONLY the narration text:"
                        )
                    }]
                },
                timeout=25,
            )
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"].strip()
                if len(text) > 50:
                    return text
        except Exception as e:
            print(f"  Claude error: {e} — using template")

    # Fallback templates
    templates = {
        "toddler": f"""Welcome friends! I am so happy to see you today!

Today we are going to learn about {title}. Are you excited? I am!

{topic} is so much fun. Can you see all the beautiful colours?
Red! Yellow! Blue! Green!

Let us count together — one, two, three, four, five!
Very good! You are so smart and wonderful!

Always be kind, always be curious, and always keep learning.
I love you so much!

See you in the next episode!""",

        "kids": f"""Hey everyone! Welcome back to our {topic} series!

Today — Episode {ep_num} — {title}!

Have you ever thought about this before? Well today we find out everything!

Here are the three most important things to know:
Number one — {topic} is part of our everyday world in ways you never imagined.
Number two — Scientists have been studying this for hundreds of years.
Number three — You can explore this yourself right at home!

Now you know something amazing. Share it with your friends!
Keep being curious and never stop asking questions.

See you in the next episode!""",

        "adult": f"""Welcome to Episode {ep_num} of our {topic} series — {title}.

If you have been following along you are already ahead of most people.
Today we go deeper.

The most important insight about {topic} that most people miss is this:
It is not about what you know — it is about how you apply it.

Here is the framework that works:
First, understand the core principle completely.
Second, practice it in a low-stakes environment.
Third, iterate based on what the results show you.

This is exactly how experts in {topic} think and operate.

Apply this today. You will see results immediately.

See you in the next episode!""",
    }
    return templates.get(aud, templates["kids"])


# ── PEXELS HD VIDEO FETCH ─────────────────────────────────────────
def fetch_pexels(query, count=6):
    """Fetch HD video clips from Pexels. Returns list of download URLs."""
    if not PEXELS_KEY:
        print("  ⚠ No Pexels key — videos will be black screen")
        return []

    videos = []
    for page in range(1, 4):
        if len(videos) >= count:
            break
        try:
            r = requests.get(
                "https://api.pexels.com/v1/videos/search",
                headers={"Authorization": PEXELS_KEY},
                params={
                    "query": query,
                    "per_page": 15,
                    "page": page,
                    "size": "medium",
                    "orientation": "landscape",
                },
                timeout=15,
            )
            if r.status_code == 403:
                print("  Pexels: Invalid API key")
                break
            if r.status_code != 200:
                print(f"  Pexels error: {r.status_code}")
                break

            for v in r.json().get("videos", []):
                if v.get("duration", 0) < 4:
                    continue
                # Pick best quality file
                files = [
                    f for f in v.get("video_files", [])
                    if f.get("quality") in ("hd", "sd")
                    and f.get("width", 0) >= 1280
                ]
                if not files:
                    files = [f for f in v.get("video_files", [])
                             if f.get("quality") in ("hd", "sd")]
                if files:
                    best = max(files, key=lambda f: f.get("width", 0))
                    videos.append({
                        "url": best["link"],
                        "duration": v["duration"],
                        "w": best.get("width", 0),
                        "h": best.get("height", 0),
                    })
                if len(videos) >= count:
                    break

            time.sleep(0.4)
        except Exception as e:
            print(f"  Pexels fetch error: {e}")
            break

    print(f"  Pexels: {len(videos)} clips found")
    return videos


def download_clip(url, path):
    """Download video clip with timeout and progress."""
    try:
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
        size = os.path.getsize(path)
        return size > 10000  # Must be > 10KB
    except Exception as e:
        print(f"  Download error: {e}")
        return False


# ── EDGE TTS VOICEOVER ────────────────────────────────────────────
async def _tts(text, voice, path):
    import edge_tts
    tts = edge_tts.Communicate(text, voice, rate="+0%", volume="+0%")
    await tts.save(path)

def generate_voice(text, voice, path):
    """Generate voiceover with Edge TTS. Tries primary then English fallback."""
    try:
        asyncio.run(_tts(text, voice, path))
        size = os.path.getsize(path)
        if size > 5000:
            print(f"  Voice: {size//1024}KB  voice={voice} ✅")
            return True
    except Exception as e:
        print(f"  TTS error ({voice}): {e}")

    # Fallback to English
    fallback = "en-IN-NeerjaNeural"
    try:
        asyncio.run(_tts(text, fallback, path))
        size = os.path.getsize(path)
        if size > 5000:
            print(f"  Voice fallback ({fallback}): {size//1024}KB ✅")
            return True
    except Exception as e:
        print(f"  TTS fallback error: {e}")
        return False


# ── PROFESSIONAL THUMBNAIL ────────────────────────────────────────
ACCENT_COLORS = {
    "toddler": [(255, 180, 0), (255, 100, 150), (100, 200, 255)],
    "kids":    [(99, 102, 241), (6, 182, 212), (16, 185, 129)],
    "preteen": [(245, 158, 11), (239, 68, 68), (99, 102, 241)],
    "adult":   [(6, 182, 212), (99, 102, 241), (16, 185, 129)],
}

def create_thumbnail(title, series_name, ep_num, aud, out_path):
    """
    Professional 1280x720 YouTube thumbnail.
    Features: gradient background, glow effect, shadow text,
    episode badge, series name, accent bar, branding.
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont

        W, H = 1280, 720
        colors = ACCENT_COLORS.get(aud, ACCENT_COLORS["kids"])
        C1, C2, C3 = colors  # three accent colours

        # ── BACKGROUND ──────────────────────────────────────────────
        img = Image.new("RGB", (W, H), (4, 6, 18))
        draw = ImageDraw.Draw(img)

        # Dark gradient base
        for y in range(H):
            t = y / H
            r = int(4  + t * 12)
            g = int(6  + t * 8)
            b = int(18 + t * 22)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Radial glow (bottom-left)
        glow_x, glow_y = int(W * 0.15), int(H * 0.75)
        for rad in range(320, 0, -8):
            t = 1 - rad / 320
            alpha = int(t * 55)
            rc = max(0, min(255, C1[0]//6 + alpha))
            gc = max(0, min(255, C1[1]//6 + alpha))
            bc = max(0, min(255, C1[2]//6 + alpha))
            draw.ellipse(
                [glow_x - rad, glow_y - rad, glow_x + rad, glow_y + rad],
                fill=(rc, gc, bc)
            )

        # Secondary glow (top-right)
        glow_x2, glow_y2 = int(W * 0.88), int(H * 0.2)
        for rad in range(200, 0, -8):
            t = 1 - rad / 200
            alpha = int(t * 40)
            rc = max(0, min(255, C2[0]//8 + alpha))
            gc = max(0, min(255, C2[1]//8 + alpha))
            bc = max(0, min(255, C2[2]//8 + alpha))
            draw.ellipse(
                [glow_x2 - rad, glow_y2 - rad, glow_x2 + rad, glow_y2 + rad],
                fill=(rc, gc, bc)
            )

        # ── GRADIENT TOP BAR (10px) ──────────────────────────────────
        for x in range(W):
            t = x / W
            r2 = int(C1[0] + t * (C2[0] - C1[0]))
            g2 = int(C1[1] + t * (C2[1] - C1[1]))
            b2 = int(C1[2] + t * (C2[2] - C1[2]))
            draw.line([(x, 0), (x, 9)], fill=(r2, g2, b2))

        # ── BOTTOM BAR (8px) ─────────────────────────────────────────
        for x in range(W):
            t = x / W
            r2 = int(C2[0] + t * (C3[0] - C2[0]))
            g2 = int(C2[1] + t * (C3[1] - C2[1]))
            b2 = int(C2[2] + t * (C3[2] - C2[2]))
            draw.line([(x, H - 9), (x, H - 1)], fill=(r2, g2, b2))

        # ── EPISODE BADGE ────────────────────────────────────────────
        bx, by, bw, bh = 44, 38, 156, 64
        # Badge shadow
        draw.rounded_rectangle(
            [bx + 4, by + 4, bx + bw + 4, by + bh + 4],
            radius=14, fill=(0, 0, 0)
        )
        # Badge background
        draw.rounded_rectangle(
            [bx, by, bx + bw, by + bh],
            radius=14, fill=C1
        )
        # Badge text
        ep_text = f"EP {ep_num:02d}"
        draw.text((bx + bw // 2 + 2, by + bh // 2 + 2), ep_text,
                  fill=(0, 0, 0), anchor="mm")
        draw.text((bx + bw // 2, by + bh // 2), ep_text,
                  fill=(255, 255, 255), anchor="mm")

        # ── SERIES NAME ──────────────────────────────────────────────
        series_short = (series_name[:40] + "…") if len(series_name) > 40 else series_name
        # Shadow
        draw.text((W // 2 + 2, 162), series_short.upper(), fill=(0, 0, 0), anchor="mm")
        # Text
        draw.text((W // 2, 160), series_short.upper(), fill=(160, 190, 230), anchor="mm")

        # ── MAIN TITLE ───────────────────────────────────────────────
        # Clean title: remove emoji for better rendering
        clean_title = re.sub(r'[^\w\s\-–—:!?,.]', '', title).strip()

        # Word wrap at 18 chars per line
        words = clean_title.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if len(test) <= 18:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        lines = lines[:3]

        # Calculate vertical center
        n = len(lines)
        line_h = 110
        total_h = n * line_h
        y0 = H // 2 - total_h // 2 + 30

        for i, line in enumerate(lines):
            cy = y0 + i * line_h
            # Black shadow (multiple offsets for thick shadow)
            for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,4),(4,0),(-4,0),(0,-4)]:
                draw.text((W // 2 + dx, cy + dy), line,
                          fill=(0, 0, 0), anchor="mm")
            # Main white text
            draw.text((W // 2, cy), line,
                      fill=(255, 255, 255), anchor="mm")

        # ── AUDIENCE BADGE (top right) ───────────────────────────────
        aud_labels = {
            "toddler": "KIDS 2-4",
            "kids":    "KIDS 4-8",
            "preteen": "AGE 8-12",
            "teen":    "TEENS",
            "adult":   "ADULTS",
        }
        aud_label = aud_labels.get(aud, "EDUCATION")
        abx = W - 200
        draw.rounded_rectangle([abx, 38, W - 44, 102],
                               radius=14, fill=C3)
        draw.text(((abx + W - 44) // 2 + 2, 72),
                  aud_label, fill=(0, 0, 0), anchor="mm")
        draw.text(((abx + W - 44) // 2, 70),
                  aud_label, fill=(255, 255, 255), anchor="mm")

        # ── BOTTOM BRANDING STRIP ────────────────────────────────────
        draw.rectangle([0, H - 58, W, H - 10], fill=(8, 12, 30))
        draw.text((W // 2 + 1, H - 34 + 1), "ViraLab AI  •  Free Education Series",
                  fill=(0, 0, 0), anchor="mm")
        draw.text((W // 2, H - 34), "ViraLab AI  •  Free Education Series",
                  fill=(70, 90, 140), anchor="mm")

        # ── DECORATIVE CORNER DOTS ───────────────────────────────────
        for (cx, cy) in [(44, H - 78), (W - 44, H - 78)]:
            draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=C2)
            draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 255, 255))

        # ── SAVE ──────────────────────────────────────────────────────
        img.save(out_path, "JPEG", quality=97, optimize=True, subsampling=0)
        size = os.path.getsize(out_path) // 1024
        print(f"  Thumbnail: {W}x{H} | {size}KB ✅")
        return True

    except Exception as e:
        print(f"  Thumbnail error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── VIDEO ASSEMBLY ────────────────────────────────────────────────
def assemble_video(clip_paths, audio_path, out_path):
    """
    Assemble final video:
    - Loops video clips to match voiceover duration
    - Adds voiceover audio track
    - Outputs 1080p MP4 H.264
    """
    try:
        from moviepy.editor import (
            VideoFileClip, AudioFileClip,
            concatenate_videoclips, ColorClip,
        )

        audio = AudioFileClip(audio_path)
        dur = audio.duration
        print(f"  Audio duration: {dur:.1f}s")

        if not clip_paths:
            # Black screen with audio
            black = ColorClip(size=(1920, 1080), color=[5, 8, 20], duration=dur)
            final = black.set_audio(audio)
            final.write_videofile(
                out_path, fps=24, codec="libx264",
                audio_codec="aac", audio_bitrate="192k",
                bitrate="3000k", logger=None,
            )
            audio.close()
            return True

        # Load clips
        clips = []
        for cp in clip_paths:
            try:
                vc = VideoFileClip(cp)
                # Resize maintaining aspect ratio, pad to 1920x1080
                vc_resized = vc.resize(height=1080)
                if vc_resized.w < 1920:
                    vc_resized = vc.resize(width=1920)
                vc_cropped = vc_resized.crop(
                    x_center=vc_resized.w / 2,
                    y_center=vc_resized.h / 2,
                    width=1920, height=1080
                )
                clips.append(vc_cropped)
            except Exception as e:
                print(f"  Clip error {cp}: {e}")

        if not clips:
            print("  No valid clips — using black screen")
            black = ColorClip(size=(1920, 1080), color=[5, 8, 20], duration=dur)
            final = black.set_audio(audio)
            final.write_videofile(
                out_path, fps=24, codec="libx264",
                audio_codec="aac", audio_bitrate="192k",
                logger=None,
            )
            audio.close()
            return True

        # Loop clips to match audio duration
        assembled, total_dur = [], 0.0
        while total_dur < dur:
            for clip in clips:
                remaining = dur - total_dur
                if clip.duration <= remaining:
                    assembled.append(clip)
                    total_dur += clip.duration
                else:
                    assembled.append(clip.subclip(0, remaining))
                    total_dur = dur
                    break
            if total_dur >= dur:
                break

        video = concatenate_videoclips(assembled, method="compose")
        video = video.subclip(0, min(dur, video.duration))
        video = video.set_audio(audio)

        video.write_videofile(
            out_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate="4000k",
            threads=2,
            logger=None,
        )

        audio.close()
        for c in clips:
            try: c.close()
            except: pass

        size = os.path.getsize(out_path) // (1024 * 1024)
        print(f"  Video: {size}MB ✅")
        return True

    except Exception as e:
        print(f"  Assembly error: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── YOUTUBE UPLOAD ────────────────────────────────────────────────
def youtube_upload(video_path, thumb_path, title, desc, tags, category="27"):
    """Upload video to YouTube with thumbnail. Returns video ID or None."""
    if not all([YT_CLIENT_ID, YT_CLIENT_SEC, YT_REFRESH]):
        print("  ⚠ YouTube credentials missing — skipping upload")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials(
            token=None,
            refresh_token=YT_REFRESH,
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SEC,
            token_uri="https://oauth2.googleapis.com/token",
        )

        # Force token refresh
        creds.refresh(Request())

        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

        body = {
            "snippet": {
                "title": title[:100],
                "description": desc[:4900],
                "tags": [t[:30] for t in tags[:15]],
                "categoryId": category,
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
            chunksize=5 * 1024 * 1024,  # 5MB chunks
        )

        req = yt.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        retry = 0
        while response is None:
            try:
                status, response = req.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    print(f"  Upload: {pct}%")
            except Exception as chunk_err:
                retry += 1
                if retry > 5:
                    raise chunk_err
                print(f"  Chunk error (retry {retry}): {chunk_err}")
                time.sleep(5 * retry)

        vid_id = response["id"]
        url = f"https://youtu.be/{vid_id}"
        print(f"  YouTube: {url} ✅")

        # Set thumbnail
        if thumb_path and os.path.exists(thumb_path):
            try:
                yt.thumbnails().set(
                    videoId=vid_id,
                    media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg"),
                ).execute()
                print("  Thumbnail set ✅")
            except Exception as te:
                print(f"  Thumbnail error: {te}")

        return vid_id

    except Exception as e:
        print(f"  YouTube upload error: {e}")
        import traceback
        traceback.print_exc()
        return None


# ── LOAD / SAVE TOPICS ────────────────────────────────────────────
def load_topics():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_topics(topics):
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)


# ── MAIN ─────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  VIRALAB STUDIO — VIDEO PIPELINE v2")
    print(f"  {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}")
    print("=" * 60)

    print("\n[CREDENTIALS]")
    print(f"  Pexels:   {'OK' if PEXELS_KEY else 'MISSING — no video clips'}")
    print(f"  YouTube:  {'OK' if YT_REFRESH else 'MISSING — no upload'}")
    print(f"  Claude:   {'OK (better scripts)' if CLAUDE_KEY else 'Not set (using templates)'}")

    # Load topics
    if not os.path.exists(TOPICS_FILE):
        print(f"\nERROR: {TOPICS_FILE} not found")
        sys.exit(1)

    topics = load_topics()
    pending = [t for t in topics if t.get("status") == "pending"]

    if not pending:
        print("\nNo pending topics. Edit topics.json and set status to 'pending'.")
        sys.exit(0)

    topic_obj = pending[0]
    topic    = topic_obj["topic"].strip()
    aud      = topic_obj.get("audience", "kids")
    lang     = topic_obj.get("language", "hi-IN")
    n_eps    = min(int(topic_obj.get("episodes", 3)), 10)
    voice    = topic_obj.get("voice") or VOICE_MAP.get(lang, "hi-IN-SwaraNeural")
    cfg      = AUDIENCE.get(aud, AUDIENCE["kids"])

    print(f"\n[TOPIC] {topic}")
    print(f"  Audience: {aud} | Language: {lang} | Episodes: {n_eps}")
    print(f"  Voice: {voice}")

    titles  = plan_episodes(topic, aud, n_eps)
    results = []

    for ep_idx, ep_title in enumerate(titles):
        ep_num = ep_idx + 1
        print(f"\n{'─'*60}")
        print(f"  EPISODE {ep_num}/{n_eps}: {ep_title}")
        print(f"{'─'*60}")

        ep_dir = OUT_DIR / f"ep_{ep_num:02d}"
        ep_dir.mkdir(exist_ok=True)

        # 1 — Script
        print("[1/6] Generating script...")
        script = generate_script(ep_title, topic, aud, lang, ep_num, n_eps)
        (ep_dir / "script.txt").write_text(script, encoding="utf-8")
        print(f"  Script: {len(script.split())} words")

        # 2 — Pexels videos
        print("[2/6] Fetching video clips from Pexels...")
        import random
        pexels_query = random.choice(cfg["pexels"]) + " " + topic.split()[0]
        clips_meta = fetch_pexels(pexels_query, cfg["clips"])
        clip_paths = []
        for j, cm in enumerate(clips_meta):
            cp = str(ep_dir / f"clip_{j:02d}.mp4")
            print(f"  Downloading clip {j+1}/{len(clips_meta)} ({cm['w']}x{cm['h']})...")
            if download_clip(cm["url"], cp):
                clip_paths.append(cp)
            time.sleep(0.2)
        print(f"  Downloaded: {len(clip_paths)}/{len(clips_meta)} clips")

        # 3 — Voiceover
        print("[3/6] Generating voiceover (Edge TTS)...")
        audio_path = str(ep_dir / "voice.mp3")
        if not generate_voice(script, voice, audio_path):
            print("  ERROR: Voiceover failed — skipping episode")
            continue

        # 4 — Assemble video
        print("[4/6] Assembling video...")
        video_path = str(ep_dir / "final.mp4")
        if not assemble_video(clip_paths, audio_path, video_path):
            print("  ERROR: Assembly failed — skipping episode")
            continue

        # 5 — Thumbnail
        print("[5/6] Creating professional thumbnail...")
        thumb_path = str(ep_dir / "thumbnail.jpg")
        create_thumbnail(ep_title, topic, ep_num, aud, thumb_path)

        # 6 — YouTube upload
        print("[6/6] Uploading to YouTube...")
        description = (
            f"{ep_title}\n\n"
            f"Episode {ep_num} of {n_eps} — {topic}\n\n"
            f"{script[:400]}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Subscribe for more free educational videos!\n"
            f"New video every 2 days\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"#{aud} #education #learning #{topic.replace(' ','').lower()[:20]}"
        )
        tags = [topic, aud, "education", "learning",
                f"episode{ep_num}", ep_title[:30], "viralab", lang[:5]]

        vid_id = youtube_upload(
            video_path, thumb_path,
            ep_title, description, tags, cfg["category"]
        )

        result = {
            "ep": ep_num,
            "title": ep_title,
            "video_id": vid_id,
            "url": f"https://youtu.be/{vid_id}" if vid_id else None,
            "status": "published" if vid_id else "assembled",
        }
        results.append(result)

        # Save progress after each episode
        for t in topics:
            if t.get("topic") == topic_obj.get("topic"):
                t["results"] = results
                t["last_updated"] = datetime.utcnow().isoformat()
        save_topics(topics)

        # Cleanup clips to save disk space
        for cp in clip_paths:
            try: os.remove(cp)
            except: pass
        try: os.remove(audio_path)
        except: pass

        print(f"  Episode {ep_num} complete! {'Published to YouTube ✅' if vid_id else 'Assembled only ⚠'}")
        time.sleep(2)

    # Mark topic as done
    for t in topics:
        if t.get("topic") == topic_obj.get("topic"):
            t["status"]    = "done"
            t["completed"] = datetime.utcnow().isoformat()
            t["results"]   = results
    save_topics(topics)

    # Summary
    published = [r for r in results if r.get("video_id")]
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Episodes processed : {len(results)}")
    print(f"  Published YouTube  : {len(published)}")
    for r in published:
        print(f"    EP{r['ep']:02d}: {r['url']}")
    print("="*60)


if __name__ == "__main__":
    main()
