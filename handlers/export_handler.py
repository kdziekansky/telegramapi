# handlers/export_handler.py
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from database.supabase_client import get_active_conversation, get_conversation_history, get_or_create_user
from utils.pdf_generator import generate_conversation_pdf
from config import BOT_NAME
from utils.translations import get_text
from handlers.menu_handler import get_user_language
import io

async def export_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksportuje aktualną konwersację użytkownika do PDF"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    status_message = await update.message.reply_text(
        get_text("export_generating", language)
    )
    
    await update.message.chat.send_action(action=ChatAction.UPLOAD_DOCUMENT)
    
    try:
        # Dodane await
        conversation = await get_active_conversation(user_id)
        
        if not conversation:
            await status_message.edit_text(get_text("conversation_error", language))
            return
        
        # Dodane await
        history = await get_conversation_history(conversation['id'])
        
        if not history:
            await status_message.edit_text(get_text("export_empty", language))
            return
        
        # Naprawiony sposób pobrania danych użytkownika
        # Zamiast get_or_create_user użyjemy bezpośrednio Supabase
        user_info = {}
        try:
            from database.supabase_client import supabase
            response = supabase.table('users').select('*').eq('id', user_id).execute()
            if response.data:
                user_info = response.data[0]
        except Exception as e:
            print(f"Błąd pobierania danych użytkownika: {e}")
        
        # Generuj PDF
        pdf_buffer = generate_conversation_pdf(history, user_info, BOT_NAME)
        
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        file_name = f"Konwersacja_{BOT_NAME}_{current_date}.pdf"
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=file_name,
            caption=get_text("export_file_caption", language)
        )
        
        await status_message.delete()
        
    except Exception as e:
        print(f"Błąd podczas generowania PDF: {e}")
        import traceback
        traceback.print_exc()
        await status_message.edit_text(
            get_text("export_error", language)
        )