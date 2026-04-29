import os
import io
import random
import requests
import logging
from flask import Flask, request, jsonify
from PIL import Image
import google.generativeai as genai
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# APP & BOT INITIALIZATION
# ==========================================
app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# threaded=False is strictly required for Vercel Serverless environments
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)

GROQ_KEYS = [os.getenv("GROQ_API_KEY_1"), os.getenv("GROQ_API_KEY_2"), os.getenv("GROQ_API_KEY_3")]
GEMINI_KEYS = [os.getenv("GEMINI_API_KEY_1"), os.getenv("GEMINI_API_KEY_2")]
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# ==========================================
# LOAD SKILLS
# ==========================================
def load_skill(filename):
    base_dir = os.path.dirname(os.path.dirname(__file__)) 
    file_path = os.path.join(base_dir, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
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
# AI SMART ROUTER
# ==========================================
def try_groq(system_prompt, user_text):
    keys = [k for k in GROQ_KEYS if k]
    random.shuffle(keys)
    for key in keys:
        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
                temperature=0.7
            )
            return response.choices[0].message.content
        except: continue
    return None

def try_gemini(system_prompt, user_text, image_data=None):
    keys = [k for k in GEMINI_KEYS if k]
    random.shuffle(keys)
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            contents = [system_prompt + "\n\nUser Context:\n" + user_text]
            if image_data:
                img = Image.open(io.BytesIO(image_data))
                contents.append(img)
            response = model.generate_content(contents)
            return response.text
        except: continue
    return None

def try_together(system_prompt, user_text):
    if not TOGETHER_API_KEY: return None
    try:
        url = "https://api.together.xyz/v1/chat/completions"
        headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "meta-llama/Llama-3-8b-chat-hf", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]}
        r = requests.post(url, headers=headers, json=data)
        return r.json()["choices"][0]["message"]["content"]
    except: return None

def try_huggingface(system_prompt, user_text):
    if not HUGGINGFACE_API_KEY: return None
    try:
        url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        payload = {"inputs": system_prompt + "\n\n" + user_text}
        r = requests.post(url, headers=headers, json=payload)
        return r.json()[0]["generated_text"].replace(payload["inputs"], "").strip()
    except: return None

def generate_ai(system_prompt, user_text, image_data=None):
    if image_data:
        result = try_gemini(system_prompt, user_text, image_data)
        if result: return result
        return "❌ Vision AI failed."
    
    result = try_groq(system_prompt, user_text)
    if result: return result
    result = try_gemini(system_prompt, user_text)
    if result: return result
    result = try_together(system_prompt, user_text)
    if result: return result
    result = try_huggingface(system_prompt, user_text)
    if result: return result
    return "❌ All AI providers failed."

# ==========================================
# BOT COMMANDS & HANDLERS
# ==========================================
@bot.message_handler(commands=["start"])
def start(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("✨ Humanize Post"), KeyboardButton("🎣 Add Hook"), KeyboardButton("💬 Generate Comments"))
    text = "Hello 👋 Welcome to Humanify AI\n\nYou can use buttons below or directly use commands:\n/comment <paste tweet>\n/reply <paste thread>\n"
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["comment", "reply"])
def handle_comment_reply_commands(message):
    chat_id = message.chat.id
    command = message.text.split()[0] 
    user_input = message.text.replace(command, "", 1).strip()
    
    if not user_input:
        bot.send_message(chat_id, f"⚠️ Please provide the text.\nExample: `{command} this is a cool tweet`", parse_mode="Markdown")
        return
        
    wait = bot.reply_to(message, "Generating elite CT response... 🧠⏳")
    system_prompt = SKILLS.get("💬 Generate Comments", load_skill("comment.md"))
    result = generate_ai(system_prompt, message.text)
    bot.delete_message(chat_id, wait.message_id)
    bot.reply_to(message, result)

@bot.message_handler(func=lambda message: message.text in SKILLS.keys())
def buttons(message):
    user_states[message.chat.id] = message.text
    bot.reply_to(message, f"You selected **{message.text}**.\n\nSend your post or image 👇", parse_mode="Markdown")

@bot.message_handler(content_types=["text"])
def text(message):
    chat_id = message.chat.id
    if message.text.startswith('/'): return
    if chat_id not in user_states:
        bot.send_message(chat_id, "Please choose an option from the menu first, or use /comment or /reply.")
        return
    wait = bot.reply_to(message, "Processing text... ⏳")
    system_prompt = SKILLS[user_states[chat_id]]
    result = generate_ai(system_prompt, message.text)
    bot.delete_message(chat_id, wait.message_id)
    bot.send_message(chat_id, result)

@bot.message_handler(content_types=["photo"])
def image(message):
    chat_id = message.chat.id
    if chat_id not in user_states:
        bot.send_message(chat_id, "Please choose an option from the menu first.")
        return
    wait = bot.reply_to(message, "Analyzing image and drafting response... 👁️⏳")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        caption = message.caption if message.caption else "Analyze this image."
        system_prompt = SKILLS[user_states[chat_id]]
        result = generate_ai(system_prompt, caption, image_data=downloaded_file)
    except Exception as e:
        result = "❌ Failed to process the image."
    bot.delete_message(chat_id, wait.message_id)
    bot.send_message(chat_id, result)

# ==========================================
# FLASK WEBHOOK ROUTES FOR VERCEL
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return "Bot is running perfectly on Vercel! 🚀", 200

# Exposes deep telebot errors to the Vercel logs
telebot.logger.setLevel(logging.DEBUG) 

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            print(f"📬 Payload from Telegram: {json_string}")
            
            update = telebot.types.Update.de_json(json_string)
            
            # DIRECT TEST: Verifies Vercel can ping the Telegram API
            if update.message:
                print(f"💬 Attempting to reply to chat_id: {update.message.chat.id}")
                bot.send_message(update.message.chat.id, "✅ Testing: Webhook is alive and Vercel is sending messages!")
            
            bot.process_new_updates([update])
            return 'OK', 200
            
        return 'Invalid Request', 403
    except Exception as e:
        print(f"🔥 CRITICAL BOT ERROR: {e}")
        return 'Error', 500

@app.route('/api/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = f"https://{request.host}/api/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    return f"✅ Webhook successfully set to: {webhook_url}", 200
    def try_groq(system_prompt, user_text):
    keys = [k for k in GROQ_KEYS if k]
    random.shuffle(keys)
    for key in keys:
        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e: 
            print(f"❌ GROQ ERROR: {e}") # This will now show up in Vercel logs!
            continue
    return None

def try_gemini(system_prompt, user_text, image_data=None):
    keys = [k for k in GEMINI_KEYS if k]
    random.shuffle(keys)
    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            contents = [system_prompt + "\n\nUser Context:\n" + user_text]
            if image_data:
                img = Image.open(io.BytesIO(image_data))
                contents.append(img)
            response = model.generate_content(contents)
            return response.text
        except Exception as e: 
            print(f"❌ GEMINI ERROR: {e}") # This will now show up in Vercel logs!
            continue
    return None
