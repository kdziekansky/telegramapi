import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ADMIN_USER_IDS, CREDIT_PACKAGES
from utils.translations import get_text
from utils.user_utils import get_user_language

async def add_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dodaje lub aktualizuje pakiet kredytów
    Tylko dla administratorów
    Użycie: /addpackage [id] [nazwa] [kredyty] [cena]
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik jest administratorem
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text("no_permission", language, default="Nie masz uprawnień do tej komendy."))
        return
    
    # Sprawdź, czy podano argumenty
    if not context.args or len(context.args) < 4:
        await update.message.reply_text(
            get_text("addpackage_usage", language, default="Użycie: /addpackage [id] [nazwa] [kredyty] [cena]") + "\n" +
            get_text("addpackage_example", language, default="Przykład: /addpackage 1 \"Starter\" 100 4.99")
        )
        return
    
    try:
        # Parsowanie argumentów
        package_id = int(context.args[0])
        
        # Obsługa nazwy w cudzysłowach
        text = ' '.join(context.args[1:])
        name_match = re.search(r'"([^"]*)"', text)
        
        if not name_match:
            await update.message.reply_text(
                get_text("addpackage_name_quotes", language, default="Nazwa musi być w cudzysłowach.") + "\n" +
                get_text("addpackage_example", language, default="Przykład: /addpackage 1 \"Starter\" 100 4.99")
            )
            return
        
        name = name_match.group(1)
        
        # Pozostałe argumenty
        remaining_text = text[text.find('"', text.find(name) + len(name)) + 1:].strip()
        remaining_args = remaining_text.split()
        
        if len(remaining_args) < 2:
            await update.message.reply_text(
                get_text("addpackage_invalid_args", language, default="Nieprawidłowa liczba argumentów.") + "\n" +
                get_text("addpackage_example", language, default="Przykład: /addpackage 1 \"Starter\" 100 4.99")
            )
            return
        
        credits = int(remaining_args[0])
        price = float(remaining_args[1])
        
        # Dodaj lub aktualizuj pakiet w bazie
        from database.supabase_client import supabase
        
        # Sprawdź czy pakiet już istnieje
        response = supabase.table('credit_packages').select('*').eq('id', package_id).execute()
        
        if response.data:
            # Aktualizuj istniejący pakiet
            response = supabase.table('credit_packages').update({
                'name': name,
                'credits': credits,
                'price': price,
                'is_active': True
            }).eq('id', package_id).execute()
            message = get_text("package_updated", language, name=name, default=f"✅ Zaktualizowano pakiet: *{name}*")
        else:
            # Dodaj nowy pakiet
            response = supabase.table('credit_packages').insert({
                'id': package_id,
                'name': name,
                'credits': credits,
                'price': price,
                'is_active': True
            }).execute()
            message = get_text("package_added", language, name=name, default=f"✅ Dodano nowy pakiet: *{name}*")
        
        # Potwierdź operację
        await update.message.reply_text(
            f"{message}\n\n" +
            f"ID: *{package_id}*\n" +
            f"{get_text('name', language, default='Nazwa')}: *{name}*\n" +
            f"{get_text('credits', language, default='Kredyty')}: *{credits}*\n" +
            f"{get_text('price', language, default='Cena')}: *{price}* PLN",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(get_text("package_error", language, error=str(e), default=f"❌ Wystąpił błąd: {str(e)}"))

async def list_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Wyświetla listę pakietów kredytów
    Tylko dla administratorów
    Użycie: /listpackages
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik jest administratorem
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text("no_permission", language, default="Nie masz uprawnień do tej komendy."))
        return
    
    try:
        # Pobierz pakiety z bazy
        from database.supabase_client import supabase
        response = supabase.table('credit_packages').select('*').order('id', desc=False).execute()
        
        if not response.data:
            await update.message.reply_text(
                get_text("no_packages", language, default="Brak pakietów kredytów w bazie danych.") + "\n\n" +
                get_text("add_packages_command", language, default="Możesz dodać pakiety komendą:") + "\n" +
                "/addpackage [id] [nazwa] [kredyty] [cena]"
            )
            return
        
        # Stwórz wiadomość z listą pakietów
        message = f"*{get_text('packages_list', language, default='📦 Lista pakietów kredytów:')}*\n\n"
        
        for package in response.data:
            active_status = get_text("active_status", language, default="✅ Aktywny") if package.get('is_active', False) else get_text("inactive_status", language, default="❌ Nieaktywny")
            message += f"*{package['id']}.* {package['name']}\n"
            message += f"   {get_text('credits', language, default='Kredyty')}: *{package['credits']}*\n"
            message += f"   {get_text('price', language, default='Cena')}: *{package['price']}* PLN\n"
            message += f"   {get_text('status', language, default='Status')}: {active_status}\n\n"
        
        # Dodaj informacje o zarządzaniu
        message += f"*{get_text('package_management', language, default='Zarządzanie pakietami:')}*\n"
        message += "/addpackage [id] [nazwa] [kredyty] [cena] - " + get_text("add_update_package", language, default="Dodaje/aktualizuje pakiet") + "\n"
        message += "/togglepackage [id] - " + get_text("toggle_package", language, default="Włącza/wyłącza aktywność pakietu")
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        await update.message.reply_text(get_text("list_packages_error", language, error=str(e), default=f"❌ Wystąpił błąd: {str(e)}"))

