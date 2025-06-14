from database import AntDatabase
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_full_database():
    """Prueba todas las funcionalidades principales de database.py"""
    try:
        # Cargar variables de entorno
        load_dotenv()
        
        # Inicializar la base de datos
        logger.info("1. Inicializando conexión a la base de datos...")
        db = AntDatabase(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        # Test 1: Verificar conexión
        connection = db.get_connection()
        if connection.is_connected():
            logger.info("✅ Conexión exitosa")
        
        # Test 2: Probar registro de interacción de usuario
        logger.info("\n2. Probando registro de interacción de usuario...")
        success = db.log_user_interaction(
            user_id=123456789,
            username="test_user",
            interaction_type="message",
            command_name="test",
            chat_id=-100123456789
        )
        logger.info("✅ Registro de interacción exitoso" if success else "❌ Error en registro de interacción")
        
        # Test 3: Verificar sistema de experiencia
        logger.info("\n3. Verificando sistema de experiencia...")
        cursor = connection.cursor(dictionary=True)
        
        # Verificar tabla user_experience
        cursor.execute("SELECT * FROM user_experience WHERE user_id = 123456789")
        exp_data = cursor.fetchone()
        if exp_data:
            logger.info(f"✅ Usuario encontrado en sistema de experiencia:")
            logger.info(f"   - XP Total: {exp_data['total_xp']}")
            logger.info(f"   - Nivel: {exp_data['current_level']}")
        else:
            logger.info("❌ Usuario no encontrado en sistema de experiencia")
        
        # Test 4: Verificar recompensas
        logger.info("\n4. Verificando sistema de recompensas...")
        cursor.execute("SELECT COUNT(*) as count FROM rewards")
        rewards_count = cursor.fetchone()['count']
        logger.info(f"✅ Recompensas configuradas: {rewards_count}")
        
        if rewards_count == 0:
            logger.info("Configurando recompensas base...")
            db.setup_base_rewards()
            cursor.execute("SELECT COUNT(*) as count FROM rewards")
            rewards_count = cursor.fetchone()['count']
            logger.info(f"✅ Recompensas después de configuración: {rewards_count}")
        
        # Test 5: Probar rankings
        logger.info("\n5. Probando sistema de rankings...")
        weekly = db.get_weekly_leaderboard()
        monthly = db.get_monthly_leaderboard()
        
        logger.info("Ranking Semanal:")
        for i, user in enumerate(weekly, 1):
            logger.info(f"   {i}. @{user['username']}: {user['total_points']} puntos")
            
        logger.info("\nRanking Mensual:")
        for i, user in enumerate(monthly, 1):
            logger.info(f"   {i}. @{user['username']}: {user['total_points']} puntos")
        
        # Test 6: Verificar estructura de todas las tablas
        logger.info("\n6. Verificando estructura de tablas...")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[list(table.keys())[0]]
            logger.info(f"\nTabla: {table_name}")
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            for column in columns:
                logger.info(f"  └─ {column['Field']}: {column['Type']}")
        
        cursor.close()
        logger.info("\n✅ Todas las pruebas completadas exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante las pruebas: {str(e)}")
        return False

if __name__ == "__main__":
    test_full_database() 