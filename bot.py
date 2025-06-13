import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import psycopg2
from flask import Flask
import threading
import random

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
    verified BOOLEAN DEFAULT FALSE,
    captcha_passed BOOLEAN DEFAULT FALSE
);
""")
conn.commit()

# --------- CAPTCHA ----------
captchas = {}

def generate_captcha():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    return f"{a} + {b}", str(a + b)

def add_user(user_id, invited_by=None):
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (user_id, invited_by) VALUES (%s, %s)", (user_id, invited_by))
        if invited_by:
            cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = %s", (invited_by,))
        conn.commit()

def get_referral_count(uid):
    cur.execute("SELECT referrals FROM users WHERE user_id = %s", (uid,))
    result = cur.fetchone()
    return result[0] if result else 0

@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    args = message.text.split()
    inviter = int(args[1]) if len(args) > 1 and args[1].isdigit() and int(args[1]) != uid else None

    cur.execute("SELECT captcha_passed FROM users WHERE user_id = %s", (uid,))
    row = cur.fetchone()
    if not row:
        add_user(uid, inviter)
        cur.execute("SELECT captcha_passed FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()

    if row and not row[0]:
        q, a = generate_captcha()
        captchas[uid] = a
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"{a}", callback_data=f"captcha_{a}"))
        markup.add(InlineKeyboardButton(str(int(a) + random.randint(1, 3)), callback_data="captcha_wrong"))
        bot.send_message(uid, f"👮‍♂️ قبل المتابعة، جاوب على السؤال التالي للتحقق:\n\n❓ {q}", reply_markup=markup)
    else:
        send_welcome(uid)

def send_welcome(uid):
    username = bot.get_me().username
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 رابط إحالتك", url=f"https://t.me/{username}?start={uid}"))
    bot.send_message(uid, "🎉 أهلاً بك في نظام الإحالة!\n✅ قم بدعوة أصدقائك واربح جوائز حقيقية.\n📌 استخدم الأمر /help للتعليمات.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("captcha_"))
def handle_captcha(call):
    uid = call.from_user.id
    if call.data == f"captcha_{captchas.get(uid)}":
        cur.execute("UPDATE users SET captcha_passed = TRUE WHERE user_id = %s", (uid,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تحقق ناجح")
        send_welcome(uid)
    else:
        bot.answer_callback_query(call.id, "❌ خطأ! حاول مجددًا")

@bot.message_handler(commands=['help'])
def help_msg(message):
    bot.reply_to(message, """👋 كيف يعمل البوت؟

1. احصل على رابط الإحالة عبر /link
2. ادعُ أصدقاءك وسجل إحالاتك
3. تابع تقدمك عبر /stats
4. شاهد الجوائز عبر /rewards
5. ترتيب المتصدرين عبر /top
""")

@bot.message_handler(commands=['link'])
def referral_link(message):
    uid = message.from_user.id
    bot.reply_to(message, f"🔗 رابط الإحالة الخاص بك:\nhttps://t.me/{bot.get_me().username}?start={uid}")

@bot.message_handler(commands=['stats'])
def stats(message):
    uid = message.from_user.id
    count = get_referral_count(uid)
    bot.reply_to(message, f"📊 لقد دعوت {count} أصدقاء.")

@bot.message_handler(commands=['top'])
def top_users(message):
    cur.execute("SELECT user_id, referrals FROM users ORDER BY referrals DESC LIMIT 10")
    rows = cur.fetchall()
    msg = "🏆 أعلى 10 مستخدمين:\n\n"
    for i, row in enumerate(rows):
        msg += f"{i+1}. {row[0]} — {row[1]} إحالة\n"
    bot.reply_to(message, msg)

@bot.message_handler(commands=['rewards'])
def show_rewards(message):
    bot.reply_to(message, "🎁 الجوائز الحالية:\n\n10 إحالات = 1 دولار\n50 إحالة = 10 دولار\n100 إحالة = هدية كبرى")

@bot.message_handler(commands=['users_count'])
def users_count(message):
    if message.from_user.id == OWNER_ID:
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        bot.reply_to(message, f"👥 عدد المستخدمين: {count}")

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != OWNER_ID:
        return
    msg = message.text.replace('/broadcast', '').strip()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    for user in users:
        try:
            bot.send_message(user[0], msg)
        except:
            pass
    bot.reply_to(message, "📢 تم إرسال الرسالة للجميع.")

def run_bot():
    bot.infinity_polling()

def run_web():
    @app.route('/')
    def index():
        return "🤖 Bot is running!"
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))

threading.Thread(target=run_bot).start()
threading.Thread(target=run_web).start()