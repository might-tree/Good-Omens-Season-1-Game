"""Draw the Good Omens cast as cartoon sprite sheets (PNG) with pygame.

The designs follow the characters' look in the Amazon / BBC series.

Run:     python generate_sprites.py
Output:  assets/sprites/<name>.png   sheet of 4 columns x 2 rows of equal frames
                                     row 0 = idle, row 1 = walk (people face the camera,
                                     animals and the Bentley face right)
         assets/items/<name>.png     pickup icons
         assets/sprites/cast_preview.png   enlarged line-up for checking the art
"""
import math
import os

import pygame

UNIT_W, UNIT_H = 64, 96   # design grid every person is drawn on
OUT_SCALE = 1.5           # design units -> output pixels
SUPER = 4                 # supersampling factor, for anti-aliased edges
FRAME_W, FRAME_H = round(UNIT_W * OUT_SCALE), round(UNIT_H * OUT_SCALE)
OUTLINE = (34, 24, 22)
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
OUT_DIR = os.path.join(ASSETS, "sprites")
ITEM_DIR = os.path.join(ASSETS, "items")


def bezier(p0, p1, p2, p3, n=14):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return pts


def mirror(pts, cx, side):
    """Shapes are designed for side=+1 (screen right); flip them for side=-1."""
    return [(cx + side * (x - cx), y) for x, y in pts]


def shift(pts, dy):
    return [(x, y + dy) for x, y in pts]


class Pen:
    """Draws in design units onto a supersampled surface."""

    def __init__(self, units=(UNIT_W, UNIT_H)):
        self.k = OUT_SCALE * SUPER
        self.size = round(units[0] * OUT_SCALE), round(units[1] * OUT_SCALE)
        self.surf = pygame.Surface((round(units[0] * self.k), round(units[1] * self.k)), pygame.SRCALPHA)

    def p(self, pt):
        return round(pt[0] * self.k), round(pt[1] * self.k)

    def w(self, width):
        return max(1, round(width * self.k))

    def stroke(self, pts, width=1.0, color=OUTLINE, closed=False):
        q = [self.p(pt) for pt in pts]
        w = self.w(width)
        pygame.draw.lines(self.surf, color, closed, q, w)
        for pt in q:  # round joints and caps
            pygame.draw.circle(self.surf, color, pt, w / 2)

    def poly(self, fill, pts, outline=True, ow=1.0):
        pygame.draw.polygon(self.surf, fill, [self.p(pt) for pt in pts])
        if outline:
            self.stroke(pts, ow, closed=True)

    def ellipse(self, fill, c, rx, ry, outline=True, ow=1.0):
        r = pygame.Rect(0, 0, round(2 * rx * self.k), round(2 * ry * self.k))
        r.center = self.p(c)
        if outline:
            t = self.w(ow)
            pygame.draw.ellipse(self.surf, OUTLINE, r.inflate(2 * t, 2 * t))
        pygame.draw.ellipse(self.surf, fill, r)

    def capsule(self, fill, a, b, width, outline=True, ow=1.0):
        """Thick rounded line, used for limbs."""
        pa, pb = self.p(a), self.p(b)
        for col, extra in (((OUTLINE, ow),) if outline else ()) + ((fill, 0),):
            w = self.w(width + 2 * extra)
            pygame.draw.line(self.surf, col, pa, pb, w)
            pygame.draw.circle(self.surf, col, pa, w / 2)
            pygame.draw.circle(self.surf, col, pb, w / 2)

    def limb(self, fill, pts, width):
        """Bent limb through several joints: outline everything first so joints stay seamless."""
        for a, b in zip(pts, pts[1:]):
            self.capsule(OUTLINE, a, b, width + 2)
        for a, b in zip(pts, pts[1:]):
            self.capsule(fill, a, b, width, outline=False)

    def finish(self):
        return pygame.transform.smoothscale(self.surf, self.size)


# ---------------------------------------------------------------- poses
# rest=True is the character's signature standing pose; bob > 0 moves the body down
IDLE = [dict(rest=True), dict(rest=True, bob=0.6), dict(rest=True, bob=0.6, blink=True), dict(rest=True)]
WALK = [dict(), dict(bob=-1.2, lift_l=3, swing=1), dict(), dict(bob=-1.2, lift_r=3, swing=-1)]

SKIN = (243, 214, 190)
SKIN_SHADE = (226, 190, 164)
HAND = (238, 205, 180)


def legs(pen, pose, hip_y, hip_dx, ankle_dx, width, color, foot):
    b = pose.get("bob", 0)
    for side, lift in ((-1, pose.get("lift_l", 0)), (1, pose.get("lift_r", 0))):
        ankle = (32 + side * ankle_dx, 87 - lift)
        pen.capsule(color, (32 + side * hip_dx, hip_y + b), ankle, width)
        foot(pen, ankle, side)


def swinging_arms(pen, pose, shoulder, hand, width, sleeve, hand_col=HAND):
    """Walking arms hang straight and swing; shoulder/hand are given for side=+1."""
    b, sw = pose.get("bob", 0), pose.get("swing", 0)
    for side in (-1, 1):
        s = (32 + side * (shoulder[0] - 32), shoulder[1] + b)
        h = (32 + side * (hand[0] - 32), hand[1] + b - side * sw * 2)
        pen.capsule(sleeve, s, h, width)
        pen.ellipse(hand_col, h, 2.4, 2.4, ow=0.8)


# ---------------------------------------------------------------- Crowley
def crowley_boot(pen, ankle, side):
    """Pointed snakeskin boots."""
    bx, by = ankle
    boot = mirror([(bx - 3, by - 1.5), (bx + 3, by - 1.5), (bx + 3.6, by + 2), (bx + 9.5, by + 4.4),
                   (bx + 3, by + 5), (bx - 3.2, by + 5)], bx, side)
    pen.poly((70, 62, 54), boot)
    for dx, dy in ((-1.5, 1), (1, 2.4), (3.6, 3.7), (-0.8, 3.6), (6, 4.2)):
        pen.ellipse((112, 100, 84), (bx + side * dx, by + dy), 0.75, 0.5, outline=False)


