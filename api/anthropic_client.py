# api/anthropic_client.py
import asyncio
import time
import logging
from typing import List, Dict, Any, AsyncGenerator
from api.base_client import APIClient
from config import ANTHROPIC_API_KEY
from utils.translations import get_text

logger = logging.getLogger(__name__)

class AnthropicClient(APIClient):
    """Klient API Anthropic (Claude) z obsługą błędów i ponawianiem"""
    
    def __init__(self, api_key: str = ANTHROPIC_API_KEY, max_retries: int = 3, retry_delay: float = 1.0):
        super().__init__(max_retries, retry_delay)
        from httpx import AsyncClient
        from anthropic import AsyncAnthropic
        
        self.client = AsyncAnthropic(api_key=api_key)
        logger.info(f"Klient Anthropic zainicjalizowany z kluczem API: {'ważny' if api_key else 'brak'}")
    
    async def chat_completion(self, messages: List[Dict[str, str]], model: str = "claude-3-7-sonnet-20250219", stream: bool = False, **kwargs) -> Any:
        """Generuje odpowiedź czatu z API Anthropic"""
        try:
            # Dodajemy logowanie dla lepszego debugowania
            logger.info(f"Anthropic API: Używam modelu {model}, stream={stream}")
            
            # Wyodrębnij wiadomość systemową
            system_prompt = None
            user_messages = messages.copy()
            
            if messages and messages[0]['role'] == 'system':
                system_prompt = messages[0]['content']
                user_messages = messages[1:]
            
            # Konwersja formatu wiadomości z OpenAI na format Anthropic
            anthropic_messages = self._convert_to_anthropic_format(user_messages)
            
            # Wysyłanie zapytania
            return await self._request_with_retry(
                self._make_anthropic_request,
                model=model,
                messages=anthropic_messages,
                system=system_prompt,
                stream=stream,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Błąd API Anthropic: {str(e)}", exc_info=True)
            raise
    
    async def _make_anthropic_request(self, model: str, messages: List[Dict], system=None, stream: bool = False, **kwargs):
        """Wykonuje właściwe zapytanie do API Anthropic"""
        max_tokens = kwargs.pop('max_tokens', 4096)
        temperature = kwargs.pop('temperature', 0.7)
        
        try:
            if stream:
                response = await self.client.messages.create(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                    **kwargs
                )
                return response
            else:
                response = await self.client.messages.create(
                    model=model,
                    messages=messages,
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                return response
        except Exception as e:
            logger.error(f"Błąd w _make_anthropic_request: {e}", exc_info=True)
            raise
    
    def _convert_to_anthropic_format(self, openai_messages: List[Dict[str, str]]) -> List[Dict]:
        """Konwertuje format wiadomości OpenAI na format Anthropic"""
        anthropic_messages = []
        
        # Konwertuj wiadomości
        for msg in openai_messages:
            role = "user" if msg['role'] == 'user' else "assistant"
            anthropic_messages.append({
                "role": role,
                "content": msg['content']
            })
        
        return anthropic_messages
    
    async def chat_completion_text(self, messages: List[Dict[str, str]], model: str = "claude-3-7-sonnet-20250219", language: str = "pl", **kwargs) -> str:
        """Generuje odpowiedź czatu i zwraca tekst"""
        system_prompt = None
        user_messages = messages.copy()
        
        if messages and messages[0]['role'] == 'system':
            system_prompt = messages[0]['content']
            user_messages = messages[1:]
            
        anthropic_messages = self._convert_to_anthropic_format(user_messages)
        
        try:
            logger.info(f"Anthropic API text: Używam modelu {model}")
            response = await self.client.messages.create(
                model=model,
                messages=anthropic_messages,
                system=system_prompt,
                max_tokens=kwargs.pop('max_tokens', 4096),
                temperature=kwargs.pop('temperature', 0.7),
                **kwargs
            )
            
            return response.content[0].text
        except Exception as e:
            logger.error(f"Błąd w chat_completion_text: {e}", exc_info=True)
            error_msg = get_text("response_error", language, error=str(e), default=f"Wystąpił błąd: {str(e)}")
            return error_msg
    
    async def chat_completion_stream(self, messages: List[Dict[str, str]], model: str = "claude-3-7-sonnet-20250219", language: str = "pl", **kwargs) -> AsyncGenerator[str, None]:
        """Generuje strumieniową odpowiedź czatu"""
        system_prompt = None
        user_messages = messages.copy()
        
        if messages and messages[0]['role'] == 'system':
            system_prompt = messages[0]['content']
            user_messages = messages[1:]
            
        anthropic_messages = self._convert_to_anthropic_format(user_messages)
        
        try:
            logger.info(f"Anthropic API stream: Używam modelu {model}")
            stream = await self.client.messages.create(
                model=model,
                messages=anthropic_messages,
                system=system_prompt,
                max_tokens=kwargs.pop('max_tokens', 4096),
                temperature=kwargs.pop('temperature', 0.7),
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                # Obsługa różnych typów zdarzeń ze strumienia Anthropic
                if hasattr(chunk, 'delta') and chunk.delta and hasattr(chunk.delta, 'text'):
                    # Format v2 API
                    yield chunk.delta.text
                elif hasattr(chunk, 'type') and chunk.type == 'content_block_delta':
                    # Format Claude 3 API
                    if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
                        yield chunk.delta.text
                elif hasattr(chunk, 'content_block') and chunk.content_block and hasattr(chunk.content_block, 'text'):
                    # Inny możliwy format
                    yield chunk.content_block.text
        except Exception as e:
            logger.error(f"Błąd w chat_completion_stream: {e}", exc_info=True)
            error_msg = get_text("stream_error", language, error=str(e), default=f"Wystąpił błąd podczas generowania odpowiedzi: {str(e)}")
            yield error_msg