"""Regression test: still image + external soundtrack + burned-in subtitles."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and ffprobe are required",
)
def test_compose_image_with_audio_and_subtitles(tmp_path):
    # Check whether FFmpeg has subtitle rendering support.
    filters = subprocess.run(
        ["ffmpeg", "-filters"],
        capture_output=True,
        text=True,
    )

    if "subtitles" not in filters.stdout:
        pytest.skip("FFmpeg subtitles/libass filter is unavailable")

    image_path = tmp_path / "fixture.png"
    audio_path = tmp_path / "soundtrack.wav"
    subtitle_path = tmp_path / "captions.srt"
    output_path = tmp_path / "image_audio_subtitles.mp4"

    # Create a 2-second still image.
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi",
            "-i", "color=c=blue:s=320x240:d=2",
            "-frames:v", "1",
            str(image_path),
        ],
        check=True,
        capture_output=True,
    )

    # Create a 2-second external audio track.
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=2",
            "-ar", "48000",
            "-ac", "2",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
    )

    # Create subtitle fixture.
    subtitle_path.write_text(
        "1\n"
        "00:00:00,200 --> 00:00:01,800\n"
        "OpenMontage subtitle test\n",
        encoding="utf-8",
    )

    result = VideoCompose().execute(
        {
            "operation": "compose",
            "edit_decisions": {
                "cuts": [
                    {
                        "source": str(image_path),
                        "in_seconds": 0,
                        "out_seconds": 2,
                    }
                ],
                "metadata": {
                    "compose_target": {
                        "width": 320,
                        "height": 180,
                        "fit": "cover",
                    }
                },
            },
            "audio_path": str(audio_path),
            "subtitle_path": str(subtitle_path),
            "output_path": str(output_path),
            "preset": "ultrafast",
            "crf": 28,
        }
    )

    assert result.success, result.error
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert result.data["has_subtitles"] is True
    assert result.data["has_mixed_audio"] is True

    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=codec_name,width,height",
            "-show_entries", "format=duration",
            "-of", "json",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    metadata = json.loads(probe.stdout)

    video_stream = next(
        stream for stream in metadata["streams"]
        if stream.get("codec_name") == "h264"
    )

    audio_stream = next(
        stream for stream in metadata["streams"]
        if stream.get("codec_name") == "aac"
    )

    duration = float(metadata["format"]["duration"])

    assert video_stream["width"] == 320
    assert video_stream["height"] == 180
    assert audio_stream["codec_name"] == "aac"
    assert 1.8 <= duration <= 2.2