def draw_crowley(pen, pose):
    b = pose.get("bob", 0)
    jacket, jacket_hi = (26, 26, 31), (64, 64, 74)

    # long skinny black jeans: tall and lanky
    legs(pen, pose, 64, 3.6, 4.6, 4.8, (32, 32, 38), crowley_boot)

    # fitted, hip-length black jacket; charcoal waistcoat; black shirt; loose skinny tie
    pen.poly(jacket, shift([(21.5, 44), (42.5, 44), (40, 57), (41.2, 69), (22.8, 69), (24, 57)], b))
    pen.poly((56, 56, 64), shift([(28, 44), (36, 44), (35.2, 60), (32, 62.5), (28.8, 60)], b), ow=0.8)
    pen.poly((16, 16, 18), shift([(30, 44), (34, 44), (32, 50)], b), ow=0.5)
    pen.poly((12, 12, 14), shift([(31.4, 47.5), (32.8, 47.5), (33.4, 58.5), (32.4, 60), (31.6, 58.5)], b), ow=0.5)
    pen.stroke(shift([(28, 44), (29.6, 58)], b), 0.9, jacket_hi)              # lapels
    pen.stroke(shift([(36, 44), (34.4, 58)], b), 0.9, jacket_hi)
    for y in (53.5, 57):                                                       # waistcoat buttons
        pen.ellipse((90, 90, 100), (32.1, y + b), 0.6, 0.6, outline=False)

    if pose.get("rest"):  # hands shoved in his jeans pockets, elbows out
        for side in (-1, 1):
            pts = mirror([(40.6, 46.5), (42.6, 55), (38.6, 63)], 32, side)
            pen.limb(jacket, shift(pts, b), 4.2)
            pen.stroke(shift(mirror([(37.8, 63.6), (40.6, 62.4)], 32, side), b), 0.8)
    else:
        swinging_arms(pen, pose, (42, 46), (43.5, 62), 4.6, jacket)

    pen.capsule(SKIN, (32, 37.5 + b), (32, 44 + b), 4.6)      # neck

    hair, hair_dark, hair_hi = (170, 42, 28), (124, 26, 18), (220, 92, 54)
    pen.ellipse(hair, (32, 19 + b), 12.8, 9)                   # back of the hair
    for x in (19.8, 44.2):
        pen.ellipse(SKIN, (x, 27 + b), 2.2, 3.5)                 # ears
    pen.ellipse(SKIN, (32, 25.5 + b), 11.8, 14)                  # long, narrow face
    for side in (-1, 1):                                         # cheekbones
        pen.stroke(shift(mirror([(39.5, 30.5), (38.2, 33.4)], 32, side), b), 0.7, SKIN_SHADE)

    # red quiff swept up off the forehead and back, in soft flicks, with sideburns
    top = (bezier((20.4, 23), (18.6, 16), (20, 9), (25.5, 6), 6)
           + bezier((25.5, 6), (27.5, 3), (30, 1), (32.5, 0.6), 5)[1:]       # front flick
           + bezier((32.5, 0.6), (32, 2.6), (32.6, 3.6), (34, 3.8), 4)[1:]
           + bezier((34, 3.8), (36.5, 2), (39, 1.6), (41.5, 2.4), 5)[1:]     # second flick
           + bezier((41.5, 2.4), (40.6, 4), (41, 5.4), (42.4, 6.4), 4)[1:]
           + bezier((42.4, 6.4), (46, 9), (46.4, 16), (43.8, 23), 6)[1:])
    hairline = (bezier((43.8, 23), (42.6, 18.5), (40, 16), (36.5, 15.6), 6)[1:]
                + bezier((36.5, 15.6), (34, 15.4), (31, 16.8), (28, 16), 6)[1:]
                + bezier((28, 16), (24.5, 15.2), (21.6, 17.5), (20.4, 23), 6)[1:])
    pen.poly(hair, shift(top + hairline, b))
    for side in (-1, 1):
        pen.poly(hair, shift(mirror([(42.4, 20), (44, 20), (43.8, 30.5), (42.7, 30.5)], 32, side), b), ow=0.7)
    for p0, p1, p2, p3 in (((23, 19), (22.6, 13), (25, 8.5), (29, 5)),       # strands sweeping up and back
                           ((27.5, 16.2), (27.4, 10), (29.5, 5), (32, 2.2)),
                           ((32, 16.4), (32.6, 11), (35, 6.5), (39.5, 3.4)),
                           ((37, 15.8), (38.2, 11.5), (40.5, 8.5), (43.2, 8.6)),
                           ((41.6, 18), (43, 15), (44.2, 12.5), (44.6, 10.5))):
        pen.stroke(shift(bezier(p0, p1, p2, p3, 8), b), 0.65, hair_dark)
    pen.stroke(shift(bezier((25, 12), (26, 7.6), (28.5, 4.6), (31, 3), 8), b), 0.9, hair_hi)
    pen.stroke(shift(bezier((34.5, 11), (35.6, 7.4), (37.5, 5), (40, 3.8), 8), b), 0.9, hair_hi)

    # serpent tattoo by his sideburn
    pen.stroke(shift(bezier((20.4, 30.5), (22.6, 31.2), (20.2, 33), (22.4, 34.2), 8), b), 0.75)

    peek = pose.get("blink")  # Crowley's "blink": glasses slide down to show the snake eyes
    gy = 28.8 if peek else 26.5
    if peek:
        for ex in (27, 37):
            pen.ellipse((246, 204, 40), (ex, 24.6 + b), 2.9, 2.0, ow=0.7)
            pen.ellipse((15, 10, 5), (ex, 24.6 + b), 0.55, 1.8, outline=False)
    by = 20.8 if peek else 22.2
    for side in (-1, 1):  # sharp, arched eyebrows
        pen.stroke(shift(mirror([(34.3, by + 0.6), (37.4, by - 0.6), (41, by + 0.4)], 32, side), b), 1.0)

    # small, dark oval glasses with thin frames
    pen.stroke([(23.2, gy + b), (20.6, 26 + b)], 0.6)
    pen.stroke([(40.8, gy + b), (43.4, 26 + b)], 0.6)
    pen.stroke([(30.6, gy - 0.4 + b), (33.4, gy - 0.4 + b)], 0.7)
    for ex in (27, 37):
        pen.ellipse((18, 18, 22), (ex, gy + b), 3.9, 2.7, ow=0.7)
        pen.stroke([(ex - 2.2, gy - 0.8 + b), (ex - 0.6, gy - 1.6 + b)], 0.6, (176, 176, 196))

    pen.stroke(shift([(32.6, 28), (33.3, 31.6), (31.6, 32)], b), 0.75)                      # long nose
    pen.stroke(shift(bezier((28.4, 35.2), (31, 36.4), (34, 36), (36.8, 33.6)), b), 1.0)     # smirk


