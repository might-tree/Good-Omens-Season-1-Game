"""Good Omens: The Ineffable Plan - a cartoon pygame game.

An angel and a demon have three levels to stop Armageddon.
Run:  python game.py   (run generate_sprites.py first if assets/ is missing)
"""
import array
import json
import math
import os
import random
import sys

import pygame

TITLE = "Good Omens: The Ineffable Plan"
W, H = 1280, 720
HUD_H = 58
TOP_Y = HUD_H + 84          # highest a character's feet can go, so heads stay below the HUD
FPS = 60
SCALE = 0.62                # sprite sheets are drawn large; this is their in-game size
PLAYER_SPEED = 200
BOOST_SPEED = 420
HIT_PENALTY = 8
CREPE_BONUS = 8


def resource(*parts):
    """Path to a bundled file, both when run as a script and from a PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


SAVE_FILE = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "GoodOmensGame", "save.json")


def load_save():
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_save(data):
    try:
        os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def circle_hits_rect(x, y, r, rect):
    nx, ny = clamp(x, rect.left, rect.right), clamp(y, rect.top, rect.bottom)
    return (x - nx) ** 2 + (y - ny) ** 2 < r * r


# ---------------------------------------------------------------- text
_fonts = {}


def font(size, bold=False):
    if (size, bold) not in _fonts:
        _fonts[size, bold] = pygame.font.SysFont("georgia,palatinolinotype,timesnewroman", size, bold=bold)
    return _fonts[size, bold]


def text(surf, msg, size, color, pos, anchor="center", bold=False, shadow=True):
    f = font(size, bold)
    img = f.render(msg, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        sh = f.render(msg, True, (0, 0, 0))
        sh.set_alpha(140)
        surf.blit(sh, rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def wrap(msg, size, width):
    words, lines, line = msg.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if font(size).size(trial)[0] > width and line:
            lines.append(line)
            line = w
        else:
            line = trial
    return lines + [line] if line else lines


# ---------------------------------------------------------------- sound
class Sfx:
    """Tiny synthesised sound effects, so the game needs no audio files."""

    RATE = 22050
    RECIPES = {   # name: (wave, volume, [(frequencies, seconds, pitch slide, noise)])
        "pickup": ("square", 0.22, [([880], 0.06, 0, 0), ([1320], 0.1, 0, 0)]),
        "crepe": ("square", 0.2, [([523], 0.07, 0, 0), ([659], 0.07, 0, 0), ([784], 0.14, 0, 0)]),
        "hit": ("square", 0.4, [([200], 0.32, -0.6, 0.5)]),
        "miracle": ("sine", 0.55, [([523, 659, 784, 1047], 0.9, 0.03, 0)]),
        "bentley": ("saw", 0.35, [([70, 105], 0.7, 1.2, 0.25)]),
        "clear": ("square", 0.2, [([523], 0.12, 0, 0), ([659], 0.12, 0, 0), ([784], 0.12, 0, 0), ([1047], 0.4, 0, 0)]),
        "lose": ("square", 0.22, [([392], 0.2, 0, 0), ([330], 0.2, 0, 0), ([262], 0.2, 0, 0), ([196], 0.6, -0.1, 0)]),
        "tick": ("square", 0.12, [([1200], 0.03, 0, 0)]),
        "select": ("square", 0.15, [([660], 0.05, 0, 0)]),
        "nope": ("square", 0.15, [([220], 0.12, 0, 0)]),
    }

    def __init__(self):
        self.sounds = {}
        self.muted = False
        try:
            pygame.mixer.init(self.RATE, -16, 1, 512)
        except pygame.error:
            return   # no audio device: play silently
        rng = random.Random(3)
        for name, (wave, vol, segments) in self.RECIPES.items():
            self.sounds[name] = pygame.mixer.Sound(buffer=self._synth(wave, vol, segments, rng).tobytes())

    def _synth(self, wave, vol, segments, rng):
        out = array.array("h")
        for freqs, dur, slide, noise in segments:
            n = int(self.RATE * dur)
            phases = [0.0] * len(freqs)
            for i in range(n):
                t = i / n
                v = 0.0
                for k, f in enumerate(freqs):
                    phases[k] += f * (1 + slide * t) / self.RATE
                    p = phases[k] % 1.0
                    if wave == "sine":
                        v += math.sin(math.tau * p)
                    elif wave == "square":
                        v += 1.0 if p < 0.5 else -1.0
                    else:
                        v += 2 * p - 1
                v /= len(freqs)
                if noise:
                    v = v * (1 - noise) + rng.uniform(-1, 1) * noise
                env = min(1.0, i / 150) * (1 - t) ** 1.4
                out.append(int(clamp(v * env * vol, -1, 1) * 32767))
        return out

    def play(self, name):
        if not self.muted and name in self.sounds:
            self.sounds[name].play()


# ---------------------------------------------------------------- art
class Anim:
    """A 4x2 sprite sheet: row 0 idle (frame 2 = blink), row 1 walk."""

    def __init__(self, name, scale=SCALE):
        sheet = pygame.image.load(resource("assets", "sprites", name + ".png")).convert_alpha()
        fw, fh = sheet.get_width() // 4, sheet.get_height() // 2
        self.frames = []
        for flip in (False, True):
            rows = []
            for r in range(2):
                row = []
                for c in range(4):
                    img = pygame.transform.smoothscale_by(sheet.subsurface((c * fw, r * fh, fw, fh)), scale)
                    row.append(pygame.transform.flip(img, True, False) if flip else img)
                rows.append(row)
            self.frames.append(rows)

    def frame(self, moving, t, flip=False, blink=0.2):
        rows = self.frames[flip]
        if moving:
            return rows[1][int(t * 8) % 4]
        if t % 3.6 > 3.6 - blink:
            return rows[0][2]
        return rows[0][int(t * 1.6) % 2]


def load_item(name, size=34):
    img = pygame.image.load(resource("assets", "items", name + ".png")).convert_alpha()
    return pygame.transform.smoothscale(img, (size, size))


# ---------------------------------------------------------------- level furniture
def house(x, base, w, label, roof, wall=(226, 214, 190), h=80):
    return {"kind": "house", "x": x, "y": base, "w": w, "h": h, "label": label, "roof": roof, "wall": wall,
            "rect": pygame.Rect(x, base - 46, w, 46)}


def shop(x, base, w, label, front, h=110):
    return {"kind": "shop", "x": x, "y": base, "w": w, "h": h, "label": label, "front": front,
            "rect": pygame.Rect(x, base - 46, w, 46)}


def hangar(x, base, w, label, h=120):
    return {"kind": "hangar", "x": x, "y": base, "w": w, "h": h, "label": label,
            "rect": pygame.Rect(x, base - 50, w, 50)}


def tree(x, y):
    return {"kind": "tree", "x": x, "y": y, "rect": pygame.Rect(x - 11, y - 12, 22, 14)}


def hedge(x, y, w, h):
    return {"kind": "hedge", "x": x, "y": y + h, "w": w, "h": h, "rect": pygame.Rect(x, y, w, h)}


def lamp(x, y):
    return {"kind": "lamp", "x": x, "y": y, "rect": pygame.Rect(x - 5, y - 8, 10, 10)}


def phonebox(x, y):
    return {"kind": "phonebox", "x": x, "y": y, "rect": pygame.Rect(x - 18, y - 22, 36, 22)}


def crate(x, y):
    return {"kind": "crate", "x": x, "y": y, "rect": pygame.Rect(x - 22, y - 24, 44, 24)}


def fence(x, y, w):
    return {"kind": "fence", "x": x, "y": y, "w": w, "rect": pygame.Rect(x, y - 8, w, 8)}


def pond(x, y, w, h):
    return {"kind": "pond", "x": x, "y": y, "w": w, "h": h, "flat": True, "rect": pygame.Rect(x + 10, y + 8, w - 20, h - 16)}


LEVELS = [
    {
        "name": "Tadfield", "ground": "grass", "time": 100,
        "intro": "Saturday morning in Tadfield. Agnes Nutter's Nice and Accurate Prophecies have blown all over "
                 "the village. Gather the four missing pages and bring them to Jasmine Cottage - before the "
                 "Hellhound finds you.",
        "item": "page", "count": 4, "item_name": "Prophecy page",
        "goal": {"kind": "door", "pos": (620, 238), "label": "Jasmine Cottage"},
        "spawn": [(110, 650), (180, 650)],
        "enemies": [{"kind": "hound", "name": "Hellhound", "pos": (1180, 660), "speed": 105}],
        "obstacles": [
            house(520, 232, 200, "Jasmine Cottage", (110, 76, 58)),
            house(960, 212, 250, "Tadfield Manor", (63, 77, 99), (232, 226, 210)),
            house(70, 452, 180, "Village Hall", (139, 58, 43)),
            house(990, 560, 190, "Post Office", (150, 40, 40), (238, 230, 214)),
            tree(330, 210), tree(430, 620), tree(780, 480), tree(255, 660), tree(1210, 390),
            tree(880, 655), tree(150, 250), tree(1230, 660),
            hedge(320, 330, 22, 150), hedge(800, 300, 170, 22),
            pond(540, 530, 170, 80),
        ],
    },
    {
        "name": "Soho", "ground": "street", "time": 100,
        "intro": "Soho, London. A.Z. Fell & Co. is on fire! Rescue five of Aziraphale's rare books from the street "
                 "and get to the Bentley. Hastur and Ligur are lurking, and they are not happy with Crowley.",
        "item": "book", "count": 5, "item_name": "Rare book",
        "goal": {"kind": "bentley", "pos": (1120, 655), "label": "The Bentley"},
        "spawn": [(600, 660), (670, 660)],
        "enemies": [
            {"kind": "demon", "name": "Hastur", "pos": (150, 320), "speed": 95,
             "path": [(150, 320), (560, 330), (560, 600), (150, 600)]},
            {"kind": "demon", "name": "Ligur", "pos": (1150, 330), "speed": 95,
             "path": [(1150, 330), (800, 560), (1180, 520), (880, 330)]},
        ],
        "obstacles": [
            shop(30, 232, 230, "Soho Cafe", (60, 110, 90)),
            shop(470, 236, 320, "A.Z. Fell & Co.", (40, 64, 50)),
            shop(900, 232, 190, "Records", (110, 50, 80)),
            shop(1110, 232, 160, "Deli", (150, 90, 40)),
            phonebox(380, 450), lamp(250, 520), lamp(720, 400), lamp(1000, 480), lamp(330, 330),
            hedge(560, 500, 170, 22), crate(860, 620), crate(190, 650), hedge(970, 330, 22, 90),
        ],
        "fire": pygame.Rect(490, 112, 280, 20),   # along the bookshop's roofline
    },
    {
        "name": "Tadfield Airbase", "ground": "tarmac", "time": 120,
        "intro": "Tadfield Airbase. Armageddon is about to start. War, Famine and Pollution have dropped their "
                 "regalia - grab the Sword, the Scales and the Crown, then reach Adam so he can call the whole "
                 "thing off. Everyone from Hell is here, and they are faster now.",
        "item": ["sword", "scales", "crown"], "count": 3, "item_name": "Horseman's relic",
        "goal": {"kind": "adam", "pos": (640, 300), "label": "Adam"},
        "spawn": [(110, 660), (180, 660)],
        "enemies": [
            {"kind": "hound", "name": "Hellhound", "pos": (1190, 660), "speed": 110},
            {"kind": "demon", "name": "Hastur", "pos": (300, 300), "speed": 105,
             "path": [(300, 300), (520, 560), (180, 560)]},
            {"kind": "demon", "name": "Ligur", "pos": (1000, 320), "speed": 105,
             "path": [(1000, 320), (760, 560), (1150, 520)]},
        ],
        "obstacles": [
            hangar(60, 236, 320, "Hangar 1"), hangar(900, 236, 320, "Hangar 2"),
            fence(300, 470, 250), fence(730, 470, 250),
            crate(420, 610), crate(870, 630), crate(240, 540), crate(1040, 600), crate(1090, 600),
            tree(540, 200), tree(760, 190),
        ],
    },
]

PLAYER_LINES = {
    "aziraphale": {"pickup": ["Oh, how marvellous!", "Tickety-boo!", "Splendid!", "Oh, well done me."],
                   "hit": ["Oh, fiddlesticks!", "How rude!", "Ow!"],
                   "ability": "A small miracle!", "ability_miss": "Oh dear, nobody there."},
    "crowley": {"pickup": ["Nice.", "Sorted.", "Easy.", "Got it, angel."],
                "hit": ["Ngk!", "Oi!", "Hell's teeth!"],
                "ability": "Get in, angel!", "ability_miss": "Get in, angel!"},
}

CONTROLS_1P = {"up": [pygame.K_w, pygame.K_UP], "down": [pygame.K_s, pygame.K_DOWN],
               "left": [pygame.K_a, pygame.K_LEFT], "right": [pygame.K_d, pygame.K_RIGHT],
               "ability": [pygame.K_SPACE, pygame.K_e, pygame.K_RETURN, pygame.K_RSHIFT]}
CONTROLS_AZI = {"up": [pygame.K_w], "down": [pygame.K_s], "left": [pygame.K_a], "right": [pygame.K_d],
                "ability": [pygame.K_e, pygame.K_SPACE]}
CONTROLS_CROWLEY = {"up": [pygame.K_UP], "down": [pygame.K_DOWN], "left": [pygame.K_LEFT], "right": [pygame.K_RIGHT],
                    "ability": [pygame.K_RETURN, pygame.K_RSHIFT, pygame.K_RCTRL]}


# ---------------------------------------------------------------- characters
class Player:
    def __init__(self, who, pos, controls, anim, car):
        self.who, self.name = who, who.capitalize()
        self.x, self.y = pos
        self.r = 12
        self.controls = controls
        self.anim, self.car = anim, car
        self.stun = self.hurt = self.cd = self.boost = 0.0
        self.t = random.random() * 3
        self.moving = False
        self.flip = False
        self.max_cd = 9.0 if who == "aziraphale" else 10.0

    def held(self, keys, action):
        return any(keys[k] for k in self.controls[action])

    def update(self, dt, keys, game):
        self.t += dt
        self.stun -= dt
        self.hurt -= dt
        self.cd -= dt
        self.boost -= dt
        dx = self.held(keys, "right") - self.held(keys, "left")
        dy = self.held(keys, "down") - self.held(keys, "up")
        if self.stun > 0:
            dx = dy = 0
        self.moving = bool(dx or dy)
        if self.moving:
            n = math.hypot(dx, dy)
            sp = (BOOST_SPEED if self.boost > 0 else PLAYER_SPEED) * dt
            game.move(self, dx / n * sp, dy / n * sp)
            if dx:
                self.flip = dx < 0
            if self.boost > 0 and random.random() < 0.6:
                game.fx.append(Particle("smoke", self.x + (40 if self.flip else -40), self.y - 10))

    def use_ability(self, game):
        if self.cd > 0 or self.stun > 0:
            game.sfx.play("nope")
            return
        self.cd = self.max_cd
        lines = PLAYER_LINES[self.who]
        if self.who == "aziraphale":
            game.sfx.play("miracle")
            game.fx.append(Particle("ring", self.x, self.y - 30, life=0.7))
            for _ in range(24):
                game.fx.append(Particle("sparkle", self.x, self.y - 30))
            hit = [e for e in game.enemies if math.hypot(e.x - self.x, e.y - self.y) < 220]
            for e in hit:
                e.stun = 3.0
            game.say(self, lines["ability"] if hit else lines["ability_miss"], (255, 233, 160))
        else:
            game.sfx.play("bentley")
            self.boost = 3.2
            game.say(self, lines["ability"], (255, 160, 140))

    def draw(self, surf, game):
        if self.hurt > 0 and int(self.t * 12) % 2:
            return
        shadow(surf, self.x, self.y, 26 if self.boost <= 0 else 60)
        if self.boost > 0:
            img = self.car.frame(True, self.t * 2, self.flip)
            surf.blit(img, img.get_rect(midbottom=(self.x, self.y + 8)))
            text(surf, "~ Queen ~", 14, (255, 180, 170), (self.x, self.y - 70))
            return
        img = self.anim.frame(self.moving, self.t, self.flip, 0.6 if self.who == "crowley" else 0.18)
        surf.blit(img, img.get_rect(midbottom=(self.x, self.y + 4)))
        if self.stun > 0:
            stars(surf, self.x, self.y - img.get_height() - 4, self.t)


class Enemy:
    def __init__(self, spec, anim):
        self.kind, self.name = spec["kind"], spec["name"]
        self.x, self.y = spec["pos"]
        self.speed = spec["speed"]
        self.path = spec.get("path", [])
        self.pi = 1 % max(1, len(self.path))
        self.anim = anim
        self.r = 18 if self.kind == "hound" else 13
        self.stun = self.ghost = self.stuck = 0.0
        self.t = random.random() * 3
        self.moving = False
        self.flip = False
        self.chasing = False

    def update(self, dt, game):
        self.t += dt
        self.stun -= dt
        self.ghost -= dt
        self.moving = False
        if self.stun > 0 or not game.players:
            return
        target = min(game.players, key=lambda p: math.hypot(p.x - self.x, p.y - self.y))
        d = math.hypot(target.x - self.x, target.y - self.y)
        self.chasing = self.kind == "hound" or d < 210 or (self.chasing and d < 330)
        if target.boost > 0 and self.kind != "hound":
            self.chasing = False   # demons won't tangle with the Bentley
        if self.chasing:
            tx, ty = target.x, target.y
        else:
            tx, ty = self.path[self.pi] if self.path else (self.x, self.y)
            if math.hypot(tx - self.x, ty - self.y) < 10:
                self.pi = (self.pi + 1) % len(self.path)
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 1:
            return
        want = min(dist, self.speed * game.rage() * dt)
        ox, oy = self.x, self.y
        game.move(self, dx / dist * want, dy / dist * want, ghost=self.ghost > 0)
        moved = math.hypot(self.x - ox, self.y - oy)
        self.moving = moved > 0.1
        if abs(dx) > 2:
            self.flip = dx < 0
        self.stuck = self.stuck + dt if moved < want * 0.3 else max(0.0, self.stuck - dt)
        if self.stuck > 0.6:   # cornered by a wall: take a demonic shortcut through it
            self.ghost, self.stuck = 1.2, 0.0

    def draw(self, surf, game):
        img = self.anim.frame(self.moving, self.t, self.flip, 0.4 if self.kind == "hound" else 0.2)
        if self.ghost > 0:
            img = img.copy()
            img.set_alpha(130)
        shadow(surf, self.x, self.y, 44 if self.kind == "hound" else 26)
        surf.blit(img, img.get_rect(midbottom=(self.x, self.y + 4)))
        text(surf, self.name, 13, (255, 160, 160), (self.x, self.y + 16))
        if self.stun > 0:
            stars(surf, self.x, self.y - img.get_height() - 2, self.t)


class Particle:
    def __init__(self, kind, x, y, life=None):
        self.kind, self.x, self.y = kind, x, y
        a = random.uniform(0, math.tau)
        sp = {"sparkle": random.uniform(80, 260), "fire": 0, "smoke": 0}.get(kind, 0)
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp
        if kind == "fire":
            self.vx, self.vy = random.uniform(-10, 10), random.uniform(-70, -40)
        elif kind == "smoke":
            self.vx, self.vy = random.uniform(-10, 10), random.uniform(-40, -20)
        self.life = self.max_life = life or {"sparkle": 0.8, "fire": 0.7, "smoke": 0.9, "ring": 0.6}[kind]
        self.r = 10

    def update(self, dt):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.kind == "ring":
            self.r += (220 - self.r) * dt * 7
        elif self.kind == "sparkle":
            self.vx *= 0.92
            self.vy *= 0.92

    def draw(self, surf):
        k = clamp(self.life / self.max_life, 0, 1)
        if self.kind == "ring":
            pygame.draw.circle(surf, (255, 230, 140), (self.x, self.y), self.r, max(1, int(5 * k)))
        elif self.kind == "sparkle":
            pygame.draw.circle(surf, (255, 240, 170), (self.x, self.y), 1 + 3 * k)
        elif self.kind == "fire":
            col = (255, int(110 + 110 * k), 40) if k > 0.5 else (220, int(70 * k * 2), 30)
            pygame.draw.circle(surf, col, (self.x, self.y), 2 + 6 * k)
        elif self.kind == "smoke":
            s = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(s, (110, 110, 110, int(120 * k)), (20, 20), 6 + 12 * (1 - k))
            surf.blit(s, (self.x - 20, self.y - 20))


def shadow(surf, x, y, w):
    s = pygame.Surface((w * 2, w), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 60), s.get_rect())
    surf.blit(s, s.get_rect(center=(x, y)))


def stars(surf, x, y, t):
    for i in range(3):
        a = t * 5 + i * 2.1
        text(surf, "*", 22, (255, 224, 102), (x + math.cos(a) * 16, y + math.sin(a) * 5), shadow=False, bold=True)


# ---------------------------------------------------------------- drawing the world
def draw_ground(kind, level):
    g = pygame.Surface((W, H))
    rng = random.Random(len(level["name"]))
    if kind == "grass":
        g.fill((88, 134, 66))
        for _ in range(2600):
            g.fill(rng.choice([(78, 122, 58), (100, 148, 76)]), (rng.randrange(W), rng.randrange(H), 2, 4))
        for _ in range(140):
            pygame.draw.circle(g, rng.choice([(243, 227, 124), (247, 247, 247), (215, 127, 179)]),
                               (rng.randrange(W), rng.randrange(H)), 2)
        pts = [(x, 300 + 30 * math.sin(x / 210)) for x in range(-20, W + 40, 20)]
        pygame.draw.lines(g, (160, 132, 92), False, pts, 34)
        pts = [(560 + 40 * math.sin(y / 120), y) for y in range(300, H + 20, 20)]
        pygame.draw.lines(g, (160, 132, 92), False, pts, 30)
    elif kind == "street":
        g.fill((156, 150, 142))
        for x in range(0, W, 48):
            pygame.draw.line(g, (136, 130, 124), (x, 0), (x, H))
        for y in range(0, H, 48):
            pygame.draw.line(g, (136, 130, 124), (0, y), (W, y))
        road = pygame.Rect(0, 372, W, 96)
        g.fill((72, 72, 78), road)
        for x in range(0, W, 80):
            g.fill((230, 230, 220), (x + 10, road.centery - 3, 44, 6))
        g.fill((120, 116, 110), (0, road.top - 6, W, 6))
        g.fill((120, 116, 110), (0, road.bottom, W, 6))
    else:  # tarmac
        g.fill((112, 114, 110))
        for _ in range(2000):
            c = rng.randint(100, 124)
            g.fill((c, c + 2, c - 2), (rng.randrange(W), rng.randrange(H), 2, 2))
        g.fill((88, 134, 66), (0, HUD_H, W, 40))
        for x in range(0, W, 120):
            g.fill((236, 236, 226), (x + 20, 640, 70, 8))
        pygame.draw.line(g, (230, 196, 60), (0, 420), (W, 420), 4)
    for o in level["obstacles"]:
        if o["kind"] == "pond":
            r = pygame.Rect(o["x"], o["y"], o["w"], o["h"])
            pygame.draw.ellipse(g, (64, 104, 60), r.inflate(10, 10))
            pygame.draw.ellipse(g, (47, 94, 138), r)
            pygame.draw.ellipse(g, (90, 140, 180), r.inflate(-50, -36), 2)
    return g


def draw_obstacle(surf, o, t):
    k = o["kind"]
    if k in ("house", "shop", "hangar"):
        x, base, w, h = o["x"], o["y"], o["w"], o["h"]
        wall = pygame.Rect(x, base - h, w, h)
        shadow_r = wall.move(8, 6)
        s = pygame.Surface(shadow_r.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 50))
        surf.blit(s, shadow_r)
        if k == "house":
            pygame.draw.rect(surf, o["wall"], wall)
            pygame.draw.rect(surf, (60, 40, 30), wall, 2)
            for wx in range(x + 22, x + w - 30, 56):
                win = pygame.Rect(wx, base - h + 18, 28, 24)
                pygame.draw.rect(surf, (150, 190, 214), win)
                pygame.draw.rect(surf, (80, 60, 46), win, 2)
                pygame.draw.line(surf, (80, 60, 46), win.midtop, win.midbottom, 2)
            door = pygame.Rect(0, 0, 26, 40)
            door.midbottom = (x + w // 2, base)
            pygame.draw.rect(surf, (96, 60, 40), door)
            pygame.draw.rect(surf, (50, 32, 22), door, 2)
            roof = [(x - 10, base - h), (x + w + 10, base - h), (x + w - 18, base - h - 50), (x + 18, base - h - 50)]
            pygame.draw.polygon(surf, o["roof"], roof)
            pygame.draw.polygon(surf, (40, 26, 20), roof, 2)
            text(surf, o["label"], 15, (250, 244, 228), (x + w // 2, base - h - 24))
        elif k == "shop":
            pygame.draw.rect(surf, (196, 180, 160), wall)
            pygame.draw.rect(surf, (60, 46, 40), wall, 2)
            front = pygame.Rect(x + 10, base - 70, w - 20, 70)
            pygame.draw.rect(surf, o["front"], front)
            pygame.draw.rect(surf, (30, 24, 20), front, 2)
            glass = front.inflate(-24, -26).move(0, 2)
            pygame.draw.rect(surf, (170, 200, 214), glass)
            door = pygame.Rect(0, 0, 24, 46)
            door.midbottom = front.midbottom
            pygame.draw.rect(surf, o["front"], door)
            pygame.draw.rect(surf, (30, 24, 20), door, 2)
            sign = pygame.Rect(x + 16, base - h + 6, w - 32, 26)
            pygame.draw.rect(surf, (30, 30, 34), sign)
            pygame.draw.rect(surf, (200, 170, 90), sign, 2)
            text(surf, o["label"], 15, (232, 206, 120), sign.center, shadow=False)
            for i in range(0, w - 20, 20):   # striped awning
                col = o["front"] if (i // 20) % 2 else (236, 230, 214)
                pygame.draw.rect(surf, col, (x + 10 + i, base - 82, 20, 12))
        else:
            pygame.draw.rect(surf, (150, 156, 150), wall)
            pygame.draw.ellipse(surf, (126, 132, 128), pygame.Rect(x, base - h - 60, w, 120))
            pygame.draw.rect(surf, (150, 156, 150), wall)
            pygame.draw.rect(surf, (60, 64, 60), wall, 2)
            for i in range(x + 20, x + w, 30):
                pygame.draw.line(surf, (128, 134, 128), (i, base - h), (i, base), 2)
            door = pygame.Rect(0, 0, w // 2, h - 30)
            door.midbottom = (x + w // 2, base)
            pygame.draw.rect(surf, (70, 74, 70), door)
            text(surf, o["label"], 18, (250, 250, 240), (x + w // 2, base - h - 20))
    elif k == "tree":
        shadow(surf, o["x"] + 6, o["y"], 34)
        pygame.draw.rect(surf, (96, 66, 40), (o["x"] - 7, o["y"] - 40, 14, 40))
        for dx, dy, r, c in ((0, -66, 34, (46, 93, 31)), (-16, -56, 22, (52, 104, 36)), (14, -80, 20, (63, 122, 43))):
            pygame.draw.circle(surf, c, (o["x"] + dx, o["y"] + dy), r)
    elif k == "hedge":
        r = o["rect"]
        body = pygame.Rect(r.x, r.y - 22, r.w, r.h + 22)
        pygame.draw.rect(surf, (45, 85, 32), body, border_radius=8)
        pygame.draw.rect(surf, (62, 112, 44), (body.x, body.y, body.w, 16), border_radius=8)
    elif k == "lamp":
        pygame.draw.line(surf, (40, 40, 44), (o["x"], o["y"]), (o["x"], o["y"] - 110), 5)
        pygame.draw.rect(surf, (40, 40, 44), (o["x"] - 9, o["y"] - 126, 18, 18))
        pygame.draw.rect(surf, (255, 236, 160), (o["x"] - 6, o["y"] - 123, 12, 12))
    elif k == "phonebox":
        box = pygame.Rect(o["x"] - 18, o["y"] - 84, 36, 84)
        pygame.draw.rect(surf, (196, 30, 32), box, border_radius=4)
        for yy in range(box.y + 18, box.bottom - 10, 14):
            pygame.draw.rect(surf, (200, 220, 230), (box.x + 7, yy, 22, 10))
        pygame.draw.rect(surf, (90, 10, 12), box, 2, border_radius=4)
    elif k == "crate":
        top = pygame.Rect(o["x"] - 22, o["y"] - 46, 44, 14)
        side = pygame.Rect(o["x"] - 22, o["y"] - 32, 44, 32)
        pygame.draw.rect(surf, (196, 150, 90), top)
        pygame.draw.rect(surf, (160, 116, 66), side)
        pygame.draw.line(surf, (110, 76, 40), side.topleft, side.bottomright, 3)
        pygame.draw.rect(surf, (100, 70, 40), top.union(side), 2)
    elif k == "fence":
        for px in range(o["x"], o["x"] + o["w"] + 1, 25):
            pygame.draw.rect(surf, (210, 210, 214), (px - 3, o["y"] - 46, 6, 46))
        for yy in (o["y"] - 40, o["y"] - 22):
            pygame.draw.line(surf, (190, 190, 196), (o["x"], yy), (o["x"] + o["w"], yy), 3)


# ---------------------------------------------------------------- the game
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        try:   # SCALED lets the window be resized and go fullscreen without stretching the art
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))
        self.sfx = Sfx()
        self.anims = {n: Anim(n) for n in ("aziraphale", "crowley", "adam", "hastur", "ligur", "dog")}
        self.anims["hellhound"] = Anim("hellhound", 0.8)
        self.anims["bentley"] = Anim("bentley", 0.95)
        self.items = {n: load_item(n) for n in ("page", "book", "sword", "scales", "crown", "crepe")}
        self.small_items = {n: load_item(n, 26) for n in self.items}
        pygame.display.set_icon(load_item("page", 32))
        self.grounds = {i: draw_ground(lv["ground"], lv) for i, lv in enumerate(LEVELS)}
        self.save = load_save()
        self.timer = pygame.time.Clock()
        self.pressed = pygame.key.get_pressed
        self.running = True
        self.t = 0.0
        self.mode = "solo_azi"
        self.menu_rects = []
        self.to_title()

    # ---------------- states
    def to_title(self):
        self.state = "title"
        self.menu = [("Play as Aziraphale", lambda: self.new_game("solo_azi")),
                     ("Play as Crowley", lambda: self.new_game("solo_crowley")),
                     ("Two players (co-op)", lambda: self.new_game("coop")),
                     ("How to play", self.to_howto),
                     ("Quit", self.quit)]
        self.menu_i = 0

    def to_howto(self):
        self.state = "howto"
        self.menu = [("Back", self.to_title)]
        self.menu_i = 0

    def quit(self):
        self.running = False

    def new_game(self, mode):
        self.mode = mode
        self.score = 0
        self.level_i = 0
        self.to_intro()

    def to_intro(self):
        self.state = "intro"
        self.menu = [("Begin", self.start_level)]
        self.menu_i = 0

    def start_level(self):
        lv = self.level = LEVELS[self.level_i]
        self.obstacles = lv["obstacles"]
        self.solid = [o["rect"] for o in self.obstacles if o.get("rect")]
        sp = lv["spawn"]
        if self.mode == "coop":
            self.players = [Player("aziraphale", sp[0], CONTROLS_AZI, self.anims["aziraphale"], self.anims["bentley"]),
                            Player("crowley", sp[1], CONTROLS_CROWLEY, self.anims["crowley"], self.anims["bentley"])]
        else:
            who = "aziraphale" if self.mode == "solo_azi" else "crowley"
            self.players = [Player(who, sp[0], CONTROLS_1P, self.anims[who], self.anims["bentley"])]
        self.enemies = [Enemy(e, self.anims["hellhound" if e["kind"] == "hound" else e["name"].lower()])
                        for e in lv["enemies"]]
        kinds = lv["item"] if isinstance(lv["item"], list) else [lv["item"]] * lv["count"]
        self.pickups = []
        for k in kinds:
            x, y = self.free_spot()
            self.pickups.append({"kind": k, "x": x, "y": y, "got": False})
        self.crepes = []
        self.crepe_timer = 9.0
        self.fx, self.texts = [], []
        self.clock_left = lv["time"]
        self.hits = 0
        self.shake = 0.0
        self.nag = 0.0
        self.state = "play"
        self.menu = []

    def free_spot(self):
        avoid = [(p.x, p.y) for p in self.players] + [self.level["goal"]["pos"]]
        avoid += [(c["x"], c["y"]) for c in getattr(self, "pickups", []) + getattr(self, "crepes", [])]
        for _ in range(400):
            x, y = random.uniform(60, W - 60), random.uniform(TOP_Y + 10, H - 40)
            if self.blocked(x, y, 34) or self.hidden(x, y):
                continue
            if all(math.hypot(x - ax, y - ay) > 130 for ax, ay in avoid):
                return x, y
        return W / 2, H - 80

    def hidden(self, x, y):
        """True if a building's wall would hide something standing at (x, y)."""
        return any(o["kind"] in ("house", "shop", "hangar") and o["x"] - 30 < x < o["x"] + o["w"] + 30
                   and y < o["y"] + 10 for o in self.obstacles)

    def collected(self):
        return sum(p["got"] for p in self.pickups)

    def rage(self):
        return 1 + (1 - self.clock_left / self.level["time"]) * 0.45

    def level_clear(self):
        self.sfx.play("clear")
        secs = max(0, int(self.clock_left))
        self.breakdown = [(f"{self.level['item_name']}s x{len(self.pickups)}", len(self.pickups) * 100),
                          (f"Time left {secs}s x10", secs * 10),
                          ("Not a scratch!" if self.hits == 0 else f"Hits taken: {self.hits}", 500 if self.hits == 0 else 0)]
        self.score += sum(v for _, v in self.breakdown)
        if self.level_i == len(LEVELS) - 1:
            self.finish_game(won=True)
        else:
            self.state = "clear"
            self.menu = [("Next level", self.next_level)]
            self.menu_i = 0

    def next_level(self):
        self.level_i += 1
        self.to_intro()

    def game_over(self):
        self.sfx.play("lose")
        self.state = "over"
        self.menu = [("Try this level again", self.start_level), ("Back to title", self.to_title)]
        self.menu_i = 0
        self.record_best()

    def finish_game(self, won):
        self.state = "victory"
        self.menu = [("Back to title", self.to_title)]
        self.menu_i = 0
        self.record_best()

    def record_best(self):
        self.new_best = self.score > self.save.get("best", 0)
        if self.new_best:
            self.save["best"] = self.score
            write_save(self.save)

    def pause(self):
        self.state = "paused"
        self.menu = [("Resume", self.resume), ("Restart level", self.start_level), ("Quit to title", self.to_title)]
        self.menu_i = 0

    def resume(self):
        self.state = "play"
        self.menu = []

    # ---------------- helpers used by entities
    def blocked(self, x, y, r):
        return any(circle_hits_rect(x, y, r, rect) for rect in self.solid)

    def move(self, e, dx, dy, ghost=False):
        nx = clamp(e.x + dx, e.r + 4, W - e.r - 4)
        if ghost or not self.blocked(nx, e.y, e.r):
            e.x = nx
        ny = clamp(e.y + dy, TOP_Y, H - e.r - 4)
        if ghost or not self.blocked(e.x, ny, e.r):
            e.y = ny

    def say(self, who, msg, color=(255, 255, 255)):
        self.texts.append({"x": who.x, "y": who.y - 100, "msg": msg, "color": color, "life": 1.8})

    # ---------------- loop
    def run(self):
        autoshot = os.environ.get("GOOD_OMENS_AUTOSHOT")   # build check: save a screenshot, then quit
        frame = 0
        while self.running:
            dt = min(self.timer.tick(FPS) / 1000, 0.05)
            for e in pygame.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
            frame += 1
            if autoshot and frame == 120:
                pygame.image.save(self.screen, autoshot)
                self.running = False
        pygame.quit()

    def handle(self, e):
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif e.key == pygame.K_m:
                self.sfx.muted = not self.sfx.muted
            elif self.state == "play":
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    self.pause()
                for p in self.players:
                    if e.key in p.controls["ability"]:
                        p.use_ability(self)
            elif self.menu:
                if e.key in (pygame.K_UP, pygame.K_w):
                    self.menu_i = (self.menu_i - 1) % len(self.menu)
                    self.sfx.play("select")
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    self.menu_i = (self.menu_i + 1) % len(self.menu)
                    self.sfx.play("select")
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    self.menu[self.menu_i][1]()
                elif e.key == pygame.K_ESCAPE:
                    if self.state == "paused":
                        self.resume()
                    elif self.state != "title":
                        self.to_title()
        elif e.type == pygame.MOUSEMOTION and self.menu:
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(e.pos):
                    self.menu_i = i
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.menu:
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(e.pos):
                    self.menu[i][1]()
                    break

    def update(self, dt):
        self.t += dt
        if self.state != "play":
            return
        lv = self.level
        before = self.clock_left
        self.clock_left -= dt
        if self.clock_left <= 10 and int(before) != int(self.clock_left):
            self.sfx.play("tick")
        if self.clock_left <= 0:
            self.clock_left = 0
            self.game_over()
            return
        self.shake = max(0.0, self.shake - dt * 20)
        self.nag -= dt

        keys = self.pressed()
        for p in self.players:
            p.update(dt, keys, self)
        for e in self.enemies:
            e.update(dt, self)
            if e.stun > 0:
                continue
            for p in self.players:
                if p.hurt > 0 or p.boost > 0 or math.hypot(p.x - e.x, p.y - e.y) > p.r + e.r + 8:
                    continue
                p.stun, p.hurt = 1.2, 2.5
                self.clock_left -= HIT_PENALTY
                self.hits += 1
                self.shake = 8
                self.sfx.play("hit")
                self.say(p, f"-{HIT_PENALTY}s  " + random.choice(PLAYER_LINES[p.who]["hit"]), (255, 120, 110))
                ang = math.atan2(p.y - e.y, p.x - e.x)
                for _ in range(10):
                    self.move(p, math.cos(ang) * 5, math.sin(ang) * 5)

        for p in self.players:
            for it in self.pickups:
                if not it["got"] and math.hypot(p.x - it["x"], p.y - it["y"]) < 34:
                    it["got"] = True
                    self.sfx.play("pickup")
                    self.say(p, random.choice(PLAYER_LINES[p.who]["pickup"]), (255, 220, 120))
                    for _ in range(14):
                        self.fx.append(Particle("sparkle", it["x"], it["y"] - 10))
                    if self.collected() == len(self.pickups):
                        self.texts.append({"x": lv["goal"]["pos"][0], "y": lv["goal"]["pos"][1] - 120,
                                           "msg": f"Now get to {lv['goal']['label']}!", "color": (160, 220, 255), "life": 3})
            for c in self.crepes:
                if not c["got"] and math.hypot(p.x - c["x"], p.y - c["y"]) < 34:
                    c["got"] = True
                    self.clock_left += CREPE_BONUS
                    self.sfx.play("crepe")
                    self.say(p, f"+{CREPE_BONUS}s  Crepes!", (255, 236, 200))
            gx, gy = lv["goal"]["pos"]
            if math.hypot(p.x - gx, p.y - gy) < 46:
                if self.collected() == len(self.pickups):
                    self.level_clear()
                    return
                if self.nag <= 0:
                    self.sfx.play("nope")
                    left = len(self.pickups) - self.collected()
                    self.texts.append({"x": gx, "y": gy - 110, "msg": f"Not yet - {left} still to find",
                                       "color": (255, 170, 160), "life": 1.6})
                    self.nag = 2.0
        self.crepes = [c for c in self.crepes if not c["got"]]
        self.crepe_timer -= dt
        if self.crepe_timer <= 0:
            self.crepe_timer = 12.0
            if len(self.crepes) < 2:
                x, y = self.free_spot()
                self.crepes.append({"x": x, "y": y, "got": False})

        if lv.get("fire"):
            fr = lv["fire"]
            if random.random() < 0.7:
                self.fx.append(Particle("fire", random.uniform(fr.left, fr.right), random.uniform(fr.top, fr.bottom)))
            if random.random() < 0.15:
                self.fx.append(Particle("smoke", random.uniform(fr.left, fr.right), fr.top - 10))
        for f in self.fx:
            f.update(dt)
        self.fx = [f for f in self.fx if f.life > 0]
        for tx in self.texts:
            tx["life"] -= dt
            tx["y"] -= 26 * dt
        self.texts = [tx for tx in self.texts if tx["life"] > 0]

    # ---------------- drawing
    def draw(self):
        s = self.screen
        if self.state in ("play", "paused", "over", "clear", "victory"):
            self.draw_world(s)
        else:
            self.draw_backdrop(s)
        self.menu_rects = []
        getattr(self, "draw_" + self.state)(s)

    def draw_backdrop(self, s):
        lv = LEVELS[0 if self.state != "intro" else self.level_i]
        s.blit(self.grounds[LEVELS.index(lv)], (0, 0))
        for o in sorted(lv["obstacles"], key=lambda o: o["y"]):
            if not o.get("flat"):
                draw_obstacle(s, o, self.t)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((14, 10, 8, 170))
        s.blit(dim, (0, 0))

    def draw_world(self, s):
        lv = self.level
        world = pygame.Surface((W, H))
        world.blit(self.grounds[self.level_i], (0, 0))
        drawables = [(o["y"], lambda o=o: draw_obstacle(world, o, self.t)) for o in self.obstacles if not o.get("flat")]
        for it in self.pickups:
            if not it["got"]:
                drawables.append((it["y"], lambda it=it: self.draw_pickup(world, self.items[it["kind"]], it)))
        for c in self.crepes:
            drawables.append((c["y"], lambda c=c: self.draw_pickup(world, self.items["crepe"], c)))
        drawables.append((lv["goal"]["pos"][1], lambda: self.draw_goal(world)))
        for e in self.players + self.enemies:
            drawables.append((e.y, lambda e=e: e.draw(world, self)))
        for _, fn in sorted(drawables, key=lambda d: d[0]):
            fn()
        for p in self.players:
            text(world, p.name, 13, (255, 160, 140) if p.who == "crowley" else (255, 244, 200), (p.x, p.y + 16))
        for f in self.fx:
            f.draw(world)
        for tx in self.texts:
            text(world, tx["msg"], 17, tx["color"], (tx["x"], tx["y"]), bold=True)
        off = (random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake)) if self.shake else (0, 0)
        s.fill((0, 0, 0))
        s.blit(world, off)
        self.draw_hud(s)

    def draw_pickup(self, surf, img, it):
        bob = math.sin(self.t * 3 + it["x"]) * 4
        glow = pygame.Surface((70, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 230, 120, 70), glow.get_rect())
        surf.blit(glow, glow.get_rect(center=(it["x"], it["y"])))
        surf.blit(img, img.get_rect(midbottom=(it["x"], it["y"] - 6 + bob)))

    def draw_goal(self, surf):
        g = self.level["goal"]
        x, y = g["pos"]
        ready = self.collected() == len(self.pickups)
        if g["kind"] == "door":
            glow = pygame.Surface((120, 50), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 230, 140, 140 if ready else 50), glow.get_rect())
            surf.blit(glow, glow.get_rect(center=(x, y)))
        elif g["kind"] == "bentley":
            img = self.anims["bentley"].frame(False, 0)
            shadow(surf, x, y, 70)
            surf.blit(img, img.get_rect(midbottom=(x, y + 6)))
        else:
            aura = pygame.Surface((160, 70), pygame.SRCALPHA)
            col = (255, 230, 120, 120) if ready else (255, 50, 30, 90 + int(40 * math.sin(self.t * 3)))
            pygame.draw.ellipse(aura, col, aura.get_rect())
            surf.blit(aura, aura.get_rect(center=(x, y)))
            adam = self.anims["adam"].frame(False, self.t)
            shadow(surf, x, y, 22)
            surf.blit(adam, adam.get_rect(midbottom=(x, y + 4)))
            dog = self.anims["dog"].frame(False, self.t + 1)
            surf.blit(dog, dog.get_rect(midbottom=(x + 44, y + 4)))
            text(surf, "Adam (and Dog)", 13, (200, 230, 255), (x, y + 16))
        if ready:
            bob = abs(math.sin(self.t * 4)) * 12
            ay = y - (110 if g["kind"] != "door" else 70) - bob
            pygame.draw.polygon(surf, (255, 220, 90), [(x - 14, ay - 20), (x + 14, ay - 20), (x, ay)])
            pygame.draw.polygon(surf, (90, 60, 20), [(x - 14, ay - 20), (x + 14, ay - 20), (x, ay)], 2)

    def draw_hud(self, s):
        bar = pygame.Surface((W, HUD_H), pygame.SRCALPHA)
        bar.fill((20, 15, 12, 225))
        s.blit(bar, (0, 0))
        text(s, f"Level {self.level_i + 1}: {self.level['name']}", 18, (232, 222, 200), (16, HUD_H // 2), "midleft")
        secs = max(0, int(math.ceil(self.clock_left)))
        urgent = self.clock_left < 20 and int(self.t * 3) % 2
        text(s, f"Armageddon in {secs // 60}:{secs % 60:02d}", 24, (255, 90, 74) if urgent else (250, 240, 220),
             (430, HUD_H // 2), bold=True)
        x = 590
        for it in self.pickups:
            img = self.small_items[it["kind"]].copy()
            if not it["got"]:
                img.set_alpha(70)
            s.blit(img, img.get_rect(midleft=(x, HUD_H // 2)))
            x += 32
        x = max(x + 20, 800)
        for p in self.players:
            label = "Miracle" if p.who == "aziraphale" else "Bentley"
            text(s, f"{p.name}: {label}", 13, (220, 214, 200), (x, 18), "midleft", shadow=False)
            frac = 1 if p.cd <= 0 else 1 - p.cd / p.max_cd
            pygame.draw.rect(s, (60, 56, 52), (x, 30, 140, 9), border_radius=4)
            col = ((242, 211, 107) if p.who == "aziraphale" else (224, 83, 63)) if frac >= 1 else (130, 126, 120)
            pygame.draw.rect(s, col, (x, 30, int(140 * frac), 9), border_radius=4)
            x += 165
        text(s, f"Score {self.score}", 16, (232, 222, 200), (W - 14, HUD_H // 2), "midright")

    def panel(self, s, rect):
        p = pygame.Surface(rect.size, pygame.SRCALPHA)
        p.fill((30, 22, 18, 235))
        s.blit(p, rect)
        pygame.draw.rect(s, (200, 170, 100), rect, 2, border_radius=6)

    def draw_menu(self, s, top):
        for i, (label, _) in enumerate(self.menu):
            sel = i == self.menu_i
            r = text(s, ("> " + label + " <") if sel else label, 24, (255, 220, 110) if sel else (225, 215, 195),
                     (W // 2, top + i * 44), bold=sel)
            self.menu_rects.append(r.inflate(40, 10))

    def draw_title(self, s):
        text(s, "Good Omens", 64, (255, 215, 110), (W // 2, 110), bold=True)
        text(s, "The Ineffable Plan", 32, (235, 225, 205), (W // 2, 170))
        lineup = [("aziraphale", 0), ("crowley", 0), ("adam", 0), ("hastur", 0), ("ligur", 0)]
        for i, (n, _) in enumerate(lineup):
            img = self.anims[n].frame(False, self.t + i * 0.7)
            s.blit(img, img.get_rect(midbottom=(W // 2 - 260 + i * 130, 650)))
        hound = self.anims["hellhound"].frame(False, self.t)
        s.blit(hound, hound.get_rect(midbottom=(W // 2 + 410, 650)))
        dog = self.anims["dog"].frame(False, self.t)
        s.blit(dog, dog.get_rect(midbottom=(W // 2 - 10, 650)))
        self.draw_menu(s, 250)
        best = self.save.get("best", 0)
        foot = f"Best score: {best}    " if best else ""
        text(s, foot + "Arrows/WASD + Enter to choose  |  M: sound on/off  |  F11: fullscreen", 15,
             (190, 180, 160), (W // 2, H - 22))

    def draw_howto(self, s):
        rect = pygame.Rect(140, 60, W - 280, H - 120)
        self.panel(s, rect)
        text(s, "How to play", 34, (255, 215, 110), (W // 2, 100), bold=True)
        lines = [
            "The Antichrist is eleven, lives in Tadfield, and is about to end the world by accident.",
            "An angel and a demon would rather it didn't. Three levels stand in the way.",
            "",
            "Collect every item on a level, then reach the glowing goal before the clock hits zero.",
            f"Hastur, Ligur and the Hellhound cost you {HIT_PENALTY} seconds per hit. Crepes give you +{CREPE_BONUS}s.",
            "",
            "ONE PLAYER:  move with WASD or arrows,  ability with Space",
            "TWO PLAYERS:  Aziraphale  WASD + E      Crowley  arrows + Enter",
            "",
            "Aziraphale's miracle stuns every demon nearby for 3 seconds.",
            "Crowley's Bentley makes him fast and untouchable for 3 seconds.",
            "",
            "Esc / P: pause      M: sound      F11: fullscreen",
        ]
        for i, line in enumerate(lines):
            text(s, line, 18, (232, 224, 206), (W // 2, 150 + i * 30), shadow=False)
        self.draw_menu(s, H - 100)

    def draw_intro(self, s):
        lv = LEVELS[self.level_i]
        rect = pygame.Rect(200, 140, W - 400, 400)
        self.panel(s, rect)
        text(s, f"Level {self.level_i + 1}", 22, (200, 180, 140), (W // 2, 180))
        text(s, lv["name"], 42, (255, 215, 110), (W // 2, 225), bold=True)
        for i, line in enumerate(wrap(lv["intro"], 20, rect.w - 80)):
            text(s, line, 20, (236, 228, 210), (W // 2, 285 + i * 30), shadow=False)
        kinds = lv["item"] if isinstance(lv["item"], list) else [lv["item"]] * lv["count"]
        for i, k in enumerate(kinds):
            img = self.items[k]
            s.blit(img, img.get_rect(center=(W // 2 - (len(kinds) - 1) * 24 + i * 48, 470)))
        self.draw_menu(s, 600)

    def draw_play(self, s):
        pass

    def overlay(self, s, alpha=150):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((10, 8, 6, alpha))
        s.blit(dim, (0, 0))

    def draw_paused(self, s):
        self.overlay(s)
        text(s, "Paused", 48, (255, 215, 110), (W // 2, 220), bold=True)
        self.draw_menu(s, 320)

    def draw_clear(self, s):
        self.overlay(s, 170)
        text(s, f"{self.level['name']} - cleared!", 44, (160, 225, 255), (W // 2, 180), bold=True)
        for i, (label, pts) in enumerate(self.breakdown):
            text(s, label, 22, (236, 228, 210), (W // 2 - 40, 260 + i * 38), "midright")
            text(s, f"+{pts}", 22, (255, 220, 120), (W // 2 + 40, 260 + i * 38), "midleft")
        text(s, f"Score: {self.score}", 30, (255, 236, 200), (W // 2, 400), bold=True)
        self.draw_menu(s, 480)

    def draw_over(self, s):
        self.overlay(s, 190)
        text(s, "It All Ends", 56, (255, 100, 84), (W // 2, 200), bold=True)
        text(s, "Armageddon. Should have gone to Alpha Centauri.", 24, (236, 228, 210), (W // 2, 270))
        text(s, f"Score: {self.score}" + ("   - a new best!" if self.new_best else ""), 22, (255, 220, 120), (W // 2, 320))
        self.draw_menu(s, 400)

    def draw_victory(self, s):
        self.overlay(s, 235)
        text(s, "The World Is Saved", 56, (160, 225, 255), (W // 2, 170), bold=True)
        text(s, "Adam calls it off. Heaven and Hell are furious. The world goes on.", 22, (236, 228, 210), (W // 2, 240))
        text(s, "Lunch at the Ritz?", 26, (255, 236, 200), (W // 2, 285))
        text(s, f"Final score: {self.score}" + ("   - a new best!" if self.new_best else ""), 28, (255, 220, 120),
             (W // 2, 350), bold=True)
        for i, n in enumerate(("aziraphale", "crowley")):
            img = self.anims[n].frame(False, self.t + i)
            s.blit(img, img.get_rect(midbottom=(W // 2 - 60 + i * 120, 560)))
        self.draw_menu(s, 620)


def main():
    Game().run()


if __name__ == "__main__":
    main()
