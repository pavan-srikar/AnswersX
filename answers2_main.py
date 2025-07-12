import pytesseract
from PIL import ImageGrab, Image
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.generativeai as genai
import io
import threading
import time
import os
import pyautogui
from dotenv import load_dotenv

load_dotenv()

# Load tokens
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

# Typing setup
pyautogui.PAUSE = 0
stop_flag = threading.Event()
temporary_prompt = None
typing_speed = 60  # chars per second (default)


def type_text(text, speed):
    delay = 1.0 / speed
    for char in text:
        if stop_flag.is_set():
            break
        if char == '\n':
            pyautogui.press('enter')
        else:
            pyautogui.typewrite(char, interval=0)
        time.sleep(delay)

def start_typing(text):
    stop_flag.clear()
    threading.Thread(target=type_text, args=(text, typing_speed), daemon=True).start()

def stop_typing():
    stop_flag.set()

# Screenshot + OCR
def take_screenshot():
    img = ImageGrab.grab()
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return byte_arr.getvalue()

def extract_text_from_image(image):
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        return f"Error extracting text: {e}"

# Gemini 2.0 Flash model call
def query_gemini(prompt, image=None):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        full_prompt = f"{temporary_prompt}\n\n{prompt}" if temporary_prompt else prompt
        inputs = [full_prompt]
        if image:
            inputs.append(image)
        response = model.generate_content(inputs)
        return response.text
    except Exception as e:
        return f"Error contacting Gemini API: {e}"

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/screenshot - Take screenshot\n"
        "/screenshot_answer - Screenshot + extract + Gemini\n"
        "/text <message> - Start typing\n"
        "/stop - Stop typing\n"
        "/prompt <text> - Set temporary prompt\n"
        "/speed <num> - Set typing speed (chars/sec)\n"
        "/reset - Reset speed and prompt"
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
        await update.message.reply_text(f"Extracted Text:\n{text}\nSending to Gemini...")
        answer = query_gemini(text, img)
        await update.message.reply_text(f"Gemini Answer:\n{answer}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global temporary_prompt
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /text <message>")
        return
    if temporary_prompt:
        text = f"{temporary_prompt}\n{text}"
    start_typing(text)
    await update.message.reply_text(f"Typing started at {typing_speed} chars/sec")

async def stop_typing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stop_typing()
    await update.message.reply_text("Typing stopped.")

async def set_temporary_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global temporary_prompt
    temporary_prompt = " ".join(context.args)
    if not temporary_prompt:
        await update.message.reply_text("Prompt cleared.")
        temporary_prompt = None
    else:
        await update.message.reply_text(f"Prompt set to:\n{temporary_prompt}")

async def set_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global typing_speed
    try:
        speed = int(context.args[0])
        typing_speed = max(1, speed)
        await update.message.reply_text(f"Typing speed set to {typing_speed} chars/sec")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /speed <number>")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global typing_speed, temporary_prompt
    typing_speed = 60
    temporary_prompt = None
    await update.message.reply_text("Typing speed reset to 60 and prompt cleared.")

# Main setup
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("screenshot", screenshot))
    app.add_handler(CommandHandler("screenshot_answer", screenshot_answer))
    app.add_handler(CommandHandler("text", send_text))
    app.add_handler(CommandHandler("stop", stop_typing_command))
    app.add_handler(CommandHandler("prompt", set_temporary_prompt))
    app.add_handler(CommandHandler("speed", set_speed))
    app.add_handler(CommandHandler("reset", reset))
    app.run_polling()

if __name__ == "__main__":
    main()