# ---------------------------------------------------------------- Aziraphale
def azi_shoe(pen, ankle, side):
    """Polished brown oxfords."""
    bx, by = ankle
    pen.ellipse((112, 72, 46), (bx + side * 1.2, by + 2.8), 4.6, 2.6)
    pen.stroke([(bx + side * 0.2, by + 1.6), (bx + side * 2.6, by + 1.6)], 0.5, (160, 112, 74))


def draw_aziraphale(pen, pose):
    b = pose.get("bob", 0)
    coat, coat_dark = (214, 192, 152), (176, 152, 112)
    trousers = (228, 218, 194)

    # shorter, softer build
    legs(pen, pose, 70, 4.4, 5, 6.6, trousers, azi_shoe)

    # long camel overcoat to the knee, worn open
    left = bezier((21.5, 47), (17, 53), (17, 68), (20.5, 80.5), 8)
    pen.poly(coat, shift(left + mirror(left, 32, -1)[::-1], b))
    pen.poly(trousers, shift([(26.5, 64), (37.5, 64), (36.5, 80.5), (27.5, 80.5)], b), ow=0.8)
    # ivory waistcoat with gold buttons and pocket-watch chain
    pen.poly((240, 232, 210), shift([(26.5, 47), (37.5, 47), (40, 64), (32, 68.5), (24, 64)], b), ow=0.8)
    for y in (53, 57, 61):
        pen.ellipse((206, 168, 70), (32, y + b), 0.75, 0.75, outline=False)
    pen.stroke(shift(bezier((32, 58), (34.5, 62), (37.2, 61), (38.8, 57.5)), b), 0.6, (214, 172, 52))
    for side in (-1, 1):  # coat front edges and darker collar
        pen.stroke(shift(mirror([(38, 47), (40.4, 64), (38.2, 80.5)], 32, side), b), 0.9, coat_dark)
        pen.poly(coat_dark, shift(mirror([(37.5, 46.5), (42.5, 47), (39.6, 53)], 32, side), b), ow=0.6)

    if pose.get("rest"):  # hands clasped politely in front of his tummy
        for side in (-1, 1):
            pen.limb(coat, shift(mirror([(41, 49.5), (42.8, 57.5), (35.5, 62.4)], 32, side), b), 5)
        pen.ellipse(HAND, (32, 62.8 + b), 4.2, 2.8, ow=0.8)
        pen.stroke(shift([(31.2, 61), (32.8, 64.4)], b), 0.6)
        pen.ellipse((222, 180, 56), (34.6, 62.2 + b), 0.8, 0.8, ow=0.4)  # gold pinky ring
    else:
        swinging_arms(pen, pose, (42, 49), (44, 65), 5.6, coat)

    pen.capsule(SKIN, (32, 42 + b), (32, 47 + b), 5.4)       # neck
    for side in (-1, 1):                                      # white shirt collar
        pen.poly((252, 250, 244), shift(mirror([(32, 46.5), (35.5, 44.5), (36.5, 48)], 32, side), b), ow=0.6)
    for side in (-1, 1):                                      # tartan bow tie
        pen.poly((200, 170, 116), shift(mirror([(32, 47.5), (36.8, 45), (36.8, 50)], 32, side), b), ow=0.6)
        pen.stroke(shift(mirror([(34.2, 46.2), (34.2, 48.9)], 32, side), b), 0.4, (110, 74, 44))
        pen.stroke(shift(mirror([(33, 47.6), (36.3, 47.6)], 32, side), b), 0.4, (82, 104, 140))
    pen.ellipse((170, 136, 86), (32, 47.5 + b), 1.2, 1.4, ow=0.6)

    curls, curls_lo, curl_line = (250, 245, 228), (222, 212, 182), (206, 192, 152)
    pen.ellipse(curls_lo, (32, 25 + b), 13.6, 9)              # back of the hair
    for x in (18.4, 45.6):
        pen.ellipse(SKIN, (x, 32 + b), 2.4, 3.6)
    pen.ellipse(SKIN, (32, 31 + b), 13.4, 13.6)               # round face
    for cx in (24.8, 39.2):                                   # rosy cheeks
        pen.ellipse((242, 186, 174), (cx, 35.4 + b), 2.6, 1.6, outline=False)

    # short platinum curls: fluffy on top, close at the sides, ears showing
    top = []
    for i in range(49):  # bumpy outline gives the curly silhouette
        a = math.radians(180 + 180 * i / 48)
        r = 1 + 0.09 * abs(math.sin(a * 7))
        top.append((32 + 14.2 * r * math.cos(a), 25.5 + 15.2 * r * math.sin(a)))
    hairline = (bezier((46.2, 25.5), (44.2, 20.5), (39.5, 18.5), (36, 20), 6)[1:]
                + bezier((36, 20), (34.4, 18.4), (29.6, 18.4), (28, 20), 6)[1:]
                + bezier((28, 20), (24.5, 18.5), (19.8, 20.5), (17.8, 25.5), 6)[1:])
    pen.poly(curls, shift(top + hairline, b))
    for cx, cy in ((22, 21), (25, 15), (29.5, 11.6), (35, 11.8), (39.8, 15.4), (42.4, 21),
                   (27.6, 17.4), (33, 16.6), (38, 19), (24, 20), (31.4, 14.4), (37, 14.2), (32.4, 9.6)):
        pen.stroke(shift(bezier((cx - 1.6, cy + 0.8), (cx - 1.4, cy - 1.4), (cx + 1.4, cy - 1.6),
                                (cx + 1.5, cy + 0.2), 6), b), 0.5, curl_line)

    if pose.get("blink"):
        for ex in (27, 37):
            pen.stroke(shift(bezier((ex - 2, 31), (ex - 1, 32.2), (ex + 1, 32.2), (ex + 2, 31), 6), b), 0.9)
    else:
        for ex in (27, 37):
            pen.ellipse((76, 102, 140), (ex, 31.2 + b), 1.7, 2.1, outline=False)   # blue eyes
            pen.ellipse((255, 255, 255), (ex + 0.6, 30.4 + b), 0.55, 0.55, outline=False)
    for ex in (27, 37):  # soft, slightly anxious eyebrows
        pen.stroke(shift(bezier((ex - 2.6, 27.4), (ex - 1, 26.1), (ex + 1, 26.1), (ex + 2.6, 26.9), 6), b),
                   0.9, (200, 176, 124))
    pen.stroke(shift([(32.2, 32.6), (32.8, 34.8), (31.4, 35.2)], b), 0.7)                   # nose
    pen.stroke(shift(bezier((27.8, 37.6), (30, 40.4), (34, 40.4), (36.2, 37.6)), b), 1.0)   # warm smile


