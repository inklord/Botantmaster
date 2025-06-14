#!/usr/bin/env python3
"""
Script para corregir errores de indentación en AntmasterBot.py
"""

def fix_indentation():
    try:
        print("Leyendo archivo AntmasterBot.py...")
        with open("AntmasterBot.py", "r", encoding="utf-8") as file:
            lines = file.readlines()
        
        # Corregir líneas específicas con problemas de indentación
        problem_regions = [
            # Región 1: Alrededor de la línea 612
            (609, 615, 16),  # Desde línea 609 hasta 615, normalizar a 16 espacios
            
            # Región 2: Alrededor de la línea 1196
            (1194, 1199, 32),  # Desde línea 1194 hasta 1199, normalizar a 32 espacios
            
            # Región 3: Alrededor de la línea 1679
            (1677, 1689, 16)   # Desde línea 1677 hasta 1689, normalizar a 16 espacios
        ]
        
        # Aplicar correcciones
        modified = 0
        for start, end, indent in problem_regions:
            for i in range(start-1, end):
                # Omitir líneas en blanco
                if i >= len(lines) or lines[i].strip() == "":
                    continue
                
                # Quitar espacios iniciales y agregar la indentación correcta
                content = lines[i].lstrip()
                lines[i] = " " * indent + content
                modified += 1
        
        # Guardar el archivo corregido
        print(f"Guardando archivo con {modified} líneas corregidas...")
        with open("AntmasterBot_fixed.py", "w", encoding="utf-8") as file:
            file.writelines(lines)
        
        print("Corrección completada. Archivo guardado como AntmasterBot_fixed.py")
        print("Por favor, verifica el archivo corregido y renómbralo a AntmasterBot.py si es correcto.")
        
    except Exception as e:
        print(f"Error al procesar el archivo: {str(e)}")

if __name__ == "__main__":
    fix_indentation() 