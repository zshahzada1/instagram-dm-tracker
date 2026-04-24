# DOM-Click Reaction Findings

**Script:** `scripts/spike_react_domclick.py`
**Date:** 2026-04-23 (spike not yet run — see sections marked PENDING)
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

**PENDING verification** — these are derived from IG's known accessibility patterns and will be
confirmed/corrected after running the spike.

| Priority | Selector | Basis |
|---|---|---|
| 1 | `[aria-label="React to message"]` | Expected aria-label from IG accessibility |
| 2 | `button[aria-label*="React"]` | Looser match, same concept |
| 3 | `button[aria-label*="react"]` | Lowercase variant |
| 4 | `[role="toolbar"] button:first-child` | Reaction bar is often a `role=toolbar` row |
| 5 | `div[role="toolbar"] button` | Fallback if first-child is wrong position |

The script tries all five in order and logs which one works. The emoji reaction bar appears as a
floating element near the message after hover — it is NOT permanently in the DOM.

### PENDING after spike run:
- [ ] Which selector actually worked
- [ ] Was it a `role="toolbar"` or some other container?
- [ ] Does it appear above or below the message?

---

## C. Emoji picker — selectors to try

After clicking the smiley, a small picker appears with 6–8 common emojis. Selectors:

| Priority | Selector | Basis |
|---|---|---|
| 1 | `[aria-label="❤"]` | Most direct — aria-label on the emoji button |
| 2 | `button[aria-label="❤"]` | Explicit button + aria-label |
| 3 | `[role="dialog"] button:first-child` | Heart is often the first option |
| 4 | `[role="listbox"] [aria-label="❤"]` | Alternative picker container |
| 5 | `button:has-text("❤")` | Fallback if no aria-label |

### PENDING after spike run:
- [ ] Which selector worked
- [ ] What container wraps the emoji picker? (`role="dialog"`, `role="listbox"`, other?)
- [ ] Order of emojis in the picker (useful if aria-labels aren't set)

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

### PENDING after spike run:
- [ ] Confirm which locators resolved without timeout
- [ ] Note any `delay=` parameter needed on hover/click
- [ ] Note if `force=True` was needed on any step

---

## E. Network verification result

**PENDING — fill in after running spike**

Expected: capture one entry in `artifacts/recon_reaction_domclick.json` with:
```json
{
  "friendly_name": "IGDirectReactionSendMutation",
  "response_status": 200,
  "variables": {
    "input": {
      "emoji": "❤",
      "message_id": "mid.$...",
      "thread_id": "<internal thread id>",
      "reaction_status": "created",
      "item_id": ""
    }
  }
}
```

- [ ] Did the mutation fire? Y/N
- [ ] HTTP status: ___
- [ ] `message_id` captured: ___
- [ ] Screenshot `spike_react_after.png` shows reaction emoji on the message? Y/N

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

### PENDING after spike run:
- [ ] Confirm the `<a href="/handle/">` link is consistently present near media bubbles
- [ ] Confirm whether `<time>` elements are present (they were NOT in the initial recon DOM)
- [ ] Determine scrollable container selector for the message pane

---

## G. Failure modes observed

**PENDING — fill in after spike run**

| Failure | Observed? | Notes |
|---|---|---|
| Reaction bar did not appear on hover | ? | May need longer hover wait or `force=True` |
| Smiley button selector didn't match | ? | Script falls back to manual selector input |
| Emoji picker didn't render | ? | May need extra settle time |
| Mutation fired but HTTP non-200 | ? | Session expired? Rate limited? |
| Selector worked in one thread but not another | ? | Check if aria-labels are consistent across IG locales |

---

## H. Summary — what to hard-code in the scanner

**PENDING full confirmation, but likely:**

```python
MSG_LIST = '[data-pagelet="IGDMessagesList"]'
MEDIA_IMG = 'img[src*="cdninstagram.com"]'
REACT_BTN = '[aria-label="React to message"]'  # or confirmed alternative
HEART_BTN = '[aria-label="❤"]'                 # or confirmed alternative
```

Scroll container for the message pane: **TBD** — test `[data-pagelet="IGDMessagesList"]`
scrollable ancestor vs. the inner div.

---

*This document is a pre-populated template. Fill in all PENDING sections after running
`scripts/spike_react_domclick.py` and reviewing `artifacts/recon_reaction_domclick.json`
and the spike screenshots.*
