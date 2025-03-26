from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils.ui_elements import credit_status_bar, info_card, section_divider, feature_badge, progress_bar
from utils.message_formatter_enhanced import format_credit_info, format_transaction_report
from utils.visual_styles import style_message, create_header, create_section, create_status_indicator
from utils.tips import get_random_tip, should_show_tip
from utils.credit_warnings import get_low_credits_notification, get_credit_recommendation
from config import BOT_NAME
from utils.user_utils import get_user_language
from utils.translations import get_text
from database.credits_client import (
    get_user_credits, add_user_credits, deduct_user_credits, 
    get_credit_packages, get_package_by_id, purchase_credits,
    get_user_credit_stats, 
)
from utils.credit_analytics import (
    generate_credit_usage_chart, generate_usage_breakdown_chart, 
    get_credit_usage_breakdown, predict_credit_depletion
)
import matplotlib
matplotlib.use('Agg')

from database.credits_client import add_stars_payment_option, get_stars_conversion_rate

async def credits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /credits command with enhanced visual presentation"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    credits = get_user_credits(user_id)
    message = f"*{get_text('credit_status_title', language, default='Stan kredytów')}*\n\n"
    message += f"{get_text('available_credits', language, default='Dostępne kredyty')}: *{credits}*\n\n"
    
    try:
        from database.credits_client import get_user_credit_stats
        stats = get_user_credit_stats(user_id)
        
        if stats:
            message += f"*Statystyki:*\n"
            message += f"▪️ Łącznie zakupiono: {stats.get('total_purchased', 0)} kredytów\n"
            message += f"▪️ Średnie dzienne zużycie: {int(stats.get('avg_daily_usage', 0))} kredytów\n"
            
            if stats.get('most_expensive_operation'):
                message += f"▪️ Najdroższa operacja: {stats.get('most_expensive_operation')}\n"
    except Exception as e:
        print(f"Błąd przy pobieraniu statystyk: {e}")
    
    message += f"\n*Koszty operacji:*\n"
    message += f"▪️ Wiadomość standardowa (GPT-3.5): 1 kredyt\n"
    message += f"▪️ Wiadomość premium (GPT-4o): 3 kredyty\n"
    message += f"▪️ Wiadomość ekspercka (GPT-4): 5 kredytów\n"
    message += f"▪️ Generowanie obrazu: 10-15 kredytów\n"
    message += f"▪️ Analiza dokumentu: 5 kredytów\n"
    message += f"▪️ Analiza zdjęcia: 8 kredytów\n\n"
    
    keyboard = [
        [InlineKeyboardButton("💳 Kup kredyty", callback_data="menu_credits_buy")],
        [
            InlineKeyboardButton("💰 Metody płatności", callback_data="payment_command"),
            InlineKeyboardButton("🔄 Subskrypcje", callback_data="subscription_command")
        ],
        [InlineKeyboardButton("📜 Historia transakcji", callback_data="transactions_command")],
        [InlineKeyboardButton("⬅️ Powrót", callback_data="menu_back_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Błąd przy wysyłaniu wiadomości z kredytami: {e}")
        await update.message.reply_text(
            message.replace("*", ""),
            reply_markup=reply_markup
        )

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /buy command with enhanced visual presentation"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    message = create_header("Zakup kredytów", "credits")
    
    message += (
        "Wybierz jedną z dostępnych metod płatności, aby kupić pakiet kredytów. "
        "Kredyty są używane do wszystkich operacji w bocie, takich jak:\n\n"
        "▪️ Rozmowy z różnymi modelami AI\n"
        "▪️ Generowanie obrazów\n"
        "▪️ Analizowanie dokumentów i zdjęć\n"
        "▪️ Tłumaczenie tekstów\n\n"
        "Dostępne są różne metody płatności."
    )
    
    message += "\n\n" + create_section("Korzyści z subskrypcji", 
        "▪️ Automatyczne odnowienie kredytów co miesiąc\n"
        "▪️ Niższy koszt kredytów\n"
        "▪️ Priorytetowa obsługa\n"
        "▪️ Dodatkowe funkcje premium")
    
    keyboard = [
        [
            InlineKeyboardButton("💳 " + get_text("one_time_packages", language, default="Pakiety jednorazowe"), callback_data="payment_method_stripe"),
            InlineKeyboardButton("🔄 " + get_text("subscription", language, default="Subskrypcja"), callback_data="payment_method_stripe_subscription")
        ],
        [
            InlineKeyboardButton("⬅️ " + get_text("back", language, default="Powrót"), callback_data="menu_back_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def handle_credit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługuje callbacki związane z kredytami"""
    query = update.callback_query
    user_id = query.from_user.id
    language = get_user_language(context, user_id)
    
    await query.answer()
    
    if query.data == "credits_check" or query.data == "menu_credits_check":
        credits = get_user_credits(user_id)
        credit_stats = get_user_credit_stats(user_id)
        
        message = f"""
*{get_text('credits_management', language)}*

{get_text('current_balance', language)}: *{credits}* {get_text('credits', language)}

{get_text('total_purchased', language)}: *{credit_stats.get('total_purchased', 0)}* {get_text('credits', language)}
{get_text('total_spent', language)}: *{credit_stats.get('total_spent', 0):.2f}* PLN
{get_text('last_purchase', language)}: *{credit_stats.get('last_purchase', get_text('no_transactions', language))}*

*{get_text('credit_history', language)} ({get_text('last_10', language, default='last 10')}):*
"""
        
        if credit_stats.get('usage_history'):
            for i, transaction in enumerate(credit_stats['usage_history'], 1):
                date = transaction['date'].split('T')[0]
                if transaction['type'] in ["add", "purchase", "subscription", "subscription_renewal"]:
                    message += f"\n{i}. ➕ +{transaction['amount']} {get_text('credits', language)} ({date})"
                else:
                    message += f"\n{i}. ➖ -{transaction['amount']} {get_text('credits', language)} ({date})"
                if transaction.get('description'):
                    message += f" - {transaction['description']}"
        else:
            message += f"\n{get_text('no_transactions', language)}"
        
        keyboard = [
            [InlineKeyboardButton(get_text("buy_more_credits", language), callback_data="menu_credits_buy")],
            [InlineKeyboardButton(get_text("back", language), callback_data="menu_section_credits")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if hasattr(query.message, 'caption'):
                await query.edit_message_caption(
                    caption=message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            print(f"Error updating message: {e}")
            try:
                plain_message = message.replace("*", "")
                if hasattr(query.message, 'caption'):
                    await query.edit_message_caption(
                        caption=plain_message,
                        reply_markup=reply_markup
                    )
                else:
                    await query.edit_message_text(
                        text=plain_message,
                        reply_markup=reply_markup
                    )
            except Exception as e2:
                print(f"Second error updating message: {e2}")
        return True
    
    if query.data == "credits_buy" or query.data == "menu_credits_buy" or query.data == "Kup":
        try:
            from handlers.credit_handler import buy_command
            
            fake_update = type('obj', (object,), {
                'effective_user': query.from_user,
                'message': query.message,
                'effective_chat': query.message.chat
            })
            
            await query.message.delete()
            
            await buy_command(fake_update, context)
            return True
            
        except Exception as e:
            print(f"Błąd przy przekierowaniu do zakupu kredytów: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                keyboard = [[InlineKeyboardButton("⬅️ Menu główne", callback_data="menu_back_main")]]
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="Wystąpił błąd. Spróbuj użyć komendy /buy",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e2:
                print(f"Błąd przy wyświetlaniu komunikatu: {e2}")
            return True
    
    if query.data == "credits_stats" or query.data == "credit_advanced_analytics":
        user_id = query.from_user.id
        language = get_user_language(context, user_id)
        
        if hasattr(query.message, 'caption'):
            await query.edit_message_caption(
                caption="⏳ Analyzing credit usage data..."
            )
        else:
            await query.edit_message_text(
                text="⏳ Analyzing credit usage data..."
            )
        
        days = 30
        
        depletion_info = predict_credit_depletion(user_id, days)
        
        if not depletion_info:
            if hasattr(query.message, 'caption'):
                await query.edit_message_caption(
                    caption="You don't have enough credit usage history to perform analysis. Try again after performing several operations."
                )
            else:
                await query.edit_message_text(
                    text="You don't have enough credit usage history to perform analysis. Try again after performing several operations."
                )
            return True
        
        message = f"📊 *{get_text('credit_analytics', language, default='Analiza wykorzystania kredytów')}*\n\n"
        message += f"{get_text('current_balance', language)}: *{depletion_info['current_balance']}* {get_text('credits', language)}\n"
        message += f"{get_text('average_daily_usage', language, default='Średnie dzienne zużycie')}: *{depletion_info['average_daily_usage']}* {get_text('credits', language)}\n"
        
        if depletion_info['days_left']:
            message += f"{get_text('predicted_depletion', language, default='Przewidywane wyczerpanie kredytów')}: {get_text('in_days', language, default='za')} *{depletion_info['days_left']}* {get_text('days', language, default='dni')} "
            message += f"({depletion_info['depletion_date']})\n\n"
        else:
            message += f"{get_text('not_enough_data', language, default='Za mało danych, aby przewidzieć wyczerpanie kredytów.')}.\n\n"
        
        usage_breakdown = get_credit_usage_breakdown(user_id, days)
        
        if usage_breakdown:
            message += f"*{get_text('usage_breakdown', language, default='Rozkład zużycia kredytów')}:*\n"
            for category, amount in usage_breakdown.items():
                percentage = amount / sum(usage_breakdown.values()) * 100
                message += f"- {category}: *{amount}* {get_text('credits', language)} ({percentage:.1f}%)\n"
        
        if hasattr(query.message, 'caption'):
            await query.edit_message_caption(
                caption=message,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
        
        usage_chart = generate_credit_usage_chart(user_id, days)
        if usage_chart:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=usage_chart,
                caption=f"📈 {get_text('usage_history_chart', language, default=f'Historia wykorzystania kredytów z ostatnich {days} dni')}"
            )
        
        breakdown_chart = generate_usage_breakdown_chart(user_id, days)
        if breakdown_chart:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=breakdown_chart,
                caption=f"📊 {get_text('usage_breakdown_chart', language, default=f'Rozkład wykorzystania kredytów z ostatnich {days} dni')}"
            )
        
        keyboard = [[InlineKeyboardButton(get_text("back", language), callback_data="menu_credits_check")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if hasattr(query.message, 'caption'):
                await query.edit_message_reply_markup(reply_markup=reply_markup)
            else:
                await query.message.edit_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            print(f"Error updating keyboard: {e}")
        
        return True
    
    return False

async def credit_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /creditstats command with enhanced visual presentation"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    loading_message = await update.message.reply_text(
        "⏳ Analizuję dane wykorzystania kredytów..."
    )
    
    try:
        credits = get_user_credits(user_id)
        
        message = f"*Analiza kredytów*\n\n"
        message += f"Aktualny stan kredytów: *{credits}*\n\n"
        
        try:
            from database.credits_client import get_user_credit_stats
            # Dodane await przed wywołaniem funkcji asynchronicznej
            stats = await get_user_credit_stats(user_id)
            
            if stats:
                last_purchase = "Brak"
                if stats.get('last_purchase'):
                    if isinstance(stats['last_purchase'], str) and 'T' in stats['last_purchase']:
                        last_purchase = stats['last_purchase'].split('T')[0]
                    else:
                        last_purchase = str(stats['last_purchase'])
                
                message += f"*Statystyki kredytów:*\n"
                message += f"▪️ Łącznie zakupiono: *{stats.get('total_purchased', 0)}* kredytów\n"
                message += f"▪️ Wydano łącznie: *{stats.get('total_spent', 0)}* PLN\n"
                message += f"▪️ Ostatni zakup: *{last_purchase}*\n"
                message += f"▪️ Średnie dzienne zużycie: *{int(stats.get('avg_daily_usage', 0))}* kredytów\n\n"
                
                if stats.get('usage_history'):
                    message += f"*Historia transakcji (ostatnie 5):*\n"
                    
                    for i, transaction in enumerate(stats['usage_history'][:5]):
                        date = transaction.get('date', '')
                        if isinstance(date, str) and 'T' in date:
                            date = date.split('T')[0]
                        
                        transaction_type = transaction.get('type', '')
                        amount = transaction.get('amount', 0)
                        description = transaction.get('description', '')
                        
                        if transaction_type in ["add", "purchase", "subscription", "subscription_renewal"]:
                            message += f"🟢 +{amount} kr. ({date})"
                        else:
                            message += f"🔴 -{amount} kr. ({date})"
                            
                        if description:
                            message += f" - {description}"
                            
                        message += "\n"
        except Exception as e:
            print(f"Błąd przy pobieraniu statystyk: {e}")
            message += "*Błąd przy pobieraniu szczegółowych statystyk.*\n\n"
        
        keyboard = [
            [InlineKeyboardButton("💰 Kup więcej kredytów", callback_data="menu_credits_buy")],
            [InlineKeyboardButton("⬅️ Powrót", callback_data="menu_back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await loading_message.delete()
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
        try:
            from utils.credit_analytics import generate_credit_usage_chart, generate_usage_breakdown_chart
            
            # Dodane await przed wywołaniem funkcji asynchronicznej
            chart = await generate_credit_usage_chart(user_id)
            if chart:
                await update.message.reply_photo(
                    photo=chart,
                    caption="Historia wykorzystania kredytów"
                )
                
            # Dodane await przed wywołaniem funkcji asynchronicznej
            breakdown_chart = await generate_usage_breakdown_chart(user_id)
            if breakdown_chart:
                await update.message.reply_photo(
                    photo=breakdown_chart,
                    caption="Rozkład wykorzystania kredytów według kategorii"
                )
        except Exception as e:
            print(f"Błąd przy generowaniu wykresów: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"Błąd w credit_stats_command: {e}")
        import traceback
        traceback.print_exc()
        
        await loading_message.delete()
        
        await update.message.reply_text(
            "Wystąpił błąd podczas generowania statystyk. Spróbuj ponownie później."
        )
        
async def credit_analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display credit usage analysis"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    days = 30
    if context.args and len(context.args) > 0:
        try:
            days = int(context.args[0])
            if days < 1:
                days = 1
            elif days > 365:
                days = 365
        except ValueError:
            pass
    
    status_message = await update.message.reply_text(
        get_text("analyzing_credit_usage", language, default="⏳ Analizuję dane wykorzystania kredytów...")
    )
    
    depletion_info = predict_credit_depletion(user_id, days)
    
    if not depletion_info:
        await status_message.edit_text(
            get_text("not_enough_credit_history", language, default="Nie masz wystarczającej historii użycia kredytów, aby przeprowadzić analizę. Spróbuj ponownie po wykonaniu kilku operacji."),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = f"📊 *{get_text('credit_analytics', language, default='Analiza wykorzystania kredytów')}*\n\n"
    message += f"{get_text('current_balance', language)}: *{depletion_info['current_balance']}* {get_text('credits', language)}\n"
    message += f"{get_text('average_daily_usage', language, default='Średnie dzienne zużycie')}: *{depletion_info['average_daily_usage']}* {get_text('credits', language)}\n"
    
    if depletion_info['days_left']:
        message += f"{get_text('predicted_depletion', language, default='Przewidywane wyczerpanie kredytów')}: {get_text('in_days', language, default='za')} *{depletion_info['days_left']}* {get_text('days', language, default='dni')} "
        message += f"({depletion_info['depletion_date']})\n\n"
    else:
        message += f"{get_text('not_enough_data', language, default='Za mało danych, aby przewidzieć wyczerpanie kredytów.')}.\n\n"
    
    usage_breakdown = get_credit_usage_breakdown(user_id, days)
    
    if usage_breakdown and sum(usage_breakdown.values()) > 0:
        for category, amount in usage_breakdown.items():
            percentage = amount / sum(usage_breakdown.values()) * 100
            message += f"- {category}: *{amount}* {get_text('credits', language)} ({percentage:.1f}%)\n"
    else:
        message += f"- {get_text('no_data', language, default='Brak dostępnych danych o użyciu.')}\n"
    
    await status_message.edit_text(
        message,
        parse_mode=ParseMode.MARKDOWN
    )
    
    usage_chart = generate_credit_usage_chart(user_id, days)
    
    if usage_chart:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=usage_chart,
            caption=f"📈 {get_text('usage_history_chart', language, default=f'Historia wykorzystania kredytów z ostatnich {days} dni')}"
        )
    
    breakdown_chart = generate_usage_breakdown_chart(user_id, days)
    
    if breakdown_chart:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=breakdown_chart,
            caption=f"📊 {get_text('usage_breakdown_chart', language, default=f'Rozkład wykorzystania kredytów z ostatnich {days} dni')}"
        )

async def freecredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Dodaje 100 darmowych kredytów nowemu użytkownikowi (jednorazowo)
    Użycie: /freecredits
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    try:
        # Sprawdź bezpośrednio w tabeli transakcji czy użytkownik już wykorzystał darmowe kredyty
        from database.supabase_client import supabase
        
        response = supabase.table('credit_transactions').select('*').eq('user_id', user_id).eq('description', 'Free credits promotion').execute()
        
        if response.data and len(response.data) > 0:
            # Użytkownik już wykorzystał promocję
            message = create_header("Promocja wykorzystana", "info")
            message += get_text("free_credits_already_used", language, default="Już wykorzystałeś promocję darmowych kredytów.")
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        # Pobierz aktualny stan kredytów
        current_credits = get_user_credits(user_id)
        
        # Bezpośrednio zaktualizuj stan kredytów użytkownika
        updated_credits = current_credits + 100
        
        # Aktualizuj rekord użytkownika
        supabase.table('user_credits').update({
            'credits_amount': updated_credits
        }).eq('user_id', user_id).execute()
        
        # Dodaj wpis do historii transakcji
        import datetime
        now = datetime.datetime.now().isoformat()
        
        supabase.table('credit_transactions').insert({
            'user_id': user_id,
            'transaction_type': 'add',
            'amount': 100,
            'credits_before': current_credits,
            'credits_after': updated_credits,
            'description': 'Free credits promotion',
            'created_at': now
        }).execute()
        
        message = create_header("Darmowe kredyty dodane!", "success")
        message += get_text("free_credits_added", language, credits=100, total=updated_credits,
                         default=f"Dodano 100 darmowych kredytów do Twojego konta!\n\nAktualne saldo: {updated_credits} kredytów.")
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    
    except Exception as e:
        import logging
        logging.error(f"Błąd przy dodawaniu darmowych kredytów: {e}")
        
        message = create_header("Błąd", "error")
        message += get_text("free_credits_error", language, default="Wystąpił błąd podczas dodawania darmowych kredytów. Spróbuj ponownie później.")
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)