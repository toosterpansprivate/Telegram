import os
import json
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ────────────────────────────
# 🌐 Flask server (keep-alive)
# ────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ────────────────────────────
# 🔐 CONFIGURATION
# ────────────────────────────
OPENROUTER_API_KEY = "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"

# 🔴 HARD-CODED TELEGRAM BOT TOKEN (AS REQUESTED)
TELEGRAM_BOT_TOKEN = "8594439271:AAE8zTwFAfQCQZIjRe3E-QlqKeuMoS189yY"

MODEL_ID = "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_PROMPT = """
You are a calm, emotionally intelligent narrator.

Your task is to generate a 30-second Instagram Reel script using this structure:
Hook → Story → Shift → Close → Quote.

User input may be:
- A rough motivational draft
- Raw thoughts
- Stats or facts
- A direct instruction (/create, /stats, /edit, /quick)

Rules:
- If input looks like a draft, treat it as RAW MATERIAL and refine it.
- Improve structure, flow, and pacing without changing meaning.
- Always use second-person (“you”).
- Calm, grounded, mature tone.
- No headings.
- No explanations.
- Output ONLY the final script.
"""

# ────────────────────────────
# 🤖 OpenRouter API
# ────────────────────────────
def call_openrouter(messages):
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": MODEL_ID,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 350,
        }),
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

async def get_llm_response(messages):
    loop = threading.get_event_loop()
    return await loop.run_in_executor(None, call_openrouter, messages)

# ────────────────────────────
# 🧠 Utility: detect raw drafts
# ────────────────────────────
def looks_like_draft(text: str) -> bool:
    return len(text.splitlines()) >= 4 or len(text.split()) > 80

# ────────────────────────────
# 📩 Telegram Handlers
# ────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["history"] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    await update.message.reply_text(
        "Send raw thoughts, drafts, stats, or use commands:\n\n"
        "/create – create from scratch\n"
        "/stats – convert stats to script\n"
        "/edit – edit last script\n"
        "/quick – fast one-line idea\n"
        "/new – reset conversation"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("New conversation started. Send a fresh idea.")

# ────────────── COMMANDS ──────────────

async def create_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = f"""
Create a fresh 30-second Instagram Reel script using this input:

{update.message.text.replace('/create', '').strip()}
"""
    context.user_data["history"] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    reply = await get_llm_response(context.user_data["history"])
    context.user_data["history"].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

async def stats_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = f"""
Convert the following stats into a calm, human reel script.
Focus on emotional pressure, not numbers.

Stats:
{update.message.text.replace('/stats', '').strip()}
"""
    context.user_data["history"] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    reply = await get_llm_response(context.user_data["history"])
    context.user_data["history"].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

async def edit_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    instruction = update.message.text.replace('/edit', '').strip()

    context.user_data["history"].append({
        "role": "user",
        "content": f"Edit the previous script using these instructions:\n{instruction}"
    })

    reply = await get_llm_response(context.user_data["history"])
    context.user_data["history"].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

async def quick_script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    idea = update.message.text.replace('/quick', '').strip()

    context.user_data["history"] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Create a 30-second reel script based on this idea:\n{idea}"}
    ]

    reply = await get_llm_response(context.user_data["history"])
    context.user_data["history"].append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply)

# ────────────── DEFAULT HANDLER ──────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    if "history" not in context.user_data:
        context.user_data["history"] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    # Auto-refine raw drafts
    if looks_like_draft(user_text):
        user_text = f"""
Refine the following raw draft into a structured 30-second reel script.
Improve clarity, flow, and pacing.

Draft:
{user_text}
"""

    context.user_data["history"].append(
        {"role": "user", "content": user_text}
    )

    await context.bot.send_chat_action(
        chat_id=update.message.chat_id,
        action=ChatAction.TYPING
    )

    reply = await get_llm_response(context.user_data["history"])
    context.user_data["history"].append({"role": "assistant", "content": reply})

    await update.message.reply_text(reply)

# ────────────────────────────
# 🚀 RUN EVERYTHING
# ────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("new", reset))
    application.add_handler(CommandHandler("create", create_script))
    application.add_handler(CommandHandler("stats", stats_script))
    application.add_handler(CommandHandler("edit", edit_script))
    application.add_handler(CommandHandler("quick", quick_script))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("✅ Bot is live")
    application.run_polling()
