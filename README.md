# Good Omens: The Ineffable Plan (Python / pygame)

A three-level cartoon game inspired by *Good Omens*. Play as Aziraphale, as Crowley,
or as both in co-op on one keyboard. Stop Armageddon before the clock runs out.

All the art is drawn by code (`generate_sprites.py`) and all the sound effects are
synthesised in code, so the game has no image or audio files from anywhere else.

## Just want to play?

Run **`dist/GoodOmens.exe`** (Windows). It's a single file with nothing to install, so
you can send it to anyone.

The first time someone runs it, Windows may show **"Windows protected your PC"**.
That's because the exe isn't code-signed. Click **More info → Run anyway**. Some
antivirus tools are also suspicious of PyInstaller-built games; that's a known
false alarm with unsigned exes.

## The game

| Level | Goal | Who's after you |
|-------|------|-----------------|
| 1. Tadfield | Collect 4 of Agnes Nutter's prophecy pages, take them to Jasmine Cottage | The Hellhound |
| 2. Soho | The bookshop is on fire. Rescue 5 rare books, get to the Bentley | Hastur and Ligur |
| 3. Tadfield Airbase | Grab War's Sword, Famine's Scales and Pollution's Crown, then reach Adam | All of them, faster |

The rules:

- Each level has an **Armageddon clock**. Enemies speed up as it runs down.
- Getting caught costs **8 seconds**. **Crêpes** give you **+8 seconds**.
- **Aziraphale's miracle** stuns every demon nearby for 3 seconds (9 s cooldown).
- **Crowley's Bentley** makes him fast and untouchable for 3 seconds (10 s cooldown).
- **Score per level:** 100 per item, 10 per second left, and a 500 bonus if you never
  get caught. Your best score is saved in `%APPDATA%\GoodOmensGame\save.json`.

### Controls

| | Move | Ability |
|---|---|---|
| One player | WASD or arrow keys | Space (or E / Enter) |
| Two players: Aziraphale | WASD | E |
| Two players: Crowley | Arrow keys | Enter |

Other keys: `Esc` / `P` pause, `M` sound on/off, `F11` fullscreen. Menus also work
with the mouse.

## What's in this folder

| File / folder           | What it is |
|-------------------------|------------|
| `game.py`               | The game: levels, characters, menus, sound, HUD. |
| `generate_sprites.py`   | Draws every character, the Bentley and the item icons as PNGs into `assets/`. |
| `assets/sprites/`       | Sprite sheets: 4 columns × 2 rows (idle, walk). `cast_preview.png` shows them all. |
| `assets/items/`         | Pickup icons. |
| `smoke_test.py`         | Plays through every level in every mode with no window, to catch crashes. |
| `build_exe.py`          | Packages the game into `dist/GoodOmens.exe`. |
| `preview.py`            | Older animation test: walk Aziraphale and Crowley around a field. |
| `requirements.txt`      | Packages needed to play from source. |
| `requirements-dev.txt`  | Those plus the packages needed to build the exe. |

## Running from source

Requires **Python 3.10+**. It was developed with Python 3.13, pygame-ce 2.5.8 and
PyInstaller 6.22.3.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python game.py
```

On macOS / Linux, use `.venv/bin/python` instead.

### Python packages used

| Package | Why |
|---------|-----|
| [`pygame-ce`](https://pyga.me/) | Graphics, window, keyboard and mouse input, sound. It's the community edition of pygame, imported as `import pygame`. |
| [`pyinstaller`](https://pyinstaller.org/) | Build only: bundles Python, pygame and `assets/` into one exe. |

Everything else is from the Python standard library. Don't install the original
`pygame` package alongside `pygame-ce`, because they clash.

## Making changes

1. **Art:** edit `generate_sprites.py`, run it, then check `assets/sprites/cast_preview.png`.
2. **Levels:** edit the `LEVELS` list in `game.py`. Each level is plain data: its
   furniture (`house`, `shop`, `tree`, `hedge`, `lamp`, `crate`, ...), items, goal,
   enemies and their patrol routes, and time limit.
3. **Test:** run `python smoke_test.py`. It must end with `SMOKE TEST PASSED`.
4. **Rebuild the exe:** run `python build_exe.py`. PyInstaller's temporary files go in
   your temp folder, because OneDrive locks them mid-sync.

## Sharing

- `dist/` is git-ignored. To share the exe from GitHub, attach `GoodOmens.exe` to a
  **GitHub Release** rather than committing it.
- The exe is Windows-only. Mac or Linux players can run it from source.
- This is a non-commercial fan project. Share it for free and don't sell it.

## Credits

Fan project based on *Good Omens* by Terry Pratchett and Neil Gaiman, and the Amazon /
BBC TV adaptation. Not affiliated with or endorsed by the authors or studios.
