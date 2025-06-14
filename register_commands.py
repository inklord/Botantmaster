import asyncio
from aiogram import Bot
import os
from dotenv import load_dotenv

load_dotenv()

# Lista de comandos a registrar
COMMANDS = [
    {"command": "start", "description": "Iniciar el bot"},
    {"command": "ayuda", "description": "Mostrar comandos disponibles"},
    {"command": "hormidato", "description": "Muestra un dato curioso sobre hormigas"},
    {"command": "especie", "description": "Busca información de una especie"},
    {"command": "prediccion", "description": "Predicción de vuelos nupciales"},
    {"command": "proximos_vuelos", "description": "Info sobre próximos vuelos nupciales"},
    {"command": "nivel", "description": "Muestra tu nivel actual y experiencia"},
    {"command": "ranking", "description": "Muestra el ranking histórico de usuarios"},
    {"command": "ranking_semanal", "description": "Ranking de la última semana"},
    {"command": "ranking_mensual", "description": "Ranking del último mes"},
    {"command": "adivina_especie", "description": "Juego de adivinar especies de hormigas"},
    {"command": "normas", "description": "Muestra las reglas del grupo"}
]

async def register_commands():
    print("Iniciando registro de comandos...")
    token = os.getenv('API_TOKEN')
    if not token:
        print("❌ Error: No se encontró API_TOKEN en las variables de entorno")
        return False
        
    bot = Bot(token=token)
    try:
        print("Registrando comandos del bot en BotFather...")
        # Establecer comandos del bot
        await bot.set_my_commands(COMMANDS)
        print("✅ Comandos registrados correctamente:")
        
        # Imprimir la lista de comandos registrados
        for cmd in COMMANDS:
            print(f"   /{cmd['command']} - {cmd['description']}")
            
        return True
            
    except Exception as e:
        print(f"❌ Error al registrar comandos: {str(e)}")
        return False
    finally:
        await bot.session.close()
        
if __name__ == '__main__':
    print("=== REGISTRO DE COMANDOS DEL BOT ===")
    print("Este script registrará los comandos del bot en BotFather.")
    print("Esto permite que Telegram muestre sugerencias de comandos a los usuarios.\n")
    
    success = asyncio.run(register_commands())
    
    if success:
        print("\n✅ Operación completada exitosamente")
        print("   Los comandos están ahora disponibles en el menú de comandos de Telegram")
    else:
        print("\n❌ No se pudo completar la operación")
        print("   Verifica el token del bot y tu conexión a internet") 