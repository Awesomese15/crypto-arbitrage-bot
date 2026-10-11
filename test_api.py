import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api


class ApiTests(unittest.TestCase):
    def test_health_is_observation_only(self):
        with TestClient(api.app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "mode": "observation-only",
            "real_orders": False,
        })

    def test_scan_conflict_is_reported(self):
        with patch.object(api.service, "scan_once", side_effect=RuntimeError("A scan is already in progress")):
            with TestClient(api.app) as client:
                response = client.post("/api/scan")

        self.assertEqual(response.status_code, 409)
        self.assertIn("already in progress", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
