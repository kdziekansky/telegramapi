from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from config import CREDIT_COSTS, DALL_E_MODEL
from utils.translations import get_text
from handlers.menu_handler import get_user_language
from database.credits_client import check_user_credits, deduct_user_credits, get_user_credits
from utils.openai_client import generate_image_dall_e
from utils.visual_styles import create_header, create_status_indicator
from utils.credit_warnings import check_operation_cost, format_credit_usage_report
from utils.tips import get_random_tip, should_show_tip
from utils.menu import update_menu

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generuje obraz za pomocą DALL-E na podstawie opisu"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    quality = "standard"
    credit_cost = CREDIT_COSTS["image"][quality]
    credits = get_user_credits(user_id)
    
    if not await check_user_credits(user_id, credit_cost):
        warning_message = create_header(get_text("insufficient_credits_title", language, default="Niewystarczające kredyty"), "warning") + \
            get_text("insufficient_credits_message", language, cost=credit_cost, credits=credits, 
                     credits_needed=credit_cost-credits, default=f"Nie masz wystarczającej liczby kredytów.\n\n" + \
            f"▪️ Koszt operacji: *{credit_cost}* kredytów\n" + \
            f"▪️ Twój stan kredytów: *{credits}* kredytów\n\n" + \
            f"Potrzebujesz jeszcze *{credit_cost - credits}* kredytów.")
        
        keyboard = [
            [InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language), callback_data="menu_credits_buy")],
            [InlineKeyboardButton("⬅️ " + get_text("back", language, default="Powrót"), callback_data="menu_back_main")]
        ]
        
        await update.message.reply_text(warning_message, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if not context.args or len(' '.join(context.args)) < 3:
        usage_message = create_header(get_text("image_generation_title", language, default="Generowanie obrazów"), "image") + \
            f"{get_text('image_usage', language, default='Użycie: /image [opis obrazu]')}\n\n" + \
            f"*{get_text('examples', language, default='Przykłady')}:*\n" + \
            f"▪️ /image {get_text('image_example_1', language, default='zachód słońca nad górami z jeziorem')}\n" + \
            f"▪️ /image {get_text('image_example_2', language, default='portret kobiety w stylu renesansowym')}\n" + \
            f"▪️ /image {get_text('image_example_3', language, default='futurystyczne miasto nocą')}\n\n" + \
            f"*{get_text('tips', language, default='Wskazówki')}:*\n" + \
            f"▪️ {get_text('image_tip_1', language, default='Im bardziej szczegółowy opis, tym lepszy efekt')}\n" + \
            f"▪️ {get_text('image_tip_2', language, default='Możesz określić styl artystyczny (np. olejny, akwarela)')}\n" + \
            f"▪️ {get_text('image_tip_3', language, default='Dodaj informacje o oświetleniu, kolorach i kompozycji')}"
        
        if should_show_tip(user_id, context):
            tip = get_random_tip('image')
            usage_message += f"\n\n💡 *{get_text('tip', language, default='Porada')}:* {tip}"
        
        await update.message.reply_text(usage_message, parse_mode=ParseMode.MARKDOWN)
        return
    
    prompt = ' '.join(context.args)
    
    cost_warning = check_operation_cost(user_id, credit_cost, credits, get_text("image_generation", language, default="Generowanie obrazu"), context)
    if cost_warning['require_confirmation'] and cost_warning['level'] in ['warning', 'critical']:
        warning_message = create_header(get_text("cost_confirmation", language, default="Potwierdzenie kosztu"), "warning") + \
            cost_warning['message'] + "\n\n" + get_text("continue_question", language, default="Czy chcesz kontynuować?")
        
        keyboard = [
            [
                InlineKeyboardButton("✅ " + get_text("yes_generate", language, default="Tak, generuj"), 
                                     callback_data=f"confirm_image_{prompt.replace(' ', '_')[:50]}"),
                InlineKeyboardButton("❌ " + get_text("cancel", language, default="Anuluj"), 
                                     callback_data="cancel_operation")
            ]
        ]
        
        await update.message.reply_text(warning_message, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    message = await update.message.reply_text(
        create_status_indicator('loading', get_text("generating_image", language, default="Generowanie obrazu")) + "\n\n" +
        f"*{get_text('prompt', language, default='Prompt')}:* {prompt}\n" +
        f"*{get_text('cost', language, default='Koszt')}:* {credit_cost} {get_text('credits', language, default='kredytów')}"
    )

    await update.message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
    
    credits_before = credits
    image_url = await generate_image_dall_e(prompt)
    
    await deduct_user_credits(user_id, credit_cost, get_text("image_generation", language, default="Generowanie obrazu"))
    credits_after = get_user_credits(user_id)
    
    if image_url:
        await message.delete()
        
        caption = create_header(get_text("generated_image", language, default="Wygenerowany obraz"), "image") + \
                  f"*{get_text('prompt', language, default='Prompt')}:* {prompt}\n"
        
        usage_report = format_credit_usage_report(get_text("image_generation", language, default="Generowanie obrazu"), 
                                                 credit_cost, credits_before, credits_after)
        caption += f"\n{usage_report}"
        
        if should_show_tip(user_id, context):
            tip = get_random_tip('image')
            caption += f"\n\n💡 *{get_text('tip', language, default='Porada')}:* {tip}"
        
        await update.message.reply_photo(photo=image_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
    else:
        error_message = create_header(get_text("generation_error", language, default="Błąd generowania"), "error") + \
            get_text("image_generation_error", language, default="Przepraszam, wystąpił błąd podczas generowania obrazu.")
        
        await message.edit_text(error_message, parse_mode=ParseMode.MARKDOWN)
    
    if credits_after < 5:
        low_credits_warning = create_header(get_text("low_credits_warning", language, default="Niski stan kredytów"), "warning") + \
            get_text("low_credits_message", language, credits=credits_after, default=f"Pozostało Ci tylko *{credits_after}* kredytów. Rozważ zakup pakietu.")
        
        keyboard = [[InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language), callback_data="menu_credits_buy")]]
        await update.message.reply_text(low_credits_warning, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_image_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługuje potwierdzenie generowania obrazu"""
    query = update.callback_query
    user_id = query.from_user.id
    language = get_user_language(context, user_id)
    
    await query.answer()
    
    if query.data.startswith("confirm_image_"):
        prompt = query.data[14:].replace('_', ' ')
        
        await update_menu(
            query,
            create_status_indicator('loading', get_text("generating_image", language, default="Generowanie obrazu")) + "\n\n" +
            f"*{get_text('prompt', language, default='Prompt')}:* {prompt}",
            None,
            parse_mode=ParseMode.MARKDOWN
        )
        
        credit_cost = CREDIT_COSTS["image"]["standard"]
        credits = get_user_credits(user_id)
        
        if not await check_user_credits(user_id, credit_cost):
            await update_menu(
                query,
                create_header(get_text("insufficient_credits_title", language, default="Brak wystarczających kredytów"), "error") +
                get_text("credit_status_changed", language, default="W międzyczasie twój stan kredytów zmienił się i nie masz już wystarczającej liczby kredytów."),
                InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ " + get_text("back", language, default="Powrót"), callback_data="menu_back_main")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        credits_before = credits
        image_url = await generate_image_dall_e(prompt)
        await deduct_user_credits(user_id, credit_cost, get_text("image_generation", language, default="Generowanie obrazu"))
        credits_after = get_user_credits(user_id)
        
        if image_url:
            caption = create_header(get_text("generated_image", language, default="Wygenerowany obraz"), "image") + \
                      f"*{get_text('prompt', language, default='Prompt')}:* {prompt}\n"
            usage_report = format_credit_usage_report(get_text("image_generation", language, default="Generowanie obrazu"), 
                                                     credit_cost, credits_before, credits_after)
            caption += f"\n{usage_report}"
            
            if should_show_tip(user_id, context):
                tip = get_random_tip('image')
                caption += f"\n\n💡 *{get_text('tip', language, default='Porada')}:* {tip}"
            
            await query.message.delete()
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=image_url, 
                                        caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await update_menu(
                query,
                create_header(get_text("generation_error", language, default="Błąd generowania"), "error") +
                get_text("image_generation_error", language, default="Przepraszam, wystąpił błąd podczas generowania obrazu."),
                InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ " + get_text("back", language, default="Powrót"), callback_data="menu_back_main")]]),
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif query.data == "cancel_operation":
        await update_menu(
            query,
            create_header(get_text("operation_cancelled", language, default="Operacja anulowana"), "info") +
            get_text("image_generation_cancelled", language, default="Generowanie obrazu zostało anulowane."),
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ " + get_text("main_menu", language, default="Menu główne"), callback_data="menu_back_main")]]),
            parse_mode=ParseMode.MARKDOWN
        )