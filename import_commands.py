#!/usr/bin/env python3
"""
Módulo para importar comandos adicionales al bot principal AntmasterBot
"""

import logging
import os
import sys
from typing import Any, Callable, Dict, List

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logger = logging.getLogger(__name__)

def register_adivina_commands(dp: Dispatcher, bot: Bot, db: Any):
    """
    Registra los comandos para el juego de adivinar especies.
    """
    try:
        # Registrar el comando principal de adivinar_especie ya está en AntmasterBot.py
        
        # Crear las tablas necesarias en la base de datos si no existen
        cursor = db.get_connection().cursor()
        
        # Asegurarse de que existe la tabla species_guessing_game
        cursor.execute("""
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
        """)
        
        # Asegurarse de que exista la tabla temp_data para almacenar estados temporales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS temp_data (
                id VARCHAR(255) PRIMARY KEY,
                value TEXT,
                expires_at TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Verificar si ya hay el tipo game_guess en la tabla user_interactions
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'user_interactions' 
            AND column_name = 'interaction_type' 
            AND LOCATE('game_guess', COLUMN_TYPE) > 0
        """)
        
        if cursor.fetchone()[0] == 0:
            # Modificar la tabla user_interactions para incluir el tipo game_guess
            cursor.execute("""
                ALTER TABLE user_interactions 
                MODIFY COLUMN interaction_type 
                ENUM('command', 'message', 'photo', 'video', 'document', 'join', 'reaction', 'spam_notification', 'game_guess') 
                NOT NULL
            """)
        
        db.get_connection().commit()
        logger.info("Juego de adivinar especies registrado correctamente")
        return True
        
    except Exception as e:
        logger.error(f"Error al registrar juego de adivinar especies: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False 