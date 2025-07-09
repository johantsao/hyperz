# track/bot.py
# Hyperliquid Telegram 互動式監控跟單系統 - NodeZ 品牌風格完整改版 + 開機 Banner + 品牌互動設計

import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)
from track import db
from telegram.constants import ChatMemberStatus

# --- 基本設定 ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7757791406:AAG8Wc0Xe_mXnJaLcZdym9v8rUkdwP1oV0A"
ADMIN_IDS = ["1804238905", "1774286477"]

# 狀態常數
ADD_ADDRESS, SET_RATIO_ADDRESS, SET_RATIO_RATIO, VERIFY_INPUT = range(4)

# --- 鍵盤設計 ---
def get_main_keyboard():
    keyboard = [
        ["📊 查看地址績效", "✅ 進行身份驗證"],
        ["❌ 取消操作"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard():
    keyboard = [
        ["➕ 新增監控地址", "⚙️ 調整地址比例"],
        ["📊 查看地址績效", "✅ 進行身份驗證"],
        ["❌ 取消操作"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def is_admin(user_id: str) -> bool:
    return user_id in ADMIN_IDS

# --- /start ---
def start_handler():
    async def inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        db.add_user(str(user.id), user.username or "")
        logo = "🚀 <b>Hyper Z Bot</b>\n🪐 On-Chain Alpha Monitoring & Copy Trading\n────────────"
        tutorial = (
            "\n<b>📋 功能選單：</b>\n"
            "• 📊 查看地址績效\n"
            "• ✅ 身份驗證 (OKX UID / Contributor)\n"
            "• 🪐 即時跟單推播 (自動)\n"
            "• ➕ 新增監控地址（管理員）\n"
            "• ⚙️ 調整地址比例（管理員）\n"
            "\n請從下方鍵盤選擇開始使用 👇"
        )
        if is_admin(str(user.id)):
            kb = get_admin_keyboard()
            msg = f"{logo}\n👋 歡迎管理員，已登入成功，可編輯監控地址。\n{tutorial}"
        else:
            kb = get_main_keyboard()
            msg = f"{logo}\n👋 歡迎 {user.first_name}，已註冊成功！\n{tutorial}"
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="HTML")
    return inner

# --- ➕ 新增監控地址（僅限管理員） ---
async def add_address_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(str(update.effective_user.id)):
        await update.message.reply_text("⚠️ <b>權限不足</b>\n此功能僅限管理員使用。", parse_mode="HTML", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    await update.message.reply_text("✏️ <b>請輸入要新增的監控地址</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    return ADD_ADDRESS

async def save_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(str(update.effective_user.id)):
        await update.message.reply_text("⚠️ <b>權限不足</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    address = update.message.text.strip()
    db.add_system_address(address)
    await update.message.reply_text(f"✅ <b>已新增全系統監控地址：</b>{address}", parse_mode="HTML", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# --- ⚙️ 調整地址比例（僅限管理員） ---
async def set_ratio_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(str(update.effective_user.id)):
        await update.message.reply_text("⚠️ <b>權限不足</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    addresses = db.get_all_monitored_addresses()
    if not addresses:
        await update.message.reply_text("⚠️ <b>尚未有監控地址，請先新增。</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
        return ConversationHandler.END
    addr_list = "\n".join([f"- {addr['address']}" for addr in addresses])
    await update.message.reply_text(f"✏️ <b>請輸入要調整比例的地址（複製貼上）：</b>\n{addr_list}", parse_mode="HTML", reply_markup=get_admin_keyboard())
    return SET_RATIO_ADDRESS

async def set_ratio_receive_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['selected_address'] = update.message.text.strip()
    await update.message.reply_text("✏️ <b>請輸入新的比例（0.1 ~ 1.0）：</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    return SET_RATIO_RATIO

async def set_ratio_receive_ratio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(str(update.effective_user.id)):
        await update.message.reply_text("⚠️ <b>權限不足</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    try:
        ratio = float(update.message.text.strip())
        if not (0.1 <= ratio <= 1.0):
            await update.message.reply_text("⚠️ <b>請輸入 0.1 ~ 1.0。</b>", parse_mode="HTML")
            return SET_RATIO_RATIO
        address = context.user_data.get('selected_address')
        db.update_system_monitor_ratio(address, ratio)
        await update.message.reply_text(f"✅ <b>{address} 比例已更新為 {ratio}</b>", parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ <b>錯誤：</b>{e}", parse_mode="HTML", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# --- ✅ 進行身份驗證（所有人可用） ---
async def verify_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✏️ <b>請輸入您的 OKX UID 或 Contributor 名稱：</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    return VERIFY_INPUT

async def save_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.message.text.strip()
    user_id = str(update.effective_user.id)
    if data.isdigit():
        db.verify_user(user_id, okx_uid=data)
        await update.message.reply_text(f"✅ <b>已驗證 OKX UID：</b>{data}", parse_mode="HTML", reply_markup=get_main_keyboard())
    else:
        db.verify_user(user_id, contributor_name=data)
        await update.message.reply_text(f"✅ <b>已驗證 Contributor 名稱：</b>{data}", parse_mode="HTML", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- 📊 查看全系統監控地址績效（所有人可用） ---
async def performance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    addresses = db.get_all_monitored_addresses()
    if not addresses:
        await update.message.reply_text("⚠️ <b>尚無正在監控的地址。</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
        return
    message = "📊 <b>正在監控的地址績效：</b>\n"
    for addr in addresses:
        pnl, win_rate = db.get_address_performance(addr['address'])
        message += (
            f"\n📍 <b>地址：</b>{addr['address']}\n"
            f"⚖️ <b>比例：</b>{addr['monitor_ratio']}\n"
            f"💰 <b>30日PNL：</b>{pnl} USDT\n"
            f"🏆 <b>勝率：</b>{win_rate}%\n"
        )
    await update.message.reply_text(message, parse_mode="HTML", reply_markup=get_main_keyboard())

# --- ❌ 取消操作 ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ <b>已取消操作。</b>", parse_mode="HTML", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- 主程式啟動 ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_add_address = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ 新增監控地址$"), add_address_start)],
        states={ADD_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_address)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ 取消操作$"), cancel)]
    )

    conv_set_ratio = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚙️ 調整地址比例$"), set_ratio_start)],
        states={
            SET_RATIO_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ratio_receive_address)],
            SET_RATIO_RATIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ratio_receive_ratio)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ 取消操作$"), cancel)]
    )

    conv_verify = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✅ 進行身份驗證$"), verify_start)],
        states={VERIFY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_verification)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ 取消操作$"), cancel)]
    )

    app.add_handler(CommandHandler("start", start_handler()))
    app.add_handler(conv_add_address)
    app.add_handler(conv_set_ratio)
    app.add_handler(conv_verify)
    app.add_handler(MessageHandler(filters.Regex("^📊 查看地址績效$"), performance_handler))
    app.add_handler(MessageHandler(filters.Regex("^❌ 取消操作$"), cancel))

    print("🤖 Hyper Z Telegram Bot 已啟動，準備好迎接 NodeZ Alpha Community！")
    app.run_polling()

if __name__ == "__main__":
    main()