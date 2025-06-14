#!/usr/bin/env python3
"""
Script para convertir el código de aiogram 2.x a aiogram 3.x
"""
import re
import os

def upgrade_aiogram_file(file_path):
    """Convierte un archivo de aiogram 2.x a 3.x"""
    
    if not os.path.exists(file_path):
        print(f"❌ Archivo no encontrado: {file_path}")
        return False
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"🔄 Convirtiendo {file_path}...")
    
    # === IMPORTS ===
    # Arreglar imports principales
    content = content.replace(
        'from aiogram.dispatcher.filters import Command',
        'from aiogram.filters.command import Command'
    )
    content = content.replace(
        'from aiogram.utils.exceptions import TelegramAPIError, BotBlocked',
        'from aiogram.exceptions import TelegramAPIError, TelegramBadRequest'
    )
    
    # Añadir imports necesarios para aiogram 3.x
    if 'from aiogram.filters.command import Command' in content:
        # Agregar imports adicionales después de los imports existentes
        aiogram_imports = """from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    FSInputFile, Message, ReactionTypeEmoji,
    BufferedInputFile, InputMediaPhoto
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest"""
        
        content = content.replace(
            'from aiogram.filters.command import Command',
            f'from aiogram.filters.command import Command\n{aiogram_imports}'
        )
    
    # === DISPATCHER ===
    # Cambiar inicialización del dispatcher
    content = content.replace(
        'dp = Dispatcher(bot)',
        'dp = Dispatcher()'
    )
    
    # === DECORADORES ===
    # Convertir message_handler a message
    content = re.sub(r'@dp\.message_handler\(commands=\[([^\]]+)\]\)', r'@dp.message(Command(\1))', content)
    content = re.sub(r'@dp\.message_handler\(content_types=\[([^\]]+)\]\)', r'@dp.message(lambda message: message.\1)', content)
    content = re.sub(r'@dp\.message_handler\(\)', r'@dp.message()', content)
    
    # Convertir callback_query_handler a callback_query
    content = re.sub(r'@dp\.callback_query_handler\((.*?)\)', r'@dp.callback_query(\1)', content)
    
    # === TIPOS ===
    # Usar tipos directos en lugar de types.Tipo
    content = content.replace('types.InlineKeyboardMarkup', 'InlineKeyboardMarkup')
    content = content.replace('types.InlineKeyboardButton', 'InlineKeyboardButton')
    content = content.replace('types.Message', 'Message')
    content = content.replace('types.CallbackQuery', 'CallbackQuery')
    
    # === PARSE MODE ===
    # Convertir parse_mode a enum
    content = content.replace('parse_mode="HTML"', 'parse_mode=ParseMode.HTML')
    content = content.replace('parse_mode="MARKDOWN"', 'parse_mode=ParseMode.MARKDOWN')
    content = content.replace('parse_mode="Markdown"', 'parse_mode=ParseMode.MARKDOWN')
    
    # === POLLING ===
    # Cambiar start_polling
    content = content.replace('await dp.start_polling()', 'await dp.start_polling(bot)')
    
    # === CONTENT TYPES ===
    # Arreglar content_types para aiogram 3.x
    content = content.replace('lambda message: message."photo"', 'lambda message: message.photo')
    content = content.replace('lambda message: message."video"', 'lambda message: message.video')
    content = content.replace('lambda message: message."document"', 'lambda message: message.document')
    content = content.replace('lambda message: message."new_chat_members"', 'lambda message: message.new_chat_members')
    content = content.replace('lambda message: message."video_note"', 'lambda message: message.video_note')
    
    # Cambiar F.photo por lambda
    content = content.replace('F.photo', 'lambda message: message.photo')
    content = content.replace('F.video', 'lambda message: message.video')
    content = content.replace('F.document', 'lambda message: message.document')
    
    # === MESSAGE REACTION ===
    # Restaurar message_reaction si existe
    content = content.replace('# message_reaction not available in aiogram 2.x', '@dp.message_reaction()')
    content = content.replace('async def handle_reaction(message: types.MessageReactionUpdated):', 
                            'async def handle_reaction(message: types.MessageReactionUpdated):')
    
    # Escribir el archivo modificado
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ {file_path} convertido exitosamente")
    return True

def upgrade_all_files():
    """Convierte todos los archivos relevantes"""
    files_to_upgrade = [
        'AntmasterBot.py',
        'rewards_manager.py',
        'translation_manager.py'
    ]
    
    success_count = 0
    for file_path in files_to_upgrade:
        if upgrade_aiogram_file(file_path):
            success_count += 1
    
    print(f"\n🎉 Conversión completada: {success_count}/{len(files_to_upgrade)} archivos convertidos")
    print("📋 Recuerda:")
    print("   • Verificar que aiogram 3.x esté instalado")
    print("   • Probar el bot después de la conversión")
    print("   • Revisar cualquier funcionalidad específica")

if __name__ == "__main__":
    upgrade_all_files() 