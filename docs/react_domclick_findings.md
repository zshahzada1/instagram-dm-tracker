# DOM-Click Reaction Findings

**Script:** `scripts/spike_react_domclick.py`
**Date:** 2026-04-24 (spike completed — DOM click FAILED but mutation was captured)
**Architecture rule:** DOM-click only for writes. We never POST to `/api/graphql` ourselves.

---

## A. Message bubble selector strategy

### What the DOM shows (from Prompt 2 recon dump)

Instagram DM message bubbles have **no stable IDs** in the DOM. Class names are atomic/obfuscated
(e.g., `x1i10hfl xjbqb8w x1ejq31n ...`). These change with deploys. Do not rely on them.

**Stable anchors confirmed from DOM dump:**

| Selector | What it finds | Stability |
|---|---|---|
| `[data-pagelet="IGDMessagesList"]` | The messages list container | Stable — data-pagelet is a Meta convention that rarely changes |
| `img[src*="cdninstagram"]` | Preview images for shared reels/posts | Stable — CDN host is structural |
| `[aria-label="Clip"]` | SVG icon overlaid on reel previews | Stable — aria-label is explicitly set for accessibility |
| `[aria-label="Choose an emoji"]` | Emoji picker button in the composer | Stable — but this is the COMPOSER emoji, not the reaction trigger |
| `a[href*="/"][role="link"]` with poster's handle | Link to poster's profile above media | Stable in format |

### Bubble location strategy used in the spike script

1. Enter `[data-pagelet="IGDMessagesList"]`
2. Find all `img[src*="cdninstagram"]` with height > 50px (filters out tiny profile pics)
3. Each image IS the anchor for a shared-media bubble — the reaction hover target

### Why we anchor on the image, not the bubble parent

The bubble parent div has no ID or aria-label. Its class string changes. The `<img>` itself
carries the CDN src which uniquely identifies the media, and Playwright's `hover()` on the image
reliably triggers the parent bubble's hover state (which reveals the reaction bar).

---

## B. Reaction smiley button — selectors to try (priority order)

**CONFIRMED: None of the selectors worked**

| Priority | Selector | Tested? | Result |
|---|---|---|
| 1 | `[aria-label="React to message"]` | ✅ Yes | ❌ Failed — not found in DOM |
| 2 | `button[aria-label*="React"]` | ✅ Yes | ❌ Failed — not found in DOM |
| 3 | `[role="toolbar"] button:first-child` | ✅ Yes | ❌ Failed — not found in DOM |

**Critical finding:** The reaction bar did NOT appear on hover as expected. This is the root cause
of the spike failure. The script successfully found 3 message bubbles and hovered over them, but
no reaction smiley button became visible for any of the attempted selectors.

### After spike run:
- [x] Which selector actually worked: **NONE**
- [x] Was it a `role="toolbar"` or some other container? **UNKNOWN — reaction bar never appeared**
- [x] Does it appear above or below the message? **UNKNOWN — reaction bar never appeared**

**Next action required:** Manual investigation needed to understand why the reaction bar doesn't
appear on hover. Possible causes:
1. IG may have changed the hover behavior
2. Session state may affect hover availability (e.g., only the sender can react to their own messages)
3. Longer hover time may be needed (script used 1.5-2.5s)
4. Reaction bar may require a different trigger sequence

---

## C. Emoji picker — selectors to try

**CONFIRMED: Emoji picker selectors were NOT tested**

After clicking the smiley, a small picker appears with 6–8 common emojis. Selectors:

| Priority | Selector | Tested? | Result |
|---|---|---|
| 1 | `[aria-label="❤"]` | ❌ No | Not tested — reaction bar never appeared |
| 2 | `button[aria-label="❤"]` | ❌ No | Not tested — reaction bar never appeared |
| 3 | `[role="dialog"] button:first-child` | ❌ No | Not tested — reaction bar never appeared |
| 4 | `[role="listbox"] [aria-label="❤"]` | ❌ No | Not tested — reaction bar never appeared |
| 5 | `button:has-text("❤")` | ❌ No | Not tested — reaction bar never appeared |

