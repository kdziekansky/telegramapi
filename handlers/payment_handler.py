from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.menu import update_menu, store_menu_state  # Poprawione importy
from telegram.constants import ParseMode
from database.credits_client import (
    get_user_credits, get_credit_packages
)
from database.payment_client import (
    get_available_payment_methods, create_payment_url, 
    get_user_subscriptions, cancel_subscription,
    get_payment_transactions
)
from utils.user_utils import get_user_language
from utils.translations import get_text
import logging

logger = logging.getLogger(__name__)

async def payment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Obsługuje komendę /payment
    Wyświetla opcje płatności dla użytkownika
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Pobierz dostępne metody płatności
    payment_methods = get_available_payment_methods(language)
    
    if not payment_methods:
        await update.message.reply_text(
            get_text("payment_methods_unavailable", language)
        )
        return
    
    # Utwórz przyciski dla każdej metody płatności
    keyboard = []
    for method in payment_methods:
        keyboard.append([
            InlineKeyboardButton(
                method["name"], 
                callback_data=f"payment_method_{method['code']}"
            )
        ])
    
    # Dodaj przycisk powrotu
    keyboard.append([
        InlineKeyboardButton(
            get_text("back", language), 
            callback_data="menu_section_credits"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        get_text("select_payment_method", language),
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Obsługuje komendę /subscription
    Wyświetla aktywne subskrypcje użytkownika
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Pobierz aktywne subskrypcje
    subscriptions = get_user_subscriptions(user_id)
    
    if not subscriptions:
        await update.message.reply_text(
            get_text("no_active_subscriptions", language)
        )
        return
    
    # Utwórz listę aktywnych subskrypcji
    message = get_text("active_subscriptions", language)
    
    # Pobierz dane pakietów
    packages = {p['id']: p for p in get_credit_packages()}
    
    # Dodaj informacje o każdej subskrypcji
    for i, sub in enumerate(subscriptions, 1):
        package_id = sub['credit_package_id']
        package_name = packages.get(package_id, {}).get('name', get_text("unknown_package", language, default='Nieznany pakiet'))
        package_credits = packages.get(package_id, {}).get('credits', 0)
        next_billing = sub['next_billing_date'].split('T')[0] if sub['next_billing_date'] else get_text("unknown_date", language, default='Nieznana')
        
        message += f"{i}. *{package_name}* - {package_credits} {get_text('credits_monthly', language)}\n"
        message += f"   {get_text('next_renewal', language, default='Następne odnowienie')}: {next_billing}\n\n"
    
    # Dodaj przyciski do zarządzania subskrypcjami
    keyboard = []
    for i, sub in enumerate(subscriptions, 1):
        keyboard.append([
            InlineKeyboardButton(
                get_text("cancel_subscription", language) + f" #{i}",
                callback_data=f"cancel_subscription_{sub['id']}"
            )
        ])
    
    # Dodaj przycisk powrotu
    keyboard.append([
        InlineKeyboardButton(
            get_text("back", language), 
            callback_data="payment_back_to_credits"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Obsługuje callbacki związane z płatnościami
    """
    query = update.callback_query
    user_id = query.from_user.id
    language = get_user_language(context, user_id)
    
    await query.answer()
    
    print(f"Payment callback received: {query.data}")  # Debugging
    
    # Obsługa przycisku powrotu do menu głównego
    if query.data == "menu_back_main":
        from handlers.menu_handler import handle_back_to_main
        return await handle_back_to_main(update, context)
    
    # Obsługa przycisku powrotu do menu kredytów
    if query.data in ["payment_back_to_credits", "menu_section_credits"]:
        print("Returning to credits menu")  # Debugging
        try:
            # Stwórz klawiaturę menu kredytów
            keyboard = [
                [InlineKeyboardButton(get_text("buy_credits_btn", language), callback_data="menu_credits_buy")],
                [
                    InlineKeyboardButton(get_text("payment_methods", language), callback_data="payment_command"),
                    InlineKeyboardButton(get_text("subscription_manage", language), callback_data="subscription_command")
                ],
                [InlineKeyboardButton(get_text("transaction_history", language, default="Historia transakcji"), callback_data="transactions_command")],
                [InlineKeyboardButton(get_text("back", language), callback_data="menu_back_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Pobierz aktualny stan kredytów
            credits = get_user_credits(user_id)
            
            message = f"*{get_text('credit_status', language, default='Stan kredytów')}*\n\n"
            message += f"{get_text('available_credits', language)}: *{credits}*\n\n"
            message += f"*{get_text('operation_costs', language)}:*\n"
            message += f"▪️ {get_text('standard_message', language)} (GPT-3.5): 1 {get_text('credit', language)}\n"
            message += f"▪️ {get_text('premium_message', language)} (GPT-4o): 3 {get_text('credits', language)}\n"
            message += f"▪️ {get_text('expert_message', language)} (GPT-4): 5 {get_text('credits', language)}\n"
            message += f"▪️ {get_text('dalle_image', language)}: 10-15 {get_text('credits', language)}\n"
            message += f"▪️ {get_text('document_analysis', language)}: 5 {get_text('credits', language)}\n"
            message += f"▪️ {get_text('photo_analysis', language)}: 8 {get_text('credits', language)}\n\n"
            
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                message,
                reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Zapisz stan menu
            store_menu_state(context, user_id, 'credits')
            
            return True
        except Exception as e:
            print(f"{get_text('credits_menu_error', language, default='Error returning to credits menu')}: {e}")
            # Próbuj wysłać nową wiadomość
            try:
                message = f"{get_text('credit_status_short', language, default='Stan kredytów')}: {credits}\n\n{get_text('buy_options', language, default='Zobacz opcje zakupu kredytów poniżej:')}"
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=message,
                    reply_markup=reply_markup
                )
                return True
            except Exception as e2:
                print(f"{get_text('second_error', language, default='Second error')}: {e2}")
    
    # Obsługa starego formatu buy_package bez metody płatności
    if query.data.startswith("buy_package_") and "_" in query.data and len(query.data.split("_")) == 3:
        # Przekieruj do nowego interfejsu płatności
        await query.answer(get_text("redirecting_to_payment", language, default="Przekierowuję do nowego interfejsu płatności..."))
        
        # Stwórz sztuczny obiekt update
        fake_update = type('obj', (object,), {
            'effective_user': query.from_user,
            'message': query.message,
            'effective_chat': query.message.chat
        })
        
        # Usuń oryginalną wiadomość
        await query.message.delete()
        
        # Wywołaj nowy interfejs zakupów
        from handlers.credit_handler import buy_command
        await buy_command(fake_update, context)
        return True

    # Obsługa menu głównego
    if query.data == "menu_section_credits":
        from handlers.menu_handler import handle_credits_section
        
        # Wywołaj z odpowiednią ścieżką nawigacji
        language = get_user_language(context, user_id)
        nav_path = get_text("main_menu", language) + " > " + get_text("menu_credits", language)
        return await handle_credits_section(update, context, nav_path)
    
    # Obsługa komendy płatności
    if query.data == "payment_command":
        # Pobierz dostępne metody płatności
        payment_methods = get_available_payment_methods(language)
        
        if not payment_methods:
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("payment_methods_unavailable", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data="payment_back_to_credits")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        
        # Utwórz przyciski dla każdej metody płatności
        keyboard = []
        for method in payment_methods:
            keyboard.append([
                InlineKeyboardButton(
                    method["name"], 
                    callback_data=f"payment_method_{method['code']}"
                )
            ])
        
        # Dodaj przycisk powrotu
        keyboard.append([
            InlineKeyboardButton(
                get_text("back", language), 
                callback_data="payment_back_to_credits"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Użycie centralnego systemu menu
        await update_menu(
            query,
            get_text("select_payment_method", language),
            reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Zapisz stan menu
        store_menu_state(context, user_id, 'payment_methods')
        
        return True
    
    # Obsługa wyboru metody płatności
    if query.data.startswith("payment_method_"):
        payment_method_code = query.data[15:]  # Usunięcie prefiksu "payment_method_"
        
        # Sprawdź czy to subskrypcja
        is_subscription = payment_method_code == "stripe_subscription"
        
        # Pobierz pakiety kredytów
        packages = await get_credit_packages()
        if not packages:
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("packages_unavailable", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data="payment_command")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        
        # Utwórz przyciski dla każdego pakietu
        keyboard = []
        for package in packages:
            # Dostosuj tekst przycisku w zależności od tego, czy to subskrypcja
            if is_subscription:
                button_text = f"{package['name']} - {package['credits']} {get_text('credits_monthly', language)} ({package['price']} PLN/{get_text('month_short', language, default='mies.')})"
            else:
                button_text = f"{package['name']} - {package['credits']} {get_text('credits', language)} ({package['price']} PLN)"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"buy_package_{payment_method_code}_{package['id']}"
                )
            ])
        
        # Dodaj przycisk powrotu
        keyboard.append([
            InlineKeyboardButton(
                get_text("back", language),
                callback_data="payment_command"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Dostosuj tekst wiadomości w zależności od metody płatności
        if payment_method_code in ["allegro", "russia_payment"]:
            message = get_text(f"payment_info_{payment_method_code}", language)
        elif is_subscription:
            message = get_text("payment_subscription_info", language)
        else:
            message = get_text("payment_package_selection", language)
        
        # Użycie centralnego systemu menu
        await update_menu(
            query,
            message,
            reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Zapisz stan menu
        store_menu_state(context, user_id, f'payment_method_{payment_method_code}')
        
        return True
    
    # Obsługa wyboru pakietu z określoną metodą płatności
    elif query.data.startswith("buy_package_"):
        parts = query.data.split("_")
        if len(parts) >= 5 and parts[3] == "subscription":
            payment_method_code = parts[2] + "_" + parts[3]  # "stripe_subscription"
            package_id = int(parts[4])  # teraz bierze "2"
        else:
            payment_method_code = parts[2]
            package_id = int(parts[3])
            
        # Sprawdź czy to jest subskrypcja
        is_subscription = payment_method_code == "stripe_subscription"
        
        # Utwórz URL płatności
        success, payment_url = create_payment_url(
            user_id, package_id, payment_method_code, is_subscription
        )
        
        if success and payment_url:
            # Utwórz przycisk do przejścia do płatności
            keyboard = [[
                InlineKeyboardButton(
                    get_text("proceed_to_payment", language),
                    url=payment_url
                )
            ]]
            
            # Dodaj przycisk powrotu
            keyboard.append([
                InlineKeyboardButton(
                    get_text("back", language),
                    callback_data=f"payment_method_{payment_method_code}"
                )
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Dostosuj wiadomość w zależności od metody płatności
            if payment_method_code in ["allegro", "russia_payment"]:
                message = get_text(f"external_payment_instructions_{payment_method_code}", language)
            elif is_subscription:
                message = get_text("subscription_payment_instructions", language)
            else:
                message = get_text("payment_instructions", language)
            
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                message,
                reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Zapisz stan menu
            store_menu_state(context, user_id, f'payment_url_{payment_method_code}_{package_id}')
            
        else:
            # Wyświetl błąd, jeśli nie udało się utworzyć URL płatności
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("payment_creation_error", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data=f"payment_method_{payment_method_code}")]]),
                parse_mode=ParseMode.MARKDOWN
            )
        return True
    
    # Obsługa komendy subskrypcji
    elif query.data == "subscription_command":
        # Pobierz aktywne subskrypcje
        subscriptions = get_user_subscriptions(user_id)
        
        if not subscriptions:
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("no_active_subscriptions", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data="payment_back_to_credits")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        
        # Utwórz listę aktywnych subskrypcji
        message = get_text("active_subscriptions", language)
        
        # Pobierz dane pakietów
        packages = {p['id']: p for p in get_credit_packages()}
        
        # Dodaj informacje o każdej subskrypcji
        for i, sub in enumerate(subscriptions, 1):
            package_id = sub['credit_package_id']
            package_name = packages.get(package_id, {}).get('name', get_text("unknown_package", language, default='Nieznany pakiet'))
            package_credits = packages.get(package_id, {}).get('credits', 0)
            next_billing = sub['next_billing_date'].split('T')[0] if sub['next_billing_date'] else get_text("unknown_date", language, default='Nieznana')
            
            message += f"{i}. *{package_name}* - {package_credits} {get_text('credits_monthly', language)}\n"
            message += f"   {get_text('next_renewal', language, default='Następne odnowienie')}: {next_billing}\n\n"
        
        # Dodaj przyciski do zarządzania subskrypcjami
        keyboard = []
        for i, sub in enumerate(subscriptions, 1):
            keyboard.append([
                InlineKeyboardButton(
                    get_text("cancel_subscription", language) + f" #{i}",
                    callback_data=f"cancel_subscription_{sub['id']}"
                )
            ])
        
        # Dodaj przycisk powrotu
        keyboard.append([
            InlineKeyboardButton(
                get_text("back", language), 
                callback_data="payment_back_to_credits"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Użycie centralnego systemu menu
        await update_menu(
            query,
            message,
            reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Zapisz stan menu
        store_menu_state(context, user_id, 'subscriptions')
        
        return True
    
    # Obsługa anulowania subskrypcji
    elif query.data.startswith("cancel_subscription_"):
        subscription_id = int(query.data.split("_")[2])
        
        # Potwierdzenie anulowania
        keyboard = [
            [
                InlineKeyboardButton(
                    get_text("yes", language),
                    callback_data=f"confirm_cancel_sub_{subscription_id}"
                ),
                InlineKeyboardButton(
                    get_text("no", language),
                    callback_data="subscription_command"
                )
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Użycie centralnego systemu menu
        await update_menu(
            query,
            get_text("cancel_subscription_confirm", language),
            reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Zapisz stan menu
        store_menu_state(context, user_id, f'cancel_subscription_{subscription_id}')
        
        return True
    
    # Obsługa potwierdzenia anulowania subskrypcji
    elif query.data.startswith("confirm_cancel_sub_"):
        subscription_id = int(query.data.split("_")[3])
        
        # Anuluj subskrypcję
        success = cancel_subscription(subscription_id)
        
        if success:
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("subscription_cancelled", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data="subscription_command")]]),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("subscription_cancel_error", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data="subscription_command")]]),
                parse_mode=ParseMode.MARKDOWN
            )
        return True
        
    # Obsługa transakcji
    elif query.data == "transactions_command":
        # Pobierz historię transakcji
        transactions = get_payment_transactions(user_id)
        
        if not transactions:
            # Użycie centralnego systemu menu
            await update_menu(
                query,
                get_text("no_payment_transactions", language),
                InlineKeyboardMarkup([[InlineKeyboardButton(get_text("back", language), callback_data="payment_back_to_credits")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        
        # Utwórz wiadomość z historią transakcji
        message = get_text("payment_transactions_history", language)
        
        for i, transaction in enumerate(transactions, 1):
            status_text = get_text(f"transaction_status_{transaction['status']}", language, default=transaction['status'])
            
            date = transaction['created_at'].split('T')[0] if 'T' in transaction['created_at'] else transaction['created_at']
            
            message += f"{i}. *{transaction['package_name']}* - {transaction['package_credits']} {get_text('credits', language)}\n"
            message += f"   {transaction['payment_method_name']} - {transaction['amount']} PLN\n"
            message += f"   {get_text('status', language)}: {status_text}, {get_text('date', language)}: {date}\n\n"
        
        # Dodaj przycisk powrotu
        keyboard = [[
            InlineKeyboardButton(
                get_text("back", language), 
                callback_data="payment_back_to_credits"
            )
        ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Użycie centralnego systemu menu
        await update_menu(
            query,
            message,
            reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Zapisz stan menu
        store_menu_state(context, user_id, 'transactions')
        
        return True
    
    return False  # Jeśli callback nie został obsłużony

async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Obsługuje komendę /transactions
    Wyświetla historię transakcji płatności
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Pobierz historię transakcji
    transactions = get_payment_transactions(user_id)
    
    if not transactions:
        await update.message.reply_text(
            get_text("no_payment_transactions", language)
        )
        return
    
    # Utwórz wiadomość z historią transakcji
    message = get_text("payment_transactions_history", language)
    
    for i, transaction in enumerate(transactions, 1):
        status_text = get_text(f"transaction_status_{transaction['status']}", language, default=transaction['status'])
        
        date = transaction['created_at'].split('T')[0]
        
        message += f"{i}. *{transaction['package_name']}* - {transaction['package_credits']} {get_text('credits', language)}\n"
        message += f"   {transaction['payment_method_name']} - {transaction['amount']} PLN\n"
        message += f"   {get_text('status', language)}: {status_text}, {get_text('date', language)}: {date}\n\n"
    
    # Dodaj przycisk powrotu
    keyboard = [[
        InlineKeyboardButton(
            get_text("back", language), 
            callback_data="payment_back_to_credits"
        )
    ]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )