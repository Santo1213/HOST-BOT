import os
import telebot
import subprocess
import sqlite3
import threading
import time
from telebot import types

# ================= CONFIG =================

TOKEN = "8756147215:AAFeeatxlgAcBMKg4qb4aGWmAvANRllKFfU"
OWNER_ID = 8015509191

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

BASE = "system"
BOT_DIR = f"{BASE}/bots"
LOG_DIR = f"{BASE}/logs"

os.makedirs(BOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ================= DB =================

conn = sqlite3.connect("host.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS bots")
cursor.execute("""
CREATE TABLE bots (
    name TEXT PRIMARY KEY,
    pid INTEGER
)
""")
conn.commit()

running = {}
waiting = set()
install_mode = {}

# ================= UI =================

def btn(t, d):
    return types.InlineKeyboardButton(f"🔘 {t}", callback_data=d)

def home():
    m = types.InlineKeyboardMarkup(row_width=1)
    m.add(
        btn("📤 Upload Bot", "upload"),
        btn("🤖 My Bots", "bots"),
        btn("📦 Install Package", "pkg")
    )
    return m

def back(to="home"):
    m = types.InlineKeyboardMarkup()
    m.add(btn("⬅ Back", to))
    return m

# ================= START =================

@bot.message_handler(commands=['start'])
def start(m):
    if m.from_user.id != OWNER_ID:
        return

    bot.send_message(
        m.chat.id,
        "💎 <b>TERMUX STYLE HOSTING BOT</b>\n\n"
        "✔ Run Python Bots\n"
        "✔ Install Packages like Termux\n"
        "✔ Animated Install System\n"
        "✔ Clean UI",
        reply_markup=home()
    )

# ================= CALLBACK =================

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    if c.from_user.id != OWNER_ID:
        return

    d = c.data

    # HOME
    if d == "home":
        bot.edit_message_text("🏠 HOME", c.message.chat.id, c.message.message_id, reply_markup=home())

    # UPLOAD
    elif d == "upload":
        waiting.add(c.message.chat.id)
        bot.send_message(c.message.chat.id, "📤 SEND YOUR .PY FILE")

    # PACKAGE MODE
    elif d == "pkg":
        install_mode[c.message.chat.id] = True

        bot.send_message(
            c.message.chat.id,
            "📦 <b>PACKAGE INSTALL MODE</b>\n\n"
            "Type like Termux:\n"
            "<code>pip install colorama</code>\n"
            "<code>pip install requests</code>"
        )

    # BOT LIST
    elif d == "bots":
        files = [f for f in os.listdir(BOT_DIR) if f.endswith(".py")]

        m = types.InlineKeyboardMarkup(row_width=1)

        if not files:
            m.add(btn("Back", "home"))
            return bot.edit_message_text("❌ No bots", c.message.chat.id, c.message.message_id, reply_markup=m)

        for f in files:
            name = f.replace(".py", "")
            m.add(btn(name, f"manage_{name}"))

        m.add(btn("Back", "home"))

        bot.edit_message_text("🤖 YOUR BOTS", c.message.chat.id, c.message.message_id, reply_markup=m)

    # MANAGE
    elif d.startswith("manage_"):
        name = d.replace("manage_", "")

        is_run = name in running

        m = types.InlineKeyboardMarkup(row_width=1)

        if is_run:
            m.add(btn("⛔ STOP", f"toggle_{name}"))
        else:
            m.add(btn("▶ RUN", f"toggle_{name}"))

        m.add(btn("🔄 RESTART", f"restart_{name}"))
        m.add(btn("📜 LOGS", f"logs_{name}"))
        m.add(btn("⬅ BACK", "bots"))

        bot.edit_message_text(f"🤖 <b>{name}</b>", c.message.chat.id, c.message.message_id, reply_markup=m)

    # TOGGLE RUN/STOP
    elif d.startswith("toggle_"):
        name = d.replace("toggle_", "")
        path = os.path.join(BOT_DIR, f"{name}.py")

        if name in running:
            try:
                running[name].terminate()
            except:
                pass

            running.pop(name, None)
            cursor.execute("DELETE FROM bots WHERE name=?", (name,))
            conn.commit()

            bot.answer_callback_query(c.id, "⛔ Stopped")

        else:
            log = open(f"{LOG_DIR}/{name}.log", "a")
            p = subprocess.Popen(["python", path], stdout=log, stderr=log)
            running[name] = p

            cursor.execute("INSERT OR REPLACE INTO bots VALUES (?,?)", (name, p.pid))
            conn.commit()

            bot.answer_callback_query(c.id, "▶ Running")

    # PACKAGE INSTALL SYSTEM (TERMUX STYLE)
    elif c.message.chat.id in install_mode:
        text = c.message.text or ""

        if text.startswith("pip install"):
            package = text.replace("pip install", "").strip()

            msg = bot.send_message(c.message.chat.id, f"📦 Installing {package} ...")

            time.sleep(1)
            bot.edit_message_text("🔄 Connecting to PyPI...", c.message.chat.id, msg.message_id)

            time.sleep(1)
            bot.edit_message_text("⬇ Downloading package...", c.message.chat.id, msg.message_id)

            time.sleep(1)
            bot.edit_message_text("⚙ Installing...", c.message.chat.id, msg.message_id)

            try:
                subprocess.call(["pip", "install", package])
                bot.edit_message_text(f"✅ Installed: {package}", c.message.chat.id, msg.message_id)
            except:
                bot.edit_message_text(f"❌ Failed: {package}", c.message.chat.id, msg.message_id)

            install_mode.pop(c.message.chat.id, None)

# ================= FILE UPLOAD =================

@bot.message_handler(content_types=['document'])
def upload(m):
    if m.chat.id not in waiting:
        return

    file = m.document.file_name

    if not file.endswith(".py"):
        return bot.reply_to(m, "Only .py allowed")

    data = bot.get_file(m.document.file_id)
    dl = bot.download_file(data.file_path)

    path = os.path.join(BOT_DIR, file)

    with open(path, "wb") as f:
        f.write(dl)

    waiting.remove(m.chat.id)

    bot.reply_to(m, "✅ Uploaded")

# ================= RUN =================

print("💎 TERMUX STYLE BOT RUNNING...")
bot.infinity_polling()