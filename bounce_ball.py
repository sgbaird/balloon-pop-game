"""Impact detection for a yellow/white beach ball from its bounce alone (no shadow needed).

`--beach-mode bounce`. For setups where the projector shines almost straight at the wall,
so the ball hides its own shadow and beach_ball.py's shadow-convergence test never fires.

* A background model of the wall (projected graphics included) marks changed pixels;
  changed pixels that are yellow and not dark are ball.
* Ball blobs are tracked frame to frame. A hit is reported where a fast-moving ball
  suddenly turns (bounces off the wall) or nearly stops, at the turning point.

Tuned to err on the side of popping: a kid's yellow shirt swung fast can count too.
"""
import cv2
import numpy as np

SCALE = 0.5                 # processing scale relative to the camera frame
DIFF_THRESHOLD = 30         # per-channel change that counts as foreground
DARK = 0.6                  # pixels darker than this fraction of background are not ball
BALL_HUE = (20, 42)         # yellow (OpenCV hue 0-180); skin is ~10-20
BALL_MIN_SAT = 70
BALL_RADIUS = (4.0, 12.0)   # processing pixels
MIN_AREA, MAX_AREA = 8, 1500
MEAN_SAT = 92.0             # mean saturation of a blob's yellow pixels (ball is vivid; hair is dull)
MEAN_VAL = 130.0            # and their mean brightness (hair and camo are darker)
MEDIAN_HUE = 24.0           # median hue of those pixels: the ball reads ~25-33 to the camera, projected
                            # gold pictures (coins, Bowser, Peach's hair) ~21-24
MIN_FILL = 0.3              # blob area / enclosing-circle area (hair and shirts are ragged)
MATCH_DISTANCE = 45.0       # max jump between frames for the same ball (processing px)
TRACK_GAP = 0.25            # seconds without a sighting before a track is dropped
SPEED_MIN = 3.5             # px/frame the ball must move before the turn
TURN_ANGLE = 40.0           # degrees of direction change that count as a bounce
SUSTAIN = False             # True: the incoming motion must last two steps (fewer pops)
NET_STEPS = 3               # incoming steps over which the ball must really travel
NET_SPEED = 1.2             # px/frame of net travel over those steps
STOP_RATIO = 0.5            # or the speed drops below this fraction
COOLDOWN = 0.35             # seconds between hits
BG_RATE = 0.15
BG_RATE_FG = 0.03


