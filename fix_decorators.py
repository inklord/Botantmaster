#!/usr/bin/env python3
"""
Script para arreglar decoradores específicos de aiogram 2.x
"""
import re

def fix_decorators():
    with open('AntmasterBot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Arreglar decoradores de comandos
    content = re.sub(r'@dp\.message_handler\(commands=\["(\w+)"\]\)', r'@dp.message_handler(commands=["\1"])', content)
    
    # Arreglar content_types mal formateados
    content = content.replace('content_types=["photo"] is not None', 'content_types=["photo"]')
    content = content.replace('content_types=["video"] is not None', 'content_types=["video"]')
    content = content.replace('content_types=["document"] is not None', 'content_types=["document"]')
    content = content.replace('content_types=["new_chat_members"] is not None', 'content_types=["new_chat_members"]')
    content = content.replace('content_types=["video"]_note is not None', 'content_types=["video_note"]')
    
    # Arreglar el inicializador del bot y dispatcher para aiogram 2.x
    content = content.replace('bot = Bot(token=TOKEN)\ndp = Dispatcher()', 
                            'bot = Bot(token=TOKEN)\ndp = Dispatcher(bot)')
    
    # Arreglar inicialización del Dispatcher
    if 'dp = Dispatcher()' in content:
        content = content.replace('dp = Dispatcher()', 'dp = Dispatcher(bot)')
    
    # Comentar la función de reacciones que no existe en aiogram 2.x
    content = re.sub(r'@dp\.message_reaction\(\)\nasync def handle_reaction.*?(?=@|\nif|\nasync def|\Z)', 
                    '# message_reaction not available in aiogram 2.x\n# async def handle_reaction', 
                    content, flags=re.DOTALL)
    
    with open('AntmasterBot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Decoradores arreglados para aiogram 2.x")

if __name__ == "__main__":
    fix_decorators() 