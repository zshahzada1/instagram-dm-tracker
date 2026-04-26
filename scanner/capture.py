"""Network capture for Instagram DM thread messages.

Captures two GraphQL query types:
1. IGDThreadDetailMainViewContainerQuery — initial thread load
2. IGDMessageListOffMsysQuery — pagination (triggered by keyboard input)
"""
import json
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import parse_qs


class ThreadMessagesCapture:
    """Capture IGDThreadDetailMainViewContainerQuery and IGDMessageListOffMsysQuery.

    Pairs requests and responses by content (matching request variables to response body
    identifiers) rather than blind FIFO, because the inbox preload fires queries for
    multiple threads whose responses arrive in unpredictable order.

    Both query types feed into the same message pool, deduplicated by message_id.
    """

    FRIENDLY_NAME = "IGDThreadDetailMainViewContainerQuery"
    OFF_MSYS_FRIENDLY = "IGDMessageListOffMsysQuery"

    def __init__(self, expected_thread_fbid: str, expected_thread_internal_id: str = None):
        if not expected_thread_fbid:
            raise ValueError("expected_thread_fbid is required")
        self.expected_thread_fbid = expected_thread_fbid
        self.expected_thread_internal_id = expected_thread_internal_id
        self._request_queue: List[Dict[str, Any]] = []
        self._pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    def on_request(self, request) -> None:
        """Handle incoming request, capture if it matches either query type."""
        if '/api/graphql' not in request.url:
            return

        try:
            post_data = request.post_data
            if not post_data:
                return

            parsed = parse_qs(post_data)
            if 'fb_api_req_friendly_name' not in parsed:
                return

            friendly_name = parsed['fb_api_req_friendly_name'][0]
            if friendly_name == self.FRIENDLY_NAME:
                query_type = "container"
            elif friendly_name == self.OFF_MSYS_FRIENDLY:
                query_type = "offmsys"
            else:
                return

            variables = None
            if 'variables' in parsed:
                variables = json.loads(parsed['variables'][0])

            self._request_queue.append({
                "url": request.url,
                "method": request.method,
                "friendly_name": friendly_name,
                "query_type": query_type,
                "variables": variables,
            })
        except Exception:
            pass

    def _peek_response(self, response_body: Optional[dict]) -> Tuple[Optional[str], Optional[str]]:
        """Peek at response body to find the match key and query type.

        Returns (match_key, query_type) where query_type is "container" or "offmsys",
        or (None, None) if not a recognized response.
        """
        if not response_body:
            return None, None
        try:
            data = response_body.get("data", {})

            # Try MainViewContainer shape
            thread_data = data.get("get_slide_thread_nullable", {})
            as_thread = thread_data.get("as_ig_direct_thread", {})
            thread_key = as_thread.get("thread_key")
            if thread_key is not None:
                return thread_key, "container"

            # Try OffMsys shape
            fetch_thread = data.get("fetch__SlideThread", {})
            thread_id = fetch_thread.get("id")
            if thread_id is not None:
                return thread_id, "offmsys"

        except Exception:
            pass

        return None, None

    def on_response(self, response) -> None:
        """Pair response with matching request by query-type-specific key.

        For MainViewContainer: match request.variables.thread_fbid == response body thread_key.
        For OffMsys: match request.variables.id == response body fetch__SlideThread.id.
        """
        if not self._request_queue:
            return

        if '/api/graphql' not in response.url:
            return

        response_body = None
        try:
            response_body = response.json()
        except Exception:
            pass

        match_key, query_type = self._peek_response(response_body)
        if match_key is None:
            return

        matching_idx = None
        for i, req in enumerate(self._request_queue):
            if req["query_type"] != query_type:
                continue
            req_vars = req.get("variables") or {}
            if query_type == "container":
                if req_vars.get("thread_fbid") == match_key:
                    matching_idx = i
                    break
            elif query_type == "offmsys":
                if req_vars.get("id") == match_key:
                    matching_idx = i
                    break

        if matching_idx is None:
            return

        matched_request = self._request_queue.pop(matching_idx)
        self._pairs.append((matched_request, {
            "response_body": response_body,
            "query_type": query_type,
        }))

    def _extract_from_container(self, response_body: dict) -> Optional[Dict[str, Any]]:
        """Extract thread metadata and messages from a MainViewContainer response.

        Returns None if thread_key doesn't match expected_thread_fbid.
        """
        data = response_body.get("data", {})
        thread_data = data.get("get_slide_thread_nullable", {})
        as_thread = thread_data.get("as_ig_direct_thread", {})

        body_thread_key = as_thread.get("thread_key")
        if body_thread_key != self.expected_thread_fbid:
            return None

        viewer = as_thread.get("viewer", {})
        viewer_interop_id = viewer.get("interop_messaging_user_fbid")

        thread_internal_id = as_thread.get("id")

        # Extract participant info from users list
        display_name = None
        participant_handle = None
        users = as_thread.get("users", [])
        for user in users:
            if user.get("id") != viewer_interop_id:
                display_name = user.get("full_name")
                participant_handle = user.get("username")
                break

        slide_messages = as_thread.get("slide_messages", {})
        edges = slide_messages.get("edges", [])
        page_info = slide_messages.get("page_info")

        return {
            "viewer_interop_id": viewer_interop_id,
            "thread_key": body_thread_key,
            "thread_internal_id": thread_internal_id,
            "display_name": display_name,
            "participant_handle": participant_handle,
            "edges": edges,
            "page_info": page_info,
        }

    def _extract_from_offmsys(self, response_body: dict) -> Optional[Dict[str, Any]]:
        """Extract messages and page_info from an OffMsys response.

        Returns None if the response id doesn't match expected_thread_internal_id.
        """
        if not self.expected_thread_internal_id:
            return None

        data = response_body.get("data", {})
        fetch_thread = data.get("fetch__SlideThread", {})
        as_thread = fetch_thread.get("as_ig_direct_thread", {})

        body_thread_id = fetch_thread.get("id")
        if body_thread_id != self.expected_thread_internal_id:
            return None

        slide_messages = as_thread.get("slide_messages", {})
        edges = slide_messages.get("edges", [])
        page_info = slide_messages.get("page_info")

        return {
            "edges": edges,
            "page_info": page_info,
        }

    def extract_messages(self) -> Dict[str, Any]:
        """
        Extract all unique message nodes from captured responses for the target thread.

        Processes pairs from BOTH query types, deduplicates by message_id.
        Thread metadata (viewer_interop_id, thread_key, display_name, participant_handle)
        comes only from MainViewContainer responses. Page info prefers the most recent
        OffMsys pair (which carries the next-page cursor), falling back to the last
        MainViewContainer pair.

        Returns:
            Dict with:
                - viewer_interop_id: str
                - thread_key: str
                - thread_internal_id: str
                - display_name: str
                - participant_handle: str
                - messages: List[Dict] - unique message nodes
                - page_info: Dict or None
        """
        if not self._pairs:
            return {
                "viewer_interop_id": None,
                "thread_key": None,
                "thread_internal_id": None,
                "display_name": None,
                "participant_handle": None,
                "messages": [],
                "page_info": None,
            }

        viewer_interop_id = None
        thread_key = None
        thread_internal_id = None
        display_name = None
        participant_handle = None
        all_messages = {}
        latest_page_info = None
        last_offmsys_page_info = None  # Prefer OffMsys for next-page cursor

        for request, response in self._pairs:
            query_type = response.get("query_type", "container")
            response_body = response.get("response_body", {})

            if query_type == "container":
                req_vars = request.get("variables") or {}
                if req_vars.get("thread_fbid") != self.expected_thread_fbid:
                    continue

                extracted = self._extract_from_container(response_body)
                if extracted is None:
                    # body thread_key doesn't match expected
                    body_data = response_body.get("data", {}).get("get_slide_thread_nullable", {}).get("as_ig_direct_thread", {})
                    body_tk = body_data.get("thread_key") if body_data else None
                    if body_tk and body_tk != self.expected_thread_fbid:
                        print(f"  [warn] Pair body thread_key={body_tk} != expected={self.expected_thread_fbid}, skipping")
                    continue

                if not viewer_interop_id:
                    viewer_interop_id = extracted["viewer_interop_id"]
                if not thread_key:
                    thread_key = extracted["thread_key"]
                if not thread_internal_id:
                    thread_internal_id = extracted["thread_internal_id"]
                if not display_name or not participant_handle:
                    display_name = extracted["display_name"]
                    participant_handle = extracted["participant_handle"]

                for edge in extracted["edges"]:
                    node = edge.get("node", {})
                    message_id = node.get("message_id")
                    if message_id and message_id not in all_messages:
                        all_messages[message_id] = node

                if extracted["page_info"]:
                    latest_page_info = extracted["page_info"]

            elif query_type == "offmsys":
                # Also verify request-side matching
                req_vars = request.get("variables") or {}
                if self.expected_thread_internal_id and req_vars.get("id") != self.expected_thread_internal_id:
                    continue

                extracted = self._extract_from_offmsys(response_body)
                if extracted is None:
                    continue

                for edge in extracted["edges"]:
                    node = edge.get("node", {})
                    message_id = node.get("message_id")
                    if message_id and message_id not in all_messages:
                        all_messages[message_id] = node

                if extracted["page_info"]:
                    last_offmsys_page_info = extracted["page_info"]

        # Prefer OffMsys page_info for pagination state
        final_page_info = last_offmsys_page_info or latest_page_info

        return {
            "viewer_interop_id": viewer_interop_id,
            "thread_key": thread_key,
            "thread_internal_id": thread_internal_id,
            "display_name": display_name,
            "participant_handle": participant_handle,
            "messages": list(all_messages.values()),
            "page_info": final_page_info,
        }

    def reset(self) -> None:
        """Clear all captured data."""
        self._request_queue = []
        self._pairs = []
