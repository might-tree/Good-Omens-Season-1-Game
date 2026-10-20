"""Headless play-through of every level in every mode, to catch crashes before a release.

Run:  python smoke_test.py [screenshot_dir]
"""
import os
import random
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame  # noqa: E402

import game  # noqa: E402

game.SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".smoke_save.json")
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
DT = 1 / 60


class FakeKeys:
    def __init__(self):
        self.down = set()

    def __getitem__(self, k):
        return k in self.down


def press(g, key):
    g.handle(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))


def frames(g, n, keys=None, rng=None):
    for i in range(n):
        if keys is not None and rng and i % 20 == 0:
            keys.down = set(rng.sample([pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_UP,
                                        pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT], 2))
            if rng.random() < 0.2:
                press(g, rng.choice([pygame.K_e, pygame.K_SPACE, pygame.K_RETURN]))
        g.update(DT)
        g.draw()


def shot(g, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        pygame.image.save(g.screen, os.path.join(SHOTS, name + ".png"))


def main():
    rng = random.Random(1)
    g = game.Game()
    keys = FakeKeys()
    g.pressed = lambda: keys
    frames(g, 30)
    shot(g, "title")
    for mode_index, mode in enumerate(("solo_azi", "solo_crowley", "coop")):
        g.to_title()
        g.menu_i = mode_index
        press(g, pygame.K_RETURN)
        assert g.state == "intro" and g.mode == mode, (g.state, g.mode)
        for level in range(len(game.LEVELS)):
            frames(g, 5)
            if mode == "coop":
                shot(g, f"intro{level + 1}")
            press(g, pygame.K_RETURN)
            assert g.state == "play", g.state
            frames(g, 400, keys, rng)                   # wander, fight, use abilities
            assert g.state == "play", f"{mode} level {level + 1}: ended early ({g.state})"
            if mode == "coop":
                shot(g, f"level{level + 1}")
            p = g.players[0]
            for it in g.pickups:                       # walk onto every item...
                p.x, p.y = it["x"], it["y"]
                p.hurt = 99
                frames(g, 1)
            assert g.collected() == len(g.pickups)
            p.x, p.y = g.level["goal"]["pos"]           # ...then onto the goal
            frames(g, 1)
            if level < len(game.LEVELS) - 1:
                assert g.state == "clear", g.state
                shot(g, f"clear{level + 1}")
                press(g, pygame.K_RETURN)
        assert g.state == "victory", g.state
        frames(g, 5)
        shot(g, "victory")
        print(f"{mode}: all {len(game.LEVELS)} levels cleared, score {g.score}")

    # a demon touching a player costs time; a miracle stuns it; the Bentley makes Crowley immune
    g.new_game("coop")
    press(g, pygame.K_RETURN)
    azi, crowley = g.players
    hound = g.enemies[0]
    before = g.clock_left
    hound.x, hound.y = azi.x + 5, azi.y
    frames(g, 1)
    assert g.hits == 1 and g.clock_left < before - game.HIT_PENALTY + 0.1, (g.hits, before, g.clock_left)
    azi.stun = azi.cd = 0
    press(g, pygame.K_e)
    assert hound.stun > 0, "miracle should stun the hound"
    press(g, pygame.K_RETURN)
    assert crowley.boost > 0, "Enter should summon the Bentley"
    hound.stun, crowley.hurt = 0, 0
    hound.x, hound.y = crowley.x + 5, crowley.y
    frames(g, 1)
    assert g.hits == 1, "the Bentley should make Crowley untouchable"
    print("hits, miracle and Bentley: OK")

    # running out of time ends the game, and retry restarts the level
    g.clock_left = 0.05
    frames(g, 5)
    assert g.state == "over", g.state
    shot(g, "game_over")
    press(g, pygame.K_RETURN)
    assert g.state == "play" and g.clock_left == game.LEVELS[0]["time"]
    press(g, pygame.K_ESCAPE)
    assert g.state == "paused"
    print("game over, retry and pause: OK")
    os.remove(game.SAVE_FILE)
    pygame.quit()
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