# ---------------------------------------------------------------- Adam
def adam_trainer(pen, ankle, side):
    bx, by = ankle
    pen.ellipse((246, 246, 240), (bx + side * 1.2, by + 2.6), 4.4, 2.6)
    pen.stroke([(bx - side * 1.6, by + 2.6), (bx + side * 3, by + 2.6)], 0.7, (200, 52, 48))


def draw_adam(pen, pose):
    """Eleven years old (the sheet is scaled down), messy golden curls, striped T-shirt."""
    b, sw = pose.get("bob", 0), pose.get("swing", 0)
    legs(pen, pose, 66, 4, 4.6, 6, (70, 98, 150), adam_trainer)
    shirt, stripe = (244, 238, 222), (70, 110, 170)
    pen.poly(shirt, shift([(22.5, 46), (41.5, 46), (40.5, 68), (23.5, 68)], b))
    for y in (51, 56, 61, 65.5):
        pen.stroke(shift([(23.4, y), (40.6, y)], b), 1.4, stripe)
    for side in (-1, 1):  # short sleeves, bare forearms
        shoulder = (32 + side * 9.5, 48 + b)
        elbow = (32 + side * 11, 56 + b - side * sw)
        hand = (32 + side * 11.5, 64 + b - side * sw * 2)
        pen.capsule(SKIN, elbow, hand, 4.2)
        pen.ellipse(HAND, hand, 2.3, 2.3, ow=0.8)
        pen.capsule(shirt, shoulder, elbow, 5.4)
    pen.capsule(SKIN, (32, 41 + b), (32, 47 + b), 5)

    hair, hair_lo, hair_line = (230, 180, 66), (198, 148, 46), (168, 118, 32)
    pen.ellipse(hair_lo, (32, 25 + b), 14.5, 11)
    for x in (18.6, 45.4):
        pen.ellipse(SKIN, (x, 31.5 + b), 2.4, 3.6)
    pen.ellipse(SKIN, (32, 30.5 + b), 13, 13.8)
    for cx in (25, 39):  # freckles
        for dx, dy in ((-1.2, 0), (0.6, -0.6), (0.8, 0.9)):
            pen.ellipse((214, 150, 110), (cx + dx, 34.5 + dy + b), 0.45, 0.45, outline=False)
    top = []
    for i in range(49):  # messy mop of curls
        a = math.radians(180 + 180 * i / 48)
        r = 1 + 0.1 * abs(math.sin(a * 9))
        top.append((32 + 15.2 * r * math.cos(a), 27 + 15.5 * r * math.sin(a)))
    fringe = (bezier((47.2, 27), (44, 20), (39.5, 23), (36, 21.6), 6)[1:]
              + bezier((36, 21.6), (33, 24), (29, 20.6), (26, 22.6), 6)[1:]
              + bezier((26, 22.6), (22, 20), (19.5, 22.5), (16.8, 27), 6)[1:])
    pen.poly(hair, shift(top + fringe, b))
    for cx, cy in ((21, 21), (25, 15.5), (30, 12.5), (35.5, 12.5), (40.5, 16), (43.5, 21), (28, 18), (34, 17.5), (39, 20)):
        pen.stroke(shift(bezier((cx - 1.6, cy + 0.8), (cx - 1.4, cy - 1.4), (cx + 1.4, cy - 1.6), (cx + 1.5, cy + 0.2), 6), b),
                   0.55, hair_line)

    if pose.get("blink"):
        for ex in (27, 37):
            pen.stroke(shift(bezier((ex - 2, 30.6), (ex - 1, 31.8), (ex + 1, 31.8), (ex + 2, 30.6), 6), b), 0.9)
    else:
        for ex in (27, 37):
            pen.ellipse((70, 52, 36), (ex, 30.8 + b), 1.7, 2.1, outline=False)
            pen.ellipse((255, 255, 255), (ex + 0.6, 30 + b), 0.55, 0.55, outline=False)
    for ex in (27, 37):
        pen.stroke(shift([(ex - 2.4, 26.6), (ex + 2.2, 26)], b), 0.9, hair_line)
    mouth = bezier((27.8, 36.4), (30, 41), (34, 41), (36.2, 36.4), 10)  # big grin
    pen.poly((150, 58, 58), shift(mouth, b), ow=0.9)
    pen.poly((255, 255, 255), shift([(28.8, 36.9), (35.2, 36.9), (34.8, 38), (29.2, 38)], b), outline=False)


