"""TTS service — generate Chinese speech from slide speaker notes via edge-tts."""
from __future__ import annotations

import asyncio
import logging
import struct
import wave
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TTSService:
    """Generate narration audio + SRT subtitles from slide speaker notes."""

    async def generate(self, slides: list[dict], output_dir: str) -> dict[str, Any]:
        """Produce a concatenated audio file and SRT subtitle track.

        Returns ``{"audio_path", "srt_path", "duration_ms", "slide_durations"}``
        where ``slide_durations`` maps slide index → actual audio duration in seconds.
        """
        import edge_tts

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        audio_segments: list[str] = []
        subtitle_entries: list[dict] = []
        slide_durations: dict[int, float] = {}
        offset_ms = 0

        for i, slide in enumerate(slides):
            notes = slide.get("notes", "")
            default_duration = slide.get("duration", 5)

            if not notes:
                # Insert silence matching the slide's declared duration
                silence_path = str(out / f"silence_{i:03d}.wav")
                self._write_silence(silence_path, default_duration * 1000)
                audio_segments.append(silence_path)
                slide_durations[i] = default_duration
                offset_ms += default_duration * 1000
                continue

            segment_path = str(out / f"segment_{i:03d}.mp3")
            communicate = edge_tts.Communicate(notes, voice="zh-CN-XiaoxiaoNeural")
            await communicate.save(segment_path)

            seg_duration_ms = self._audio_duration_ms(segment_path)
            slide_durations[i] = seg_duration_ms / 1000.0
            audio_segments.append(segment_path)

            # Simple subtitle: one entry per slide
            subtitle_entries.append({
                "index": len(subtitle_entries) + 1,
                "start_ms": offset_ms,
                "end_ms": offset_ms + seg_duration_ms,
                "text": notes,
            })
            offset_ms += seg_duration_ms

        # Concatenate all audio segments via ffmpeg
        full_audio = str(out / "narration.mp3")
        await self._concat_audio(audio_segments, full_audio)
        srt_path = str(out / "subtitles.srt")
        self._write_srt(subtitle_entries, srt_path)

        return {
            "audio_path": full_audio,
            "srt_path": srt_path,
            "duration_ms": offset_ms,
            "slide_durations": slide_durations,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_silence(path: str, duration_ms: int) -> None:
        """Write a silent WAV file of the given duration."""
        sample_rate = 44100
        num_frames = int(sample_rate * duration_ms / 1000)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f"<{num_frames}h", *([0] * num_frames)))

    @staticmethod
    def _audio_duration_ms(path: str) -> int:
        """Get duration of an audio file in milliseconds using ffprobe."""
        import subprocess

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            return int(float(result.stdout.strip()) * 1000)
        except Exception:
            return 5000  # fallback: 5 seconds

    @staticmethod
    async def _concat_audio(segments: list[str], output: str) -> None:
        """Concatenate audio segments using ffmpeg."""
        import shutil
        import tempfile

        if not segments:
            return
        if len(segments) == 1:
            shutil.copy2(segments[0], output)
            return

        # Find ffmpeg binary
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for seg in segments:
                # Use absolute paths to avoid CWD issues
                f.write(f"file '{Path(seg).resolve()}'\n")
            list_path = f.name

        proc = await asyncio.create_subprocess_exec(
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", list_path, "-c", "copy", output,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        Path(list_path).unlink(missing_ok=True)

        if proc.returncode != 0:
            logger.error("Audio concat failed (rc=%d): %s", proc.returncode, stderr.decode(errors="replace")[-300:])
            raise RuntimeError(f"Audio concat failed (rc={proc.returncode})")

    @staticmethod
    def _write_srt(entries: list[dict], path: str) -> None:
        """Write SRT subtitle file."""
        lines: list[str] = []
        for entry in entries:
            idx = entry["index"]
            start = _ms_to_srt_time(entry["start_ms"])
            end = _ms_to_srt_time(entry["end_ms"])
            lines.append(f"{idx}")
            lines.append(f"{start} --> {end}")
            lines.append(entry["text"])
            lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")


def _ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT time format ``HH:MM:SS,mmm``."""
    hours = ms // 3_600_000
    ms %= 3_600_000
    minutes = ms // 60_000
    ms %= 60_000
    seconds = ms // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
