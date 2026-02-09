import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from pdf2image import convert_from_path

# Import existing logic from analects_tracing
from analects_tracing import Config, AnalectsTracingPDF, parse_text_input

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Constants
FONT_PATH = "fonts/NotoSerifCJKkr-Regular.otf"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text:
        return

    chat_id = update.effective_chat.id
    message_id = update.message.message_id
    status_message = await update.message.reply_text("PDF를 생성 중입니다. 잠시만 기다려주세요...")

    try:
        # 1. Parse input
        passages = parse_text_input(user_text)
        if not passages:
            await status_message.edit_text("입력된 텍스트에서 구절을 찾을 수 없습니다. 형식을 확인해주세요.")
            return

        # 2. Generate PDF (Using message_id for uniqueness)
        pdf_path = OUTPUT_DIR / f"analects_{chat_id}_{message_id}.pdf"
        config = Config()
        generator = AnalectsTracingPDF(config, FONT_PATH)
        generator.generate(passages, str(pdf_path))

        # 3. Convert first page to PNG
        png_path = OUTPUT_DIR / f"analects_{chat_id}_{message_id}.png"
        images = convert_from_path(str(pdf_path), first_page=1, last_page=1)
        if images:
            images[0].save(str(png_path), "PNG")

        # 4. Send files
        # Send PNG first for quick preview
        if png_path.exists():
            with open(png_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption="미리보기 (첫 페이지)")

        # Send PDF
        with open(pdf_path, 'rb') as pdf_file:
            await context.bot.send_document(chat_id=chat_id, document=pdf_file, filename=f"analects_{message_id}.pdf")

        await status_message.delete() # 상태 메시지 삭제

    except Exception as e:
        logging.error(f"Error processing message: {e}")
        await status_message.edit_text(f"처리 중 오류가 발생했습니다: {str(e)}")
    finally:
        # Clean up temporary files
        if 'pdf_path' in locals() and pdf_path.exists():
            pdf_path.unlink()
        if 'png_path' in locals() and png_path.exists():
            png_path.unlink()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "안녕하세요! 논어 필사 PDF 생성 봇입니다.\n"
        "텍스트를 보내주시면 필사 가이드 PDF와 미리보기 이미지를 만들어 드립니다.\n\n"
        "입력 예시:\n"
        "9.자한편\n"
        "29.子曰: \"歲寒, 然後知松栢之後彫也.\"\n"
        "(자왈: \"세한, 연후지송백지후조야.\")\n\n"
        "공자께서 말씀하셨다. \"날씨가 추워진 뒤에야...\""
    )
    await update.message.reply_text(help_text)

if __name__ == '__main__':
    if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("오류: .env 파일에 TELEGRAM_BOT_TOKEN을 설정해주세요.")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        
        # Handlers
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(MessageHandler(filters.COMMAND, start))
        
        print("봇이 시작되었습니다...")
        app.run_polling()