"""Unit tests for message parser."""
import json
import os
from pathlib import Path

import pytest

from scanner.parser import parse_message_node, extract_shortcode
from scanner.capture import ThreadMessagesCapture


FIXTURE_PATH = Path(__file__).parent.parent / "artifacts" / "recon_network_v2.json"


def load_fixture():
    """Load the recon fixture data."""
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture not found: {FIXTURE_PATH}")

    with open(FIXTURE_PATH, 'r') as f:
        return json.load(f)


def test_extract_shortcode_reel():
    """Test shortcode extraction from reel URLs."""
    assert extract_shortcode("https://www.instagram.com/reel/DXWHYO8ieJM/?id=123") == "DXWHYO8ieJM"
    assert extract_shortcode("https://www.instagram.com/reel/ABC123/") == "ABC123"


def test_extract_shortcode_post():
    """Test shortcode extraction from post URLs."""
    assert extract_shortcode("https://www.instagram.com/p/DXZizQRDDiF/?is_sponsored=false") == "DXZizQRDDiF"
    assert extract_shortcode("https://www.instagram.com/p/ABC123/") == "ABC123"


def test_extract_shortcode_carousel():
    """Test shortcode extraction from carousel URLs."""
    url = "https://www.instagram.com/p/DWq3zi7j-ix/?carousel_share_child_media_id=123"
    assert extract_shortcode(url) == "DWq3zi7j-ix"


def test_extract_shortcode_none():
    """Test that non-media URLs return None."""
    assert extract_shortcode("https://www.instagram.com/stories/username/123") is None
    assert extract_shortcode("https://www.instagram.com/direct/t/123/") is None


def test_parser_against_fixture():
    """Test parser against real fixture data."""
    fixture = load_fixture()

    viewer_interop_id = None
    messages_by_type = {
        "reel": [],
        "post": [],
        "carousel": [],
        "story": [],
        "text": [],
        "reaction_log": [],
        "other": [],
    }

    for req in fixture.get("requests", []):
        if req.get("friendly_name") != "IGDThreadDetailMainViewContainerQuery":
            continue

        response_body = req.get("response_body", {})
        data = response_body.get("data", {})
        thread_data = data.get("get_slide_thread_nullable", {})
        as_ig_direct_thread = thread_data.get("as_ig_direct_thread", {})

        if not viewer_interop_id:
            viewer = as_ig_direct_thread.get("viewer", {})
            viewer_interop_id = viewer.get("interop_messaging_user_fbid")

        slide_messages = as_ig_direct_thread.get("slide_messages", {})
        edges = slide_messages.get("edges", [])

        for edge in edges:
            node = edge.get("node", {})
            content_type = node.get("content_type")

            parsed = parse_message_node(node, viewer_interop_id or "")

            if parsed is None:
                if content_type == "TEXT":
                    messages_by_type["text"].append(node.get("message_id"))
                elif content_type == "REACTION_LOG_XMAT":
                    messages_by_type["reaction_log"].append(node.get("message_id"))
                else:
                    messages_by_type["other"].append((content_type, node.get("message_id")))
            else:
                item_type = parsed["item_type"]
                messages_by_type[item_type].append(parsed)

    assert len(messages_by_type["reel"]) > 0, "Should parse at least one reel"
    assert len(messages_by_type["post"]) > 0, "Should parse at least one post"
    assert len(messages_by_type["carousel"]) > 0, "Should parse at least one carousel"

    for reel in messages_by_type["reel"]:
        assert reel["item_type"] == "reel"
        assert reel["ig_message_id"].startswith("mid.$")
        assert reel["media_shortcode"] is not None
        assert reel["media_url"] is not None
        assert reel["poster_handle"] is not None

    for post in messages_by_type["post"]:
        assert post["item_type"] == "post"
        assert post["ig_message_id"].startswith("mid.$")
        assert post["media_shortcode"] is not None
        assert post["media_url"] is not None
        assert post["poster_handle"] is not None

    for carousel in messages_by_type["carousel"]:
        assert carousel["item_type"] == "carousel"
        assert carousel["ig_message_id"].startswith("mid.$")
        assert carousel["media_shortcode"] is not None
        assert carousel["media_url"] is not None
        assert carousel["poster_handle"] is not None

    assert len(messages_by_type["text"]) > 0, "Should have TEXT messages that return None"
    assert len(messages_by_type["reaction_log"]) > 0, "Should have REACTION_LOG_XMAT messages that return None"


def test_parser_message_id_validation():
    """Test that parser returns None for messages without valid message_id."""
    viewer_interop_id = "123456789"

    assert parse_message_node({}, viewer_interop_id) is None
    assert parse_message_node({"message_id": "invalid"}, viewer_interop_id) is None
    assert parse_message_node({"message_id": None}, viewer_interop_id) is None


