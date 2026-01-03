import os
import requests
import json
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- WEB SERVER FOR RENDER ---
# Render requires a web service to stay alive. We use Flask for this.
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURATION ---
# Replace the OpenRouter key with your actual key in Render's Environment Variables
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = "8594439271:AAE8zTwFAfQCQZIjRe3E-QlqKeuMoS189yY"
MODEL_ID = "meta-llama/llama-3.3-70b-instruct:free"

SYSTEM_PROMPT = """
ROLE: Calm, emotionally intelligent narrator writing a 30-second Instagram Reel script.
GOAL: Short, human, grounded advice script.
STRUCTURE:
1. Hook (0-3s): Direct "you", soft invitation.
2. Story: 2nd person, universal struggle, psychology concept, Control vs No Control.
3. Shift: Mindset shift, make them feel capable.
4. Close: Reassure, focus on today.
5. Ending Quote: Short, human, underrated quote (attribute author).
STYLE: 30s max (~90-110 words), calm/mature tone, simple English.
"""

# --- OPENROUTER API CALL ---
async def get_llm_response(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": MODEL_ID,
        "messages": messages
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=json.dumps(data))
    result = response.json()
    return result['choices'][0]['message']['content']

# --- TELEGRAM HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **Instagram Reel Script Generator**\n\n"
        "Send me your details like this:\n"
        "Theme: [Your Theme]\n"
        "Struggle: [Core Struggle]\n"
        "Concept: [Optional Concept]"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if 'history' not in context.user_data:
        context.user_data['history'] = [{"role": "system", "content": SYSTEM_PROMPT}]

    context.user_data['history'].append({"role": "user", "content": user_input})
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action="typing")

    try:
        reply = await get_llm_response(context.user_data['history'])
        context.user_data['history'].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['history'] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text("🔄 Memory cleared. Ready for a new theme!")

# --- RUN BOT ---
if __name__ == "__main__":
    # Start the Flask "Stay Alive" server in the background
    threading.Thread(target=run_flask, daemon=True).start()

    # Start the Telegram Bot
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is live...")
    application.run_polling()
