import asyncio
import logging
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import mysql.connector
import random
from database import AntDatabase

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,  # Nivel DEBUG para ver todos los mensajes
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("adivina_debug.log")
    ]
)

logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Obtener token del bot
TOKEN = os.getenv("API_TOKEN")
logger.info(f"Token cargado: {TOKEN[:5]}...{TOKEN[-5:]}")

# Conexión a la base de datos
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'antmaster')
}

db = AntDatabase(**DB_CONFIG)

# Crear instancias del bot y dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Comandos de diagnóstico
@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    try:
        logger.info("Comando /test recibido")
        await message.answer("✅ El comando de prueba funciona correctamente.")
    except Exception as e:
        logger.error(f"Error en comando test: {e}")
        await message.answer(f"❌ Error: {str(e)}")

@dp.message(Command("debug_adivina"))
async def debug_adivina(message: types.Message):
    try:
        logger.info("Comando /debug_adivina recibido")
        await message.answer("🔍 Iniciando diagnóstico del comando adivina_especie...")
        
        # Paso 1: Verificar conexión a la base de datos
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                await message.answer("✅ Conexión a la base de datos: OK")
                
                # Verificar tabla species_difficulty
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT COUNT(*) FROM species_difficulty")
                    count = cursor.fetchone()[0]
                    await message.answer(f"✅ Tabla species_difficulty: {count} registros")
                except Exception as e:
                    await message.answer(f"❌ Error en tabla species_difficulty: {str(e)}")
                
                # Verificar tabla species
                try:
                    cursor.execute("SELECT COUNT(*) FROM species WHERE photo_url IS NOT NULL")
                    count = cursor.fetchone()[0]
                    await message.answer(f"✅ Especies con foto: {count} registros")
                    
                    # Obtener una especie aleatoria para prueba
                    cursor.execute("SELECT id, scientific_name, photo_url FROM species WHERE photo_url IS NOT NULL LIMIT 1")
                    especie = cursor.fetchone()
                    if especie:
                        species_id, name, photo = especie
                        await message.answer(f"🧪 Especie de prueba: {name}")
                    else:
                        await message.answer("⚠️ No se encontraron especies con fotos para probar")
                except Exception as e:
                    await message.answer(f"❌ Error al verificar especies: {str(e)}")
                
                conn.close()
            else:
                await message.answer("❌ No se pudo conectar a la base de datos")
        except Exception as e:
            await message.answer(f"❌ Error de conexión a BD: {str(e)}")
        
        # Paso 2: Probar envío de teclado inline
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🟢 Botón de prueba", callback_data="test_callback")
                ]
            ])
            
            await message.answer(
                "🧪 Probando teclado inline...",
                reply_markup=keyboard
            )
        except Exception as e:
            await message.answer(f"❌ Error en teclado inline: {str(e)}")
        
        # Paso 3: Probar el envío de una foto
        if 'photo' in locals():
            try:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption="🧪 Probando envío de foto...",
                    parse_mode=ParseMode.HTML
                )
                await message.answer("✅ Envío de foto: OK")
            except Exception as e:
                await message.answer(f"❌ Error al enviar foto: {str(e)}")
        
        # Conclusión
        await message.answer("🔍 Diagnóstico completado. Revisa los resultados para identificar posibles problemas.")
        
    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        await message.answer(f"❌ Error general: {str(e)}")

