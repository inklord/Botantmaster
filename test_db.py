from database import AntDatabase
import os
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_database_connection():
    """Prueba la conexión a la base de datos y sus funcionalidades básicas"""
    try:
        # Cargar variables de entorno
        load_dotenv()
        
        # Intentar conectar a la base de datos
        logger.info("Intentando conectar a la base de datos...")
        db = AntDatabase(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        # Probar la conexión
        connection = db.get_connection()
        if connection and connection.is_connected():
            logger.info("✅ Conexión exitosa a la base de datos")
            
            # Verificar las tablas
            cursor = connection.cursor()
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            logger.info("\nTablas encontradas:")
            for table in tables:
                logger.info(f"- {table[0]}")
                
                # Mostrar estructura de cada tabla
                cursor.execute(f"DESCRIBE {table[0]}")
                columns = cursor.fetchall()
                for column in columns:
                    logger.info(f"  └─ {column[0]}: {column[1]}")
            
            # Verificar recompensas
            cursor.execute("SELECT COUNT(*) FROM rewards")
            rewards_count = cursor.fetchone()[0]
            logger.info(f"\nRecompensas configuradas: {rewards_count}")
            
            if rewards_count == 0:
                logger.info("Configurando recompensas base...")
                db.setup_base_rewards()
            
            cursor.close()
            return True
            
    except Exception as e:
        logger.error(f"❌ Error al conectar a la base de datos: {str(e)}")
        return False

if __name__ == "__main__":
    test_database_connection() 