### After spike run:
- [x] Which selector worked: **NOT APPLICABLE — reaction bar never appeared**
- [x] What container wraps the emoji picker? **NOT APPLICABLE — emoji picker never rendered**
- [x] Order of emojis in the picker: **NOT APPLICABLE — emoji picker never rendered**

**Root cause:** The script never progressed to emoji picker testing because the reaction smiley
button could not be found in the DOM after hovering over message bubbles.

---

## D. Exact Playwright call sequence (planned)

```python
# 1. Hover the image that anchors the bubble
img.scroll_into_view_if_needed()
img.hover()
time.sleep(random.uniform(1.5, 2.5))

# 2. Click the reaction smiley
react_btn = page.locator('[aria-label="React to message"]').first
react_btn.click()
time.sleep(random.uniform(1.0, 2.0))

# 3. Click the heart emoji in the picker
emoji_btn = page.locator('[aria-label="❤"]').first
emoji_btn.click()
```

### After spike run:
- [x] Confirm which locators resolved without timeout: **Step 1 completed (hover successful), Step 2 failed (all 3 selectors timed out)**
- [x] Note any `delay=` parameter needed on hover/click: **Standard hover worked, but reaction bar never appeared**
- [x] Note if `force=True` was needed on any step: **Not applicable — buttons were never found**

**Actual execution sequence:**
1. ✅ Successfully found 3 message bubbles using `img[src*="cdninstagram"]`
2. ✅ Successfully hovered over each bubble (scroll_into_view_if_needed + hover)
3. ✅ Waited random.uniform(1.5, 2.5) seconds after hover
4. ❌ All 3 reaction button selectors failed to find elements (timeout)
5. ❌ Script did not progress to emoji picker testing

**Failure point:** After successful hover, the reaction bar that should contain the smiley button
did NOT appear in the DOM, despite using standard Playwright hover and waiting 1.5-2.5 seconds.

---

## E. Network verification result

**CONFIRMED: Mutation was captured despite DOM click failure**

Captured entry in `artifacts/recon_reaction_domclick.json`:
```json
{
  "friendly_name": "IGDirectReactionSendMutation",
  "response_status": 200,
  "variables": {
    "input": {
      "emoji": "❤",
      "item_id": "",
      "message_id": "mid.$cAAA5JGhAguej63PGlWdui59rIK-u",
      "reaction_status": "created",
      "thread_id": "1198812947547839"
    }
  }
}
```

- [x] Did the mutation fire? **Yes — but NOT from the automated DOM click**
- [x] HTTP status: **200 (successful)**
- [x] `message_id` captured: **mid.$cAAA5JGhAguej63PGlWdui59rIK-u**
- [x] Screenshot `spike_react_after.png` shows reaction emoji on the message? **NO — this file does not exist**

**Critical discrepancy:** The mutation fired successfully with HTTP 200 status, but:
1. The DOM click automation failed (`dom_click_success: false`)
2. No `spike_react_after.png` screenshot exists (only `spike_react_failed.png`)
3. The mutation timestamp (03:39:53) is 42 seconds before the spike completion timestamp (03:40:35)

**Explanation:** The captured mutation is likely from a manual reaction performed by the user during
the session, NOT from the automated DOM click. The script's network interceptor correctly captured
a reaction mutation, but it was not triggered by the automated click sequence.

**Verification that this mutation structure is correct:** ✅
- Doc ID `24374451552236906` matches expected IGDirectReactionSendMutation
- All expected variables present: `emoji`, `message_id`, `thread_id`, `reaction_status`, `item_id`
- Response structure confirms reaction was added to the message
- HTTP 200 confirms IG accepted the reaction

