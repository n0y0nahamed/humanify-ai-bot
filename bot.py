import os
import telebot
import base64
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from groq import Groq
from dotenv import load_dotenv

# ==========================================
# 1. LOAD ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN or GROQ_API_KEY is missing in the .env file!")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# 2. LOAD SKILL FILES (.md)
# ==========================================
def load_skill(filename):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return ""

SKILLS = {
    "✨ Humanize Post": load_skill("humanize.md"),
    "🎣 Add Hook": load_skill("hook.md"),
    "💬 Generate Comments": load_skill("comment.md")
}

user_states = {}

# ==========================================
# 3. START COMMAND
# ==========================================
@bot.message_handler(commands=["start"])
def start(message):

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    btn1 = KeyboardButton("✨ Humanize Post")
    btn2 = KeyboardButton("🎣 Add Hook")
    btn3 = KeyboardButton("💬 Generate Comments")

    markup.add(btn1, btn2, btn3)

    text = (
        "Hello 👋 Welcome to Humanify AI 🤖\n\n"
        "Send a post or image and I will:\n\n"
        "✨ Make it sound more human\n"
        "🎣 Add a powerful hook\n"
        "💬 Generate engaging comments\n\n"
        "Made with ❤️ by @n0y0nahamed"
    )

    bot.send_message(message.chat.id, text, reply_markup=markup)

# ==========================================
# BUTTON HANDLER
# ==========================================
@bot.message_handler(func=lambda message: message.text in SKILLS.keys())
def handle_buttons(message):

    chat_id = message.chat.id
    user_states[chat_id] = message.text

    bot.reply_to(message, "Paste your post or send image + caption 👇")

# ==========================================
# TEXT HANDLER
# ==========================================
@bot.message_handler(content_types=["text"])
def handle_text(message):

    chat_id = message.chat.id

    if chat_id not in user_states or user_states[chat_id] is None:
        bot.send_message(chat_id, "Please choose an option first 👇")
        return

    wait = bot.reply_to(message, "Processing... ⏳")

    try:

        system_prompt = SKILLS[user_states[chat_id]]

        response = client.chat.completions.create(

            model="llama-3.1-8b-instant",

            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message.text}
            ],

            temperature=0.7
        )

        result = response.choices[0].message.content

        bot.delete_message(chat_id, wait.message_id)

        bot.send_message(chat_id, result)

    except Exception as e:

        bot.send_message(chat_id, f"Error: {str(e)}")

    finally:

        user_states[chat_id] = None

# ==========================================
# IMAGE HANDLER (IMAGE + POST TOGETHER)
# ==========================================
@bot.message_handler(content_types=["photo"])
def handle_image(message):

    chat_id = message.chat.id

    if chat_id not in user_states or user_states[chat_id] is None:
        bot.send_message(chat_id, "Please choose an option first 👇")
        return

    wait = bot.reply_to(message, "Analyzing image + post... ⏳")

    try:

        photo = message.photo[-1]

        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        base64_image = base64.b64encode(downloaded_file).decode("utf-8")

        caption = message.caption if message.caption else ""

        system_prompt = SKILLS[user_states[chat_id]]

        response = client.chat.completions.create(

            model="llama-3.2-11b-vision-preview",

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Post:\n{caption}\n\nLook at the image and the post together."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],

            temperature=0.7
        )

        result = response.choices[0].message.content

        bot.delete_message(chat_id, wait.message_id)

        bot.send_message(chat_id, result)

    except Exception as e:

        bot.send_message(chat_id, f"Error: {str(e)}")

    finally:

        user_states[chat_id] = None

# ==========================================
# RUN BOT
# ==========================================
if __name__ == "__main__":

    print("🤖 Humanify AI Bot is running...")

    bot.infinity_polling()