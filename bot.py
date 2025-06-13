import os
import random
import threading
import psycopg2
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
OWNER_ID = int(os.getenv("OWNER_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

conn = psycopg2.connect(DATABASE_URL, sslmode='require')
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    invited_by BIGINT,
    referrals INT DEFAULT 0,
    verified BOOLEAN DEFAULT FALSE
);
""")
conn.commit()

def add_user(user_id, invited_by=None):
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (user_id, invited_by) VALUES (%s, %s)", (user_id, invited_by))
        if invited_by:
            cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = %s AND verified = TRUE", (invited_by,))
        conn.commit()

def is_verified(user_id):
    cur.execute("SELECT verified FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    return row and row[0]

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    args = message.text.split()
    inviter = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    add_user(uid, inviter)

    # كابتشا بسيطة
    a, b = random.randint(1, 5), random.randint(1, 5)
    correct = a + b

    markup = InlineKeyboardMarkup()
    buttons = [correct, correct + 1, correct - 1]
    random.shuffle(buttons)
    for num in buttons:
        markup.add(InlineKeyboardButton(str(num), callback_data=f"verify_{num}_{correct}_{uid}"))

    bot.reply_to(message, f"🤖 للتأكد أنك لست روبوت: كم حاصل {a} + {b}؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def handle_captcha(call):
    _, chosen, correct, uid = call.data.split("_")
    chosen = int(chosen)
    correct = int(correct)
    uid = int(uid)

    if chosen == correct:
        cur.execute("UPDATE users SET verified = TRUE WHERE user_id = %s", (uid,))
        cur.execute("SELECT invited_by FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        if row and row[0]:
            cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = %s", (row[0],))
        conn.commit()
        bot.edit_message_text("✅ تم التحقق بنجاح! 🎉", call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text("❌ خطأ! حاول مرة أخرى بكتابة /start", call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['link'])
def referral_link(message):
    uid = message.from_user.id
    bot.reply_to(message, f"🔗 رابط إحالتك:\nhttps://t.me/{bot.get_me().username}?start={uid}")

@bot.message_handler(commands=['stats'])
def stats(message):
    uid = message.from_user.id
    cur.execute("SELECT referrals FROM users WHERE user_id = %s", (uid,))
    row = cur.fetchone()
    referrals = row[0] if row else 0
    bot.reply_to(message, f"📊 لقد قمت بدعوة {referrals} مستخدم(ين).")

@bot.message_handler(commands=['top'])
def top_referrers(message):
    cur.execute("SELECT user_id, referrals FROM users WHERE verified = TRUE ORDER BY referrals DESC LIMIT 10;")
    top = cur.fetchall()
    text = "🏆 أفضل المُحيلين:\n\n"
    for i, (user_id, count) in enumerate(top, 1):
        text += f"{i}. [{user_id}](tg://user?id={user_id}) — {count} إحالة\n"
    bot.reply_to(message, text, parse_mode='Markdown')

def run_bot():
    bot.infinity_polling()

def run_web():
    @app.route('/')
    def index():
        return "Bot is running!"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

threading.Thread(target=run_bot).start()
threading.Thread(target=run_web).start()