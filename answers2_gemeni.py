# fixed text speed, prompt and added /reset 


import pytesseract
from PIL import ImageGrab, Image
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import google.genai as genai
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

client = genai.Client(api_key=GEMINI_API_KEY)

# Typing setup
pyautogui.PAUSE = 0
stop_flag = threading.Event()
default_prompt = "if the question has multiple choise, give a short explanation and if the correct option is option B which has the the answer of 67.67 grams, end the response by saying the answer is ➡️ B) 67.67 grams. this is an example by the way change the option and value based on questions."
temporary_prompt = None
typing_speed = 60  # chars per second (default)


def type_text(text, speed):
    time.sleep(2)
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
    # List of models to try in order of preference
    models_to_try = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']
    
    active_prompt = temporary_prompt if temporary_prompt else default_prompt
    full_prompt = f"{active_prompt}\n\n{prompt}"
    content = [full_prompt, image] if image else full_prompt

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=content
            )
            return response.text
        except Exception as e:
            if "503" in str(e) or "429" in str(e):
                print(f"Model {model_name} busy, trying next...")
                continue # Try the next model in the list
            return f"Error: {e}"
            
    return "Nigga all Gemini models are currently overloaded for free plan. If your broke ass can't afford paid plan, try again in a minute."

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/screenshot - Take screenshot\n"
        "/screenshot_answer - Screenshot + extract + Gemini\n"
        "/text <message> - Start typing\n"
        "/stop - Stop typing\n"
        "/prompt <text> - default prompt is always active unless overridden \n"
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
    # Extract full message text including newlines
    if not (message_text := update.message.text):
        await update.message.reply_text("Usage: /text <message>")
        return
    
    # Remove command while preserving formatting
    command = message_text.split()[0]  # Get the first word (/text or /text@botname)
    text = message_text[len(command):].lstrip()
    
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
    await update.message.reply_text("Reset done. Back to default prompt + 60 cps speed.")

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
