from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from config import CHAT_MODES, DEFAULT_MODEL, MAX_CONTEXT_MESSAGES, CREDIT_COSTS
from utils.translations import get_text
from utils.user_utils import get_user_language, is_chat_initialized, mark_chat_initialized
from database.supabase_client import (
    get_active_conversation, save_message, get_conversation_history, increment_messages_used, create_new_conversation
)
from database.credits_client import get_user_credits, check_user_credits, deduct_user_credits
from utils.openai_client import chat_completion_stream, prepare_messages_from_history
from utils.visual_styles import create_header, create_status_indicator
from utils.credit_warnings import check_operation_cost, format_credit_usage_report
from utils.tips import get_contextual_tip, get_random_tip, should_show_tip
import datetime
import logging

logger = logging.getLogger(__name__)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługa wiadomości tekstowych od użytkownika ze strumieniowaniem odpowiedzi i ulepszonym formatowaniem"""
    user_id = update.effective_user.id
    user_message = update.message.text
    language = get_user_language(context, user_id)
    
    # Sprawdź, czy użytkownik zainicjował czat
    if not is_chat_initialized(context, user_id):
        # Enhanced UI for chat initialization prompt
        message = create_header("Rozpocznij nowy czat", "chat")
        message += (
            "Aby rozpocząć używanie AI, najpierw utwórz nowy czat używając /newchat "
            "lub przycisku poniżej. Możesz również wybrać tryb czatu z menu."
        )
        
        keyboard = [
            [InlineKeyboardButton("🆕 " + get_text("start_new_chat", language, default="Rozpocznij nowy czat"), callback_data="quick_new_chat")],
            [InlineKeyboardButton("📋 " + get_text("select_mode", language, default="Wybierz tryb czatu"), callback_data="menu_section_chat_modes")],
            [InlineKeyboardButton("❓ " + get_text("menu_help", language, default="Pomoc"), callback_data="menu_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    # Określ tryb i koszt kredytów
    current_mode = "no_mode"
    credit_cost = 1
    
    if 'user_data' in context.chat_data and user_id in context.chat_data['user_data']:
        user_data = context.chat_data['user_data'][user_id]
        if 'current_mode' in user_data and user_data['current_mode'] in CHAT_MODES:
            current_mode = user_data['current_mode']
            credit_cost = CHAT_MODES[current_mode]["credit_cost"]
    
    # Get current credits
    credits = get_user_credits(user_id)
    
    # Sprawdź, czy użytkownik ma wystarczającą liczbę kredytów
    if not await check_user_credits(user_id, credit_cost):
        warning_message = create_header("Niewystarczające kredyty", "warning")
        warning_message += (
            f"Nie masz wystarczającej liczby kredytów, aby wysłać wiadomość.\n\n"
            f"▪️ Koszt operacji: *{credit_cost}* kredytów\n"
            f"▪️ Twój stan kredytów: *{credits}* kredytów\n\n"
            f"Potrzebujesz jeszcze *{credit_cost - credits}* kredytów.\n\n"
            f"Wybierz tańszy model (np. O3-mini lub GPT-3.5 Turbo za 1 kredyt/wiadomość)"
        )
        
        # Add credit recommendation if available
        from utils.credit_warnings import get_credit_recommendation
        recommendation = get_credit_recommendation(user_id, context)
        if recommendation:
            from utils.visual_styles import create_section
            warning_message += "\n\n" + create_section("Rekomendowany pakiet", 
                f"▪️ {recommendation['package_name']} - {recommendation['credits']} kredytów\n"
                f"▪️ Cena: {recommendation['price']} PLN\n"
                f"▪️ {recommendation['reason']}")
        
        keyboard = [
            [InlineKeyboardButton("🤖 " + get_text("change_model", language, default="Zmień model"), callback_data="settings_model")],
            [InlineKeyboardButton("💳 " + get_text("buy_credits_btn", language, default="Kup kredyty"), callback_data="menu_credits_buy")],
            [InlineKeyboardButton("⬅️ " + get_text("menu_back_main", language, default="Menu główne"), callback_data="menu_back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            warning_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Check operation cost and show warning if needed
    cost_warning = check_operation_cost(user_id, credit_cost, credits, "Wiadomość AI", context)
    if cost_warning['require_confirmation'] and cost_warning['level'] in ['warning', 'critical']:
        # Show warning and ask for confirmation
        warning_message = create_header("Potwierdzenie kosztu", "warning")
        warning_message += cost_warning['message'] + "\n\nCzy chcesz kontynuować?"
        
        # Create confirmation buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Tak, wyślij", callback_data=f"confirm_message"),
                InlineKeyboardButton("❌ Anuluj", callback_data="cancel_operation")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store message in context for later use
        if 'user_data' not in context.chat_data:
            context.chat_data['user_data'] = {}
        if user_id not in context.chat_data['user_data']:
            context.chat_data['user_data'][user_id] = {}
            
        context.chat_data['user_data'][user_id]['pending_message'] = user_message
        
        await update.message.reply_text(
            warning_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return
    
    # Pobierz lub utwórz aktywną konwersację
    try:
        conversation = await get_active_conversation(user_id)
        # Używamy notacji z kropką zamiast nawiasów
        conversation_id = conversation.id if hasattr(conversation, 'id') else None
        
        # Jeśli nie mamy ID, rzuć wyjątek aby przejść do tworzenia nowej konwersacji
        if conversation_id is None:
            raise ValueError("Brak ID konwersacji")
            
    except Exception as e:
        logger.error(f"Błąd przy pobieraniu konwersacji: {e}")
        # Bezpośrednia próba utworzenia nowej konwersacji z obsługą błędów
        try:
            conversation = await create_new_conversation(user_id)
            conversation_id = conversation.id if hasattr(conversation, 'id') else None
            
            if conversation_id is None:
                # Jeśli nadal nie mamy ID, spróbujmy wykorzystać słownik
                if isinstance(conversation, dict) and 'id' in conversation:
                    conversation_id = conversation['id']
                else:
                    raise ValueError("Nie można uzyskać ID konwersacji")
                    
            logger.info(f"Utworzono nową konwersację po błędzie: {conversation_id}")
        except Exception as e2:
            logger.error(f"Nie udało się utworzyć nowej konwersacji: {e2}")
            await update.message.reply_text(
                get_text("conversation_error", language, default="Wystąpił błąd przy pobieraniu konwersacji. Spróbuj /newchat aby utworzyć nową.")
            )
            return
    
    # Zapisz wiadomość użytkownika do bazy danych
    try:
        await save_message(conversation_id, user_id, user_message, is_from_user=True)
    except Exception as e:
        logger.warning(f"Nie udało się zapisać wiadomości użytkownika: {e}")
    
    # Wyślij informację, że bot pisze
    await update.message.chat.send_action(action=ChatAction.TYPING)
    
    # Pobierz historię konwersacji
    try:
        history = await get_conversation_history(conversation_id, limit=MAX_CONTEXT_MESSAGES)
    except Exception as e:
        logger.warning(f"Nie udało się pobrać historii konwersacji: {e}")
        history = []
    
    # Określ model do użycia - domyślny lub z trybu czatu
    model_to_use = CHAT_MODES[current_mode].get("model", DEFAULT_MODEL)
    
    # Jeśli użytkownik wybrał konkretny model, użyj go
    if 'user_data' in context.chat_data and user_id in context.chat_data['user_data']:
        user_data = context.chat_data['user_data'][user_id]
        if 'current_model' in user_data:
            model_to_use = user_data['current_model']
            # Aktualizuj koszt kredytów na podstawie modelu
            credit_cost = CREDIT_COSTS["message"].get(model_to_use, CREDIT_COSTS["message"]["default"])
    
    # Przygotuj system prompt z wybranego trybu
    system_prompt = CHAT_MODES[current_mode]["prompt"]
    
    # Przygotuj wiadomości dla API OpenAI
    messages = prepare_messages_from_history(history, user_message, system_prompt)
    
    # Wyślij początkową pustą wiadomość, którą będziemy aktualizować
    response_message = await update.message.reply_text(get_text("generating_response", language, default="Generowanie odpowiedzi..."))
    
    # Zainicjuj pełną odpowiedź
    full_response = ""
    buffer = ""
    last_update = datetime.datetime.now().timestamp()
    
    # Spróbuj wygenerować odpowiedź
    try:
        # Generuj odpowiedź strumieniowo
        async for chunk in chat_completion_stream(messages, model=model_to_use):
            full_response += chunk
            buffer += chunk
            
            # Aktualizuj wiadomość co 1 sekundę lub gdy bufor jest wystarczająco duży
            current_time = datetime.datetime.now().timestamp()
            if current_time - last_update >= 1.0 or len(buffer) > 100:
                try:
                    # Dodaj migający kursor na końcu wiadomości
                    await response_message.edit_text(full_response + "▌", parse_mode=ParseMode.MARKDOWN)
                    buffer = ""
                    last_update = current_time
                except Exception as e:
                    logger.debug(f"Nieistotny błąd przy aktualizacji: {e}")
        
        # Aktualizuj wiadomość z pełną odpowiedzią bez kursora
        try:
            await response_message.edit_text(full_response, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await response_message.edit_text(full_response)
        
        # Zapisz odpowiedź do bazy danych
        try:
            await save_message(conversation_id, user_id, full_response, is_from_user=False, model_used=model_to_use)
        except Exception as e:
            logger.warning(f"Nie udało się zapisać odpowiedzi do bazy: {e}")
        
        # Odejmij kredyty
        try:
            await deduct_user_credits(user_id, credit_cost, get_text("message_model", language, model=model_to_use, default=f"Wiadomość ({model_to_use})"))
        except Exception as e:
            logger.warning(f"Nie udało się odjąć kredytów: {e}")
    except Exception as e:
        logger.error(f"Błąd generowania odpowiedzi: {e}")
        await response_message.edit_text(get_text("response_error", language, error=str(e), default=f"Wystąpił błąd podczas generowania odpowiedzi: {str(e)}"))
        return
    
    # Sprawdź aktualny stan kredytów
    try:
        credits = get_user_credits(user_id)
        if credits < 5:
            # Dodaj przycisk doładowania kredytów
            keyboard = [[InlineKeyboardButton(get_text("buy_credits_btn_with_icon", language, default="🛒 Kup kredyty"), callback_data="menu_credits_buy")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"*{get_text('low_credits_warning', language, default='Uwaga: Niski stan kredytów!')}* {get_text('low_credits_message', language, credits=credits, default=f'Pozostało tylko {credits} kredytów.')}",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.warning(f"Nie udało się sprawdzić stanu kredytów: {e}")
    
    # Zwiększ licznik wykorzystanych wiadomości
    try:
        await increment_messages_used(user_id)
    except Exception as e:
        logger.warning(f"Nie udało się zwiększyć licznika wiadomości: {e}")