
import time
import requests

from datetime import datetime, timezone
from decimal import Decimal, getcontext
from paper_ledger import PaperLedger

getcontext().prec = 28

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_URL = "https://data-api.binance.vision/api/v3/depth"

STARTING_USDT = Decimal("100")
FEE_RATE = Decimal("0.001")  # Assumed 0.1% per leg
SAFETY_MARGIN_PCT = Decimal("0.05")  # 0.05% net return
DEPTH_LIMIT = 100
POLL_INTERVAL_SECONDS = 5

SYMBOLS = ["BTCUSDT", "ETHBTC", "ETHUSDT"]

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
FEE_FACTOR = ONE - FEE_RATE


# --------------------------------------------------
# Fetch Binance order-book depth
# --------------------------------------------------

def fetch_depth(session, symbol):
    response = session.get(
        BASE_URL,
        params={
            "symbol": symbol,
            "limit": DEPTH_LIMIT,
        },
        timeout=10,
    )

    response.raise_for_status()
    data = response.json()

    return {
        "bids": [
            (Decimal(price), Decimal(quantity))
            for price, quantity in data["bids"]
        ],
        "asks": [
            (Decimal(price), Decimal(quantity))
            for price, quantity in data["asks"]
        ],
        "last_update_id": data["lastUpdateId"],
        "received_at": datetime.now(timezone.utc),
    }


# --------------------------------------------------
# Buy base currency using quote currency
# Example: USDT -> BTC using BTCUSDT asks
# --------------------------------------------------

def buy_base_with_quote(quote_amount, asks):
    remaining_quote = quote_amount
    base_received = ZERO

    for price, available_base in asks:
        if remaining_quote <= ZERO:
            break

        if price <= ZERO or available_base <= ZERO:
            continue

        affordable_base = remaining_quote / price
        bought_base = min(available_base, affordable_base)

        base_received += bought_base
        remaining_quote -= bought_base * price

    tolerance = max(
        Decimal("0.00000001"),
        quote_amount * Decimal("1e-12"),
    )

    if remaining_quote > tolerance:
        return None

    # Assumes fee is deducted from received base currency.
    return base_received * FEE_FACTOR


# --------------------------------------------------
# Sell base currency for quote currency
# Example: BTC -> USDT using BTCUSDT bids
# --------------------------------------------------

def sell_base_for_quote(base_amount, bids):
    remaining_base = base_amount
    quote_received = ZERO

    for price, available_base in bids:
        if remaining_base <= ZERO:
            break

        if price <= ZERO or available_base <= ZERO:
            continue

        sold_base = min(available_base, remaining_base)

        quote_received += sold_base * price
        remaining_base -= sold_base

    tolerance = max(
        Decimal("0.00000001"),
        base_amount * Decimal("1e-12"),
    )

    if remaining_base > tolerance:
        return None

    # Assumes fee is deducted from received quote currency.
    return quote_received * FEE_FACTOR


# --------------------------------------------------
# Rejected route result
# No fabricated final balance for incomplete routes
# --------------------------------------------------

def report_rejection(name, reason):
    print(f"\n{name}")
    print(f"  Status            : REJECTED - {reason}")

    return {
        "route": name,
        "final_usdt": None,
        "net_profit": None,
        "net_pct": None,
        "eligible": False,
        "reason": reason,
    }


# --------------------------------------------------
# Simulate one triangular arbitrage route
# --------------------------------------------------

