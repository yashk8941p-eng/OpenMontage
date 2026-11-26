"""Tests for crossfade and fade transitions in video composition."""

import json
import shutil
import subprocess

import pytest

from tools.video.video_compose import VideoCompose


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and ffprobe are required",
)
@pytest.mark.parametrize("transition", ["crossfade", "fade"])
def test_compose_transitions(tmp_path, transition):
    image_path = tmp_path / "fixture.png"
    video_path = tmp_path / "fixture.mp4"
    output_path = tmp_path / f"{transition}_output.mp4"

    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi",
            "-i", "color=c=blue:s=320x240:d=1",
            "-frames:v", "1",
            str(image_path),
        ],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi",
            "-i", "color=c=red:s=320x240:d=2:r=30",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-g", "30",
            "-an",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )

    result = VideoCompose().execute(
        {
            "operation": "compose",
            "edit_decisions": {
                "cuts": [
                    {
                        "source": str(image_path),
                        "in_seconds": 0,
                        "out_seconds": 1,
                    },
                    {
                        "source": str(video_path),
                        "in_seconds": 0,
                        "out_seconds": 2,
                    },
                ],
                "metadata": {
                    "compose_target": {
                        "width": 320,
                        "height": 180,
                        "fit": "cover",
                    }
                },
            },
            "output_path": str(output_path),
            "transition": transition,
            "transition_duration": 0.5,
            "preset": "ultrafast",
            "crf": 28,
        }
    )

    assert result.success, result.error
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
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
    assert 2.3 <= duration <= 2.8
