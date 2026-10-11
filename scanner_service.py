import threading
import time
from datetime import datetime, timezone
from decimal import Decimal

import requests

import triangular_scanner as engine
from paper_ledger import OBSERVATIONS_FILE, PaperLedger


class ScannerService:
    """Observation-only scanner lifecycle used by the local dashboard."""

    def __init__(self, session=None, ledger=None):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._session = session or requests.Session()
        self._ledger = ledger or PaperLedger()
        self._config = {
            "starting_amount": engine.STARTING_USDT,
            "fee_rate": engine.FEE_RATE,
            "safety_threshold_pct": engine.SAFETY_MARGIN_PCT,
            "poll_interval_seconds": engine.POLL_INTERVAL_SECONDS,
        }
        self._latest = None
        self._last_error = None

    @property
    def observation_file(self):
        return OBSERVATIONS_FILE

    def status(self):
        return {
            "running": self.is_running(),
            "config": self.serialized_config(),
            "latest_scan": self._latest,
            "last_error": self._last_error,
            "observation_file": OBSERVATIONS_FILE,
        }

    def serialized_config(self):
        return {
            "starting_amount": str(self._config["starting_amount"]),
            "fee_rate": str(self._config["fee_rate"]),
            "safety_threshold_pct": str(self._config["safety_threshold_pct"]),
            "poll_interval_seconds": self._config["poll_interval_seconds"],
            "receive_skew_threshold_seconds": (
                engine.BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS
            ),
        }

    def update_config(self, starting_amount, fee_rate, safety_threshold_pct, poll_interval_seconds):
        if self.is_running():
            raise RuntimeError("Stop monitoring before changing configuration")
        if starting_amount <= 0 or fee_rate < 0 or safety_threshold_pct < 0:
            raise ValueError("Amounts, fees, and thresholds must be non-negative; amount must be positive")
        if poll_interval_seconds < 1 or poll_interval_seconds > 3600:
            raise ValueError("Polling interval must be between 1 and 3600 seconds")
        self._config.update({
            "starting_amount": Decimal(str(starting_amount)),
            "fee_rate": Decimal(str(fee_rate)),
            "safety_threshold_pct": Decimal(str(safety_threshold_pct)),
            "poll_interval_seconds": int(poll_interval_seconds),
        })

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def scan_once(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("A scan is already in progress")
        try:
            result = self._scan_once_locked()
            self._latest = result
            self._last_error = None
            return result
        except Exception as exc:
            self._last_error = str(exc)
            raise
        finally:
            self._lock.release()

    def _scan_once_locked(self):
        started = datetime.now(timezone.utc)
        books = {
            symbol: engine.fetch_depth(self._session, symbol)
            for symbol in engine.SYMBOLS
        }
        finished = datetime.now(timezone.utc)
        skew = engine.calculate_receive_time_skew(books)
        fee_factor = Decimal("1") - self._config["fee_rate"]

        route_names = [
            ("Route A: USDT -> BTC -> ETH -> USDT", "A"),
            ("Route B: USDT -> ETH -> BTC -> USDT", "B"),
        ]
        if skew.total_seconds() > engine.BOOK_RECEIVE_SKEW_THRESHOLD_SECONDS:
            results = [
                engine.report_rejection(name, "BOOK_RECEIVE_SKEW_EXCEEDED")
                for name, _ in route_names
            ]
        else:
            results = [
                engine.evaluate_route(
                    name,
                    route,
                    books,
                    self._config["starting_amount"],
                    fee_factor,
                    self._config["safety_threshold_pct"],
                )
                for name, route in route_names
            ]

        for result in results:
            self._ledger.record_observation(
                route=result["route"],
                starting_balance=self._config["starting_amount"],
                ending_balance=result["final_usdt"],
                status=result["status"],
                reason=result["reason"],
            )

        return {
            "scan_started_at": started.isoformat(),
            "scan_finished_at": finished.isoformat(),
            "fetch_window_seconds": (finished - started).total_seconds(),
            "receive_time_skew_seconds": skew.total_seconds(),
            "books": self._serialize_books(books),
            "routes": self._serialize_routes(results),
        }

    def _serialize_books(self, books):
        serialized = {}
        for symbol, book in books.items():
            best_bid = book["bids"][0][0] if book["bids"] else None
            best_ask = book["asks"][0][0] if book["asks"] else None
            serialized[symbol] = {
                "best_bid": str(best_bid) if best_bid is not None else None,
                "best_ask": str(best_ask) if best_ask is not None else None,
                "spread": str(best_ask - best_bid) if best_bid is not None and best_ask is not None else None,
                "last_update_id": book["last_update_id"],
                "received_at": book["received_at"].isoformat(),
            }
        return serialized

    @staticmethod
    def _serialize_routes(results):
        return [
            {
                "route": result["route"],
                "final_usdt": None if result["final_usdt"] is None else str(result["final_usdt"]),
                "net_profit": None if result["net_profit"] is None else str(result["net_profit"]),
                "net_pct": None if result["net_pct"] is None else str(result["net_pct"]),
                "gross_pct_estimate": None if result["gross_pct_estimate"] is None else str(result["gross_pct_estimate"]),
                "eligible": result["eligible"],
                "status": result["status"],
                "reason": result["reason"],
            }
            for result in results
        ]

    def start(self):
        if self.is_running():
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor, name="scanner-monitor", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if not self.is_running():
            return False
        self._stop_event.set()
        self._thread.join(timeout=2)
        return True

    def _monitor(self):
        while not self._stop_event.is_set():
            try:
                self.scan_once()
            except (requests.RequestException, ValueError, KeyError, ArithmeticError) as exc:
                self._last_error = str(exc)
            self._stop_event.wait(self._config["poll_interval_seconds"])

