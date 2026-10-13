from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
shots = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})

    # 1. Login
    page.goto(BASE + "/accounts/login/")
    page.screenshot(path="shot_1_login.png")
    shots.append("shot_1_login.png")
    page.fill('input[name="username"]', "testmgr")
    page.fill('input[name="password"]', "demo12345")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    page.screenshot(path="shot_2_dashboard.png")
    shots.append("shot_2_dashboard.png")

    # 2. Order detail with calc table
    page.goto(BASE + "/orders/1/")
    page.wait_for_load_state("networkidle")
    page.screenshot(path="shot_3_order_detail.png", full_page=True)
    shots.append("shot_3_order_detail.png")

    # 3. Live recalculation: change contractor cost of first editable row
    row = page.locator("tr.calc-row").nth(1)
    before_total = row.locator(".calc-out-total").inner_text()
    row.locator("input[name='contractor_cost']").fill("1000")
    row.locator("input[name='markup_percent']").fill("50")
    row.locator("input[name='tax_rate']").fill("10")
    # clear manual price so auto-calc kicks in? price input has value; set it to trigger recompute from markup
    row.locator("input[name='price']").fill("")
    row.locator("input[name='price']").dispatch_event("input")
    page.wait_for_timeout(300)
    after_total = row.locator(".calc-out-total").inner_text()
    print("LIVE RECALC:", before_total, "->", after_total)
    print("MARKUP RUB:", row.locator(".calc-out-markup-rub").inner_text())
    print("MARKUP PCT:", row.locator(".calc-out-markup-pct").inner_text())
    page.screenshot(path="shot_4_live_recalc.png", full_page=True)
    shots.append("shot_4_live_recalc.png")

    # 4. Save row to server
    row.locator("button.calc-save").click()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="shot_5_after_save.png", full_page=True)
    shots.append("shot_5_after_save.png")

    # verify persisted values
    row2 = page.locator("tr.calc-row").nth(1)
    print("PERSISTED cost:", row2.locator("input[name='contractor_cost']").input_value(),
          "markup:", row2.locator("input[name='markup_percent']").input_value(),
          "total:", row2.locator(".calc-out-total").inner_text())

    # 5. Documents upload section
    docs = page.locator("text=Документы")
    if docs.count():
        docs.first.scroll_into_view_if_needed()
        page.screenshot(path="shot_6_documents.png")
        shots.append("shot_6_documents.png")

    browser.close()
print("SHOTS:", shots)
