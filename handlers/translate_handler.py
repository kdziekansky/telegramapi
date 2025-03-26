from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from utils.translations import get_text
from utils.openai_client import analyze_image, analyze_document
from database.credits_client import check_user_credits, deduct_user_credits, get_user_credits
from utils.user_utils import get_user_language
import re

async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Obsługa komendy /translate
    Instruuje użytkownika jak korzystać z funkcji tłumaczenia
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy komenda zawiera argumenty (tekst do tłumaczenia i docelowy język)
    if context.args and len(context.args) >= 2:
        # Format: /translate [język_docelowy] [tekst]
        # np. /translate en Witaj świecie!
        target_lang = context.args[0].lower()
        text_to_translate = ' '.join(context.args[1:])
        await translate_text(update, context, text_to_translate, target_lang)
        return
    
    # Sprawdź, czy wiadomość jest odpowiedzią na zdjęcie lub dokument
    if update.message.reply_to_message:
        # Obsługa odpowiedzi na wcześniejszą wiadomość
        replied_message = update.message.reply_to_message
        
        # Ustal docelowy język tłumaczenia z argumentów komendy
        target_lang = "en"  # Domyślnie angielski
        if context.args and len(context.args) > 0:
            target_lang = context.args[0].lower()
        
        if replied_message.photo:
            # Odpowiedź na zdjęcie - wykonaj tłumaczenie tekstu ze zdjęcia
            await translate_photo(update, context, replied_message.photo[-1], target_lang)
            return
        elif replied_message.document:
            # Odpowiedź na dokument - wykonaj tłumaczenie dokumentu
            await translate_document(update, context, replied_message.document, target_lang)
            return
        elif replied_message.text:
            # Odpowiedź na zwykłą wiadomość tekstową
            await translate_text(update, context, replied_message.text, target_lang)
            return
    
    # Jeśli nie ma odpowiedzi ani argumentów, wyświetl instrukcje
    instruction_text = get_text("translate_instruction", language)
    
    await update.message.reply_text(
        instruction_text,
        parse_mode=ParseMode.MARKDOWN
    )

async def translate_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, photo, target_lang="en"):
    """Tłumaczy tekst wykryty na zdjęciu"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik ma wystarczającą liczbę kredytów
    credit_cost = 8  # Koszt tłumaczenia zdjęcia
    if not check_user_credits(user_id, credit_cost):
        await update.message.reply_text(get_text("subscription_expired", language))
        return
    
    # Wyślij informację o rozpoczęciu tłumaczenia
    message = await update.message.reply_text(
        get_text("translating_image", language)
    )
    
    # Wyślij informację o aktywności bota
    await update.message.chat.send_action(action=ChatAction.TYPING)
    
    # Pobierz zdjęcie
    file = await context.bot.get_file(photo.file_id)
    file_bytes = await file.download_as_bytearray()
    
    # Tłumacz tekst ze zdjęcia w określonym kierunku
    result = await analyze_image(file_bytes, f"photo_{photo.file_unique_id}.jpg", mode="translate", target_language=target_lang)
    
    # Odejmij kredyty
    deduct_user_credits(user_id, credit_cost, get_text("photo_translation_operation", language, target_lang=target_lang, default=f"Tłumaczenie tekstu ze zdjęcia na język {target_lang}"))
    
    # Wyślij tłumaczenie
    await message.edit_text(
        f"*{get_text('translation_result', language)}*\n\n{result}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Sprawdź aktualny stan kredytów
    credits = get_user_credits(user_id)
    if credits < 5:
        await update.message.reply_text(
            f"{get_text('low_credits_warning', language)} {get_text('low_credits_message', language, credits=credits)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def translate_document(update: Update, context: ContextTypes.DEFAULT_TYPE, document, target_lang="en"):
    """Tłumaczy tekst z dokumentu"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik ma wystarczającą liczbę kredytów
    credit_cost = 8  # Koszt tłumaczenia dokumentu
    if not check_user_credits(user_id, credit_cost):
        await update.message.reply_text(get_text("subscription_expired", language))
        return
    
    file_name = document.file_name
    
    # Sprawdź rozmiar pliku (limit 25MB)
    if document.file_size > 25 * 1024 * 1024:
        await update.message.reply_text(get_text("file_too_large", language))
        return
    
    # Wyślij informację o rozpoczęciu tłumaczenia
    message = await update.message.reply_text(
        get_text("translating_document", language)
    )
    
    # Wyślij informację o aktywności bota
    await update.message.chat.send_action(action=ChatAction.TYPING)
    
    # Pobierz plik
    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()
    
    # Tłumacz dokument
    result = await analyze_document(file_bytes, file_name, mode="translate", target_language=target_lang)
    
    # Odejmij kredyty
    deduct_user_credits(user_id, credit_cost, get_text("document_translation_operation", language, file_name=file_name, target_lang=target_lang, default=f"Tłumaczenie dokumentu na język {target_lang}: {file_name}"))
    
    # Wyślij tłumaczenie
    await message.edit_text(
        f"*{get_text('translation_result', language)}*\n\n{result}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Sprawdź aktualny stan kredytów
    credits = get_user_credits(user_id)
    if credits < 5:
        await update.message.reply_text(
            f"{get_text('low_credits_warning', language)} {get_text('low_credits_message', language, credits=credits)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text, target_lang="en"):
    """Tłumaczy podany tekst na określony język"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik ma wystarczającą liczbę kredytów
    credit_cost = 3  # Koszt tłumaczenia tekstu
    if not check_user_credits(user_id, credit_cost):
        await update.message.reply_text(get_text("subscription_expired", language))
        return
    
    # Wyślij informację o rozpoczęciu tłumaczenia
    message = await update.message.reply_text(
        get_text("translating_text", language)
    )
    
    # Wyślij informację o aktywności bota
    await update.message.chat.send_action(action=ChatAction.TYPING)
    
    # Wykonaj tłumaczenie korzystając z API OpenAI
    from utils.openai_client import chat_completion
    
    # Uniwersalny prompt niezależny od języka
    system_prompt = f"You are a professional translator. Translate the following text to {target_lang}. Preserve formatting. Only return the translation."
    
    # Przygotuj wiadomości dla API
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    # Wykonaj tłumaczenie
    translation = await chat_completion(messages, model="gpt-3.5-turbo")
    
    # Odejmij kredyty
    deduct_user_credits(user_id, credit_cost, get_text("text_translation_operation", language, target_lang=target_lang, default=f"Tłumaczenie tekstu na język {target_lang}"))
    
    # Wyślij tłumaczenie
    source_lang_name = get_language_name(language)
    target_lang_name = get_language_name(target_lang)
    
    await message.edit_text(
        f"*{get_text('translation_result', language)}* ({source_lang_name} → {target_lang_name})\n\n{translation}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Sprawdź aktualny stan kredytów
    credits = get_user_credits(user_id)
    if credits < 5:
        await update.message.reply_text(
            f"{get_text('low_credits_warning', language)} {get_text('low_credits_message', language, credits=credits)}",
            parse_mode=ParseMode.MARKDOWN
        )

def get_language_name(lang_code):
    """Zwraca nazwę języka na podstawie kodu"""
    languages = {
        "pl": "Polski",
        "en": "English",
        "ru": "Русский",
        "fr": "Français",
        "de": "Deutsch",
        "es": "Español",
        "it": "Italiano",
        "zh": "中文",
        "ja": "日本語",
        "ko": "한국어",
        "ar": "العربية",
        "pt": "Português"
    }
    return languages.get(lang_code.lower(), lang_code)