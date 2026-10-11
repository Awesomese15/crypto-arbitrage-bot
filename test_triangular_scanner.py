import unittest

from datetime import datetime, timedelta, timezone

from triangular_scanner import (
    BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS,
    calculate_receive_time_skew,
)


class ReceiveTimeSkewTests(unittest.TestCase):
    def setUp(self):
        received_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.books = {
            "BTCUSDT": {"received_at": received_at},
            "ETHBTC": {"received_at": received_at},
            "ETHUSDT": {"received_at": received_at},
        }

    def test_accepts_skew_at_provisional_threshold(self):
        self.books["ETHUSDT"]["received_at"] += timedelta(
            seconds=BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS
        )

        skew = calculate_receive_time_skew(self.books)

        self.assertLessEqual(
            skew.total_seconds(), BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS
        )

    def test_identifies_excessive_skew(self):
        self.books["ETHUSDT"]["received_at"] += timedelta(
            seconds=BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS,
            milliseconds=1,
        )

        skew = calculate_receive_time_skew(self.books)

        self.assertGreater(
            skew.total_seconds(), BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS
        )


if __name__ == "__main__":
    unittest.main()