def evaluate_route(name, route, books):
    btcusdt = books["BTCUSDT"]
    ethbtc = books["ETHBTC"]
    ethusdt = books["ETHUSDT"]

    start_usdt = STARTING_USDT

    if route == "A":
        # USDT -> BTC -> ETH -> USDT

        btc = buy_base_with_quote(
            start_usdt,
            btcusdt["asks"],
        )

        if btc is None:
            return report_rejection(
                name,
                "Insufficient BTCUSDT ask depth",
            )

        eth = buy_base_with_quote(
            btc,
            ethbtc["asks"],
        )

        if eth is None:
            return report_rejection(
                name,
                "Insufficient ETHBTC ask depth",
            )

        final_usdt = sell_base_for_quote(
            eth,
            ethusdt["bids"],
        )

        if final_usdt is None:
            return report_rejection(
                name,
                "Insufficient ETHUSDT bid depth",
            )

    elif route == "B":
        # USDT -> ETH -> BTC -> USDT

        eth = buy_base_with_quote(
            start_usdt,
            ethusdt["asks"],
        )

        if eth is None:
            return report_rejection(
                name,
                "Insufficient ETHUSDT ask depth",
            )

        btc = sell_base_for_quote(
            eth,
            ethbtc["bids"],
        )

        if btc is None:
            return report_rejection(
                name,
                "Insufficient ETHBTC bid depth",
            )

        final_usdt = sell_base_for_quote(
            btc,
            btcusdt["bids"],
        )

        if final_usdt is None:
            return report_rejection(
                name,
                "Insufficient BTCUSDT bid depth",
            )

    else:
        raise ValueError(f"Unknown route: {route}")

    # Calculate simulated return after assumed fees.
    profit = final_usdt - start_usdt
    net_pct = profit / start_usdt * HUNDRED

    # Diagnostic estimate only; not an independently
    # calculated executable gross return.
    gross_final = final_usdt / (FEE_FACTOR ** 3)
    gross_pct = (
        (gross_final / start_usdt) - ONE
    ) * HUNDRED

    eligible = net_pct > SAFETY_MARGIN_PCT

    status = (
        "CANDIDATE - PAPER OBSERVATION ONLY"
        if eligible
        else "REJECTED - EDGE TOO LOW"
    )

    print(f"\n{name}")
    print(f"  Start balance      : {start_usdt:.6f} USDT")
    print(f"  Final balance      : {final_usdt:.8f} USDT")
    print(f"  Gross return*      : {gross_pct:+.5f}%")
    print(f"  Net profit         : {profit:+.8f} USDT")
    print(f"  Net return         : {net_pct:+.5f}%")
    print(f"  Required return    : > {SAFETY_MARGIN_PCT:.4f}%")
    print(f"  Status             : {status}")

    return {
        "route": name,
        "final_usdt": final_usdt,
        "net_profit": profit,
        "net_pct": net_pct,
        "eligible": eligible,
        "reason": (
            ""
            if eligible
            else "EDGE_TOO_LOW"
        ),
    }


# --------------------------------------------------
# Main scanning loop
# --------------------------------------------------

def main():
    print("=" * 65)
    print("TRIANGULAR ARBITRAGE SCANNER V4")
    print("Public Binance depth data | Paper observation mode")
    print("Real orders: DISABLED")
    print(f"Starting amount: {STARTING_USDT} USDT")
    print(f"Assumed fee per leg: {FEE_RATE * HUNDRED}%")
    print(f"Minimum net return: > {SAFETY_MARGIN_PCT}%")
    print(f"Polling interval: {POLL_INTERVAL_SECONDS} seconds")
    print("=" * 65)

    ledger = PaperLedger()

    with requests.Session() as session:
        while True:
            try:
                # These are separate snapshots, not an atomic
                # snapshot of all three trading pairs.
                books = {
                    symbol: fetch_depth(session, symbol)
                    for symbol in SYMBOLS
                }

                print("\n" + "=" * 65)
                print(
                    datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds")
                )

                for symbol, book in books.items():
                    print(
                        f"{symbol}: "
                        f"updateId={book['last_update_id']}, "
                        f"bids={len(book['bids'])}, "
                        f"asks={len(book['asks'])}"
                    )

                results = [
                    evaluate_route(
                        "Route A: USDT -> BTC -> ETH -> USDT",
                        "A",
                        books,
                    ),
                    evaluate_route(
                        "Route B: USDT -> ETH -> BTC -> USDT",
                        "B",
                        books,
                    ),
                ]

                candidates = 0

                for result in results:
                    route_name = result["route"]

                    if result["final_usdt"] is None:
                        # An incomplete route has no valid
                        # final balance or meaningful P&L.
                        print(
                            f"  Ledger observation skipped for "
                            f"{route_name}: route incomplete."
                        )
                        continue

                    if result["eligible"]:
                        candidates += 1
                        status = "CANDIDATE"
                        reason = (
                            "Passed configured net-return threshold; "
                            "not executed"
                        )
                    else:
                        status = "REJECTED"
                        reason = "EDGE_TOO_LOW"

                    # Observation only: do not change the wallet.
                    ledger.record_observation(
                        route=route_name,
                        ending_balance=result["final_usdt"],
                        status=status,
                        reason=reason,
                    )

                print(
                    f"\nPaper candidates this scan: {candidates}"
                )
                print("Paper trades executed this scan: 0")
                print("Ledger balance remains unchanged.")
                ledger.summary()

            except (
                requests.RequestException,
                ValueError,
                KeyError,
                ArithmeticError,
            ) as exc:
                print(f"\nScan failed: {exc}")

            except KeyboardInterrupt:
                print("\nScanner stopped by user.")
                break

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
