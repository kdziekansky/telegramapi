import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database.supabase_client import create_license
from utils.translations import get_text
from utils.user_utils import get_user_language

# Lista ID administratorów bota - tutaj należy dodać swoje ID
from config import ADMIN_USER_IDS  # Zastąp swoim ID użytkownika Telegram

async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Pobiera informacje o użytkowniku
    Tylko dla administratorów
    Użycie: /userinfo [user_id]
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik jest administratorem
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text("no_permission", language, default="Nie masz uprawnień do tej komendy."))
        return
    
    # Sprawdź, czy podano ID użytkownika
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(get_text("userinfo_usage", language, default="Użycie: /userinfo [user_id]"))
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(get_text("userid_must_be_number", language, default="ID użytkownika musi być liczbą."))
        return
    
    # Pobierz informacje o użytkowniku
    from database.supabase_client import supabase
    
    response = supabase.table('users').select('*').eq('id', target_user_id).execute()
    
    if not response.data:
        await update.message.reply_text(get_text("user_not_exists", language, default="Użytkownik nie istnieje w bazie danych."))
        return
    
    user_data = response.data[0]
    
    # Formatuj dane
    subscription_end = user_data.get('subscription_end_date', get_text("no_subscription", language, default="Brak subskrypcji"))
    if subscription_end and subscription_end != get_text("no_subscription", language, default="Brak subskrypcji"):
        import datetime
        import pytz
        end_date = datetime.datetime.fromisoformat(subscription_end.replace('Z', '+00:00'))
        subscription_end = end_date.strftime('%d.%m.%Y %H:%M')
    
    info = f"""
*{get_text("user_information", language, default="Informacje o użytkowniku:")}*
ID: `{user_data['id']}`
{get_text("username", language, default="Nazwa użytkownika")}: {user_data.get('username', get_text("none", language, default="Brak"))}
{get_text("first_name", language, default="Imię")}: {user_data.get('first_name', get_text("none", language, default="Brak"))}
{get_text("last_name", language, default="Nazwisko")}: {user_data.get('last_name', get_text("none", language, default="Brak"))}
{get_text("language_code", language, default="Język")}: {user_data.get('language_code', get_text("none", language, default="Brak"))}
{get_text("subscription_until", language, default="Subskrypcja do")}: {subscription_end}
{get_text("active", language, default="Aktywny")}: {get_text("yes", language, default="Tak") if user_data.get('is_active', False) else get_text("no", language, default="Nie")}
{get_text("registration_date", language, default="Data rejestracji")}: {user_data.get('created_at', get_text("none", language, default="Brak"))}
    """
    
    await update.message.reply_text(info, parse_mode=ParseMode.MARKDOWN)

async def add_prompt_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dodaje nowy szablon prompta do bazy danych
    Tylko dla administratorów
    Użycie: /addtemplate [nazwa] [opis] [tekst prompta]
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik jest administratorem
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text("no_permission", language, default="Nie masz uprawnień do tej komendy."))
        return
    
    # Sprawdź, czy wiadomość jest odpowiedzią na inną wiadomość
    if not update.message.reply_to_message:
        await update.message.reply_text(
            get_text("addtemplate_reply_required", language, default="Ta komenda musi być odpowiedzią na wiadomość zawierającą prompt.") + "\n" +
            get_text("addtemplate_format", language, default="Format: /addtemplate [nazwa] [opis]") + "\n" +
            get_text("addtemplate_example", language, default="Przykład: /addtemplate \"Asystent kreatywny\" \"Pomaga w kreatywnym myśleniu\"")
        )
        return
    
    # Sprawdź, czy podano argumenty
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            get_text("addtemplate_usage", language, default="Użycie: /addtemplate [nazwa] [opis]") + "\n" +
            get_text("addtemplate_example", language, default="Przykład: /addtemplate \"Asystent kreatywny\" \"Pomaga w kreatywnym myśleniu\"")
        )
        return
    
    # Pobierz tekst prompta z odpowiedzi
    prompt_text = update.message.reply_to_message.text
    
    # Pobierz nazwę i opis
    # Obsługa nazwy i opisu w cudzysłowach
    text = update.message.text[len('/addtemplate '):]
    matches = re.findall(r'"([^"]*)"', text)
    
    if len(matches) < 2:
        await update.message.reply_text(
            get_text("addtemplate_format_error", language, default="Nieprawidłowy format. Nazwa i opis muszą być w cudzysłowach.") + "\n" +
            get_text("addtemplate_example", language, default="Przykład: /addtemplate \"Asystent kreatywny\" \"Pomaga w kreatywnym myśleniu\"")
        )
        return
    
    name = matches[0]
    description = matches[1]
    
    # Dodaj szablon do bazy danych
    from database.supabase_client import save_prompt_template
    
    template = save_prompt_template(name, description, prompt_text)
    
    if template:
        await update.message.reply_text(
            get_text("addtemplate_success", language, default="Dodano nowy szablon prompta:") + "\n" +
            f"*{get_text('name', language, default='Nazwa')}:* {name}\n" +
            f"*{get_text('description', language, default='Opis')}:* {description}",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(get_text("addtemplate_error", language, default="Wystąpił błąd podczas dodawania szablonu prompta."))