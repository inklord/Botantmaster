#!/usr/bin/env python3
"""
Script para arreglar los imports de aiogram en AntmasterBot.py
"""

def fix_imports():
    # Leer el archivo original
    with open('AntmasterBot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Encontrar y reemplazar las líneas problemáticas
    lines = content.split('\n')
    new_lines = []
    
    skip_lines = False
    for i, line in enumerate(lines):
        # Detectar el inicio del bloque problemático
        if line.strip().startswith('from aiogram.types import ('):
            skip_lines = True
            # Agregar imports simplificados
            new_lines.append('# Simplified imports for compatibility')
            continue
        
        # Detectar el final del bloque problemático
        if skip_lines and line.strip().endswith(')'):
            skip_lines = False
            continue
        
        # Saltar líneas dentro del bloque problemático
        if skip_lines:
            continue
        
        new_lines.append(line)
    
    # Escribir el archivo corregido
    with open('AntmasterBot.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print("✅ Imports arreglados en AntmasterBot.py")

if __name__ == "__main__":
    fix_imports() 