"""
Generate a demo GIF for the README by automating the Chem Editor via Playwright.

Prerequisites (run once):
    pip install playwright Pillow
    playwright install chromium

Usage (make sure the Chem Editor server is running first):
    python generate_demo_gif.py

The GIF will be saved to docs/demo.gif
"""

import io
import time
from pathlib import Path
from PIL import Image

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install dependencies first:")
    print("  pip install playwright Pillow")
    print("  playwright install chromium")
    raise SystemExit(1)

OUTPUT_DIR = Path(__file__).parent / "docs"
OUTPUT_DIR.mkdir(exist_ok=True)
GIF_PATH = OUTPUT_DIR / "demo.gif"

# Compounds to demonstrate: (name, SMILES)
COMPOUNDS = [
    ("Benzene", "c1ccccc1"),
    ("Aspirin", "CC(=O)Oc1ccccc1C(=O)O"),
    ("Caffeine", "Cn1c(=O)c2c(ncn2C)n(C)c1=O"),
]


def capture(page) -> Image.Image:
    """Take a screenshot and return as PIL Image."""
    buf = page.screenshot(type="png")
    return Image.open(io.BytesIO(buf))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1400, "height": 700})

        # Handle dialogs (confirm on Reset All, etc.)
        page.on("dialog", lambda d: d.accept())

        page.goto("http://127.0.0.1:8000")
        page.wait_for_timeout(4000)  # wait for Ketcher iframe to load

        frames: list[Image.Image] = []
        durations: list[int] = []

        # --- Reset existing data ---
        try:
            page.click("text=Reset All", timeout=2000)
            page.wait_for_timeout(1500)
        except Exception:
            pass
        page.reload()
        page.wait_for_timeout(4000)

        # --- Frame 1: Empty editor ---
        frames.append(capture(page))
        durations.append(2000)
        print(f"[1/{4 + len(COMPOUNDS) * 2}] Empty editor")

        # --- Draw & stock each compound ---
        for i, (name, smiles) in enumerate(COMPOUNDS):
            # Set molecule via Ketcher API
            page.evaluate(f"""
                (async () => {{
                    const frame = document.getElementById('ketcher-frame');
                    const ketcher = frame.contentWindow.ketcher;
                    await ketcher.setMolecule('{smiles}');
                }})();
            """)
            page.wait_for_timeout(1500)

            # Type name
            name_input = page.locator("input[placeholder*='Name'], #name-input").first
            name_input.fill(name)
            page.wait_for_timeout(300)

            # Capture: structure drawn + name filled
            frames.append(capture(page))
            durations.append(1500)
            print(f"  [{len(frames)}/...] {name} drawn")

            # Click Stock button
            page.click("button:has-text('Stock')")
            page.wait_for_timeout(2000)

            # Capture: compound stocked
            frames.append(capture(page))
            durations.append(1500)
            print(f"  [{len(frames)}/...] {name} stocked")

        # --- Hover over first card to show tooltip ---
        cards = page.locator(".compound-thumb")
        if cards.count() > 0:
            cards.first.hover()
            page.wait_for_timeout(1200)
            frames.append(capture(page))
            durations.append(2500)
            print(f"  [{len(frames)}/...] Tooltip shown")

        # --- Final overview ---
        page.mouse.move(700, 500)
        page.wait_for_timeout(500)
        frames.append(capture(page))
        durations.append(3000)
        print(f"  [{len(frames)}/...] Final overview")

        browser.close()

    # --- Assemble GIF ---
    if len(frames) < 2:
        print("ERROR: Not enough frames captured!")
        return

    # Convert RGBA to RGB (GIF doesn't support alpha)
    rgb_frames = []
    for f in frames:
        if f.mode == "RGBA":
            bg = Image.new("RGB", f.size, (255, 255, 255))
            bg.paste(f, mask=f.split()[3])
            rgb_frames.append(bg)
        else:
            rgb_frames.append(f.convert("RGB"))

    # Resize to reasonable dimensions for README
    target_w = 800
    ratio = target_w / rgb_frames[0].width
    target_h = int(rgb_frames[0].height * ratio)
    resized = [f.resize((target_w, target_h), Image.LANCZOS) for f in rgb_frames]

    # Save GIF
    resized[0].save(
        GIF_PATH,
        save_all=True,
        append_images=resized[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )

    size_kb = GIF_PATH.stat().st_size / 1024
    print(f"\nDone! GIF saved to: {GIF_PATH}")
    print(f"Frames: {len(resized)}, Size: {size_kb:.0f} KB")


if __name__ == "__main__":
    run()
