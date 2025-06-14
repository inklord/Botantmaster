import asyncio
import aiohttp
import json
import logging
from urllib.parse import quote
from typing import Dict, List, Optional, Tuple
import re
import hashlib

logger = logging.getLogger(__name__)

class TranslationManager:
    def __init__(self, database):
        self.db = database
        self.session = None
        
        # Idiomas soportados con sus códigos y nombres
        self.supported_languages = {
            'en': {'name': 'English', 'flag': '🇺🇸'},
            'pt': {'name': 'Português', 'flag': '🇧🇷'},
            'fr': {'name': 'Français', 'flag': '🇫🇷'},
            'de': {'name': 'Deutsch', 'flag': '🇩🇪'},
            'it': {'name': 'Italiano', 'flag': '🇮🇹'},
            'ru': {'name': 'Русский', 'flag': '🇷🇺'},
            'zh': {'name': '中文', 'flag': '🇨🇳'},
            'ja': {'name': '日本語', 'flag': '🇯🇵'},
            'ko': {'name': '한국어', 'flag': '🇰🇷'},
            'ar': {'name': 'العربية', 'flag': '��🇦'},
            'es': {'name': 'Hablo Español', 'flag': '🇪🇸'}
        }
        
        # Initialize session when needed instead of in __init__
        # asyncio.create_task(self.init_session())

    async def init_session(self):
        """Inicializa la sesión HTTP para traducción"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close_session(self):
        """Cierra la sesión HTTP"""
        if self.session:
            await self.session.close()

    def should_translate_text(self, text: str) -> bool:
        """Determina si un texto debe ser traducido"""
        # No traducir si es muy corto
        if len(text.strip()) < 3:
            return False
            
        # No traducir si solo contiene URLs, menciones o hashtags
        if re.match(r'^[@#]|^https?://', text.strip()):
            return False
            
        # No traducir si solo contiene emojis
        if re.match(r'^[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\s]+$', text):
            return False
            
        # No traducir comandos
        if text.strip().startswith('/'):
            return False
            
        return True

    async def detect_language(self, text: str) -> str:
        """Detecta el idioma de un texto usando Google Translate"""
        try:
            if not self.session:
                await self.init_session()
                
            # URL para detección de idioma
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': 'auto',
                'tl': 'es',
                'dt': 't',
                'q': text[:500]  # Limitar a 500 caracteres para detección
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.text()
                    # Parsear respuesta JSON
                    data = json.loads(result)
                    detected_lang = data[2] if len(data) > 2 else 'es'
                    return detected_lang
                    
        except Exception as e:
            logger.error(f"Error detectando idioma: {str(e)}")
            
        return 'es'  # Por defecto español

    async def translate_text(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """Traduce texto usando Google Translate"""
        try:
            # No traducir si los idiomas son iguales
            if source_lang == target_lang:
                return text
                
            # Verificar caché primero
            cached = self.db.get_cached_translation(text, source_lang, target_lang)
            if cached:
                return cached
                
            if not self.session:
                await self.init_session()
                
            # URL de Google Translate
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': source_lang,
                'tl': target_lang,
                'dt': 't',
                'q': text
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    result = await response.text()
                    # Parsear respuesta JSON
                    data = json.loads(result)
                    
                    if data and data[0]:
                        # Combinar todas las traducciones
                        translated_parts = []
                        for part in data[0]:
                            if part[0]:
                                translated_parts.append(part[0])
                        
                        translated_text = ''.join(translated_parts)
                        
                        # Guardar en caché
                        self.db.cache_translation(text, source_lang, target_lang, translated_text)
                        
                        return translated_text
                        
        except Exception as e:
            logger.error(f"Error traduciendo texto: {str(e)}")
            
        return None

    async def translate_for_user(self, text: str, user_id: int, chat_id: int, 
                               source_lang: str = None) -> Optional[str]:
        """Traduce un texto para un usuario específico según sus preferencias"""
        try:
            # Obtener idioma del usuario
            user_lang_info = self.db.get_user_language(user_id, chat_id)
            
            if not user_lang_info or user_lang_info['is_spanish_native']:
                return None  # Usuario habla español, no necesita traducción
                
            target_lang = user_lang_info['language_code']
            
            # Detectar idioma si no se proporciona
            if not source_lang:
                source_lang = await self.detect_language(text)
                
            # Traducir
            return await self.translate_text(text, source_lang, target_lang)
            
        except Exception as e:
            logger.error(f"Error traduciendo para usuario {user_id}: {str(e)}")
            return None

    async def translate_to_spanish(self, text: str, source_lang: str = None) -> Optional[str]:
        """Traduce un texto al español"""
        try:
            # Detectar idioma si no se proporciona
            if not source_lang:
                source_lang = await self.detect_language(text)
                
            # Si ya está en español, no traducir
            if source_lang in ['es', 'es-ES']:
                return None
                
            return await self.translate_text(text, source_lang, 'es')
            
        except Exception as e:
            logger.error(f"Error traduciendo al español: {str(e)}")
            return None

    def get_language_keyboard(self):
        """Genera teclado inline para selección de idioma"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        # Crear botones en filas de 2
        row = []
        for code, info in self.supported_languages.items():
            if code == 'es':  # Skip Spanish since it's the default
                continue
                
            button = InlineKeyboardButton(
                text=f"{info['flag']} {info['name']}",
                callback_data=f"lang:{code}"
            )
            
            row.append(button)
            
            if len(row) == 2:
                keyboard.inline_keyboard.append(row)
                row = []
        
        # Agregar última fila si tiene botones
        if row:
            keyboard.inline_keyboard.append(row)
            
        # Botón para indicar que habla español
        spanish_button = InlineKeyboardButton(
            text="🇪🇸 Hablo Español",
            callback_data="lang:es"
        )
        keyboard.inline_keyboard.append([spanish_button])
        
        return keyboard

    async def process_message_translation(self, message, bot):
        """Procesa un mensaje para traducir automáticamente"""
        try:
            text = message.text
            if not text or not self.should_translate_text(text):
                return
                
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Verificar si el usuario tiene idioma configurado
            user_lang_info = self.db.get_user_language(user_id, chat_id)
            
            # Si el usuario no tiene idioma configurado, es español por defecto
            if not user_lang_info:
                # Detectar idioma del mensaje
                detected_lang = await self.detect_language(text)
                
                # Si no es español, traducir para todos los usuarios no hispanohablantes
                if detected_lang not in ['es', 'es-ES']:
                    await self._translate_for_spanish_users(text, detected_lang, chat_id, bot, message.message_id)
                    
            else:
                # Usuario tiene idioma configurado
                if not user_lang_info['is_spanish_native']:
                    # Usuario no hispanohablante - traducir su mensaje al español para otros
                    detected_lang = await self.detect_language(text)
                    if detected_lang not in ['es', 'es-ES']:
                        await self._translate_for_spanish_users(text, detected_lang, chat_id, bot, message.message_id)
                else:
                    # Usuario hispanohablante - traducir para usuarios no hispanohablantes
                    await self._translate_for_non_spanish_users(text, 'es', chat_id, user_id, bot, message.message_id)
                    
        except Exception as e:
            logger.error(f"Error procesando traducción de mensaje: {str(e)}")

    async def _translate_for_spanish_users(self, text: str, source_lang: str, chat_id: int, bot, original_message_id: int):
        """Traduce un mensaje al español y lo envía como respuesta"""
        try:
            translated = await self.translate_text(text, source_lang, 'es')
            if translated and translated != text:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"🔄 <i>{translated}</i>",
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=original_message_id
                )
        except Exception as e:
            logger.error(f"Error enviando traducción al español: {str(e)}")

    async def _translate_for_non_spanish_users(self, text: str, source_lang: str, chat_id: int, 
                                             exclude_user_id: int, bot, original_message_id: int):
        """Traduce un mensaje para usuarios no hispanohablantes"""
        try:
            # Obtener usuarios que necesitan traducción
            users_for_translation = self.db.get_users_for_translation(chat_id, exclude_user_id)
            
            # Agrupar usuarios por idioma para optimizar traducciones
            users_by_lang = {}
            for user in users_for_translation:
                lang = user['language_code']
                if lang not in users_by_lang:
                    users_by_lang[lang] = []
                users_by_lang[lang].append(user['user_id'])
            
            # Traducir y enviar para cada idioma
            for target_lang, user_ids in users_by_lang.items():
                translated = await self.translate_text(text, source_lang, target_lang)
                if translated and translated != text:
                    # Enviar mensaje privado a cada usuario
                    for user_id in user_ids:
                        try:
                            flag = self.supported_languages.get(target_lang, {}).get('flag', '🌐')
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"{flag} <i>{translated}</i>\n\n"
                                     f"<b>Mensaje original en el grupo:</b> {text}",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            # Si falla el mensaje privado, usuario probablemente no inició bot
                            logger.debug(f"No se pudo enviar traducción privada a {user_id}: {str(e)}")
                            
        except Exception as e:
            logger.error(f"Error enviando traducciones a usuarios: {str(e)}")

    async def setup_database_tables(self):
        """Configura las tablas de base de datos necesarias"""
        self.db.create_translation_tables()
        logger.info("Sistema de traducción inicializado") 