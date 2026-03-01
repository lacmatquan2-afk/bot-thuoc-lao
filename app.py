from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import logging

# ====== CẤU HÌNH ======
TOKEN = "BOT_TOKEN_CUA_BAN"
ADMIN_CHAT_ID = "ID_TELEGRAM_CUA_BAN"

IMAGE_1 = "https://i.postimg.cc/mkr16TKC/eed758ff-534e-4dad-878b-605d8b9ec503.jpg"
IMAGE_2 = "https://i.postimg.cc/Dz2vcB9m/85cd5e65-2888-4bc8-b4c9-55489412431d.jpg"

# ======================

logging.basicConfig(level=logging.INFO)

NAME, PHONE, ADDRESS = range(3)

# ====== BÀI ĐĂNG TỰ ĐỘNG ======
async def auto_post(context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 Đặt hàng ngay", callback_data="order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_media_group(
        chat_id=ADMIN_CHAT_ID,
        media=[
            InputMediaPhoto(IMAGE_1, caption=
            "🌿 THUỐC LÀO QUẢNG ĐỊNH CHÍNH GỐC\n\n"
            "🔥 Thơm đậm – Nặng đô – Không pha tạp\n"
            "🚚 Ship toàn quốc\n"
            "📞 0868862907")
            ,
            InputMediaPhoto(IMAGE_2)
        ]
    )

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text="👇 Bấm nút bên dưới để đặt hàng",
        reply_markup=reply_markup
    )

# ====== START ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 Đặt hàng", callback_data="order")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Chào anh em 👋\nThuốc lào Quảng Định chính gốc đây!",
        reply_markup=reply_markup
    )

# ====== XỬ LÝ NÚT ======
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order":
        await query.message.reply_text("Anh cho em xin TÊN người nhận:")
        return NAME

# ====== NHẬP TÊN ======
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Nhập SỐ ĐIỆN THOẠI:")
    return PHONE

# ====== NHẬP SĐT ======
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("Nhập ĐỊA CHỈ giao hàng:")
    return ADDRESS

# ====== NHẬP ĐỊA CHỈ ======
async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text

    order_text = f"""
🛒 CÓ ĐƠN MỚI!

👤 Tên: {context.user_data['name']}
📞 SĐT: {context.user_data['phone']}
🏠 Địa chỉ: {context.user_data['address']}
🕒 Thời gian: {datetime.now()}
"""

    # Gửi cho admin
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=order_text
    )

    # Lưu file
    with open("orders.txt", "a", encoding="utf-8") as f:
        f.write(order_text + "\n")

    await update.message.reply_text("✅ Đặt hàng thành công! Bên em sẽ gọi xác nhận ngay.")

    return ConversationHandler.END

# ====== MAIN ======
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_post, "interval", days=1, args=[app])
    scheduler.start()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
