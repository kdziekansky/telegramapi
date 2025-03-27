# services/document_service.py
import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from utils.translations import get_text

logger = logging.getLogger(__name__)

class DocumentService:
    """Serwis do analizy dokumentów i obrazów"""
    
    def __init__(self, openai_client, anthropic_client=None):
        """
        Inicjalizuje serwis dokumentów
        
        Args:
            openai_client: Klient API OpenAI
            anthropic_client: Opcjonalny klient Anthropic
        """
        self.openai_client = openai_client
        self.anthropic_client = anthropic_client
        logger.info("Serwis analizy dokumentów zainicjalizowany")
    
    async def analyze(self, file_bytes: bytes, file_name: str, mode: str = "analyze", target_language: Optional[str] = None, language: str = "pl") -> str:
        """
        Analizuje dokument
        
        Args:
            file_bytes: Bajty pliku
            file_name: Nazwa pliku
            mode: Tryb analizy ('analyze' lub 'translate')
            target_language: Język docelowy dla tłumaczenia
            language: Język komunikatów
            
        Returns:
            str: Wynik analizy
        """
        try:
            # Określ system_prompt w zależności od trybu
            if mode == "translate":
                system_prompt = get_text("document_translation_prompt", language, 
                                        target_lang=target_language, 
                                        default=f"Jesteś ekspertem tłumaczem. Przetłumacz tekst z dokumentu na język {target_language}. Zachowaj formatowanie.")
            else:
                system_prompt = get_text("document_analysis_prompt", language, 
                                        default="Jesteś asystentem analizującym dokumenty. Przeanalizuj treść dokumentu i przedstaw jego główne tezy, strukturę i kluczowe informacje.")
            
            extension = file_name.split('.')[-1].lower() if '.' in file_name else ''
            
            # Przygotuj bajty do wysłania
            if extension in ['pdf', 'doc', 'docx', 'txt']:
                try:
                    # Użyj Vision API dla PDFów, które mogą zawierać obrazy i tekst
                    if extension == 'pdf':
                        # Konwertuj bajty do base64
                        import base64
                        file_b64 = base64.b64encode(file_bytes).decode('utf-8')
                        
                        # Utwórz wiadomość dla modelu z obrazem
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user", 
                                "content": [
                                    {"type": "text", "text": get_text("document_analysis_request", language, default="Przeanalizuj ten dokument:")},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:application/pdf;base64,{file_b64}"
                                        }
                                    }
                                ]
                            }
                        ]
                        
                        response = await self.openai_client.client.chat.completions.create(
                            model="gpt-4o",
                            messages=messages,
                            max_tokens=4000
                        )
                        
                        return response.choices[0].message.content
                    else:
                        # Dla innych typów dokumentów, próbuj ekstrahować tekst
                        # (W rzeczywistej implementacji tutaj byłaby obsługa różnych typów dokumentów)
                        text_content = self._extract_text_from_document(file_bytes, extension)
                        
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text_content}
                        ]
                        
                        response = await self.openai_client.client.chat.completions.create(
                            model="gpt-4o",
                            messages=messages,
                            max_tokens=4000
                        )
                        
                        return response.choices[0].message.content
                except Exception as e:
                    logger.error(f"Błąd analizy dokumentu: {e}", exc_info=True)
                    return get_text("document_analysis_error", language, error=str(e), 
                                  default=f"Wystąpił błąd podczas analizy dokumentu: {str(e)}")
            else:
                return get_text("unsupported_document_format", language, format=extension,
                              default=f"Nieobsługiwany format dokumentu: {extension}")
        except Exception as e:
            logger.error(f"Globalny błąd analizy dokumentu: {e}", exc_info=True)
            return get_text("document_analysis_error", language, error=str(e),
                          default=f"Wystąpił błąd podczas analizy dokumentu: {str(e)}")
    
    async def analyze_image(self, file_bytes: bytes, file_name: str, mode: str = "analyze", target_language: Optional[str] = None, language: str = "pl") -> str:
        """
        Analizuje obraz
        
        Args:
            file_bytes: Bajty obrazu
            file_name: Nazwa pliku obrazu
            mode: Tryb analizy ('analyze' lub 'translate')
            target_language: Język docelowy dla tłumaczenia
            language: Język komunikatów
            
        Returns:
            str: Wynik analizy
        """
        try:
            # Określ system_prompt w zależności od trybu
            if mode == "translate":
                system_prompt = get_text("image_text_translation_prompt", language, 
                                        target_lang=target_language,
                                        default=f"Znajdź tekst na tym zdjęciu i przetłumacz go na język {target_language}. Zachowaj formatowanie.")
            else:
                system_prompt = get_text("image_analysis_prompt", language,
                                        default="Przeanalizuj to zdjęcie i szczegółowo opisz jego zawartość.")
            
            # Konwertuj bajty do base64
            import base64
            file_b64 = base64.b64encode(file_bytes).decode('utf-8')
            
            # Określ MIME type na podstawie rozszerzenia pliku
            extension = file_name.split('.')[-1].lower() if '.' in file_name else 'jpg'
            mime_type = self._get_mime_type(extension)
            
            # Utwórz wiadomość dla modelu z obrazem
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": get_text("image_analysis_request", language, default="Przeanalizuj ten obraz:")},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{file_b64}"
                            }
                        }
                    ]
                }
            ]
            
            # Wywołaj OpenAI API
            response = await self.openai_client.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"Błąd analizy obrazu: {e}", exc_info=True)
            return get_text("image_analysis_error", language, error=str(e),
                          default=f"Wystąpił błąd podczas analizy obrazu: {str(e)}")
    
    def _extract_text_from_document(self, file_bytes: bytes, extension: str) -> str:
        """
        Ekstrahuje tekst z dokumentu
        
        Args:
            file_bytes: Bajty dokumentu
            extension: Rozszerzenie pliku
            
        Returns:
            str: Ekstrahotwany tekst
        """
        # Tutaj byłaby faktyczna implementacja dla różnych typów dokumentów
        # Na razie zwracamy uproszczoną wersję
        import io
        
        if extension == 'txt':
            return io.BytesIO(file_bytes).read().decode('utf-8', errors='ignore')
        elif extension == 'pdf':
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n\n"
                return text
            except Exception as e:
                logger.error(f"Błąd ekstrakcji tekstu z PDF: {e}")
                return "Nie udało się odczytać tekstu z dokumentu PDF."
        else:
            return "Ekstrakcja tekstu dla tego formatu nie jest jeszcze zaimplementowana."
    
    def _get_mime_type(self, extension: str) -> str:
        """
        Zwraca typ MIME na podstawie rozszerzenia pliku
        
        Args:
            extension: Rozszerzenie pliku
            
        Returns:
            str: Typ MIME
        """
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
            'tiff': 'image/tiff',
            'tif': 'image/tiff'
        }
        
        return mime_types.get(extension.lower(), 'image/jpeg')