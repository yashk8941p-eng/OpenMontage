"""Test chained transitions across three image clips."""

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
def test_three_clip_transitions(tmp_path, transition):
    images = []

    for index, color in enumerate(["blue", "red", "green"]):
        path = tmp_path / f"clip_{index}.png"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi",
                "-i", f"color=c={color}:s=320x240",
                "-frames:v", "1",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        images.append(path)

    output = tmp_path / f"three_clip_{transition}.mp4"

    result = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": {
            "cuts": [
                {
                    "source": str(path),
                    "in_seconds": 0,
                    "out_seconds": 2,
                }
                for path in images
            ],
            "metadata": {
                "compose_target": {
                    "width": 320,
                    "height": 180,
                    "fit": "cover",
                }
            },
        },
        "output_path": str(output),
        "transition": transition,
        "transition_duration": 0.5,
        "preset": "ultrafast",
        "crf": 28,
    })

    assert result.success, result.error
    assert output.exists()
    assert output.stat().st_size > 0

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,width,height",
            "-show_entries", "format=duration",
            "-of", "json",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(probe.stdout)
    video = next(s for s in data["streams"] if s["codec_name"] == "h264")
    audio = next(s for s in data["streams"] if s["codec_name"] == "aac")
    duration = float(data["format"]["duration"])

    assert video["width"] == 320
    assert video["height"] == 180
    assert audio["codec_name"] == "aac"
    assert 4.7 <= duration <= 5.3
