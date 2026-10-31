"""Halloween theme (`--theme halloween` or BALLOON_THEME=halloween).

Adds, on top of the normal game:

* coins: every popped balloon throws out spinning coins that fly to a coin counter,
  each with a synthesized "ching";
* shy ghosts floating around: they hide their eyes when a ball lands nearby, and a
  direct hit pops them for coins (one of them is sometimes a blue "Bluigey" ghost
  with a green cap);
* bats flapping across, spiders dangling on threads, cobwebs in the top corners,
  and a spiky shell that rolls by now and then for a big coin bonus;
* pennants in the costume colours (red, green, pink, yellow) and the occasional
  shout ("Wahoo!", "For real life!", ...).

Everything stays on the normal white background, and nothing is near-black, so the
beach-ball detector, which looks for a dark unsaturated shadow next to a yellow ball,
does not mistake the decorations for a ball and its shadow. Coins are orange-gold for
the same reason (the detector's ball hue is yellow).
"""
import io
import math
import random
import struct
import wave

import pygame

WIDTH, HEIGHT = 1920, 1080

COSTUME_COLORS = [(230, 40, 40), (40, 170, 60), (255, 105, 180), (250, 200, 0)]  # red, green, pink, yellow
COIN_FACE = (255, 165, 20)
COIN_EDGE = (225, 120, 0)
COIN_SHINE = (255, 225, 150)
COIN_SIZE = 44
COUNTER_POS = (90, HEIGHT - 80)

GHOST_BODY = (236, 232, 255)
GHOST_LINE = (140, 120, 205)
BLUIGEY_BODY = (165, 210, 255)
BLUIGEY_CAP = (40, 170, 60)
EYE = (70, 25, 110)
MOUTH = (150, 40, 90)
TONGUE = (255, 120, 170)
BAT = (120, 45, 175)
SPIDER_BODY = (235, 115, 20)
SPIDER_LEGS = (120, 45, 175)
THREAD = (185, 185, 200)
WEB = (205, 205, 220)

SHOUTS = ["Wahoo!", "Bluigey!", "For real life!", "Wackadoo!", "Hooray!", "Boo!", "Spooky!", "Coins!"]

N_GHOSTS = 3
MAX_BATS = 2
MAX_SPIDERS = 2
SHELL_EVERY = (25.0, 40.0)   # seconds between spiky shells


# --------------------------------------------------------------------------- sounds

def _tone_wav(segments, rate=44100, volume=0.35):
    """WAV bytes of (freq_start, freq_end, seconds, shape) segments; shape is 'square' or 'sine'."""
    frames = []
    phase = 0.0
    for f0, f1, dur, shape in segments:
        n = int(rate * dur)
        for i in range(n):
            t = i / max(1, n - 1)
            f = f0 + (f1 - f0) * t
            phase += 2 * math.pi * f / rate
            if shape == "square":
                s = 1.0 if math.sin(phase) >= 0 else -1.0
                s *= 0.55
            elif shape == "warble":
                s = math.sin(phase + 3 * math.sin(2 * math.pi * 7 * i / rate))
            else:
                s = math.sin(phase)
            env = min(1.0, i / (rate * 0.004)) * (1.0 - t) ** 1.5 if dur > 0.1 else min(1.0, i / (rate * 0.004))
            frames.append(int(32767 * volume * s * env))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % len(frames), *frames))
    buf.seek(0)
    return buf


def _make_sound(segments, volume):
    try:
        return pygame.mixer.Sound(file=_tone_wav(segments, volume=volume))
    except pygame.error:
        return None


# --------------------------------------------------------------------------- drawing helpers