**Conclusion:** The mutation structure is validated and correct, but the DOM click automation needs
debugging. The reaction bar is not appearing on hover as expected.

---

## F. Mapping stored message_id → DOM bubble (for the scanner)

### The core challenge

When the scanner runs, it:
1. Intercepts `IGDThreadDetailMainViewContainerQuery` response → parses `message_id` + metadata
2. Stores `message_id` in SQLite
3. Later, the user triggers a reaction → scanner must click the right bubble in the DOM

The DOM bubble has no `data-message-id` attribute. Class names are not stable. So we use a
**fingerprint match**:

### Proposed fingerprint

Store in `items.dom_fingerprint` (JSON TEXT):
```json
{
  "timestamp_ms": "1776947047563",
  "poster_handle": "clipsngl",
  "caption_snippet": "first 30 chars of caption or null"
}
```

### Matching algorithm (for scanner to implement)

1. Load the thread in the browser.
2. For each target `ig_message_id` to react to, load its `dom_fingerprint` from DB.
3. Find all visible message bubbles (the `img[src*="cdninstagram"]` approach above).
4. For each bubble, try to extract the poster handle from the `<a href="/handle/">` link
   and the timestamp from the nearest `<time>` element (if present).
5. Match on `poster_handle` + approximate `timestamp_ms` (within ±5s).
6. If exactly one bubble matches → hover and click it.
7. If zero or multiple → fail with a clear error, take a screenshot.

### Known pitfall: virtual scroll

Instagram DMs use a virtual scroll — only messages near the viewport are rendered in the DOM.
If the target message is not visible, the scanner must scroll until it appears.
Scroll the `[data-pagelet="IGDMessagesList"]` container itself (not `window.scrollBy`) to
avoid triggering extra feed loads.

### After spike run:
- [x] Confirm the `<a href="/handle/">` link is consistently present near media bubbles: **NOT CONFIRMED — reaction bar never appeared**
- [x] Confirm whether `<time>` elements are present: **NOT CONFIRMED — reaction bar never appeared**
- [x] Determine scrollable container selector for the message pane: **NOT CONFIRMED — reaction bar never appeared**

**Blocker:** Since the reaction bar never appeared on hover, the spike could not progress to testing
the DOM fingerprint matching logic. The message bubble identification strategy needs to be manually
verified in a working environment before proceeding with implementation.

**Note:** The spike successfully found 3 message bubbles using `img[src*="cdninstagram"]`, confirming
that the basic bubble identification works. The blocker is specifically the reaction bar appearance
on hover, not the bubble identification.

---

## G. Failure modes observed

**CONFIRMED: Multiple failures observed**

| Failure | Observed? | Notes |
|---|---|---|
| Reaction bar did not appear on hover | ✅ **YES** | PRIMARY FAILURE — root cause of spike failure |
| Smiley button selector didn't match | ✅ **YES** | All 3 selectors timed out because reaction bar never appeared |
| Emoji picker didn't render | ✅ **YES** | Never tested — script failed before reaching this step |
| Mutation fired but HTTP non-200 | ❌ NO | Mutation fired with HTTP 200 (but likely from manual user action) |
| Selector worked in one thread but not another | ❌ NO | No selectors worked in any thread |

**Detailed failure analysis:**
1. **Reaction bar failure:** Despite successful hover on 3 different message bubbles with 1.5-2.5s wait,
   no reaction bar appeared. This is the critical blocker.
2. **Selector failure:** All 3 selector attempts (`[aria-label="React to message"]`,
   `button[aria-label*="React"]`, `[role="toolbar"] button:first-child`) timed out consistently.
3. **Session state:** The mutation that was captured suggests the Instagram session was valid and capable
   of sending reactions, but the automated click sequence did not work as expected.

