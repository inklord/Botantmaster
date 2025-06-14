from aiogram import types
from aiogram.filters.command import Command
import logging

logger = logging.getLogger(__name__)

async def mostrar_reglas(message: types.Message, db):
    """Muestra las reglas del grupo en un formato simple"""
    try:
        # Registrar interacción en la base de datos
        db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='reglas',
            chat_id=message.chat.id
        )
        
        # Texto de las reglas
        texto = """🐜 REGLAS DEL GRUPO ANTMASTER 🐜

• Respeta a todos los miembros
• Solo contenido de mirmecología
• Información precisa y verificada
• No spam ni mensajes repetitivos
• Promueve prácticas éticas

• No liberar especies en ecosistemas ajenos
• Respetar leyes locales de captura
• Compras en antmastershop.com
• Ayuda a principiantes con paciencia

El incumplimiento puede resultar en expulsión.
Los administradores tienen la última palabra.

¡DISFRUTA Y APRENDE!"""
        
        # Enviar el mensaje
        await message.answer(texto)
        logger.info(f"Reglas enviadas a {message.from_user.id} en chat {message.chat.id}")
        
    except Exception as e:
        logger.error(f"Error al mostrar reglas: {str(e)}")
        # Intentar enviar un mensaje de error sencillo
        try:
            await message.answer("Error al mostrar las reglas. Por favor, inténtalo de nuevo.")
        except:
            pass  # Si falla incluso el mensaje de error, simplemente continuar
            
def register_handlers(dp, db):
    """Registra los handlers del comando de reglas"""
    dp.message.register(lambda msg: mostrar_reglas(msg, db), Command("reglas")) 