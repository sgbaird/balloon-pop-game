"""Impact detection for a pale, banded ball (e.g. a white/yellow beach ball).

Colour-only detection (main.detect_ball) needs a solid, saturated ball. A beach
ball's white bands look like the projected wall and its yellow bands are only a
fragment of the ball, so its apparent radius is unreliable. This detector
instead uses the ball's shadow on the projection:

* A background model of the wall (projected game graphics included) marks the
  pixels that changed this frame.
* Changed pixels much darker than the background and unsaturated are shadow;
  changed pixels that are warm/yellowish and not dark are ball.
* As the ball flies toward the wall its shadow converges on it, and they touch
  only when the ball reaches the wall. A moving ball blob next to a ball-sized
  shadow blob is reported as an impact, once per cooldown.

Tuned on recordings of a ~25 cm white/yellow beach ball with the camera about
5 m from the wall (ball radius at the wall ~12 px at 640x480). Work is done at
half resolution (~10 ms per frame).
"""
import os

import cv2
import numpy as np

SCALE = 0.5                 # processing scale relative to the camera frame
DIFF_THRESHOLD = 35         # per-channel change that counts as foreground
SHADOW_DARKNESS = 0.65      # shadow luminance below this fraction of background
SHADOW_MAX_SAT = 70
BALL_HUE = (22, 40)         # yellow (OpenCV hue 0-180); skin is ~10-20, so it is excluded
BALL_MIN_SAT = 40
BALL_RADIUS = (3.0, 8.5)    # ball radius at the wall, processing pixels
SHADOW_MAX_RADIUS = 8.0
PAIR_DISTANCE = 13.0        # max ball-shadow centre distance at impact
STATIC_FRAMES = 4           # blob within 2 px for this many frames = ghost
COOLDOWN = 0.6              # seconds between impacts
SPEED_MIN = 4.0             # px/frame the ball or its shadow must have moved just before
                            # contact (a held or carried ball drifts slower than this)
SPEED_WINDOW = 0.25         # seconds before contact in which that speed is looked for
MATCH_DISTANCE = 40.0       # max blob jump between frames when estimating speed
TRACK_FRAMES = 6            # frames of history used for a ball's own speed
MAX_COMPONENT_AREA = 900    # changed-pixel region containing the ball must be smaller than this;
                            # a held or carried ball is joined to the person holding it
BG_RATE = 0.15              # background learning rate (unchanged pixels)
BG_RATE_FG = 0.03           # learning rate where something changed (ghosts fade)