@dp.message(Command("adivina_test"))
async def adivina_test(message: types.Message):
    """Versión simplificada del comando adivina_especie para pruebas"""
    try:
        logger.info("Comando /adivina_test recibido")
        
        # Mostrar opciones de dificultad simplificadas
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Probar juego", callback_data="adivina_test:prueba")
            ]
        ])
        
        await message.answer(
            "🎮 <b>PRUEBA ADIVINA ESPECIE</b>\n\n"
            "Este es un mensaje de prueba para verificar si el comando funciona.",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error en comando adivina_test: {e}")
        await message.answer(f"❌ Error: {str(e)}")

@dp.callback_query(lambda c: c.data and c.data.startswith('adivina_test:'))
async def handle_adivina_test(callback_query: types.CallbackQuery):
    """Maneja la respuesta de prueba del juego"""
    try:
        logger.info(f"Callback adivina_test recibido: {callback_query.data}")
        await callback_query.answer("✅ Callback funciona correctamente")
        
        # Obtener una especie con foto para mostrar
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT id, scientific_name, photo_url
                FROM species
                WHERE photo_url IS NOT NULL
                LIMIT 1
            """)
            
            especie = cursor.fetchone()
            conn.close()
            
            if especie:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Volver a probar", callback_data="adivina_test:prueba")]
                ])
                
                await bot.send_photo(
                    chat_id=callback_query.message.chat.id,
                    photo=especie['photo_url'],
                    caption=f"🎮 <b>PRUEBA DE FOTO</b>\n\n"
                            f"Especie: {especie['scientific_name']}\n\n"
                            f"Si puedes ver esta foto, significa que el bot puede enviar imágenes correctamente.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
                
                # Borrar mensaje anterior
                await callback_query.message.delete()
            else:
                await callback_query.message.edit_text(
                    "❌ No se encontraron especies con fotos para probar",
                    reply_markup=None
                )
        except Exception as e:
            logger.error(f"Error al obtener especie: {e}")
            await callback_query.message.edit_text(
                f"❌ Error al obtener especie: {str(e)}",
                reply_markup=None
            )
        
    except Exception as e:
        logger.error(f"Error en callback adivina_test: {e}")
        try:
            await callback_query.message.edit_text(f"❌ Error: {str(e)}")
        except:
            pass
@dp.message(Command("adivina_especie", "adivina_especie@AntmasterBot"))
async def adivina_especie(message: types.Message):
    """Inicia el juego de adivinar especies de hormigas"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        logger.info(f"Comando /adivina_especie recibido de {user_id} en chat {chat_id}")

        # Limitar a 3 intentos cada 24h
        if hasattr(db, 'can_play_guessing_game') and not db.can_play_guessing_game(user_id, chat_id):
            await message.answer("Ya has jugado 3 veces en las últimas 24 horas. ¡Vuelve mañana!")
            return

        await adivina_especie_directo(chat_id, message.from_user)
    except Exception as e:
        logger.error(f"Error en comando adivina_especie: {str(e)}")
        await message.answer(f"❌ Error al iniciar el juego: {str(e)}")

async def adivina_especie_directo(chat_id, from_user):
    try:
        wait_message = await bot.send_message(chat_id=chat_id, text="🔍 Buscando especies para el juego...")

        # Registrar interacción
        await db.log_user_interaction(
            user_id=from_user.id,
            username=from_user.username or from_user.first_name,
            interaction_type='command',
            command_name='adivina_especie',
            chat_id=chat_id
        )

        # Obtener especies con foto
        def is_valid_photo_url(url):
            return url and url.startswith("http")

        especies = [e for e in db.get_all_species() if is_valid_photo_url(e.get('photo_url'))]
        if len(especies) < 3:
            await wait_message.edit_text("❌ No hay suficientes especies con fotos para jugar.")
            return

        especie_correcta = random.choice(especies)
        opciones = [especie_correcta]
        while len(opciones) < 4:
            candidata = random.choice(especies)
            if candidata not in opciones:
                opciones.append(candidata)
        random.shuffle(opciones)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=op['scientific_name'],
                callback_data=f"adivina:{op['id']}:{especie_correcta['id']}"
            )] for op in opciones
        ])

        await wait_message.delete()
        await bot.send_photo(
            chat_id=chat_id,
            photo=especie_correcta['photo_url'],
            caption="🎮 <b>¡ADIVINA LA ESPECIE!</b> 🔍\n\n"
                    "¿Qué especie de hormiga muestra la imagen?\n"
                    "Selecciona la respuesta correcta:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error en juego directo: {str(e)}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Error al iniciar el juego: {str(e)}")

@dp.callback_query(lambda c: c.data and c.data.startswith('adivina:'))
async def handle_respuesta(callback_query: types.CallbackQuery):
    try:
        partes = callback_query.data.split(':')
        id_seleccionado = int(partes[1])
        id_correcto = int(partes[2])
        user_id = callback_query.from_user.id
        username = callback_query.from_user.username or callback_query.from_user.first_name
        chat_id = callback_query.message.chat.id

        es_correcta = (id_seleccionado == id_correcto)
        especie = db.get_species_by_id(id_correcto)
        nombre_correcto = especie['scientific_name'] if especie else "Especie desconocida"

        if es_correcta:
            # Otorgar XP como game_guess
            if hasattr(db, 'register_game_attempt'):
                await db.register_game_attempt(user_id, chat_id, id_correcto, is_correct=True)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Jugar de nuevo", callback_data="adivina_nuevo")]
            ])
            await callback_query.message.edit_caption(
                caption=f"✅ <b>¡CORRECTO!</b>\n\n"
                        f"La especie es <i>{nombre_correcto}</i>\n\n"
                        f"🏆 Has ganado <b>10 XP</b>\n\n"
                        f"¿Quieres jugar de nuevo?",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await callback_query.answer("¡Respuesta correcta! +10 XP", show_alert=True)
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Intentar de nuevo", callback_data="adivina_nuevo")]
            ])
            await callback_query.message.edit_caption(
                caption=f"❌ <b>INCORRECTO</b>\n\n"
                        f"La especie correcta es <i>{nombre_correcto}</i>\n\n"
                        f"¿Quieres intentarlo de nuevo?",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await callback_query.answer("Respuesta incorrecta. Prueba de nuevo.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in handle_respuesta: {e}")
        await callback_query.answer("Error al procesar tu respuesta", show_alert=True)

@dp.callback_query(lambda c: c.data == "adivina_nuevo")
async def reiniciar_juego(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
        await callback_query.message.delete()
        await adivina_especie_directo(callback_query.message.chat.id, callback_query.from_user)
    except Exception as e:
        logger.error(f"Error al reiniciar juego: {str(e)}")
        await callback_query.answer("Error al reiniciar el juego", show_alert=True)
@dp.callback_query(lambda c: c.data == "test_callback")
async def handle_test_callback(callback_query: types.CallbackQuery):
    """Manejador para el botón de prueba"""
    try:
        logger.info("Callback test_callback recibido")
        await callback_query.answer("✅ Los callbacks funcionan correctamente")
        await callback_query.message.edit_text("✅ Prueba de callback exitosa")
    except Exception as e:
        logger.error(f"Error en test callback: {e}")

# Función principal
async def main():
    logger.info("Iniciando bot de diagnóstico...")
    print("Bot de diagnóstico iniciado. Envía /debug_adivina o /adivina_test para probar.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        logger.info("Iniciando script de diagnóstico para adivina_especie")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot de diagnóstico detenido")
    except Exception as e:
        logger.error(f"Error crítico: {e}") 