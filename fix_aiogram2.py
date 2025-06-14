#!/usr/bin/env python3
"""
Script para convertir imports de aiogram 3.x a aiogram 2.x
"""

def fix_aiogram2_imports():
    # Leer el archivo original
    with open('AntmasterBot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Convertir imports de aiogram 3.x a 2.x
    replacements = {
        # Imports básicos
        'from aiogram import Bot, Dispatcher, types': 'from aiogram import Bot, Dispatcher, types',
        'from aiogram.filters import Command': 'from aiogram.dispatcher.filters import Command',
        'from aiogram.utils.keyboard import InlineKeyboardBuilder': '# InlineKeyboardBuilder not available in aiogram 2.x',
        'from aiogram.enums import ParseMode': '# ParseMode as string in aiogram 2.x',
        'from aiogram.exceptions import TelegramAPIError, TelegramBadRequest': 'from aiogram.utils.exceptions import TelegramAPIError, BotBlocked',
        
        # Decoradores
        '@dp.message(Command(': '@dp.message_handler(commands=[',
        '@dp.callback_query(': '@dp.callback_query_handler(',
        '@dp.message(lambda message: message.photo': '@dp.message_handler(content_types=["photo"]',
        '@dp.message(lambda message: message.video': '@dp.message_handler(content_types=["video"]',
        '@dp.message(lambda message: message.document': '@dp.message_handler(content_types=["document"]',
        '@dp.message(lambda message: message.new_chat_members': '@dp.message_handler(content_types=["new_chat_members"]',
        '@dp.message(lambda message: message.video_note': '@dp.message_handler(content_types=["video_note"]',
        '@dp.message()': '@dp.message_handler()',
        '@dp.message_reaction()': '# message_reaction not available in aiogram 2.x',
        
        # Métodos
        'parse_mode="HTML"': 'parse_mode="HTML"',
        'parse_mode=ParseMode.HTML': 'parse_mode="HTML"',
        'await dp.start_polling(bot)': 'await dp.start_polling()',
        'async def main():': 'async def main():',
        
        # Tipos
        'types.Message': 'types.Message',
        'types.CallbackQuery': 'types.CallbackQuery',
        'InlineKeyboardMarkup': 'types.InlineKeyboardMarkup',
        'InlineKeyboardButton': 'types.InlineKeyboardButton',
    }
    
    # Aplicar reemplazos
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    # Arreglos específicos para Command syntax
    import re
    
    # Convertir @dp.message_handler(commands=["comando"])
    content = re.sub(r'@dp\.message_handler\(commands=\[(\w+)\]\)', r'@dp.message_handler(commands=["\1"])', content)
    
    # Escribir el archivo corregido
    with open('AntmasterBot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Código convertido para aiogram 2.x")

if __name__ == "__main__":
    fix_aiogram2_imports() 