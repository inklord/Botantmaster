#!/usr/bin/env python3
"""
Script para arreglar la sintaxis de comandos en aiogram 2.x
"""
import re

def fix_commands():
    with open('AntmasterBot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Arreglar decoradores de comandos mal formateados
    # Cambiar @dp.message_handler(commands=["comando")) por @dp.message_handler(commands=["comando"])
    content = re.sub(r'@dp\.message_handler\(commands=\["([^"]+)"\]\)', r'@dp.message_handler(commands=["\1"])', content)
    
    # Arreglar casos específicos con paréntesis mal cerrados
    content = re.sub(r'@dp\.message_handler\(commands=\["([^"]+)"\)\)', r'@dp.message_handler(commands=["\1"])', content)
    
    # Arreglar casos con múltiples comandos
    content = re.sub(r'@dp\.message_handler\(commands=\["([^"]+)", "([^"]+)"\]\)', r'@dp.message_handler(commands=["\1", "\2"])', content)
    
    with open('AntmasterBot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Sintaxis de comandos arreglada")

if __name__ == "__main__":
    fix_commands()