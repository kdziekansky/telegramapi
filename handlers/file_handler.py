from telegram import Update
from utils.translations import get_text
from utils.user_utils import get_user_language
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.supabase_client import check_active_subscription
from utils.openai_client import analyze_document, analyze_image
from utils.ui_elements import info_card, section_divider, feature_badge, progress_bar
from utils.visual_styles import style_message, create_header, create_section, create_status_indicator
from utils.tips import get_random_tip, should_show_tip
from utils.credit_warnings import check_operation_cost, format_credit_usage_report
from database.credits_client import check_user_credits, deduct_user_credits, get_user_credits
from config import CREDIT_COSTS

async def _check_file_prerequisites(update, context, file_type, file_size_limit=25*1024*1024):
    """Common prerequisites check for both document and photo handlers"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Check subscription
    if not check_active_subscription(user_id):
        message = create_header(get_text("subscription_expired_short", language, default="Subskrypcja wygasła"), "warning") + \
                 get_text("subscription_expired", language)
        
        keyboard = [
            [InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language), callback_data="menu_credits_buy")],
            [InlineKeyboardButton("⬅️ " + get_text("back", language, default="Powrót"), callback_data="menu_back_main")]
        ]
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    
    # Check size limit for documents
    if hasattr(update.message, 'document') and update.message.document and update.message.document.file_size > file_size_limit:
        error_message = create_header(get_text("file_too_large_header", language, default="Plik zbyt duży"), "error") + \
                       get_text("file_too_large", language) + \
                       f" ({update.message.document.file_size/(1024*1024):.1f}MB)"
        await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)
        return False
    
    # Check credits
    credit_cost = CREDIT_COSTS[file_type]
    credits = get_user_credits(user_id)
    
    if not check_user_credits(user_id, credit_cost):
        warning_message = create_header(get_text("insufficient_credits", language, default="Brak wystarczających kredytów"), "warning") + \
                         get_text("insufficient_credits_detailed", language, default="Nie masz wystarczającej liczby kredytów.") + "\n\n" + \
                         f"▪️ {get_text('operation_cost', language, default='Koszt operacji')}: *{credit_cost}* {get_text('credits', language)}\n" + \
                         f"▪️ {get_text('current_balance', language, default='Twój stan kredytów')}: *{credits}* {get_text('credits', language)}"
        
        keyboard = [
            [InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language), callback_data="menu_credits_buy")],
            [InlineKeyboardButton("⬅️ " + get_text("back", language, default="Powrót"), callback_data="menu_back_main")]
        ]
        await update.message.reply_text(warning_message, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    
    return True

async def _handle_file_analysis(update, context, file_id, file_name, file_type, operation_name, 
                              analyze_func, credit_cost, mode="analyze", target_language=None):
    """Common function for handling file analysis with appropriate UI and credit management"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    # Initial loading message
    message = await update.message.reply_text(
        create_status_indicator('loading', get_text(operation_name, language, default=operation_name)) + "\n\n" +
        (f"*{get_text('document', language, default='Dokument')}:* {file_name}" if file_type == "document" else "")
    )
    
    await update.message.chat.send_action(action=ChatAction.TYPING)
    
    credits_before = get_user_credits(user_id)
    
    try:
        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        
        if file_type == "document":
            result = await analyze_document(file_bytes, file_name, mode, target_language)
        else:  # photo
            result = await analyze_image(file_bytes, f"photo_{file_id}.jpg", mode, target_language)
        
        deduct_user_credits(user_id, credit_cost, f"{get_text(operation_name, language, default=operation_name)}: {file_name if file_type == 'document' else ''}")
        
        credits_after = get_user_credits(user_id)
        
        # Prepare result message with appropriate header
        if mode == "translate":
            result_message = create_header(get_text("text_translation", language, default="Tłumaczenie tekstu"), "translation")
        elif file_type == "document":
            result_message = create_header(get_text("file_analysis_title", language, file_name=file_name, default=f"Analiza dokumentu: {file_name}"), "document")
        else:
            result_message = create_header(get_text("photo_analysis", language, default="Analiza zdjęcia"), "analysis")
        
        # Handle long responses
        if file_type == "document" and len(result) > 3000:
            result = result[:3000] + "...\n\n" + get_text("analysis_truncated", language, default="(Analiza została skrócona ze względu na długość)")
            
        result_message += result
        
        # Add usage report
        usage_report = format_credit_usage_report(get_text(operation_name, language, default=operation_name), 
                                                 credit_cost, credits_before, credits_after)
        result_message += f"\n\n{usage_report}"
        
        # Add tip if appropriate
        if should_show_tip(user_id, context):
            tip = get_random_tip(file_type)
            result_message += f"\n\n💡 *{get_text('tip', language, default='Porada')}:* {tip}"
        
        await message.edit_text(result_message, parse_mode=ParseMode.MARKDOWN)
        
        # Show low credits warning if needed
        if credits_after < 5:
            low_credits_warning = create_header(get_text("low_credits_warning", language, default="Niski stan kredytów"), "warning") + \
                                get_text("low_credits_message", language, credits=credits_after, default=f"Pozostało Ci tylko *{credits_after}* kredytów. Rozważ zakup pakietu.")
            
            keyboard = [[InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language), callback_data="menu_credits_buy")]]
            await update.message.reply_text(low_credits_warning, parse_mode=ParseMode.MARKDOWN, 
                                           reply_markup=InlineKeyboardMarkup(keyboard))
        
        return True
    except Exception as e:
        await message.edit_text(
            create_header(get_text("operation_error", language, operation_type=operation_name, default=f"Błąd {operation_name}"), "error") +
            get_text("error_occurred", language, error=str(e), default=f"Wystąpił błąd podczas {operation_name.lower()}: {str(e)}"),
            parse_mode=ParseMode.MARKDOWN
        )
        return False

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługa przesłanych dokumentów z ulepszoną prezentacją"""
    if not await _check_file_prerequisites(update, context, "document"):
        return
    
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    document = update.message.document
    file_name = document.file_name
    credit_cost = CREDIT_COSTS["document"]
    credits = get_user_credits(user_id)
    
    caption = update.message.caption or ""
    caption_lower = caption.lower()
    
    is_pdf = file_name.lower().endswith('.pdf')
    
    if is_pdf and any(word in caption_lower for word in ["tłumacz", "przetłumacz", "translate", "переводить"]):
        options_message = create_header(get_text("pdf_document_options", language, default="Opcje dla dokumentu PDF"), "document") + \
                         f"{get_text('pdf_detected', language, default='Wykryto dokument PDF')}: *{file_name}*\n\n{get_text('pdf_options', language, default='Wybierz co chcesz zrobić z tym dokumentem:')}"
        
        options_message += "\n\n" + create_section(get_text("operation_cost", language, default="Koszt operacji"), 
            f"▪️ {get_text('document_analysis', language)}: *{CREDIT_COSTS['document']}* {get_text('credits', language)}\n" +
            f"▪️ {get_text('document_translation', language, default='Tłumaczenie dokumentu')}: *8* {get_text('credits', language)}")
        
        if should_show_tip(user_id, context):
            tip = get_random_tip('document')
            options_message += f"\n\n💡 *{get_text('tip', language, default='Porada')}:* {tip}"
        
        keyboard = [
            [
                InlineKeyboardButton("📝 " + get_text("document_analysis", language), callback_data="analyze_document"),
                InlineKeyboardButton("🔤 " + get_text("document_translation", language, default="Tłumaczenie dokumentu"), callback_data="translate_document")
            ],
            [InlineKeyboardButton("❌ " + get_text("cancel", language, default="Anuluj"), callback_data="cancel_operation")]
        ]
        
        await update.message.reply_text(options_message, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        
        if 'user_data' not in context.chat_data:
            context.chat_data['user_data'] = {}
        if user_id not in context.chat_data['user_data']:
            context.chat_data['user_data'][user_id] = {}
            
        context.chat_data['user_data'][user_id]['last_document_id'] = document.file_id
        context.chat_data['user_data'][user_id]['last_document_name'] = file_name
        
        return
    
    cost_warning = check_operation_cost(user_id, credit_cost, credits, get_text("document_analysis", language), context)
    if cost_warning['require_confirmation'] and cost_warning['level'] in ['warning', 'critical']:
        warning_message = create_header(get_text("cost_confirmation", language, default="Potwierdzenie kosztu"), "warning") + \
                         cost_warning['message'] + "\n\n" + get_text("want_to_continue", language, default="Czy chcesz kontynuować?")
        
        keyboard = [
            [
                InlineKeyboardButton("✅ " + get_text("yes_analyze", language, default="Tak, analizuj"), callback_data=f"confirm_doc_analysis_{document.file_id}"),
                InlineKeyboardButton("❌ " + get_text("cancel", language, default="Anuluj"), callback_data="cancel_operation")
            ]
        ]
        
        await update.message.reply_text(warning_message, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        
        if 'user_data' not in context.chat_data:
            context.chat_data['user_data'] = {}
        if user_id not in context.chat_data['user_data']:
            context.chat_data['user_data'][user_id] = {}
            
        context.chat_data['user_data'][user_id]['last_document_id'] = document.file_id
        context.chat_data['user_data'][user_id]['last_document_name'] = file_name
        
        return
    
    await _handle_file_analysis(
        update, context, document.file_id, file_name, "document", 
        "document_analysis", analyze_document, credit_cost
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługa przesłanych zdjęć z ulepszoną prezentacją"""
    if not await _check_file_prerequisites(update, context, "photo"):
        return
    
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    credit_cost = CREDIT_COSTS["photo"]
    credits = get_user_credits(user_id)
    
    photo = update.message.photo[-1]
    
    caption = update.message.caption or ""
    
    if not caption:
        options_message = create_header(get_text("photo_options", language, default="Opcje dla zdjęcia"), "image") + \
                         get_text("photo_detected", language, default="Wykryto zdjęcie. Wybierz co chcesz zrobić z tym zdjęciem:")
        
        options_message += "\n\n" + create_section(get_text("operation_cost", language, default="Koszt operacji"), 
            f"▪️ {get_text('photo_analysis', language)}: *{CREDIT_COSTS['photo']}* {get_text('credits', language)}\n" +
            f"▪️ {get_text('text_translation', language, default='Tłumaczenie tekstu')}: *{CREDIT_COSTS['photo']}* {get_text('credits', language)}")
        
        if should_show_tip(user_id, context):
            tip = get_random_tip('document')
            options_message += f"\n\n💡 *{get_text('tip', language, default='Porada')}:* {tip}"
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 " + get_text("photo_analysis", language), callback_data="analyze_photo"),
                InlineKeyboardButton("🔤 " + get_text("text_translation", language, default="Tłumaczenie tekstu"), callback_data="translate_photo")
            ],
            [InlineKeyboardButton("❌ " + get_text("cancel", language, default="Anuluj"), callback_data="cancel_operation")]
        ]
        
        await update.message.reply_text(options_message, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=InlineKeyboardMarkup(keyboard))
        
        if 'user_data' not in context.chat_data:
            context.chat_data['user_data'] = {}
        if user_id not in context.chat_data['user_data']:
            context.chat_data['user_data'][user_id] = {}
            
        context.chat_data['user_data'][user_id]['last_photo_id'] = photo.file_id
        
        return
    
    caption_lower = caption.lower()
    
    # Determine operation type
    if any(word in caption_lower for word in ["tłumacz", "przetłumacz", "translate", "переводить"]):
        mode = "translate"
        operation_name = get_text("photo_translation", language, default="Tłumaczenie tekstu ze zdjęcia")
    else:
        mode = "analyze"
        operation_name = get_text("photo_analysis", language)
    
    cost_warning = check_operation_cost(user_id, credit_cost, credits, operation_name, context)
    if cost_warning['require_confirmation'] and cost_warning['level'] in ['warning', 'critical']:
        warning_message = create_header(get_text("cost_confirmation", language, default="Potwierdzenie kosztu"), "warning") + \
                         cost_warning['message'] + "\n\n" + get_text("want_to_continue", language, default="Czy chcesz kontynuować?")
        
        callback_data = f"confirm_photo_{mode}_{photo.file_id}"
        keyboard = [
            [
                InlineKeyboardButton("✅ " + get_text("yes_continue", language, default="Tak, kontynuuj"), callback_data=callback_data),
                InlineKeyboardButton("❌ " + get_text("cancel", language, default="Anuluj"), callback_data="cancel_operation")
            ]
        ]
        
        await update.message.reply_text(warning_message, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup(keyboard))
        
        if 'user_data' not in context.chat_data:
            context.chat_data['user_data'] = {}
        if user_id not in context.chat_data['user_data']:
            context.chat_data['user_data'][user_id] = {}
            
        context.chat_data['user_data'][user_id]['last_photo_id'] = photo.file_id
        context.chat_data['user_data'][user_id]['last_photo_mode'] = mode
        
        return
    
    await _handle_file_analysis(
        update, context, photo.file_id, None, "photo", operation_name,
        analyze_image, credit_cost, mode=mode
    )