def draw_dog(pen, pose):
    """Adam's scruffy little terrier, side view facing right (was a hellhound once)."""
    b, sw = pose.get("bob", 0), pose.get("swing", 0)
    fur, fur_dark, muzzle = (156, 116, 74), (118, 84, 50), (214, 186, 146)
    for x, d in ((12, -1), (26, 1)):   # far legs
        pen.capsule(fur_dark, (x, 19 + b), (x - d * sw * 2, 27), 2.6)
    pen.stroke(shift(bezier((8, 15), (5, 12), (5, 8), (6.5, 6), 6), b), 2.2, fur)   # perky tail
    pen.ellipse(fur, (18, 17 + b), 10, 5.5)
    for x, d in ((14, 1), (28, -1)):   # near legs
        pen.capsule(fur, (x, 19 + b), (x - d * sw * 2, 27.5), 2.8)
    pen.ellipse(fur, (30, 11.5 + b), 5.4, 5)
    pen.ellipse(muzzle, (35.2, 13.5 + b), 3, 2.3)
    pen.ellipse(OUTLINE, (37.6, 12.6 + b), 0.9, 0.8, outline=False)
    pen.poly(fur_dark, shift([(26.5, 8), (28, 5), (30.5, 8.5)], b), ow=0.7)        # floppy ear
    if pose.get("blink"):
        pen.stroke(shift([(31, 10.4), (33, 10.4)], b), 0.7)
    else:
        pen.ellipse(OUTLINE, (32, 10.2 + b), 0.9, 1.0, outline=False)
    for x in (13, 18, 23):             # scruffy fur
        pen.stroke(shift([(x, 13.2), (x + 1, 12)], b), 0.5, fur_dark)


# ---------------------------------------------------------------- Hastur
def hastur_boot(pen, ankle, side):
    bx, by = ankle
    pen.poly((44, 38, 32), mirror([(bx - 3, by - 1.5), (bx + 3, by - 1.5), (bx + 3.6, by + 2), (bx + 7, by + 3.6),
                                   (bx + 6.4, by + 5), (bx - 3.2, by + 5)], bx, side))


def draw_hastur(pen, pose):
    """Gaunt Duke of Hell: lank black hair, ragged grimy coat, a frog on his head."""
    b = pose.get("bob", 0)
    pale, pale_shade = (212, 208, 180), (184, 176, 146)
    legs(pen, pose, 64, 3.6, 4.6, 5, (58, 54, 48), hastur_boot)
    coat = (74, 70, 60)
    hem = [(40.5, 80), (38.4, 77.4), (36.4, 81), (34, 77.8), (31.6, 81.4), (29, 77.8), (26.6, 81), (24.6, 77.4), (23.5, 80)]
    pen.poly(coat, shift([(21.5, 44), (42.5, 44), (41, 60), (42.5, 80)] + hem + [(21.5, 80), (23, 60)], b))
    pen.poly((190, 182, 152), shift([(28, 44), (36, 44), (32, 55)], b), ow=0.8)     # grubby shirt
    for x, y in ((30.5, 47), (33, 50.5)):
        pen.ellipse((150, 130, 96), (x, y + b), 0.8, 0.6, outline=False)
    for side in (-1, 1):
        pen.stroke(shift(mirror([(36, 44), (34, 62)], 32, side), b), 0.9, (52, 48, 42))
    swinging_arms(pen, pose, (41, 46), (43, 64), 4.6, coat, pale)
    pen.capsule(pale, (32, 37.5 + b), (32, 44 + b), 4.4)

    hair, hair_hi = (30, 28, 26), (66, 62, 58)
    pen.poly(hair, shift([(18.5, 15), (45.5, 15), (46.6, 38), (42, 37), (40.5, 25), (23.5, 25), (22, 37), (17.4, 38)], b))
    pen.ellipse(pale, (32, 26 + b), 11.2, 14.2)                   # long, gaunt face
    for side in (-1, 1):
        pen.stroke(shift(mirror([(39.5, 30), (38.2, 34.5)], 32, side), b), 0.7, pale_shade)  # hollow cheeks
    cap = (bezier((19.6, 26), (18, 12), (30, 9.5), (32, 13.5), 8)
           + bezier((32, 13.5), (34, 9.5), (46, 12), (44.4, 26), 8)[1:]
           + bezier((44.4, 26), (42, 18), (36, 16), (32, 15.2), 6)[1:]
           + bezier((32, 15.2), (28, 16), (22, 18), (19.6, 26), 6)[1:])
    pen.poly(hair, shift(cap, b))
    for x in (20.5, 43.5, 45.5, 18.6):
        pen.stroke(shift([(x, 27), (x + (0.6 if x > 32 else -0.6), 36)], b), 0.6, hair_hi)

    for ex in (27, 37):  # sunken, beady eyes under a scowl
        pen.ellipse(pale_shade, (ex, 26.8 + b), 3, 2.4, outline=False)
        if pose.get("blink"):
            pen.stroke(shift([(ex - 1.6, 26), (ex + 1.6, 26)], b), 0.8)
        else:
            pen.ellipse((24, 20, 18), (ex, 25.8 + b), 1.1, 1.2, outline=False)
    pen.stroke(shift([(23, 21.6), (29.5, 23.2)], b), 1.1)
    pen.stroke(shift([(41, 21.6), (34.5, 23.2)], b), 1.1)
    pen.stroke(shift([(32.5, 27), (33.2, 31), (31.6, 31.4)], b), 0.75)
    mouth = shift([(27.5, 35), (36.5, 34.4), (35.5, 36.6), (28.4, 36.8)], b)
    pen.poly((70, 30, 30), mouth, ow=0.8)
    for x in (29, 31, 33, 35):  # snaggly teeth
        pen.poly((236, 228, 196), shift([(x - 0.7, 35), (x + 0.7, 34.9), (x, 36.2)], b), outline=False)

    frog, frog_belly = (96, 150, 62), (176, 204, 110)   # the frog on his head
    pen.ellipse(frog, (32, 9.6 + b), 6, 3.8)
    pen.ellipse(frog_belly, (32, 11 + b), 3.6, 1.6, outline=False)
    for ex in (28.6, 35.4):
        pen.ellipse(frog, (ex, 6.6 + b), 1.9, 1.9, ow=0.7)
        if pose.get("blink"):
            pen.stroke(shift([(ex - 1, 6.6), (ex + 1, 6.6)], b), 0.5)
        else:
            pen.ellipse(OUTLINE, (ex, 6.6 + b), 0.7, 0.9, outline=False)
    pen.stroke(shift(bezier((29.5, 9.2), (31, 10.2), (33, 10.2), (34.5, 9.2), 6), b), 0.5)


