import asyncio
from aiogram import Bot
import os
from dotenv import load_dotenv

load_dotenv()

async def reset_webhook():
    print("Iniciando eliminación de webhook...")
    token = os.getenv('API_TOKEN')
    if not token:
        print("❌ Error: No se encontró API_TOKEN en las variables de entorno")
        return False
        
    bot = Bot(token=token)
    try:
        # Obtener información actual del webhook
        webhook_info = await bot.get_webhook_info()
        
        if webhook_info.url:
            print(f"📌 Webhook actual: {webhook_info.url}")
            print(f"   Pendientes: {webhook_info.pending_update_count}")
            
            # Eliminar webhook y descartar actualizaciones pendientes
            await bot.delete_webhook(drop_pending_updates=True)
            print("✅ Webhook eliminado correctamente")
        else:
            print("ℹ️ No hay webhook configurado actualmente")
            
        # Verificar que se eliminó correctamente
        webhook_info = await bot.get_webhook_info()
        if not webhook_info.url:
            print("✅ Verificado: No hay webhook configurado")
            return True
        else:
            print(f"❌ Error: El webhook sigue configurado: {webhook_info.url}")
            return False
            
    except Exception as e:
        print(f"❌ Error al eliminar webhook: {str(e)}")
        return False
    finally:
        await bot.session.close()
        
if __name__ == '__main__':
    print("=== ELIMINACIÓN DE WEBHOOK DE TELEGRAM ===")
    print("Este script eliminará cualquier webhook configurado para el bot.")
    print("Esto puede resolver problemas si el bot no responde a comandos.\n")
    
    success = asyncio.run(reset_webhook())
    
    if success:
        print("\n✅ Operación completada exitosamente")
        print("   Ahora reinicia el bot con: python restart_bot.py")
    else:
        print("\n❌ No se pudo completar la operación")
        print("   Verifica el token del bot y tu conexión a internet") 