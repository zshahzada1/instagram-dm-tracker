# Instagram DM Thread Reconnaissance v2 — Concrete Findings

**Date:** 2026-04-23
**Script:** `scripts/recon_thread_v2.py`
**Artifacts:** `artifacts/recon_network_v2.json` (59 requests, full payloads), `artifacts/recon_reaction.json` (31 requests)
**Supersedes:** `docs/thread_recon.md`

## 1. Which GraphQL query returns thread messages?

**Friendly name:** `IGDThreadDetailMainViewContainerQuery`
**Doc ID:** `26562617700073112`
**Occurrences:** 31 requests across inbox load + thread navigation

### Request variables (real example)

```json
{
  "min_uq_seq_id": null,
  "thread_fbid": "111594096907116",
  "__relay_internal__pv__IGDEnableOffMsysChatThemesQErelayprovider": false,
  "__relay_internal__pv__IGDEnableOffMsysPinnedMessagesQErelayprovider": true,
  "__relay_internal__pv__IGDInitialMessagePageCountrelayprovider": 20
}
```

The only variable that matters is `thread_fbid`. The `__relay_internal__` flags are QE params and can be hardcoded. `min_uq_seq_id` was always `null` in our capture (pagination not triggered — see Section 4).

### Response path to messages

```
response_body.data.get_slide_thread_nullable.as_ig_direct_thread.slide_messages.edges[N].node
```

Each thread query returns up to 20 messages (`IGDInitialMessagePageCountrelayprovider` controls page size).

---

## 2. Message object schema

### Full field map (every field on a message node)

```
node
  __typename                    "SlideMessage"
  id                            str, duplicates message_id
  message_id                    str, e.g. "mid.$cAAA5JGhAguej65F0i2dukwrtlcOT"
  sender_fbid                   str, interop_messaging_user_fbid of sender
  thread_fbid                   str, internal thread ID
  content_type                  str (see below)
  content                       object, varies by type (see below)
  timestamp_ms                  str, unix epoch ms
  offline_threading_id          str, client dedup ID
  text_body                     str or null, text preview
  bot_response_id               str or null
  is_reported                   bool
  igd_is_forwarded              bool
  is_pinned                     bool
  mentions                      list (usually empty)
  reactions                     list of {reaction: str, sender_fbid: str}
  replied_to_message_id         str or null
  replied_to_message            object or null (partial message preview)
  slide_edit_history            list (empty in capture)
  sender                        {name, id, igid, user_dict: {profile_pic_url, username, full_name, ...}}
  igd_wearables_attribution_text  null
  igd_wearables_attribution_type  null
  expiration_timestamp_ms        null
  view_expiration_timestamp_ms   null
```

### Content types found (9 total)

| content_type | content.__typename | Count | What it is |
|---|---|---|---|
| TEXT | SlideMessageText | 274 | Plain text message |
| MESSAGE_INLINE_SHARE | SlideMessageXMAContent | 142 | Shared post/reel/carousel |
| RAVEN_IMAGE | SlideMessageRavenImageContent | 10 | Disappearing photo |
| REACTION_LOG_XMAT | SlideMessageAdminText | 6 | "Liked a message" log |
| IMAGES | SlideMessageImageContent | 4 | Direct image upload |
| RAVEN_VIDEO | SlideMessageRavenVideoContent | 2 | Disappearing video |
| INSTAGRAM_MESSAGING_ANIMATED_IMAGE | SlideMessageAnimatedMediaContent | 2 | GIF |
| MONTAGE_SHARE_XMA | SlideMessageXMAContent | 2 | Story share |
| INSTAGRAM_MESSAGING_MEDIA_NOTE | SlideMessageXMAContent | 2 | Voice note (XMA wrapper) |

### a) Shared reel (MESSAGE_INLINE_SHARE, SlideMessagePortraitXMA)

```json
{
  "content_type": "MESSAGE_INLINE_SHARE",
  "message_id": "mid.$cAAA5JGhAguej65F0i2dukwrtlcOT",
  "sender_fbid": "110975426965828",
  "timestamp_ms": "1776947047563",
  "content": {
    "__typename": "SlideMessageXMAContent",
    "xma": {
      "__typename": "SlideMessagePortraitXMA",
      "target_url": "https://www.instagram.com/reel/DXWHYO8ieJM/?id=3879320580667335244_76737956623&is_sponsored=false",
      "target_id": "3879320580667335244",
      "xmaHeaderTitle": "clipsngl",
      "xmaPreviewImage": {
        "url": "https://scontent-lhr6-2.cdninstagram.com/v/t51.71878-15/..."
      }
    }
  }
}
```

