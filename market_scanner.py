
import time
import requests
from decimal import Decimal
from datetime import datetime

BASE_URL = "https://data-api.binance.vision/api/v3/ticker/bookTicker"

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
]

POLL_INTERVAL_SECONDS = 5


def fetch_order_book_top(symbol):
    """Fetch the best bid and ask using public market data."""
    response = requests.get(
        BASE_URL,
        params={"symbol": symbol},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()

    bid = Decimal(data["bidPrice"])
    ask = Decimal(data["askPrice"])
    bid_qty = Decimal(data["bidQty"])
    ask_qty = Decimal(data["askQty"])

    if bid <= 0 or ask <= 0:
        return None

    midpoint = (bid + ask) / Decimal("2")
    spread = ask - bid
    spread_pct = (spread / midpoint) * Decimal("100")

    return {
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "bid_qty": bid_qty,
        "ask_qty": ask_qty,
        "spread": spread,
        "spread_pct": spread_pct,
    }


def scan_markets():
    print(f"\nMarket scan: {datetime.now().isoformat(timespec='seconds')}")
    print("-" * 85)

    for symbol in SYMBOLS:
        try:
            market = fetch_order_book_top(symbol)

            if market is None:
                print(f"{symbol}: invalid market data")
                continue

            print(
                f"{symbol:10} "
                f"Bid: {market['bid']:>14,.8f}  "
                f"Ask: {market['ask']:>14,.8f}  "
                f"Spread: {market['spread_pct']:.5f}%"
            )

        except requests.RequestException as exc:
            print(f"{symbol}: request failed: {exc}")
        except (KeyError, ValueError, ArithmeticError) as exc:
            print(f"{symbol}: invalid response: {exc}")


if __name__ == "__main__":
    print("Binance public market scanner")
    print("Read-only mode: no orders will be placed.")

    while True:
        scan_markets()
        time.sleep(POLL_INTERVAL_SECONDS)
