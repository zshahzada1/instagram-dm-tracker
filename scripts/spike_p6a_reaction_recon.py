#!/usr/bin/env python3
"""
P6a — Reaction bar diagnostic spike (READ-ONLY).

Goal: Find the correct DOM interaction sequence that makes Instagram's
reaction bar appear on a DM message bubble. We try 5 strategies in order
and scan the DOM after each. No reactions are fired. No mutations are sent.

Architecture rule: READ-ONLY. Passive DOM observation only.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import time
import os
import re
import random
from pathlib import Path
from datetime import datetime

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox not installed. Run: pip install camoufox[geoip]")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROBE_SELECTORS = [
    '[aria-label="React to message"]',
    '[aria-label*="React"]',
    '[aria-label*="react"]',
    'button[aria-label*="emoji"]',
    '[aria-label*="emoji"]',
    '[role="toolbar"]',
    '[role="toolbar"] button',
    'div[role="toolbar"]',
    '[data-visualcompletion="ignore-dynamic"]',
    'button:has(svg)',
    '[aria-label="More"]',
    '[aria-label="Like"]',
]

MEDIA_IMG_SELECTOR = 'img[src*="cdninstagram"][src*="-15/"]'
MSG_LIST_SELECTOR = '[data-pagelet="IGDMessagesList"]'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_cookies(path="test-cookies/cookies.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cookies not found at {path}")
    with open(path, "r") as f:
        raw = json.load(f)
    out = []
    for c in raw:
        conv = {
            "name": c["name"], "value": c["value"],
            "domain": c["domain"], "path": c["path"],
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", True),
        }
        if c.get("expirationDate"):
            conv["expires"] = int(c["expirationDate"])
        ss = c.get("sameSite", "unspecified")
        conv["sameSite"] = {
            "no_restriction": "None", "none": "None",
            "lax": "Lax", "strict": "Strict",
        }.get(ss, "None")
        out.append(conv)
    return out


def jitter(lo=1.5, hi=3.0):
    d = random.uniform(lo, hi)
    time.sleep(d)
    return d


def check_blockers(page):
    found = []
    checks = [
        ('text=Suspicious Login', 'Suspicious Login'),
        ('text=Checkpoint', 'Checkpoint'),
        ('iframe[src*="captcha"]', 'CAPTCHA'),
        ('text=unusual', 'Unusual activity'),
    ]
    for sel, label in checks:
        try:
            if page.query_selector(sel):
                found.append(label)
        except Exception:
            pass
    return found


def handle_blockers(page, tag="blocker"):
    found = check_blockers(page)
    if not found:
        return False
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss = f"artifacts/{tag}_{ts}.png"
    page.screenshot(path=ss)
    report = (
        f"# Blocker — {', '.join(found)}\n\n"
        f"**Time:** {datetime.now().isoformat()}\n"
        f"**Screenshot:** {ss}\n\n"
        f"## Action Required\n"
        f"1. Complete the challenge in the browser window.\n"
        f"2. Re-export cookies if session expired.\n"
    )
    rp = f"artifacts/{tag}_{ts}.md"
    Path(rp).write_text(report, encoding="utf-8")
    print(f"\n[BLOCKER] {', '.join(found)}")
    print(f"  Screenshot: {ss}")
    print(f"  Report:     {rp}")
    return True


def dismiss_popups(page):
    for selector in ['button:has-text("Not Now")', '[aria-label="Close"]']:
        try:
            el = page.query_selector(selector)
            if el and el.is_visible():
                el.click()
                time.sleep(0.8)
        except Exception:
            pass
    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception:
        pass


def scan_dom(page):
    """
    Scan the DOM for each probe selector.
    Returns dict: selector → {"count": N, "visible": bool, "html_snippet": "..."}
    """
    results = {}
    msg_list = page.locator(MSG_LIST_SELECTOR)
    for sel in PROBE_SELECTORS:
        try:
            loc = msg_list.locator(sel)
            count = loc.count()
            if count > 0:
                visible = False
                snippet = ""
                try:
                    visible = loc.first.is_visible()
                    snippet = loc.first.evaluate("el => el.outerHTML")[:300]
                except Exception:
                    pass
                results[sel] = {
                    "count": count,
                    "visible": visible,
                    "html_snippet": snippet,
                }
        except Exception as e:
            pass
    return results


def dom_scan_summary(results):
    """One-line summary of what was found."""
    visible = [s for s, r in results.items() if r.get("visible")]
    hidden = [s for s, r in results.items() if not r.get("visible")]
    parts = []
    if visible:
        parts.append(f"VISIBLE: {', '.join(visible)}")
    if hidden:
        parts.append(f"HIDDEN: {', '.join(hidden)}")
    return " | ".join(parts) if parts else "NOTHING FOUND"


def save_dom_dump(page, path):
    """Dump the full outerHTML of the message list container."""
    try:
        html = page.locator(MSG_LIST_SELECTOR).first.evaluate("el => el.outerHTML")
        Path(path).write_text(html, encoding="utf-8")
        print(f"  DOM dump saved: {path} ({len(html)} chars)")
    except Exception as e:
        print(f"  [WARN] DOM dump failed: {e}")


def screenshot(page, path):
    page.screenshot(path=path)
    print(f"  Screenshot: {path}")


def find_media_bubbles(page):
    """
    Find all media bubbles using the confirmed working selector.
    Returns list of Playwright locators (img elements with naturalHeight > 50).
    """
    all_imgs = page.locator(MEDIA_IMG_SELECTOR).all()
    bubbles = []
    for img in all_imgs:
        try:
            box = img.bounding_box()
            if not box:
                continue
            # Also check naturalHeight to filter tiny images
            nh = img.evaluate("el => el.naturalHeight")
            if nh and nh > 50:
                bubbles.append(img)
        except Exception:
            pass
    return bubbles


def extract_bubble_fingerprint(page, img, index):
    """
    Try to extract fingerprint data from a media bubble and its surrounding DOM.
    Returns dict with what was found.
    """
    result = {
        "bubble_index": index,
        "img_src_prefix": "",
        "poster_handle": None,
        "time_element": None,
        "has_link_nearby": False,
    }
    try:
        src = img.get_attribute("src") or ""
        result["img_src_prefix"] = src[:80]
    except Exception:
        pass

    # Walk up from img to find the bubble container, then look for <a href="/handle/">
    try:
        # Get the img's parent chain
        parent_chain = img.evaluate("""el => {
            const chain = [];
            let cur = el;
            for (let i = 0; i < 8 && cur && cur !== document.body; i++) {
                chain.push(cur.tagName + (cur.className ? '.' + cur.className.split(' ').slice(0,2).join('.') : ''));
                cur = cur.parentElement;
            }
            return chain;
        }""")
        result["parent_chain"] = parent_chain
    except Exception:
        pass

    # Look for poster handle link near the bubble
    try:
        # Get a broader ancestor, then search within it
        ancestor = img.locator("xpath=ancestor::div[contains(@class,'x')]").first
        links = ancestor.locator("a[href*='/']").all()
        for link in links:
            try:
                href = link.get_attribute("href") or ""
                # Match profile links like /handle/
                m = re.match(r'^/([\w.]+)/?$', href)
                if m and m.group(1) not in ("direct", "p", "reel", "stories", "explore"):
                    result["poster_handle"] = m.group(1)
                    result["has_link_nearby"] = True
                    break
            except Exception:
                pass
    except Exception:
        pass

    # Look for <time> element
    try:
        time_el = img.locator("xpath=ancestor::div[contains(@class,'x')]//time").first
        dt = time_el.get_attribute("datetime")
        if dt:
            result["time_element"] = dt
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Strategy runners — each returns (label, scan_results, screenshot_path)
# ---------------------------------------------------------------------------

def strategy_A_direct_hover(page, img):
    print("\n--- Strategy A: Direct image hover ---")
    img.scroll_into_view_if_needed()
    time.sleep(0.5)
    img.hover()
    time.sleep(3.0)
    ss = "artifacts/p6a_strategy_A.png"
    screenshot(page, ss)
    results = scan_dom(page)
    print(f"  Result: {dom_scan_summary(results)}")
    return "A_direct_hover", results, ss


def strategy_B_parent_hover(page, img):
    print("\n--- Strategy B: Parent element hover ---")
    results = {}
    # Walk up to 2nd, 3rd, 4th parent
    for level in [2, 3, 4]:
        print(f"  Trying level {level} parent...")
        try:
            xpath = "/".join([".."] * level)
            parent = img.locator(f"xpath={xpath}").first
            parent.scroll_into_view_if_needed()
            time.sleep(0.3)
            parent.hover()
            time.sleep(3.0)
            scan = scan_dom(page)
            visible_found = any(r.get("visible") for r in scan.values())
            print(f"    Level {level} result: {dom_scan_summary(scan)}")
            # Merge results — keep anything new
            for k, v in scan.items():
                if k not in results:
                    results[k] = v
            if visible_found:
                ss = f"artifacts/p6a_strategy_B_level{level}.png"
                screenshot(page, ss)
                return f"B_parent_hover_level{level}", scan, ss
        except Exception as e:
            print(f"    Level {level} failed: {e}")

    ss = "artifacts/p6a_strategy_B.png"
    screenshot(page, ss)
    return "B_parent_hover", results, ss


def strategy_C_mouse_move(page, img):
    print("\n--- Strategy C: Mouse move instead of hover ---")
    try:
        box = img.bounding_box()
        if box:
            page.mouse.move(
                box['x'] + box['width'] / 2,
                box['y'] + box['height'] / 2
            )
            time.sleep(3.0)
    except Exception as e:
        print(f"  [ERROR] Mouse move failed: {e}")
    ss = "artifacts/p6a_strategy_C.png"
    screenshot(page, ss)
    results = scan_dom(page)
    print(f"  Result: {dom_scan_summary(results)}")
    return "C_mouse_move", results, ss


def strategy_D_click_then_hover(page, img):
    print("\n--- Strategy D: Click to focus, then hover ---")
    try:
        img.click()
        time.sleep(1.0)
        img.hover()
        time.sleep(3.0)
    except Exception as e:
        print(f"  [ERROR] Click-then-hover failed: {e}")
    ss = "artifacts/p6a_strategy_D.png"
    screenshot(page, ss)
    results = scan_dom(page)
    print(f"  Result: {dom_scan_summary(results)}")
    return "D_click_then_hover", results, ss


def strategy_E_long_hover(page, img):
    print("\n--- Strategy E: Long hover (8 seconds) ---")
    try:
        img.hover()
        time.sleep(8.0)
    except Exception as e:
        print(f"  [ERROR] Long hover failed: {e}")
    ss = "artifacts/p6a_strategy_E.png"
    screenshot(page, ss)
    results = scan_dom(page)
    print(f"  Result: {dom_scan_summary(results)}")
    return "E_long_hover", results, ss


def strategy_manual_check(page):
    print("\n" + "=" * 60)
    print("MANUAL CHECK: In the Camoufox window, hover your mouse over a")
    print("message bubble manually. The script will scan the DOM in 10 seconds.")
    print("=" * 60)
    time.sleep(10)
    print("\n--- Manual check scan ---")
    ss = "artifacts/p6a_strategy_manual.png"
    screenshot(page, ss)
    results = scan_dom(page)
    print(f"  Result: {dom_scan_summary(results)}")
    return "manual_check", results, ss


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs("artifacts", exist_ok=True)
    print("=" * 65)
    print("P6a — Reaction bar diagnostic spike (READ-ONLY)")
    print("Goal: Find DOM interaction that triggers the reaction bar")
    print("=" * 65)

    thread_url = input("\nPaste the IG DM thread URL: ").strip()
    if not thread_url or "instagram.com/direct/t/" not in thread_url:
        print("Invalid URL. Must contain instagram.com/direct/t/")
        sys.exit(1)

    findings = {
        "timestamp": datetime.now().isoformat(),
        "thread_url": thread_url,
        "bubbles_found": 0,
        "strategy_results": {},
        "fingerprint_viability": {},
        "recommended_next_step": "",
    }

    with camoufox.Camoufox(headless=False) as browser:
        ctx = browser.new_context(viewport={"width": 1528, "height": 794})
        ctx.add_cookies(load_cookies())
        print(f"Loaded {len(load_cookies())} cookies")

        page = ctx.new_page()

        # --- Navigate to thread ---
        print("\n[1] Navigating to thread...")
        page.goto(thread_url)
        jitter(4.5, 5.5)

        if handle_blockers(page, "p6a_blocker"):
            return

        dismiss_popups(page)
        print("  Thread loaded.")

        # --- Wait for messages to render ---
        print("\n[2] Waiting for messages to render...")
        try:
            page.wait_for_selector(MSG_LIST_SELECTOR, timeout=15000)
            print(f"  {MSG_LIST_SELECTOR} is visible.")
        except Exception:
            print("  [WARN] Message list selector not found within timeout.")
            page.screenshot(path="artifacts/p6a_no_msg_list.png")
            # Continue anyway

        jitter(3, 5)

        # --- Find media bubbles ---
        print("\n[3] Finding media bubbles...")
        bubbles = find_media_bubbles(page)
        findings["bubbles_found"] = len(bubbles)
        print(f"  Found {len(bubbles)} media bubbles.")

        if not bubbles:
            print("  [ERROR] No media bubbles found. Taking diagnostic screenshot.")
            page.screenshot(path="artifacts/p6a_no_bubbles.png")
            # Try to dump what we can see
            try:
                all_imgs = page.locator("img[src*='cdninstagram']").all()
                print(f"  Fallback: found {len(all_imgs)} total cdninstagram imgs")
                for i, img in enumerate(all_imgs[:20]):
                    try:
                        src = img.get_attribute("src") or ""
                        nh = img.evaluate("el => el.naturalHeight")
                        print(f"    img[{i}]: nh={nh}, src={src[:100]}")
                    except Exception:
                        pass
            except Exception:
                pass
            browser.close()
            return

        # --- Fingerprint data collection ---
        print("\n[4] Collecting fingerprint data from first 10 bubbles...")
        fingerprints = []
        for i, img in enumerate(bubbles[:10]):
            fp = extract_bubble_fingerprint(page, img, i)
            fingerprints.append(fp)
            handle = fp.get("poster_handle", "?")
            time_el = fp.get("time_element", "?")
            src_pre = fp.get("img_src_prefix", "?")[:60]
            print(f"  Bubble {i+1}: handle={handle}, time={time_el}, src={src_pre}...")

        handles_found = sum(1 for f in fingerprints if f.get("poster_handle"))
        times_found = sum(1 for f in fingerprints if f.get("time_element"))
        print(f"  Handles found: {handles_found}/10, Time elements found: {times_found}/10")

        if handles_found >= 7 and times_found >= 3:
            assessment = "viable"
        elif handles_found >= 4:
            assessment = "partial"
        else:
            assessment = "not viable"

        findings["fingerprint_viability"] = {
            "poster_handle_found_in_n_of_10": handles_found,
            "time_element_found_in_n_of_10": times_found,
            "assessment": assessment,
            "details": fingerprints,
        }

        # --- Diagnostic sequence on first bubble ---
        target = bubbles[0]
        print(f"\n[5] Running diagnostic sequence on first bubble...")
        try:
            src = target.get_attribute("src") or ""
            print(f"  Target img src: {src[:120]}...")
        except Exception:
            pass

        strategy_runners = [
            strategy_A_direct_hover,
            strategy_B_parent_hover,
            strategy_C_mouse_move,
            strategy_D_click_then_hover,
            strategy_E_long_hover,
            strategy_manual_check,
        ]

        any_bar_appeared = False
        winning_strategy = None

        for runner in strategy_runners:
            if any_bar_appeared:
                print(f"\n  [SKIP] Reaction bar already found by '{winning_strategy}', skipping remaining strategies.")
                break

            label, scan, ss_path = runner(page, target)
            selectors_found = list(scan.keys())
            visible_selectors = [s for s, r in scan.items() if r.get("visible")]
            bar_appeared = len(visible_selectors) > 0

            findings["strategy_results"][label] = {
                "selectors_found": selectors_found,
                "visible_selectors": visible_selectors,
                "any_reaction_bar_appeared": bar_appeared,
                "screenshot": ss_path,
                "scan_details": scan,
            }

            if bar_appeared:
                any_bar_appeared = True
                winning_strategy = label
                print(f"\n  *** REACTION BAR DETECTED via '{label}'! ***")
                print(f"  Visible selectors: {visible_selectors}")
                print("  STOPPING — not clicking anything. Logging and exiting.")

        # --- Final DOM dump ---
        print("\n[6] Saving final DOM dump...")
        save_dom_dump(page, "artifacts/p6a_dom_after_hover.html")

        # --- Final screenshot ---
        screenshot(page, "artifacts/p6a_hover_state.png")

        browser.close()

    # --- Build recommendation ---
    if any_bar_appeared:
        sw = findings["strategy_results"][winning_strategy]
        findings["recommended_next_step"] = (
            f"Reaction bar appeared using strategy '{winning_strategy}'. "
            f"Visible selectors: {sw['visible_selectors']}. "
            f"Next: write a targeted P6b spike that confirms the emoji picker "
            f"can be opened using {sw['visible_selectors'][0]} as the trigger button. "
            f"DO NOT click the emoji — just confirm the picker opens."
        )
    else:
        findings["recommended_next_step"] = (
            "No strategy triggered a reaction bar. "
            "Review artifacts/p6a_dom_after_hover.html to manually identify "
            "the reaction trigger element. Consider: (1) right-click path, "
            "(2) double-click path, (3) the reaction bar may only appear when "
            "you are the receiver (not sender) of the message, (4) the bar may "
            "require a specific thread/message state. "
            "Also check if the manual check found selectors that automated hover did not."
        )

    # --- Write findings ---
    findings_path = "artifacts/p6a_spike_findings.json"
    Path(findings_path).write_text(
        json.dumps(findings, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\nFindings written: {findings_path}")

    # --- Summary ---
    print("\n" + "=" * 65)
    print("P6a SPIKE COMPLETE")
    print(f"  Bubbles found: {findings['bubbles_found']}")
    print(f"  Fingerprint viability: {assessment} ({handles_found}/10 handles, {times_found}/10 times)")
    print(f"  Reaction bar appeared: {any_bar_appeared}")
    if any_bar_appeared:
        print(f"  Winning strategy: {winning_strategy}")
    print(f"  Strategies tried: {len(findings['strategy_results'])}")
    for label, sr in findings["strategy_results"].items():
        vis = "VISIBLE" if sr["any_reaction_bar_appeared"] else "nothing visible"
        print(f"    {label}: {len(sr['selectors_found'])} selectors in DOM, {vis}")
    print(f"\n  Findings: artifacts/p6a_spike_findings.json")
    print(f"  DOM dump:  artifacts/p6a_dom_after_hover.html")
    print(f"  Zero reactions fired. Zero mutations sent.")
    print("=" * 65)


if __name__ == "__main__":
    main()