**Type detection:** `xma.__typename == "SlideMessagePortraitXMA"` AND `target_url` contains `/reel/`
**Shortcode:** Extract from `target_url` → `DXWHYO8ieJM`
**Poster handle:** `xma.xmaHeaderTitle`
**Media ID:** `xma.target_id`

### b) Shared post (MESSAGE_INLINE_SHARE, SlideMessageStandardXMA)

```json
{
  "content_type": "MESSAGE_INLINE_SHARE",
  "message_id": "mid.$cAAA5JGhAguej63K9GGdui10Iir49",
  "sender_fbid": "110975426965828",
  "timestamp_ms": "1776945034520",
  "content": {
    "__typename": "SlideMessageXMAContent",
    "xma": {
      "__typename": "SlideMessageStandardXMA",
      "target_url": "https://www.instagram.com/p/DXZizQRDDiF/?is_sponsored=false",
      "target_id": "3880285609696966789",
      "xmaHeaderTitle": "icyy_y1",
      "xmaTitle": "Just let me dig up a hole and die at this point #real #relatable",
      "xmaPreviewImage": {
        "url": "https://scontent-lhr8-2.cdninstagram.com/v/t51.82787-15/..."
      }
    }
  }
}
```

**Type detection:** `xma.__typename == "SlideMessageStandardXMA"` AND `target_url` contains `/p/` WITHOUT `carousel_share_child_media_id`
**Shortcode:** `DXZizQRDDiF`
**Caption:** `xma.xmaTitle`

### c) Shared carousel (MESSAGE_INLINE_SHARE, SlideMessageStandardXMA)

```json
{
  "content_type": "MESSAGE_INLINE_SHARE",
  "message_id": "mid.$cAAA5JGhAguej63PGlWdui59rIK-u",
  "content": {
    "__typename": "SlideMessageXMAContent",
    "xma": {
      "__typename": "SlideMessageStandardXMA",
      "target_url": "https://www.instagram.com/p/DWq3zi7j-ix/?carousel_share_child_media_id=3867148664808925361_243254259&is_sponsored=false",
      "target_id": "3867148664808925361",
      "xmaHeaderTitle": "borotan",
      "xmaTitle": "borotan 穏やかなティータイムぞよ🍵..."
    }
  }
}
```

**Type detection:** `xma.__typename == "SlideMessageStandardXMA"` AND `target_url` contains `carousel_share_child_media_id`
**Key difference from regular post:** `target_url` has `carousel_share_child_media_id` parameter
**Slide index:** The `carousel_share_child_media_id` points to a specific child media, not the carousel root

**Note:** Only ONE preview image per carousel share, regardless of slide count. Individual slide URLs are NOT included in the XMA data. The scanner would need to fetch the carousel post separately to get all slides, or only track the shared slide.

### d) Story share (MONTAGE_SHARE_XMA)

```json
{
  "content_type": "MONTAGE_SHARE_XMA",
  "message_id": "mid.$cAEBDL4Z3jHqjCtdrCWc2ZKMZMAl8",
  "content": {
    "__typename": "SlideMessageXMAContent",
    "xma": {
      "__typename": "SlideMessagePortraitXMA",
      "target_url": "https://www.instagram.com/stories/djdkkrnrnemem/3849701718972171366?reel_id=44903709848",
      "target_id": "ee.mid.$cAEBDL4Z3jHqjCtdrCWc2ZKMZMAl8",
      "xmaHeaderTitle": "djdkkrnrnemem"
    }
  }
}
```

**Type detection:** `content_type == "MONTAGE_SHARE_XMA"` OR `target_url` contains `/stories/`
**Note:** Stories are ephemeral. The URL will expire. Track for completeness but media won't be accessible later.

### e) Direct image (IMAGES)

```json
{
  "content_type": "IMAGES",
  "message_id": "mid.$gAFXusaS8sd2hjQ_cw2bW8qQGGzPd",
  "content": {
    "__typename": "SlideMessageImageContent",
    "attachments": [{
      "attachment_fbid": "1210833077641739",
      "attachment_type": 2,
      "preview_cdn_url": "https://scontent-lhr6-1.xx.fbcdn.net/v/t1.15752-9/...",
      "attachment_cdn_url": "https://scontent-lhr6-1.xx.fbcdn.net/v/t1.15752-9/..."
    }]
  }
}
```