# ---------------------------------------------------------------- Ligur
def draw_ligur(pen, pose):
    """Duke of Hell with a chameleon on his head and a long brown leather coat."""
    b = pose.get("bob", 0)
    skin, skin_shade = (132, 92, 64), (108, 72, 48)

    def boot(pen, ankle, side):
        bx, by = ankle
        pen.poly((26, 22, 20), mirror([(bx - 3.2, by - 1.5), (bx + 3.2, by - 1.5), (bx + 3.8, by + 2), (bx + 7, by + 3.4),
                                       (bx + 6.4, by + 5), (bx - 3.4, by + 5)], bx, side))

    legs(pen, pose, 64, 3.8, 4.8, 5.6, (42, 38, 36), boot)
    coat = (98, 64, 40)
    pen.poly(coat, shift([(21, 44), (43, 44), (41.5, 60), (43.5, 80), (20.5, 80), (22.5, 60)], b))
    pen.poly((112, 36, 30), shift([(28, 44), (36, 44), (35, 60), (29, 60)], b), ow=0.8)   # dark red shirt
    for side in (-1, 1):
        pen.stroke(shift(mirror([(36, 44), (35, 80)], 32, side), b), 0.9, (72, 46, 28))
    pen.poly((40, 30, 24), shift([(22.4, 59), (41.6, 59), (41.6, 61.6), (22.4, 61.6)], b), ow=0.6)  # belt
    swinging_arms(pen, pose, (41.5, 46), (43.5, 64), 5, coat, skin)
    pen.capsule(skin, (32, 38 + b), (32, 44.5 + b), 5)

    for x in (19.8, 44.2):
        pen.ellipse(skin, (x, 27.5 + b), 2.3, 3.5)
    pen.ellipse(skin, (32, 26 + b), 12, 14)                     # shaved head
    pen.stroke(shift(bezier((25, 16), (28, 13.6), (33, 13.2), (37, 14.6), 8), b), 1.0, (160, 118, 88))  # shine
    pen.poly((38, 28, 22), shift(bezier((28.4, 37.4), (30, 40.6), (34, 40.6), (35.6, 37.4), 8), b), ow=0.6)  # goatee
    for ex in (27, 37):  # narrowed, sinister eyes
        if pose.get("blink"):
            pen.stroke(shift([(ex - 2, 26.6), (ex + 2, 26.6)], b), 0.8)
        else:
            pen.poly((246, 236, 214), shift([(ex - 2.6, 26.6), (ex, 25.2), (ex + 2.6, 26.6), (ex, 27.6)], b), ow=0.6)
            pen.ellipse((150, 30, 20), (ex, 26.4 + b), 0.9, 0.9, outline=False)
    pen.stroke(shift([(23.4, 23.2), (29.6, 24.4)], b), 1.2)
    pen.stroke(shift([(40.6, 23.2), (34.4, 24.4)], b), 1.2)
    pen.stroke(shift([(32.6, 27.6), (33.4, 31.6), (31.4, 32)], b), 0.75, skin_shade)
    pen.stroke(shift(bezier((28.6, 35.4), (31, 35.8), (33.5, 35.6), (35.8, 34.6), 6), b), 1.0)

    cham, cham_hi = (104, 168, 72), (196, 220, 96)   # the chameleon, gripping his scalp
    pen.stroke(shift([(25, 14.2), (23.6, 16.4)], b), 0.8, cham)
    pen.stroke(shift([(36, 13.6), (37.6, 15.8)], b), 0.8, cham)
    pen.ellipse(cham, (31, 11.6 + b), 7, 3.4)
    pen.poly(cham, shift([(37, 9.6), (42.6, 11.4), (37.4, 13.6)], b), ow=0.8)
    pen.stroke(shift([(26, 11.2), (35, 10.6)], b), 0.8, cham_hi)
    pen.ellipse(cham_hi, (38.4, 10.8 + b), 1.4, 1.4, ow=0.6)
    pen.ellipse(OUTLINE, (38.6, 10.8 + b), 0.5, 0.5, outline=False)
    pen.stroke(shift(bezier((24.2, 12), (20, 12.6), (19.4, 8.6), (22, 8.4), 8) + bezier((22, 8.4), (23.6, 8.4), (23.4, 10.4), (22, 10.2), 4)[1:], b),
               1.0, cham)  # curly tail


