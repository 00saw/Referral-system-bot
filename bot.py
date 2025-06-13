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
    username TEXT,
    invited_by BIGINT,
    referrals INT DEFAULT 0,
    verified BOOLEAN DEFAULT FALSE,
    captcha_passed BOOLEAN DEFAULT FALSE
);
""")
conn.commit()

captchas = {}

def generate_captcha():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    return f"{a} + {b}", str(a + b)

def add_user(user_id, username, invited_by=None):
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users (user_id, username, invited_by) VALUES (%s, %s, %s)", (user_id, username, invited_by))
        if invited_by:
            cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = %s", (invited_by,))
        conn.commit()

def get_referral_count(uid):
    cur.execute("SELECT referrals FROM users WHERE user_id = %s", (uid,))
    result = cur.fetchone()
    return result[0] if result else 0

def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        return status in ["member", "administrator", "creator"]
    except:
        return False

@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.from_user.id
    username = message.from_user.username
    args = message.text.split()
    inviter = int(args[1]) if len(args) > 1 and args[1].isdigit() and int(args[1]) != uid else None

    cur.execute("SELECT captcha_passed FROM users WHERE user_id = %s", (uid,))
    row = cur.fetchone()
    if not row:
        add_user(uid, username, inviter)
        cur.execute("SELECT captcha_passed FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()

    if row and not row[0]:
        q, a = generate_captcha()
        captchas[uid] = a
        markup = InlineKeyboardMarkup()
        btns = [a, str(int(a) + random.randint(1, 3))]
        random.shuffle(btns)
        for b in btns:
            markup.add(InlineKeyboardButton(b, callback_data=f"captcha_{b}"))
        bot.send_message(uid, f"👮‍♂️ قبل المتابعة، جاوب على السؤال:\n\n❓ {q}", reply_markup=markup)
    else:
        send_welcome(uid)

def send_welcome(uid):
    if not is_subscribed(uid):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"))
        bot.send_message(uid, "🚫 يجب عليك الاشتراك في القناة للاستمرار.", reply_markup=markup)
        return
    username = bot.get_me().username
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 رابط الإحالة", url=f"https://t.me/{username}?start={uid}"))
    bot.send_message(uid, "🎉 أهلاً بك في نظام الإحالة!\n✅ ادعُ أصدقاءك واربح جوائز.\n📌 استخدم /help لمعرفة كل الأوامر.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("captcha_"))
def handle_captcha(call):
    uid = call.from_user.id
    value = call.data.replace("captcha_", "")
    if value == captchas.get(uid):
        cur.execute("UPDATE users SET captcha_passed = TRUE WHERE user_id = %s", (uid,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تحقق ناجح")
        send_welcome(uid)
    else:
        bot.answer_callback_query(call.id, "❌ خطأ! حاول مجددًا")

@bot.message_handler(commands=['help'])
def help_msg(message):
    bot.reply_to(message, """👋 طريقة الاستخدام:

/link — رابط الإحالة الخاص بك  
/stats — عدد الأشخاص الذين دعوتهم  
/top — المتصدرين  
/rewards — الجوائز المتاحة  
""")

@bot.message_handler(commands=['link'])
def referral_link(message):
    uid = message.from_user.id
    bot.reply_to(message, f"🔗 رابطك:\nhttps://t.me/{bot.get_me().username}?start={uid}")

@bot.message_handler(commands=['stats'])
def stats(message):
    uid = message.from_user.id
    count = get_referral_count(uid)
    bot.reply_to(message, f"📊 عدد الإحالات: {count}")

@bot.message_handler(commands=['top'])
def top_users(message):
    cur.execute("SELECT user_id, referrals FROM users ORDER BY referrals DESC LIMIT 10")
    rows = cur.fetchall()
    msg = "🏆 المتصدرون:\n\n"
    for i, row in enumerate(rows):
        uid, count = row
        cur.execute("SELECT username FROM users WHERE user_id = %s", (uid,))
        uname = cur.fetchone()[0]
        name = f"@{uname}" if uname else f"ID: {uid}"
        msg += f"{i+1}. {name} — {count}\n"
    bot.reply_to(message, msg)

@bot.message_handler(commands=['rewards'])
def show_rewards(message):
    bot.reply_to(message, "🎁 الجوائز:\n\n10 إحالات = 1$\n50 إحالة = 10$\n100 إحالة = هدية كبرى")

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
    bot.reply_to(message, "📝 أرسل الآن الرسالة التي تريد إرسالها للجميع.")

    @bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID)
    def confirm_broadcast(msg):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ تأكيد", callback_data="confirm_broadcast"))
        markup.add(InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast"))
        bot.send_message(OWNER_ID, f"🔔 هذه الرسالة:\n\n{msg.text}", reply_markup=markup)

        @bot.callback_query_handler(func=lambda call: call.data in ["confirm_broadcast", "cancel_broadcast"])
        def handle_broadcast_confirm(call):
            if call.data == "cancel_broadcast":
                bot.send_message(OWNER_ID, "🚫 تم الإلغاء.")
            else:
                cur.execute("SELECT user_id FROM users")
                users = cur.fetchall()
                for u in users:
                    try:
                        bot.send_message(u[0], msg.text)
                    except:
                        pass
                bot.send_message(OWNER_ID, "📢 تم الإرسال.")

def run_bot():
    bot.infinity_polling()

def run_web():
    @app.route('/')
    def index():
        return "Bot running"
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))

threading.Thread(target=run_bot).start()
threading.Thread(target=run_web).start()