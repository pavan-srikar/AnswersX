import pytesseract
import pyautogui
from PIL import Image
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from groq import Groq
import io
import threading
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Windows Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Load tokens
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or GROQ_API_KEY in environment variables")

client = Groq(api_key=GROQ_API_KEY)

# Typing setup
pyautogui.PAUSE = 0
stop_flag = threading.Event()
temporary_prompt = None
typing_speed = 60  # chars per second

DEFAULT_STYLE_PROMPT = """
Respond a bit like a Gen Z nigga .
Keep answers short if they are MCQs like only give the option and answer and 2 lines expanation.
be chill and all you are helping me cheat in exams so dont spit essays that sound AI.
Never write essays. Never explain like a professor.
Max 6-7 sentences per answer unless its specifically asked. If too long, summarize aggressively unless its a code snippet.
"""

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


# Windows Screenshot
def take_screenshot():
    img = pyautogui.screenshot()
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return byte_arr.getvalue()


# OCR function
def extract_text_from_image(image):
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception as e:
        return f"Error extracting text: {e}"


# FIXED Groq call
def query_gemini(prompt):
    try:
        full_prompt = f"{DEFAULT_STYLE_PROMPT}\n\nUser Content:\n{prompt}"

        if temporary_prompt:
            full_prompt = f"{temporary_prompt}\n\n{full_prompt}"

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "user", "content": full_prompt}
            ],
            temperature=1,
            max_tokens=1500,
            top_p=1
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"Error contacting Groq API: {e}"


# Split long Telegram messages
def split_message(text, max_len=4000):
    return [text[i:i + max_len] for i in range(0, len(text), max_len)]


# Telegram bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/screenshot - Take screenshot\n"
        "/screenshot_answer - Screenshot + OCR + Groq\n"
        "/text <message> - Start typing\n"
        "/stop - Stop typing\n"
        "/prompt <text> - Set temporary prompt\n"
        "/speed <num> - Set typing speed\n"
        "/reset - Reset prompt & speed"
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

        await update.message.reply_text(f"Extracted Text:\n{text}\nSending to Groq...")

        answer = query_gemini(text)

        # send in chunks
        for chunk in split_message(answer):
            await update.message.reply_text(chunk)

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def send_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global temporary_prompt
    message_text = update.message.text

    if not message_text:
        await update.message.reply_text("Usage: /text <message>")
        return

    command = message_text.split()[0]
    text = message_text[len(command):].strip()

    if not text:
        await update.message.reply_text("Usage: /text <message>")
        return

    if text.startswith('```') and text.endswith('```'):
        text = text[3:-3].strip()

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
        temporary_prompt = None
        await update.message.reply_text("Prompt cleared.")
    else:
        await update.message.reply_text(f"Prompt set:\n{temporary_prompt}")


async def set_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global typing_speed
    try:
        speed = int(context.args[0])
        typing_speed = max(1, speed)
        await update.message.reply_text(f"Typing speed set to {typing_speed} chars/sec")
    except:
        await update.message.reply_text("Usage: /speed <number>")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global typing_speed, temporary_prompt
    typing_speed = 60
    temporary_prompt = None
    await update.message.reply_text("Typing speed reset to 60 and prompt cleared.")


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