# Instagram DM Media Tracker — CLAUDE.md

## Project Overview

A tool to track media (reels, posts, carousels, stories) shared in an Instagram DM thread.
Features: scan thread → store new items in SQLite → auto-react to new items → React UI (later).
**User is non-coder.** All scripts must work via simple terminal commands with clear prompts.

## Stack

- Python 3 + Camoufox (Firefox-based, anti-detect browser automation)
- SQLite — database file `instagram_dm_tracker.db` (not yet created)
- React UI — not yet built (Prompt 4+)
- Windows 11, venv at `./venv` (activate: `venv\Scripts\activate`)

---

## Architecture Rule (Absolute)

This project uses a real browser (Camoufox) driven by Playwright. There are exactly two ways we interact with Instagram:

1. **READS** — we navigate and scroll normally; we passively intercept GraphQL responses that IG's React app fires on its own. We never construct a GraphQL query ourselves.
2. **WRITES (reactions only)** — DOM-click. We hover/click the real UI. We never POST to `/api/graphql`. We never use `page.evaluate()` to construct an API call. We never issue the call from Python.

If a future task seems to require calling an IG endpoint directly, stop and ask the orchestrator. The answer is almost certainly "no, find a DOM-click path."

## Status as of Prompt 2.75

Recon complete. Architecture corrected (DOM-click for writes). Reaction spike script written. Ready for **Prompt 3: Scanner Build** once spike is verified.

All key API parameters confirmed. See `docs/thread_recon_v2.md` for full findings. See `docs/react_domclick_findings.md` for DOM-click reaction selectors (written after spike runs).

---

## Instagram API: Concrete Facts (from Recon)

### Querying thread messages

- **Query name:** `IGDThreadDetailMainViewContainerQuery`
- **Doc ID:** `26562617700073112`
- **Variable:** `thread_fbid` = the numeric segment from the thread URL (also called `interop_messaging_user_fbid` or `thread_key`)
- **Response path:** `data.get_slide_thread_nullable.as_ig_direct_thread.slide_messages.edges[N].node`
- **Page size:** 20 messages per query

### ID types — use the right one

| ID | Source | Use for |
|---|---|---|
| URL segment / `thread_key` | URL path or `thread_key` field | Querying messages (`thread_fbid`) |
| `thread.id` / `thread_fbid` in response | Response body | Reactions (`thread_id` in mutation) |

### Message node key fields

```
message_id          str, format: "mid.$..."  — stable identifier for reactions
sender_fbid         str — compare to viewer's interop ID to determine sender
timestamp_ms        str, unix epoch ms
content_type        str — see table below
content             object — varies by type
reactions           list of {reaction: str, sender_fbid: str}
```

### Content types to track

| content_type | Identify by | What |
|---|---|---|
| MESSAGE_INLINE_SHARE | `xma.__typename == "SlideMessagePortraitXMA"` + `/reel/` in target_url | Reel |
| MESSAGE_INLINE_SHARE | `xma.__typename == "SlideMessageStandardXMA"` + no `carousel_share_child_media_id` | Feed post |
| MESSAGE_INLINE_SHARE | `xma.__typename == "SlideMessageStandardXMA"` + `carousel_share_child_media_id` in target_url | Carousel |
| MONTAGE_SHARE_XMA | `content_type == "MONTAGE_SHARE_XMA"` | Story share |
| TEXT | — | Plain text — ignore |
| REACTION_LOG_XMAT | — | System message — ignore |

Shortcode from target_url: extract `/reel/<shortcode>/` or `/p/<shortcode>/`

### Sending a reaction

Reactions are sent via **DOM-click only**. Playwright simulates hover → click smiley → click emoji on the actual Instagram UI. We never POST to `/api/graphql` ourselves. See `docs/react_domclick_findings.md` for selectors and the verified flow.

The captured mutation details below are retained for one purpose only: **verifying via network intercept that the correct mutation fired after a DOM-click**. They are NOT implementation inputs. Do not construct or call this mutation from code.

Verification shape (read-only):
- **Friendly name:** `IGDirectReactionSendMutation`
- **Doc ID:** `24374451552236906`
- **Expected `variables.input` fields:** `emoji`, `message_id`, `thread_id`, `reaction_status`, `item_id`

### Pagination

- `slide_messages.page_info.has_next_page` → bool
- `slide_messages.page_info.end_cursor` → base64 string to pass for next page
- **Gap:** Cursor variable name not confirmed (`after` or `cursor` — test during scanner build)

### Viewer identity

Available in response `viewer` object. Store `viewer.interop_messaging_user_fbid` to identify
which messages are "mine" vs "hers" and which reactions are mine.

---

## Key Files

| File | Purpose |
|---|---|
| `scripts/spike_login.py` | Initial login/cookie proof (done, working) |
| `scripts/recon_thread_v2.py` | Recon script — captures full GraphQL traffic |
| `scripts/spike_react_domclick.py` | DOM-click reaction spike (Prompt 2.75) |
| `docs/thread_recon_v2.md` | Full recon findings with real data examples |
| `docs/react_domclick_findings.md` | DOM-click selectors and verified flow (post-spike) |
| `docs/schema.md` | SQLite schema design (5 tables + dom_fingerprint) |
| `test-cookies/cookies.json` | Instagram session cookies (**gitignored, never commit**) |
| `artifacts/recon_network_v2.json` | Captured GraphQL traffic from recon (gitignored) |
| `artifacts/recon_reaction.json` | Reaction mutation capture (gitignored) |
| `artifacts/recon_reaction_domclick.json` | DOM-click spike reaction capture (gitignored) |

---

## Guardrails (Permanent — Apply to Every Script)

1. **Headed browser only** — `camoufox.Camoufox(headless=False)`. Never `headless=True`.
2. **Human-like pacing** — `random.uniform(1.5, 3.0)` second jitter between actions; 3–5s settle after any `page.goto()`.
3. **Blocker detection** — check for IG checkpoints/captchas/suspicious-login modals after every navigation. If found: screenshot → `artifacts/blocker_<timestamp>.png`, write `artifacts/blocker_<timestamp>.md`, stop and print instructions. Never proceed past a blocker.
4. **Dismiss popups** — click "Not Now" or press Escape on notification/PWA overlays before interacting.
5. **No unsolicited sends** — never send messages or reactions unless the script was explicitly built for that.
6. **Windows encoding fix** — every script starts with:
   ```python
   import sys, io
   sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
   ```

---

## Known Gaps (Going into Prompt 3)

| Gap | Severity | Plan |
|---|---|---|
| Pagination cursor variable name | Medium | Test `after` first, fall back to `cursor` |
| Carousel individual slides | Low | Only preview image in XMA; skip or fetch separately |
| Reaction removal mutation | Low | Use `reaction_status: "deleted"` — test during scanner |
| FIFO request-response pairing | Low | Use `friendly_name` field to match, not URL FIFO |

---

## Prompt 3 — What Will Be Built

1. `db/init_db.py` — Create SQLite DB from schema (`migrations/001_initial_schema.sql`)
2. `scanner/scanner.py` — Core scanner: open thread via Camoufox, intercept `IGDThreadDetailMainViewContainerQuery` responses, parse messages, store new media items, handle pagination
3. `scanner/reaction.py` — Send a reaction to a specific `message_id`
4. `migrations/001_initial_schema.sql` — SQL from `docs/schema.md`
5. A simple `main.py` or CLI entry point the user can run

Do NOT start building until Prompt 3 is issued.
