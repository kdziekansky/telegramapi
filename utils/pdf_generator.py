# utils/pdf_generator.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import datetime
import re
import unicodedata

def generate_conversation_pdf(conversation, user_info, bot_name="AI Bot"):
    """
    Generuje plik PDF z historią konwersacji
    
    Args:
        conversation (list): Lista wiadomości z konwersacji
        user_info (dict): Informacje o użytkowniku
        bot_name (str): Nazwa bota
        
    Returns:
        BytesIO: Bufor zawierający wygenerowany plik PDF
    """
    buffer = io.BytesIO()
    
    # Rejestracja fontów z obsługą Unicode
    try:
        # Sprawdź czy font DejaVu jest dostępny (ma obsługę polskich znaków)
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        
        if not os.path.exists(font_dir):
            os.makedirs(font_dir)
            
        dejavu_regular = os.path.join(font_dir, "DejaVuSans.ttf")
        dejavu_bold = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
        
        if os.path.exists(dejavu_regular) and os.path.exists(dejavu_bold):
            pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_regular))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_bold))
            main_font = 'DejaVuSans'
            bold_font = 'DejaVuSans-Bold'
        else:
            main_font = 'Helvetica'
            bold_font = 'Helvetica-Bold'
    except:
        main_font = 'Helvetica'
        bold_font = 'Helvetica-Bold'
    
    # Konfiguracja dokumentu
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
        title=f"Konwersacja z {bot_name}",
        encoding='utf-8'
    )
    
    # Style
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='UserMessage',
        parent=styles['Normal'],
        fontName=bold_font,
        spaceAfter=6,
        firstLineIndent=0,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        name='BotMessage',
        parent=styles['Normal'],
        fontName=main_font,
        leftIndent=20,
        spaceAfter=12,
        firstLineIndent=0
    ))
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Title'],
        fontName=bold_font,
        alignment=1,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name='CustomItalic',
        parent=styles['Italic'],
        fontName=main_font,
        spaceAfter=6
    ))
    
    # Funkcja do przetwarzania tekstu - zamiana znaków diakrytycznych
    def process_text(text):
        if not text:
            return ""
        # Konwertuj do string
        text = str(text)
        
        # Usuń znaczniki Markdown
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
        text = re.sub(r'__(.*?)__', r'\1', text)      # Underline
        text = re.sub(r'_([^_]+)_', r'\1', text)      # Italic
        text = re.sub(r'~~(.*?)~~', r'\1', text)      # Strikethrough
        text = re.sub(r'`([^`]+)`', r'\1', text)      # Inline code
        text = re.sub(r'```(?:.|\n)*?```', r'[Code block]', text)  # Code block
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1', text)  # Links
        
        # Zamień polskie znaki na ASCII
        nfkd_form = unicodedata.normalize('NFKD', text)
        text = ''.join([c for c in nfkd_form if not unicodedata.combining(c)])
        
        # Escapuj znaki HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        return text
    
    # Elementy dokumentu
    elements = []
    
    # Nagłówek
    title = process_text(f"Konwersacja z {bot_name}")
    elements.append(Paragraph(title, styles['CustomTitle']))
    
    # Metadane
    current_time = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    metadata_text = process_text(f"Eksportowano: {current_time}")
    
    # Dodaj informacje o użytkowniku jeśli są dostępne
    username = None
    if isinstance(user_info, dict):
        username = user_info.get('username')
    elif hasattr(user_info, 'username'):
        username = user_info.username
        
    if username:
        metadata_text += f"<br/>{process_text('Uzytkownik')}: {process_text(username)}"
        
    elements.append(Paragraph(metadata_text, styles['CustomItalic']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Treść konwersacji
    for msg in conversation:
        try:
            # Sprawdź czy mamy obiekt czy słownik
            if hasattr(msg, 'is_from_user'):
                # Obiekt Message
                is_from_user = msg.is_from_user
                content = msg.content
                created_at = getattr(msg, 'created_at', None)
            else:
                # Słownik
                is_from_user = msg.get('is_from_user', False)
                content = msg.get('content', '')
                created_at = msg.get('created_at', None)
            
            if is_from_user:
                icon = "👤 "  # Ikona użytkownika
                style = styles['UserMessage']
                content_text = f"{icon}{process_text('Ty')}: {process_text(content)}"
            else:
                icon = "🤖 "  # Ikona bota
                style = styles['BotMessage']
                content_text = f"{icon}{process_text(bot_name)}: {process_text(content)}"
            
            # Dodaj datę i godzinę wiadomości, jeśli są dostępne
            if created_at:
                try:
                    # Konwersja formatu daty
                    if isinstance(created_at, str) and 'T' in created_at:
                        dt = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        time_str = dt.strftime("%d-%m-%Y %H:%M")
                        content_text += f"<br/><font size=8 color=gray>{time_str}</font>"
                except:
                    pass
            
            elements.append(Paragraph(content_text, style))
        except Exception as e:
            # W przypadku błędu dodaj informację
            elements.append(Paragraph(f"Blad formatowania wiadomosci: {str(e)}", styles['Normal']))
    
    # Stopka
    elements.append(Spacer(1, 1*cm))
    footer_text = process_text(f"Wygenerowano przez {bot_name} • {current_time}")
    elements.append(Paragraph(footer_text, styles['CustomItalic']))
    
    # Wygeneruj dokument
    doc.build(elements)
    
    # Zresetuj pozycję w buforze i zwróć go
    buffer.seek(0)
    return buffer