class BeachBallImpactDetector:
    def __init__(self, screen_coords, frame_shape=(480, 640), strict=True):
        # strict: ignore a ball joined to a person (no pops from carrying it along the wall,
        # but also none from pressing it onto the wall or hitting right next to someone).
        self.max_area = MAX_COMPONENT_AREA if strict else float("inf")
        h, w = frame_shape[:2]
        self.size = (int(w * SCALE), int(h * SCALE))
        pts = (np.asarray(screen_coords, np.float32) * SCALE).astype(np.int32)
        roi = np.zeros((self.size[1], self.size[0]), np.uint8)
        cv2.fillPoly(roi, [pts], 255)
        self.roi = cv2.dilate(roi, np.ones((7, 7), np.uint8)) > 0
        self.k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        self.bg = None
        self.history = []
        self.last_impact = -1e9
        self.last_small = None
        self.prev = ([], [])       # (shadows, balls) of the previous frame
        self.speeds = []           # (time, fastest small ball/shadow blob speed)
        self.pending = None        # closest ball-shadow approach so far: (d, x, y, r, time)
        self.decisions = []        # recent candidate outcomes, for tuning
        self.ball_hist = []        # ball blobs of the last frames, for this ball's own speed
        self.last_masks = None  # (shadow, ball) for debugging displays

    @staticmethod
    def _blobs(mask, min_area, max_area):
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in contours:
            area = cv2.contourArea(c)
            if min_area <= area <= max_area:
                (x, y), r = cv2.minEnclosingCircle(c)
                out.append((x, y, r))
        return out

    def _track_speed(self, x, y):
        """Fastest step of this ball over the last frames, following nearest neighbours back."""
        fastest = 0.0
        for frame_balls in reversed(self.ball_hist):
            d = [(np.hypot(x - p[0], y - p[1]), p) for p in frame_balls]
            if not d:
                break
            step, p = min(d, key=lambda e: e[0])
            if step > MATCH_DISTANCE:
                break
            fastest = max(fastest, step)
            x, y = p[0], p[1]
        return fastest

    def update(self, frame, now):
        """Feed one BGR camera frame; return (x, y, radius) in camera pixels on impact, else None.

        The impact is reported one frame after contact, at the frame where the ball
        and its shadow were closest.
        """
        # The game loop can run faster than the camera and hand over the same frame
        # twice; a repeated frame would make a moving ball look stationary.
        small = frame[::8, ::8]
        if self.last_small is not None and np.array_equal(small, self.last_small):
            return None
        self.last_small = small.copy()

        f = cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA).astype(np.float32)
        if self.bg is None or self.bg.shape != f.shape:
            self.bg = f.copy()
            return None

        fg = (np.abs(f - self.bg).max(axis=2) > DIFF_THRESHOLD) & self.roi
        lum, lum_bg = f.mean(axis=2), self.bg.mean(axis=2)
        hsv = cv2.cvtColor(f.astype(np.uint8), cv2.COLOR_BGR2HSV)
        dark = lum < SHADOW_DARKNESS * lum_bg
        shadow = fg & dark & (hsv[..., 1] < SHADOW_MAX_SAT)
        ball = (fg & ~dark & (hsv[..., 0] >= BALL_HUE[0]) & (hsv[..., 0] <= BALL_HUE[1])
                & (hsv[..., 1] >= BALL_MIN_SAT))

        shadow_m = cv2.morphologyEx(shadow.astype(np.uint8) * 255, cv2.MORPH_OPEN, self.k3)
        ball_m = cv2.morphologyEx(ball.astype(np.uint8) * 255, cv2.MORPH_CLOSE, self.k7)
        ball_m = cv2.morphologyEx(ball_m, cv2.MORPH_OPEN, self.k3)
        self.last_masks = (shadow_m, ball_m)

        shadows = [s for s in self._blobs(shadow_m, 25, 900) if s[2] <= SHADOW_MAX_RADIUS]
        balls = self._blobs(ball_m, 10, 900)

        # Ignore ball blobs that have not moved (background ghosts, static yellow graphics).
        recent = self.history[-STATIC_FRAMES:]
        moving = [b for b in balls
                  if not (len(recent) == STATIC_FRAMES and all(
                      any(np.hypot(b[0] - p[0], b[1] - p[1]) < 2.0 for p in h) for h in recent))]
        self.history = (self.history + [balls])[-STATIC_FRAMES:]
        moving = [b for b in moving if BALL_RADIUS[0] <= b[2] <= BALL_RADIUS[1]]

        rate = np.where(fg[..., None], BG_RATE_FG, BG_RATE)
        self.bg = self.bg * (1 - rate) + f * rate

        # Speed of ball-sized blobs: distance to the nearest same-kind blob last frame.
        fastest = 0.0
        for cur, prev in ((shadows, self.prev[0]), (moving, self.prev[1])):
            for b in cur:
                d = [np.hypot(b[0] - p[0], b[1] - p[1]) for p in prev]
                if d and min(d) <= MATCH_DISTANCE:
                    fastest = max(fastest, min(d))
        self.prev = (shadows, moving)
        self.speeds = [(t, v) for t, v in self.speeds if now - t <= 1.0] + [(now, fastest)]

        best = None
        for s in shadows:
            for b in moving:
                d = np.hypot(s[0] - b[0], s[1] - b[1])
                if d < PAIR_DISTANCE and (best is None or d < best[0]):
                    best = (d, b[0], b[1], b[2], now)
        if best is not None:
            # Size of the connected changed region the ball belongs to.
            fg_u8 = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_CLOSE, self.k3)
            _, labels, stats, _ = cv2.connectedComponentsWithStats(fg_u8, connectivity=8)
            bx, by = int(round(best[1])), int(round(best[2]))
            lab = labels[min(max(by, 0), labels.shape[0] - 1), min(max(bx, 0), labels.shape[1] - 1)]
            area = int(stats[lab, cv2.CC_STAT_AREA]) if lab > 0 else 0
            best = best + (area, self._track_speed(best[1], best[2]))
        self.ball_hist = (self.ball_hist + [balls])[-TRACK_FRAMES:]

        # Report at the closest approach: wait until the distance grows again or the pair is lost.
        if best is not None and (self.pending is None or best[0] <= self.pending[0]):
            self.pending = best
            return None
        done, self.pending = self.pending, best
        if done is None:
            return None
        approach = max((v for t, v in self.speeds if done[4] - SPEED_WINDOW <= t <= done[4]), default=0.0)
        if done[4] - self.last_impact < COOLDOWN:
            reason = "cooldown"
        elif approach < SPEED_MIN:
            reason = "slow"
        elif done[5] > self.max_area:
            reason = "attached"
        else:
            reason = "impact"
        # Recent decisions, for tuning:
        # (time, reason, distance, x, y, radius, region area, any-blob speed, this ball's speed)
        self.decisions = (self.decisions + [(done[4], reason, done[0], done[1], done[2], done[3],
                                             done[5], approach, done[6])])[-500:]
        if reason != "impact":
            return None
        self.last_impact = done[4]
        x, y, r = done[1:4]
        return x / SCALE, y / SCALE, r / SCALE


class DebugRecorder:
    """Saves every processed frame (JPEG) and a CSV of timing and impacts, for tuning.

    Enabled by setting BALLOON_DEBUG_DIR. Frames are written one file at a time so
    nothing is lost if the game is closed abruptly.
    """

    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.dir = directory
        self.n = 0
        self.log = open(os.path.join(directory, "frames.csv"), "w")
        self.log.write("index,time,impact_x,impact_y,impact_r\n")

    def record(self, frame, now, impact):
        cv2.imwrite(os.path.join(self.dir, f"{self.n:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        x, y, r = impact if impact is not None else ("", "", "")
        self.log.write(f"{self.n},{now:.3f},{x},{y},{r}\n")
        self.log.flush()
        self.n += 1
