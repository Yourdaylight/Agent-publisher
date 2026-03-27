"""Video exporter — Playwright screen-recording of reveal.js + ffmpeg merge."""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_ffmpeg() -> str:
    """Return the path to a usable ffmpeg binary.

    Preference order:
      1. System ffmpeg (supports libx264 → mp4)
      2. Playwright-bundled ffmpeg (webm only, limited codecs)
    """
    system = shutil.which("ffmpeg")
    if system:
        return system

    import glob
    patterns = [
        "/root/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux",
        "/home/*/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux",
        "/usr/local/share/ms-playwright/ffmpeg-*/ffmpeg-linux",
    ]
    for pattern in patterns:
        found = glob.glob(pattern)
        if found:
            logger.warning(
                "System ffmpeg not found; using Playwright-bundled ffmpeg (%s). "
                "Output will be webm. Install system ffmpeg for mp4 support.",
                found[0],
            )
            return found[0]

    raise RuntimeError(
        "ffmpeg not found. Install it with: apt-get install ffmpeg"
    )


class VideoExporter:
    """Record a reveal.js auto-play presentation and produce a video file."""

    async def export(
        self,
        html_path: str,
        output_mp4: str,
        tts_audio_path: str | None = None,
    ) -> str:
        """Run headless Chromium to record the slideshow, then merge audio.

        Returns the final video path (.mp4 if system ffmpeg available, .webm otherwise).
        """
        from playwright.async_api import async_playwright

        ffmpeg_bin = _find_ffmpeg()
        # Playwright-bundled ffmpeg only supports webm; adjust output path if needed
        output_path = output_mp4
        if "ms-playwright" in ffmpeg_bin and output_mp4.endswith(".mp4"):
            output_path = output_mp4[:-4] + ".webm"
            logger.info("Using Playwright ffmpeg — output will be .webm: %s", output_path)

        temp_dir = tempfile.mkdtemp(prefix="slideshow_video_")

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox"],  # required when running as root in containers
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    record_video_dir=temp_dir,
                    record_video_size={"width": 1280, "height": 720},
                )
                page = await context.new_page()

                # Navigate to the reveal.js HTML (auto-play mode)
                # Resolve to absolute path for valid file:// URL
                abs_html_path = str(Path(html_path).resolve())
                await page.goto(f"file://{abs_html_path}")

                # Wait for reveal.js to be ready
                await page.wait_for_function(
                    "window.__REVEAL_READY__ === true", timeout=30000
                )

                logger.info("Reveal.js ready, waiting for auto-play to finish …")

                # Wait for the last slide to be reached
                await page.wait_for_function(
                    "() => typeof Reveal !== 'undefined' && Reveal.isLastSlide() && Reveal.getProgress() === 1",
                    timeout=300_000,  # 5 min
                )

                # Wait for the last slide's timing
                last_timing = await page.evaluate(
                    "(Reveal.getCurrentSlide().dataset.timing || '5')"
                )
                await page.wait_for_timeout(int(float(last_timing) * 1000))

                # Small extra buffer for final animations
                await page.wait_for_timeout(1000)

                await page.close()
                await context.close()
                await browser.close()

            # Find the recorded video
            raw_videos = list(Path(temp_dir).glob("*.webm"))
            if not raw_videos:
                raise RuntimeError("Playwright did not produce a video file")

            raw_video = str(raw_videos[0])
            logger.info("Raw video recorded: %s", raw_video)

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            if tts_audio_path and Path(tts_audio_path).exists():
                await self._ffmpeg_merge(raw_video, tts_audio_path, output_path, ffmpeg_bin)
            else:
                await self._ffmpeg_convert(raw_video, output_path, ffmpeg_bin)

            return output_path

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------

    @staticmethod
    async def _ffmpeg_merge(video: str, audio: str, output: str, ffmpeg_bin: str) -> None:
        """Merge video + audio → output file."""
        is_webm = output.endswith(".webm")
        vcodec = "copy" if is_webm else "libx264"
        acodec = "libvorbis" if is_webm else "aac"
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin, "-y",
            "-i", video, "-i", audio,
            "-c:v", vcodec, "-c:a", acodec,
            "-shortest", output,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("ffmpeg merge failed: %s", stderr.decode(errors="replace"))
            raise RuntimeError(f"ffmpeg merge failed (rc={proc.returncode})")

    @staticmethod
    async def _ffmpeg_convert(video: str, output: str, ffmpeg_bin: str) -> None:
        """Convert webm → output format."""
        is_webm = output.endswith(".webm")
        if is_webm:
            args = [ffmpeg_bin, "-y", "-i", video, "-c", "copy", output]
        else:
            args = [ffmpeg_bin, "-y", "-i", video, "-c:v", "libx264", "-c:a", "aac", output]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("ffmpeg convert failed: %s", stderr.decode(errors="replace"))
            raise RuntimeError(f"ffmpeg convert failed (rc={proc.returncode})")