def test_parser_required_fields():
    """Test that parser returns None when required fields are missing."""
    viewer_interop_id = "123456789"

    node = {
        "message_id": "mid.$ABC123",
        "content_type": "MESSAGE_INLINE_SHARE",
        "content": {
            "__typename": "SlideMessageXMAContent",
            "xma": {
                "__typename": "SlideMessagePortraitXMA",
                "xmaHeaderTitle": "test_user",
                "xmaPreviewImage": {"url": "https://example.com/img.jpg"},
                "target_url": "https://www.instagram.com/reel/ABC123/"
            }
        },
        "sender_fbid": "999999999",
    }

    result = parse_message_node(node, viewer_interop_id)
    assert result is None


class MockRequest:
    """Minimal mock of Playwright request for capture tests."""
    def __init__(self, url, post_data):
        self.url = url
        self.post_data = post_data
        self.method = "POST"


# NOTE: These capture tests use the recon fixture which only contains
# IGDThreadDetailMainViewContainerQuery data. IGDMessageListOffMsysQuery
# is not in the fixture, so OffMsys pairing/filtering is tested by real scans.


class MockResponse:
    """Minimal mock of Playwright response for capture tests."""
    def __init__(self, url, body):
        self.url = url
        self._body = body

    def json(self):
        return self._body


def test_capture_filters_by_thread_fbid():
    """Test that ThreadMessagesCapture only returns messages for the expected thread.

    Simulates the inbox preload scenario: multiple IGDThreadDetailMainViewContainerQuery
    requests for different threads fire, then responses arrive in unpredictable order.
    Verifies content-based pairing matches correctly and extract_messages filters
    to only the expected thread.
    """
    from urllib.parse import urlencode

    fixture = load_fixture()

    target_requests = []
    other_requests = []
    all_responses = []

    for entry in fixture.get("requests", []):
        url = entry.get("url", "https://www.instagram.com/api/graphql")
        friendly_name = entry.get("friendly_name")
        doc_id = entry.get("doc_id")
        variables = entry.get("variables")
        response_body = entry.get("response_body")

        if friendly_name == "IGDThreadDetailMainViewContainerQuery" and doc_id:
            params = {
                "fb_api_req_friendly_name": friendly_name,
                "doc_id": doc_id,
            }
            if variables:
                params["variables"] = json.dumps(variables)
            tfb = (variables or {}).get("thread_fbid")
            target_requests.append((tfb, MockRequest(url, urlencode(params))))

        if response_body is not None:
            all_responses.append(MockResponse(url, response_body))

    if not target_requests:
        pytest.skip("No IGDThreadDetailMainViewContainerQuery requests in fixture")

    # Pick the thread_fbid that appears most often in target requests
    from collections import Counter
    tfb_counts = Counter(tfb for tfb, _ in target_requests if tfb)
    expected_thread_fbid = tfb_counts.most_common(1)[0][0]

    capture = ThreadMessagesCapture(expected_thread_fbid=expected_thread_fbid)

    # Feed all requests first (simulating inbox preload firing multiple queries)
    for _, mock_req in target_requests:
        capture.on_request(mock_req)

    # Feed all responses (some may not be for our query type)
    for mock_resp in all_responses:
        capture.on_response(mock_resp)

    extracted = capture.extract_messages()

    assert extracted["thread_key"] == expected_thread_fbid, \
        f"Expected thread_key={expected_thread_fbid}, got {extracted['thread_key']}"

    assert len(extracted["messages"]) > 0, \
        "Should have at least one message for the expected thread"

    for msg in extracted["messages"]:
        assert msg.get("message_id", "").startswith("mid.$"), \
            f"All messages should have mid.$ IDs, got {msg.get('message_id')}"


def test_capture_rejects_wrong_thread():
    """Test that extract_messages returns empty for a thread_fbid not in the data."""
    from urllib.parse import urlencode

    fixture = load_fixture()

    all_responses = []
    any_target_found = False

    for entry in fixture.get("requests", []):
        url = entry.get("url", "https://www.instagram.com/api/graphql")
        friendly_name = entry.get("friendly_name")
        doc_id = entry.get("doc_id")
        variables = entry.get("variables")
        response_body = entry.get("response_body")

        if friendly_name == "IGDThreadDetailMainViewContainerQuery" and doc_id:
            any_target_found = True
            params = {
                "fb_api_req_friendly_name": friendly_name,
                "doc_id": doc_id,
            }
            if variables:
                params["variables"] = json.dumps(variables)
            mock_req = MockRequest(url, urlencode(params))
            # We don't feed these requests — they won't be queued.
            # The capture should have zero matching pairs for the nonexistent thread.

        if response_body is not None:
            all_responses.append(MockResponse(url, response_body))

    if not any_target_found:
        pytest.skip("No IGDThreadDetailMainViewContainerQuery requests in fixture")

    capture = ThreadMessagesCapture(expected_thread_fbid="99999999999999999")

    for mock_resp in all_responses:
        capture.on_response(mock_resp)

    extracted = capture.extract_messages()
    assert extracted["thread_key"] is None
    assert len(extracted["messages"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
