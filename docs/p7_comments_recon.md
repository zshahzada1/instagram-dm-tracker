# P7 Comments Recon — 2026-04-26T20:38:00Z

## Target
- Shortcode: DWNK5V3DW_L
- Poster: @nickc.tv
- Direct URL: https://www.instagram.com/reel/DWNK5V3DW_L/

## GraphQL calls captured
- Total: 32
- Comment-related: 0

## All friendly_names observed
- IGDBadgeCountOffMsysQuery
- IGDInboxTrayQuery
- IGDPartnershipInboxThreadListButtonOffMsysQuery
- IGDThreadDetailMainViewContainerQuery
- LSPlatformGraphQLLightspeedRequestForIGDQuery
- PolarisAutomaticPreviewsDisabledContextProviderQuery
- PolarisDirectInboxQPInterstitialQuery
- PolarisDirectInboxQuery
- PolarisViewerSettingsQuery
- QuickPromotionSupportIGSchemaBatchFetchQuery
- useFeatureLimitsOffMsysQuery
- useIGDNoteCTADataQuery
- useIGDShouldShowAdResponsesTabQuery
- useIGDSystemFolderUnreadThreadCountQuery

## Comment query identification
**None found.** No comment-related GraphQL calls were captured during either pass.

## Pass A outcome: FAILED — reason
Pass A (DM inbox flow) failed because the DM inbox query selector `a[href*="/direct/t/"]` returned 0 thread links. The screenshot `p7_a1_inbox.png` shows the inbox loaded but no thread list was visible in the DOM structure captured by Playwright. This may be due to:
- Instagram's current DOM structure using different selectors for thread links
- Thread list rendering after JavaScript hydration
- Inbox state showing a different view (e.g., empty inbox or search view)

## Key observations from Pass B (direct URL)
**IMPORTANT FINDING:** Comments are clearly visible in the UI (see screenshots `p7_b1_post_direct.png`, `p7_b3_comments_visible.png`, `p7_b4_comments_scrolled.png`), but ZERO comment-related GraphQL calls were captured. This suggests one of the following scenarios:

1. **Comments embedded in initial page load:** Comments may be returned as part of the initial HTML/JSON data when the reel page loads, rather than fetched via separate GraphQL queries.

2. **Different API endpoint:** Comments might use a non-GraphQL endpoint (e.g., REST API or WebSocket) that our interceptor doesn't capture.

3. **Client-side rendering with cached data:** Comments could be rendered from client-side cache or embedded data that doesn't trigger network requests.

4. **Keyword matching too narrow:** The actual comment query may use a friendly_name that doesn't contain our keywords ("comment", "Comment", "MediaComment", etc.).

## Key open questions for P7 build
1. **Where do comments actually come from?** The visible comments in the UI did not trigger any captured GraphQL calls, suggesting they're embedded in the initial page load or use a different API.

2. **What is the actual data source?** Without a captured GraphQL call, we don't know the field structure, pagination mechanism, or how to fetch comments programmatically.

3. **How to access comments data?** Need to determine if comments are:
   - Embedded in the initial page HTML/JSON
   - Available via a different API endpoint (not /api/graphql)
   - Loaded via a different mechanism (WebSocket, SSE, etc.)

4. **Missing fields we expected to find:** None were found because no comment calls were captured at all.

## Recommendation for P7
**BLOCKER:** The P7 comments recon spike did not capture any comment-related GraphQL calls, despite comments being clearly visible in the UI. This indicates that Instagram's current implementation does not use the expected GraphQL endpoint for comment fetching on reels, OR the comments are embedded in the initial page load data.

**Next steps required:**
1. Investigate the initial page load response to see if comments are embedded in the HTML or inline JSON.
2. Check if comments use a different API endpoint (e.g., `/api/v1/media/{id}/comments/` or similar).
3. Consider alternative approaches such as parsing the page HTML directly or using a different network interception strategy.

**Current status:** Not ready to proceed with P7 comments panel build. The data source and API shape for comments remains unknown.

---

## Recon v2 — 2026-04-26T20:48:00Z

### Method
Broad interceptor (all IG domains, not just /api/graphql) + inline JSON extraction + manual HTML parsing.

