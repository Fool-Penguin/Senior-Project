"""Unit tests for Stage 5 FastAPI Server endpoints."""

import unittest
from fastapi.testclient import TestClient
from codedee.server import app


class TestServerEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        resp = self.client.get("/api/v1/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ONLINE")
        self.assertIn("python", data["supported_languages"])

    def test_analyze_endpoint_symbolic(self):
        payload = {
            "code": "def search(user):\n    sql = 'SELECT * FROM u WHERE id=' + user\n    cursor.execute(sql)\n",
            "language": "python",
            "enable_oracle": False
        }
        resp = self.client.post("/api/v1/analyze", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["language"], "python")
        self.assertIn("maintainability", data)
        self.assertIn("vulnerabilities", data)
        self.assertTrue(len(data["vulnerabilities"]) >= 1)
        self.assertEqual(data["vulnerabilities"][0]["cwe_id"], "CWE-89")


if __name__ == "__main__":
    unittest.main()
