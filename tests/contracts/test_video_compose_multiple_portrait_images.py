"""Regression: multiple still images rendered in portrait 9:16."""

import json
import shutil
import subprocess

import pytest

from tools.video.video_compose import VideoCompose


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and ffprobe are required",
)
def test_multiple_images_portrait_composition(tmp_path):
    colors = ["red", "green", "blue"]
    images = []

    # Generate three different color images.
    for index, color in enumerate(colors):
        image = tmp_path / f"image_{index}.png"
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error",
                "-f", "lavfi",
                "-i", f"color=c={color}:s=320x240",
                "-frames:v", "1",
                str(image),
            ],
            check=True,
            capture_output=True,
        )
        images.append(image)

    output_path = tmp_path / "portrait_multiple_images.mp4"

    cuts = [
        {
            "source": str(image),
            "in_seconds": 0,
            "out_seconds": 1,
        }
        for image in images
    ]

    result = VideoCompose().execute(
        {
            "operation": "compose",
            "edit_decisions": {
                "cuts": cuts,
                "metadata": {
                    "compose_target": {
                        "width": 360,
                        "height": 640,
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

    video = next(
        s for s in metadata["streams"]
        if s.get("codec_name") == "h264"
    )
    audio = next(
        s for s in metadata["streams"]
        if s.get("codec_name") == "aac"
    )

    duration = float(metadata["format"]["duration"])

    assert video["width"] == 360
    assert video["height"] == 640
    assert audio["codec_name"] == "aac"
    assert 2.8 <= duration <= 3.2

    # Verify that each color appears at its expected point in the timeline.
    expected_colors = [
        (0.5, "red"),
        (1.5, "green"),
        (2.5, "blue"),
    ]

    for timestamp, expected in expected_colors:
        frame = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-ss", str(timestamp),
                "-i", str(output_path),
                "-frames:v", "1",
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "pipe:1",
            ],
            check=True,
            capture_output=True,
        )

        pixel = frame.stdout[:3]
        r, g, b = pixel

        if expected == "red":
            assert r > g * 1.5 and r > b * 1.5, (r, g, b)
        elif expected == "green":
            assert g > r * 1.3 and g > b * 1.3, (r, g, b)
        elif expected == "blue":
            assert b > r * 1.5 and b > g * 1.5, (r, g, b)
