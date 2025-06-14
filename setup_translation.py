#!/usr/bin/env python3
"""
Script para configurar el sistema de traducción automática del bot
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Añadir directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import AntDatabase
from translation_manager import TranslationManager

async def setup_translation_system():
    """Configura el sistema de traducción"""
    try:
        # Cargar variables de entorno
        from dotenv import load_dotenv
        load_dotenv()
        
        logger.info("🔧 Iniciando configuración del sistema de traducción...")
        
        # Conectar a la base de datos
        db = AntDatabase(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'antmaster')
        )
        
        logger.info("✅ Conectado a la base de datos")
        
        # Crear tablas de traducción
        db.create_translation_tables()
        logger.info("✅ Tablas de traducción creadas")
        
        # Inicializar gestor de traducción
        translation_manager = TranslationManager(db)
        await translation_manager.setup_database_tables()
        logger.info("✅ Gestor de traducción inicializado")
        
        # Probar funcionalidad de traducción
        logger.info("🧪 Probando funcionalidad de traducción...")
        
        test_text = "Hello, how are you?"
        translated = await translation_manager.translate_text(test_text, 'en', 'es')
        
        if translated:
            logger.info(f"✅ Prueba de traducción exitosa:")
            logger.info(f"   Original: {test_text}")
            logger.info(f"   Traducido: {translated}")
        else:
            logger.warning("⚠️ No se pudo probar la traducción")
        
        # Cerrar sesión
        await translation_manager.close_session()
        
        logger.info("🎉 ¡Sistema de traducción configurado exitosamente!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error configurando sistema de traducción: {str(e)}")
        return False

def add_translation_handlers_to_bot():
    """
    Genera el código que debe añadirse al bot principal
    """
    code = '''
# === SISTEMA DE TRADUCCIÓN AUTOMÁTICA ===

# Inicializar el gestor de traducción
translation_manager = TranslationManager(db)

@dp.message(Command("idioma"))
async def seleccionar_idioma(message: types.Message):
    """Permite al usuario seleccionar su idioma"""
    try:
        # Verificar si es un chat grupal
        if message.chat.type not in ['group', 'supergroup']:
            await message.answer("Este comando solo funciona en grupos.")
            return
            
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='idioma',
            chat_id=message.chat.id
        )
        
        # Mostrar teclado de selección de idioma
        keyboard = translation_manager.get_language_keyboard()
        
        await message.answer(
            "🌐 <b>Selecciona tu idioma</b>\\n\\n"
            "Si seleccionas un idioma diferente al español, recibirás traducciones automáticas "
            "de los mensajes del grupo en mensajes privados.\\n\\n"
            "Si hablas español, selecciona '🇪🇸 Hablo Español'.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error en comando idioma: {str(e)}")
        await message.answer("❌ Error al mostrar opciones de idioma.")

@dp.callback_query(lambda c: c.data and c.data.startswith('lang:'))
async def handle_language_selection(callback_query: types.CallbackQuery):
    """Maneja la selección de idioma"""
    try:
        language_code = callback_query.data.split(':')[1]
        user_id = callback_query.from_user.id
        chat_id = callback_query.message.chat.id
        username = callback_query.from_user.username
        first_name = callback_query.from_user.first_name
        
        # Guardar idioma en base de datos
        success = db.set_user_language(
            user_id=user_id,
            chat_id=chat_id,
            language_code=language_code,
            username=username,
            first_name=first_name
        )
        
        if success:
            lang_info = translation_manager.supported_languages.get(language_code, {})
            flag = lang_info.get('flag', '🌐')
            name = lang_info.get('name', language_code)
            
            if language_code == 'es':
                response = f"✅ {flag} Configurado como hispanohablante. No recibirás traducciones automáticas."
            else:
                response = (f"✅ {flag} Idioma configurado: {name}\\n\\n"
                          f"Ahora recibirás traducciones automáticas de los mensajes del grupo "
                          f"en tu idioma mediante mensajes privados.\\n\\n"
                          f"<b>Importante:</b> Debes iniciar una conversación privada conmigo (@AntmasterBot) "
                          f"para recibir las traducciones.")
            
            await callback_query.message.edit_text(response, parse_mode="HTML")
        else:
            await callback_query.message.edit_text("❌ Error al configurar el idioma.")
            
    except Exception as e:
        logger.error(f"Error seleccionando idioma: {str(e)}")
        await callback_query.answer("❌ Error al configurar idioma.")

# Modificar el handler de nuevos miembros existente para incluir selección de idioma
@dp.message(lambda message: message.new_chat_members is not None)
async def handle_new_members_with_translation(message: types.Message):
    """Maneja nuevos miembros y les ofrece selección de idioma"""
    try:
        # Código existente del handler...
        # [Aquí iría el código actual del handler]
        
        # Agregar selección de idioma para nuevos miembros
        for new_member in message.new_chat_members:
            if not new_member.is_bot:
                # Verificar si es nuevo en el chat
                is_new = db.is_user_new_to_chat(new_member.id, message.chat.id)
                
                if is_new:
                    # Esperar un poco antes de mostrar el mensaje
                    await asyncio.sleep(2)
                    
                    keyboard = translation_manager.get_language_keyboard()
                    welcome_msg = (
                        f"¡Hola {new_member.first_name}! 🐜\\n\\n"
                        f"🌐 <b>Selecciona tu idioma</b>\\n\\n"
                        f"Si no hablas español, puedes recibir traducciones automáticas "
                        f"de los mensajes del grupo. Selecciona tu idioma preferido:"
                    )
                    
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=welcome_msg,
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                    
    except Exception as e:
        logger.error(f"Error en handler de nuevos miembros con traducción: {str(e)}")

# Modificar el handler de mensajes para incluir traducción automática
@dp.message()
async def handle_message_with_translation(message: types.Message):
    """Maneja mensajes normales incluyendo traducción automática"""
    try:
        # Código existente del handler...
        # [Aquí iría el código actual del handler]
        
        # Procesar traducción automática
        await translation_manager.process_message_translation(message, bot)
        
    except Exception as e:
        logger.error(f"Error en handler de mensajes con traducción: {str(e)}")

# === FIN SISTEMA DE TRADUCCIÓN ===
'''
    
    print("=== CÓDIGO PARA AÑADIR AL BOT ===")
    print(code)
    print("=== FIN DEL CÓDIGO ===")

async def main():
    """Función principal"""
    print("🚀 Configurador del Sistema de Traducción Automática")
    print("=" * 50)
    
    # Configurar sistema
    success = await setup_translation_system()
    
    if success:
        print("\\n📋 Próximos pasos:")
        print("1. El sistema de traducción está configurado")
        print("2. Añade los handlers al bot principal (se mostrará el código)")
        print("3. Reinicia el bot")
        print("4. Los usuarios podrán usar /idioma para configurar su idioma")
        
        print("\\n" + "=" * 50)
        add_translation_handlers_to_bot()
    else:
        print("❌ Error en la configuración. Revisa los logs.")

if __name__ == "__main__":
    asyncio.run(main()) 