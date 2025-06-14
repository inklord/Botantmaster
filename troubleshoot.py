import os
import sys
import logging
import asyncio
import json
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("troubleshoot.log")
    ]
)

logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

def check_environment_variables():
    """Verificar variables de entorno necesarias"""
    print("\n=== Verificando variables de entorno ===")
    
    required_vars = ['API_TOKEN', 'DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked_value = value[:3] + "***" + value[-3:] if len(value) > 6 else "***"
            print(f"✅ {var}: {masked_value}")
        else:
            missing_vars.append(var)
            print(f"❌ {var}: No encontrado")
    
    if missing_vars:
        print("\n⚠️ Faltan variables de entorno. Crea un archivo .env con lo siguiente:")
        for var in missing_vars:
            print(f"{var}=tu_{var.lower()}_aqui")
    else:
        print("\n✅ Todas las variables de entorno están configuradas")
    
    return len(missing_vars) == 0

def check_database_connection():
    """Verificar conexión a la base de datos"""
    print("\n=== Verificando conexión a la base de datos ===")
    
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'antmaster')
        )
        
        if conn.is_connected():
            print(f"✅ Conexión exitosa a la base de datos '{os.getenv('DB_NAME')}'")
            
            # Verificar tablas principales
            cursor = conn.cursor()
            
            # Lista de tablas a verificar
            tables = ['species', 'user_interactions', 'user_experience', 'pending_photos', 'temp_data', 'species_difficulty']
            
            print("\n--- Verificando tablas ---")
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"✅ Tabla '{table}': {count} registros")
                except Exception as e:
                    print(f"❌ Problema con tabla '{table}': {str(e)}")
            
            # Verificar privilegios del usuario de BD
            print("\n--- Verificando privilegios ---")
            try:
                # Intentar crear una tabla temporal
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_privileges (
                        id INT PRIMARY KEY,
                        test_column VARCHAR(50)
                    )
                """)
                print("✅ Privilegios CREATE TABLE: OK")
                
                # Intentar insertar datos
                cursor.execute("INSERT INTO test_privileges (id, test_column) VALUES (1, 'test')")
                print("✅ Privilegios INSERT: OK")
                
                # Intentar actualizar datos
                cursor.execute("UPDATE test_privileges SET test_column = 'updated' WHERE id = 1")
                print("✅ Privilegios UPDATE: OK")
                
                # Intentar eliminar datos
                cursor.execute("DELETE FROM test_privileges WHERE id = 1")
                print("✅ Privilegios DELETE: OK")
                
                # Eliminar la tabla temporal
                cursor.execute("DROP TABLE test_privileges")
                print("✅ Privilegios DROP TABLE: OK")
                
            except Exception as e:
                print(f"❌ Problema con privilegios: {str(e)}")
            
            conn.close()
            return True
        else:
            print("❌ No se pudo conectar a la base de datos")
            return False
    
    except Exception as e:
        print(f"❌ Error al conectar a la base de datos: {str(e)}")
        return False

def check_command_registration():
    """Verificar registros de comandos recientes"""
    print("\n=== Verificando registros de comandos ===")
    
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'antmaster')
        )
        
        if conn.is_connected():
            cursor = conn.cursor(dictionary=True)
            
            # Consultar los últimos 10 comandos registrados
            cursor.execute("""
                SELECT id, user_id, username, interaction_type, command_name, created_at
                FROM user_interactions
                WHERE interaction_type = 'command'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            commands = cursor.fetchall()
            
            if commands:
                print(f"📋 Últimos {len(commands)} comandos registrados:")
                for cmd in commands:
                    # Formatear fecha para mostrar
                    date_str = cmd['created_at'].strftime("%Y-%m-%d %H:%M:%S")
                    print(f"  • {date_str}: {cmd['username']} ejecutó /{cmd['command_name']}")
            else:
                print("❌ No se encontraron comandos registrados recientemente")
            
            # Registrar un comando de prueba para verificar si funciona el registro
            cursor.execute("""
                INSERT INTO user_interactions 
                (user_id, username, interaction_type, command_name, points, chat_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (0, 'troubleshoot_script', 'command', 'test_command', 0, 0))
            
            conn.commit()
            print("\n✅ Se registró un comando de prueba en la base de datos")
            
            conn.close()
            return True
    
    except Exception as e:
        print(f"❌ Error al verificar registros de comandos: {str(e)}")
        return False

def check_bot_activity():
    """Verificar actividad reciente del bot"""
    print("\n=== Verificando actividad reciente del bot ===")
    
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'antmaster')
        )
        
        if conn.is_connected():
            cursor = conn.cursor(dictionary=True)
            
            # Consultar las últimas interacciones del bot
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM user_interactions
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            
            result = cursor.fetchone()
            
            if result and result['count'] > 0:
                print(f"✅ El bot ha registrado {result['count']} interacciones en la última hora")
            else:
                print("⚠️ No se han detectado interacciones del bot en la última hora")
            
            conn.close()
            return True
    
    except Exception as e:
        print(f"❌ Error al verificar actividad del bot: {str(e)}")
        return False

def check_scheduler_status():
    """Verificar estado del scheduler"""
    print("\n=== Verificando estado del scheduler ===")
    
    # No podemos verificar directamente el estado del scheduler
    # Así que vamos a verificar si hay tareas programadas en la base de datos
    try:
        # Verificar los últimos hormidatos enviados
        print("⚠️ No se puede verificar directamente el estado del scheduler")
        print("💡 Sugerencia: Verifica los logs del bot (bot.log) para ver si el scheduler está funcionando")
        print("    Busca mensajes como 'Enviando hormidato automático' o 'Mensaje diario enviado'")
    except Exception as e:
        print(f"❌ Error al verificar estado del scheduler: {str(e)}")

def suggest_fixes():
    """Sugerir soluciones a problemas comunes"""
    print("\n=== Posibles soluciones ===")
    
    print("1️⃣ Reinicia el bot usando el script restart_bot.py:")
    print("   python restart_bot.py")
    
    print("\n2️⃣ Asegúrate de que el token del bot es correcto y el bot está activo en Telegram")
    print("   Habla con @BotFather en Telegram para verificar")
    
    print("\n3️⃣ Verifica que la base de datos está accesible y el usuario tiene los permisos correctos")
    
    print("\n4️⃣ Si el problema persiste, prueba con un bot simple para descartar problemas:")
    print("   python test_bot.py")
    
    print("\n5️⃣ Revisa los logs para ver errores específicos:")
    print("   cat bot.log | grep ERROR")

def main():
    print("========================================")
    print("🔍 DIAGNÓSTICO DE ANTMASTER BOT 🔍")
    print("========================================")
    print(f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("----------------------------------------")
    
    # Ejecutar verificaciones
    env_ok = check_environment_variables()
    db_ok = check_database_connection()
    cmd_ok = check_command_registration()
    activity_ok = check_bot_activity()
    check_scheduler_status()
    
    # Mostrar resultados generales
    print("\n========================================")
    print("📊 RESUMEN DEL DIAGNÓSTICO 📊")
    print("========================================")
    print(f"✓ Variables de entorno: {'OK' if env_ok else 'Problemas detectados'}")
    print(f"✓ Conexión a base de datos: {'OK' if db_ok else 'Problemas detectados'}")
    print(f"✓ Registro de comandos: {'OK' if cmd_ok else 'Problemas detectados'}")
    print(f"✓ Actividad del bot: {'OK' if activity_ok else 'Problemas detectados'}")
    
    # Sugerir soluciones
    suggest_fixes()
    
    print("\n----------------------------------------")
    print("Diagnóstico completado. Verifica el archivo troubleshoot.log para más detalles.")
    print("----------------------------------------")

if __name__ == "__main__":
    main() 