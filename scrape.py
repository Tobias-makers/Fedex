#!/usr/bin/env python3
"""FedEx sista minuten-pris — automatisk priskoll.
 
Kör FedEx öppna prisverktyg (sv-se) headless och läser av
"FAST SISTA MINUTEN-PRIS" för FedEx International Economy®.
 
Rutt:  Sverige 52390 -> Middletown, Pennsylvania 17057, USA
Kolli: 10 st à 18 kg, 60x40x20 cm, "Din förpackning", förvalt datum.
 
Lyckad körning: lägger till en mätpunkt sist i docs/history.json.
Misslyckad körning: sparar screenshot + sidtext i debug/ och avslutar med kod 1.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
 
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
 
URL = "https://www.fedex.com/sv-se/online/rating.html"
HISTORY = Path(__file__).parent / "docs" / "history.json"
DEBUG = Path(__file__).parent / "debug"
 
FROM_POSTAL = "52390"
TO_QUERY = "Middletown, 17057"
TO_SUGGESTION = "Middletown, Pennsylvania 17057, USA"
PACKAGES = "10"
WEIGHT = "18"
DIMS = ("60", "40", "20")
TOTAL_KG = 180
 
 
def log(msg):
    print(f"[priskoll] {msg}", flush=True)
 
 
def dismiss_cookies(page):
    """Stäng ev. cookiebanner (välj det mest integritetsvänliga alternativet)."""
    selectors = [
        "#onetrust-reject-all-handler",
        "button:has-text('Avvisa alla')",
        "button:has-text('Avvisa')",
        "#onetrust-accept-btn-handler",  # sista utväg om ingen avvisa-knapp finns
        "button:has-text('Godkänn alla')",
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible(timeout=1500):
                btn.click(timeout=3000)
                log(f"cookiebanner stängd via {sel}")
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue
 
 
def visible_inputs(page):
    """Lista synliga input-fält med metadata, i DOM-ordning."""
    return page.eval_on_selector_all(
        "input",
        """els => els
            .filter(e => e.offsetParent !== null && e.type !== 'checkbox' && e.type !== 'radio')
            .map(e => ({
                id: e.id || '',
                name: e.name || '',
                aria: e.getAttribute('aria-label') || '',
                ph: e.placeholder || '',
                value: e.value,
                type: e.type,
            }))""",
    )
 
 
def find_index(inputs, *keywords):
    for i, item in enumerate(inputs):
        blob = " ".join([item["id"], item["name"], item["aria"], item["ph"]]).lower()
        if any(k.lower() in blob for k in keywords):
            return i
    return None
 
 
def fill_nth_visible(page, idx, value):
    loc = page.locator(
        "input:visible:not([type=checkbox]):not([type=radio])"
    ).nth(idx)
    loc.click()
    loc.press("ControlOrMeta+a")
    loc.type(value, delay=40)
 
 
def run():
    DEBUG.mkdir(exist_ok=True)
    with sync_playwright() as p:
        # Firefox i icke-headless läge (körs mot virtuell skärm, xvfb, i CI) —
        # betydligt svårare för botskydd att särskilja från en vanlig webbläsare.
        browser = p.firefox.launch(headless=False)
        ctx = browser.new_context(
            locale="sv-SE",
            timezone_id="Europe/Stockholm",
            viewport={"width": 1440, "height": 900},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = ctx.new_page()
        try:
            log("laddar prissidan ...")
            page.goto(URL, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(6000)
            dismiss_cookies(page)
 
            # --- FRÅN: öppna manuell inmatning ---
            fran = page.get_by_role("textbox").first
            fran.click()
            fran.type("Hammaregatan 5, 52390", delay=40)
            page.wait_for_timeout(2000)
            manual = page.get_by_text("ANGE DEN SJÄLV", exact=False).first
            if manual.count() and manual.is_visible():
                manual.click()
            else:
                page.get_by_text("ange hela adressen själv", exact=False).first.click()
            page.wait_for_timeout(2000)
            log("manuell inmatning öppen")
 
            # --- Postnummer ---
            inputs = visible_inputs(page)
            log("synliga fält: " + json.dumps(inputs, ensure_ascii=False))
            i_postal = find_index(inputs, "postnummer", "zip", "postal")
            if i_postal is None:
                raise RuntimeError("hittade inte postnummerfältet")
            fill_nth_visible(page, i_postal, FROM_POSTAL)
            log("postnummer ifyllt")
 
            # --- TILL ---
            inputs = visible_inputs(page)
            i_till = find_index(inputs, "mottagaradress", "toGoogle", "destination")
            if i_till is None:
                i_till = len(inputs) - 1  # sista synliga textfältet
            fill_nth_visible(page, i_till, TO_QUERY)
            page.wait_for_timeout(2500)
            sugg = page.get_by_text(TO_SUGGESTION, exact=False).first
            sugg.click()
            page.wait_for_timeout(1500)
            # ibland krävs två klick för att valet ska registreras
            sugg2 = page.get_by_text(TO_SUGGESTION, exact=False).first
            if sugg2.count() and sugg2.is_visible():
                sugg2.click()
                page.wait_for_timeout(1500)
            log("destination vald")
 
            # --- FORTSÄTT ---
            page.get_by_role("button", name=re.compile("FORTSÄTT", re.I)).first.click()
            page.wait_for_timeout(4000)
            log("paketformuläret öppet")
 
            # --- Paketuppgifter ---
            inputs = visible_inputs(page)
            log("paketfält: " + json.dumps(inputs, ensure_ascii=False))
            i_qty = find_index(inputs, "antal paket", "quantity", "package-count")
            i_wt = find_index(inputs, "paketets vikt", "weight", "vikt")
            if i_qty is None or i_wt is None:
                raise RuntimeError("hittade inte paket-/viktfälten")
            i_l = find_index(inputs, "längd", "length")
            i_w = find_index(inputs, "bredd", "width")
            i_h = find_index(inputs, "höjd", "height")
            if i_l is None or i_w is None or i_h is None:
                # dimensionsfälten ligger direkt efter viktfältet i DOM-ordning
                i_l, i_w, i_h = i_wt + 1, i_wt + 2, i_wt + 3
                log("dimensionsfält antas ligga direkt efter viktfältet")
 
            fill_nth_visible(page, i_qty, PACKAGES)
            fill_nth_visible(page, i_wt, WEIGHT)
            for idx, val in zip((i_l, i_w, i_h), DIMS):
                fill_nth_visible(page, idx, val)
            page.wait_for_timeout(1000)
 
            body = page.inner_text("body")
            if "180 KG" not in body.replace(" ", " "):
                log("VARNING: totalvikt 180 KG syns inte — fortsätter ändå")
 
            # --- VISA PRISER ---
            page.get_by_role("button", name=re.compile("visa priser", re.I)).first.click()
            log("väntar på priser ...")
            page.wait_for_timeout(12000)
 
            body = page.inner_text("body")
            return parse(body)
        except Exception:
            try:
                page.screenshot(path=str(DEBUG / "fel.png"), full_page=True)
                (DEBUG / "sidtext.txt").write_text(page.inner_text("body"), encoding="utf-8")
                log(f"debugfiler sparade i {DEBUG}/")
            except Exception as e2:
                log(f"kunde inte spara debugfiler: {e2}")
            raise
        finally:
            browser.close()
 
 
def parse(body):
    text = body.replace(" ", " ").replace(" ", " ")
    m = re.search(
        r"FAST SISTA MINUTEN-PRIS\s+LEVERERAS INNAN\s+[\d:.]+\s+"
        r"FedEx International Economy®.*?([\d ]+,\d{2})\s*kr",
        text,
        re.S,
    )
    if not m:
        raise RuntimeError("hittade inget sista minuten-pris för Economy i resultatet")
    price = float(m.group(1).replace(" ", "").replace(",", "."))
 
    dm = re.search(r"som skickats\s*\n?\s*([^\n]+)", text)
    ship_date = dm.group(1).strip() if dm else "okänt"
    return price, ship_date
 
 
def save(price, ship_date):
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    now = datetime.now(ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%dT%H:%M")
    history.append({"ts": now, "price": price, "ship_date": ship_date})
    HISTORY.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    prev = history[-2]["price"] if len(history) > 1 else None
    delta = f" ({price - prev:+.2f} kr sedan förra)" if prev is not None else ""
    log(f"KLART: {price:.2f} kr = {price / TOTAL_KG:.2f} kr/kg, avgång {ship_date}{delta}")
 
 
if __name__ == "__main__":
    try:
        price, ship_date = run()
    except Exception as e:
        log(f"FEL: {e}")
        sys.exit(1)
    save(price, ship_date)
