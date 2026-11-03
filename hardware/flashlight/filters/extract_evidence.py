"""Extract representative, uncorrected frames from the second issue #5 video.

Usage: python extract_evidence.py /path/to/downloaded-video.mp4 [output.jpg]
Requires opencv-python (or opencv-python-headless) and Pillow.
"""

import argparse
from pathlib import Path

import cv2
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "output", type=Path, nargs="?",
        default=Path(__file__).with_name("cup-video-evidence.jpg"),
    )
    args = parser.parse_args()
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        parser.error(f"Cannot open video: {args.video}")
    panels = [(2.0, "Early bright core + rings"),
              (6.8, "Later cyan wash"),
              (10.8, "Blue cup shown")]
    sheet = Image.new("RGB", (810, 520), "#191919")
    draw = ImageDraw.Draw(sheet)
    try:
        for index, (seconds, label) in enumerate(panels):
            cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
            ok, frame = cap.read()
            if not ok:
                parser.error(f"Cannot decode frame at {seconds}s")
            picture = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            picture.thumbnail((270, 470))
            x = index * 270
            sheet.paste(picture, (x + (270 - picture.width) // 2, 0))
            draw.text((x + 8, 477), f"{seconds:.1f}s: {label}", fill="white")
        draw.text((8, 502), "Resized full frames; no exposure/color correction. Not a controlled A/B test.", fill="white")
        sheet.save(args.output, quality=90)
    finally:
        cap.release()


if __name__ == "__main__":
    main()
