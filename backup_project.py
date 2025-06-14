import os
import zipfile
from datetime import datetime
import shutil
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_backup():
    try:
        # Crear directorio de backups si no existe
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            logger.info(f"Directorio de backups creado: {backup_dir}")

        # Generar nombre del archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"antmaster_backup_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Archivos y directorios a excluir
        exclude = {
            '__pycache__',
            'backups',
            '.git',
            '.env',
            'logs',
            '.pytest_cache',
            'venv',
            'env'
        }

        # Crear archivo ZIP
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Recorrer todos los archivos y directorios
            for root, dirs, files in os.walk('.'):
                # Excluir directorios no deseados
                dirs[:] = [d for d in dirs if d not in exclude]
                
                for file in files:
                    # Comprobar si el archivo debe ser incluido
                    if any(ex in file for ex in ['.pyc', '.pyo', '.pyd']):
                        continue
                        
                    file_path = os.path.join(root, file)
                    
                    # Excluir archivos de backup anteriores
                    if file.startswith('antmaster_backup_'):
                        continue
                        
                    # Excluir archivos temporales
                    if file.endswith('.tmp'):
                        continue
                        
                    # Añadir archivo al ZIP
                    arcname = os.path.relpath(file_path, '.')
                    zipf.write(file_path, arcname)
                    logger.info(f"Añadido: {arcname}")

        # Verificar que el archivo se creó correctamente
        if os.path.exists(backup_path):
            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            logger.info(f"Backup creado exitosamente: {backup_filename}")
            logger.info(f"Tamaño del backup: {size_mb:.2f} MB")
            logger.info(f"Ubicación: {os.path.abspath(backup_path)}")
            return True
        else:
            logger.error("Error: El archivo de backup no se creó correctamente")
            return False

    except Exception as e:
        logger.error(f"Error al crear el backup: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Iniciando proceso de backup...")
    create_backup() 