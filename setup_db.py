import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_database():
    """Configura la base de datos inicial"""
    try:
        # Cargar variables de entorno
        load_dotenv()
        
        # Conectar sin especificar base de datos
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            
            # Crear base de datos si no existe
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {os.getenv('DB_NAME')} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info(f"✅ Base de datos {os.getenv('DB_NAME')} creada o verificada")
            
            # Usar la base de datos
            cursor.execute(f"USE {os.getenv('DB_NAME')}")
            
            # Otorgar todos los privilegios al usuario
            cursor.execute(f"GRANT ALL PRIVILEGES ON {os.getenv('DB_NAME')}.* TO '{os.getenv('DB_USER')}'@'localhost'")
            cursor.execute("FLUSH PRIVILEGES")
            logger.info("✅ Privilegios configurados correctamente")
            
            cursor.close()
            connection.close()
            logger.info("✅ Configuración inicial completada")
            return True
            
    except Error as e:
        logger.error(f"❌ Error durante la configuración: {str(e)}")
        return False

if __name__ == "__main__":
    setup_database() 