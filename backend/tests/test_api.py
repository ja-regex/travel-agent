import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app


async def fake_agent_stream(_messages):
    yield '{"type":"status","message":"Python agent reached."}\n'
    yield '{"type":"token","text":"Hello from Python."}\n'


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_identifies_python_agent(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "agent": "python"})

    def test_chat_preserves_ndjson_stream_contract(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test", "TAVILY_API_KEY": "test"},
            ),
            patch("backend.app.run_travel_agent", fake_agent_stream),
        ):
            response = self.client.post(
                "/chat",
                json={"messages": [{"role": "user", "content": "Plan Vietnam"}]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-ndjson", response.headers["content-type"])
        self.assertEqual(
            response.text.splitlines(),
            [
                '{"type":"status","message":"Python agent reached."}',
                '{"type":"token","text":"Hello from Python."}',
            ],
        )


if __name__ == "__main__":
    unittest.main()
