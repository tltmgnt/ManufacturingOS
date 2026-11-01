"""Real-Chromium smoke checks for the offline demo, with screenshots for review.

Install requirements-browser-tests.txt and run `playwright install chromium`.
Execute from the repository root after generating runs/browser-offline-suite.
"""
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from examples.offline_repeatability import compare_runs
from examples.offline_suite_integrity import write_suite_manifest, verify_suite


def main():
    suite = Path("runs/browser-offline-suite").resolve()
    pilot = suite / "repeatability/first"
    root = pilot / "planning"
    screenshots = suite / "screenshots"
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
            page.goto((suite / "index.html").as_uri(), wait_until="load")
            assert page.title() == "ManufacturingOS — offline synthetic suite"
            assert page.locator("tbody tr").count() == 3
            assert page.locator("#overall-result").inner_text() == "PASS"
            assert "No real-system reads" in page.locator(".notice").inner_text()
            assert page.locator("a").count() == 7
            for href in page.locator("a").evaluate_all("links => links.map(link => link.getAttribute('href'))"):
                assert (suite / href).is_file(), f"Missing offline-suite review link: {href}"
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / f"offline-suite-{width}.png"), full_page=True)
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto((pilot / "index.html").as_uri(), wait_until="load")
            assert page.title() == "ManufacturingOS — synthetic pilot rehearsal"
            assert page.locator("tbody tr").count() == 6
            assert "Software rehearsal only" in page.locator(".notice").inner_text()
            assert page.locator("a").count() == 15
            for href in page.locator("a").evaluate_all("links => links.map(link => link.getAttribute('href'))"):
                assert (pilot / href).is_file(), f"Missing combined review link: {href}"
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / f"pilot-{width}.png"), full_page=True)
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto((pilot / "api-failures/index.html").as_uri(), wait_until="load")
            assert page.title() == "Mock API failure rehearsal"
            assert page.locator("tbody tr").count() == 9
            assert "Rejected before study" in page.locator("body").inner_text()
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(screenshots / f"api-failures-{width}.png"), full_page=True)
        for width in (375, 768, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto((root / "index.html").as_uri(), wait_until="load")
            assert page.title() == "Synthetic bracket demo — case comparison"
            assert page.locator("tbody tr").count() == 4
            assert page.locator(".notice").is_visible()
            rows = page.locator("tbody tr")
            assert "HUMAN_REVIEW" in rows.nth(0).inner_text()
            assert "+5" in rows.nth(1).inner_text()
            assert "FAIL" in rows.nth(1).inner_text()
            assert "2 / 3" in rows.nth(2).inner_text()
            assert "MISSED" in rows.nth(2).inner_text()
            assert "REVISION_REQUIRED" in rows.nth(2).inner_text()
            assert "3 / 3" in rows.nth(3).inner_text()
            assert "HUMAN_REVIEW" in rows.nth(3).inner_text()
            assert "MISSED" not in rows.nth(3).inner_text()
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
        for case in ("baseline", "cost-disagreement", "target-miss", "capacity-remedy"):
            page.goto((root / "index.html").as_uri(), wait_until="load")
            page.locator(f'a[href="{case}/study-review.html"]').click()
            page.wait_for_url((root / case / "study-review.html").as_uri())
            assert page.locator("body").inner_text().strip()
            page.screenshot(path=str(screenshots / f"{case}-review.png"), full_page=True)
        assert not errors, errors
        browser.close()
    assert compare_runs(pilot, suite / "repeatability/second")["status"] == "REPEATABLE"
    write_suite_manifest(suite, replace=True)
    verify_suite(suite)
    print("Chromium: 3 viewport checks, 14 local links, 4 review navigations; 16 screenshots saved, including offline-suite, combined and failure reviews at 3 widths.")
    print("Automated browser checks passed; screenshots still require human visual review.")


if __name__ == "__main__":
    main()
