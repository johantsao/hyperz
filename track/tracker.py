from track.monitor import HyperliquidMonitor
from hyperliquid_monitor.types import Trade
from datetime import datetime, timezone
import telegram
import requests
import time
import threading
from collections import defaultdict

lock = threading.Lock()

processed_fills = {}
processed_tx_hashes = set()

START_TIME = datetime.now(timezone.utc)

# --- Telegram 設定 ---
BOT_TOKEN = "8271110094:AAF1WQtgUxB_SWg5MpYxHFOOBu5J9YYuYkw"
CHAT_ID = "-4843613367"
bot = telegram.Bot(token=BOT_TOKEN)

def get_stop_loss_price(wallet, direction):
    url = "https://api.hyperliquid.xyz/info"
    headers = {"Content-Type": "application/json"}
    payload = {
        "type": "frontendOpenOrders",
        "user": wallet
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code != 200:
            return "N/A"

        orders = res.json()
        for order in orders:
            if order.get("isTrigger", False) and order.get("orderType") == "Stop Market":
                trigger_px = int(float(order["triggerPx"]))
                trigger = order['triggerCondition']

                if direction == 'Open Long':
                    return trigger_px
                elif direction == 'Open Short':
                    return trigger_px

        return "N/A"

    except Exception as e:
        print(f"❗ 查詢止損價格失敗：{e}")
        return "N/A"
    
def get_take_profit_price(wallet, direction):
    url = "https://api.hyperliquid.xyz/info"
    headers = {"Content-Type": "application/json"}
    payload = {
        "type": "frontendOpenOrders",
        "user": wallet
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code != 200:
            return "N/A"

        orders = res.json()
        for order in orders:
            if order.get("isTrigger", False) and order.get("orderType") == "Take Profit Market":
                trigger_px = int(float(order["triggerPx"]))
                trigger = order['triggerCondition']

                if direction == 'Open Long':
                    return trigger_px
                elif direction == 'Open Short':
                    return trigger_px

        return "N/A"

    except Exception as e:
        print(f"❗ 查詢止盈價格失敗：{e}")
        return "N/A"

def get_portfolio_info(wallet_address):
    url = "https://api.hyperliquid.xyz/info"
    headers = {"Content-Type": "application/json"}
    payload_pnl = {
        "type": "portfolio",
        "user": wallet_address
    }
    payload_value = {
        "type": "clearinghouseState",
        "user": wallet_address
    }

    
    try:
        response_pnl = requests.post(url, headers=headers, json=payload_pnl, timeout=10)
        response_value = requests.post(url, headers=headers, json=payload_value, timeout=10)
        if response_pnl.status_code == 200 and response_value.status_code == 200:
            data_pnl = response_pnl.json()
            data_value = response_value.json()
            # 提取 allTime 資訊
            all_time = dict(data_pnl)["allTime"]
            all_value = dict(data_value)["marginSummary"]
            latest_value = float(all_value["accountValue"])
            latest_pnl = float(all_time["pnlHistory"][-1][1])
            return latest_value, latest_pnl
        else:
            print(f"⚠️ 查詢失敗：HTTP PNL:{response_pnl.status_code}, VALUE:{response_value.status_code}")
    except Exception as e:
        print(f"❗ 查詢 portfolio 出錯：{e}")
    
    return None, None  # 查詢失敗

from datetime import datetime, timedelta
import requests

def get_win_rate(wallet_address):
    url = "https://api.hyperliquid.xyz/info"
    headers = {"Content-Type": "application/json"}

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=30)
    start_time_ms = int(start_time.timestamp() * 1000)


    payload = {
        "type": "userFillsByTime",
        "user": wallet_address,
        "startTime": start_time_ms
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code != 200:
            print(f"❗ 勝率查詢失敗：{res.status_code} - {res.text}")
            return None, None

        fills = res.json()
        if not isinstance(fills, list):
            print(f"❗ 回傳格式錯誤：{fills}")
            return None, None

        total_closes = 0
        win_closes = 0

        for fill in fills:
            direction = fill.get("dir")
            pnl_str = fill.get("closedPnl")

            # 只算 Close Short / Close Long 的單
            if direction not in ["Close Short", "Close Long"]:
                continue

            if pnl_str is not None:
                pnl = float(pnl_str)
                total_closes += 1
                if pnl > 0:
                    win_closes += 1

        if total_closes == 0:
            return 0.0, 0

        win_rate = (win_closes / total_closes) * 100
        return round(win_rate, 2), total_closes

    except Exception as e:
        print(f"❗ 查詢失敗：{e}")
        return None, None

def get_nickname(address):
    if address == "0x8af700ba841f30e0a3fcb0ee4c4a9d223e1efa05":
        return "一眼屌"
    elif address == "0xcb92c5988b1d4f145a7b481690051f03ead23a13":
        return "ETH 100%勝率巨鯨"
    elif address == "0x916ea2a9f3ba1ddd006c52babd0216e2ac54ed32":
        return "內幕哥"
    elif address == "0x6e4d47dad1e97833f4ecb0ef56347ba8e6fd1c0e":
        return "穩"
    elif address == "0x1f250Df59A777d61Cb8bd043c12970F3AFE4F925":
        return "反指標"
    elif address == "0x8da6BEAA2f002A511809101b24d181a324aE82D6":
        return "James Wynn"
    elif address == "0xa6A753c230755A2872B4dee4F59914c6Cad3b5c4":
        return "小蝦米"
    else:
        return address  # 找不到就顯示地址

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"❗ 傳送失敗：{e}")

recent_fills = defaultdict(list)

def flush_fill(trade, get_portfolio_info, get_win_rate, get_nickname, send_telegram_message):
    key = trade.tx_hash
    current_time = time.time()
    trades = recent_fills.pop(key, [])
    if not trades:
        return
    
    with lock:
        if key in processed_tx_hashes:
            return  # 已處理過，跳過
        processed_tx_hashes.add(key)
        processed_fills[key] = current_time

    # 清除超過 N 秒的歷史紀錄
    for k in list(processed_fills.keys()):
        if current_time - processed_fills[k] > 600:  # 保留 10 分鐘
            del processed_fills[k]

    total_size = sum(t.size for t in trades)
    avg_price = sum(t.size * t.price for t in trades) / total_size
    direction = trades[0].direction
    coin = trades[0].coin
    address = trades[0].address
    timestamp = trades[0].timestamp.strftime('%Y-%m-%d %H:%M:%S')
    tx_hash = trades[0].tx_hash
    pnl = sum(t.closed_pnl or 0 for t in trades)
    stop_loss = get_stop_loss_price(address, trades[0].direction)
    take_profit = get_take_profit_price(address, trades[0].direction)

    # 以下為補足原 print_trade 的資料
    nickname = get_nickname(address)
    account_value, account_pnl = get_portfolio_info(address)
    win_rate, trade_count = get_win_rate(address)

    if direction == 'Open Long':
        direction = '多'
    elif direction == 'Open Short':
        direction = '空'
    elif direction == 'Close Short':
        direction = '空單平倉'
    elif direction == 'Close Long':
        direction = '多單平倉'

    message = (
        f"通知: {coin} {direction}\n"
        f"時間: {timestamp}\n"
        f"錢包: {nickname} {address}\n"
        f"\n倉位: {total_size * avg_price:,.2f} USDT\n"
        f"平均市價: {avg_price:,.2f} USDT\n"
        f"止損價格: {stop_loss} USDT\n"
        f"止盈價格: {take_profit} USDT\n"
        f"盈虧: {pnl:,.2f} USDT\n"
        f"\n\n💼 錢包餘額: {account_value:,.2f} USDT\n📊 累積盈虧: {account_pnl:,.2f} USDT\n🏆 30日勝率：{win_rate:.2f}%（共 {trade_count} 筆）\n"
        f"────────────\n"
        f'\n🔗 <a href="https://hypurrscan.io/tx/{tx_hash}">交易紀錄</a>'
        f'\n📈 <a href="https://hyperdash.info/trader/{address}">錢包分析與收益曲線</a>\n'
        f'\n內容僅供資訊參考，並不構成任何投資建議。'
    )

    send_telegram_message(message)

def print_trade_combined(trade, get_portfolio_info, get_win_rate, get_nickname, send_telegram_message):
    if trade.timestamp.tzinfo is None:
        trade_time = trade.timestamp.replace(tzinfo=timezone.utc)
    else:
        trade_time = trade.timestamp.astimezone(timezone.utc)

    if trade_time < START_TIME:
        print(f"[跳過] {trade_time.isoformat()} 是啟動前的單")
        return

    if trade.trade_type == "FILL":
        key = trade.tx_hash
        recent_fills[key].append(trade)
        threading.Timer(60, flush_fill, args=(trade, get_portfolio_info, get_win_rate, get_nickname, send_telegram_message)).start()
    else:
        print(f"[非 FILL] {trade.trade_type}: {trade.coin} {trade.side} {trade.size}@{trade.price}")

def print_trade(trade: Trade):
    if trade.timestamp.tzinfo is None:
        trade_time = trade.timestamp.replace(tzinfo=timezone.utc)
    else:
        trade_time = trade.timestamp.astimezone(timezone.utc)

    if trade_time < START_TIME:
        print(f"[跳過] {trade_time.isoformat()} 是啟動前的單")
        return

    timestamp = trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    nickname = get_nickname(trade.address)

    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

    color = GREEN if trade.side == "BUY" else RED
    print(f"\n{BLUE}[{timestamp}]{RESET} New {trade.trade_type}:")
    print(f"Address: {trade.address}")
    print(f"Coin: {trade.coin}")
    print(f"{color}Side: {trade.side}{RESET}")
    print(f"Size: {trade.size}")
    print(f"Price: {trade.price}")
    
    if trade.trade_type == "FILL":
        print(f"Direction: {trade.direction}")
        if trade.closed_pnl is not None:
            pnl_color = GREEN if trade.closed_pnl > 0 else RED
            print(f"PnL: {pnl_color}{trade.closed_pnl:.2f}{RESET}")
        print(f"Hash: {trade.tx_hash}")

def main():
    addresses = [
        "0x8af700ba841f30e0a3fcb0ee4c4a9d223e1efa05",
        "0xcb92c5988b1d4f145a7b481690051f03ead23a13",
        "0x916ea2a9f3ba1ddd006c52babd0216e2ac54ed32",
        "0x6e4d47dad1e97833f4ecb0ef56347ba8e6fd1c0e",
        "0x1f250Df59A777d61Cb8bd043c12970F3AFE4F925",
        "0x8da6BEAA2f002A511809101b24d181a324aE82D6",
        "0xa6A753c230755A2872B4dee4F59914c6Cad3b5c4"
    ]

    print(START_TIME)

    while True:
        try:
            try:
                monitor.stop()
            except:
                pass

            monitor = HyperliquidMonitor(
                addresses=addresses,
                db_path="trades.db",
                callback=lambda trade: print_trade_combined(
                    trade,
                    get_portfolio_info,
                    get_win_rate,
                    get_nickname,
                    send_telegram_message
                )
            )
            print("📡 Monitoring started... Press Ctrl+C to stop.")
            print(f"追蹤錢包數量: {len(addresses)}")
            print(f"錢包列表: {addresses}")
            monitor.start()
        except KeyboardInterrupt:
            monitor.stop()
            print("👋 Monitor stopped.")
            break
        except Exception as e:
            print(f"❗ 監控異常中斷：{e}")
            try:
                monitor.stop()
            except:
                pass
            print("⏳ 5 秒後自動重啟監控...")
            time.sleep(5)



if __name__ == "__main__":
    main()
