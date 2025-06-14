import mysql.connector
import logging
from typing import Optional, Dict, List, Union
from datetime import datetime, timedelta
from mysql.connector import Error
import requests
import json
import math
import asyncio

logger = logging.getLogger(__name__)

class AntDatabase:
    def __init__(self, host, user, password, database):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.bot_start_time = datetime.now()  # Añadir tiempo de inicio del bot
        self.connect()
        self.setup_database()

    def connect(self):
        """Establece la conexión a la base de datos"""
        try:
            if self.connection is None or not self.connection.is_connected():
                # Configuración con SSL permisivo para caching_sha2_password
                config = {
                    'host': self.host,
                    'user': self.user,
                    'password': self.password,
                    'database': self.database,
                    'autocommit': True,
                    'ssl_verify_cert': False,
                    'ssl_verify_identity': False,
                    'ssl_ca': None,
                    'allow_local_infile': True,
                    'use_unicode': True,
                    'charset': 'utf8mb4',
                    'collation': 'utf8mb4_unicode_ci',
                    'get_warnings': False,  # Desactivar advertencias para evitar errores
                    'raise_on_warnings': False
                }
                
                self.connection = mysql.connector.connect(**config)
                logger.info("Conexión a la base de datos establecida")
        except Exception as e:
            logger.error(f"Error al conectar a la base de datos: {e}")
            self.connection = None
            raise

    def ensure_connection(self):
        """Asegura que la conexión está activa, reconectando si es necesario"""
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connect()
            return True
        except Exception as e:
            logger.error(f"Error al asegurar la conexión: {str(e)}")
            return False

    def get_connection(self):
        """Obtiene la conexión a la base de datos, reconectando si es necesario"""
        self.ensure_connection()
        return self.connection

    def setup_database(self):
        """Configura la estructura de la base de datos"""
        try:
            cursor = self.connection.cursor()
            
            # Crear tabla de especies si no existe
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS species (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    scientific_name VARCHAR(255) NOT NULL,
                    antwiki_url TEXT,
                    photo_url TEXT,
                    inaturalist_id VARCHAR(50),
                    region TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_scientific_name (scientific_name),
                    INDEX idx_scientific_name (scientific_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Verificar si la columna region existe
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'species'
                AND column_name = 'region'
            """)
            
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    ALTER TABLE species
                    ADD COLUMN region TEXT AFTER photo_url
                """)
                self.connection.commit()
                logger.info("Columna 'region' añadida a la tabla species")
            
            # Crear tabla para guardar la información de AntOnTop
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS antontop_info (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    species_id INT NOT NULL,
                    scientific_name VARCHAR(255) NOT NULL,
                    description TEXT,
                    short_description TEXT,
                    photo_url TEXT,
                    region VARCHAR(255),
                    behavior VARCHAR(255),
                    difficulty VARCHAR(255),
                    temperature VARCHAR(100),
                    humidity VARCHAR(100),
                    queen_size VARCHAR(100),
                    worker_size VARCHAR(100),
                    colony_size VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_species_antontop (species_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Crear tabla para la dificultad de las especies en los juegos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS species_difficulty (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    species_id INT NOT NULL,
                    difficulty_level ENUM('facil', 'medio', 'dificil') NOT NULL DEFAULT 'medio',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_species_difficulty (species_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Crear tabla para notificaciones de límites diarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_limit_notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    notification_type ENUM('limit_reached', 'approaching_limit') NOT NULL,
                    notification_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_chat_date (user_id, chat_id, notification_date),
                    UNIQUE KEY unique_notification (user_id, chat_id, notification_type, notification_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Crear tabla de estadísticas de búsqueda si no existe
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_stats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    species_id INT,
                    search_count INT DEFAULT 0,
                    last_search TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Crear tabla de interacciones de usuarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_interactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    interaction_type ENUM('command', 'message', 'photo', 'video', 'document', 'join', 'reaction', 'spam_notification', 'game_guess') NOT NULL,
                    command_name VARCHAR(50),
                    points INT DEFAULT 1,
                    chat_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_created_at (created_at),
                    INDEX idx_chat_id (chat_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            # Crear tabla para fotos pendientes de aprobación
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_photos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    approved BOOLEAN DEFAULT FALSE,
                    approved_by BIGINT,
                    xp_given BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_id (user_id),
                    INDEX idx_message_id (message_id),
                    INDEX idx_chat_id (chat_id),
                    UNIQUE KEY unique_photo (chat_id, message_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Verificar si el tipo 'spam_notification' existe
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'user_interactions'
                AND column_name = 'interaction_type'
            """)
            
            if cursor.fetchone()[0] > 0:
                cursor.execute("""
                    ALTER TABLE user_interactions
                    MODIFY COLUMN interaction_type ENUM('command', 'message', 'photo', 'video', 'document', 'join', 'reaction', 'spam_notification', 'game_guess') NOT NULL
                """)
                self.connection.commit()
                logger.info("Tipos 'spam_notification' y 'game_guess' añadidos a la tabla user_interactions")
            
            # Crear tabla de experiencia de usuarios
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_experience (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    total_xp INT DEFAULT 0,
                    current_level INT DEFAULT 1,
                    chat_id BIGINT,
                    last_message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_chat (user_id, chat_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_chat_id (chat_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Crear tabla de búsquedas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS searches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    query VARCHAR(255) NOT NULL,
                    found_species_id INT,
                    success BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (found_species_id) REFERENCES species(id) ON DELETE CASCADE,
                    INDEX idx_query (query)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Crear tabla para el juego de adivinar la especie
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS species_guessing_game (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    species_id INT NOT NULL,
                    attempts INT DEFAULT 0,
                    last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (species_id) REFERENCES species(id),
                    INDEX idx_user_chat (user_id, chat_id),
                    INDEX idx_last_attempt (last_attempt)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            # Tabla para datos temporales (usado para captchas, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temp_data (
                    id VARCHAR(255) PRIMARY KEY,
                    value TEXT,
                    expires_at TIMESTAMP
                )
            """)
            
            # Crear tabla de descripciones si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS species_descriptions (
                    scientific_name VARCHAR(255) PRIMARY KEY,
                    description TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source VARCHAR(50) DEFAULT 'chatgpt'
                )
            """)
            
            self.connection.commit()
            cursor.close()
            logger.info("Base de datos configurada correctamente")
            
        except Exception as e:
            logger.error(f"Error al configurar la base de datos: {str(e)}")
            if self.connection:
                self.connection.rollback()
            raise
        finally:
            if cursor:
                cursor.close()

    def setup_base_rewards(self):
        """Configura las recompensas base si no existen"""
        try:
            cursor = self.connection.cursor()
            
            # Verificar si ya hay recompensas configuradas
            cursor.execute("SELECT COUNT(*) FROM rewards")
            if cursor.fetchone()[0] == 0:
                # Insertar recompensas base
                rewards = [
                    (10, 'discount', 'Código de descuento del 5% en tu próxima compra', 5, None),
                    (20, 'gift_card', 'Tarjeta regalo de 20€', None, 20.00),
                    (30, 'starter_kit', 'Kit de iniciación para hormigas', None, None),
                    (40, 'medium_kit', 'Kit mediano para hormigas', None, None),
                    (50, 'large_kit', 'Kit grande para hormigas', None, None),
                    (75, 'xl_kit', 'Kit XL para hormigas', None, None),
                    (100, 'gift_card', 'Tarjeta regalo de 100€', None, 100.00)
                ]
                
                cursor.executemany("""
                    INSERT INTO rewards 
                    (level_required, reward_type, description, discount_amount, gift_card_value)
                    VALUES (%s, %s, %s, %s, %s)
                """, rewards)
                
                self.connection.commit()
                logger.info("Recompensas base configuradas correctamente")
                
        except Exception as e:
            logger.error(f"Error al configurar recompensas base: {str(e)}")
            self.connection.rollback()
        finally:
            if cursor:
                cursor.close()

    def update_reward_discount_percentage(self):
        """Actualiza el porcentaje de descuento de la recompensa de nivel 10"""
        try:
            cursor = self.connection.cursor()
            
            # Actualizar la recompensa de nivel 10
            cursor.execute("""
                UPDATE rewards 
                SET description = 'Código de descuento del 5% en tu próxima compra',
                    discount_amount = 5
                WHERE level_required = 10 AND reward_type = 'discount'
            """)
            
            affected_rows = cursor.rowcount
            self.connection.commit()
            
            if affected_rows > 0:
                logger.info(f"Recompensa de nivel 10 actualizada: descuento cambiado a 5%")
            
            return affected_rows > 0
            
        except Exception as e:
            logger.error(f"Error al actualizar recompensa de nivel 10: {str(e)}")
            self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def add_species(self, nombre_cientifico: str, subespecie: Optional[str] = None, region: Optional[str] = None,
                    photo_url: Optional[str] = None, description: Optional[str] = None, habitat: Optional[str] = None,
                    behavior: Optional[str] = None, queen_size: Optional[str] = None, worker_size: Optional[str] = None,
                    colony_size: Optional[str] = None, characteristics: Optional[List[str]] = None,
                    distribution: Optional[List[str]] = None, inat_id: Optional[str] = None,
                    antwiki_url: Optional[str] = None, antmaps_url: Optional[str] = None,
                    antontop_url: Optional[str] = None) -> bool:
        """Añade una nueva especie a la base de datos"""
        try:
            cursor = self.get_connection().cursor()
            
            # Insertar en la tabla species
            cursor.execute("""
                INSERT INTO species (scientific_name, antwiki_url, photo_url, inaturalist_id, region)
                VALUES (%s, %s, %s, %s, %s)
            """, (nombre_cientifico, antwiki_url, photo_url, inat_id, region))
            
            species_id = cursor.lastrowid
            
            # Insertar en la tabla antontop_info si hay información
            if any([description, habitat, behavior, queen_size, worker_size, colony_size, characteristics]):
                cursor.execute("""
                    INSERT INTO antontop_info (
                        species_id, scientific_name, description, photo_url, region,
                        behavior, queen_size, worker_size, colony_size
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    species_id, nombre_cientifico, description, photo_url, region,
                    behavior, queen_size, worker_size, colony_size
                ))
            
            # Insertar en la tabla search_stats
            cursor.execute("""
                INSERT INTO search_stats (species_id, search_count)
                VALUES (%s, 0)
            """, (species_id,))
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error al añadir especie: {str(e)}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()

    def init_db(self):
        """Inicializa la base de datos con las tablas necesarias"""
        cursor = None
        try:
            # Primero crear la base de datos si no existe
            temp_config = self.db_config.copy()
            temp_config.pop('database', None)
            connection = mysql.connector.connect(**temp_config)
            cursor = connection.cursor()
            
            # Crear la base de datos si no existe
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.db_config['database']}")
            cursor.execute(f"USE {self.db_config['database']}")
            
            # Crear las tablas
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS species (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scientific_name VARCHAR(255) UNIQUE NOT NULL,
                genus VARCHAR(100) NOT NULL,
                specific_epithet VARCHAR(100) NOT NULL,
                antwiki_url TEXT,
                inaturalist_id VARCHAR(255),
                photo_url TEXT,
                region TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_species_name (scientific_name),
                INDEX idx_species_genus (genus)
            ) ENGINE=InnoDB
            ''')

            # Nueva tabla para información detallada de especies
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS species_info (
                id INT AUTO_INCREMENT PRIMARY KEY,
                species_id INT NOT NULL,
                distribution TEXT,
                habitat TEXT,
                behavior TEXT,
                nesting TEXT,
                diet TEXT,
                colony_size TEXT,
                queen_info TEXT,
                worker_info TEXT,
                breeding_tips TEXT,
                interesting_facts TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (species_id) REFERENCES species(id),
                UNIQUE KEY unique_species_info (species_id)
            ) ENGINE=InnoDB
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                query VARCHAR(255) NOT NULL,
                found_species_id INT,
                success BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (found_species_id) REFERENCES species(id),
                INDEX idx_searches_query (query)
            ) ENGINE=InnoDB
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS species_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                species_id INT NOT NULL,
                inaturalist_id VARCHAR(50),
                photo_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (species_id) REFERENCES species(id)
            ) ENGINE=InnoDB
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_stats (
                id INT AUTO_INCREMENT PRIMARY KEY,
                species_id INT,
                search_count INT DEFAULT 1,
                last_search TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (species_id) REFERENCES species(id)
            )
            ''')

            connection.commit()
            logger.info("Base de datos MySQL inicializada correctamente")
            
        except Error as e:
            logger.error(f"Error al inicializar la base de datos MySQL: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    def levenshtein_distance(self, s1, s2):
        """Calcula la distancia de Levenshtein entre dos cadenas"""
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def calculate_similarity(self, s1, s2):
        """Calcula la similitud entre dos cadenas usando varios métodos"""
        s1 = s1.lower()
        s2 = s2.lower()
        
        # Distancia de Levenshtein
        lev_distance = self.levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        lev_similarity = 1 - (lev_distance / max_len) if max_len > 0 else 0
        
        # Coincidencia de caracteres
        chars1 = set(s1)
        chars2 = set(s2)
        common_chars = len(chars1.intersection(chars2))
        char_similarity = common_chars / max(len(chars1), len(chars2)) if max(len(chars1), len(chars2)) > 0 else 0
        
        # Coincidencia de subcadenas
        subseq_len = 0
        last_pos = -1
        for char in s1:
            pos = s2.find(char, last_pos + 1)
            if pos > last_pos:
                subseq_len += 1
                last_pos = pos
        subseq_similarity = subseq_len / max(len(s1), len(s2)) if max(len(s1), len(s2)) > 0 else 0
        
        # Promedio ponderado de las similitudes
        return (lev_similarity * 0.5) + (char_similarity * 0.3) + (subseq_similarity * 0.2)

    def find_species(self, search_term):
        """Busca una especie por nombre, solo devuelve coincidencias exactas"""
        cursor = None
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            # Normalizar el término de búsqueda
            search_term = search_term.lower().strip()
            
            # Consulta para buscar coincidencia exacta
            query = """
            SELECT 
                s.id,
                s.scientific_name,
                s.antwiki_url,
                s.photo_url,
                s.inaturalist_id,
                s.region
            FROM species s
            WHERE LOWER(s.scientific_name) = %s
            """
            
            cursor.execute(query, (search_term,))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"Especie encontrada: {result['scientific_name']}")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error al buscar especie: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def find_species_by_name(self, scientific_name):
        """Busca una especie directamente por su nombre científico"""
        cursor = None
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            # Normalizar el nombre científico
            scientific_name = scientific_name.strip()
            
            # Consulta para buscar por nombre científico
            query = """
            SELECT 
                s.id,
                s.scientific_name,
                s.antwiki_url,
                s.photo_url,
                s.inaturalist_id,
                s.region
            FROM species s
            WHERE s.scientific_name = %s
            """
            
            cursor.execute(query, (scientific_name,))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"Especie encontrada directamente por nombre: {result['scientific_name']}")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error al buscar especie por nombre: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def log_search(self, query, species_id=None, success=False):
        """Registra una búsqueda en la base de datos"""
        try:
            cursor = self.get_connection().cursor()
            cursor.execute(
                "INSERT INTO searches (query, found_species_id, success) VALUES (%s, %s, %s)",
                (query, species_id, success)
            )
            self.get_connection().commit()
        except Exception as e:
            logger.error(f"Error al registrar búsqueda: {str(e)}")
        finally:
            if cursor:
                cursor.close()

    def get_similar_queries(self, query, limit=5):
        """Obtiene búsquedas similares anteriores"""
        try:
            connection = self.get_connection()
            if not connection:
                return []
                
            cursor = connection.cursor()
            cursor.execute('''
            SELECT DISTINCT s.query, sp.scientific_name
            FROM searches s
            JOIN species sp ON s.found_species_id = sp.id
            WHERE s.success = 1
            AND s.query LIKE %s
            LIMIT %s
            ''', (f"%{query}%", limit))
            
            return cursor.fetchall()
            
        except Error as e:
            logger.error(f"Error al obtener búsquedas similares: {e}")
            return []
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    def add_species_info(self, species_id, info):
        """Añade información adicional de una especie"""
        try:
            cursor = self.connection.cursor()
            
            # Verificar si ya existe información para esta especie
            cursor.execute("""
                SELECT id FROM species_info 
                WHERE species_id = %s
            """, (species_id,))
            
            if cursor.fetchone():
                # Actualizar información existente
                cursor.execute("""
                    UPDATE species_info 
                    SET info = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE species_id = %s
                """, (json.dumps(info), species_id))
            else:
                # Insertar nueva información
                cursor.execute("""
                    INSERT INTO species_info (species_id, info)
                    VALUES (%s, %s)
                """, (species_id, json.dumps(info)))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error al añadir información de especie: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def update_species_info(self, scientific_name, updates):
        """Actualiza la información de una especie existente"""
        try:
            cursor = self.connection.cursor()
            
            # Obtener el ID de la especie
            cursor.execute("""
                SELECT id FROM species 
                WHERE scientific_name = %s
            """, (scientific_name,))
            
            result = cursor.fetchone()
            if not result:
                logger.error(f"Especie no encontrada: {scientific_name}")
                return False
                
            species_id = result[0]
            
            # Construir la consulta de actualización dinámicamente
            update_fields = []
            params = []
            
            for field, value in updates.items():
                if value is not None:  # Solo actualizar campos con valores no nulos
                    update_fields.append(f"{field} = %s")
                    params.append(value)
            
            if not update_fields:
                logger.warning("No hay campos para actualizar")
                return False
                
            # Añadir el ID de la especie a los parámetros
            params.append(species_id)
            
            # Ejecutar la actualización
            query = f"""
                UPDATE species 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """
            
            cursor.execute(query, params)
            self.connection.commit()
            
            logger.info(f"Información actualizada para la especie: {scientific_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error al actualizar información de especie: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_species_info(self, scientific_name):
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    s.scientific_name,
                    s.antwiki_url,
                    s.photo_url,
                    si.distribution,
                    si.habitat,
                    si.behavior,
                    si.nesting,
                    si.diet,
                    si.colony_size,
                    si.queen_info,
                    si.worker_info,
                    si.breeding_tips,
                    si.interesting_facts
                FROM species s
                LEFT JOIN species_info si ON s.id = si.species_id
                WHERE s.scientific_name = %s
            """, (scientific_name,))
            
            result = cursor.fetchone()
            return result if result else None
            
        except Error as e:
            logging.error(f"Error al obtener información de especie: {e}")
            return None
            
    def get_species_info_by_id(self, species_id):
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            cursor.execute("""
                SELECT 
                    s.scientific_name,
                    s.antwiki_url,
                    s.photo_url,
                    si.distribution,
                    si.habitat,
                    si.behavior,
                    si.nesting,
                    si.diet,
                    si.colony_size,
                    si.queen_info,
                    si.worker_info,
                    si.breeding_tips,
                    si.interesting_facts
                FROM species s
                LEFT JOIN species_info si ON s.id = si.species_id
                WHERE s.id = %s
            """, (species_id,))
            
            result = cursor.fetchone()
            return result if result else None
            
        except Error as e:
            logging.error(f"Error al obtener información de especie: {e}")
            return None

    def update_species_region(self, scientific_name, region):
        """Actualiza la región de una especie"""
        try:
            cursor = self.get_connection().cursor()
            cursor.execute(
                'UPDATE species SET region = %s WHERE scientific_name = %s',
                (region, scientific_name)
            )
            self.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Error al actualizar región de especie: {str(e)}")
            return False

    def get_species_by_region(self, region):
        """Obtiene todas las especies de una región específica"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute(
                'SELECT * FROM species WHERE region LIKE %s',
                (f"%{region}%",)
            )
            results = cursor.fetchall()
            cursor.close()
            return results
        except Exception as e:
            logger.error(f"Error al obtener especies por región: {str(e)}")
            return []

    def get_all_species(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, scientific_name, photo_url FROM species WHERE photo_url IS NOT NULL")
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error al obtener todas las especies: {str(e)}")
            return []

    def set_species_difficulty(self, species_id, difficulty_level):
        """Establece el nivel de dificultad para una especie en los juegos
        
        Args:
            species_id (int): ID de la especie
            difficulty_level (str): Nivel de dificultad ('facil', 'medio', 'dificil')
            
        Returns:
            bool: True si se estableció con éxito, False en caso contrario
        """
        try:
            cursor = self.get_connection().cursor()
            
            # Validar que el nivel de dificultad sea válido
            if difficulty_level not in ['facil', 'medio', 'dificil']:
                logger.error(f"Nivel de dificultad no válido: {difficulty_level}")
                return False
                
            # Insertar o actualizar la dificultad
            cursor.execute("""
                INSERT INTO species_difficulty (species_id, difficulty_level)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                difficulty_level = VALUES(difficulty_level),
                updated_at = CURRENT_TIMESTAMP
            """, (species_id, difficulty_level))
            
            self.connection.commit()
            cursor.close()
            return True
            
        except Exception as e:
            logger.error(f"Error al establecer dificultad para especie ID {species_id}: {str(e)}")
            self.connection.rollback()
            return False
            
    def get_species_difficulty(self, species_id):
        """Obtiene el nivel de dificultad de una especie
        
        Args:
            species_id (int): ID de la especie
            
        Returns:
            str: Nivel de dificultad ('facil', 'medio', 'dificil') o 'medio' por defecto
        """
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT difficulty_level
                FROM species_difficulty
                WHERE species_id = %s
            """, (species_id,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result['difficulty_level']
            else:
                return 'medio'  # Nivel de dificultad por defecto
                
        except Exception as e:
            logger.error(f"Error al obtener dificultad para especie ID {species_id}: {str(e)}")
            return 'medio'  # En caso de error, devolver el nivel medio
            
    def get_species_by_difficulty(self, difficulty_level):
        """Obtiene especies por nivel de dificultad
        
        Args:
            difficulty_level (str): Nivel de dificultad ('facil', 'medio', 'dificil')
            
        Returns:
            list: Lista de especies con el nivel de dificultad especificado
        """
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    s.id,
                    s.genus,
                    s.species,
                    s.scientific_name,
                    s.photo_url,
                    sd.difficulty_level
                FROM species s
                JOIN species_difficulty sd ON s.id = sd.species_id
                WHERE sd.difficulty_level = %s
                AND s.photo_url IS NOT NULL
                ORDER BY RAND()
                LIMIT 20
            """, (difficulty_level,))
            
            results = cursor.fetchall()
            cursor.close()
            return results
            
        except Exception as e:
            logger.error(f"Error al obtener especies por dificultad {difficulty_level}: {str(e)}")
            return []

    def update_all_regions(self):
        """Actualiza las regiones de todas las especies usando datos de AntWiki e iNaturalist y normaliza a continentes"""
        
        # Diccionario de mapeo de países y regiones a continentes
        region_to_continent = {
            # América del Norte
            'mexico': 'América del Norte',
            'united states': 'América del Norte',
            'canada': 'América del Norte',
            'north america': 'América del Norte',
            
            # América del Sur
            'brazil': 'América del Sur',
            'argentina': 'América del Sur',
            'chile': 'América del Sur',
            'peru': 'América del Sur',
            'colombia': 'América del Sur',
            'venezuela': 'América del Sur',
            'ecuador': 'América del Sur',
            'bolivia': 'América del Sur',
            'paraguay': 'América del Sur',
            'uruguay': 'América del Sur',
            'south america': 'América del Sur',
            
            # Europa
            'spain': 'Europa',
            'france': 'Europa',
            'germany': 'Europa',
            'italy': 'Europa',
            'united kingdom': 'Europa',
            'portugal': 'Europa',
            'greece': 'Europa',
            'europe': 'Europa',
            
            # Asia
            'china': 'Asia',
            'japan': 'Asia',
            'india': 'Asia',
            'russia': 'Asia',
            'southeast asia': 'Asia',
            'asia': 'Asia',
            
            # África
            'south africa': 'África',
            'egypt': 'África',
            'morocco': 'África',
            'kenya': 'África',
            'africa': 'África',
            
            # Oceanía
            'australia': 'Oceanía',
            'new zealand': 'Oceanía',
            'oceania': 'Oceanía'
        }
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Obtener todas las especies
            cursor.execute('SELECT id, scientific_name, antwiki_url FROM species')
            species = cursor.fetchall()
            
            updated_count = 0
            error_count = 0
            
            for specie in species:
                try:
                    raw_region = None
                    
                    # 1. Primero intentar con AntWiki
                    if specie['antwiki_url']:
                        try:
                            response = requests.get(specie['antwiki_url'], timeout=10)
                            if response.status_code == 200:
                                html_content = response.text
                                distribution_markers = ["Distribution:", "Geographic Range:", "Native range:"]
                                for marker in distribution_markers:
                                    if marker in html_content:
                                        start_idx = html_content.find(marker) + len(marker)
                                        end_idx = html_content.find(".", start_idx)
                                        if end_idx > start_idx:
                                            raw_region = html_content[start_idx:end_idx].strip()
                                            break
                        except Exception as e:
                            logger.error(f"Error al obtener datos de AntWiki para {specie['scientific_name']}: {str(e)}")
                    
                    # 2. Si no se encontró en AntWiki, intentar con iNaturalist
                    if not raw_region:
                        cursor.execute('SELECT inaturalist_id FROM species WHERE id = %s', (specie['id'],))
                        inat_result = cursor.fetchone()
                        if inat_result and inat_result['inaturalist_id']:
                            response = requests.get(f"https://api.inaturalist.org/v1/taxa/{inat_result['inaturalist_id']}")
                            if response.status_code == 200:
                                inat_data = response.json()['results'][0]
                                
                                if 'establishment_means' in inat_data and inat_data['establishment_means'] == 'native':
                                    native_places = [place['name'] for place in inat_data.get('native_places', [])]
                                    if native_places:
                                        raw_region = ", ".join(native_places)
                    
                    # 3. Normalizar la región a continentes
                    continents = set()
                    if raw_region:
                        raw_region = raw_region.lower()
                        for region, continent in region_to_continent.items():
                            if region in raw_region:
                                continents.add(continent)
                    
                    final_region = ", ".join(sorted(continents)) if continents else "Desconocido"
                    
                    # Actualizar región en la base de datos
                    update_cursor = self.connection.cursor()
                    update_cursor.execute(
                        'UPDATE species SET region = %s WHERE id = %s',
                        (final_region, specie['id'])
                    )
                    self.connection.commit()
                    updated_count += 1
                    logger.info(f"Región actualizada para {specie['scientific_name']}: {final_region}")
                            
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error al actualizar región para {specie['scientific_name']}: {str(e)}")
            
            return {
                'total': len(species),
                'updated': updated_count,
                'errors': error_count
            }
            
        except Exception as e:
            logger.error(f"Error al actualizar regiones: {str(e)}")
            return {
                'total': 0,
                'updated': 0,
                'errors': 1
            }
        finally:
            if cursor:
                cursor.close()

    def reset_tables(self):
        """Reinicia todas las tablas de la base de datos"""
        try:
            cursor = self.connection.cursor()
            
            # Desactivar verificación de claves foráneas temporalmente
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # Eliminar todas las tablas en orden
            tables = [
                "search_stats",
                "searches",
                "species_synonyms",
                "flight_stats",
                "species_info",
                "species_images",
                "antontop_info",
                "species_difficulty",
                "species"
            ]
            
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            
            # Reactivar verificación de claves foráneas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            # Recrear las tablas
            self.setup_database()
            
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error al reiniciar las tablas: {str(e)}")
            self.connection.rollback()
            return False

    def add_flight_stats(self, species_id, stats_type, value, count, hemisphere='World'):
        """Añade o actualiza estadísticas de vuelos nupciales"""
        try:
            cursor = self.connection.cursor()
            
            if stats_type == 'month':
                cursor.execute("""
                    INSERT INTO flight_stats (species_id, month, flight_count, hemisphere)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE flight_count = %s
                """, (species_id, value, count, hemisphere, count))
            elif stats_type == 'hour':
                cursor.execute("""
                    INSERT INTO flight_stats (species_id, hour, flight_count, hemisphere)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE flight_count = %s
                """, (species_id, value, count, hemisphere, count))
            elif stats_type == 'temperature':
                cursor.execute("""
                    INSERT INTO flight_stats (species_id, temperature_c, flight_count, hemisphere)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE flight_count = %s
                """, (species_id, value, count, hemisphere, count))
            elif stats_type == 'moon':
                cursor.execute("""
                    INSERT INTO flight_stats (species_id, moon_phase, flight_count, hemisphere)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE flight_count = %s
                """, (species_id, value, count, hemisphere, count))
                
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error al añadir estadísticas de vuelo: {str(e)}")
            self.connection.rollback()
            return False

    def get_flight_stats(self, species_id, stats_type=None):
        """Obtiene las estadísticas de vuelos nupciales para una especie"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            if stats_type == 'month':
                cursor.execute("""
                    SELECT month, flight_count, hemisphere
                    FROM flight_stats
                    WHERE species_id = %s AND month IS NOT NULL
                    ORDER BY month
                """, (species_id,))
            elif stats_type == 'hour':
                cursor.execute("""
                    SELECT hour, flight_count, hemisphere
                    FROM flight_stats
                    WHERE species_id = %s AND hour IS NOT NULL
                    ORDER BY hour
                """, (species_id,))
            elif stats_type == 'temperature':
                cursor.execute("""
                    SELECT temperature_c, flight_count, hemisphere
                    FROM flight_stats
                    WHERE species_id = %s AND temperature_c IS NOT NULL
                    ORDER BY temperature_c
                """, (species_id,))
            elif stats_type == 'moon':
                cursor.execute("""
                    SELECT moon_phase, flight_count, hemisphere
                    FROM flight_stats
                    WHERE species_id = %s AND moon_phase IS NOT NULL
                """, (species_id,))
            else:
                cursor.execute("""
                    SELECT * FROM flight_stats
                    WHERE species_id = %s
                """, (species_id,))
                
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de vuelo: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def create_flight_stats_table(self):
        """Crea la tabla flight_stats si no existe"""
        try:
            cursor = self.connection.cursor()
            
            # Crear tabla de estadísticas de vuelos nupciales
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS flight_stats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    species_id INT NOT NULL,
                    month INT,
                    hour INT,
                    temperature_c FLOAT,
                    moon_phase VARCHAR(50),
                    flight_count INT DEFAULT 0,
                    hemisphere VARCHAR(20),
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (species_id) REFERENCES species(id) ON DELETE CASCADE,
                    INDEX idx_species_month (species_id, month),
                    INDEX idx_species_hour (species_id, hour),
                    INDEX idx_species_temp (species_id, temperature_c)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')
            
            self.connection.commit()
            logger.info("Tabla flight_stats creada correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error al crear la tabla flight_stats: {str(e)}")
            self.connection.rollback()
            return False
            
    async def log_user_interaction(self, user_id, username, interaction_type, command_name=None, points=None, chat_id=None):
        """Registra una interacción de usuario y actualiza la experiencia"""
        cursor = None
        try:
            logger.info(f"log_user_interaction llamado: user_id={user_id}, username={username}, interaction_type={interaction_type}, command_name={command_name}, points={points}, chat_id={chat_id}")
            
            # Ensure connection is established
            self.ensure_connection()
            if not self.connection or not self.connection.is_connected():
                logger.error("No hay conexión a la base de datos")
                return False

            cursor = self.connection.cursor()
            
            # Verificar si el usuario está haciendo spam (excepto para el juego)
            if interaction_type != 'game_guess':
                is_spam_detected = self.is_spam(user_id, interaction_type, chat_id)
                if is_spam_detected:
                    logger.warning(f"Posible spam detectado del usuario {username} ({user_id}) en el chat {chat_id}")
                    await self.notify_spam_detected(user_id, username, chat_id, interaction_type)
                    return False
            
            # Determinar puntos basados en el tipo de interacción si no se especifican
            if points is None:
                points = 0
                if interaction_type == 'message':
                    points = 1  # Mensajes normales: 1 XP
                elif interaction_type == 'photo':
                    points = 5  # Fotos: 5 XP
                elif interaction_type == 'command':
                    if command_name in ['ayuda', 'hormidato', 'especie', 'normas']:
                        points = 2  # Comandos de información: 2 XP
                elif interaction_type == 'game_guess':
                    points = 10  # Aciertos en el juego: 10 XP
            
            logger.info(f"Puntos determinados: {points} para interaction_type: {interaction_type}")
            
            # Verificar si el usuario ya alcanzó el límite diario
            if self.reached_daily_xp_limit(user_id, chat_id):
                logger.info(f"Usuario {username} alcanzó el límite diario de XP (100 XP)")
                return False
            
            # Insertar registro de interacción
            cursor.execute("""
                INSERT INTO user_interactions 
                (user_id, username, interaction_type, command_name, points, chat_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, username, interaction_type, command_name, points, chat_id))
            
            logger.info(f"Registro insertado en user_interactions con {points} puntos")
            
            # Si la interacción otorga puntos, actualizar experiencia
            if points > 0:
                logger.info(f"Actualizando experiencia para usuario {user_id} con {points} puntos")
                
                # Obtener experiencia actual
                cursor.execute("""
                    SELECT total_xp, current_level 
                    FROM user_experience 
                    WHERE user_id = %s AND chat_id = %s
                """, (user_id, chat_id))
                
                result = cursor.fetchone()
                if result:
                    current_xp = result[0]
                    current_level = result[1]
                    logger.info(f"XP actual del usuario: {current_xp}, nivel actual: {current_level}")
                else:
                    current_xp = 0
                    current_level = 1
                    logger.info("Usuario nuevo - XP inicial: 0, nivel inicial: 1")
                
                # Calcular nuevo XP y nivel
                new_xp = current_xp + points
                new_level = self.calcular_nivel(new_xp)
                
                logger.info(f"Nuevo XP: {new_xp}, nuevo nivel: {new_level}")
                
                # Actualizar o insertar experiencia
                if result:
                    cursor.execute("""
                        UPDATE user_experience 
                        SET total_xp = %s,
                            current_level = %s,
                            last_message_time = NOW(),
                            updated_at = NOW()
                        WHERE user_id = %s AND chat_id = %s
                    """, (new_xp, new_level, user_id, chat_id))
                    logger.info("Experiencia actualizada en la base de datos")
                else:
                    cursor.execute("""
                        INSERT INTO user_experience 
                        (user_id, username, total_xp, current_level, chat_id, last_message_time)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                    """, (user_id, username, new_xp, new_level, chat_id))
                    logger.info("Nuevo registro de experiencia insertado en la base de datos")
                
                # Si subió de nivel, registrar en el log
                if new_level > current_level:
                    logger.info(f"Usuario {username} subió al nivel {new_level}")
            
            # Commit the transaction
            self.connection.commit()
            logger.info(f"Interacción registrada exitosamente: {interaction_type} para usuario {username} con {points} puntos")
            return True
            
        except Exception as e:
            logger.error(f"Error al registrar interacción de usuario: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def is_spam(self, user_id, interaction_type, chat_id):
        """Verifica si una interacción es spam basado en la frecuencia"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Obtener el tiempo de inicio del bot (cuando se creó la instancia de la base de datos)
            if not hasattr(self, 'bot_start_time'):
                self.bot_start_time = datetime.now()
            
            # Definir ventana de tiempo para análisis de spam (último minuto desde inicio del bot)
            time_window_start = max(
                datetime.now() - timedelta(minutes=1),  # Último minuto
                self.bot_start_time + timedelta(seconds=30)  # Mínimo 30 segundos después del inicio
            )
            
            # Solo considerar interacciones recientes y posteriores al inicio del bot
            cursor.execute("""
                SELECT created_at
                FROM user_interactions
                WHERE user_id = %s 
                AND interaction_type = %s 
                AND chat_id = %s
                AND created_at >= %s
                ORDER BY created_at DESC
            """, (user_id, interaction_type, chat_id, time_window_start))
            
            interactions = cursor.fetchall()
            
            if not interactions:
                return False
            
            # Límites de frecuencia por tipo de interacción
            limites = {
                'message': 15,    # 15 mensajes por minuto
                'photo': 8,       # 8 fotos por minuto
                'video': 6,       # 6 videos por minuto
                'command': 8,     # 8 comandos por minuto
                'reaction': 20    # 20 reacciones por minuto
            }
            
            limite = limites.get(interaction_type, 15)
            
            # Analizar la distribución temporal de las interacciones
            now = datetime.now()
            count_recent = 0
            
            # Contar solo interacciones que están distribuidas temporalmente de forma natural
            for interaction in interactions:
                time_diff = (now - interaction['created_at']).total_seconds()
                if time_diff <= 60:  # Último minuto
                    count_recent += 1
            
            # Si hay muchas interacciones, verificar si están distribuidas naturalmente
            if count_recent >= limite:
                # Verificar si las interacciones están muy agrupadas en tiempo
                if len(interactions) >= 5:
                    # Calcular la distribución temporal
                    times = [interaction['created_at'] for interaction in interactions[:10]]  # Últimas 10
                    time_diffs = []
                    
                    for i in range(1, len(times)):
                        diff = (times[i-1] - times[i]).total_seconds()
                        time_diffs.append(abs(diff))
                    
                    # Si la mayoría de las interacciones están muy juntas (menos de 2 segundos de diferencia)
                    # es probable que sean del procesamiento inicial del bot
                    if time_diffs:
                        avg_diff = sum(time_diffs) / len(time_diffs)
                        very_close_count = sum(1 for diff in time_diffs if diff < 2.0)
                        
                        # Si más del 70% de las interacciones están muy juntas temporalmente,
                        # probablemente sea procesamiento inicial del bot
                        if very_close_count / len(time_diffs) > 0.7 and avg_diff < 3.0:
                            logger.info(f"Interacciones agrupadas detectadas para usuario {user_id} - posible procesamiento inicial del bot")
                            return False
                
                logger.warning(f"Posible spam detectado: Usuario {user_id} en chat {chat_id}, tipo {interaction_type}, {count_recent} interacciones en el último minuto (límite: {limite})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error al verificar spam: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def notify_spam_detected(self, user_id, username, chat_id, interaction_type, command_name=None, points=0):
        """
        Notifica al usuario que se ha detectado comportamiento de spam
        """
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Verificar si ya se notificó recientemente
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM user_interactions
                WHERE user_id = %s 
                AND interaction_type = 'spam_notification'
                AND chat_id = %s
                AND created_at >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
            """, (user_id, chat_id))
            
            result = cursor.fetchone()
            if result and result['count'] > 0:
                return False  # Ya se notificó recientemente
            
            # Registrar la notificación
            cursor.execute("""
                INSERT INTO user_interactions 
                (user_id, username, interaction_type, command_name, points, chat_id)
                VALUES (%s, %s, 'spam_notification', %s, %s, %s)
            """, (user_id, username, command_name, points, chat_id))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error al registrar notificación de spam: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def reached_daily_xp_limit(self, user_id, chat_id, limit=100):
        """
        Verifica si un usuario ha alcanzado el límite diario de XP
        """
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Consultar puntos totales ganados hoy por el usuario en este chat
            cursor.execute("""
                SELECT SUM(points) as total_daily_points
                FROM user_interactions
                WHERE user_id = %s 
                AND chat_id = %s
                AND DATE(created_at) = CURDATE()
            """, (user_id, chat_id))
            
            result = cursor.fetchone()
            
            # Si no hay registros, no ha alcanzado el límite
            if not result or result['total_daily_points'] is None:
                return False
                
            # Verificar si ya superó el límite diario
            return result['total_daily_points'] >= limit
            
        except Exception as e:
            logger.error(f"Error al verificar límite diario de XP: {str(e)}")
            return False  # En caso de error, permitir la interacción
        finally:
            if cursor:
                cursor.close()

    def is_approaching_daily_limit(self, user_id, chat_id, limit=100, threshold=0.8):
        """
        Verifica si un usuario está cerca de alcanzar el límite diario de XP
        El threshold define qué tan cerca (por defecto 80% del límite)
        """
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Consultar puntos totales ganados hoy por el usuario en este chat
            cursor.execute("""
                SELECT SUM(points) as total_daily_points
                FROM user_interactions
                WHERE user_id = %s 
                AND chat_id = %s
                AND DATE(created_at) = CURDATE()
            """, (user_id, chat_id))
            
            result = cursor.fetchone()
            
            # Si no hay registros, no está cerca del límite
            if not result or result['total_daily_points'] is None:
                return False
                
            # Verificar si está cerca del límite (por defecto 80%)
            threshold_points = limit * threshold
            return result['total_daily_points'] >= threshold_points and result['total_daily_points'] < limit
            
        except Exception as e:
            logger.error(f"Error al verificar proximidad al límite diario: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def calcular_nivel(self, xp):
        """
        Calcula el nivel basado en XP con un sistema equilibrado y sostenible
        
        Nuevo sistema de progresión:
        - Niveles 1-10: Progresión lineal rápida (inicio accesible)
        - Niveles 11-30: Progresión moderada (crecimiento controlado)  
        - Niveles 31-60: Progresión estable (desafío constante)
        - Niveles 61-100: Progresión alta (niveles de élite)
        """
        if xp < 0:
            return 1
            
        nivel = 1
        xp_acumulado = 0
        
        # Calcular nivel iterando a través de los rangos
        while nivel <= 100:
            xp_necesario = self.calcular_xp_para_nivel(nivel + 1)
            
            if xp_acumulado + xp_necesario > xp:
                break
                
            xp_acumulado += xp_necesario
            nivel += 1
            
        return min(nivel, 100)  # Máximo nivel 100
    
    def calcular_xp_para_nivel(self, nivel):
        """
        Calcula el XP necesario para alcanzar un nivel específico desde el anterior
        
        Fórmula progresiva equilibrada:
        - Niveles 1-10: Crecimiento lineal suave
        - Niveles 11-30: Crecimiento moderado
        - Niveles 31-60: Crecimiento estable
        - Niveles 61-100: Crecimiento para élite
        """
        if nivel <= 1:
            return 0
        elif nivel <= 10:
            # Progresión inicial: 75, 100, 125, 150, 175, 200, 225, 250, 275
            return 50 + (nivel - 1) * 25
        elif nivel <= 30:
            # Progresión moderada: incremento de 40 XP por nivel
            return 275 + (nivel - 10) * 40
        elif nivel <= 60:
            # Progresión estable: incremento de 75 XP por nivel
            return 1075 + (nivel - 30) * 75
        else:
            # Progresión alta: incremento de 125 XP por nivel
            return 3325 + (nivel - 60) * 125
    
    def calcular_xp_total_para_nivel(self, nivel_objetivo):
        """
        Calcula el XP total necesario para alcanzar un nivel específico
        """
        xp_total = 0
        for nivel in range(2, nivel_objetivo + 1):
            xp_total += self.calcular_xp_para_nivel(nivel)
        return xp_total
    
    def calcular_progreso_nivel(self, xp_actual):
        """
        Calcula el progreso hacia el siguiente nivel
        Retorna: (nivel_actual, xp_en_nivel_actual, xp_necesario_siguiente)
        """
        nivel_actual = self.calcular_nivel(xp_actual)
        
        if nivel_actual >= 100:
            return 100, 0, 0
            
        xp_total_nivel_actual = self.calcular_xp_total_para_nivel(nivel_actual)
        xp_en_nivel = xp_actual - xp_total_nivel_actual
        xp_necesario_siguiente = self.calcular_xp_para_nivel(nivel_actual + 1)
        
        return nivel_actual, xp_en_nivel, xp_necesario_siguiente

    def get_weekly_leaderboard(self):
        """Obtiene el ranking semanal de usuarios"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Obtener el inicio de la semana actual (lunes)
            cursor.execute("""
                SELECT 
                    user_id,
                    username,
                    SUM(points) as total_points,
                    COUNT(*) as interactions
                FROM user_interactions
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
                GROUP BY user_id, username
                ORDER BY total_points DESC
                LIMIT 10
            """)
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error al obtener ranking semanal: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_monthly_leaderboard(self):
        """Obtiene el ranking mensual de usuarios"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Obtener el inicio del mes actual
            cursor.execute("""
                SELECT 
                    user_id,
                    username,
                    SUM(points) as total_points,
                    COUNT(*) as interactions
                FROM user_interactions
                WHERE created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
                GROUP BY user_id, username
                ORDER BY total_points DESC
                LIMIT 10
            """)
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error al obtener ranking mensual: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def add_reward(self, user_id, reward_type, description):
        """Añade una recompensa para un usuario"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO rewards (user_id, reward_type, reward_description)
                VALUES (%s, %s, %s)
            """, (user_id, reward_type, description))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error al añadir recompensa: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def claim_reward(self, user_id, reward_id):
        """Marca una recompensa como reclamada"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                UPDATE rewards 
                SET claimed = TRUE, claimed_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s AND claimed = FALSE
            """, (reward_id, user_id))
            
            self.connection.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Error al reclamar recompensa: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_user_rewards(self, user_id):
        """Obtiene las recompensas de un usuario"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM rewards
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error al obtener recompensas de usuario: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    # Nuevas funciones para manejar la aprobación de fotos

    def register_pending_photo(self, user_id, username, message_id, chat_id):
        """Registra una foto pendiente de aprobación"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute("""
                INSERT INTO pending_photos 
                (user_id, username, message_id, chat_id)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                approved = FALSE,
                approved_by = NULL,
                xp_given = FALSE,
                updated_at = CURRENT_TIMESTAMP
            """, (user_id, username, message_id, chat_id))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error al registrar foto pendiente: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def approve_photo(self, message_id, chat_id, approver_id):
        """Aprueba una foto pendiente"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Obtener la información de la foto pendiente
            cursor.execute("""
                SELECT * FROM pending_photos
                WHERE message_id = %s AND chat_id = %s AND approved = FALSE
            """, (message_id, chat_id))
            
            photo = cursor.fetchone()
            if not photo:
                logger.warning(f"No se encontró foto pendiente para aprobar con message_id {message_id} en chat {chat_id}")
                return None
            
            # Marcar la foto como aprobada
            cursor.execute("""
                UPDATE pending_photos
                SET approved = TRUE, 
                    approved_by = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE message_id = %s AND chat_id = %s
            """, (approver_id, message_id, chat_id))
            
            self.connection.commit()
            return photo
            
        except Exception as e:
            logger.error(f"Error al aprobar foto: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return None
        finally:
            if cursor:
                cursor.close()
    

    async def give_xp_for_approved_photo(self, message_id, chat_id):
        """Otorga XP por una foto aprobada"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            # Obtener la información de la foto aprobada
            cursor.execute("""
                SELECT * FROM pending_photos
                WHERE message_id = %s AND chat_id = %s AND approved = TRUE AND xp_given = FALSE
            """, (message_id, chat_id))
            
            photo = cursor.fetchone()
            if not photo:
                logger.warning(f"No se encontró foto aprobada para dar XP con message_id {message_id} en chat {chat_id}")
                return False
            
            # Registrar interacción para dar XP
            await self.log_user_interaction(
                user_id=photo['user_id'],
                username=photo['username'],
                interaction_type='photo',
                command_name=None,
                chat_id=photo['chat_id']
            )
            
            # Marcar XP como otorgado
            cursor.execute("""
                UPDATE pending_photos
                SET xp_given = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE message_id = %s AND chat_id = %s
            """, (message_id, chat_id))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error al dar XP por foto aprobada: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
                
    def is_photo_approved(self, message_id, chat_id):
        """Verifica si una foto ya fue aprobada"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT approved, xp_given 
                FROM pending_photos
                WHERE message_id = %s AND chat_id = %s
            """, (message_id, chat_id))
            
            result = cursor.fetchone()
            if not result:
                return False
                
            return result['approved']
            
        except Exception as e:
            logger.error(f"Error al verificar si la foto está aprobada: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def reset_bot_start_time(self):
        """Resetea el tiempo de inicio del bot"""
        self.bot_start_time = datetime.now()

    def save_antontop_info(self, species_id, scientific_name, info):
        """Guarda la información de la especie obtenida de AntOnTop"""
        try:
            cursor = self.get_connection().cursor()
            
            # Preparar los datos para insertar o actualizar
            data = (
                species_id,
                scientific_name,
                info.get('description', ''),
                info.get('short_description', ''),
                info.get('photo_url', ''),
                info.get('region', ''),
                info.get('behavior', ''),
                info.get('difficulty', ''),
                info.get('temperature', ''),
                info.get('humidity', ''),
                info.get('queen_size', ''),
                info.get('worker_size', ''),
                info.get('colony_size', '')
            )
            
            # Query para insertar o actualizar (REPLACE INTO)
            query = """
                REPLACE INTO antontop_info (
                    species_id, scientific_name, description, short_description, 
                    photo_url, region, behavior, difficulty, temperature, 
                    humidity, queen_size, worker_size, colony_size
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, data)
            self.connection.commit()
            logger.info(f"Información de AntOnTop guardada para especie ID {species_id}: {scientific_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error al guardar información de AntOnTop para {scientific_name}: {str(e)}")
            return False
            
    def get_antontop_info(self, species_id):
        """Obtiene la información de AntOnTop para una especie específica"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            query = """
                SELECT * FROM antontop_info
                WHERE species_id = %s
            """
            
            cursor.execute(query, (species_id,))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"Información de AntOnTop recuperada para especie ID {species_id}")
                return result
                
            return None
            
        except Exception as e:
            logger.error(f"Error al obtener información de AntOnTop para especie ID {species_id}: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
                
    def get_antontop_info_by_name(self, scientific_name):
        """Obtiene la información de AntOnTop para una especie por nombre científico"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            query = """
                SELECT * FROM antontop_info
                WHERE scientific_name = %s
            """
            
            cursor.execute(query, (scientific_name,))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"Información de AntOnTop recuperada para especie: {scientific_name}")
                return result
                
            return None
            
        except Exception as e:
            logger.error(f"Error al obtener información de AntOnTop para {scientific_name}: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def set_temp_data(self, key, value, expire=300):
        """Almacena datos temporales con tiempo de expiración.
        
        Args:
            key (str): Clave para identificar los datos
            value: Valor a almacenar (se convertirá a string)
            expire (int): Tiempo de expiración en segundos (por defecto 5 minutos)
        """
        try:
            cursor = self.get_connection().cursor()
            cursor.execute("""
                INSERT INTO temp_data (id, value, expires_at)
                VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL %s SECOND))
                ON DUPLICATE KEY UPDATE
                    value = VALUES(value),
                    expires_at = VALUES(expires_at)
            """, (key, str(value), expire))
            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error al guardar datos temporales: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()
    
    def get_temp_data(self, key):
        """Recupera datos temporales si no han expirado.
        
        Args:
            key (str): Clave de los datos a recuperar
            
        Returns:
            El valor almacenado o None si no existe o ha expirado
        """
        try:
            cursor = self.get_connection().cursor()
            
            # Eliminar datos expirados
            cursor.execute("DELETE FROM temp_data WHERE expires_at < NOW()")
            self.connection.commit()
            
            # Obtener datos
            cursor.execute("SELECT value FROM temp_data WHERE id = %s", (key,))
            result = cursor.fetchone()
            
            if result:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error al recuperar datos temporales: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
                
    def delete_temp_data(self, key):
        """
        Elimina datos temporales basados en una clave
        
        Args:
            key (str): Clave única para identificar los datos
            
        Returns:
            bool: True si la operación tuvo éxito, False en caso contrario
        """
        cursor = None
        try:
            self.ensure_connection()
            cursor = self.connection.cursor()
            
            # Eliminar los datos temporales
            cursor.execute("DELETE FROM temp_data WHERE id = %s", (key,))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error al eliminar datos temporales: {str(e)}")
            if self.connection:
                self.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def reset_daily_xp_limits(self):
        """Restablece los límites diarios de XP para todos los usuarios"""
        try:
            cursor = self.get_connection().cursor()
            
            # Actualizar la fecha de último XP para todos los usuarios
            # Esto hará que reached_daily_xp_limit() retorne False
            cursor.execute("""
                UPDATE user_experience
                SET last_xp_date = NULL
                WHERE DATE(last_xp_date) = CURDATE()
            """)
            
            self.get_connection().commit()
            cursor.close()
            logger.info("Límites de XP restablecidos en la base de datos")
            return True
        except Exception as e:
            logger.error(f"Error al restablecer límites de XP: {str(e)}")
            return False

    def get_species(self, scientific_name: str) -> Optional[Dict]:
        """Obtiene una especie por su nombre científico"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT s.*, a.*
                FROM species s
                LEFT JOIN antontop_info a ON s.id = a.species_id
                WHERE s.scientific_name = %s
            """, (scientific_name,))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"Error al obtener especie: {str(e)}")
            return None
        finally:
            cursor.close()

    def get_random_species(self):
        """Obtiene una especie aleatoria con foto"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT id, scientific_name, photo_url
                FROM species
                WHERE photo_url IS NOT NULL
                ORDER BY RAND()
                LIMIT 1
            """)
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error al obtener especie aleatoria: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def can_play_guessing_game(self, user_id, chat_id):
        """Verifica si el usuario puede jugar al juego de adivinar la especie"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT attempts, last_attempt
                FROM species_guessing_game
                WHERE user_id = %s AND chat_id = %s
                AND last_attempt >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """, (user_id, chat_id))
            
            result = cursor.fetchone()
            if not result:
                return True
                
            return result['attempts'] < 3
        except Exception as e:
            logger.error(f"Error al verificar si puede jugar: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_next_game_time(self, user_id, chat_id):
        """Obtiene la hora exacta en la que el usuario podrá jugar de nuevo"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT last_attempt, 
                       DATE_ADD(last_attempt, INTERVAL 24 HOUR) as next_game_time,
                       attempts
                FROM species_guessing_game
                WHERE user_id = %s AND chat_id = %s
                AND attempts >= 3
                AND last_attempt >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                ORDER BY last_attempt DESC
                LIMIT 1
            """, (user_id, chat_id))
            
            result = cursor.fetchone()
            if result:
                # Formatear la fecha para España (hora local)
                next_time = result['next_game_time']
                
                # Verificar si ya puede jugar (por si acaso)
                from datetime import datetime
                now = datetime.now()
                if next_time <= now:
                    return None  # Ya puede jugar
                
                # Formatear según si es hoy, mañana o después
                if next_time.date() == now.date():
                    return f"{next_time.strftime('%H:%M')} (hoy)"
                elif (next_time.date() - now.date()).days == 1:
                    return f"{next_time.strftime('%H:%M')} (mañana)"
                else:
                    return next_time.strftime("%H:%M del %d/%m/%Y")
            return None
        except Exception as e:
            logger.error(f"Error al obtener próxima hora de juego: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    async def register_game_attempt(self, user_id, chat_id, species_id, is_correct):
        """Registra un intento del juego de adivinar la especie"""
        try:
            cursor = self.get_connection().cursor()
            # Verificar si ya existe un registro para este usuario en las últimas 24h
            cursor.execute("""
                SELECT id, attempts
                FROM species_guessing_game
                WHERE user_id = %s AND chat_id = %s
                AND last_attempt >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """, (user_id, chat_id))
            result = cursor.fetchone()
            
            if result:
                # Actualizar intentos existentes
                cursor.execute("""
                    UPDATE species_guessing_game
                    SET attempts = attempts + 1,
                        last_attempt = NOW(),
                        species_id = %s
                    WHERE id = %s
                """, (species_id or result[1], result[0]))
            else:
                # Crear nuevo registro
                cursor.execute("""
                    INSERT INTO species_guessing_game
                    (user_id, chat_id, species_id, attempts)
                    VALUES (%s, %s, %s, 1)
                """, (user_id, chat_id, species_id or 0))
            
            self.connection.commit()
            logger.info(f"Intento de juego registrado: usuario {user_id}, correcto: {is_correct}")
            return True
        except Exception as e:
            logger.error(f"Error al registrar intento del juego: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_species_by_id(self, species_id):
        """Obtiene una especie por su ID"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT id, scientific_name, photo_url
                FROM species
                WHERE id = %s
            """, (species_id,))
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"Error al obtener especie por ID: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def create_tables(self):
        """Crea las tablas necesarias si no existen"""
        try:
            cursor = self.get_connection().cursor()
            
            # Tabla para intentos del juego
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_attempts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    species_id INT NOT NULL,
                    is_correct BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (species_id) REFERENCES species(id)
                )
            """)
            
            # Tabla para datos temporales
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS temp_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    key_name VARCHAR(255) NOT NULL,
                    value TEXT,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_key (key_name)
                )
            """)
            
            self.get_connection().commit()
            return True
        except Exception as e:
            logger.error(f"Error al crear tablas: {str(e)}")
            return False

    def get_cached_description(self, scientific_name: str) -> Optional[str]:
        """Obtiene la descripción guardada de una especie"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT description, last_updated 
                FROM species_descriptions 
                WHERE scientific_name = %s
            """, (scientific_name,))
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                # Verificar si la descripción tiene más de 30 días
                last_updated = result['last_updated']
                if last_updated:
                    days_old = (datetime.now() - last_updated).days
                    if days_old > 30:
                        return None  # Forzar regeneración si es muy antigua
                return result['description']
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo descripción de especie: {str(e)}")
            return None

    def save_species_description(self, scientific_name: str, description: str) -> bool:
        """
        Guarda la descripción de una especie en caché
        """
        try:
            cursor = self.get_connection().cursor()
            
            # Insertar o actualizar la descripción usando las columnas correctas
            query = """
                INSERT INTO species_descriptions (scientific_name, description, last_updated) 
                VALUES (%s, %s, NOW()) 
                ON DUPLICATE KEY UPDATE 
                description = VALUES(description), 
                last_updated = NOW()
            """
            
            cursor.execute(query, (scientific_name, description))
            self.connection.commit()
            logger.info(f"Descripción guardada para {scientific_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error al guardar descripción de {scientific_name}: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def create_translation_tables(self):
        """Crea las tablas necesarias para el sistema de traducción"""
        try:
            cursor = self.get_connection().cursor()
            
            # Tabla para preferencias de idioma de usuarios
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_languages (
                    user_id BIGINT PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    language_code VARCHAR(10) NOT NULL,
                    is_spanish_native BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_chat_user (chat_id, user_id),
                    INDEX idx_language (language_code)
                )
            """)
            
            # Tabla para cachear traducciones y evitar retraducir
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translation_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    original_text TEXT NOT NULL,
                    source_lang VARCHAR(10) NOT NULL,
                    target_lang VARCHAR(10) NOT NULL,
                    translated_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_translation (original_text(100), source_lang, target_lang),
                    INDEX idx_created (created_at)
                )
            """)
            
            # Tabla para mensajes pendientes de traducción (para procesamiento asíncrono)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translation_queue (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    message_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    original_text TEXT NOT NULL,
                    source_lang VARCHAR(10),
                    target_users JSON,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_pending (processed, created_at),
                    INDEX idx_message (message_id, chat_id)
                )
            """)
            
            self.connection.commit()
            logger.info("Tablas de traducción creadas exitosamente")
            
        except Exception as e:
            logger.error(f"Error al crear tablas de traducción: {str(e)}")
        finally:
            if cursor:
                cursor.close()

    def set_user_language(self, user_id: int, chat_id: int, language_code: str, username: str = None, first_name: str = None):
        """Establece el idioma preferido de un usuario"""
        try:
            cursor = self.get_connection().cursor()
            
            is_spanish_native = language_code in ['es', 'es-ES', 'es-MX', 'es-AR', 'es-CL', 'es-CO']
            
            query = """
                INSERT INTO user_languages 
                (user_id, chat_id, username, first_name, language_code, is_spanish_native)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                username = VALUES(username),
                first_name = VALUES(first_name),
                language_code = VALUES(language_code),
                is_spanish_native = VALUES(is_spanish_native),
                updated_at = CURRENT_TIMESTAMP
            """
            
            cursor.execute(query, (user_id, chat_id, username, first_name, language_code, is_spanish_native))
            self.connection.commit()
            logger.info(f"Idioma {language_code} establecido para usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error al establecer idioma: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_user_language(self, user_id: int, chat_id: int):
        """Obtiene el idioma preferido de un usuario"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            query = """
                SELECT language_code, is_spanish_native 
                FROM user_languages 
                WHERE user_id = %s AND chat_id = %s
            """
            
            cursor.execute(query, (user_id, chat_id))
            result = cursor.fetchone()
            
            return result
            
        except Exception as e:
            logger.error(f"Error al obtener idioma del usuario: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def get_users_for_translation(self, chat_id: int, exclude_user_id: int = None):
        """Obtiene usuarios que necesitan traducción en un chat"""
        try:
            cursor = self.get_connection().cursor(dictionary=True)
            
            query = """
                SELECT user_id, language_code, is_spanish_native 
                FROM user_languages 
                WHERE chat_id = %s AND is_spanish_native = FALSE
            """
            params = [chat_id]
            
            if exclude_user_id:
                query += " AND user_id != %s"
                params.append(exclude_user_id)
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error al obtener usuarios para traducción: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def cache_translation(self, original_text: str, source_lang: str, target_lang: str, translated_text: str):
        """Guarda una traducción en caché"""
        try:
            cursor = self.get_connection().cursor()
            
            # Limpiar caché antiguo (más de 30 días)
            cursor.execute("""
                DELETE FROM translation_cache 
                WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
            """)
            
            # Guardar nueva traducción
            query = """
                INSERT INTO translation_cache 
                (original_text, source_lang, target_lang, translated_text)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                translated_text = VALUES(translated_text)
            """
            
            cursor.execute(query, (original_text[:1000], source_lang, target_lang, translated_text))
            self.connection.commit()
            
        except Exception as e:
            logger.error(f"Error al cachear traducción: {str(e)}")
        finally:
            if cursor:
                cursor.close()

    def get_cached_translation(self, original_text: str, source_lang: str, target_lang: str):
        """Busca una traducción en caché"""
        try:
            cursor = self.get_connection().cursor()
            
            query = """
                SELECT translated_text 
                FROM translation_cache 
                WHERE original_text = %s AND source_lang = %s AND target_lang = %s
                AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
            """
            
            cursor.execute(query, (original_text[:1000], source_lang, target_lang))
            result = cursor.fetchone()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error al buscar traducción en caché: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def is_user_new_to_chat(self, user_id: int, chat_id: int):
        """Verifica si un usuario es nuevo en el chat (primera interacción)"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM user_interactions 
                WHERE user_id = %s AND chat_id = %s
            """, (user_id, chat_id))
            
            count = cursor.fetchone()[0]
            cursor.close()
            
            return count == 0
            
        except Exception as e:
            logger.error(f"Error al verificar si el usuario es nuevo: {str(e)}")
            return False
    
    def ya_notificado_limite_hoy(self, user_id: int, chat_id: int, fecha: str) -> bool:
        """Verifica si ya se notificó al usuario sobre el límite diario hoy"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM daily_limit_notifications 
                WHERE user_id = %s AND chat_id = %s 
                AND notification_type = 'limit_reached' 
                AND notification_date = %s
            """, (user_id, chat_id, fecha))
            
            count = cursor.fetchone()[0]
            cursor.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error al verificar notificación de límite: {str(e)}")
            return False
    
    def ya_notificado_acercamiento_hoy(self, user_id: int, chat_id: int, fecha: str) -> bool:
        """Verifica si ya se notificó al usuario sobre acercarse al límite hoy"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM daily_limit_notifications 
                WHERE user_id = %s AND chat_id = %s 
                AND notification_type = 'approaching_limit' 
                AND notification_date = %s
            """, (user_id, chat_id, fecha))
            
            count = cursor.fetchone()[0]
            cursor.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error al verificar notificación de acercamiento: {str(e)}")
            return False
    
    def registrar_notificacion_limite(self, user_id: int, chat_id: int, fecha: str):
        """Registra que se notificó al usuario sobre el límite diario"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT IGNORE INTO daily_limit_notifications 
                (user_id, chat_id, notification_type, notification_date)
                VALUES (%s, %s, 'limit_reached', %s)
            """, (user_id, chat_id, fecha))
            
            cursor.close()
            logger.info(f"Notificación de límite registrada para usuario {user_id} en chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error al registrar notificación de límite: {str(e)}")
    
    def registrar_notificacion_acercamiento(self, user_id: int, chat_id: int, fecha: str):
        """Registra que se notificó al usuario sobre acercarse al límite"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT IGNORE INTO daily_limit_notifications 
                (user_id, chat_id, notification_type, notification_date)
                VALUES (%s, %s, 'approaching_limit', %s)
            """, (user_id, chat_id, fecha))
            
            cursor.close()
            logger.error(f"Error al verificar si usuario es nuevo: {str(e)}")
            return True  # Asumir que es nuevo en caso de error
        finally:
            if cursor:
                cursor.close()