import signal
import sys
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from hyperliquid.info import Info
from hyperliquid.utils import constants

from hyperliquid_monitor.database import TradeDatabase
from hyperliquid_monitor.types import Trade, TradeCallback


class HyperliquidMonitor:
    def __init__(
        self,
        addresses: List[str],
        db_path: Optional[str] = None,
        callback: Optional[TradeCallback] = None,
        silent: bool = False,
    ):
        self.info = Info(constants.MAINNET_API_URL)
        self.addresses = addresses
        self.callback = callback if not silent else None
        self.silent = silent
        self.db = TradeDatabase(db_path) if db_path else None
        self._stop_event = threading.Event()
        self._db_lock = threading.Lock() if db_path else None
        self.subscriptions = []  # unsubscribe callback handles

        if silent and not db_path:
            raise ValueError("Silent mode requires a database path to be specified")

    def handle_shutdown(self, signum=None, frame=None):
        if self._stop_event.is_set():
            sys.exit(0)

        print("\nShutting down gracefully...")
        self.stop()
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        sys.exit(0)

    def cleanup(self):
        if self.db:
            with self._db_lock:
                self.db.close()
            if not self.silent:
                print("Database connection closed.")

    def create_event_handler(self, address: str):
        def handle_event(event: Dict[str, Any]) -> None:
            if self._stop_event.is_set():
                return

            if not isinstance(event, dict):
                return

            data = event.get("data", {})

            if "fills" in data:
                for fill in data["fills"]:
                    if not isinstance(fill, dict):
                        continue
                    try:
                        trade = self._process_fill(fill, address)
                        if self.db:
                            with self._db_lock:
                                self.db.store_fill(fill)
                        if self.callback and not self.silent:
                            self.callback(trade)
                    except Exception as e:
                        if not self.silent:
                            print(f"Error processing fill: {e}")

            if "orderUpdates" in data:
                for update in data["orderUpdates"]:
                    if not isinstance(update, dict):
                        continue
                    try:
                        trades = self._process_order_update(update, address)
                        if self.db:
                            with self._db_lock:
                                if "placed" in update:
                                    self.db.store_order(update, "placed")
                                elif "canceled" in update:
                                    self.db.store_order(update, "canceled")
                        if self.callback and not self.silent:
                            for trade in trades:
                                self.callback(trade)
                    except Exception as e:
                        if not self.silent:
                            print(f"Error processing order update: {e}")

        return handle_event

    def _process_fill(self, fill: Dict, address: str) -> Trade:
        timestamp = datetime.fromtimestamp(int(fill.get("time", 0)) / 1000)
        return Trade(
            timestamp=timestamp,
            address=address,
            coin=fill.get("coin", "Unknown"),
            side="BUY" if fill.get("side", "B") == "A" else "SELL",
            size=float(fill.get("sz", 0)),
            price=float(fill.get("px", 0)),
            trade_type="FILL",
            direction=fill.get("dir"),
            tx_hash=fill.get("hash"),
            fee=float(fill.get("fee", 0)),
            fee_token=fill.get("feeToken"),
            start_position=float(fill.get("startPosition", 0)),
            closed_pnl=float(fill.get("closedPnl", 0))
        )

    def _process_order_update(self, update: Dict, address: str) -> List[Trade]:
        from datetime import timezone
        timestamp = datetime.fromtimestamp(int(update.get("time", 0)) / 1000, tz=timezone.utc)
        trades = []
        if "placed" in update:
            order = update["placed"]
            trades.append(Trade(
                timestamp=timestamp,
                address=address,
                coin=update.get("coin", "Unknown"),
                side="BUY" if order.get("side", "B") == "A" else "SELL",
                size=float(order.get("sz", 0)),
                price=float(order.get("px", 0)),
                trade_type="ORDER_PLACED",
                order_id=int(order.get("oid", 0))
            ))
        elif "canceled" in update:
            order = update["canceled"]
            trades.append(Trade(
                timestamp=timestamp,
                address=address,
                coin=update.get("coin", "Unknown"),
                side="BUY" if order.get("side", "B") == "A" else "SELL",
                size=float(order.get("sz", 0)),
                price=float(order.get("px", 0)),
                trade_type="ORDER_CANCELLED",
                order_id=int(order.get("oid", 0))
            ))
        return trades

    def start(self) -> None:
        if not self.addresses:
            raise ValueError("No addresses configured to monitor")

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        for address in self.addresses:
            handler = self.create_event_handler(address)
            try:
                unsub1 = self.info.subscribe({"type": "userEvents", "user": address}, handler)
                self.subscriptions.append(unsub1)
            except Exception as e:
                print(f"[錯誤] 訂閱 userEvents 失敗：{e}")
            try:
                unsub2 = self.info.subscribe({"type": "userFills", "user": address}, handler)
                self.subscriptions.append(unsub2)
            except Exception as e:
                print(f"[錯誤] 訂閱 userFills 失敗：{e}")

        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(1)
        except KeyboardInterrupt:
            self.handle_shutdown()

    def stop(self):
        self._stop_event.set()
        for unsub in self.subscriptions:
            try:
                unsub()
            except Exception as e:
                print(f"[錯誤] unsubscribe 失敗：{e}")
        self.subscriptions.clear()
        self.cleanup()
