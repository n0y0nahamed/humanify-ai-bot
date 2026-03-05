import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from groq import Groq
from dotenv import load_dotenv

# ==========================================
# 1. LOAD ENVIRONMENT VARIABLES
# ==========================================
# Load tokens from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Raise error if tokens are missing
if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN or GROQ_API_KEY is missing in the .env file!")

# Initialize Telegram Bot and Groq Client
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# 2. LOAD SKILL FILES (.md)
# ==========================================
def load_skill(filename):
    """Utility function to read markdown skill files."""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return ""

# Map buttons to their respective skill prompts
SKILLS = {
    '✨ Humanize Post': load_skill('humanize.md'),
    '🎣 Add Hook': load_skill('hook.md'),
    '💬 Generate Comments': load_skill('comment.md')
}

# State dictionary to track user's selected action
user_states = {}

# ==========================================
# 3. BOT COMMANDS & HANDLERS
# ==========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handle /start command and show the main menu."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton('✨ Humanize Post')
    btn2 = KeyboardButton('🎣 Add Hook')
    btn3 = KeyboardButton('💬 Generate Comments')
    markup.add(btn1, btn2, btn3)
    
    welcome_text = (
        "Hello 👋 Welcome to Humanify AI 🤖\n"
        "Send me any post and I will:\n\n"
        "✨ Make it sound more human\n"
        "🎣 Add a powerful hook\n"
        "💬 Generate engaging comments\n\n"
        "Let’s turn your content into something people actually want to read 🚀\n\n"
        "Made with ❤️ by @n0y0nahamed"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in SKILLS.keys())
def handle_button_click(message):
    """Handle menu button clicks and ask for user input."""
    chat_id = message.chat.id
    selected_skill = message.text
    
    # Store the user's current selection
    user_states[chat_id] = selected_skill
    
    # Prompt the user to paste their content
    bot.reply_to(message, "paste your post here :")

@bot.message_handler(func=lambda message: True)
def handle_user_post(message):
    """Process the user's text based on the selected skill."""
    chat_id = message.chat.id
    user_text = message.text
    
    # Validate if a skill was selected first
    if chat_id not in user_states or user_states[chat_id] is None:
        bot.send_message(chat_id, "Please select an option from the menu below first! 👇")
        return
    
    # Send a temporary 'waiting' status message
    wait_msg = bot.reply_to(message, "wait 2-3 seconds ⏳✨")
    
    selected_skill = user_states[chat_id]
    system_prompt = SKILLS[selected_skill]
    
    try:
        # Call Groq API using Llama 3.1 8b
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_text,
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.7,
        )
        
        # Extract the AI-generated result
        ai_response = chat_completion.choices[0].message.content
        
        # Delete the temporary 'wait' message
        bot.delete_message(chat_id, wait_msg.message_id)
        
        # Send the final processed result to the user
        bot.send_message(chat_id, ai_response)
        
    except Exception as e:
        # Error handling for API or network issues
        if wait_msg:
            bot.delete_message(chat_id, wait_msg.message_id)
        bot.send_message(chat_id, f"Error processing request: {str(e)}")
        
    finally:
        # Clear user state for the next interaction
        user_states[chat_id] = None

# ==========================================
# 4. START THE POLLING ENGINE
# ==========================================
if __name__ == "__main__":
    print("🤖 Humanify AI Bot is live and running...")
    bot.infinity_polling()