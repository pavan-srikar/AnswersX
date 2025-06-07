import pytesseract
from PIL import ImageGrab, Image
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai
import io
import threading
import time
from pynput.keyboard import Controller, Key
import os
from dotenv import load_dotenv

load_dotenv()

# Load tokens from .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

# Typing setup
keyboard = Controller()
stop_flag = threading.Event()
typing_speed = 25  # chars per second

def type_text(text, speed):
    delay = 1.0 / speed
    for char in text:
        if stop_flag.is_set():
            break
        if char == '\n':
            keyboard.press(Key.enter)
            keyboard.release(Key.enter)
        else:
            keyboard.type(char)
        time.sleep(delay)

def start_typing(text):
    stop_flag.clear()
    threading.Thread(target=type_text, args=(text, typing_speed), daemon=True).start()

def stop_typing():
    stop_flag.set()

# Screenshot and OCR
def take_screenshot():
    img = ImageGrab.grab()
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return byte_arr.getvalue()

def extract_text_from_image(image):
    try:
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return f"Error extracting text: {e}"

# Gemini 2.0 Flash model call
def query_gemini(prompt, image=None):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        inputs = [prompt]
        if image:
            inputs.append(image)
        response = model.generate_content(inputs)
        return response.text
    except Exception as e:
        return f"Error contacting Gemini API: {e}"

# Telegram command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Commands:\n"
        "/screenshot - Take a screenshot\n"
        "/screenshot_answer - Screenshot + analyze text with Gemini\n"
        "/text <message> - Start typing text\n"
        "/stop - Stop typing\n"
        "/prompt <temporary prompt> - Set a temp prompt (not fully implemented)"
    )

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image_bytes = take_screenshot()
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes)

async def screenshot_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image_bytes = take_screenshot()
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes)
    await update.message.reply_text("Extracting text...")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        text = extract_text_from_image(img)
        if text.startswith("Error"):
            await update.message.reply_text(text)
            return
        await update.message.reply_text(f"Extracted Text:\n{text}\nSending to Gemini for analysis...")
        answer = query_gemini(text, img)
        await update.message.reply_text(f"Gemini Answer:\n{answer}")
    except Exception as e:
        await update.message.reply_text(f"Error processing screenshot: {e}")

async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Please provide text to type. Example: /text Hello World")
        return
    start_typing(text)
    await update.message.reply_text("Typing started.")

async def stop_typing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stop_typing()
    await update.message.reply_text("Typing stopped.")

async def set_temporary_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global temporary_prompt
    temporary_prompt = " ".join(context.args)
    if not temporary_prompt:
        await update.message.reply_text("Temporary prompt cleared.")
        temporary_prompt = None
    else:
        await update.message.reply_text(f"Temporary prompt set to: {temporary_prompt}")

# Main app setup
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("screenshot", screenshot))
    app.add_handler(CommandHandler("screenshot_answer", screenshot_answer))
    app.add_handler(CommandHandler("text", send_text))
    app.add_handler(CommandHandler("stop", stop_typing_command))
    app.add_handler(CommandHandler("prompt", set_temporary_prompt))
    app.run_polling()

if __name__ == "__main__":
    main()
