import pytesseract
from PIL import ImageGrab
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai
import io
from PIL import Image
import threading
import time
from pynput.keyboard import Controller, Key

# Set your bot token and Gemini API key
TELEGRAM_BOT_TOKEN = "API_NIGGA"
GEMINI_API_KEY = "API_NIGGA"

genai.configure(api_key=GEMINI_API_KEY)

# Typing-related variables
keyboard = Controller()
stop_flag = threading.Event()
typing_speed = 25  # Typing speed in characters per second

# Prompt configuration
DEFAULT_PROMPT = "Always answer in medium size with simple vocabulary. For multiple-choice questions, include options formatting like A) Correct Answer."
temporary_prompt = None

# Typing functions
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
    threading.Thread(target=type_text, args=(text, typing_speed)).start()

def stop_typing():
    stop_flag.set()

# Screenshot and OCR functions
def take_screenshot():
    image = ImageGrab.grab()
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr

def extract_text(image_path):
    try:
        image = ImageGrab.grab()
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return f"Error extracting text: {e}"

# Gemini API function
def query_gemini(image_bytes, text):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')  # Updated model name
        img = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([text, img])
        return response.text
    except Exception as e:
        return f"Error contacting Gemini API: {e}"

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to your enhanced bot! Available commands:\n"
        "/screenshot - Take a screenshot\n"
        "/screenshot_answer - Take a screenshot and analyze text with Gemini\n"
        "/text <message> - Start typing the provided text\n"
        "/stop - Stop typing\n"
        "/prompt <temporary prompt> - Set a temporary response behavior"
    )

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image_bytes = take_screenshot()
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes)

async def screenshot_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image_bytes = take_screenshot()
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes)
    await update.message.reply_text("Extracting text...")
    text = extract_text("screenshot.png")
    if "Error" in text:
        await update.message.reply_text(text)
        return
    await update.message.reply_text(f"Extracted Text:\n{text}\nSending to Gemini for analysis...")
    answer = query_gemini(image_bytes, text)
    await update.message.reply_text(f"Gemini Answer:\n{answer}")

async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text("Please provide text to type. Example: /text Hello World")
            return
        start_typing(text)
        await update.message.reply_text("Typing started.")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

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

# Main function
def main():
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("screenshot", screenshot))
    application.add_handler(CommandHandler("screenshot_answer", screenshot_answer))
    application.add_handler(CommandHandler("text", send_text))
    application.add_handler(CommandHandler("stop", stop_typing_command))
    application.add_handler(CommandHandler("prompt", set_temporary_prompt))

    application.run_polling()

if __name__ == "__main__":
    main()
