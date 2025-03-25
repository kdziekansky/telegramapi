# utils/openai_client.py
from services.api_service import APIService
import logging

logger = logging.getLogger(__name__)

# Utworzenie globalnej instancji
api_service = APIService()

# Funkcje kompatybilne ze starym kodem
async def chat_completion(messages, model=None):
    """Funkcja dla kompatybilności wstecznej"""
    return await api_service.chat_completion_text(messages, model)

async def chat_completion_stream(messages, model=None):
    """
    Funkcja dla kompatybilności wstecznej zwracająca asynchroniczny generator
    """
    try:
        # Zaktualizowana lista modeli Claude
        claude_models = [
            "claude-3-5-sonnet-20240307", 
            "claude-3-haiku-20240307", 
            "claude-3-sonnet-20240229", 
            "claude-3-opus-20240229"
        ]
        
        # Sprawdź czy stare nazwy modeli Claude i mapuj je na nowe
        claude_model_mapping = {
            "claude-3-5-sonnet": "claude-3-5-sonnet-20240307",
            "claude-3-5-haiku": "claude-3-haiku-20240307", 
            "claude-3-haiku": "claude-3-haiku-20240307",
            "claude-3-sonnet": "claude-3-sonnet-20240229",
            "claude-3-opus": "claude-3-opus-20240229"
        }
        
        # Automatycznie koryguj stare nazwy modeli
        if model in claude_model_mapping:
            logger.info(f"Konwersja nazwy modelu z {model} na {claude_model_mapping[model]}")
            model = claude_model_mapping[model]
        
        if model in claude_models:
            logger.info(f"Używam API Anthropic dla modelu {model}")
            # Użyj API service do obsługi modelu Claude
            async for chunk in api_service.chat_completion_stream(messages, model):
                yield chunk
        else:
            # Bezpośrednie utworzenie klienta OpenAI dla modeli OpenAI
            logger.info(f"Używam bezpośrednio API OpenAI dla modelu {model or 'gpt-4o'}")
            from openai import AsyncOpenAI
            
            from config import OPENAI_API_KEY
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            
            response = await client.chat.completions.create(
                model=model or "gpt-4o",
                messages=messages,
                stream=True
            )
            
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
    except Exception as e:
        logger.error(f"Błąd w chat_completion_stream: {e}")
        yield "Wystąpił błąd podczas generowania odpowiedzi."

async def generate_image_dall_e(prompt):
    """Funkcja dla kompatybilności wstecznej"""
    return await api_service.generate_image(prompt)

async def analyze_document(file_bytes, file_name, mode="analyze", target_language=None):
    """Funkcja dla kompatybilności wstecznej"""
    return await api_service.document_service.analyze(file_bytes, file_name, mode, target_language)

async def analyze_image(file_bytes, file_name, mode="analyze", target_language=None):
    """Funkcja dla kompatybilności wstecznej"""
    return await api_service.document_service.analyze_image(file_bytes, file_name, mode, target_language)

def prepare_messages_from_history(history, user_message, system_prompt):
    """
    Przygotowuje wiadomości dla API OpenAI na podstawie historii konwersacji
    
    Wspiera zarówno obiekty Message jak i słowniki
    """
    messages = [{"role": "system", "content": system_prompt}]
    
    # Dodaj historię konwersacji
    for msg in history:
        # Sprawdzamy typ obiektu i odpowiednio pobieramy dane
        if hasattr(msg, 'is_from_user') and hasattr(msg, 'content'):
            # Obiekt Message
            role = "user" if msg.is_from_user else "assistant"
            content = msg.content
        else:
            # Słownik
            role = "user" if msg.get("is_from_user", False) else "assistant"
            content = msg.get("content", "")
        
        messages.append({"role": role, "content": content})
    
    # Dodaj bieżącą wiadomość użytkownika
    messages.append({"role": "user", "content": user_message})
    
    return messages