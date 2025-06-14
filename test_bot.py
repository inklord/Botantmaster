import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Cargar variables de entorno
load_dotenv()

# Obtener token del bot
TOKEN = os.getenv("API_TOKEN")
print(f"Token: {TOKEN}")

# Crear instancias del bot y dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Comando /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        await message.answer("¡Hola! Este es un bot de prueba para verificar la conexión. ⚠️")
    except Exception as e:
        logging.error(f"Error en comando start: {e}")

# Comando /ping para verificar la respuesta
@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    try:
        await message.answer("¡Pong! El bot está funcionando correctamente.")
    except Exception as e:
        logging.error(f"Error en comando ping: {e}")

# Manejador para todos los mensajes
@dp.message()
async def echo(message: types.Message):
    try:
        await message.answer(f"Mensaje recibido: {message.text}")
    except Exception as e:
        logging.error(f"Error en echo: {e}")

# Función principal
async def main():
    print("Iniciando el bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        print("Ejecutando bot de prueba...")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot detenido")
    except Exception as e:
        print(f"Error crítico: {e}") 