**Type detection:** `content_type == "IMAGES"`
**CDN host:** `fbcdn.net` (not `cdninstagram.com`)

### f) GIF (INSTAGRAM_MESSAGING_ANIMATED_IMAGE)

```json
{
  "content_type": "INSTAGRAM_MESSAGING_ANIMATED_IMAGE",
  "content": {
    "__typename": "SlideMessageAnimatedMediaContent",
    "animated_media": [{
      "is_sticker": false,
      "alt_text": "Cartoon gif...",
      "attachment_webp_url": "https://media2.giphy.com/media/...",
      "attachment_mp4_url": "..."
    }]
  }
}
```

### g) Disappearing media (RAVEN_IMAGE / RAVEN_VIDEO)

```json
{
  "content_type": "RAVEN_IMAGE",
  "content": {
    "__typename": "SlideMessageRavenImageContent",
    "view_mode": 1,
    "attachment": null
  }
}
```

**Note:** `attachment` was `null` in capture. Disappearing media has likely already expired or is only accessible via a separate API call. Not a priority for the scanner.

---

## 3. Which ID is the "real" thread ID?

There are THREE distinct ID types visible in thread responses:

| Field | Example value | Source |
|---|---|---|
| `thread_key` | `110975426965828` | Response — matches other person's `interop_messaging_user_fbid` |
| `thread.id` / `thread.thread_fbid` | `1198812947547839` | Response — internal thread identifier |
| `thread.thread_id` | `340282366841710301244259373830524634815` | Response — 128-bit UUID-like |

### Which to use where

**Querying a thread (IGDThreadDetailMainViewContainerQuery):**
- Variable `thread_fbid` = the `interop_messaging_user_fbid` of the other person
- For the URL `https://www.instagram.com/direct/t/110975426965828/`, use `thread_fbid = "110975426965828"`
- Confirmed: Entry 12 variable `thread_fbid=111594096907116` matched response `thread_key=111594096907116`

**Sending a reaction (IGDirectReactionSendMutation):**
- Variable `thread_id` = `thread.id` / `thread.thread_fbid` (the INTERNAL thread ID)
- For bel's thread: `thread_id = "1198812947547839"`
- Confirmed: Reaction mutation used `thread_id = "1198812947547839"` on a message from bel's thread

### Scanner flow for IDs

1. Extract `interop_messaging_user_fbid` from URL (the numeric path segment)
2. Query `IGDThreadDetailMainViewContainerQuery` with `thread_fbid = <interop_id>`
3. From response, store BOTH:
   - `thread_key` = the interop ID (for querying)
   - `thread.id` = the internal thread ID (for reactions)
4. When reacting, use `thread.id` as `thread_id`

### FIFO matching caveat

The capture script uses FIFO matching (queue responses by URL). Since all GraphQL calls hit the same URL (`/api/graphql`), responses arriving out of order cause incorrect request-response pairing. Entry 12 matched correctly; entry 19 did not (variable `thread_fbid=24187819760857565` got paired with "bel" thread response). The response data itself is valid — only the pairing is unreliable.

---

## 4. Pagination cursor format

### What we know

`page_info` exists on every thread's `slide_messages`:

```
slide_messages.page_info
  has_next_page       bool (true on threads with >20 messages)
  has_previous_page   bool (always false — first page loads most recent)
  start_cursor        str, base64-encoded
  end_cursor          str, base64-encoded
```

Per-edge cursors also exist: `edges[N].cursor` (base64-encoded strings).

Real example from bel's thread:
- `start_cursor`: `AQHSXigLIlMjE9l7-hBqVJnFZI0tenuTaySgwVzCaoO-uJ3FmDL-ELBYTq7G...`
- `end_cursor`: `AQHSKL0DK8FsHq1hiEsgxwHOMIYR_2oxZqpUxtIiUaVsRMrBlsct5EDr_sxh...`

### What we DON'T know

The actual pagination call was NOT captured. Scrolling used `window.scrollBy(0, -800)` which scrolled the browser window, not the DM message pane's scroll container. No additional GraphQL requests were triggered by scrolling.

