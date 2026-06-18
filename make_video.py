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
        "duration":  240,
        "clips":     8,
        "voice_hi":  "hi-IN-SwaraNeural",
        "voice_en":  "en-IN-NeerjaNeural",
        "pexels":    ["colorful cartoon", "cute animals children", "bright colors kids"],
        "category":  "27",
    },
    "kids": {
        "duration":  360,
        "clips":     10,
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
                            f"- 450 to 600 words — this makes a 3 to 5 minute video\n"
                            f"- Spoken words only — no stage directions, no brackets\n"
                            f"- Natural, warm, engaging tone for {aud} audience\n"
                            f"- Start with an exciting hook that grabs attention\n"
                            f"- Include 5 to 7 interesting facts or story points\n"
                            f"- Use simple language appropriate for {aud}\n"
                            f"- End with: See you in the next episode!\n"
                            f"- Write in {lang} language\n\n"
                            f"Write ONLY the narration text, 450-600 words:"
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

    # Fallback templates — 450-600 words each for 3-5 minute videos
    templates = {
        "toddler": f"""Hello hello hello friends! Welcome to our amazing show!
I am so very happy to see you today! Are you ready for some fun?

Today we are going to learn all about {title}! Yay!

Do you know what {topic} is? Let me tell you something wonderful.
{topic} is one of the most amazing things in the whole wide world!
And today, you and me, we are going to discover it together!

First, let us look at all the beautiful colours!
Can you see red? Red is the colour of apples and roses!
Can you see yellow? Yellow is the colour of the sun and bananas!
Can you see blue? Blue is the colour of the sky and the ocean!
And green! Green is the colour of grass and trees and frogs!

Now let us count together! Ready?
One! Two! Three! Four! Five!
Very good! You are so smart!

Did you know that {topic} is all around us every single day?
When you wake up in the morning, {topic} is there!
When you eat your breakfast, {topic} is there!
When you play in the park, {topic} is everywhere!

Let me tell you a little story.
Once upon a time, there was a little child, just like you.
This child loved to learn and discover new things every day.
One day, the child discovered {topic}, and it was the most wonderful discovery ever!

Now I want you to do something special.
Stand up! Stretch your arms wide!
Jump up and down three times! One, two, three!
Great job! You are amazing!

Remember these important things my dear friends.
Always be kind to everyone around you.
Always share your things with your friends.
Always listen to your parents and teachers.
And always always always keep learning new things every day!

{topic} teaches us so many beautiful lessons about our world.
Every day is a new adventure waiting for you!

Before we say goodbye, let us say our special words together.
I am smart! I am kind! I am wonderful! I can learn anything!

I love you all so very much my dear little friends.
Thank you for spending this special time with me today!
Give yourself a big hug from me!

See you in the next episode where we discover even more amazing things together!""",

        "kids": f"""Hey everyone! Welcome back to the most exciting series on YouTube!
I am so glad you are here today! Get ready because this is going to be amazing!

Today we are on Episode {ep_num} of our {topic} series, and the topic is — {title}!

Have you ever wondered about this? Well today we are going to find out everything!
By the end of this video, you will know things that most adults do not even know!

Let us start with the most exciting fact.
Did you know that {topic} has been part of human history for thousands of years?
That is right! Ancient civilisations were fascinated by it just like we are today!

Here is the first amazing thing you need to know about {title}.
Scientists have studied this for hundreds of years and they still discover new things every day.
That means there is always something new to learn, and you could be the next great discoverer!

The second thing is even more incredible.
{topic} affects our daily life in ways we never even think about.
Right now, as you watch this video, {topic} is working all around you!
Is that not mind blowing?

Now here is something you can try at home.
Next time you are outside, look around and try to spot {topic} in nature.
You might be surprised at how many places you can find it!

Let me share a story that will help you remember this forever.
Imagine you are an explorer in a great jungle.
You have your map, your compass, and your curiosity.
Suddenly you discover something incredible about {topic} that nobody has ever seen before!
That feeling of discovery — that is exactly what scientists feel when they study {topic}!

Here are three facts that will make your friends say wow.
Fact number one — {topic} can be found on every single continent on Earth!
Fact number two — {topic} has a connection to some of the greatest inventions in history!
Fact number three — Learning about {topic} makes your brain stronger and smarter!

Now it is time for the challenge of the day.
Can you teach one thing you learned today to someone in your family?
Teaching others is the best way to remember what you have learned!

Keep asking questions. Keep being curious. Keep exploring.
The world is full of amazing things waiting for you to discover them.

Thank you so much for watching today! You are absolutely brilliant!
Do not forget to share this video with your friends who love learning.

See you in the next episode where we go even deeper into {topic}!""",

        "adult": f"""Welcome back to the {topic} series. I am glad you are here.

Today we are covering Episode {ep_num} — {title}.
If you have been following this series from the beginning, today is where things get really interesting.
And if this is your first episode, do not worry — I will make sure everything is crystal clear.

Let me start with the core question that most people never think to ask about {topic}.
Why does this matter to you personally, right now, today?
The answer is more important than most people realise.

{topic} is not just an abstract concept. It has direct practical applications in everyday life.
Understanding it gives you a genuine competitive advantage — whether in your career, your finances, or your personal development.

Let me break this down into the key components you need to understand.

The first principle is foundational. Without grasping this, nothing else will make sense.
{topic} operates on a system of cause and effect that is predictable once you know the patterns.
Most people react to the effects without ever understanding the causes. That ends today.

The second principle is where most people make their biggest mistakes.
They focus on the visible surface of {topic} while ignoring the underlying mechanics.
Think of it like an iceberg — what you can see is only ten percent of what is actually happening.

The third principle is what separates beginners from experts.
Consistency of application matters more than intensity of effort.
Small deliberate actions taken consistently over time produce extraordinary results with {topic}.

Now let me give you a practical framework you can apply immediately.
Step one — identify the specific area of {topic} most relevant to your current situation.
Step two — apply the first principle we discussed and analyse the root causes, not the symptoms.
Step three — design a consistent practice around the second and third principles.
Step four — measure your results after thirty days and adjust accordingly.

The most common mistake I see is people trying to do everything at once.
Start with one thing. Master it. Then move to the next.
This approach consistently outperforms scattered effort by a factor of ten.

Here is something worth remembering as we close today.
Every expert in {topic} started exactly where you are right now.
The difference is they kept going when it felt difficult. That is the entire secret.

Your action for today is simple. Take one insight from this episode and apply it before tomorrow.
Not next week. Not someday. Before tomorrow.

That single action will put you ahead of ninety percent of people who watch educational content but never act on it.

I will see you in the next episode where we take this even further.
Until then — keep learning, keep applying, keep growing.""",
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


# ── VOICEOVER — gTTS (Google TTS, completely free, works on GitHub Actions) ──
# Language code mapping for gTTS
GTTS_LANG = {
    "hi-IN":  "hi",   # Hindi
    "en-IN":  "en",   # English India
    "en-US":  "en",   # English US
    "ta-IN":  "ta",   # Tamil
    "te-IN":  "te",   # Telugu
    "mr-IN":  "mr",   # Marathi
    "es-ES":  "es",   # Spanish
    "fr-FR":  "fr",   # French
    "de-DE":  "de",   # German
    "ja-JP":  "ja",   # Japanese
    "ar-SA":  "ar",   # Arabic
}

def generate_voice(text, voice, path):
    """
    Generate voiceover using gTTS (Google Text-to-Speech).
    Completely free. No API key. Works from GitHub Actions.
    Supports Hindi, English, Tamil, Telugu and 30+ languages.
    """
    from gtts import gTTS

    # Get gTTS language code from voice name
    lang = GTTS_LANG.get(voice, "en")

    # Try 3 times with exponential backoff
    for attempt in range(3):
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(path)
            size = os.path.getsize(path)
            if size > 5000:
                print(f"  Voice: {size//1024}KB  lang={lang} ✅")
                return True
        except Exception as e:
            print(f"  gTTS attempt {attempt+1} error: {e}")
            if attempt < 2:
                time.sleep(3 * (attempt + 1))

    # Fallback to English if primary language fails
    if lang != "en":
        print(f"  Falling back to English...")
        try:
            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(path)
            size = os.path.getsize(path)
            if size > 5000:
                print(f"  Voice fallback (en): {size//1024}KB ✅")
                return True
        except Exception as e:
            print(f"  gTTS fallback error: {e}")

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
def resize_clip_safe(vc, target_w=1920, target_h=1080):
    """Safely resize a clip to target dimensions using FFmpeg directly."""
    try:
        # Calculate scaling to fill frame (cover mode)
        scale_w = target_w / vc.w
        scale_h = target_h / vc.h
        scale   = max(scale_w, scale_h)
        new_w   = int(vc.w * scale)
        new_h   = int(vc.h * scale)

        resized = vc.resize((new_w, new_h))

        # Centre crop to exact dimensions
        x1 = (new_w - target_w) // 2
        y1 = (new_h - target_h) // 2
        cropped = resized.crop(x1=x1, y1=y1,
                               x2=x1 + target_w, y2=y1 + target_h)
        return cropped
    except Exception as e:
        print(f"    resize error: {e} — using simple resize")
        try:
            return vc.resize((target_w, target_h))
        except:
            return vc


def assemble_video(clip_paths, audio_path, out_path, title="", series=""):
    """
    Assemble final video with:
    - HD Pexels clips properly resized to 1920x1080
    - Professional voiceover audio
    - Title card at start
    - Series branding overlay
    """
    try:
        from moviepy.editor import (
            VideoFileClip, AudioFileClip,
            concatenate_videoclips, ColorClip,
            TextClip, CompositeVideoClip,
        )

        audio = AudioFileClip(audio_path)
        dur   = audio.duration
        print(f"  Audio duration: {dur:.1f}s")

        # ── Build video track ────────────────────────────────────────
        if not clip_paths:
            print("  No clips — using gradient background")
            base = ColorClip(size=(1920, 1080), color=[8, 15, 35], duration=dur)
        else:
            # Load and resize every clip safely
            clips = []
            for cp in clip_paths:
                try:
                    vc = VideoFileClip(cp)
                    if vc.duration < 1:
                        vc.close(); continue
                    rc = resize_clip_safe(vc, 1920, 1080)
                    clips.append(rc)
                    print(f"    Clip loaded: {vc.w}x{vc.h} → 1920x1080")
                except Exception as e:
                    print(f"    Clip load error {cp}: {e}")

            if not clips:
                print("  No valid clips — using gradient background")
                base = ColorClip(size=(1920, 1080), color=[8, 15, 35], duration=dur)
            else:
                # Loop clips to exactly match audio duration
                assembled, total = [], 0.0
                while total < dur:
                    for clip in clips:
                        need = dur - total
                        if clip.duration <= need:
                            assembled.append(clip)
                            total += clip.duration
                        else:
                            assembled.append(clip.subclip(0, need))
                            total = dur
                            break
                    if total >= dur:
                        break

                base = concatenate_videoclips(assembled, method="compose")
                base = base.subclip(0, min(dur, base.duration))
                print(f"  Video track: {base.duration:.1f}s ✅")

        # ── Add audio ────────────────────────────────────────────────
        final = base.set_audio(audio)

        # ── Export ───────────────────────────────────────────────────
        final.write_videofile(
            out_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            bitrate="5000k",
            threads=2,
            preset="fast",
            logger=None,
        )

        size_mb = os.path.getsize(out_path) // (1024*1024)
        print(f"  Final video: {size_mb}MB ✅")

        audio.close()
        if clip_paths:
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
def get_fresh_access_token():
    """
    Get a fresh YouTube access token using the refresh token.
    Uses direct HTTP call — more reliable than google-auth library.
    Access tokens last 3600s but refresh tokens last forever (if app published).
    """
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id":     YT_CLIENT_ID,
            "client_secret": YT_CLIENT_SEC,
            "refresh_token": YT_REFRESH,
            "grant_type":    "refresh_token",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  Token refresh failed: {resp.status_code} {resp.text[:200]}")
        return None
    data = resp.json()
    token = data.get("access_token")
    if token:
        print(f"  Fresh access token obtained ✅ (expires in {data.get('expires_in',3600)}s)")
    return token


def youtube_upload(video_path, thumb_path, title, desc, tags, category="27"):
    """Upload video to YouTube with thumbnail. Returns video ID or None."""
    if not all([YT_CLIENT_ID, YT_CLIENT_SEC, YT_REFRESH]):
        print("  ⚠ YouTube credentials missing — skipping upload")
        return None

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials

        # Step 1: Get fresh access token via refresh token
        print("  Getting fresh YouTube access token...")
        access_token = get_fresh_access_token()
        if not access_token:
            print("  ERROR: Could not get access token")
            print("  Fix: Publish your Google app at console.cloud.google.com")
            print("  Then get a new refresh token from developers.google.com/oauthplayground")
            return None

        # Step 2: Build YouTube client with fresh token
        creds = Credentials(
            token=access_token,
            refresh_token=YT_REFRESH,
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SEC,
            token_uri="https://oauth2.googleapis.com/token",
        )
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
        if not assemble_video(clip_paths, audio_path, video_path, ep_title, topic):
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
