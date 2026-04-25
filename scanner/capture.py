"""Network capture for Instagram DM thread messages."""
import json
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import parse_qs


class ThreadMessagesCapture:
    """Capture IGDThreadDetailMainViewContainerQuery responses from network traffic.

    Filters to a single target thread by expected_thread_fbid. Pairs requests and
    responses by content (matching request variables.thread_fbid to response body
    thread_key) rather than blind FIFO, because the inbox preload fires queries for
    multiple threads whose responses arrive in unpredictable order.
    """

    FRIENDLY_NAME = "IGDThreadDetailMainViewContainerQuery"

    def __init__(self, expected_thread_fbid: str):
        if not expected_thread_fbid:
            raise ValueError("expected_thread_fbid is required")
        self.expected_thread_fbid = expected_thread_fbid
        self._request_queue: List[Dict[str, Any]] = []
        self._pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    def on_request(self, request) -> None:
        """Handle incoming request, capture if it matches our query."""
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
            if friendly_name != self.FRIENDLY_NAME:
                return

            variables = None
            if 'variables' in parsed:
                variables = json.loads(parsed['variables'][0])

            self._request_queue.append({
                "url": request.url,
                "method": request.method,
                "friendly_name": friendly_name,
                "variables": variables,
            })
        except Exception:
            pass

    def _extract_thread_key(self, response_body: Optional[dict]) -> Optional[str]:
        """Extract thread_key from a response body, or None if not our query type."""
        if not response_body:
            return None
        try:
            data = response_body.get("data", {})
            thread_data = data.get("get_slide_thread_nullable", {})
            as_ig_direct_thread = thread_data.get("as_ig_direct_thread", {})
            return as_ig_direct_thread.get("thread_key")
        except Exception:
            return None

    def on_response(self, response) -> None:
        """Handle incoming response, pair with matching request by thread_key content.

        Peek at the response body first. If it doesn't contain a thread_key
        (i.e. it's not an IGDThreadDetailMainViewContainerQuery response), leave
        the request queue untouched. If it does, find the queued request whose
        variables.thread_fbid matches and pair them.
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

        thread_key = self._extract_thread_key(response_body)
        if thread_key is None:
            return

        matching_idx = None
        for i, req in enumerate(self._request_queue):
            req_vars = req.get("variables") or {}
            if req_vars.get("thread_fbid") == thread_key:
                matching_idx = i
                break

        if matching_idx is None:
            return

        matched_request = self._request_queue.pop(matching_idx)
        self._pairs.append((matched_request, {
            "response_body": response_body,
        }))

    def extract_messages(self) -> Dict[str, Any]:
        """
        Extract all unique message nodes from captured responses for the target thread.

        Only considers pairs where the request's variables.thread_fbid matches
        expected_thread_fbid. Verifies each kept response's body thread_key
        matches expected_thread_fbid as well.

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

        for request, response in self._pairs:
            req_vars = request.get("variables") or {}
            if req_vars.get("thread_fbid") != self.expected_thread_fbid:
                continue

            response_body = response.get("response_body", {})
            data = response_body.get("data", {})
            thread_data = data.get("get_slide_thread_nullable", {})
            as_ig_direct_thread = thread_data.get("as_ig_direct_thread", {})

            body_thread_key = as_ig_direct_thread.get("thread_key")
            if body_thread_key != self.expected_thread_fbid:
                # FIFO pairing may have matched wrong response to right request
                print(f"  [warn] Pair body thread_key={body_thread_key} != expected={self.expected_thread_fbid}, skipping")
                continue

            if not viewer_interop_id:
                viewer = as_ig_direct_thread.get("viewer", {})
                viewer_interop_id = viewer.get("interop_messaging_user_fbid")

            if not thread_key:
                thread_key = body_thread_key

            if not thread_internal_id:
                thread_internal_id = as_ig_direct_thread.get("id")

            if not display_name or not participant_handle:
                users = as_ig_direct_thread.get("users", [])
                for user in users:
                    if user.get("id") != viewer_interop_id:
                        display_name = user.get("full_name")
                        participant_handle = user.get("username")
                        break

            slide_messages = as_ig_direct_thread.get("slide_messages", {})
            edges = slide_messages.get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                message_id = node.get("message_id")
                if message_id and message_id not in all_messages:
                    all_messages[message_id] = node

            page_info = slide_messages.get("page_info")
            if page_info:
                latest_page_info = page_info

        return {
            "viewer_interop_id": viewer_interop_id,
            "thread_key": thread_key,
            "thread_internal_id": thread_internal_id,
            "display_name": display_name,
            "participant_handle": participant_handle,
            "messages": list(all_messages.values()),
            "page_info": latest_page_info,
        }

    def reset(self) -> None:
        """Clear all captured data."""
        self._request_queue = []
        self._pairs = []
