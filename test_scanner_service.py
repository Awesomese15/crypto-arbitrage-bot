import unittest
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from scanner_service import ScannerService


class MemoryLedger:
    def __init__(self):
        self.observations = []

    def record_observation(self, **kwargs):
        self.observations.append(kwargs)


def fake_book(received_at):
    return {
        "bids": [(Decimal("100"), Decimal("10"))],
        "asks": [(Decimal("101"), Decimal("10"))],
        "last_update_id": 42,
        "received_at": received_at,
    }


class ScannerServiceTests(unittest.TestCase):
    def service(self):
        return ScannerService(ledger=MemoryLedger())

    @patch("scanner_service.engine.fetch_depth")
    def test_one_shot_scan_records_each_route_once(self, fetch_depth):
        received_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        fetch_depth.side_effect = [
            fake_book(received_at),
            fake_book(received_at),
            fake_book(received_at),
        ]
        service = self.service()

        result = service.scan_once()

        self.assertEqual(len(result["routes"]), 2)
        self.assertEqual(len(service._ledger.observations), 2)
        self.assertEqual(
            [observation["route"] for observation in service._ledger.observations],
            [
                "Route A: USDT -> BTC -> ETH -> USDT",
                "Route B: USDT -> ETH -> BTC -> USDT",
            ],
        )

    @patch("scanner_service.engine.fetch_depth")
    def test_excessive_skew_records_two_incomplete_observations(self, fetch_depth):
        received_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        fetch_depth.side_effect = [
            fake_book(received_at),
            fake_book(received_at),
            fake_book(received_at + timedelta(seconds=3)),
        ]
        service = self.service()

        result = service.scan_once()

        self.assertEqual(result["receive_time_skew_seconds"], 3.0)
        self.assertEqual(len(service._ledger.observations), 2)
        for observation in service._ledger.observations:
            self.assertEqual(observation["status"], "INCOMPLETE")
            self.assertEqual(observation["reason"], "BOOK_RECEIVE_SKEW_EXCEEDED")
            self.assertIsNone(observation["ending_balance"])

    def test_start_is_idempotent_and_stop_is_safe(self):
        service = self.service()
        started = threading.Event()
        release = threading.Event()

        def monitor():
            started.set()
            release.wait(1)

        with patch.object(service, "_monitor", side_effect=monitor) as mocked_monitor:
            self.assertTrue(service.start())
            self.assertTrue(started.wait(1))
            self.assertFalse(service.start())
            release.set()
            service.stop()
            mocked_monitor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
