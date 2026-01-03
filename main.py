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
# 🌐 FLASK SERVER (Render Keep-Alive)
# ────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ────────────────────────────
# 🔐 CONFIGURATION
# ────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# 🔴 HARD-CODED TELEGRAM TOKEN (as requested)
TELEGRAM_BOT_TOKEN = "8594439271:AAE8zTwFAfQCQZIjRe3E-QlqKeuMoS189yY"

MODEL_ID = "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_PROMPT = """
ROLE:
You are a calm, emotionally intelligent narrator who speaks with quiet confidence and empathy.

TASK:
Read the user's input and transform it into a short, reflective script suitable for a 20–30 second social media reel.

VOICE & TONE:
- Simple, clear English
- Calm, mature, grounded
- Sounds spoken, not written
- Emotionally honest
- Never preachy, dramatic, or hype-driven

STRUCTURE (use naturally, not rigidly):
- Open with a soft hook that speaks directly to the listener (“you”)
- Reflect a common human struggle or feeling present in the input
- Gently distinguish between what cannot be controlled and what can
- Introduce a reassuring mindset shift that restores a sense of agency
- End with calm reassurance or focus on the present moment
- Close with a short, human, underrated quote, including the author’s name

OUTPUT RULES:
- 90–120 words maximum
- Always use second-person voice (“you”)
- Use short lines and natural pauses for spoken flow
- Avoid clichés, buzzwords, or motivational shouting
- Make it feel like quiet advice from someone who truly understands

IMPORTANT:
Do not explain the structure.
Only output the final script.
"""

# ────────────────────────────
# 🤖 OPENROUTER CALL
# ────────────────────────────
def call_openrouter(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 350,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=60,
    )

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]

async def get_llm_response(messages):
    return await threading.get_event_loop().run_in_executor(
        None, call_openrouter, messages
    )

# ────────────────────────────
# 📩 TELEGRAM HANDLERS
# ────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Instagram Reel Script Generator\n\n"
        "Send any thought, theme, or raw idea.\n"
        "I’ll turn it into a calm, reflective reel script."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    if "history" not in context.user_data:
        context.user_data["history"] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    context.user_data["history"].append(
        {"role": "user", "content": user_input}
    )

    await context.bot.send_chat_action(
        chat_id=update.message.chat_id,
        action=ChatAction.TYPING,
    )

    try:
        reply = await get_llm_response(context.user_data["history"])
        context.user_data["history"].append(
            {"role": "assistant", "content": reply}
        )
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text("⚠️ Something went wrong. Try again.")
        print("Error:", e)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    await update.message.reply_text("🔄 Memory cleared. Send a new idea!")

# ────────────────────────────
# 🚀 RUN BOT
# ────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("✅ Bot is live…")
    application.run_polling()
