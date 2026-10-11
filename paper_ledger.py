import csv
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

STARTING_BALANCE = Decimal("100")

TRADES_FILE = "paper_trades.csv"
OBSERVATIONS_FILE = "paper_observations.csv"

ZERO = Decimal("0")
HUNDRED = Decimal("100")


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize_csv(filename, headers):
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        with open(filename, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headers)


class PaperLedger:
    """
    Observation writer plus a dormant paper-trade ledger.

    Recording an observation must never change paper-trading capital.
    Paper-trade persistence/recovery will be implemented separately
    before execute_paper_trade is enabled.
    """

    def __init__(self, starting_balance=STARTING_BALANCE):
        self.starting_balance = Decimal(str(starting_balance))
        self.balance = self.starting_balance
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        self.rejected_observations = 0

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
        self,
        route,
        starting_balance,
        ending_balance: Optional[Decimal],
        status,
        reason="",
    ):
        """
        Record one route observation.

        ending_balance=None means the route did not complete; in that
        case P&L and return are unknown and are written as empty CSV cells.
        The observation's P&L is always relative to its own starting balance,
        never the ledger's current paper balance.
        """
        starting = Decimal(str(starting_balance))
        if starting <= ZERO:
            raise ValueError("starting_balance must be greater than zero")

        if ending_balance is None:
            ending = None
            pnl = None
            return_pct = None
        else:
            ending = Decimal(str(ending_balance))
            pnl = ending - starting
            return_pct = pnl / starting * HUNDRED

        with open(OBSERVATIONS_FILE, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                now(),
                route,
                str(starting),
                "" if ending is None else str(ending),
                "" if pnl is None else str(pnl),
                "" if return_pct is None else str(return_pct),
                status,
                reason,
            ])

        if status != "CANDIDATE":
            self.rejected_observations += 1

        # Intentionally do not mutate self.balance or trade counters.

    def execute_paper_trade(self, route, ending_balance):
        """
        Record a simulated completed cycle.
        This never places an exchange order.

        Do not enable this method in the scanner until durable ledger
        recovery, deduplication, and execution modelling are implemented.
        """
        ending_balance = Decimal(str(ending_balance))
        starting = self.balance
        if starting <= ZERO:
            raise ValueError("Cannot execute a paper trade with non-positive balance")

        pnl = ending_balance - starting
        return_pct = pnl / starting * HUNDRED

        self.balance = ending_balance
        self.trade_count += 1

        if pnl > ZERO:
            self.wins += 1
        elif pnl < ZERO:
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
        print(f"Initial balance       : {self.starting_balance:.6f} USDT")
        print(f"Current balance       : {self.balance:.6f} USDT")
        print(
            f"Cumulative P&L        : "
            f"{self.balance - self.starting_balance:+.6f} USDT"
        )
        print(f"Completed trades      : {self.trade_count}")
        print(f"Winning trades        : {self.wins}")
        print(f"Losing trades         : {self.losses}")
        print(f"Rejected observations : {self.rejected_observations}")

        if self.trade_count:
            print(f"Win rate              : {self.wins / self.trade_count * 100:.2f}%")
        else:
            print("Win rate              : N/A (no completed trades)")
