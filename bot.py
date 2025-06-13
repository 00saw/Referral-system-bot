import telebot from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton import os import psycopg2 from flask import Flask import threading import random

API_TOKEN = os.getenv("API_TOKEN") CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME") OWNER_ID = int(os.getenv("OWNER_ID")) DATABASE_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(API_TOKEN) app = Flask(name)

conn = psycopg2.connect(DATABASE_URL, sslmode='require') cur = conn.cursor()

cur.execute(""" CREATE TABLE IF NOT EXISTS users ( user_id BIGINT PRIMARY KEY, invited_by BIGINT, referrals INT DEFAULT 0, verified BOOLEAN DEFAULT FALSE ); """) conn.commit()

captcha_store = {}

def add_user(user_id, invited_by=None): cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,)) if cur.fetchone() is None: cur.execute("INSERT INTO users (user_id, invited_by) VALUES (%s, %s)", (user_id, invited_by)) if invited_by: cur.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = %s", (invited_by,)) conn.commit()

def is_verified(user_id): cur.execute("SELECT verified FROM users WHERE user_id = %s", (user_id,)) row = cur.fetchone() return row and row[0]

def mark_verified(user_id): cur.execute("UPDATE users SET verified = TRUE WHERE user_id = %s", (user_id,)) conn.commit()

@bot.message_handler(commands=['start']) def start(message): uid = message.from_user.id if is_verified(uid): bot.send_message(uid, "✅ لقد تم التحقق منك مسبقًا.") return

args = message.text.split()
inviter = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
add_user(uid, inviter)

a, b = random.randint(1, 10), random.randint(1, 10)
captcha_store[uid] = a + b
bot.send_message(uid, f"🚫 لحمايتنا من السبام، أجب:

كم حاصل {a} + {b}؟")

@bot.message_handler(func=lambda msg: msg.from_user.id in captcha_store) def handle_captcha(message): uid = message.from_user.id try: if int(message.text.strip()) == captcha_store[uid]: mark_verified(uid) del captcha_store[uid] bot.send_message(uid, "✅ تم التحقق بنجاح! مرحباً بك 👋") else: bot.send_message(uid, "❌ إجابة خاطئة. حاول مرة أخرى.") except: bot.send_message(uid, "❌ يرجى كتابة رقم فقط.")

@bot.message_handler(commands=['link']) def referral_link(message): uid = message.from_user.id if not is_verified(uid): bot.reply_to(message, "❗ تحقق أولاً من الكابتشا.") return bot.reply_to(message, f"🔗 رابط إحالتك: t.me/{bot.get_me().username}?start={uid}")

@bot.message_handler(commands=['stats']) def stats(message): uid = message.from_user.id if not is_verified(uid): bot.reply_to(message, "❗ تحقق أولاً من الكابتشا.") return cur.execute("SELECT referrals FROM users WHERE user_id = %s", (uid,)) row = cur.fetchone() referrals = row[0] if row else 0 bot.reply_to(message, f"📊 لقد دعوت {referrals} مستخدم(ين).")

@bot.message_handler(commands=['top']) def top_invites(message): cur.execute("SELECT user_id, referrals FROM users ORDER BY referrals DESC LIMIT 10") top = cur.fetchall() msg = "🏆 أفضل 10 مستخدمين: " for i, (uid, count) in enumerate(top, 1): msg += f"{i}. {uid} - {count} إحالة\n" bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['admin']) def admin_panel(message): if message.from_user.id != OWNER_ID: return cur.execute("SELECT COUNT(*) FROM users") total_users = cur.fetchone()[0] cur.execute("SELECT user_id, referrals FROM users ORDER BY referrals DESC LIMIT 1") top_user = cur.fetchone() msg = f"👑 لوحة الإدارة: المستخدمين: {total_users} أعلى محيل: {top_user[0]} بـ {top_user[1]} إحالة" bot.send_message(message.chat.id, msg)

def run_bot(): bot.infinity_polling()

def run_web(): @app.route('/') def index(): return "Bot is running!"

app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))

threading.Thread(target=run_bot).start() threading.Thread(target=run_web).start()

