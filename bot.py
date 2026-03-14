import os
import telebot
import base64
import requests
import random
import google.generativeai as genai
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# TOKENS
# ==========================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1"),
    os.getenv("GROQ_API_KEY_2"),
    os.getenv("GROQ_API_KEY_3")
]

GEMINI_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2")
]

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ==========================================
# LOAD SKILLS
# ==========================================

def load_skill(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

SKILLS = {
    "✨ Humanize Post": load_skill("humanize.md"),
    "🎣 Add Hook": load_skill("hook.md"),
    "💬 Generate Comments": load_skill("comment.md")
}

user_states = {}

# ==========================================
# GROQ ROTATION
# ==========================================

def try_groq(system_prompt, user_text):

    keys = [k for k in GROQ_KEYS if k]
    random.shuffle(keys)

    for key in keys:

        try:

            client = Groq(api_key=key)

            response = client.chat.completions.create(

                model="llama-3.1-8b-instant",

                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],

                temperature=0.7
            )

            print("Using GROQ")

            return response.choices[0].message.content

        except Exception as e:

            print("Groq failed:", e)

    return None


# ==========================================
# GEMINI ROTATION
# ==========================================

def try_gemini(system_prompt, user_text):

    keys = [k for k in GEMINI_KEYS if k]
    random.shuffle(keys)

    for key in keys:

        try:

            genai.configure(api_key=key)

            model = genai.GenerativeModel("gemini-1.5-flash")

            response = model.generate_content(
                system_prompt + "\n\nUser:\n" + user_text
            )

            print("Using GEMINI")

            return response.text

        except Exception as e:

            print("Gemini failed:", e)

    return None


# ==========================================
# TOGETHER AI
# ==========================================

def try_together(system_prompt, user_text):

    try:

        url = "https://api.together.xyz/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "meta-llama/Llama-3-8b-chat-hf",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        }

        r = requests.post(url, headers=headers, json=data)

        result = r.json()

        print("Using TOGETHER")

        return result["choices"][0]["message"]["content"]

    except Exception as e:

        print("Together failed:", e)

    return None


# ==========================================
# HUGGINGFACE
# ==========================================

def try_huggingface(system_prompt, user_text):

    try:

        url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"

        headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}"
        }

        payload = {
            "inputs": system_prompt + "\n\n" + user_text
        }

        r = requests.post(url, headers=headers, json=payload)

        result = r.json()

        print("Using HUGGINGFACE")

        return result[0]["generated_text"]

    except Exception as e:

        print("Huggingface failed:", e)

    return None


# ==========================================
# AI ROUTER
# ==========================================

def generate_ai(system_prompt, user_text):

    result = try_groq(system_prompt, user_text)

    if result:
        return result

    result = try_gemini(system_prompt, user_text)

    if result:
        return result

    result = try_together(system_prompt, user_text)

    if result:
        return result

    result = try_huggingface(system_prompt, user_text)

    if result:
        return result

    return "❌ All AI providers failed."


# ==========================================
# START
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    markup.add(
        KeyboardButton("✨ Humanize Post"),
        KeyboardButton("🎣 Add Hook"),
        KeyboardButton("💬 Generate Comments")
    )

    text = (
        "Hello 👋 Welcome to Humanify AI\n\n"
        "✨ Humanize Post\n"
        "🎣 Add Hook\n"
        "💬 Generate Comments\n\n"
        "Send text or image + caption"
    )

    bot.send_message(message.chat.id, text, reply_markup=markup)


# ==========================================
# BUTTON
# ==========================================

@bot.message_handler(func=lambda message: message.text in SKILLS.keys())
def buttons(message):

    user_states[message.chat.id] = message.text

    bot.reply_to(message, "Send your post 👇")


# ==========================================
# TEXT
# ==========================================

@bot.message_handler(content_types=["text"])
def text(message):

    chat_id = message.chat.id

    if chat_id not in user_states:

        bot.send_message(chat_id, "Choose option first")
        return

    wait = bot.reply_to(message, "Processing... ⏳")

    system_prompt = SKILLS[user_states[chat_id]]

    result = generate_ai(system_prompt, message.text)

    bot.delete_message(chat_id, wait.message_id)

    bot.send_message(chat_id, result)

    user_states.pop(chat_id, None)


# ==========================================
# IMAGE
# ==========================================

@bot.message_handler(content_types=["photo"])
def image(message):

    chat_id = message.chat.id

    if chat_id not in user_states:

        bot.send_message(chat_id, "Choose option first")
        return

    wait = bot.reply_to(message, "Analyzing image...")

    caption = message.caption if message.caption else ""

    system_prompt = SKILLS[user_states[chat_id]]

    result = generate_ai(system_prompt, caption)

    bot.delete_message(chat_id, wait.message_id)

    bot.send_message(chat_id, result)

    user_states.pop(chat_id, None)


# ==========================================
# RUN
# ==========================================

print("🤖 Humanify AI Advanced Bot Running...")

bot.infinity_polling()