"""
Video text-removal pipeline.

extract_frames() and encode_video() are real, runnable implementations using
OpenCV + ffmpeg. detect_text_masks() and inpaint_frames() are stubbed —
that's where the actual ML models plug in. See the comments in each for
exactly what to install and call.
"""

import subprocess
from pathlib import Path
from typing import Callable

import cv2
import numpy as np


def extract_frames(video_path: str) -> tuple[list[np.ndarray], float]:
    """Read every frame of the video into memory as BGR numpy arrays.

    For longer videos you'll want to stream frames in batches instead of
    loading the whole thing into RAM — fine for short clips, not for a
    10-minute upload.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        raise ValueError("Could not read any frames from the uploaded file")

    return frames, fps


def detect_text_masks(
    frames: list[np.ndarray],
    on_progress: Callable[[float], None] | None = None,
) -> list[np.ndarray]:
    """Return one binary mask per frame marking where text was detected.

    --- Plug in here ---
    pip install paddleocr paddlepaddle-gpu   (or paddlepaddle for CPU)

        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=False, lang="en", det=True, rec=False)

        for i, frame in enumerate(frames):
            result = ocr.ocr(frame, rec=False)  # detection only, faster
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            for box in result[0] or []:
                pts = np.array(box, dtype=np.int32)
                cv2.fillPoly(mask, [pts], 255)
            # Dilate so the inpainting model covers text edges cleanly
            mask = cv2.dilate(mask, np.ones((9, 9), np.uint8))
            masks.append(mask)
            if on_progress:
                on_progress((i + 1) / len(frames) * 100)

    Optimization: if the text is static (a fixed watermark/caption position),
    run detection on every Nth frame and hold/interpolate the mask between
    samples instead of running OCR on every single frame.
    """
    masks = [_detect_text_regions_heuristic(f) for f in frames]
    if on_progress:
        on_progress(100)
    return masks


def _detect_text_regions_heuristic(frame: np.ndarray) -> np.ndarray:
    """Cheap, model-free stand-in for real OCR-based detection.

    Uses MSER (finds small, high-contrast connected regions — the shape
    profile of individual letters/glyphs) plus a bit of morphology to merge
    nearby glyphs into text-block regions. This is meaningfully worse than
    PaddleOCR/CRAFT — it will pick up some non-text high-contrast clutter and
    miss low-contrast or stylized text — but it's dependency-free and lets
    you see the pipeline actually do something before installing the real
    detection model.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mser = cv2.MSER_create()
    mser.setMinArea(30)
    mser.setMaxArea(3000)
    regions, _ = mser.detectRegions(gray)

    mask = np.zeros(gray.shape, dtype=np.uint8)
    for region in regions:
        x, y, w, h = cv2.boundingRect(region.reshape(-1, 1, 2))
        # Text glyphs are roughly this aspect ratio; filters out long thin
        # edges and blobs that MSER also picks up from non-text content.
        if 0.1 < w / max(h, 1) < 8 and h < gray.shape[0] * 0.3:
            cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)

    # Merge nearby glyph boxes into contiguous text-block regions, then
    # dilate a bit further so the eventual inpainting model covers edges.
    mask = cv2.dilate(mask, np.ones((15, 15), np.uint8), iterations=2)
    return mask


def inpaint_frames(
    frames: list[np.ndarray],
    masks: list[np.ndarray],
    on_progress: Callable[[float], None] | None = None,
) -> list[np.ndarray]:
    """Fill in the masked regions using a temporally-consistent video
    inpainting model.

    --- Plug in here ---
    git clone https://github.com/sczhou/ProPainter
    (follow their README for model weights + environment setup — needs a
    CUDA GPU with ~8GB+ VRAM for reasonable speed)

    ProPainter takes the full frame sequence + mask sequence together
    (not frame-by-frame) so it can propagate information across time,
    which is what avoids the flickering you'd get from single-image
    inpainting. Wire it up roughly as:

        from propainter_inference import ProPainter  # after cloning/adapting their inference script
        model = ProPainter(device="cuda")
        result_frames = model.inpaint(frames, masks)

    Report progress via ProPainter's own callback if it exposes one, or by
    chunking the video into segments and reporting after each segment.
    """
    if on_progress:
        on_progress(100)
    return frames  # passthrough stub — replace with model output


def encode_video(
    frames: list[np.ndarray],
    fps: float,
    original_path: str,
    output_path: Path,
) -> None:
    """Write frames back to video and remux the original audio track."""
    silent_path = output_path.with_suffix(".silent.mp4")

    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(silent_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)
    )
    for frame in frames:
        writer.write(frame)
    writer.release()

    # Remux: take video from our silent output, audio from the original.
    # -c:v copy avoids re-encoding video we just wrote; audio is re-encoded
    # to AAC for broad compatibility. If the source has no audio track,
    # ffmpeg's -shortest + missing stream will just drop straight to video-only.
    cmd = [
        "ffmpeg", "-y",
        "-i", str(silent_path),
        "-i", original_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    silent_path.unlink(missing_ok=True)
