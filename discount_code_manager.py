#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import string
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import mysql.connector
from enum import Enum

logger = logging.getLogger(__name__)

class DiscountType(Enum):
    PERCENTAGE = "percentage"  # Descuento por porcentaje (5%, 10%, etc.)
    FIXED_AMOUNT = "fixed"     # Descuento fijo (5€, 10€, etc.)
    FREE_SHIPPING = "shipping" # Envío gratuito
    BUY_ONE_GET_ONE = "bogo"   # Compra uno, lleva otro gratis

class DiscountCodeManager:
    """Sistema automático de generación y gestión de códigos de descuento"""
    
    def __init__(self, database):
        self.db = database
        self.setup_discount_tables()
        
    def setup_discount_tables(self):
        """Crea las tablas necesarias para el sistema de códigos de descuento"""
        try:
            cursor = self.db.get_connection().cursor()
            
            # Tabla principal de códigos de descuento
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discount_codes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(20) UNIQUE NOT NULL,
                    discount_type ENUM('percentage', 'fixed', 'shipping', 'bogo') NOT NULL,
                    discount_value DECIMAL(10,2) NOT NULL,
                    min_purchase_amount DECIMAL(10,2) DEFAULT 0,
                    max_uses INT DEFAULT 1,
                    current_uses INT DEFAULT 0,
                    user_id BIGINT,
                    created_for_level INT DEFAULT NULL,
                    expires_at DATETIME,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    description TEXT,
                    INDEX idx_code (code),
                    INDEX idx_user_id (user_id),
                    INDEX idx_expires_at (expires_at),
                    INDEX idx_active (is_active)
                )
            """)
            
            # Tabla de uso de códigos (historial)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discount_code_usage (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    discount_code_id INT,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255),
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    purchase_amount DECIMAL(10,2),
                    discount_applied DECIMAL(10,2),
                    chat_id BIGINT,
                    FOREIGN KEY (discount_code_id) REFERENCES discount_codes(id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_used_at (used_at)
                )
            """)
            
            self.db.get_connection().commit()
            logger.info("Tablas de códigos de descuento configuradas correctamente")
            
        except Exception as e:
            logger.error(f"Error al configurar tablas de códigos de descuento: {str(e)}")
            self.db.get_connection().rollback()
        finally:
            if cursor:
                cursor.close()
    
    def generate_unique_code(self, prefix: str = "", length: int = 8) -> str:
        """Genera un código único que no existe en la base de datos"""
        max_attempts = 50
        attempt = 0
        
        while attempt < max_attempts:
            # Generar código base
            if prefix:
                code_suffix = ''.join(random.choices(
                    string.ascii_uppercase + string.digits, 
                    k=length - len(prefix)
                ))
                code = f"{prefix}{code_suffix}"
            else:
                code = ''.join(random.choices(
                    string.ascii_uppercase + string.digits, 
                    k=length
                ))
            
            # Verificar si el código ya existe
            if not self._code_exists(code):
                return code
                
            attempt += 1
        
        # Si no se pudo generar un código único, agregar timestamp
        timestamp = str(int(datetime.now().timestamp()))[-4:]
        return f"{prefix}{timestamp}"
    
    def _code_exists(self, code: str) -> bool:
        """Verifica si un código ya existe en la base de datos"""
        try:
            cursor = self.db.get_connection().cursor()
            cursor.execute("SELECT 1 FROM discount_codes WHERE code = %s", (code,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error al verificar existencia de código: {str(e)}")
            return True  # En caso de error, asumir que existe para evitar duplicados
        finally:
            if cursor:
                cursor.close()
    
    def create_level_reward_code(self, user_id: int, level: int, username: str = None) -> Optional[str]:
        """Crea un código de descuento específico para recompensa de nivel"""
        try:
            # Determinar tipo y valor del descuento según el nivel
            if level == 10:
                discount_type = DiscountType.PERCENTAGE
                discount_value = 5.0
                description = "Descuento 5% por alcanzar nivel 10"
                prefix = "LVL10"
            elif level == 25:
                discount_type = DiscountType.PERCENTAGE
                discount_value = 10.0
                description = "Descuento 10% por alcanzar nivel 25"
                prefix = "LVL25"
            elif level == 50:
                discount_type = DiscountType.PERCENTAGE
                discount_value = 15.0
                description = "Descuento 15% por alcanzar nivel 50"
                prefix = "LVL50"
            elif level == 75:
                discount_type = DiscountType.FIXED_AMOUNT
                discount_value = 50.0
                description = "50€ de descuento por alcanzar nivel 75"
                prefix = "LVL75"
            elif level == 100:
                discount_type = DiscountType.FIXED_AMOUNT
                discount_value = 100.0
                description = "100€ de descuento por alcanzar nivel 100"
                prefix = "LVL100"
            else:
                return None  # No hay códigos para este nivel
            
            # Generar código único
            code = self.generate_unique_code(prefix=prefix, length=12)
            
            # Calcular fecha de expiración (6 meses para recompensas de nivel)
            expires_at = datetime.now() + timedelta(days=180)
            
            # Insertar en la base de datos
            cursor = self.db.get_connection().cursor()
            cursor.execute("""
                INSERT INTO discount_codes 
                (code, discount_type, discount_value, user_id, created_for_level, 
                 expires_at, description, max_uses)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                code, 
                discount_type.value, 
                discount_value, 
                user_id, 
                level, 
                expires_at, 
                description,
                1  # Uso único para recompensas de nivel
            ))
            
            self.db.get_connection().commit()
            
            logger.info(f"Código de descuento creado: {code} para usuario {user_id} nivel {level}")
            return code
            
        except Exception as e:
            logger.error(f"Error al crear código de recompensa de nivel: {str(e)}")
            self.db.get_connection().rollback()
            return None
        finally:
            if cursor:
                cursor.close()
    
    def create_promotional_code(self, 
                              discount_type: DiscountType,
                              discount_value: float,
                              max_uses: int = 100,
                              expires_days: int = 30,
                              min_purchase: float = 0,
                              description: str = "",
                              prefix: str = "PROMO") -> Optional[str]:
        """Crea un código promocional general"""
        try:
            code = self.generate_unique_code(prefix=prefix, length=10)
            expires_at = datetime.now() + timedelta(days=expires_days)
            
            cursor = self.db.get_connection().cursor()
            cursor.execute("""
                INSERT INTO discount_codes 
                (code, discount_type, discount_value, max_uses, expires_at, 
                 min_purchase_amount, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                code, 
                discount_type.value, 
                discount_value, 
                max_uses, 
                expires_at, 
                min_purchase, 
                description or f"Código promocional {discount_value}{'%' if discount_type == DiscountType.PERCENTAGE else '€'}"
            ))
            
            self.db.get_connection().commit()
            
            logger.info(f"Código promocional creado: {code}")
            return code
            
        except Exception as e:
            logger.error(f"Error al crear código promocional: {str(e)}")
            self.db.get_connection().rollback()
            return None
        finally:
            if cursor:
                cursor.close()
    
    def validate_code(self, code: str, user_id: int = None, purchase_amount: float = 0) -> Dict:
        """Valida un código de descuento y retorna información sobre su validez"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            # Obtener información del código
            cursor.execute("""
                SELECT * FROM discount_codes 
                WHERE code = %s AND is_active = TRUE
            """, (code,))
            
            discount_code = cursor.fetchone()
            
            if not discount_code:
                return {
                    "valid": False,
                    "error": "Código no encontrado o inactivo",
                    "error_type": "NOT_FOUND"
                }
            
            # Verificar expiración
            if discount_code['expires_at'] < datetime.now():
                return {
                    "valid": False,
                    "error": "Código expirado",
                    "error_type": "EXPIRED",
                    "expired_at": discount_code['expires_at']
                }
            
            # Verificar usos máximos
            if discount_code['current_uses'] >= discount_code['max_uses']:
                return {
                    "valid": False,
                    "error": "Código agotado (máximo de usos alcanzado)",
                    "error_type": "MAX_USES_REACHED"
                }
            
            # Verificar monto mínimo de compra
            if purchase_amount < discount_code['min_purchase_amount']:
                return {
                    "valid": False,
                    "error": f"Compra mínima requerida: {discount_code['min_purchase_amount']}€",
                    "error_type": "MIN_PURCHASE_NOT_MET",
                    "min_purchase": discount_code['min_purchase_amount']
                }
            
            # Verificar si el código es específico para un usuario
            if discount_code['user_id'] and discount_code['user_id'] != user_id:
                return {
                    "valid": False,
                    "error": "Este código es específico para otro usuario",
                    "error_type": "WRONG_USER"
                }
            
            # Verificar si el usuario ya usó este código (para códigos de un solo uso)
            if discount_code['max_uses'] == 1 and user_id:
                cursor.execute("""
                    SELECT 1 FROM discount_code_usage 
                    WHERE discount_code_id = %s AND user_id = %s
                """, (discount_code['id'], user_id))
                
                if cursor.fetchone():
                    return {
                        "valid": False,
                        "error": "Ya has usado este código anteriormente",
                        "error_type": "ALREADY_USED"
                    }
            
            # Calcular descuento
            discount_amount = self._calculate_discount(discount_code, purchase_amount)
            
            return {
                "valid": True,
                "code_info": discount_code,
                "discount_amount": discount_amount,
                "final_amount": max(0, purchase_amount - discount_amount)
            }
            
        except Exception as e:
            logger.error(f"Error al validar código: {str(e)}")
            return {
                "valid": False,
                "error": "Error interno del sistema",
                "error_type": "SYSTEM_ERROR"
            }
        finally:
            if cursor:
                cursor.close()
    
    def _calculate_discount(self, discount_code: Dict, purchase_amount: float) -> float:
        """Calcula el monto del descuento basado en el tipo de código"""
        if discount_code['discount_type'] == DiscountType.PERCENTAGE.value:
            return min(purchase_amount * (discount_code['discount_value'] / 100), purchase_amount)
        elif discount_code['discount_type'] == DiscountType.FIXED_AMOUNT.value:
            return min(discount_code['discount_value'], purchase_amount)
        elif discount_code['discount_type'] == DiscountType.FREE_SHIPPING.value:
            # Asumir costo de envío estándar de 5€
            return min(5.0, purchase_amount)
        else:  # BOGO u otros tipos especiales
            return 0  # Necesitaría lógica específica del negocio
    
    def use_code(self, code: str, user_id: int, username: str, purchase_amount: float, chat_id: int = None) -> Dict:
        """Marca un código como usado y registra el uso"""
        try:
            # Primero validar el código
            validation = self.validate_code(code, user_id, purchase_amount)
            
            if not validation["valid"]:
                return validation
            
            discount_code = validation["code_info"]
            discount_amount = validation["discount_amount"]
            
            cursor = self.db.get_connection().cursor()
            
            # Incrementar contador de usos
            cursor.execute("""
                UPDATE discount_codes 
                SET current_uses = current_uses + 1 
                WHERE id = %s
            """, (discount_code['id'],))
            
            # Registrar el uso
            cursor.execute("""
                INSERT INTO discount_code_usage 
                (discount_code_id, user_id, username, purchase_amount, discount_applied, chat_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                discount_code['id'], 
                user_id, 
                username, 
                purchase_amount, 
                discount_amount, 
                chat_id
            ))
            
            self.db.get_connection().commit()
            
            logger.info(f"Código {code} usado por usuario {user_id} con descuento de {discount_amount}€")
            
            return {
                "success": True,
                "discount_amount": discount_amount,
                "final_amount": purchase_amount - discount_amount,
                "message": f"Código aplicado correctamente. Descuento: {discount_amount}€"
            }
            
        except Exception as e:
            logger.error(f"Error al usar código: {str(e)}")
            self.db.get_connection().rollback()
            return {
                "success": False,
                "error": "Error interno al procesar el código",
                "error_type": "SYSTEM_ERROR"
            }
        finally:
            if cursor:
                cursor.close()
    
    def get_user_codes(self, user_id: int) -> List[Dict]:
        """Obtiene todos los códigos disponibles para un usuario específico"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            cursor.execute("""
                SELECT code, discount_type, discount_value, expires_at, description, 
                       current_uses, max_uses, min_purchase_amount
                FROM discount_codes 
                WHERE user_id = %s AND is_active = TRUE AND expires_at > NOW()
                ORDER BY created_at DESC
            """, (user_id,))
            
            codes = cursor.fetchall()
            
            # Formatear información para mostrar
            for code in codes:
                if code['discount_type'] == DiscountType.PERCENTAGE.value:
                    code['discount_text'] = f"{code['discount_value']}% de descuento"
                elif code['discount_type'] == DiscountType.FIXED_AMOUNT.value:
                    code['discount_text'] = f"{code['discount_value']}€ de descuento"
                elif code['discount_type'] == DiscountType.FREE_SHIPPING.value:
                    code['discount_text'] = "Envío gratuito"
                else:
                    code['discount_text'] = code['description']
                
                code['uses_remaining'] = code['max_uses'] - code['current_uses']
                code['is_expired'] = code['expires_at'] < datetime.now()
            
            return codes
            
        except Exception as e:
            logger.error(f"Error al obtener códigos de usuario: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def cleanup_expired_codes(self):
        """Limpia códigos expirados y marca como inactivos"""
        try:
            cursor = self.db.get_connection().cursor()
            
            cursor.execute("""
                UPDATE discount_codes 
                SET is_active = FALSE 
                WHERE expires_at < NOW() AND is_active = TRUE
            """)
            
            affected_rows = cursor.rowcount
            self.db.get_connection().commit()
            
            if affected_rows > 0:
                logger.info(f"Se desactivaron {affected_rows} códigos expirados")
            
            return affected_rows
            
        except Exception as e:
            logger.error(f"Error al limpiar códigos expirados: {str(e)}")
            self.db.get_connection().rollback()
            return 0
        finally:
            if cursor:
                cursor.close()
    
    def get_usage_stats(self, days: int = 30) -> Dict:
        """Obtiene estadísticas de uso de códigos"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            # Estadísticas generales
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_codes_used,
                    SUM(discount_applied) as total_discount_given,
                    AVG(discount_applied) as average_discount,
                    COUNT(DISTINCT user_id) as unique_users
                FROM discount_code_usage 
                WHERE used_at > DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            
            stats = cursor.fetchone() or {}
            
            # Códigos más populares
            cursor.execute("""
                SELECT dc.code, dc.description, COUNT(*) as usage_count,
                       SUM(dcu.discount_applied) as total_discount
                FROM discount_code_usage dcu
                JOIN discount_codes dc ON dcu.discount_code_id = dc.id
                WHERE dcu.used_at > DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY dc.id
                ORDER BY usage_count DESC
                LIMIT 10
            """, (days,))
            
            stats['popular_codes'] = cursor.fetchall()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de uso: {str(e)}")
            return {}
        finally:
            if cursor:
                cursor.close() 