"""Tests for the MOTD module.

Uses FastAPI TestClient to test the API endpoints directly.
"""

from fastapi.testclient import TestClient
from modules.motd import get_module, register_routes, storage
from api import app


client = TestClient(app)


class TestMotdModule:
    """Test the MOTD module definition."""

    def test_get_module_name(self):
        """get_module() returns a Module with name='motd'."""
        module = get_module()
        assert module.name == "motd"

    def test_get_module_has_post_motd(self):
        """get_module() includes a post_motd called_fn."""
        module = get_module()
        fn_names = [fn.name for fn in module.called_fns]
        assert "post_motd" in fn_names

    def test_get_module_post_motd_description(self):
        """post_motd description mentions broadcasting to remote screens."""
        module = get_module()
        fn = next(fn for fn in module.called_fns if fn.name == "post_motd")
        assert "remote screen" in fn.description.lower()


class TestMotdRoutes:
    """Test MOTD API endpoints."""

    def setup_method(self):
        """Clear storage before each test."""
        storage._messages.clear()
        storage._next_id = 1

    def test_list_empty(self):
        """GET /module/motd/ returns empty list when no messages."""
        resp = client.get("/module/motd/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["count"] == 0
        assert data["latest_id"] is None

    def test_post_and_list(self):
        """POST then GET shows the message."""
        resp = client.post("/module/motd/", json={"message": "Hello world!"})
        assert resp.status_code == 200
        msg = resp.json()
        assert msg["message"] == "Hello world!"
        assert msg["author"] is None
        assert "id" in msg
        assert "created_at" in msg

        resp = client.get("/module/motd/")
        data = resp.json()
        assert data["count"] == 1
        assert data["messages"][0]["message"] == "Hello world!"
        assert data["latest_id"] == msg["id"]

    def test_post_with_author(self):
        """POST with author field is stored correctly."""
        resp = client.post("/module/motd/", json={
            "message": "Deploy day!",
            "author": "riven",
        })
        assert resp.status_code == 200
        assert resp.json()["author"] == "riven"

    def test_latest_empty(self):
        """GET /module/motd/latest returns empty message when no messages."""
        resp = client.get("/module/motd/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"]["id"] == 0
        assert data["message"]["message"] == ""

    def test_latest_returns_newest(self):
        """GET /module/motd/latest returns most recent message."""
        client.post("/module/motd/", json={"message": "first"})
        newest = client.post("/module/motd/", json={"message": "second"})
        newest_id = newest.json()["id"]

        resp = client.get("/module/motd/latest")
        assert resp.json()["message"]["id"] == newest_id
        assert resp.json()["message"]["message"] == "second"

    def test_latest_returns_newest_first(self):
        """GET /module/motd/ list is newest-first."""
        client.post("/module/motd/", json={"message": "first"})
        client.post("/module/motd/", json={"message": "second"})

        resp = client.get("/module/motd/")
        messages = resp.json()["messages"]
        assert messages[0]["message"] == "second"
        assert messages[1]["message"] == "first"

    def test_post_empty_message_rejected(self):
        """POST with empty message is rejected by Pydantic validation."""
        resp = client.post("/module/motd/", json={"message": ""})
        assert resp.status_code == 422  # Validation error

    def test_module_discovery(self):
        """GET /module/ lists modules with registered routes."""
        resp = client.get("/module/")
        assert resp.status_code == 200
        modules = resp.json()["modules"]
        names = [m["name"] for m in modules]
        assert "motd" in names


class TestMotdTool:
    """Test the post_motd Python function directly."""

    def setup_method(self):
        storage._messages.clear()
        storage._next_id = 1

    def test_post_motd_basic(self):
        """post_motd() returns a confirmation with ID and preview."""
        from modules.motd.tools import post_motd
        result = post_motd("Deploy v2.1 today!")
        assert "#1" in result
        assert "Deploy v2.1 today!" in result

    def test_post_motd_with_author(self):
        """post_motd() includes author in output."""
        from modules.motd.tools import post_motd
        result = post_motd("Weekly deploy", author="riven")
        assert "by riven" in result

    def test_post_motd_empty_rejected(self):
        """post_motd() rejects empty message."""
        from modules.motd.tools import post_motd
        result = post_motd("")
        assert "empty" in result.lower()
