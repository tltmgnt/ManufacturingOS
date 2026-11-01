"""Real-Chromium smoke checks for the offline demo, with screenshots for review.

Install requirements-browser-tests.txt and run `playwright install chromium`.
Execute from the repository root after generating runs/browser-demo.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    root = Path("runs/browser-demo").resolve()
    screenshots = root / "screenshots"
    screenshots.mkdir(exist_ok=False)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        # Offline pages must not depend on external services or assets.
        page.route("http://**/*", lambda route: route.abort())
        page.route("https://**/*", lambda route: route.abort())
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto((root / "index.html").as_uri(), wait_until="load")
            assert page.title() == "Synthetic bracket demo — case comparison"
            assert page.locator("tbody tr").count() == 3
            assert page.locator(".notice").is_visible()
            rows = page.locator("tbody tr")
            assert "HUMAN_REVIEW" in rows.nth(0).inner_text()
            assert "+5" in rows.nth(1).inner_text()
            assert "FAIL" in rows.nth(1).inner_text()
            assert "2 / 3" in rows.nth(2).inner_text()
            assert "MISSED" in rows.nth(2).inner_text()
            assert "REVISION_REQUIRED" in rows.nth(2).inner_text()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Page overflows viewport"
            for href in page.locator("a").evaluate_all("links => links.map(link => link.getAttribute('href'))"):
                assert (root / href).is_file(), f"Missing local link: {href}"
            for cell in page.locator("tbody td").all():
                box = cell.bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= width, "Case cell clipped off-screen"
            page.locator('a[href="target-miss/study-review.html"]').scroll_into_view_if_needed()
            assert page.locator('a[href="target-miss/study-review.html"]').is_visible()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(screenshots / f"comparison-{width}.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        for case in ("baseline", "cost-disagreement", "target-miss"):
            page.goto((root / "index.html").as_uri(), wait_until="load")
            page.locator(f'a[href="{case}/study-review.html"]').click()
            page.wait_for_url((root / case / "study-review.html").as_uri())
            assert page.locator("body").inner_text().strip()
            page.screenshot(path=str(screenshots / f"{case}-review.png"), full_page=True)
        assert not errors, errors
        browser.close()
    print("Chromium: 3 viewport checks, 11 local links, 3 review navigations; 6 screenshots saved.")
    print("Automated browser checks passed; screenshots still require human visual review.")


if __name__ == "__main__":
    main()
