#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de instalación del sistema de códigos de descuento
Configura las tablas necesarias y migra datos existentes si es necesario
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import AntDatabase
from discount_code_manager import DiscountCodeManager, DiscountType

def install_discount_system():
    """Instala el sistema de códigos de descuento"""
    try:
        logger.info("🚀 Iniciando instalación del sistema de códigos de descuento...")
        
        # Conectar a la base de datos
        db = AntDatabase(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        # Verificar conexión - el método connect() ya configura la base de datos
        db.connect()
        logger.info("✅ Conexión a la base de datos establecida")
        
        # Crear el manager de códigos de descuento (esto crea las tablas automáticamente)
        discount_manager = DiscountCodeManager(db)
        
        logger.info("✅ Tablas de códigos de descuento creadas/verificadas")
        
        # Verificar si hay usuarios con niveles altos que deberían tener códigos
        cursor = db.get_connection().cursor(dictionary=True)
        
        cursor.execute("""
            SELECT user_id, username, current_level, total_xp, chat_id
            FROM user_experience 
            WHERE current_level >= 10
            ORDER BY current_level DESC, total_xp DESC
        """)
        
        usuarios_alto_nivel = cursor.fetchall()
        
        if usuarios_alto_nivel:
            logger.info(f"📊 Encontrados {len(usuarios_alto_nivel)} usuarios con nivel 10+")
            
            # Generar códigos retroactivos para usuarios que ya alcanzaron niveles con recompensas
            codigos_generados = 0
            
            for usuario in usuarios_alto_nivel:
                user_id = usuario['user_id']
                username = usuario['username']
                nivel = usuario['current_level']
                
                # Niveles que otorgan códigos de descuento
                niveles_con_codigos = [10, 25, 50, 75, 100]
                
                for nivel_codigo in niveles_con_codigos:
                    if nivel >= nivel_codigo:
                        # Verificar si ya tiene un código para este nivel
                        cursor.execute("""
                            SELECT COUNT(*) as count FROM discount_codes
                            WHERE user_id = %s AND created_for_level = %s
                        """, (user_id, nivel_codigo))
                        
                        resultado = cursor.fetchone()
                        
                        if resultado['count'] == 0:
                            # Generar código retroactivo
                            codigo = discount_manager.create_level_reward_code(
                                user_id=user_id,
                                level=nivel_codigo,
                                username=username
                            )
                            
                            if codigo:
                                codigos_generados += 1
                                logger.info(f"💳 Código retroactivo generado: {codigo} para {username} (nivel {nivel_codigo})")
            
            if codigos_generados > 0:
                logger.info(f"✅ Se generaron {codigos_generados} códigos retroactivos")
            else:
                logger.info("ℹ️ No se necesitaron códigos retroactivos")
        
        # Crear algunos códigos promocionales de ejemplo
        logger.info("🎁 Creando códigos promocionales de ejemplo...")
        
        ejemplos_creados = 0
        
        # Código de bienvenida
        codigo_bienvenida = discount_manager.create_promotional_code(
            discount_type=DiscountType.PERCENTAGE,
            discount_value=10.0,
            max_uses=50,
            expires_days=90,
            min_purchase=30.0,
            description="Código de bienvenida para nuevos usuarios",
            prefix="WELCOME"
        )
        
        if codigo_bienvenida:
            ejemplos_creados += 1
            logger.info(f"💳 Código de bienvenida creado: {codigo_bienvenida}")
        
        # Código de envío gratis
        codigo_envio = discount_manager.create_promotional_code(
            discount_type=DiscountType.FREE_SHIPPING,
            discount_value=0,
            max_uses=100,
            expires_days=60,
            min_purchase=25.0,
            description="Envío gratuito para pedidos superiores a 25€",
            prefix="SHIP"
        )
        
        if codigo_envio:
            ejemplos_creados += 1
            logger.info(f"📦 Código de envío gratis creado: {codigo_envio}")
        
        # Limpiar códigos expirados
        codigos_limpiados = discount_manager.cleanup_expired_codes()
        if codigos_limpiados > 0:
            logger.info(f"🧹 Se limpiaron {codigos_limpiados} códigos expirados")
        
        # Mostrar estadísticas finales
        cursor.execute("SELECT COUNT(*) as total FROM discount_codes WHERE is_active = TRUE")
        total_codigos = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as total FROM discount_code_usage")
        total_usos = cursor.fetchone()['total']
        
        logger.info("📊 Estadísticas del sistema:")
        logger.info(f"   • Códigos activos: {total_codigos}")
        logger.info(f"   • Usos registrados: {total_usos}")
        logger.info(f"   • Ejemplos creados: {ejemplos_creados}")
        
        cursor.close()
        
        logger.info("🎉 ¡Sistema de códigos de descuento instalado correctamente!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante la instalación: {str(e)}")
        return False

def test_discount_system():
    """Prueba básica del sistema de códigos de descuento"""
    try:
        logger.info("🧪 Ejecutando pruebas del sistema...")
        
        # Conectar a la base de datos
        db = AntDatabase(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        
        db.connect()
        discount_manager = DiscountCodeManager(db)
        
        # Test 1: Crear código de prueba
        logger.info("Test 1: Creando código de prueba...")
        test_code = discount_manager.create_promotional_code(
            discount_type=DiscountType.PERCENTAGE,
            discount_value=5.0,
            max_uses=1,
            expires_days=1,
            min_purchase=0,
            description="Código de prueba del sistema",
            prefix="TEST"
        )
        
        if test_code:
            logger.info(f"✅ Código de prueba creado: {test_code}")
            
            # Test 2: Validar código
            logger.info("Test 2: Validando código...")
            validation = discount_manager.validate_code(test_code, user_id=999999, purchase_amount=10.0)
            
            if validation["valid"]:
                logger.info(f"✅ Código válido. Descuento: {validation['discount_amount']}€")
                
                # Test 3: Usar código
                logger.info("Test 3: Usando código...")
                usage = discount_manager.use_code(test_code, 999999, "test_user", 10.0, chat_id=-999999)
                
                if usage.get("success"):
                    logger.info(f"✅ Código usado correctamente. Precio final: {usage['final_amount']}€")
                    
                    # Test 4: Intentar usar código de nuevo (debería fallar)
                    logger.info("Test 4: Intentando usar código usado...")
                    usage2 = discount_manager.use_code(test_code, 999999, "test_user", 10.0, chat_id=-999999)
                    
                    if not usage2.get("success"):
                        logger.info("✅ Código usado rechazado correctamente")
                        
                        # Limpiar código de prueba
                        cursor = db.get_connection().cursor()
                        cursor.execute("DELETE FROM discount_codes WHERE code = %s", (test_code,))
                        cursor.execute("DELETE FROM discount_code_usage WHERE user_id = 999999")
                        db.get_connection().commit()
                        cursor.close()
                        
                        logger.info("🧹 Datos de prueba limpiados")
                        logger.info("🎉 ¡Todas las pruebas pasaron correctamente!")
                        return True
        
        logger.error("❌ Alguna prueba falló")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error durante las pruebas: {str(e)}")
        return False

def main():
    """Función principal"""
    print("🤖 AntmasterBot - Instalador del Sistema de Códigos de Descuento")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("🧪 Modo de prueba activado")
        success = test_discount_system()
    else:
        print("🚀 Instalando sistema de códigos de descuento...")
        success = install_discount_system()
    
    if success:
        print("\n✅ ¡Operación completada exitosamente!")
        print("\n📋 Próximos pasos:")
        print("1. Reinicia el bot para cargar el nuevo sistema")
        print("2. Los usuarios comenzarán a recibir códigos al subir de nivel")
        print("3. Usa /crear_codigo_promo para crear códigos promocionales")
        print("4. Los usuarios pueden usar /mis_codigos para ver sus códigos")
        sys.exit(0)
    else:
        print("\n❌ La operación falló. Revisa los logs para más detalles.")
        sys.exit(1)

if __name__ == "__main__":
    main() 