def _ghost_surface(size, bluigey=False, shy=False):
    s = size
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    body = BLUIGEY_BODY if bluigey else GHOST_BODY
    c = (s // 2, s // 2 + s // 20)
    r = int(s * 0.40)
    # little curly tail at the back (left; flipped when moving left)
    pygame.draw.polygon(surf, body, [(c[0] - r + 6, c[1] + r // 3), (int(s * 0.04), int(s * 0.80)),
                                     (c[0] - r // 3, c[1] + r - 4)])
    pygame.draw.circle(surf, body, c, r)
    pygame.draw.circle(surf, GHOST_LINE, c, r, 5)
    if bluigey:
        cap = pygame.Rect(0, 0, int(r * 1.5), int(r * 0.9))
        cap.midbottom = (c[0] + r // 6, c[1] - int(r * 0.45))
        pygame.draw.ellipse(surf, BLUIGEY_CAP, cap)
        brim = pygame.Rect(0, 0, int(r * 1.0), int(r * 0.28))
        brim.midleft = (cap.centerx, cap.bottom - 4)
        pygame.draw.ellipse(surf, BLUIGEY_CAP, brim)
    ex1, ex2, ey = c[0] - int(r * 0.05), c[0] + int(r * 0.42), c[1] - int(r * 0.18)
    if shy:
        # blush, and both arms over the eyes
        for ex in (ex1, ex2):
            pygame.draw.ellipse(surf, (255, 170, 200), (ex - r * 0.2, ey + r * 0.3, r * 0.4, r * 0.18))
        for ex in (ex1, ex2):
            arm = pygame.Rect(0, 0, int(r * 0.55), int(r * 0.42))
            arm.center = (ex, ey + 2)
            pygame.draw.ellipse(surf, body, arm)
            pygame.draw.ellipse(surf, GHOST_LINE, arm, 2)
    else:
        for ex in (ex1, ex2):
            pygame.draw.ellipse(surf, EYE, (ex - r * 0.08, ey - r * 0.17, r * 0.16, r * 0.34))
        mouth = pygame.Rect(0, 0, int(r * 0.75), int(r * 0.45))
        mouth.midtop = (c[0] + int(r * 0.18), c[1] + int(r * 0.12))
        pygame.draw.ellipse(surf, MOUTH, mouth)
        tongue = pygame.Rect(0, 0, int(r * 0.4), int(r * 0.25))
        tongue.midbottom = (mouth.centerx + int(r * 0.08), mouth.bottom - 2)
        pygame.draw.ellipse(surf, TONGUE, tongue)
        for side in (-1, 1):  # stubby arms
            arm = pygame.Rect(0, 0, int(r * 0.35), int(r * 0.25))
            arm.center = (c[0] + side * int(r * 0.95), c[1] + int(r * 0.35))
            pygame.draw.ellipse(surf, body, arm)
            pygame.draw.ellipse(surf, GHOST_LINE, arm, 2)
    return surf


def _shell_surface(size):
    s = size
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    c = (s // 2, s // 2 + s // 10)
    r = int(s * 0.36)
    pygame.draw.ellipse(surf, (240, 190, 160), (c[0] - r - 6, c[1] - 6, 2 * r + 12, r * 0.55))  # rim
    pygame.draw.circle(surf, (40, 160, 60), c, r, draw_top_right=True, draw_top_left=True)
    for k in range(5):  # spikes
        a = math.pi * (0.15 + 0.7 * k / 4)
        bx, by = c[0] - math.cos(a) * r * 0.78, c[1] - math.sin(a) * r * 0.78
        tx, ty = c[0] - math.cos(a) * r * 1.35, c[1] - math.sin(a) * r * 1.35
        nx, ny = -math.sin(a) * r * 0.16, math.cos(a) * r * 0.16
        pygame.draw.polygon(surf, (250, 250, 245), [(bx + nx, by + ny), (bx - nx, by - ny), (tx, ty)])
        pygame.draw.polygon(surf, (190, 190, 200), [(bx + nx, by + ny), (bx - nx, by - ny), (tx, ty)], 2)
    return surf


def _web_surface():
    size = 320
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    spokes = [math.radians(a) for a in (0, 18, 36, 54, 72, 90)]
    for a in spokes:
        pygame.draw.line(surf, WEB, (0, 0), (math.cos(a) * size, math.sin(a) * size), 2)
    for ring in range(1, 6):
        d = ring * size / 6
        pts = [(math.cos(a) * d, math.sin(a) * d) for a in spokes]
        for p, q in zip(pts, pts[1:]):
            mid = ((p[0] + q[0]) / 2 * 0.9, (p[1] + q[1]) / 2 * 0.9)  # sagging threads
            pygame.draw.lines(surf, WEB, False, [p, mid, q], 2)
    return surf


# --------------------------------------------------------------------------- actors

class Coin:
    def __init__(self, x, y, delay=0.0):
        self.x, self.y = x, y
        self.vx = random.uniform(-7, 7)
        self.vy = random.uniform(-17, -11)
        self.spin = random.uniform(0, math.pi)
        self.age = -delay
        self.flying = False
        self.start = None
        self.done = False

    def update(self, dt):
        self.age += dt
        if self.age < 0:
            return
        self.spin += dt * 14
        if self.age < 0.55:
            self.x += self.vx * dt * 60
            self.y += self.vy * dt * 60
            self.vy += 0.75 * dt * 60
        else:
            if self.start is None:
                self.start = (self.x, self.y)
            t = min(1.0, (self.age - 0.55) / 0.45)
            e = t * t * (3 - 2 * t)
            self.x = self.start[0] + (COUNTER_POS[0] - self.start[0]) * e
            self.y = self.start[1] + (COUNTER_POS[1] - self.start[1]) * e - math.sin(math.pi * t) * 120
            if t >= 1.0:
                self.done = True

    def draw(self, surface):
        if self.age < 0:
            return
        draw_coin(surface, self.x, self.y, COIN_SIZE, self.spin)


def draw_coin(surface, x, y, size, spin=0.0):
    w = max(4, int(size * abs(math.cos(spin))))
    rect = pygame.Rect(0, 0, w, size)
    rect.center = (int(x), int(y))
    pygame.draw.ellipse(surface, COIN_EDGE, rect)
    inner = rect.inflate(-max(2, w // 5), -size // 5)
    if inner.width > 2:
        pygame.draw.ellipse(surface, COIN_FACE, inner)
    if w > size // 3:
        pygame.draw.line(surface, COIN_SHINE, (rect.centerx, rect.top + size // 4),
                         (rect.centerx, rect.bottom - size // 4), max(2, w // 8))


class Ghost:
    def __init__(self, bluigey=False, first=False):
        self.bluigey = bluigey
        self.size = 220 if bluigey else random.randint(170, 210)
        self.normal = _ghost_surface(self.size, bluigey)
        self.shy_img = _ghost_surface(self.size, bluigey, shy=True)
        side = random.choice((-1, 1))
        self.x = random.uniform(200, WIDTH - 200) if first else (-self.size if side > 0 else WIDTH + self.size)
        self.vx = side * random.uniform(0.6, 1.4)
        self.base_y = random.uniform(220, HEIGHT - 260)
        self.phase = random.uniform(0, 2 * math.pi)
        self.y = self.base_y
        self.shy = 0.0
        self.alpha = 0.0
        self.gone = False

    def update(self, dt, now):
        self.x += self.vx * dt * 60
        self.y = self.base_y + math.sin(now * 1.3 + self.phase) * 30
        self.shy = max(0.0, self.shy - dt)
        self.alpha = min(200.0, self.alpha + dt * 250)
        if (self.vx > 0 and self.x > WIDTH + self.size) or (self.vx < 0 and self.x < -self.size):
            self.vx = -self.vx  # turn around at the edge and come back

    def draw(self, surface):
        img = self.shy_img if self.shy > 0 else self.normal
        if self.vx < 0:
            img = pygame.transform.flip(img, True, False)
        img.set_alpha(int(self.alpha))
        surface.blit(img, img.get_rect(center=(int(self.x), int(self.y))))

    def contains(self, x, y, pad):
        return math.hypot(x - self.x, y - self.y) <= self.size * 0.42 + pad


class Bat:
    def __init__(self):
        self.dir = random.choice((-1, 1))
        self.x = -80 if self.dir > 0 else WIDTH + 80
        self.base_y = random.uniform(120, 520)
        self.speed = random.uniform(4.0, 6.5)
        self.phase = random.uniform(0, 6.28)
        self.y = self.base_y

    def update(self, dt, now):
        self.x += self.dir * self.speed * dt * 60
        self.y = self.base_y + math.sin(now * 2.2 + self.phase) * 60
        self.flap = math.sin(now * 16 + self.phase)

    @property
    def gone(self):
        return self.x < -120 or self.x > WIDTH + 120

    def draw(self, surface):
        x, y, f, k = self.x, self.y, getattr(self, "flap", 0.0), 1.7
        tip = 40 * f
        for side in (-1, 1):
            wing = [(8, -4), (30, -16 - tip), (56, -6 - tip * 1.3), (46, 8 - tip * 0.6), (34, 2), (22, 10), (8, 6)]
            pygame.draw.polygon(surface, BAT, [(x + side * k * px, y + k * py) for px, py in wing])
        pygame.draw.ellipse(surface, BAT, (x - 11 * k, y - 14 * k, 22 * k, 28 * k))
        for side in (-1, 1):
            ear = [(9, -10), (6, -22), (2, -12)]
            pygame.draw.polygon(surface, BAT, [(x + side * k * px, y + k * py) for px, py in ear])
            pygame.draw.circle(surface, (255, 230, 120), (int(x + side * 4 * k), int(y - 6 * k)), 5)


class Spider:
    def __init__(self):
        self.x = random.uniform(150, WIDTH - 150)
        self.target = random.uniform(160, 460)
        self.y = -30.0
        self.life = random.uniform(10, 18)
        self.phase = random.uniform(0, 6.28)
        self.leaving = False

    def update(self, dt, now):
        self.life -= dt
        if self.life <= 0:
            self.leaving = True
        goal = -40 if self.leaving else self.target + math.sin(now * 1.1 + self.phase) * 25
        self.y += (goal - self.y) * min(1.0, dt * 1.5)
        self.wiggle = math.sin(now * 9 + self.phase)

    @property
    def gone(self):
        return self.leaving and self.y < -30

    def draw(self, surface):
        x, y, w = self.x, self.y, getattr(self, "wiggle", 0.0)
        pygame.draw.line(surface, THREAD, (int(x), 0), (int(x), int(y - 14)), 2)
        for side in (-1, 1):
            for k in range(4):
                a = (k - 1.5) * 0.45 + w * 0.08 * (1 if k % 2 else -1)
                knee = (x + side * 26, y - 6 + k * 7 - 14 * math.cos(a))
                foot = (x + side * 44, y + 6 + k * 9)
                pygame.draw.lines(surface, SPIDER_LEGS, False, [(x, y), knee, foot], 3)
        pygame.draw.circle(surface, SPIDER_BODY, (int(x), int(y + 6)), 17)
        pygame.draw.circle(surface, SPIDER_BODY, (int(x), int(y - 12)), 10)
        for ex in (-4, 4):
            pygame.draw.circle(surface, (255, 255, 255), (int(x + ex), int(y - 13)), 3)
            pygame.draw.circle(surface, SPIDER_LEGS, (int(x + ex), int(y - 12)), 1)


class Shell:
    def __init__(self):
        self.size = 210
        self.img = _shell_surface(self.size)
        self.dir = random.choice((-1, 1))
        self.x = -self.size if self.dir > 0 else WIDTH + self.size
        self.y = random.uniform(HEIGHT * 0.5, HEIGHT - 220)
        self.angle = 0.0
        self.hit = False

    def update(self, dt, now):
        self.x += self.dir * 5.0 * dt * 60
        self.angle = math.sin(now * 6) * 12  # waddle

    @property
    def gone(self):
        return self.hit or self.x < -self.size * 1.5 or self.x > WIDTH + self.size * 1.5

    def draw(self, surface):
        img = pygame.transform.rotate(self.img, self.angle)
        surface.blit(img, img.get_rect(center=(int(self.x), int(self.y))))

    def contains(self, x, y, pad):
        return math.hypot(x - self.x, y - self.y) <= self.size * 0.45 + pad


class Shout:
    def __init__(self, text, x, y, color, font):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.font = font
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        self.y -= 40 * dt

    @property
    def gone(self):
        return self.age > 1.6

    def draw(self, surface):
        scale = min(1.0, self.age * 6)
        img = self.font.render(self.text, True, self.color)
        outline = self.font.render(self.text, True, (255, 255, 255))
        if scale < 1.0:
            size = (max(1, int(img.get_width() * scale)), max(1, int(img.get_height() * scale)))
            img = pygame.transform.smoothscale(img, size)
            outline = pygame.transform.smoothscale(outline, size)
        a = int(255 * min(1.0, (1.6 - self.age) * 2))
        img.set_alpha(a)
        outline.set_alpha(a)
        r = img.get_rect(center=(int(self.x), int(self.y)))
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
            surface.blit(outline, r.move(dx, dy))
        surface.blit(img, r)


# --------------------------------------------------------------------------- the layer

class HalloweenLayer:
    def __init__(self):
        if pygame.mixer.get_num_channels() < 16:
            pygame.mixer.set_num_channels(16)  # room for overlapping coin sounds
        self.coins = []
        self.coin_count = 0
        self.ghosts = [Ghost(first=True) for _ in range(N_GHOSTS)]
        self.respawns = []        # times at which a popped ghost comes back
        self.bats, self.spiders, self.shells, self.shouts = [], [], [], []
        self.next_bat = 3.0
        self.next_spider = 5.0
        self.next_shell = random.uniform(*SHELL_EVERY)
        self.pending_sounds = []  # (time, sound)
        self.web = _web_surface()
        self.web_flipped = pygame.transform.flip(self.web, True, False)
        self.font = pygame.font.Font(None, 96)
        self.counter_font = pygame.font.Font(None, 72)
        self.title_font = pygame.font.Font(None, 64)
        self.last_tick = pygame.time.get_ticks() / 1000.0
        self.now = 0.0
        self.prev_state = None
        self.coin_sound = _make_sound([(988, 988, 0.07, "square"), (1319, 1319, 0.45, "square")], 0.22)
        self.boo_sound = _make_sound([(620, 280, 0.7, "warble")], 0.4)
        self.bonk_sound = _make_sound([(200, 90, 0.25, "square")], 0.35)

    # ---- game hooks
    def update(self, game_state):
        t = pygame.time.get_ticks() / 1000.0
        dt = min(0.1, max(0.0, t - self.last_tick))
        self.last_tick = t
        if game_state == "paused":
            return
        if game_state == "playing" and self.prev_state == "start":
            self.coin_count = 0
            self.coins.clear()
        self.prev_state = game_state
        self.now += dt
        now = self.now

        for g in self.ghosts:
            g.update(dt, now)
        while self.respawns and self.respawns[0] <= now:
            self.respawns.pop(0)
            self.ghosts.append(Ghost(bluigey=random.random() < 0.3))

        self.next_bat -= dt
        if self.next_bat <= 0 and len(self.bats) < MAX_BATS:
            self.bats.append(Bat())
            self.next_bat = random.uniform(5, 11)
        self.next_spider -= dt
        if self.next_spider <= 0 and len(self.spiders) < MAX_SPIDERS:
            self.spiders.append(Spider())
            self.next_spider = random.uniform(7, 14)
        if game_state == "playing":
            self.next_shell -= dt
            if self.next_shell <= 0:
                self.shells.append(Shell())
                self.next_shell = random.uniform(*SHELL_EVERY)

        for group in (self.bats, self.spiders, self.shells):
            for a in group:
                a.update(dt, now)
            group[:] = [a for a in group if not a.gone]

        for c in self.coins:
            c.update(dt)
        arrived = [c for c in self.coins if c.done]
        if arrived:
            self.coins = [c for c in self.coins if not c.done]
            self.coin_count += len(arrived)
            for _ in arrived:
                self._play(self.coin_sound)

        for s in self.shouts:
            s.update(dt)
        self.shouts = [s for s in self.shouts if not s.gone]

        due = [p for p in self.pending_sounds if p[0] <= now]
        if due:
            self.pending_sounds = [p for p in self.pending_sounds if p[0] > now]
            for _, snd in due:
                self._play(snd)

    def on_pop(self, x, y, balloon):
        """A balloon was popped at (x, y)."""
        if balloon.points <= 0:
            self.shout("Boo!", x, y - 80, (150, 60, 200))
            return
        n = 3 + (3 if getattr(balloon, "balloon_type", "") == "bonus" else 0)
        if getattr(balloon, "size_scale", 1.0) > 1.0:
            n += 2
        self.burst(x, y, n)
        if random.random() < 0.15:
            self.shout(random.choice(SHOUTS), x, y - 110)

    def hit(self, x, y, radius, game_state):
        """A ball landed at (x, y) without popping a balloon. True if it hit a ghost or shell."""
        if game_state != "playing":
            return False
        for sh in self.shells:
            if not sh.hit and sh.contains(x, y, radius):
                sh.hit = True
                self.burst(sh.x, sh.y, 15)
                self.shout("Bowser bonus!", sh.x, sh.y - 140, (235, 115, 20))
                self._play(self.bonk_sound)
                return True
        for g in self.ghosts:
            if g.contains(x, y, radius):
                self.ghosts.remove(g)
                self.respawns.append(self.now + random.uniform(4, 8))
                self.respawns.sort()
                self.burst(g.x, g.y, 10 if g.bluigey else 5)
                self.shout("Bluigey!" if g.bluigey else "Boo!", g.x, g.y - 120,
                           (40, 120, 230) if g.bluigey else (150, 60, 200))
                self._play(self.boo_sound)
                return True
        for g in self.ghosts:  # a near miss makes nearby ghosts hide their eyes
            if math.hypot(x - g.x, y - g.y) < 350:
                g.shy = 1.5
        return False

    def draw_back(self, surface):
        surface.blit(self.web, (0, 0))
        surface.blit(self.web_flipped, (WIDTH - self.web.get_width(), 0))
        # pennants in the costume colours along the top
        n = 24
        for i in range(n):
            x0 = WIDTH * 0.17 + i * (WIDTH * 0.66 / n)
            w = WIDTH * 0.66 / n
            sag = math.sin(math.pi * (i + 0.5) / n) * 40
            pygame.draw.polygon(surface, COSTUME_COLORS[i % 4],
                                [(x0 + 3, 12 + sag), (x0 + w - 3, 12 + sag), (x0 + w / 2, 60 + sag)])
        for group in (self.spiders, self.ghosts, self.bats):
            for a in group:
                a.draw(surface)

    def draw_front(self, surface, game_state):
        for sh in self.shells:
            sh.draw(surface)
        for c in self.coins:
            c.draw(surface)
        for s in self.shouts:
            s.draw(surface)
        if game_state in ("playing", "paused", "end"):
            draw_coin(surface, COUNTER_POS[0], COUNTER_POS[1], 64, math.sin(self.now * 3) * 0.6)
            txt = self.counter_font.render("x %d" % self.coin_count, True, COIN_EDGE)
            surface.blit(txt, txt.get_rect(midleft=(COUNTER_POS[0] + 45, COUNTER_POS[1] + 4)))
        if game_state == "mode_select":
            title = self.title_font.render("Happy Halloween!", True, (235, 115, 20))
            surface.blit(title, title.get_rect(midtop=(WIDTH // 2, 80)))

    # ---- helpers
    def burst(self, x, y, n):
        for i in range(n):
            self.coins.append(Coin(x, y, delay=i * 0.04))

    def shout(self, text, x, y, color=None):
        color = color or random.choice(COSTUME_COLORS)
        x = min(max(x, 250), WIDTH - 250)
        y = min(max(y, 120), HEIGHT - 120)
        for other in self.shouts:  # stack instead of overlapping
            if abs(other.x - x) < 500 and abs(other.y - y) < 90:
                y = other.y - 100
        self.shouts.append(Shout(text, x, y, color, self.font))

    def _play(self, snd):
        if snd is not None:
            ch = pygame.mixer.find_channel(True)
            if ch is not None:
                ch.play(snd)