The query variable `min_uq_seq_id` was always `null` — this is likely NOT the pagination cursor (it's probably a sequence ID for real-time updates via Iris/Msys).

**Likely pagination mechanism:** Relay-style cursor-based pagination where `end_cursor` is passed back as a variable (possibly named `after` or `cursor`) in a subsequent `IGDThreadDetailMainViewContainerQuery` call. This needs to be confirmed by:
1. Finding the scrollable message container's CSS selector
2. Scrolling that container specifically to trigger pagination
3. Capturing the resulting GraphQL call with cursor variable

### Impact on scanner

For threads with ≤20 media items (common for DMs), no pagination is needed. For longer threads, pagination is required but the exact variable name is still unknown. This is a known gap that should be filled before or during scanner development.

---

## 5. Reaction mutation

**Friendly name:** `IGDirectReactionSendMutation`
**Doc ID:** `24374451552236906`
**HTTP Status:** 200 (success)
**Source:** `artifacts/recon_reaction.json`

### Request variables

```json
{
  "input": {
    "emoji": "❤",
    "item_id": "",
    "message_id": "mid.$cAAA5JGhAguej64_vaWdukqmd_h3j",
    "reaction_status": "created",
    "thread_id": "1198812947547839"
  }
}
```

| Parameter | Type | Value | Notes |
|---|---|---|---|
| `input.emoji` | str | `❤` (U+2764) | The emoji to react with |
| `input.message_id` | str | `mid.$cAAA5JGhAguej64_...` | The message being reacted to |
| `input.thread_id` | str | `1198812947547839` | Internal thread ID (NOT interop ID) |
| `input.reaction_status` | str | `"created"` | Always `"created"` for new reactions |
| `input.item_id` | str | `""` | Empty string — not used |

### To remove a reaction

Not captured. Likely same mutation with `reaction_status: "deleted"`.

### Response body

Not captured — browser closed before response was read. HTTP 200 confirms success.

---

## 6. Reaction state on read

Reactions are embedded in each message node:

```json
{
  "reactions": [
    {
      "reaction": "❤",
      "sender_fbid": "111594096907116"
    }
  ]
}
```

**Field paths:**
- Emoji: `node.reactions[N].reaction` (str, emoji character)
- Who reacted: `node.reactions[N].sender_fbid` (str, interop_messaging_user_fbid)
- No timestamp in the read response (only added in mutation response)

**Observed emoji values:** `❤` (U+2764 heart), `😂` (U+1F602 laugh), `💔` (U+1F494 broken heart), `💚` (U+1F49A green heart)

**To determine if YOU reacted:** Compare `sender_fbid` against the viewer's `interop_messaging_user_fbid` (available from the thread response's `viewer` object).

### Scanner logic for reactions

1. On scan, check `node.reactions` for each message
2. Filter where `sender_fbid == viewer_interop_id` to find your own reactions
3. Store the emoji in `my_existing_reaction` field
4. Only auto-react if `my_existing_reaction` is empty AND `my_auto_sent_reaction` is empty

---

## Known gaps (honest assessment)

| Gap | Severity | Mitigation |
|---|---|---|
| Pagination not captured | Medium | Most threads have <20 media items. Test with scrollable container later. |
| Reaction removal mutation | Low | Likely `reaction_status: "deleted"`. Can test manually. |
| Carousel individual slides | Low | Only preview image available. Child media ID in URL but not full slide data. |
| Raven media attachment=null | Low | Disappearing media — not a scanner priority. |
| FIFO matching unreliable | Low | Response data is valid; only request-response pairing affected. Fix in future with request ID tracking. |
| message_id type | Confirmed | String format `mid.$...`, NOT numeric. Schema uses TEXT. |

---

## Summary of concrete answers

1. **Thread-messages query:** `IGDThreadDetailMainViewContainerQuery`, doc_id `26562617700073112`, variable `thread_fbid` = interop messaging user fbid
2. **Message schema:** Documented above with 9 content types, all field paths confirmed from real data
3. **Real thread ID:** `thread.id` / `thread.thread_fbid` (internal) for reactions; `thread_key` / URL param (interop) for queries
4. **Pagination:** `page_info` with base64 cursors exists, but pagination call not captured
5. **Reaction mutation:** `IGDirectReactionSendMutation`, doc_id `24374451552236906`, uses `thread.id` (not interop) and `message_id`
6. **Reaction state on read:** `node.reactions[].reaction` + `node.reactions[].sender_fbid`
