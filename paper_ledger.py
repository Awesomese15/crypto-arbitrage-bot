
import csv
import os
from datetime import datetime, timezone
from decimal import Decimal

STARTING_BALANCE = Decimal("100")

TRADES_FILE = "paper_trades.csv"
OBSERVATIONS_FILE = "paper_observations.csv"


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize_csv(filename, headers):
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        with open(filename, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headers)


class PaperLedger:
    def __init__(self, starting_balance=STARTING_BALANCE):
        self.starting_balance = Decimal(starting_balance)
        self.balance = self.starting_balance
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        self.rejected = 0

        initialize_csv(
            TRADES_FILE,
            [
                "timestamp",
                "route",
                "starting_balance",
                "ending_balance",
                "profit_loss",
                "return_pct",
                "status",
            ],
        )

        initialize_csv(
            OBSERVATIONS_FILE,
            [
                "timestamp",
                "route",
                "starting_balance",
                "estimated_ending_balance",
                "estimated_profit_loss",
                "return_pct",
                "status",
                "reason",
            ],
        )

    def record_observation(
        self, route, ending_balance, status, reason=""
    ):
        ending_balance = Decimal(ending_balance)
        pnl = ending_balance - self.balance
        return_pct = pnl / self.balance * Decimal("100")

        with open(OBSERVATIONS_FILE, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                now(),
                route,
                str(self.balance),
                str(ending_balance),
                str(pnl),
                str(return_pct),
                status,
                reason,
            ])

        if status != "CANDIDATE":
            self.rejected += 1

    def execute_paper_trade(self, route, ending_balance):
        """
        Record a simulated completed cycle.
        This never places an exchange order.
        """
        ending_balance = Decimal(ending_balance)
        starting = self.balance
        pnl = ending_balance - starting
        return_pct = pnl / starting * Decimal("100")

        self.balance = ending_balance
        self.trade_count += 1

        if pnl > 0:
            self.wins += 1
        elif pnl < 0:
            self.losses += 1

        with open(TRADES_FILE, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                now(),
                route,
                str(starting),
                str(self.balance),
                str(pnl),
                str(return_pct),
                "PAPER_EXECUTED",
            ])

        print(
            f"\nPAPER TRADE: {route}"
            f"\n  Starting balance: {starting:.6f} USDT"
            f"\n  Ending balance:   {self.balance:.6f} USDT"
            f"\n  P&L:              {pnl:+.6f} USDT"
        )

    def summary(self):
        print("\n" + "=" * 45)
        print("PAPER LEDGER SUMMARY")
        print("=" * 45)
        print(f"Initial balance : {self.starting_balance:.6f} USDT")
        print(f"Current balance : {self.balance:.6f} USDT")
        print(
            f"Cumulative P&L  : "
            f"{self.balance - self.starting_balance:+.6f} USDT"
        )
        print(f"Completed trades: {self.trade_count}")
        print(f"Winning trades  : {self.wins}")
        print(f"Losing trades   : {self.losses}")
        print(f"Rejected scans  : {self.rejected}")

        if self.trade_count:
            print(
                f"Win rate        : "
                f"{self.wins / self.trade_count * 100:.2f}%"
            )
        else:
            print("Win rate        : N/A (no completed trades)")
