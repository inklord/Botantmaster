#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import os
import sys
from database import AntDatabase
from dotenv import load_dotenv
from aiogram import Bot
# Removed aiogram.client import for aiogram 2.x compatibility
import aiohttp
from discount_code_manager import DiscountCodeManager, DiscountType

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rewards_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Configuración de puntos por actividad
XP_POR_MENSAJE = 1
XP_POR_FOTO = 5
XP_POR_REACCION = 1
XP_POR_COMANDO = 0
XP_POR_COMANDO_INFO = 2
XP_POR_GAME_WIN = 10
XP_FOTO_APROBADA = 25

class RewardsManager:
    def __init__(self, db):
        self.db = db
        self.sistema_activo = True
        self.logger = logging.getLogger('rewards_manager')
        
        # Configurar logging
        if not self.logger.handlers:
            handler = logging.FileHandler('rewards_manager.log', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Configurar límites de experiencia
        self.LIMITE_DIARIO_XP = 100
        self.LIMITE_XP_BURST = 5
        self.XP_POR_MENSAJE = XP_POR_MENSAJE
        self.XP_POR_FOTO = XP_POR_FOTO
        self.XP_POR_REACCION = XP_POR_REACCION
        self.XP_POR_COMANDO = XP_POR_COMANDO
        self.XP_POR_COMANDO_INFO = XP_POR_COMANDO_INFO
        self.XP_POR_GAME_WIN = XP_POR_GAME_WIN
        self.XP_FOTO_APROBADA = XP_FOTO_APROBADA
        
        # Inicializar sistema de códigos de descuento
        self.discount_manager = DiscountCodeManager(db)
        
        logger.info("Sistema de recompensas inicializado con gestión de códigos de descuento")
        
        # Bot se configurará después con set_bot()
        self.bot = None
    
    def set_bot(self, bot):
        """Establece la referencia al bot para enviar mensajes"""
        self.bot = bot
    
    def detener_sistema(self):
        """Detiene el sistema de recompensas"""
        self.sistema_activo = False
        logger.info("Sistema de recompensas detenido")
    
    async def actualizar_experiencia(self, user_id, username, chat_id, interaction_type, command_name=None):
        """Actualiza la experiencia de un usuario basado en su interacción"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            # Determinar XP a otorgar
            xp_ganado = 0
            if interaction_type == 'message':
                xp_ganado = self.XP_POR_MENSAJE
            elif interaction_type == 'photo' or interaction_type == 'video':
                xp_ganado = self.XP_POR_FOTO
            elif interaction_type == 'reaction':
                xp_ganado = self.XP_POR_REACCION
            elif interaction_type == 'command':
                if command_name in ['ayuda', 'hormidato', 'especie', 'normas']:
                    xp_ganado = self.XP_POR_COMANDO_INFO
                else:
                    xp_ganado = self.XP_POR_COMANDO
                
            if xp_ganado == 0:
                return
                
            # Verificar si el usuario existe
            cursor.execute("""
                SELECT * FROM user_experience 
                WHERE user_id = %s AND chat_id = %s
            """, (user_id, chat_id))
            user = cursor.fetchone()
            
            if user:
                # Actualizar experiencia existente
                nuevo_xp = user['total_xp'] + xp_ganado
                nuevo_nivel = self.calcular_nivel(nuevo_xp)
                nivel_anterior = user['current_level']
                
                # Verificar si subió de nivel
                if nuevo_nivel > nivel_anterior:
                    await self.notificar_subida_nivel(user_id, chat_id, nuevo_nivel)
                    await self.verificar_recompensas(user_id, chat_id, nuevo_nivel)
                    
                    # Otorgar badge automático si corresponde
                    badge_otorgado = await self.otorgar_badge_automatico(user_id, chat_id, nuevo_nivel, username)
                    if badge_otorgado:
                        logger.info(f"Badge automático otorgado al usuario {user_id} para nivel {nuevo_nivel}")
                    else:
                        logger.info(f"No se otorgó badge automático para nivel {nuevo_nivel} al usuario {user_id}")
                
                cursor.execute("""
                    UPDATE user_experience 
                    SET total_xp = %s,
                        current_level = %s,
                        last_message_time = NOW(),
                        updated_at = NOW()
                    WHERE user_id = %s AND chat_id = %s
                """, (nuevo_xp, nuevo_nivel, user_id, chat_id))
                
            else:
                # Crear nuevo registro de experiencia
                nivel_inicial = self.calcular_nivel(xp_ganado)
                cursor.execute("""
                    INSERT INTO user_experience 
                    (user_id, username, total_xp, current_level, chat_id, last_message_time)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (user_id, username, xp_ganado, nivel_inicial, chat_id))
            
            self.db.get_connection().commit()
            
        except Exception as e:
            logger.error(f"Error al actualizar experiencia: {str(e)}")
            self.db.get_connection().rollback()
        finally:
            if cursor:
                cursor.close()
    
    def calcular_nivel(self, xp):
        """
        Calcula el nivel basado en XP con un sistema equilibrado y sostenible
        Debe ser idéntico a la función en database.py para consistencia
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
    
    async def notificar_subida_nivel(self, user_id, chat_id, nuevo_nivel):
        """Notifica al usuario cuando sube de nivel con información detallada"""
        try:
            # Obtener información del usuario
            cursor = self.db.get_connection().cursor(dictionary=True)
            cursor.execute("""
                SELECT username, total_xp FROM user_experience 
                WHERE user_id = %s AND chat_id = %s
            """, (user_id, chat_id))
            user_data = cursor.fetchone()
            
            if not user_data:
                return
                
            username = user_data['username'] or f"Usuario {user_id}"
            xp_total = user_data['total_xp']
            
            # Determinar badge y emoji según nivel
            if nuevo_nivel < 5:
                emoji = "🌱"
                badge = "Nurse"
            elif nuevo_nivel < 10:
                emoji = "🌿"
                badge = "Explorador Mirmecólogo"
            elif nuevo_nivel < 25:
                emoji = "🌳"
                badge = "Guardián de la Reina"
            elif nuevo_nivel < 50:
                emoji = "⭐"
                badge = "Comandante Imperial"
            elif nuevo_nivel < 75:
                emoji = "🔥"
                badge = "Señor de las Castas"
            elif nuevo_nivel < 100:
                emoji = "👑"
                badge = "Emperador Entomólogo"
            else:
                emoji = "🏆"
                badge = "Ser supremo"
            
            # Recompensas especiales por nivel con código automático
            recompensas_especiales = {
                5: {
                    "titulo": "🌱 Badge 'nurse'",
                    "descripcion": "Ahora eres una pequeña hormiga",
                    "tipo": "acceso"
                },
                10: {
                    "titulo": "🌿 Descuento 5% + Badge 'Explorador Mirmecólogo'",
                    "descripcion": "Descuento del 5% en la tienda y badge especial de administrador",
                    "tipo": "descuento"
                },
                15: {
                    "titulo": "🌳 Kit de inicio Terra",
                    "descripcion": "Kit de iniciación Terra para cuidado de hormigas",
                    "tipo": "kit"
                },
                25: {
                    "titulo": "⭐ Descuento 10% + Badge 'Guardián de la Reina'",
                    "descripcion": "Descuento del 10% en la tienda y badge avanzado de administrador",
                    "tipo": "descuento"
                },
                35: {
                    "titulo": "🔥 Kit M Terra",
                    "descripcion": "Kit M Terra con herramientas avanzadas",
                    "tipo": "kit"
                },
                50: {
                    "titulo": "💎 Badge 'Comandante Imperial' + Kit L Terra",
                    "descripcion": "Badge de élite de administrador y kit L Terra avanzado",
                    "tipo": "kit_premium"
                },
                75: {
                    "titulo": "👑 Badge 'Señor de las Castas' + Tarjeta Regalo 50€",
                    "descripcion": "Badge supremo de administrador y tarjeta regalo de 50€",
                    "tipo": "premio_grande"
                },
                100: {
                    "titulo": "🏆 Badge 'Emperador Entomólogo' + Tarjeta Regalo 100€",
                    "descripcion": "Badge máximo de administrador y tarjeta regalo de 100€",
                    "tipo": "premio_maximo"
                }
            }
            
            # Generar código de descuento automáticamente si corresponde
            codigo_descuento = None
            if nuevo_nivel in [10, 25, 50, 75, 100]:
                codigo_descuento = self.discount_manager.create_level_reward_code(
                    user_id=user_id, 
                    level=nuevo_nivel, 
                    username=username
                )
                if codigo_descuento:
                    logger.info(f"Código de descuento generado automáticamente: {codigo_descuento} para nivel {nuevo_nivel}")
            
            # Calcular XP para próximo nivel
            xp_proximo_nivel = self.db.calcular_xp_total_para_nivel(nuevo_nivel + 1)
            xp_faltante = xp_proximo_nivel - xp_total if nuevo_nivel < 100 else 0
            
            # Mensaje base de felicitación
            mensaje = (
                f"🎉 ¡LEVEL UP! 🎉\n\n"
                f"{emoji} **@{username}** ha alcanzado el **NIVEL {nuevo_nivel}**! {emoji}\n"
                f"🏅 Badge: **{badge}**\n"
                f"⚡ XP Total: **{xp_total:,}**\n"
            )
            
            # Verificar si este nivel otorga badge automático 
            badges_automaticos = {10: "🌿 Explorador Mirmecólogo", 25: "⭐ Guardián de la Reina", 50: "💎 Comandante Imperial", 75: "👑 Señor de las Castas", 100: "🏆 Emperador Entomólogo"}
            if nuevo_nivel in badges_automaticos:
                mensaje += f"👑 **¡BADGE AUTOMÁTICO OTORGADO!** 👑\n"
                mensaje += f"🎖️ Título: **{badges_automaticos[nuevo_nivel]}**\n"
                mensaje += f"✨ Ahora eres administrador con permisos especiales\n"
            
            # Añadir información del próximo nivel si no es nivel máximo
            if nuevo_nivel < 100:
                mensaje += f"🎯 Para Nivel {nuevo_nivel + 1}: **{xp_faltante:,} XP restantes**\n"
            else:
                mensaje += "🏆 **¡NIVEL MÁXIMO ALCANZADO!**\n"
            
            # Verificar si hay recompensa especial en este nivel
            if nuevo_nivel in recompensas_especiales:
                recompensa = recompensas_especiales[nuevo_nivel]
                mensaje += (
                    f"\n🎁 **¡RECOMPENSA ESPECIAL DESBLOQUEADA!** 🎁\n"
                    f"📦 {recompensa['titulo']}\n"
                    f"📝 {recompensa['descripcion']}\n"
                )
                
                if codigo_descuento and recompensa['tipo'] in ['descuento', 'premio_grande', 'premio_maximo']:
                    mensaje += f"🔑 Código: **{codigo_descuento}**\n"
                    
                mensaje += "\n💬 Para reclamar tu recompensa, contacta con un administrador."
            
            mensaje += "\n\n🌟 ¡Gracias por tu participación en la comunidad Antmaster! 🌟"
            
            # Enviar mensaje en el grupo
            from aiogram.enums import ParseMode
            await self.bot.send_message(
                chat_id=chat_id,
                text=mensaje,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Enviar mensaje privado detallado si hay recompensa especial
            if nuevo_nivel in recompensas_especiales:
                try:
                    recompensa = recompensas_especiales[nuevo_nivel]
                    mensaje_privado = (
                        f"🎉 ¡Felicitaciones por alcanzar el NIVEL {nuevo_nivel}! 🎉\n\n"
                        f"🎁 **RECOMPENSA ESPECIAL DESBLOQUEADA**\n"
                        f"📦 {recompensa['titulo']}\n"
                        f"📝 {recompensa['descripcion']}\n\n"
                    )
                    
                    # Añadir información del badge automático si corresponde
                    badges_automaticos = {10: "🌿 Explorador Mirmecólogo", 25: "⭐ Guardián de la Reina", 50: "💎 Comandante Imperial", 75: "👑 Señor de las Castas", 100: "🏆 Emperador Entomólogo"}
                    if nuevo_nivel in badges_automaticos:
                        mensaje_privado += (
                            f"👑 **¡BADGE AUTOMÁTICO OTORGADO!** 👑\n"
                            f"🎖️ **Título:** {badges_automaticos[nuevo_nivel]}\n"
                            f"✨ **Privilegios especiales:**\n"
                            f"• Título personalizado visible en el grupo\n"
                            f"• Permisos de administrador básicos\n"
                            f"• Reconocimiento especial de la comunidad\n\n"
                        )
                    
                    if codigo_descuento and recompensa['tipo'] in ['descuento', 'premio_grande', 'premio_maximo']:
                        mensaje_privado += (
                            f"🔑 **Tu código de descuento:** `{codigo_descuento}`\n\n"
                            f"📋 **Instrucciones:**\n"
                            f"1. Copia este código (válido por 6 meses)\n"
                            f"2. Contacta con un administrador en el grupo\n"
                            f"3. Presenta tu código para reclamar la recompensa\n"
                            f"4. Usa /mis_codigos para ver todos tus códigos\n\n"
                        )
                    elif recompensa['tipo'] in ['kit', 'kit_premium']:
                        mensaje_privado += (
                            f"📋 **Para reclamar tu kit:**\n"
                            f"1. Contacta con un administrador en el grupo\n"
                            f"2. Proporciona tu información de envío\n"
                            f"3. El kit será enviado a tu dirección\n\n"
                        )
                    else:  # acceso
                        mensaje_privado += (
                            f"✅ **Tu recompensa se ha activado automáticamente**\n"
                            f"Ya tienes acceso a todas las funciones desbloqueadas.\n\n"
                        )
                    
                    mensaje_privado += (
                        f"🏅 Tu nuevo badge: **{badge}**\n"
                        f"⚡ XP Total: **{xp_total:,}**\n\n"
                        f"🌟 ¡Gracias por ser parte de la comunidad Antmaster! 🌟"
                    )
                    
                    await self.bot.send_message(
                        chat_id=user_id, 
                        text=mensaje_privado,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Registrar la recompensa en la base de datos
                    self.db.add_reward(user_id, recompensa['tipo'], recompensa['descripcion'])
                    
                except Exception as e:
                    logger.error(f"No se pudo enviar mensaje privado al usuario {user_id}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error al notificar subida de nivel: {str(e)}")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
    
    async def verificar_recompensas(self, user_id, chat_id, nivel):
        """Verifica y otorga recompensas por nivel"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            # Obtener nombre de usuario
            cursor.execute("SELECT username FROM user_experience WHERE user_id = %s AND chat_id = %s", (user_id, chat_id))
            user_data = cursor.fetchone()
            
            if not user_data:
                return
                
            # Verificar si la recompensa ya ha sido otorgada
            cursor.execute("""
                SELECT * FROM user_rewards 
                WHERE user_id = %s AND level = %s
            """, (user_id, nivel))
            
            reward = cursor.fetchone()
            
            if not reward:
                # Lista de recompensas por nivel (solo niveles específicos tienen recompensas)
                recompensas = {
                    5: "Acceso a comandos informativos",
                    10: "Descuento 5% en la tienda",
                    15: "Kit básico de hormigas",
                    25: "Descuento 10% en la tienda",
                    35: "Kit intermedio de hormigas",
                    50: "Kit avanzado de hormigas",
                    75: "Tarjeta regalo 50€",
                    100: "Tarjeta regalo 100€"
                }
                
                if nivel in recompensas:
                    descripcion = recompensas[nivel]
                    
                    # Generar código de descuento para niveles con descuentos monetarios usando el nuevo sistema
                    codigo = None
                    if nivel in [10, 25, 50, 75, 100]:
                        codigo = self.discount_manager.create_level_reward_code(user_id, nivel, user_data['username'])
                    
                    # Registrar recompensa en la base de datos
                    cursor.execute("""
                        INSERT INTO user_rewards 
                        (user_id, username, level, reward_name, claimed, chat_id)
                        VALUES (%s, %s, %s, %s, 0, %s)
                    """, (user_id, user_data['username'], nivel, descripcion, chat_id))
                    
                    self.db.get_connection().commit()
                    logger.info(f"Recompensa de nivel {nivel} otorgada al usuario {user_data['username']} (ID: {user_id})")
            
        except Exception as e:
            logger.error(f"Error al verificar recompensas: {str(e)}")
            self.db.get_connection().rollback()
        finally:
            if cursor:
                cursor.close()
    
    async def mostrar_ranking_semanal(self):
        """Muestra el ranking semanal en todos los grupos activos"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            # Obtener lista de grupos activos
            cursor.execute("""
                SELECT DISTINCT chat_id FROM user_experience
                WHERE chat_id < 0  -- Solo grupos, no chats privados
            """)
            
            grupos = cursor.fetchall()
            
            for grupo in grupos:
                chat_id = grupo['chat_id']
                
                # Calcular fecha de hace una semana
                una_semana_atras = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                
                # Obtener el ranking semanal
                cursor.execute("""
                    SELECT ui.user_id, ue.username, COUNT(*) as interacciones, SUM(ui.points) as puntos_semana, ue.current_level
                    FROM user_interactions ui
                    JOIN user_experience ue ON ui.user_id = ue.user_id AND ui.chat_id = ue.chat_id
                    WHERE ui.chat_id = %s AND ui.created_at > %s
                    GROUP BY ui.user_id
                    ORDER BY puntos_semana DESC
                    LIMIT 10
                """, (chat_id, una_semana_atras))
                
                ranking = cursor.fetchall()
                
                if ranking:
                    mensaje = "🏆 RANKING SEMANAL 🏆\n\nLos usuarios más activos de la semana:\n\n"
                    
                    for i, user in enumerate(ranking):
                        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                        mensaje += f"{medal} @{user['username']} - {user['puntos_semana']} XP (Nivel {user['current_level']})\n"
                    
                    mensaje += "\n¡Felicidades a los más activos! Sigue participando para subir en el ranking. 🌟"
                    
                    # Enviar el mensaje al grupo
                    await self.bot.send_message(chat_id=chat_id, text=mensaje)
                    
                    logger.info(f"Ranking semanal enviado al grupo {chat_id}")
                
        except Exception as e:
            logger.error(f"Error al mostrar ranking semanal: {str(e)}")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
    
    async def mostrar_ranking_mensual(self):
        """Muestra el ranking mensual en todos los grupos activos"""
        try:
            cursor = self.db.get_connection().cursor(dictionary=True)
            
            # Obtener lista de grupos activos
            cursor.execute("""
                SELECT DISTINCT chat_id FROM user_experience
                WHERE chat_id < 0  -- Solo grupos, no chats privados
            """)
            
            grupos = cursor.fetchall()
            
            for grupo in grupos:
                chat_id = grupo['chat_id']
                
                # Calcular fecha de hace un mes
                un_mes_atras = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
                
                # Obtener el ranking mensual
                cursor.execute("""
                    SELECT ui.user_id, ue.username, COUNT(*) as interacciones, SUM(ui.points) as puntos_mes, ue.current_level
                    FROM user_interactions ui
                    JOIN user_experience ue ON ui.user_id = ue.user_id AND ui.chat_id = ue.chat_id
                    WHERE ui.chat_id = %s AND ui.created_at > %s
                    GROUP BY ui.user_id
                    ORDER BY puntos_mes DESC
                    LIMIT 10
                """, (chat_id, un_mes_atras))
                
                ranking = cursor.fetchall()
                
                if ranking:
                    mensaje = "🏆 RANKING MENSUAL 🏆\n\nLos usuarios más activos del mes:\n\n"
                    
                    for i, user in enumerate(ranking):
                        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
                        mensaje += f"{medal} @{user['username']} - {user['puntos_mes']} XP (Nivel {user['current_level']})\n"
                    
                    mensaje += "\n¡Felicidades a los más activos del mes! El usuario #1 recibirá una mención especial. 🌟"
                    
                    # Enviar el mensaje al grupo
                    await self.bot.send_message(chat_id=chat_id, text=mensaje)
                    
                    logger.info(f"Ranking mensual enviado al grupo {chat_id}")
                    
                    # Premiar al usuario top 1 del mes
                    if ranking and len(ranking) > 0:
                        top_user = ranking[0]
                        await self.premiar_usuario_top(top_user['user_id'], top_user['username'], chat_id)
                
        except Exception as e:
            logger.error(f"Error al mostrar ranking mensual: {str(e)}")
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
    
    async def premiar_usuario_top(self, user_id, username, chat_id):
        """Premia al usuario top del mes"""
        try:
            # Enviar mensaje especial en el grupo
            mensaje = (
                f"🌟 ¡FELICIDADES AL TOP 1 DEL MES! 🌟\n\n"
                f"@{username} ha sido el usuario más activo este mes.\n"
                f"Como reconocimiento, recibirá un premio especial. ¡Gracias por tu contribución a la comunidad!"
            )
            
            await self.bot.send_message(chat_id=chat_id, text=mensaje)
            
            # Intentar enviar mensaje privado
            try:
                mensaje_privado = (
                    f"🎉 ¡Felicidades! Has sido el usuario más activo del mes en el grupo.\n\n"
                    f"Como reconocimiento, has ganado un premio especial.\n"
                    f"Un administrador se pondrá en contacto contigo para entregarte tu recompensa.\n\n"
                    f"¡Gracias por tu valiosa participación en la comunidad Antmaster!"
                )
                await self.bot.send_message(chat_id=user_id, text=mensaje_privado)
            except Exception as e:
                logger.error(f"No se pudo enviar mensaje privado al usuario top {user_id}: {str(e)}")
                
            # Registrar el premio en la base de datos
            cursor = self.db.get_connection().cursor()
            cursor.execute("""
                INSERT INTO user_rewards 
                (user_id, username, level, reward_name, claimed, chat_id)
                VALUES (%s, %s, 0, 'Premio Top 1 mensual', 0, %s)
            """, (user_id, username, chat_id))
            
            self.db.get_connection().commit()
            logger.info(f"Premio Top 1 mensual registrado para el usuario {username} (ID: {user_id})")
            
        except Exception as e:
            logger.error(f"Error al premiar usuario top: {str(e)}")
            if 'cursor' in locals() and cursor:
                self.db.get_connection().rollback()
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
    
    async def check_and_show_rankings(self):
        """Verifica si es momento de mostrar los rankings semanales y mensuales"""
        try:
            now = datetime.now()
            
            # Ranking semanal cada domingo a las 20:00
            if now.weekday() == 6 and now.hour == 20 and now.minute < 10:  # Domingo, entre 20:00 y 20:09
                await self.mostrar_ranking_semanal()
                logger.info("Ranking semanal generado y mostrado")
            
            # Ranking mensual el primer día del mes a las 12:00
            if now.day == 1 and now.hour == 12 and now.minute < 10:  # Día 1, entre 12:00 y 12:09
                await self.mostrar_ranking_mensual()
                logger.info("Ranking mensual generado y mostrado")
            
        except Exception as e:
            logger.error(f"Error al verificar y mostrar rankings: {str(e)}")
    
    async def main(self):
        """Función principal que se ejecuta continuamente para verificar rankings"""
        logger.info("Sistema de recompensas iniciado")
        
        while self.sistema_activo:
            try:
                # Verificar rankings
                await self.check_and_show_rankings()
                
                # Esperar 5 minutos antes de volver a verificar
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error en el bucle principal del sistema de recompensas: {str(e)}")
                await asyncio.sleep(60)  # Esperar un minuto en caso de error
                
        logger.info("Sistema de recompensas detenido")

    async def otorgar_badge_automatico(self, user_id, chat_id, nivel, badge_name):
        """Otorga automáticamente un badge promocionando al usuario a administrador con título personalizado"""
        try:
            # Solo otorgar badges en niveles específicos
            badges_niveles = {
                5: "Pequeña Nurse",
                10: "Explorador Mirmecólogo",
                25: "Guardián de la Reina", 
                50: "Comandante Imperial",
                75: "Señor de las Castas",
                100: "Emperador Entomólogo"
            }
            
            if nivel not in badges_niveles:
                return False
                
            badge_titulo = badges_niveles[nivel]
            
            logger.info(f"Intentando otorgar badge '{badge_titulo}' al usuario {user_id} en chat {chat_id}")
            
            # Verificar que el bot tenga permisos para promocionar administradores
            try:
                bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=self.bot.id)
                if not hasattr(bot_member, 'can_promote_members') or not bot_member.can_promote_members:
                    logger.warning(f"El bot no tiene permisos para promocionar miembros en el chat {chat_id}")
                    return False
            except Exception as e:
                logger.error(f"Error verificando permisos del bot: {str(e)}")
                return False
            
            # Verificar el estado actual del usuario
            try:
                user_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                
                # Si ya es administrador, solo actualizar el título
                if hasattr(user_member, 'status') and user_member.status in ['administrator', 'creator']:
                    if user_member.status == 'creator':
                        logger.info(f"Usuario {user_id} es el creador del grupo, no se puede cambiar título")
                        return False
                        
                    # Solo cambiar título si es diferente
                    current_title = getattr(user_member, 'custom_title', None)
                    if current_title != badge_titulo:
                        success = await self.bot.set_chat_administrator_custom_title(
                            chat_id=chat_id,
                            user_id=user_id,
                            custom_title=badge_titulo
                        )
                        
                        if success:
                            logger.info(f"Título actualizado a '{badge_titulo}' para usuario {user_id}")
                            return True
                        else:
                            logger.error(f"Error al actualizar título para usuario {user_id}")
                            return False
                    else:
                        logger.info(f"Usuario {user_id} ya tiene el título '{badge_titulo}'")
                        return True
                        
                # Si no es administrador, promoverlo
                else:
                    # Permisos básicos para el badge (sin permisos destructivos)
                    success = await self.bot.promote_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        is_anonymous=False,  # No anónimo
                        can_manage_chat=False,  # No puede gestionar chat
                        can_delete_messages=False,  # No puede borrar mensajes
                        can_manage_video_chats=False,  # No puede gestionar videollamadas
                        can_restrict_members=False,  # No puede restringir miembros
                        can_promote_members=False,  # No puede promover otros
                        can_change_info=False,  # No puede cambiar info del grupo
                        can_invite_users=True,  # Puede invitar usuarios (básico)
                        can_pin_messages=False,  # No puede anclar mensajes
                        can_manage_topics=False  # No puede gestionar topics
                    )
                    
                    if success:
                        logger.info(f"Usuario {user_id} promovido a administrador con permisos básicos")
                        
                        # Establecer título personalizado
                        title_success = await self.bot.set_chat_administrator_custom_title(
                            chat_id=chat_id,
                            user_id=user_id,
                            custom_title=badge_titulo
                        )
                        
                        if title_success:
                            logger.info(f"Badge '{badge_titulo}' otorgado exitosamente al usuario {user_id}")
                            return True
                        else:
                            logger.error(f"Error al establecer título '{badge_titulo}' para usuario {user_id}")
                            return False
                    else:
                        logger.error(f"Error al promover usuario {user_id} a administrador")
                        return False
                        
            except Exception as e:
                logger.error(f"Error obteniendo información del usuario {user_id}: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error general al otorgar badge automático: {str(e)}")
            return False

if __name__ == '__main__':
    asyncio.run(RewardsManager(AntDatabase(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )).main()) 