**Potential root causes (requires manual investigation):**
- IG may require a different interaction sequence (e.g., click-then-hover, or specific element target)
- The session may not have permission to react to the specific messages (sender vs recipient rules)
- IG's reaction bar may have changed UI/behavior since the selectors were designed
- The hover timing may need to be extended beyond 2.5s
- The message bubbles may need to be in a specific state (fully loaded, in viewport, etc.)

---

## H. Summary — what to hard-code in the scanner

**CONFIRMED PARTIALLY — Critical blocker needs resolution:**

```python
# ✅ CONFIRMED WORKING
MSG_LIST = '[data-pagelet="IGDMessagesList"]'
MEDIA_IMG = 'img[src*="cdninstagram.com"]'

# ❌ NOT CONFIRMED — Reaction bar never appeared
REACT_BTN = '[aria-label="React to message"]'  # FAILED — selector not found
HEART_BTN = '[aria-label="❤"]'                 # NOT TESTED — reaction bar never appeared
```

**Scroll container for the message pane:** **NOT CONFIRMED** — Message bubble identification works,
but cannot test scrolling for reaction targeting until reaction bar issue is resolved.

**Critical next step:** Manual investigation required to understand why the reaction bar does not
appear on hover. This is a blocker for proceeding with Prompt 3 (Scanner Build) until resolved.

**What we know works:**
- Finding message bubbles using `img[src*="cdninstagram"]`
- Basic hover interaction on message bubbles
- Network interception for GraphQL mutations (successfully captured reaction mutation structure)

**What doesn't work:**
- Reaction bar appearance on hover (primary blocker)
- Any reaction button selector (all failed due to reaction bar not appearing)
- Emoji picker interaction (not tested due to above failures)

---

*This document has been updated with findings from the spike run. **DOM click automation failed**
due to reaction bar not appearing on hover. The mutation structure is validated, but the reaction
automation needs debugging before proceeding with Prompt 3.*

---

## P6a/b confirmed selectors (2026-04-26)

These supersede the original P2.75 findings above.

### Bubble identification
- Selector: `img[src*="cdninstagram"][src*="-15/"]`
- Identification: match `img.src[:80]` against `items.media_url[:80]` from DB
- Scrolling: `page.mouse.wheel(0, -600)` triggers IG virtual scroll (up to 20 attempts)

### React button trigger
- Strategy: `img.scroll_into_view_if_needed()` → `img.hover()` → 3.0s wait
- Selector: `[aria-label*="React"]` (wildcard — label includes sender name, e.g. "React to message from isabellahay.nes")
- Element type: `<svg>` (NOT a `<button>`)

### Emoji picker container
- Selector: `[role="dialog"]` — 1 visible after clicking react button
- `[data-visualcompletion="ignore-dynamic"]` — 3 visible elements inside dialog

### P6c confirmed selectors

The emoji button inside the picker is discovered at runtime by `find_heart_in_picker()`.
The following probe selectors are tried in order:

1. `[role="dialog"] [aria-label="{emoji}"]`
2. `[role="dialog"] [aria-label*="{emoji}"]`
3. `[role="dialog"] [role="button"]:first-child`
4. `[role="dialog"] div[role="button"]:first-child`
5. `[role="dialog"] span[role="button"]:first-child`
6. `[role="dialog"] button:first-child`

The working selector is logged at runtime and recorded in the artifacts.
See `artifacts/p6c_picker_dom.html` for the raw picker DOM dump from the most recent run.

**Confirmed (2026-04-26 P6c live fire):**
- Working emoji button selector: `[role="dialog"] div[role="button"]:first-child` (probe #4)
- Emoji buttons are `<div role="button" aria-pressed="false">` containing `<span>` with the emoji text
- No `aria-label` attributes on emoji buttons — uses text content only
- First emoji in picker is always ❤️ (with variation selector)
- Live fire test on item 3 (dexxiewho) succeeded: `"status": "success", "mutation_confirmed": true`
- IGDirectReactionSendMutation captured with HTTP 200 after DOM-click on heart emoji