class BounceImpactDetector:
    def __init__(self, screen_coords, frame_shape=(480, 640), **_):
        h, w = frame_shape[:2]
        self.size = (int(w * SCALE), int(h * SCALE))
        pts = (np.asarray(screen_coords, np.float32) * SCALE).astype(np.int32)
        roi = np.zeros((self.size[1], self.size[0]), np.uint8)
        cv2.fillPoly(roi, [pts], 255)
        self.roi = cv2.dilate(roi, np.ones((9, 9), np.uint8)) > 0
        self.k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self.bg = None
        self.last_small = None
        self.tracks = []            # each: list of (time, x, y, r)
        self.last_impact = -1e9
        self.last_masks = None
        self.decisions = []

    def _blobs(self, mask, raw, hsv):
        """Ball-sized blobs as (x, y, r, mean saturation, mean value) of their yellow pixels."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in contours:
            a = cv2.contourArea(c)
            if MIN_AREA <= a <= MAX_AREA:
                (x, y), r = cv2.minEnclosingCircle(c)
                if BALL_RADIUS[0] <= r <= BALL_RADIUS[1] and a >= MIN_FILL * np.pi * r * r:
                    bx, by, bw, bh = cv2.boundingRect(c)
                    sel = raw[by:by + bh, bx:bx + bw]
                    if not sel.any():
                        continue
                    px = hsv[by:by + bh, bx:bx + bw][sel]
                    sat, val = float(px[:, 1].mean()), float(px[:, 2].mean())
                    if sat >= MEAN_SAT and val >= MEAN_VAL and np.median(px[:, 0]) >= MEDIAN_HUE:
                        out.append((x, y, r, sat, val))
        return out

    def update(self, frame, now):
        """Feed one BGR camera frame; return (x, y, radius) in camera pixels on a hit, else None."""
        small = frame[::8, ::8]
        if self.last_small is not None and np.array_equal(small, self.last_small):
            return None
        self.last_small = small.copy()
        f = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA).astype(np.float32)
        if self.bg is None or self.bg.shape != f.shape:
            self.bg = f.copy()
            return None
        fg = (np.abs(f - self.bg).max(axis=2) > DIFF_THRESHOLD) & self.roi
        dark = f.mean(axis=2) < DARK * self.bg.mean(axis=2)
        hsv = cv2.cvtColor(f.astype(np.uint8), cv2.COLOR_BGR2HSV)
        ball = (fg & ~dark & (hsv[..., 0] >= BALL_HUE[0]) & (hsv[..., 0] <= BALL_HUE[1])
                & (hsv[..., 1] >= BALL_MIN_SAT))
        m = cv2.morphologyEx(ball.astype(np.uint8) * 255, cv2.MORPH_CLOSE, self.k7)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, self.k3)
        self.last_masks = (np.zeros_like(m), m)
        blobs = self._blobs(m, ball, hsv)
        rate = np.where(fg[..., None], BG_RATE_FG, BG_RATE)
        self.bg = self.bg * (1 - rate) + f * rate
        self.tracks = [t for t in self.tracks if now - t[-1][0] <= TRACK_GAP]
        used = set()
        hit = None
        for b in sorted(blobs, key=lambda b: -b[2]):
            best, bd = None, MATCH_DISTANCE
            for i, t in enumerate(self.tracks):
                if i in used:
                    continue
                d = np.hypot(b[0] - t[-1][1], b[1] - t[-1][2])
                if d < bd:
                    best, bd = i, d
            if best is None:
                self.tracks.append([(now, b[0], b[1], b[2], b[3], b[4])])
                used.add(len(self.tracks) - 1)
                continue
            used.add(best)
            t = self.tracks[best]
            t.append((now, b[0], b[1], b[2], b[3], b[4]))
            del t[:-8]
            h = self._bounce(t, now)
            if h is not None and (hit is None or h[2] > hit[2]):
                hit = h
        if hit is None or now - self.last_impact < COOLDOWN:
            return None
        self.last_impact = now
        x, y, r = hit
        return x / SCALE, y / SCALE, r / SCALE

    def _bounce(self, t, now):
        if len(t) < 3:
            return None
        p0, p1, p2 = (np.array(p[1:3]) for p in t[-3:])
        v1, v2 = p1 - p0, p2 - p1
        s1, s2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if len(t) >= 4:  # use the faster of the last two incoming steps (blur makes steps uneven)
            s1 = max(s1, np.linalg.norm(p0 - np.array(t[-4][1:3])))
        # Net travel over the incoming steps: a blob whose centre only jitters (a projected
        # picture overlapping another, a hand moving over a shirt) has fast steps but goes nowhere.
        back = min(len(t) - 1, NET_STEPS + 1)
        net = np.linalg.norm(p1 - np.array(t[-back][1:3])) / max(1, back - 1)
        if back < 3 or net < NET_SPEED:
            return None
        if s1 < SPEED_MIN or (SUSTAIN and len(t) >= 4 and min(np.linalg.norm(v1), np.linalg.norm(p0 - np.array(t[-4][1:3]))) < SPEED_MIN * 0.6):
            return None
        cos = float(np.dot(v1, v2) / (np.linalg.norm(v1) * s2)) if s2 > 1e-6 and np.linalg.norm(v1) > 1e-6 else 1.0
        angle = np.degrees(np.arccos(np.clip(cos, -1, 1)))
        if angle >= TURN_ANGLE or s2 < STOP_RATIO * s1:
            self.decisions = (self.decisions + [(now, "bounce", angle, s1, s2)])[-500:]
            self.last_stats = t[-2][4:6]
            return (p1[0], p1[1], t[-2][3])
        return None
