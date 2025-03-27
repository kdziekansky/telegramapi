from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import BOT_NAME, AVAILABLE_MODELS, CREDIT_COSTS
from utils.translations import get_text
from utils.user_utils import get_user_language, mark_chat_initialized
from database.supabase_client import create_new_conversation, get_active_conversation, get_message_status
from database.credits_client import get_user_credits
from utils.menu import get_navigation_path


async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Obsługa komendy /restart
    Resetuje kontekst bota, pokazuje informacje o bocie i aktualnych ustawieniach użytkownika
    """
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        language = get_user_language(context, user_id)
        
        conversation = create_new_conversation(user_id)
        
        user_data = {}
        if 'user_data' in context.chat_data and user_id in context.chat_data['user_data']:
            # Pobieramy tylko podstawowe ustawienia, reszta jest resetowana
            old_user_data = context.chat_data['user_data'][user_id]
            if 'language' in old_user_data:
                user_data['language'] = old_user_data['language']
            if 'current_model' in old_user_data:
                user_data['current_model'] = old_user_data['current_model']
            if 'current_mode' in old_user_data:
                user_data['current_mode'] = old_user_data['current_mode']
        
        if 'user_data' not in context.chat_data:
            context.chat_data['user_data'] = {}
        context.chat_data['user_data'][user_id] = user_data
        
        language = get_user_language(context, user_id)
        
        restart_message = get_text("restart_command", language)
        
        keyboard = [
            [
                InlineKeyboardButton(get_text("menu_chat_mode", language), callback_data="menu_section_chat_modes"),
                InlineKeyboardButton(get_text("image_generate", language), callback_data="menu_image_generate")
            ],
            [
                InlineKeyboardButton(get_text("menu_credits", language), callback_data="menu_section_credits"),
                InlineKeyboardButton(get_text("menu_dialog_history", language), callback_data="menu_section_history")
            ],
            [
                InlineKeyboardButton(get_text("menu_settings", language), callback_data="menu_section_settings"),
                InlineKeyboardButton(get_text("menu_help", language), callback_data="menu_help")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            welcome_text = get_text("welcome_message", language, bot_name=BOT_NAME)
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=restart_message + "\n\n" + welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            from handlers.menu_handler import store_menu_state
            store_menu_state(context, user_id, 'main', message.message_id)
        except Exception as e:
            print(f"Błąd przy wysyłaniu wiadomości po restarcie: {e}")
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=restart_message
                )
            except Exception as e2:
                print(f"Nie udało się wysłać nawet prostej wiadomości: {e2}")
        
    except Exception as e:
        print(f"Błąd w funkcji restart_command: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=get_text("restart_error", get_user_language(context, update.effective_user.id))
            )
        except Exception as e2:
            print(f"Błąd przy wysyłaniu wiadomości o błędzie: {e2}")

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obsługuje komendę /models - otwiera menu wyboru modelu AI"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    message_text = f"*{get_navigation_path('settings', language)} > {get_text('settings_choose_model', language)}*\n\n"
    message_text += get_text("settings_choose_model", language, default="Wybierz model AI:")
    
    standard_openai_models = ["gpt-3.5-turbo", "o3-mini"]
    premium_openai_models = ["gpt-4o", "gpt-4", "o1"]
    standard_claude_models = ["claude-3-5-haiku-20241022", "claude-3-haiku-20240307"]
    premium_claude_models = ["claude-3-7-sonnet-20250219", "claude-3-opus-20240229", 
                           "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-20240620"]
    
    message_text += "\n\n*🤖 " + get_text("openai_standard_models", language, default="OpenAI - Modele standardowe") + ":*"
    message_text += "\n\n*🤖 " + get_text("openai_premium_models", language, default="OpenAI - Modele premium") + ":*"
    message_text += "\n\n*🤖 " + get_text("claude_standard_models", language, default="Claude - Modele standardowe") + ":*"
    message_text += "\n\n*🤖 " + get_text("claude_premium_models", language, default="Claude - Modele premium") + ":*"
    
    buttons = []
    
    def add_model_buttons(model_ids, is_premium=False):
        for model_id in model_ids:
            if model_id in AVAILABLE_MODELS:
                model_name = AVAILABLE_MODELS[model_id]
                credit_cost = CREDIT_COSTS["message"].get(model_id, CREDIT_COSTS["message"]["default"])
                prefix = "⭐ " if is_premium else ""
                buttons.append([
                    InlineKeyboardButton(
                        f"{prefix}{model_name} ({credit_cost} {get_text('credits_per_message', language)})",
                        callback_data=f"model_{model_id}"
                    )
                ])
    
    add_model_buttons(standard_openai_models)
    add_model_buttons(premium_openai_models, is_premium=True)
    add_model_buttons(standard_claude_models)
    add_model_buttons(premium_claude_models, is_premium=True)
    
    buttons.append([InlineKeyboardButton(get_text("back", language), callback_data="menu_section_settings")])
    
    reply_markup = InlineKeyboardMarkup(buttons)
    
    message = await update.message.reply_text(
        message_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    store_menu_state(context, user_id, 'model_selection', message.message_id)

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sprawdza status konta użytkownika
    Użycie: /status
    """
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    credits = get_user_credits(user_id)
    
    from config import CHAT_MODES, BOT_NAME
    current_mode = get_text("no_mode", language)
    current_mode_cost = 1
    if 'user_data' in context.chat_data and user_id in context.chat_data['user_data']:
        user_data = context.chat_data['user_data'][user_id]
        if 'current_mode' in user_data and user_data['current_mode'] in CHAT_MODES:
            mode_id = user_data['current_mode']
            current_mode = get_text(f"chat_mode_{mode_id}", language, default=CHAT_MODES[mode_id]["name"])
            current_mode_cost = CHAT_MODES[mode_id]["credit_cost"]
    
    from config import DEFAULT_MODEL, AVAILABLE_MODELS
    current_model = DEFAULT_MODEL
    if 'user_data' in context.chat_data and user_id in context.chat_data['user_data']:
        user_data = context.chat_data['user_data'][user_id]
        if 'current_model' in user_data and user_data['current_model'] in AVAILABLE_MODELS:
            current_model = user_data['current_model']
    
    model_name = AVAILABLE_MODELS.get(current_model, get_text("unknown_model", language, default="Unknown Model"))
    
    message_status = await get_message_status(user_id)
    
    message = f"""
*{get_text("status_command", language, bot_name=BOT_NAME)}*

{get_text("available_credits", language)}: *{credits}*
{get_text("current_mode", language)}: *{current_mode}* ({get_text("cost", language)}: {current_mode_cost} {get_text("credits_per_message", language)})
{get_text("current_model", language)}: *{model_name}*

{get_text("messages_info", language)}:
- {get_text("messages_used", language)}: *{message_status["messages_used"]}*
- {get_text("messages_limit", language)}: *{message_status["messages_limit"]}*
- {get_text("messages_left", language)}: *{message_status["messages_left"]}*

{get_text("operation_costs", language)}:
- {get_text("standard_message", language)} (GPT-3.5): 1 {get_text("credit", language)}
- {get_text("premium_message", language)} (GPT-4o): 3 {get_text("credits", language)}
- {get_text("expert_message", language)} (GPT-4): 5 {get_text("credits", language)}
- {get_text("dalle_image", language)}: 10-15 {get_text("credits", language)}
- {get_text("document_analysis", language)}: 5 {get_text("credits", language)}
- {get_text("photo_analysis", language)}: 8 {get_text("credits", language)}

{get_text("buy_more_credits", language)}: /buy
"""
    
    keyboard = [
        [InlineKeyboardButton(get_text("buy_credits_btn", language), callback_data="menu_credits_buy")],
        [InlineKeyboardButton("⬅️ " + get_text("back_to_main_menu", language, default="Powrót do menu głównego"), callback_data="menu_back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        print(f"Błąd formatowania w check_status: {e}")
        await update.message.reply_text(message, reply_markup=reply_markup)

async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rozpoczyna nową konwersację z ulepszonym interfejsem"""
    user_id = update.effective_user.id
    language = get_user_language(context, user_id)
    
    conversation = await create_new_conversation(user_id)
    
    if conversation:
        mark_chat_initialized(context, user_id)
        
        from config import DEFAULT_MODEL, AVAILABLE_MODELS, CHAT_MODES, CREDIT_COSTS
        
        current_mode = "no_mode"
        model_to_use = DEFAULT_MODEL
        credit_cost = CREDIT_COSTS["message"].get(model_to_use, 1)
        
        if 'user_data' in context.chat_data and user_id in context.chat_data['user_data']:
            user_data = context.chat_data['user_data'][user_id]
            
            if 'current_mode' in user_data and user_data['current_mode'] in CHAT_MODES:
                current_mode = user_data['current_mode']
                model_to_use = CHAT_MODES[current_mode].get("model", DEFAULT_MODEL)
                credit_cost = CHAT_MODES[current_mode]["credit_cost"]
            
            if 'current_model' in user_data and user_data['current_model'] in AVAILABLE_MODELS:
                model_to_use = user_data['current_model']
                credit_cost = CREDIT_COSTS["message"].get(model_to_use, CREDIT_COSTS["message"]["default"])
        
        model_name = AVAILABLE_MODELS.get(model_to_use, get_text("unknown_model", language, default="Nieznany model"))
        
        base_message = get_text("new_chat_created_message", language, default="✅ Utworzono nową rozmowę. Możesz zacząć pisać!")
        model_info = get_text("model_info", language, model=model_name, cost=credit_cost, default=f"Używasz modelu {model_name} za {credit_cost} kredyt(ów) za wiadomość")
        
        keyboard = [
            [InlineKeyboardButton("🤖 " + get_text("select_model", language, default="Wybierz model czatu"), callback_data="menu_section_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            base_message + " " + model_info,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            get_text("new_chat_error", language),
            parse_mode=ParseMode.MARKDOWN
        )