# ---------------------------------------------------------------- Hellhound
def draw_hellhound(pen, pose):
    """Huge black hound of Hell, side view facing right, with glowing red eyes."""
    b, sw = pose.get("bob", 0), pose.get("swing", 0)
    fur, far = (26, 24, 27), (14, 13, 15)
    for x, d in ((22, -1), (44, 1)):    # far legs
        pen.capsule(far, (x, 28 + b), (x + d * sw * 4, 43), 4)
        pen.ellipse(far, (x + d * sw * 4 + 1, 43.6), 2.6, 1.4)
    pen.stroke(shift(bezier((15, 20), (9, 15), (7, 9), (9, 5), 8), b), 3.2, fur)   # tail
    pen.ellipse(fur, (19, 23 + b), 8.5, 8.5)                   # rump
    pen.ellipse(fur, (32, 24 + b), 16, 8.5)                    # body
    pen.ellipse(fur, (45, 23 + b), 8.5, 9.5)                   # chest
    pen.poly(fur, shift([(43, 15), (52, 10), (58, 17), (50, 24)], b))   # neck
    for x, d in ((19, 1), (47, -1)):    # near legs
        pen.capsule(fur, (x, 28 + b), (x + d * sw * 4, 43.5), 4.4)
        pen.ellipse(fur, (x + d * sw * 4 + 1.2, 44), 2.8, 1.5)
    pen.ellipse(fur, (56, 15 + b), 7, 6)                       # head
    pen.poly(fur, shift([(58, 12), (68.5, 15.5), (68.5, 20), (58, 21)], b))   # snout
    pen.ellipse((60, 52, 56), (68.4, 16.4 + b), 1.4, 1.2, outline=False)       # nose
    pen.poly(fur, shift([(51.5, 11), (53, 2.6), (57, 9)], b))                 # pointed ear
    snarl = pose.get("blink")
    pen.poly((120, 20, 20), shift([(59, 19.6), (68, 19.6), (67.4, 21.4 + (1.6 if snarl else 0)), (60, 21.2)], b), ow=0.6)
    for x in (61, 63.5, 66):            # fangs
        pen.poly((240, 236, 220), shift([(x - 0.7, 19.6), (x + 0.7, 19.6), (x, 21.6)], b), outline=False)
    glow = 2.6 if snarl else 2.0
    pen.ellipse((255, 120, 40), (59.4, 13.6 + b), glow, glow * 0.7, outline=False)
    pen.ellipse((255, 30, 20), (59.4, 13.6 + b), 1.6, 1.1, outline=False)
    for x in (26, 32, 38):              # shaggy fur
        pen.stroke(shift([(x, 17.2), (x + 2, 16)], b), 0.6, (60, 56, 62))


# ---------------------------------------------------------------- the Bentley
def draw_bentley(pen, pose):
    """Crowley's black 1926 Bentley, side view facing right. Wheels turn with the frame."""
    spin = pose.get("frame", 0) * math.pi / 8
    black, chrome, glass = (20, 20, 24), (200, 200, 212), (96, 116, 138)
    for wx in (24, 80):
        pen.ellipse((16, 16, 16), (wx, 33), 8, 8)
        pen.ellipse((60, 60, 66), (wx, 33), 5.4, 5.4, outline=False)
        for k in range(6):
            a = spin + k * math.pi / 3
            pen.stroke([(wx, 33), (wx + 5 * math.cos(a), 33 + 5 * math.sin(a))], 0.6, chrome)
        pen.ellipse(chrome, (wx, 33), 2, 2, ow=0.6)
    pen.poly(black, [(12, 29), (12, 21), (30, 20), (30, 29)])                       # boot
    pen.poly(black, [(30, 29), (30, 13), (34, 9), (58, 9), (63, 20), (63, 29)])      # cabin
    pen.poly(glass, [(33, 19), (33, 13), (36, 11.4), (45, 11.4), (45, 19)], ow=0.7)
    pen.poly(glass, [(47, 11.4), (56.6, 11.4), (60, 19), (47, 19)], ow=0.7)
    pen.poly(black, [(62, 20), (92, 21.5), (92, 29.5), (62, 29.5)])                  # long bonnet
    for x in range(67, 88, 4):
        pen.stroke([(x, 22.6), (x, 27.6)], 0.5, (70, 70, 80))
    pen.poly(chrome, [(91.5, 18), (95, 18), (95, 30.5), (91.5, 30.5)], ow=0.7)        # radiator
    pen.ellipse(chrome, (89, 19.6), 3, 3, ow=0.7)                                    # headlamp
    pen.ellipse((250, 240, 180), (89.6, 19.6), 1.8, 1.8, outline=False)
    pen.poly(black, [(34, 30), (70, 30), (70, 32.4), (34, 32.4)], ow=0.7)           # running board
    for wx in (24, 80):                                                               # mudguards
        pen.poly(black, bezier((wx - 12, 32), (wx - 9, 21.5), (wx + 9, 21.5), (wx + 12, 32), 10)
                 + [(wx + 9, 31), (wx - 9, 31)], ow=0.8)
    pen.stroke([(30, 23.5), (62, 23.5)], 0.6, (90, 90, 100))
    pen.ellipse(chrome, (52, 23.4), 1.4, 0.6, outline=False)                         # door handle


# ---------------------------------------------------------------- pickups
def item_page(pen):
    pen.poly((240, 226, 184), [(5, 3.5), (19, 4.5), (19.5, 21), (5.5, 20)])
    for y in (8, 11, 14, 17):
        pen.stroke([(8, y), (16.5, y + 0.4)], 0.6, (140, 110, 70))
    pen.ellipse((170, 40, 40), (15.5, 18), 1.6, 1.6, ow=0.5)   # wax seal


def item_book(pen):
    pen.poly((246, 240, 220), [(6.5, 6), (19.5, 4), (21, 19), (8, 21)], ow=0.7)
    pen.poly((126, 40, 38), [(4, 5.5), (17.6, 3.5), (19.2, 18.8), (5.6, 20.8)])
    pen.stroke([(7.5, 9), (15.5, 7.8)], 0.8, (220, 180, 70))
    pen.stroke([(8, 12), (14, 11.1)], 0.6, (220, 180, 70))


def item_sword(pen):
    pen.poly((214, 218, 228), [(17.5, 3.5), (20.5, 3.5), (20.5, 6.5), (9, 17.5), (6.5, 15)])
    pen.stroke([(14.5, 9.5), (19, 5)], 0.5, (150, 156, 170))
    pen.capsule((212, 172, 60), (5, 13), (11, 19), 2.2)
    pen.capsule((140, 30, 30), (7, 17), (4, 20), 2.4)
    pen.ellipse((212, 172, 60), (3.6, 20.4), 1.5, 1.5, ow=0.6)


