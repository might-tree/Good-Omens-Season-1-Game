"""Package the game as a single Windows exe:  dist/GoodOmens.exe

Run:  python build_exe.py   (needs the packages in requirements-dev.txt)
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
# PyInstaller's scratch files live outside the project: OneDrive locks them mid-sync
BUILD = os.path.join(tempfile.gettempdir(), "goodomens-build")


def make_icon():
    """Crowley's and Aziraphale's heads on a dark disc, saved as a 256px .ico."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    icon = pygame.Surface((256, 256), pygame.SRCALPHA)
    pygame.draw.circle(icon, (36, 26, 22), (128, 128), 124)
    pygame.draw.circle(icon, (214, 176, 64), (128, 128), 124, 8)
    heads = (("aziraphale", (22, 12, 52, 57), (78, 136)), ("crowley", (22, 0, 52, 58), (178, 124)))
    for name, region, centre in heads:
        sheet = pygame.image.load(os.path.join(HERE, "assets", "sprites", name + ".png"))
        head = pygame.transform.smoothscale_by(sheet.subsurface(region), 2.3)
        icon.blit(head, head.get_rect(center=centre))
    os.makedirs(BUILD, exist_ok=True)
    png = os.path.join(BUILD, "icon.png")
    pygame.image.save(icon, png)
    with open(png, "rb") as f:
        data = f.read()
    ico = os.path.join(BUILD, "icon.ico")
    with open(ico, "wb") as f:   # an .ico holding one 256x256 PNG image
        f.write(struct.pack("<HHH", 0, 1, 1))
        f.write(struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(data), 22))
        f.write(data)
    pygame.quit()
    return ico


def main():
    if not os.path.exists(os.path.join(HERE, "assets", "sprites", "hellhound.png")):
        subprocess.run([sys.executable, os.path.join(HERE, "generate_sprites.py")], check=True)
    ico = make_icon()
    import PyInstaller.__main__
    PyInstaller.__main__.run([
        os.path.join(HERE, "game.py"),
        "--name", "GoodOmens",
        "--onefile",
        "--windowed",
        "--icon", ico,
        "--add-data", f"{os.path.join(HERE, 'assets')}{os.pathsep}assets",
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", BUILD,
        "--specpath", BUILD,
        "--noconfirm",
        "--clean",
    ])
    print("\nBuilt", os.path.join(HERE, "dist", "GoodOmens.exe"))


if __name__ == "__main__":
    main()
