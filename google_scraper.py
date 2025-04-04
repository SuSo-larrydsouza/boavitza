from playwright.sync_api import sync_playwright
import json

url = "https://sustainability.google/reports/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url)
    page.wait_for_timeout(5000)  # wait for 5 sec to let JS render

    # Get the page content
    content = page.content()

    # Extract JSON inside the <script id="initial-data">
    json_text = page.locator('script#initial-data').inner_text()
    data_blob = json.loads(json_text)

    print(f"Found {len(data_blob['allRepoItems'])} reports!")

    # Optionally dump to file
    with open('google_reports.json', 'w') as f:
        json.dump(data_blob, f, indent=2)

    browser.close()
