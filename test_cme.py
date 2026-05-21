from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]
    page = context.pages[0]
    print(f"URL ปัจจุบัน: {page.url}")
    print(f"Title: {page.title()}")
    print("✅ เชื่อมต่อสำเร็จ!")
    browser.close()