async def toggle_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Włącza/wyłącza aktywność pakietu kredytów
    Tylko dla administratorów
    Użycie: /togglepackage [id]
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik jest administratorem
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text("no_permission", language, default="Nie masz uprawnień do tej komendy."))
        return
    
    # Sprawdź, czy podano ID pakietu
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(get_text("togglepackage_usage", language, default="Użycie: /togglepackage [id]"))
        return
    
    try:
        package_id = int(context.args[0])
        
        # Pobierz pakiet z bazy
        from database.supabase_client import supabase
        response = supabase.table('credit_packages').select('*').eq('id', package_id).execute()
        
        if not response.data:
            await update.message.reply_text(get_text("package_not_exists", language, package_id=package_id, default=f"❌ Pakiet o ID {package_id} nie istnieje."))
            return
        
        package = response.data[0]
        new_status = not package.get('is_active', False)
        
        # Aktualizuj status pakietu
        supabase.table('credit_packages').update({
            'is_active': new_status
        }).eq('id', package_id).execute()
        
        status_text = get_text("status_active", language, default="aktywny") if new_status else get_text("status_inactive", language, default="nieaktywny")
        await update.message.reply_text(
            get_text("package_status_changed", language, package_name=package['name'], status=status_text, default=f"✅ Status pakietu *{package['name']}* zmieniony na: *{status_text}*"),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(get_text("toggle_package_error", language, error=str(e), default=f"❌ Wystąpił błąd: {str(e)}"))

async def add_default_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dodaje domyślne pakiety kredytów z config.py
    Tylko dla administratorów
    Użycie: /adddefaultpackages
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik jest administratorem
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text(get_text("no_permission", language, default="Nie masz uprawnień do tej komendy."))
        return
    
    try:
        # Pobierz pakiety z config.py
        packages = CREDIT_PACKAGES
        
        # Dodaj każdy pakiet do bazy danych
        from database.supabase_client import supabase
        added_count = 0
        updated_count = 0
        
        for package in packages:
            # Sprawdź czy pakiet już istnieje
            response = supabase.table('credit_packages').select('*').eq('id', package['id']).execute()
            
            if response.data:
                # Aktualizuj istniejący pakiet
                supabase.table('credit_packages').update({
                    'name': package['name'],
                    'credits': package['credits'],
                    'price': package['price'],
                    'is_active': True
                }).eq('id', package['id']).execute()
                updated_count += 1
            else:
                # Dodaj nowy pakiet
                supabase.table('credit_packages').insert({
                    'id': package['id'],
                    'name': package['name'],
                    'credits': package['credits'],
                    'price': package['price'],
                    'is_active': True
                }).execute()
                added_count += 1
        
        await update.message.reply_text(
            get_text("default_packages_added", language, added=added_count, updated=updated_count, 
                     default=f"✅ Dodawanie domyślnych pakietów zakończone.\n\n"
                            f"Dodano nowych pakietów: *{added_count}*\n"
                            f"Zaktualizowano istniejących pakietów: *{updated_count}*"),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await update.message.reply_text(get_text("default_packages_error", language, error=str(e), default=f"❌ Wystąpił błąd: {str(e)}"))