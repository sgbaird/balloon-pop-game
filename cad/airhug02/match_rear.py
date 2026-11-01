"""Extract rear-face lettering correspondences, including oblique views.

python cad/airhug02/match_rear.py /path/to/source.mp4
Requires NumPy and OpenCV (SIFT). Deterministic RANSAC seed; manual face masks
come from dimension-landmarks.json. 18s remains excluded from shape fitting.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    source = json.loads((ROOT / "evidence/source.json").read_text())
    if hashlib.sha256(args.video.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError("Video does not match source hash")
    cv2.setRNGSeed(0)
    data = json.loads((ROOT / "evidence/dimension-landmarks.json").read_text())
    sift = cv2.SIFT_create(contrastThreshold=0.015)
    cap = cv2.VideoCapture(str(args.video))
    images = {}
    for frame in data["frames"]:
        if not frame["rear"] or frame["second"] == 45:
            continue
        cap.set(cv2.CAP_PROP_POS_MSEC, frame["second"] * 1000)
        ok, bgr = cap.read()
        if not ok or bgr.shape[:2] != (1920, 1080):
            raise ValueError("Wrong frame size")
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(gray)
        cv2.fillPoly(mask, [np.array(frame["rear"], np.int32)], 255)
        images[frame["second"]] = (gray, mask)
    cap.release()
    ref_image, ref_mask = images[36]
    reference, descriptors = sift.detectAndCompute(ref_image, ref_mask)
    pairs = []
    for frame in data["frames"]:
        second = frame["second"]
        if second not in images or second == 36:
            continue
        gray, mask = images[second]
        aa = []
        bb = []
        # Restore some of the narrow face's short-axis resolution before SIFT.
        # Mapping keypoints back preserves original image coordinates.
        for factor in [1, 1.5, 2, 3, 4]:
            angle = np.deg2rad(frame["angle_deg"])
            direction = np.array([-np.sin(angle), np.cos(angle)])
            affine = np.eye(2) + (factor - 1) * np.outer(direction, direction)
            corners = np.array([[0, 0], [1080, 0], [0, 1920], [1080, 1920]]) @ affine.T
            offset = -corners.min(axis=0)
            size = tuple(np.ceil(np.ptp(corners, axis=0)).astype(int))
            transform = np.c_[affine, offset]
            warped = cv2.warpAffine(gray, transform, size)
            warped_mask = cv2.warpAffine(mask, transform, size)
            keypoints, target = sift.detectAndCompute(warped, warped_mask)
            if target is None or len(target) < 2:
                continue
            for first, next_best in cv2.BFMatcher().knnMatch(descriptors, target, k=2):
                if first.distance < 0.75 * next_best.distance:
                    aa.append(reference[first.queryIdx].pt)
                    bb.append(
                        np.linalg.solve(
                            affine, np.array(keypoints[first.trainIdx].pt) - offset
                        )
                    )
        if len(aa) < 4:
            raise ValueError(f"Insufficient matches at {second}s")
        a = np.float32(aa)
        b = np.float32(bb)
        homography, inliers = cv2.findHomography(a, b, cv2.RANSAC, 3.0)
        if homography is None:
            raise ValueError(f"Homography failed at {second}s")
        keep = inliers.ravel().astype(bool)
        a = a[keep]
        b = b[keep]
        _, unique = np.unique(np.round(a, 0), axis=0, return_index=True)
        a = a[unique]
        b = b[unique]
        pairs.append(
            dict(
                second=second,
                reference_second=36,
                reference_pixels=a.tolist(),
                pixels=b.tolist(),
                homography=homography.tolist(),
                used_for_fit=frame["role"] == "train",
            )
        )
        print(f"{second}s: {len(a)} distinct matched reference pixels")
    report = dict(
        method="SIFT ratio 0.75; rear-face masks; target affine stretch factors 1,1.5,2,3,4 across long axis; RANSAC homography 3px; rounded reference-pixel deduplication. 18s reserved for evaluation.",
        matches=pairs,
    )
    (ROOT / "evidence/rear-matches.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
