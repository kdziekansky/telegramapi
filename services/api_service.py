# services/api_service.py
import logging
from typing import Dict, List, AsyncGenerator
from api.openai_client import OpenAIClient
from api.anthropic_client import AnthropicClient
from api.supabase_client import SupabaseClient
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, DEFAULT_MODEL, SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

class APIService:
    """Centralny serwis API zapewniający dostęp do wszystkich zewnętrznych API"""
    
    def __init__(self):
        self.openai = OpenAIClient(api_key=OPENAI_API_KEY)
        self.anthropic = AnthropicClient(api_key=ANTHROPIC_API_KEY)
        self.supabase = SupabaseClient(url=SUPABASE_URL, key=SUPABASE_KEY)
        
        # Zaktualizowana lista modeli Claude
        self.claude_models = [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022", 
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-haiku-20240307"
        ]
        
        logger.info("Serwis API zainicjalizowany")
        logger.info(f"Zarejestrowane modele Claude: {self.claude_models}")
    
    async def chat_completion_text(self, messages: List[Dict[str, str]], model: str = DEFAULT_MODEL) -> str:
        """Generuje odpowiedź czatu i zwraca tekst"""
        if model in self.claude_models:
            return await self.anthropic.chat_completion_text(messages, model)
        else:
            return await self.openai.chat_completion_text(messages, model)
    
    async def chat_completion_stream(self, messages: List[Dict[str, str]], model: str = DEFAULT_MODEL) -> AsyncGenerator[str, None]:
        """Generuje strumieniową odpowiedź czatu"""
        try:
            # Dodane logowanie aby ułatwić debugowanie
            logger.info(f"API Service: Używam modelu: {model}, sprawdzam czy to Claude: {model in self.claude_models}")
            
            if model in self.claude_models:
                logger.info(f"API Service: Przekierowuję do klienta Anthropic dla modelu {model}")
                async for chunk in self.anthropic.chat_completion_stream(messages, model):
                    yield chunk
            else:
                logger.info(f"API Service: Przekierowuję do klienta OpenAI dla modelu {model}")
                async for chunk in self.openai.chat_completion_stream(messages, model):
                    yield chunk
        except Exception as e:
            logger.error(f"Błąd w chat_completion_stream: {e}", exc_info=True)
            yield f"Wystąpił błąd: {str(e)}"
    
    async def generate_image(self, prompt: str) -> str:
        """Generuje obraz za pomocą DALL-E"""
        return await self.openai.generate_image(prompt)