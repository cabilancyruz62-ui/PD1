"""Exercise the ASGI endpoints using the standard library (no HTTP test dependency)."""
import asyncio
import json
import unittest
import main
from wire import WireMonitor


async def request(method, path, payload=None):
    messages = []
    body = b"" if payload is None else json.dumps(payload).encode()

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    await main.app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 12345),
    }, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    response = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status, json.loads(response)


class WireAPITests(unittest.TestCase):
    def setUp(self):
        self.original = main.wire_monitor
        self.now = 0.0
        main.wire_monitor = WireMonitor(clock=lambda: self.now)

    def tearDown(self):
        main.wire_monitor = self.original

    def call(self, method, path, payload=None):
        return asyncio.run(request(method, path, payload))

    def test_wire_lifecycle_through_api(self):
        status, data = self.call("GET", "/api/sensors")
        self.assertEqual(status, 200)
        self.assertIsNone(data["wire"]["connected"])
        self.assertIsNone(data["angle_deg"])
        for connected in (True, False):
            status, data = self.call("POST", "/api/hardware/wire", {"connected": connected})
            self.assertEqual(status, 200)
            self.assertIs(data["wire"]["connected"], connected)
            _, sensors = self.call("GET", "/api/sensors")
            self.assertIs(sensors["wire"]["connected"], connected)
        self.now = 5.0
        _, sensors = self.call("GET", "/api/sensors")
        self.assertFalse(sensors["wire"]["fresh"])
        self.assertIsNone(sensors["wire"]["connected"])

    def test_rejects_invalid_signals_without_updating_state(self):
        for payload in ({}, {"connected": "true"}, {"connected": 1}, {"connected": None}, {"connected": True, "extra": 1}):
            status, _ = self.call("POST", "/api/hardware/wire", payload)
            self.assertEqual(status, 422)
            self.assertFalse(main.wire_monitor.snapshot()["fresh"])


if __name__ == "__main__":
    unittest.main()
