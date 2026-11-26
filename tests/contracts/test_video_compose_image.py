"""Regression tests for FFmpeg still-image composition."""

import json
import shutil
import subprocess

import pytest

from tools.video.video_compose import VideoCompose


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and ffprobe are required",
)
def test_compose_still_image_to_mp4(tmp_path):
    """A still image should produce a valid MP4 through VideoCompose."""

    image_path = tmp_path / "fixture.png"
    output_path = tmp_path / "image_composition.mp4"

    # Generate a tiny fixture without downloading anything.
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=1",
            "-frames:v",
            "1",
            str(image_path),
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
            "output_path": str(output_path),
            "preset": "ultrafast",
            "crf": 28,
        }
    )

    assert result.success, result.error
    assert output_path.exists()
    assert output_path.stat().st_size > 0

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,width,height",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    metadata = json.loads(probe.stdout)
    video_stream = next(
        stream
        for stream in metadata["streams"]
        if stream.get("codec_name") == "h264"
    )

    assert video_stream["width"] == 320
    assert video_stream["height"] == 180
    assert float(metadata["format"]["duration"]) >= 0.9
