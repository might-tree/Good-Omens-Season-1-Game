"""Walk the generated sprites around to check how they animate.

Run generate_sprites.py first, then:  python preview.py
Aziraphale: WASD    Crowley: arrow keys    Esc: quit
"""
import os
import random

import pygame

from generate_sprites import FRAME_W, FRAME_H, OUT_DIR

W, H = 900, 560
SPEED = 170          # pixels per second
WALK_FPS, IDLE_FPS = 8, 2


class Walker:
    def __init__(self, name, x, keys):
        sheet = pygame.image.load(os.path.join(OUT_DIR, f"{name}.png")).convert_alpha()
        self.frames = [[sheet.subsurface((c * FRAME_W, r * FRAME_H, FRAME_W, FRAME_H)) for c in range(4)]
                       for r in range(2)]
        self.name = name.capitalize()
        self.x, self.y = x, H / 2
        self.keys = keys
        self.t = 0.0
        self.moving = False
        self.facing_left = False

    def update(self, dt, pressed):
        up, down, left, right = (pressed[k] for k in self.keys)
        dx, dy = right - left, down - up
        self.moving = bool(dx or dy)
        if self.moving:
            n = (dx * dx + dy * dy) ** 0.5
            self.x = min(max(self.x + dx / n * SPEED * dt, FRAME_W / 2), W - FRAME_W / 2)
            self.y = min(max(self.y + dy / n * SPEED * dt, FRAME_H / 2), H - FRAME_H / 2)
            if dx:
                self.facing_left = dx < 0
        self.t += dt

    def draw(self, screen, font):
        row, fps = (1, WALK_FPS) if self.moving else (0, IDLE_FPS)
        img = self.frames[row][int(self.t * fps) % 4]
        if self.facing_left:
            img = pygame.transform.flip(img, True, False)
        feet_y = self.y + FRAME_H / 2
        shadow = pygame.Rect(0, 0, 50, 14)
        shadow.center = (self.x, feet_y - 6)
        pygame.draw.ellipse(screen, (60, 100, 45), shadow)
        screen.blit(img, img.get_rect(center=(self.x, self.y)))
        label = font.render(self.name, True, (255, 250, 230))
        screen.blit(label, label.get_rect(center=(self.x, feet_y + 8)))


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Good Omens: sprite preview")
    font = pygame.font.SysFont("georgia", 16)
    clock = pygame.time.Clock()

    grass = pygame.Surface((W, H))
    grass.fill((88, 134, 66))
    rng = random.Random(1)
    for _ in range(1800):
        grass.fill(rng.choice([(78, 122, 58), (100, 148, 76)]), (rng.randrange(W), rng.randrange(H), 2, 4))

    walkers = [
        Walker("aziraphale", W * 0.35, (pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d)),
        Walker("crowley", W * 0.65, (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)),
    ]
    hint = font.render("Aziraphale: WASD    Crowley: arrows    Esc: quit", True, (240, 235, 215))

    while True:
        dt = clock.tick(60) / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                return
        pressed = pygame.key.get_pressed()
        for wk in walkers:
            wk.update(dt, pressed)
        screen.blit(grass, (0, 0))
        for wk in sorted(walkers, key=lambda w: w.y):
            wk.draw(screen, font)
        screen.blit(hint, (12, 10))
        pygame.display.flip()


if __name__ == "__main__":
    main()
