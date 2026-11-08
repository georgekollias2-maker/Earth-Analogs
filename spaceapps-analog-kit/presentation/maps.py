"""Στιγμιότυπα των χαρτών Γη ↔ Άρης (δοκιμή ορυκτολογίας) από το site, για το PDF.
Χρήση: python -m http.server 8765 -d docs   (σε άλλο τερματικό, από τον φάκελο του kit)
       python presentation/maps.py presentation"""
import sys, asyncio
from playwright.async_api import async_playwright
OUT = sys.argv[1]
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1500, "height": 1200}, device_scale_factor=2)
        await pg.goto("http://localhost:8765/analogs.html"); await pg.wait_for_timeout(800)
        for idx, name in ((0, "gale"), (1, "jezero")):
            await pg.select_option("#target", index=idx); await pg.wait_for_timeout(300)
            await pg.click("text=Ορυκτολογία / όργανα"); await pg.wait_for_timeout(600)
            await pg.locator("#map").screenshot(path=f"{OUT}/map_{name}.png")
        await b.close()
asyncio.run(main())