### All unique URL paths seen
/ajax/bootloader-endpoint/, /ajax/bulk-route-definitions/, /ajax/bz, /ajax/qm/, /api/graphql, /api/graphql/, /api/v1/web/fxcal/ig_sso_users/, /btmanifest/, /common/referer_frame.php, /graphql/query, /instagram/login_sync/, /instagram/login_sync/update/, /instagram/sync/, /o1/v/t* (media files), /reel/DWNK5V3DW_L/, /reels/DWNK5V3DW_L/, /rsrc.php/* (JS/CSS assets), /static_resources/webworker_v1/init_script/, /sync/instagram/, /v/t* (images)

### Comment-containing responses (from network)
- Count: 4
- Response 1: POST /graphql/query (status=200, friendly=PolarisFeedTimelineRootV2Query, doc_id=26119595701076165)
- Response 2: POST /graphql/query (status=200, friendly=PolarisClipsTabDesktopPaginationQuery, doc_id=26465136803170435)
- Response 3: POST /graphql/query (status=200, friendly=PolarisClipsAdsPoolQuery, doc_id=34488391784138948)
- Response 4: POST /graphql/query (status=200, friendly=PolarisClipsTabDesktopPaginationQuery, doc_id=26465136803170435)

**Note:** These 4 responses contain "comment" keyword in body but are feed timeline and clips pagination queries, NOT specific comment fetching for our target reel. The actual comment arrays were not found in any network responses.

### Inline JSON findings
- Blobs found: 48 inline JSON blobs from script tags
- Comment data found: 0 actual comment arrays in inline JSON
- Comment metadata found: Embedded in page HTML (see Step 3 findings)
  - comment_count: 676
  - comments_disabled: null (comments enabled)
  - commenting_disabled_for_viewer: null (viewer can comment)
  - caption text: "they been cookin 🔥"

### Step 3 findings
Manual HTML extraction revealed:

**Comment Metadata (embedded in page HTML):**
```
"comment_count": 676
"comments_disabled": null
"commenting_disabled_for_viewer": null
```

**Caption (embedded in page HTML):**
```json
{"text":"they been cookin 🔥","pk":"18346921210241041","has_translation":null}
```

**Individual Comments:** NOT found in initial HTML. Only 2 "text" fields found total (caption text + one other), out of 676 total comments. This confirms that individual comment objects are NOT embedded in the initial page load.

**Script Tags Analysis:**
- 103 script tags found in page HTML
- 8 script tags contain "comment" keyword
- Script tag 65 contains target shortcode DWNK5V3DW_L with media metadata
- No script tags contain actual comment arrays with user/text/pk structure

### Conclusion
**CRITICAL FINDING:** Instagram comments for reels use a lazy-loading mechanism that does NOT trigger during initial page load or scrolling. The evidence is clear:

1. **Comment metadata IS embedded:** comment_count (676), disabled flags, and caption are in the initial HTML
2. **Individual comments are NOT embedded:** Only 2 "text" fields found in entire HTML vs 676 actual comments
3. **No GraphQL calls captured:** Despite visible comments in UI, no comment-specific GraphQL requests were made during navigation or scrolling
4. **Different loading mechanism:** Comments appear to use a mechanism that doesn't fire during passive observation (possibly WebSocket, SSE, or a very specific trigger that our session didn't activate)

**Blocker for P7:** The comment data source and API shape remain unknown. Comments are visible in the UI but:
- Not in initial HTML (only metadata)
- Not fetched via captured GraphQL calls during passive navigation/scrolling
- Require an unknown trigger or mechanism to load

**Next steps required:**
1. Identify the trigger that causes comments to load (likely user interaction with comments section)
2. Capture the actual comment API call that fires when that trigger occurs
3. Determine if comments use a different endpoint (REST, WebSocket, etc.) or require specific request parameters

**Status:** STILL BLOCKED — Comment data source and API shape unknown.

---

## Recon v3 — 2026-04-26T22:38:00Z

### Fix applied
Clicked comment button (right-side action bar) to trigger comment loading.

### Comment button selector outcome
- Found: yes
- Selector that matched: `[aria-label="Comment"]` (7 matches on page, used first match)
- Comment button successfully clicked, triggering 55 new network responses

### Post-click network calls (new calls after click)
- Total new responses after click: 55
- Paths seen (new only): Multiple new JS resources loaded, plus 2 new GraphQL calls
- Comment arrays found: yes — endpoint identified!

### If comment arrays found
- **friendly_name**: `PolarisPostCommentsContainerQuery`
- **doc_id**: `26113520058347588`
- **Endpoint**: POST /api/graphql
- **Path in response JSON**: `xdt_api__v1__media__media_id__comments__connection.edges[]`
- **Fields on each comment**: NOT YET KNOWN — response data was truncated in artifacts. Additional recon needed to capture full comment object structure.
- **Sample comment text**: NOT YET KNOWN — see above
- **has pagination**: yes — `page_info` contains `end_cursor`, `has_next_page`, `start_cursor`, `has_previous_page`

### Additional findings
- **Comment metadata endpoint**: `PolarisClipsDesktopCommentsPopoverQuery` (doc_id=26591948213770017) returns comment_count, commenting_disabled_for_viewer, comments_disabled, but not individual comments
- **Actual comments endpoint**: `PolarisPostCommentsContainerQuery` (doc_id=26113520058347588) returns the comment array in `xdt_api__v1__media__media_id__comments__connection.edges[]`

### Status
**RESOLVED — endpoint identified** but **partial data**. We successfully found the comments endpoint and pagination structure, but need to capture a full response (non-truncated) to determine the complete field structure of individual comment objects (text, pk, user, timestamps, likes, etc.).

**Next steps required**:
1. Re-run the capture with larger truncation limits to preserve full comment object structure
2. Determine the query variables required (likely media ID/pk)
3. Map all comment fields for database schema design

---

## Recon v4 — 2026-04-26T22:45:00Z

### Calls captured
- Total PolarisPostCommentsContainerQuery calls: 1 (initial load)
- PolarisClipsDesktopCommentsPopoverQuery: 1 (metadata only)

### Query variables shape
```json
{
  "media_id": "3858788376673873867",
  "__relay_internal__pv__PolarisIsLoggedInrelayprovider": true
}
```
**Media ID variable**: `media_id` — Instagram's internal media ID (not the shortcode). For our target reel DWNK5V3DW_L, the media_id is "3858788376673873867".

### Comment object schema (from call 0)
**Path**: `xdt_api__v1__media__media_id__comments__connection.edges[].node`

**Fields on each comment node**:
- `pk`: str — Comment primary key, e.g., "18074401373446963"
- `user`: dict — User object (see fields below)
- `is_covered`: bool — Whether comment is covered/hidden
- `child_comment_count`: int — Number of replies, e.g., 30
- `restricted_status`: null | str — Content restriction status
- `has_translation`: null | bool — Whether translation available
- `has_liked_comment`: bool — Whether current user liked this comment
- `text`: str — Comment text content
- `giphy_media_info`: null | dict — GIF media info (for animated comments)
- `created_at`: int — Unix timestamp (seconds), e.g., 1774233668
- `is_edited`: bool — Whether comment was edited
- `parent_comment_id`: null | str — Parent comment pk if this is a reply
- `comment_like_count`: int — Number of likes on this comment, e.g., 96124
- `fallback_user_info`: null | dict — Fallback user info
- `__typename`: str — Always "XDTCommentDict"

### Pagination
- **cursor field**: `page_info.end_cursor` — Base64-encoded JSON string containing:
  - `cached_comments_cursor`: Internal cache cursor
  - `bifilter_token`: Bifurcation filter token
- **has_next_page**: bool — Whether more comments available
- **has_previous_page**: bool — Whether previous page available (always false for initial load)
- **variable to send next cursor**: NOT DETERMINED — Likely `after` or `cursor` parameter in variables for pagination calls. Would need to trigger a pagination call to confirm.

### Replies
- **Are replies nested inside comment objects?**: PARTIALLY — Only `child_comment_count` is present (number of replies), but the actual reply comments are NOT in the same response. Replies appear to be fetched separately (different endpoint or pagination).

### User object fields
Fields on `comment.user`:
- `is_verified`: bool — Whether user has blue checkmark
- `id`: str — User ID, e.g., "74687067973"
- `pk`: str — User pk (same as id), e.g., "74687067973"
- `is_unpublished`: bool — Account publication status
- `profile_pic_url`: str — CDN URL to profile picture
- `username`: str — Instagram handle, e.g., "smittythechamp06"
- `fbid_v2`: str — Facebook ID v2

### Status
**COMPLETE — schema fully mapped**. We have captured the full comment object schema with all 16 fields, user object schema with 7 fields, and pagination structure. The only unknown is the exact variable name for pagination cursor (likely `after` or `cursor`), but this can be determined during implementation by testing the standard Relay pagination pattern.

**Key findings for P7 build**:
1. Endpoint: `POST /api/graphql` with `doc_id=26113520058347588` and `friendly_name=PolarisPostCommentsContainerQuery`
2. Required variable: `media_id` (Instagram's internal media ID, not shortcode)
3. Comments array path: `data.xdt_api__v1__media__media_id__comments__connection.edges[].node`
4. Each comment has: pk, user object, text, likes count, timestamp, reply count, edit status, like status
5. Pagination available via `page_info.end_cursor` and `has_next_page`
6. Replies counted via `child_comment_count` but actual replies fetched separately
7. Media ID needs to be obtained from media metadata (e.g., via `PolarisClipsDesktopCommentsPopoverQuery`)
