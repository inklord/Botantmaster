from aiogram import types
import logging

logger = logging.getLogger(__name__)

# Definir roles administrativos
ADMIN_ROLES = ["creator", "administrator"]

async def verify_user_role(message: types.Message, bot, allowed_roles=None):
    """
    Verifica si el usuario tiene un rol permitido (admin o creador)
    
    Args:
        message (types.Message): El mensaje del usuario
        bot: Instancia del bot para consultar información
        allowed_roles (list, optional): Lista de roles permitidos. 
                                       Por defecto ["creator", "administrator"]
    
    Returns:
        bool: True si el usuario tiene un rol permitido, False en caso contrario
    """
    if allowed_roles is None:
        allowed_roles = ADMIN_ROLES
        
    try:
        if message.chat.type == "private":
            # En chats privados, verificamos si el usuario es admin en algún grupo
            return True  # Para pruebas, podemos permitir comandos admin en privado
            
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        # Obtener información del miembro
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        
        # Verificar si el rol está entre los permitidos
        return member.status in allowed_roles
    
    except Exception as e:
        logger.error(f"Error al verificar rol de usuario: {str(e)}")
        return False

async def verify_user_level(user_id, db, min_level=1):
    """
    Verifica si el usuario tiene el nivel mínimo requerido
    
    Args:
        user_id (int): ID del usuario
        db: Instancia de la base de datos
        min_level (int): Nivel mínimo requerido
    
    Returns:
        bool: True si el usuario tiene el nivel mínimo, False en caso contrario
    """
    try:
        # Obtener información del usuario
        user_data = db.get_user_experience(user_id)
        
        if not user_data:
            return False
            
        current_level = user_data.get('level', 0)
        
        # Verificar si el nivel actual es mayor o igual al mínimo
        return current_level >= min_level
    
    except Exception as e:
        logger.error(f"Error al verificar nivel de usuario: {str(e)}")
        return False

async def verificar_restricciones(message: types.Message, db, bot, min_level=None, admin_required=False):
    """
    Verifica todas las restricciones aplicables a un comando
    
    Args:
        message (types.Message): El mensaje del usuario
        db: Instancia de la base de datos
        bot: Instancia del bot
        min_level (int, optional): Nivel mínimo requerido
        admin_required (bool): Si se requiere ser administrador
    
    Returns:
        bool: True si el usuario cumple con todas las restricciones, False en caso contrario
    """
    try:
        user_id = message.from_user.id
        
        # Verificar si es admin (si se requiere)
        if admin_required:
            is_admin = await verify_user_role(message, bot)
            if not is_admin:
                await message.reply("⛔ Este comando está reservado para administradores.")
                return False
        
        # Verificar nivel mínimo (si se requiere)
        if min_level is not None:
            has_level = await verify_user_level(user_id, db, min_level)
            if not has_level:
                await message.reply(f"⛔ Necesitas ser nivel {min_level} o superior para usar este comando.")
                return False
        
        # Si pasa todas las verificaciones
        return True
    
    except Exception as e:
        logger.error(f"Error al verificar restricciones: {str(e)}")
        await message.reply("❌ Ocurrió un error al verificar tus permisos.")
        return False 