import unittest
import csv
import tempfile
from pathlib import Path
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

    def test_route_history_filters_match_csv_route_names(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "paper_observations.csv"
            with filename.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=[
                    "timestamp", "route", "starting_balance",
                    "estimated_ending_balance", "estimated_profit_loss",
                    "return_pct", "status", "reason",
                ])
                writer.writeheader()
                writer.writerows([
                    {"timestamp": "a", "route": "Route A: USDT -> BTC -> ETH -> USDT", "status": "REJECTED"},
                    {"timestamp": "b", "route": "Route B: USDT -> ETH -> BTC -> USDT", "status": "INCOMPLETE"},
                ])

            with patch("scanner_service.OBSERVATIONS_FILE", str(filename)):
                route_a = api.observations(route="Route A: USDT -> BTC -> ETH -> USDT", status_filter=None, limit=100)
                route_b = api.observations(route="Route B: USDT -> ETH -> BTC -> USDT", status_filter=None, limit=100)

        self.assertEqual([row["timestamp"] for row in route_a["observations"]], ["a"])
        self.assertEqual([row["timestamp"] for row in route_b["observations"]], ["b"])

    def test_status_scan_lifecycle_and_config_endpoints(self):
        scan_result = {"routes": [
            {"route": "Route A: USDT -> BTC -> ETH -> USDT", "status": "REJECTED"},
            {"route": "Route B: USDT -> ETH -> BTC -> USDT", "status": "INCOMPLETE"},
        ]}
        config_result = {
            "starting_amount": "125",
            "fee_rate": "0.001",
            "safety_threshold_pct": "0.05",
            "poll_interval_seconds": 5,
            "receive_skew_threshold_seconds": 2,
        }
        with patch.object(api.service, "status", return_value={"running": False}), \
             patch.object(api.service, "scan_once", return_value=scan_result), \
             patch.object(api.service, "start", return_value=True), \
             patch.object(api.service, "is_running", return_value=False), \
             patch.object(api.service, "stop"), \
             patch.object(api.service, "update_config"), \
             patch.object(api.service, "serialized_config", return_value=config_result):
            with TestClient(api.app) as client:
                self.assertEqual(client.get("/api/status").status_code, 200)
                scan_response = client.post("/api/scan")
                start_response = client.post("/api/monitor/start")
                stop_response = client.post("/api/monitor/stop")
                config_response = client.post("/api/config", json={
                    "starting_amount": 125,
                    "fee_rate": 0.001,
                    "safety_threshold_pct": 0.05,
                    "poll_interval_seconds": 5,
                })

        self.assertEqual(scan_response.status_code, 200)
        self.assertEqual(len(scan_response.json()["routes"]), 2)
        self.assertEqual(start_response.json(), {"running": True})
        self.assertEqual(stop_response.json(), {"running": False})
        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(config_response.json(), config_result)


if __name__ == "__main__":
    unittest.main()
