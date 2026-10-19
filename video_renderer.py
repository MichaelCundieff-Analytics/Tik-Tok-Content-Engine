"""
Video rendering module — assembles TikTok-ready vertical MP4s.

MVP approach: dark background + animated text overlays + voiceover + subtitles.
Uses MoviePy for composition and Pillow for text rendering.
"""

import json
import textwrap
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip, ImageClip, VideoFileClip,
    CompositeVideoClip, concatenate_videoclips
)
from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_BG_COLOR,
    FONT_PATH, FONT_SIZE, SUBTITLE_FONT_SIZE,
    OUTPUT_DIR, ASSETS_DIR
)
from modules.logger import get_logger

log = get_logger("video_renderer")

# Fallback font if custom font not found
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Load font with fallback."""
    for path in [FONT_PATH, FALLBACK_FONT]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _create_text_frame(
    text: str,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    font_size: int = FONT_SIZE,
    text_color: str = "#FFFFFF",
    bg_color: str = None,
    y_position: float = 0.3,  # fraction from top
    max_chars_per_line: int = 25,
) -> np.ndarray:
    """Create a single frame with centered text on transparent/colored background."""
    bg = _hex_to_rgb(bg_color) if bg_color else _hex_to_rgb(VIDEO_BG_COLOR)
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)

    # Wrap text
    lines = textwrap.wrap(text, width=max_chars_per_line)

    # Calculate total text height
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_height = sum(line_heights) + (len(lines) - 1) * 20  # 20px spacing
    start_y = int(height * y_position) - total_height // 2

    # Draw each line centered
    for i, line in enumerate(lines):
        x = (width - line_widths[i]) // 2
        y = start_y + sum(line_heights[:i]) + i * 20

        # Draw text shadow for readability
        shadow_offset = 3
        draw.text((x + shadow_offset, y + shadow_offset), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=_hex_to_rgb(text_color))

    return np.array(img)


def _create_subtitle_clips(
    script: str,
    duration: float,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> list:
    """
    Create timed subtitle clips from the script.
    Splits script into chunks and distributes them across the duration.
    """
    # Split into sentences/phrases
    import re
    sentences = re.split(r'[.!?]+', script)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    time_per_sentence = duration / len(sentences)
    clips = []

    for i, sentence in enumerate(sentences):
        start = i * time_per_sentence
        end = min((i + 1) * time_per_sentence, duration)

        frame = _create_text_frame(
            text=sentence,
            width=width,
            height=height,
            font_size=SUBTITLE_FONT_SIZE,
            text_color="#FFDD00",  # yellow subtitles
            bg_color=None,
            y_position=0.75,  # lower third
            max_chars_per_line=30,
        )

        clip = (
            ImageClip(frame)
            .with_duration(end - start)
            .with_start(start)
            .with_position(("center", "center"))
        )
        clips.append(clip)

    return clips


def render_video(
    topic_id: str,
    script: str,
    hook: str,
    on_screen_text: list[str],
    voiceover_path: Path,
    cta: str = "Follow for more",
    bg_video_path: Path | None = None,
) -> Path:
    """
    Render a complete TikTok video.

    Args:
        topic_id: Unique identifier for naming
        script: Full voiceover script (used for subtitle timing)
        hook: Opening hook text
        on_screen_text: List of text overlay lines
        voiceover_path: Path to voiceover MP3
        cta: Call-to-action text
        bg_video_path: Optional background video (loops if shorter)

    Returns:
        Path to rendered MP4
    """
    output_path = OUTPUT_DIR / "videos" / f"{topic_id}.mp4"

    # Get voiceover duration
    audio = AudioFileClip(str(voiceover_path))
    total_duration = audio.duration

    # Add 1s padding at end
    total_duration += 1.0

    log.info(f"Rendering video: {topic_id} ({total_duration:.1f}s)")

    # ── Base layer: background ──────────────────────────────────
    if bg_video_path and bg_video_path.exists():
        bg = VideoFileClip(str(bg_video_path)).resized((VIDEO_WIDTH, VIDEO_HEIGHT))
        if bg.duration < total_duration:
            # Loop the background
            loops = int(total_duration / bg.duration) + 1
            bg = concatenate_videoclips([bg] * loops)
        bg = bg.subclipped(0, total_duration)
    else:
        # Solid color background
        bg_frame = _create_text_frame(
            "", VIDEO_WIDTH, VIDEO_HEIGHT,
            bg_color=VIDEO_BG_COLOR
        )
        bg = ImageClip(bg_frame).with_duration(total_duration)

    # ── Hook text (first 3 seconds) ─────────────────────────────
    layers = [bg]

    if hook:
        hook_frame = _create_text_frame(
            hook, VIDEO_WIDTH, VIDEO_HEIGHT,
            font_size=int(FONT_SIZE * 1.2),
            text_color="#FFFFFF",
            y_position=0.35,
            max_chars_per_line=20,
        )
        hook_clip = (
            ImageClip(hook_frame)
            .with_duration(min(3.0, total_duration))
            .with_start(0)
            .with_position(("center", "center"))
        )
        layers.append(hook_clip)

    # ── On-screen text overlays (distributed across middle) ─────
    if on_screen_text:
        text_start = 3.0 if hook else 0.5
        text_duration = total_duration - text_start - 3.0  # leave room for CTA
        time_per_text = max(text_duration / len(on_screen_text), 1.5)

        for i, text in enumerate(on_screen_text):
            start = text_start + i * time_per_text
            if start >= total_duration - 2:
                break

            text_frame = _create_text_frame(
                text, VIDEO_WIDTH, VIDEO_HEIGHT,
                font_size=FONT_SIZE,
                text_color="#FFFFFF",
                y_position=0.4,
                max_chars_per_line=22,
            )
            text_clip = (
                ImageClip(text_frame)
                .with_duration(min(time_per_text, total_duration - start))
                .with_start(start)
                .with_position(("center", "center"))
            )
            layers.append(text_clip)

    # ── CTA (last 2.5 seconds) ──────────────────────────────────
    if cta:
        cta_frame = _create_text_frame(
            cta, VIDEO_WIDTH, VIDEO_HEIGHT,
            font_size=int(FONT_SIZE * 0.9),
            text_color="#00FF88",
            y_position=0.5,
            max_chars_per_line=25,
        )
        cta_start = max(total_duration - 2.5, 0)
        cta_clip = (
            ImageClip(cta_frame)
            .with_duration(total_duration - cta_start)
            .with_start(cta_start)
            .with_position(("center", "center"))
        )
        layers.append(cta_clip)

    # ── Subtitle overlays ───────────────────────────────────────
    subtitle_clips = _create_subtitle_clips(
        script, audio.duration, VIDEO_WIDTH, VIDEO_HEIGHT
    )
    layers.extend(subtitle_clips)

    # ── Composite and write ─────────────────────────────────────
    final = CompositeVideoClip(layers, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final = final.with_duration(total_duration)
    final = final.with_audio(audio)

    final.write_videofile(
        str(output_path),
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None,  # suppress moviepy progress bars
    )

    # Clean up
    audio.close()
    final.close()

    log.info(f"Video rendered: {output_path} ({total_duration:.1f}s)")
    return output_path
