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
    get_user_credit_stats
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
    message += f"{get_text('available_credits', language)}: *{credits}*\n\n"
    
    try:
        from database.credits_client import get_user_credit_stats
        stats = get_user_credit_stats(user_id)
        
        if stats:
            message += f"*{get_text('statistics', language, default='Statystyki')}:*\n"
            message += f"▪️ {get_text('total_purchased', language)}: {stats.get('total_purchased', 0)} {get_text('credits', language)}\n"
            message += f"▪️ {get_text('average_daily_usage', language, default='Średnie dzienne zużycie')}: {int(stats.get('avg_daily_usage', 0))} {get_text('credits', language)}\n"
            
            if stats.get('most_expensive_operation'):
                message += f"▪️ {get_text('most_expensive_operation', language, default='Najdroższa operacja')}: {stats.get('most_expensive_operation')}\n"
    except Exception as e:
        print(f"{get_text('stats_error', language, default='Błąd przy pobieraniu statystyk')}: {e}")
    
    message += f"\n*{get_text('operation_costs', language)}:*\n"
    message += f"▪️ {get_text('standard_message', language)} (GPT-3.5): 1 {get_text('credit', language)}\n"
    message += f"▪️ {get_text('premium_message', language)} (GPT-4o): 3 {get_text('credits', language)}\n"
    message += f"▪️ {get_text('expert_message', language)} (GPT-4): 5 {get_text('credits', language)}\n"
    message += f"▪️ {get_text('dalle_image', language)}: 10-15 {get_text('credits', language)}\n"
    message += f"▪️ {get_text('document_analysis', language)}: 5 {get_text('credits', language)}\n"
    message += f"▪️ {get_text('photo_analysis', language)}: 8 {get_text('credits', language)}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language), callback_data="menu_credits_buy")],
        [
            InlineKeyboardButton("💰 " + get_text("payment_methods", language, default="Metody płatności"), callback_data="payment_command"),
            InlineKeyboardButton("🔄 " + get_text("subscription_manage", language, default="Subskrypcje"), callback_data="subscription_command")
        ],
        [InlineKeyboardButton("📜 " + get_text("transaction_history", language, default="Historia transakcji"), callback_data="transactions_command")],
        [InlineKeyboardButton("⬅️ " + get_text("back", language), callback_data="menu_back_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"{get_text('message_error', language, default='Błąd przy wysyłaniu wiadomości z kredytami')}: {e}")
        await update.message.reply_text(
            message.replace("*", ""),
            reply_markup=reply_markup
        )

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /buy command with enhanced visual presentation"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    message = create_header(get_text("buy_credits_title", language, default="Zakup kredytów"), "credits")
    
    message += (
        get_text("buy_credits_info", language, default="Wybierz jedną z dostępnych metod płatności, aby kupić pakiet kredytów. "
        "Kredyty są używane do wszystkich operacji w bocie, takich jak:\n\n"
        "▪️ Rozmowy z różnymi modelami AI\n"
        "▪️ Generowanie obrazów\n"
        "▪️ Analizowanie dokumentów i zdjęć\n"
        "▪️ Tłumaczenie tekstów\n\n"
        "Dostępne są różne metody płatności.")
    )
    
    message += "\n\n" + create_section(get_text("subscription_benefits", language, default="Korzyści z subskrypcji"), 
        "▪️ " + get_text("auto_renewal", language, default="Automatyczne odnowienie kredytów co miesiąc") + "\n"
        "▪️ " + get_text("lower_cost", language, default="Niższy koszt kredytów") + "\n"
        "▪️ " + get_text("priority_service", language, default="Priorytetowa obsługa") + "\n"
        "▪️ " + get_text("premium_features", language, default="Dodatkowe funkcje premium"))
    
    keyboard = [
        [
            InlineKeyboardButton("💳 " + get_text("one_time_packages", language, default="Pakiety jednorazowe"), callback_data="payment_method_stripe"),
            InlineKeyboardButton("🔄 " + get_text("subscription", language, default="Subskrypcja"), callback_data="payment_method_stripe_subscription")
        ],
        [
            InlineKeyboardButton("⬅️ " + get_text("back", language), callback_data="menu_back_main")
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
            print(f"{get_text('message_update_error', language, default='Error updating message')}: {e}")
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
                print(f"{get_text('second_message_update_error', language, default='Second error updating message')}: {e2}")
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
            print(f"{get_text('buy_credits_redirect_error', language, default='Błąd przy przekierowaniu do zakupu kredytów')}: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                keyboard = [[InlineKeyboardButton("⬅️ " + get_text("main_menu", language, default="Menu główne"), callback_data="menu_back_main")]]
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=get_text("buy_command_error", language, default="Wystąpił błąd. Spróbuj użyć komendy /buy"),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e2:
                print(f"{get_text('message_display_error', language, default='Błąd przy wyświetlaniu komunikatu')}: {e2}")
            return True
    
    if query.data == "credits_stats" or query.data == "credit_advanced_analytics":
        user_id = query.from_user.id
        language = get_user_language(context, user_id)
        
        if hasattr(query.message, 'caption'):
            await query.edit_message_caption(
                caption=get_text("analyzing_credit_usage", language)
            )
        else:
            await query.edit_message_text(
                text=get_text("analyzing_credit_usage", language)
            )
        
        days = 30
        
        depletion_info = predict_credit_depletion(user_id, days)
        
        if not depletion_info:
            if hasattr(query.message, 'caption'):
                await query.edit_message_caption(
                    caption=get_text("not_enough_credit_history", language)
                )
            else:
                await query.edit_message_text(
                    text=get_text("not_enough_credit_history", language)
                )
            return True
        
        message = f"📊 *{get_text('credit_analytics', language)}*\n\n"
        message += f"{get_text('current_balance', language)}: *{depletion_info['current_balance']}* {get_text('credits', language)}\n"
        message += f"{get_text('average_daily_usage', language)}: *{depletion_info['average_daily_usage']}* {get_text('credits', language)}\n"
        
        if depletion_info['days_left']:
            message += f"{get_text('predicted_depletion', language)}: {get_text('in_days', language)} *{depletion_info['days_left']}* {get_text('days', language)} "
            message += f"({depletion_info['depletion_date']})\n\n"
        else:
            message += f"{get_text('not_enough_data', language)}.\n\n"
        
        usage_breakdown = get_credit_usage_breakdown(user_id, days)
        
        if usage_breakdown:
            message += f"*{get_text('usage_breakdown', language)}:*\n"
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
                caption=f"📈 {get_text('usage_history_chart', language, days=days)}"
            )
        
        breakdown_chart = generate_usage_breakdown_chart(user_id, days)
        if breakdown_chart:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=breakdown_chart,
                caption=f"📊 {get_text('usage_breakdown_chart', language, days=days)}"
            )
        
        keyboard = [[InlineKeyboardButton(get_text("back", language), callback_data="menu_credits_check")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if hasattr(query.message, 'caption'):
                await query.edit_message_reply_markup(reply_markup=reply_markup)
            else:
                await query.message.edit_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            print(f"{get_text('keyboard_update_error', language, default='Error updating keyboard')}: {e}")
        
        return True
    
    return False

async def credit_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /creditstats command with enhanced visual presentation"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    loading_message = await update.message.reply_text(
        get_text("analyzing_credit_usage", language)
    )
    
    try:
        credits = get_user_credits(user_id)
        
        message = f"*{get_text('credit_analytics', language, default='Analiza kredytów')}*\n\n"
        message += f"{get_text('current_balance', language)}: *{credits}*\n\n"
        
        try:
            from database.credits_client import get_user_credit_stats
            # Dodane await przed wywołaniem funkcji asynchronicznej
            stats = await get_user_credit_stats(user_id)
            
            if stats:
                last_purchase = get_text("none", language, default="Brak")
                if stats.get('last_purchase'):
                    if isinstance(stats['last_purchase'], str) and 'T' in stats['last_purchase']:
                        last_purchase = stats['last_purchase'].split('T')[0]
                    else:
                        last_purchase = str(stats['last_purchase'])
                
                message += f"*{get_text('credit_statistics', language, default='Statystyki kredytów')}:*\n"
                message += f"▪️ {get_text('total_purchased', language)}: *{stats.get('total_purchased', 0)}* {get_text('credits', language)}\n"
                message += f"▪️ {get_text('total_spent', language)}: *{stats.get('total_spent', 0)}* PLN\n"
                message += f"▪️ {get_text('last_purchase', language)}: *{last_purchase}*\n"
                message += f"▪️ {get_text('average_daily_usage', language)}: *{int(stats.get('avg_daily_usage', 0))}* {get_text('credits', language)}\n\n"
                
                if stats.get('usage_history'):
                    message += f"*{get_text('transaction_history', language, default='Historia transakcji')} ({get_text('last_5', language, default='ostatnie 5'}):*\n"
                    
                    for i, transaction in enumerate(stats['usage_history'][:5]):
                        date = transaction.get('date', '')
                        if isinstance(date, str) and 'T' in date:
                            date = date.split('T')[0]
                        
                        transaction_type = transaction.get('type', '')
                        amount = transaction.get('amount', 0)
                        description = transaction.get('description', '')
                        
                        if transaction_type in ["add", "purchase", "subscription", "subscription_renewal"]:
                            message += f"🟢 +{amount} {get_text('credits_short', language, default='kr.')} ({date})"
                        else:
                            message += f"🔴 -{amount} {get_text('credits_short', language, default='kr.')} ({date})"
                            
                        if description:
                            message += f" - {description}"
                            
                        message += "\n"
        except Exception as e:
            print(f"{get_text('stats_error', language)}: {e}")
            message += f"*{get_text('detailed_stats_error', language, default='Błąd przy pobieraniu szczegółowych statystyk.')}*\n\n"
        
        keyboard = [
            [InlineKeyboardButton("💰 " + get_text("buy_more_credits", language), callback_data="menu_credits_buy")],
            [InlineKeyboardButton("⬅️ " + get_text("back", language), callback_data="menu_back_main")]
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
                    caption=get_text("usage_history_chart", language, days=30, default="Historia wykorzystania kredytów")
                )
                
            # Dodane await przed wywołaniem funkcji asynchronicznej
            breakdown_chart = await generate_usage_breakdown_chart(user_id)
            if breakdown_chart:
                await update.message.reply_photo(
                    photo=breakdown_chart,
                    caption=get_text("usage_breakdown_chart", language, days=30, default="Rozkład wykorzystania kredytów według kategorii")
                )
        except Exception as e:
            print(f"{get_text('charts_error', language, default='Błąd przy generowaniu wykresów')}: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"{get_text('credit_stats_error', language, default='Błąd w credit_stats_command')}: {e}")
        import traceback
        traceback.print_exc()
        
        await loading_message.delete()
        
        await update.message.reply_text(
            get_text("stats_generation_error", language, default="Wystąpił błąd podczas generowania statystyk. Spróbuj ponownie później.")
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
        get_text("analyzing_credit_usage", language)
    )
    
    depletion_info = predict_credit_depletion(user_id, days)
    
    if not depletion_info:
        await status_message.edit_text(
            get_text("not_enough_credit_history", language),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    message = f"📊 *{get_text('credit_analytics', language)}*\n\n"
    message += f"{get_text('current_balance', language)}: *{depletion_info['current_balance']}* {get_text('credits', language)}\n"
    message += f"{get_text('average_daily_usage', language)}: *{depletion_info['average_daily_usage']}* {get_text('credits', language)}\n"
    
    if depletion_info['days_left']:
        message += f"{get_text('predicted_depletion', language)}: {get_text('in_days', language)} *{depletion_info['days_left']}* {get_text('days', language)} "
        message += f"({depletion_info['depletion_date']})\n\n"
    else:
        message += f"{get_text('not_enough_data', language)}.\n\n"
    
    usage_breakdown = get_credit_usage_breakdown(user_id, days)
    
    if usage_breakdown and sum(usage_breakdown.values()) > 0:
        for category, amount in usage_breakdown.items():
            percentage = amount / sum(usage_breakdown.values()) * 100
            message += f"- {category}: *{amount}* {get_text('credits', language)} ({percentage:.1f}%)\n"
    else:
        message += f"- {get_text('no_data', language)}\n"
    
    await status_message.edit_text(
        message,
        parse_mode=ParseMode.MARKDOWN
    )
    
    usage_chart = generate_credit_usage_chart(user_id, days)
    
    if usage_chart:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=usage_chart,
            caption=f"📈 {get_text('usage_history_chart', language, days=days)}"
        )
    
    breakdown_chart = generate_usage_breakdown_chart(user_id, days)
    
    if breakdown_chart:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=breakdown_chart,
            caption=f"📊 {get_text('usage_breakdown_chart', language, days=days)}"
        )