def item_scales(pen):
    gold = (214, 176, 64)
    pen.capsule(gold, (12, 5), (12, 19.5), 1.4)
    pen.ellipse(gold, (12, 20.4), 5, 1.4)
    pen.capsule(gold, (3.5, 7.5), (20.5, 7.5), 1.2)
    for x in (4.5, 19.5):
        pen.stroke([(x, 7.5), (x - 2.4, 14)], 0.4)
        pen.stroke([(x, 7.5), (x + 2.4, 14)], 0.4)
        pen.poly(gold, bezier((x - 3.4, 14), (x - 2.4, 17), (x + 2.4, 17), (x + 3.4, 14), 6), ow=0.7)
    pen.ellipse(gold, (12, 4.6), 1.4, 1.4, ow=0.6)


def item_crown(pen):
    pen.poly((214, 176, 64), [(4, 18.5), (3.5, 8), (8, 12.5), (12, 5.5), (16, 12.5), (20.5, 8), (20, 18.5)])
    pen.poly((180, 140, 40), [(4, 15.5), (20, 15.5), (20, 18.5), (4, 18.5)], ow=0.7)
    for x, c in ((8, (170, 40, 40)), (12, (60, 110, 190)), (16, (170, 40, 40))):
        pen.ellipse(c, (x, 17), 1.1, 1.1, ow=0.5)
    for x, y in ((3.5, 8), (12, 5.5), (20.5, 8)):
        pen.ellipse((240, 220, 140), (x, y), 1.2, 1.2, ow=0.5)


def item_crepe(pen):
    pen.ellipse((246, 246, 240), (12, 16.5), 9.5, 4, ow=0.7)                       # plate
    pen.poly((234, 188, 104), [(4.5, 15), (19.5, 15), (12, 5.5)])
    pen.poly((248, 244, 228), [(8, 13), (16, 13), (12, 9.6)], outline=False)         # cream
    for x, y in ((8, 14), (13.5, 8.6), (16.6, 13.6)):
        pen.ellipse((190, 132, 64), (x, y), 0.7, 0.6, outline=False)
    pen.ellipse((200, 40, 60), (12, 9.2), 1.3, 1.3, ow=0.5)                         # strawberry


ITEMS = {"page": item_page, "book": item_book, "sword": item_sword, "scales": item_scales,
         "crown": item_crown, "crepe": item_crepe}

# name: (draw function, design units, final scale)
CAST = {
    "crowley": (draw_crowley, (UNIT_W, UNIT_H), 1.0),
    "aziraphale": (draw_aziraphale, (UNIT_W, UNIT_H), 1.0),
    "adam": (draw_adam, (UNIT_W, UNIT_H), 0.8),
    "hastur": (draw_hastur, (UNIT_W, UNIT_H), 1.0),
    "ligur": (draw_ligur, (UNIT_W, UNIT_H), 1.0),
    "dog": (draw_dog, (40, 30), 1.0),
    "hellhound": (draw_hellhound, (72, 48), 1.0),
    "bentley": (draw_bentley, (100, 44), 1.0),
}


def build_sheet(draw, units, scale):
    fw, fh = round(units[0] * OUT_SCALE), round(units[1] * OUT_SCALE)
    sheet = pygame.Surface((fw * 4, fh * 2), pygame.SRCALPHA)
    for row, poses in enumerate((IDLE, WALK)):
        for col, pose in enumerate(poses):
            pen = Pen(units)
            draw(pen, dict(pose, frame=row * 4 + col))
            frame = pen.finish()
            if scale != 1.0:  # smaller character: shrink and stand it on the frame's floor
                small = pygame.transform.smoothscale_by(frame, scale)
                frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
                frame.blit(small, ((fw - small.get_width()) // 2, fh - small.get_height()))
            sheet.blit(frame, (col * fw, row * fh))
    return sheet


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # no window needed
    pygame.init()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(ITEM_DIR, exist_ok=True)
    sheets = {}
    for name, (draw, units, scale) in CAST.items():
        sheets[name] = build_sheet(draw, units, scale)
        pygame.image.save(sheets[name], os.path.join(OUT_DIR, f"{name}.png"))
    items = {}
    for name, draw in ITEMS.items():
        pen = Pen((24, 24))
        draw(pen)
        items[name] = pen.finish()
        pygame.image.save(items[name], os.path.join(ITEM_DIR, f"{name}.png"))
    print(f"wrote {len(sheets)} sprite sheets to {OUT_DIR}")
    print(f"wrote {len(items)} item icons to {ITEM_DIR}")

    # line-up for eyeballing the art: one row per sheet (idle frames, then walk frames)
    gap = 16
    rows = []
    for s in list(sheets.values()) + [None]:
        if s is None:  # last row: the item icons
            row = pygame.Surface((sum(i.get_width() + gap for i in items.values()), 40), pygame.SRCALPHA)
            for k, i in enumerate(items.values()):
                row.blit(i, (k * (i.get_width() + gap), 2))
        else:
            fh = s.get_height() // 2
            row = pygame.Surface((s.get_width() * 2, fh), pygame.SRCALPHA)
            row.blit(s, (0, 0), (0, 0, s.get_width(), fh))
            row.blit(s, (s.get_width(), 0), (0, fh, s.get_width(), fh))
        rows.append(row)
    preview = pygame.Surface((max(r.get_width() for r in rows) + 2 * gap, sum(r.get_height() + gap for r in rows) + gap))
    preview.fill((92, 138, 70))
    y = gap
    for r in rows:
        preview.blit(r, (gap, y))
        y += r.get_height() + gap
    path = os.path.join(OUT_DIR, "cast_preview.png")
    pygame.image.save(preview, path)
    print("wrote", path)


if __name__ == "__main__":
    main()
