"""
Record the README demo GIF against the production site.

Drives the real demo flow with Playwright (system Chrome, headless):
pressure map → Risk view → sensor gain curve → ChatOps question with
tool chips and map highlights. Frames are assembled into assets/demo.gif
with Pillow.

Run: .venv/bin/python scripts/record_demo.py [url]
"""

import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://bentonville-gas-sim.vercel.app"
OUT = Path(__file__).parent.parent / "assets" / "demo.gif"
WIDTH = 960  # output GIF width

frames: list[tuple[Image.Image, int]] = []  # (frame, duration_ms)


def snap(page, hold_ms: int) -> None:
    png = page.screenshot(type="png")
    img = Image.open(io.BytesIO(png)).convert("RGB")
    ratio = WIDTH / img.width
    img = img.resize((WIDTH, int(img.height * ratio)), Image.LANCZOS)
    frames.append((img, hold_ms))


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1360, "height": 850})
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(7000)  # map tiles + simulation

        # 1. Landing: pressure-colored street-true network
        snap(page, 2200)

        # 2. Risk view
        page.get_by_role("button", name="Risk", exact=True).click()
        page.wait_for_timeout(2500)
        snap(page, 2400)

        # 3. FEMA flood overlay on top of risk
        page.get_by_role("button", name="FEMA flood zones").click()
        page.wait_for_timeout(2000)
        snap(page, 2000)

        # 4. Sensor planning card (scroll down)
        page.get_by_text("Sensor Planning").scroll_into_view_if_needed()
        page.wait_for_timeout(1800)
        snap(page, 2400)

        # 5. Back to top; ask the agent the flagship question
        page.keyboard.press("Home")
        page.wait_for_timeout(800)
        page.get_by_role("button", name="Pressure", exact=True).click()
        chip = page.get_by_role("button").filter(
            has_text="How does gas pressure look today"
        )
        chip.click()
        # capture the stream: chips appear, text grows, map highlights
        for _ in range(14):
            page.wait_for_timeout(2000)
            snap(page, 900)
        page.wait_for_timeout(2500)
        snap(page, 3500)  # final answer + highlighted pipes, long hold

        browser.close()

    OUT.parent.mkdir(exist_ok=True)
    imgs = [f.quantize(colors=128, dither=Image.FLOYDSTEINBERG) for f, _ in frames]
    imgs[0].save(
        OUT,
        save_all=True,
        append_images=imgs[1:],
        duration=[d for _, d in frames],
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
