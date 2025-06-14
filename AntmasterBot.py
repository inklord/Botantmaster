import logging
import os
import sys
import re
import json
import random
import requests
import time
from datetime import datetime, timedelta, date
import asyncio
import aiohttp
import urllib.parse
from urllib.parse import quote
import threading
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from typing import Dict, List, Union, Optional, Any
from functools import wraps
import tempfile
import zipfile
import io
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from deep_translator import GoogleTranslator
import mysql.connector
import ssl
from aiogram import Bot, Dispatcher, types
from aiohttp import ClientSession as AiohttpSession
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, Message, ReactionTypeEmoji, 
    BufferedInputFile, InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from openai import AsyncOpenAI

# Importar el módulo de reglas
from usuario_rules import verify_user_role, verify_user_level, ADMIN_ROLES, verificar_restricciones

# Importar la base de datos
from database import AntDatabase
from translation_manager import TranslationManager
from rewards_manager import RewardsManager

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

logger = logging.getLogger(__name__)

# Obtener el token del bot
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("No se encontró el token del bot en las variables de entorno")
    sys.exit(1)

# Configuración de reintentos para solicitudes HTTP
TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 2


# Configuración de la sesión de requests con reintentos
http_session = requests.Session()
retry_strategy = requests.adapters.Retry(
    total=MAX_RETRIES,
    backoff_factor=RETRY_BACKOFF,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
http_session.mount("http://", adapter)
http_session.mount("https://", adapter)

# Inicializar base de datos
db = AntDatabase(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'root'),
    password=os.getenv('DB_PASSWORD', ''),
    database=os.getenv('DB_NAME', 'antmaster')
)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'antmaster')
}

db = AntDatabase(**DB_CONFIG)

# Inicializar el gestor de descuentos
from discount_code_manager import DiscountCodeManager
discount_manager = DiscountCodeManager(db)

# Inicializar el gestor de recompensas
rewards_manager = RewardsManager(db)

# Inicializar el gestor de traducción
translation_manager = TranslationManager(db)

# Configuración de APIs
INATURALIST_API = 'https://api.inaturalist.org/v1/taxa?q='
ANTWIKI_API = 'https://www.antwiki.org/wiki/'
ANTMAPS_API = 'https://antmaps.org/api/v01'
ANTFLIGHTS_API = 'https://antflights.com'
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')
GOOGLE_SEARCH_API = 'https://www.googleapis.com/customsearch/v1'
GEOCODING_API = 'https://geocoding-api.open-meteo.com/v1/search'
WEATHER_API = 'https://api.open-meteo.com/v1/forecast'

# Datos de vuelos nupciales por especie
especies_vuelos = {
    "Messor barbarus": {
        "meses_vuelo": ["julio", "agosto", "septiembre"],
        "temperatura": {"min": 25, "max": 32},
        "humedad": {"min": 40, "max": 60},
        "viento_max": 15,
        "horas_activas": "16:00-20:00",
        "distribucion": ["España", "Portugal", "Francia", "Italia", "Marruecos"],
        "region": "Europa y Norte de África"
    },
    "Lasius niger": {
        "meses_vuelo": ["junio", "julio", "agosto"],
        "temperatura": {"min": 20, "max": 28},
        "humedad": {"min": 50, "max": 70},
        "viento_max": 12,
        "horas_activas": "15:00-19:00",
        "distribucion": ["España", "Europa"],
        "region": "Europa"
    },
    "Pheidole pallidula": {
        "meses_vuelo": ["mayo", "junio", "julio", "agosto"],
        "temperatura": {"min": 22, "max": 30},
        "humedad": {"min": 45, "max": 65},
        "viento_max": 10,
        "horas_activas": "17:00-21:00",
        "distribucion": ["España", "Mediterráneo"],
        "region": "Mediterráneo"
    },
    "Acromyrmex lobicornis": {
        "meses_vuelo": ["octubre", "noviembre", "diciembre"],
        "temperatura": {"min": 20, "max": 30},
        "humedad": {"min": 40, "max": 70},
        "viento_max": 15,
        "horas_activas": "16:00-20:00",
        "distribucion": ["Argentina", "Brasil", "Paraguay", "Uruguay"],
        "region": "Sudamérica"
    },
    "Solenopsis invicta": {
        "meses_vuelo": ["septiembre", "octubre", "noviembre", "diciembre"],
        "temperatura": {"min": 24, "max": 32},
        "humedad": {"min": 45, "max": 75},
        "viento_max": 12,
        "horas_activas": "15:00-19:00",
        "distribucion": ["Argentina", "Brasil", "Paraguay", "Estados Unidos"],
        "region": "América"
    }
}

# Regiones geográficas para las especies
REGIONES_GEOGRAFICAS = {
    "Europa": {
        "paises": ["España", "Portugal", "Francia", "Italia", "Alemania", "Reino Unido"],
        "coordenadas": {
            "min_lat": 35,
            "max_lat": 60,
            "min_lon": -10,
            "max_lon": 30
        }
    },
    "Mediterráneo": {
        "paises": ["España", "Portugal", "Italia", "Grecia", "Marruecos", "Túnez"],
        "coordenadas": {
            "min_lat": 30,
            "max_lat": 45,
            "min_lon": -10,
            "max_lon": 35
        }
    },
    "Sudamérica": {
        "paises": ["Argentina", "Brasil", "Paraguay", "Uruguay", "Chile", "Colombia"],
        "coordenadas": {
            "min_lat": -55,
            "max_lat": 12,
            "min_lon": -80,
            "max_lon": -35
        }
    },
    "América del Norte": {
        "paises": ["Estados Unidos", "Canadá", "México"],
        "coordenadas": {
            "min_lat": 15,
            "max_lat": 70,
            "min_lon": -165,
            "max_lon": -50
        }
    }
}

# Mapeo de países a regiones
regiones = {
    "España": ["Europa", "Mediterráneo"],
    "Portugal": ["Europa"],
    "Francia": ["Europa"],
    "Italia": ["Europa", "Mediterráneo"],
    "Marruecos": ["Norte de África"],
    "Argentina": ["Sudamérica", "América"],
    "Brasil": ["Sudamérica", "América"],
    "Paraguay": ["Sudamérica", "América"],
    "Uruguay": ["Sudamérica", "América"],
    "Estados Unidos": ["América del Norte", "América"]
}

# Crear el bot sin sesión personalizada primero
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Variable global para la sesión que se inicializará en main()
global_session = None

async def init_session():
    """Inicializa la sesión HTTP global"""
    global global_session
    if global_session is None:
        global_session = aiohttp.ClientSession()
    return global_session

async def close_session():
    """Cierra la sesión HTTP global"""
    global global_session
    if global_session and not global_session.closed:
        await global_session.close()
        global_session = None

# Inicializar el traductor
translator = GoogleTranslator(source='en', target='es')

def translate_text(text):
    """Traduce texto del inglés al español usando deep-translator"""
    if not text or not isinstance(text, str):
        return ""
        
    try:
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Error en la traducción: {str(e)}")
        return text

def make_request(url, params=None, timeout=TIMEOUT):
    """Función auxiliar para hacer peticiones HTTP con reintentos"""
    try:
        response = http_session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al acceder a {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al acceder a {url}: {str(e)}")
        return None

async def buscar_especie_google(query):
    """Busca la especie usando Google Custom Search API y guarda en la base de datos"""
    logger.info(f"Iniciando búsqueda en fuentes externas para: {query}")
    
    try:
        query = query.strip().lower()
        words = query.split()
        if len(words) < 2:
            return None
            
        genus = words[0].capitalize()
        species = words[1].lower()
        scientific_name = f"{genus} {species}"
        
        # 1. Intentar búsqueda directa en AntWiki
        antwiki_url = f"{ANTWIKI_API}{genus}_{species}"
        response = make_request(antwiki_url)
        photo_url = None
        
        if response and response.status_code == 200:
            # 2. Si se encuentra en AntWiki, buscar en iNaturalist
            url = f"https://api.inaturalist.org/v1/taxa?q={quote(scientific_name)}&rank=species&per_page=1"
            inat_response = make_request(url)
            inat_id = None
            
            if inat_response:
                data = inat_response.json()
                if data.get('total_results', 0) > 0 and data.get('results'):
                    result = data['results'][0]
                    inat_id = str(result.get('id'))
                    if result.get('default_photo'):
                        photo_url = result['default_photo'].get('medium_url')
            
            # Si no hay foto en iNaturalist, intentar en AntWiki
            if not photo_url:
                photo_url = await buscar_foto_antwiki(genus, species)
            
            # 3. Guardar en la base de datos
            db.add_species(
                scientific_name,
                antwiki_url=antwiki_url,
                inat_id=inat_id,
                photo_url=photo_url
            )
            return scientific_name
            
        # 4. Si no se encuentra en AntWiki, buscar en Google
        params = {
            'key': GOOGLE_API_KEY,
            'cx': GOOGLE_CSE_ID,
            'q': f"site:antwiki.org/wiki {query}",
            'num': 10
        }
        
        response = make_request(GOOGLE_SEARCH_API, params=params)
        if response:
            data = response.json()
            if 'items' in data:
                for item in data['items']:
                    if 'antwiki.org/wiki/' in item['link']:
                        species_name = item['link'].split('antwiki.org/wiki/')[1]
                        species_name = species_name.replace('_', ' ').strip()
                        if ' ' in species_name:
                            # Buscar en iNaturalist
                            url = f"https://api.inaturalist.org/v1/taxa?q={quote(species_name)}&rank=species&per_page=1"
                            inat_response = make_request(url)
                            inat_id = None
                            photo_url = None
                            
                            if inat_response:
                                data = inat_response.json()
                                if data.get('total_results', 0) > 0 and data.get('results'):
                                    result = data['results'][0]
                                    inat_id = str(result.get('id'))
                                    if result.get('default_photo'):
                                        photo_url = result['default_photo'].get('medium_url')
                            
                            # Si no hay foto en iNaturalist, intentar en AntWiki
                            if not photo_url:
                                genus, species = species_name.split()
                                photo_url = await buscar_foto_antwiki(genus, species)
                            
                            # Guardar en la base de datos
                            db.add_species(
                                species_name,
                                antwiki_url=item['link'],
                                inat_id=inat_id,
                                photo_url=photo_url
                            )
                            return species_name
        
        return None
        
    except Exception as e:
        logger.error(f"Error en la búsqueda externa: {str(e)}", exc_info=True)
        return None

def encontrar_especies_similares(nombre_especie: str, umbral: int = 60) -> List[Dict[str, Union[str, float]]]:
    """
    Encuentra especies similares en la base de datos basándose en la similitud del nombre.
    
    Args:
        nombre_especie: Nombre de la especie a buscar
        umbral: Porcentaje mínimo de similitud (default: 60)
    
    Returns:
        Lista de diccionarios con nombres de especies y su porcentaje de similitud
    """
    especies_similares = []
    todas_especies = db.get_all_species()
    
    # Normalizar el nombre de búsqueda
    nombre_busqueda = nombre_especie.lower().strip()
    
    for especie in todas_especies:
        nombre_bd = especie['scientific_name'].lower().strip()
        
        # Calcular similitud por diferentes métodos
        similitud_exacta = 100 if nombre_bd == nombre_busqueda else 0
        similitud_contiene = 90 if nombre_busqueda in nombre_bd or nombre_bd in nombre_busqueda else 0
        similitud_palabras = calcular_similitud(nombre_busqueda, nombre_bd)
        
        # Tomar la mayor similitud encontrada
        similitud = max(similitud_exacta, similitud_contiene, similitud_palabras)
        
        if similitud >= umbral:
            especies_similares.append({
                'nombre': especie['scientific_name'],
                'similitud': round(similitud, 1),
                'region': especie.get('region', 'No especificada'),
                'photo_url': especie.get('photo_url', None)
            })
    
    # Ordenar por similitud descendente
    return sorted(especies_similares, key=lambda x: x['similitud'], reverse=True)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    # Registrar interacción
    await db.log_user_interaction(
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.first_name,
        interaction_type='command',
        command_name='start',
        chat_id=message.chat.id
    )
    await message.answer("🐜 ¡Bienvenido a AntMasterBot! El bot para amantes de la mirmecología. Usa /hormidato para un dato curioso o /especie [nombre] para buscar información sobre una especie.")

@dp.message(Command("ayuda"))
async def ayuda(message: types.Message):
    """Muestra información de ayuda sobre los comandos disponibles"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='ayuda',
            chat_id=message.chat.id
        )
        
        # Verificar si el usuario es administrador
        es_admin = await is_admin(message.chat.id, message.from_user.id)
        
        mensaje = """🤖 <b>AntmasterBot - Comandos Disponibles</b>

🔍 <b>Información y Búsqueda:</b>
/especie [nombre] - Buscar información sobre especies de hormigas
/hormidato - Dato curioso aleatorio sobre hormigas
/prediccion [ubicación] - Predicción de vuelos nupciales

🎮 <b>Juegos:</b>
/adivina_especie - Juego para adivinar especies de hormigas

📊 <b>Rankings y Estadísticas:</b>
/ranking - Ver el ranking general de usuarios
/ranking_semanal - Ver el ranking semanal
/ranking_mensual - Ver el ranking mensual
/nivel - Ver tu nivel y puntos

🎁 <b>Recompensas:</b>
/recompensas - Ver las recompensas disponibles
/mis_codigos - Ver tus códigos de descuento
/validar_codigo [código] - Validar un código de descuento

📋 <b>Información:</b>
/normas - Ver las normas del grupo
/ayuda - Mostrar esta ayuda"""

        if es_admin:
            mensaje += """

👑 <b>Comandos de Administrador:</b>
/cargar_especies - Cargar especies desde archivo
/actualizar_regiones - Actualizar regiones de especies
/actualizar_estadisticas - Actualizar estadísticas de vuelos
/actualizar_todo - Actualización completa
/enviar_mensaje [mensaje] - Enviar mensaje a todos los chats
/iniciar_ranking - Iniciar sistema de ranking
/detener_ranking - Detener sistema de ranking
/reset_db - Resetear base de datos (¡CUIDADO!)"""

        await message.answer(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error al mostrar ayuda: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al mostrar la ayuda.")

@dp.message(Command("normas"))
async def mostrar_normas(message: types.Message):
    """Muestra las normas del grupo"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='normas',
            chat_id=message.chat.id
        )
        
        # Texto de las normas
        texto = """🐜 NORMAS DEL GRUPO ANTMASTER 🐜

• Respeta a todos los miembros del grupo
• Solo comparte contenido de mirmecología
• Información precisa y verificada
• No spam ni mensajes repetitivos
• Preferiblemente español, también inglés

• Prácticas éticas de crianza
• No liberar especies en ecosistemas ajenos
• Respetar leyes locales de captura
• Fotos claras para identificación

• Compras en antmastershop.com
• Ayuda a principiantes con paciencia

El incumplimiento puede resultar en expulsión.
Los administradores tienen la última palabra.

¡DISFRUTA Y APRENDE!"""
        
        # Enviar el mensaje
        await message.answer(texto)
        
    except Exception as e:
        logger.error(f"Error en comando normas: {str(e)}")
        await message.answer("Error al mostrar las normas. Por favor, inténtalo de nuevo más tarde.")

@dp.message(Command("iniciar_ranking"))
async def iniciar_ranking(message: types.Message):
    """Inicia el sistema de ranking"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='iniciar_ranking',
            chat_id=message.chat.id
        )
        
        # Iniciar el gestor de ranking en segundo plano
        asyncio.create_task(rewards_manager.main())
        await message.answer("✅ Sistema de ranking iniciado correctamente")
        
    except Exception as e:
        logger.error(f"Error al iniciar el sistema de ranking: {str(e)}")
        await message.answer("❌ Error al iniciar el sistema de ranking")

@dp.message(Command("detener_ranking"))
async def detener_ranking(message: types.Message):
    """Detiene el sistema de ranking"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='detener_ranking',
            chat_id=message.chat.id
        )
        
        # Detener el gestor de ranking
        rewards_manager.detener_sistema()
        await message.answer("✅ Sistema de ranking detenido correctamente")
        
    except Exception as e:
        logger.error(f"Error al detener el sistema de ranking: {str(e)}")
        await message.answer("❌ Error al detener el sistema de ranking")

@dp.message(Command("hormidato"))
async def hormidato(message: types.Message):
    # Registrar interacción
    await db.log_user_interaction(
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.first_name,
        interaction_type='command',
        command_name='hormidato',
        chat_id=message.chat.id
    )
    
    # Sistema para evitar repetición de hormidatos
    chat_id = message.chat.id
    
    # Comprobar si existe el registro de hormidatos anteriores para este chat
    if not hasattr(hormidato, "ultimos_hormidatos"):
        hormidato.ultimos_hormidatos = {}
    
    # Crear registro para este chat si no existe
    if chat_id not in hormidato.ultimos_hormidatos:
        hormidato.ultimos_hormidatos[chat_id] = []
    
    # Base de datos ampliada de hormidatos
    datos = {
        "Curiosidades Generales": [
            "Las hormigas pueden levantar hasta 50 veces su propio peso.",
            "La reina de una colonia de hormigas puede vivir hasta 30 años.",
            "Algunas especies de hormigas practican la agricultura cultivando hongos.",
            "Las hormigas del género Myrmecocystus almacenan alimento en el abdomen de hormigas obreras especiales llamadas 'hormigas miel'.",
            "Las hormigas pueden construir puentes vivientes usando sus propios cuerpos.",
            "Las hormigas usan feromonas para comunicarse, creando complejos 'mapas químicos'.",
            "El cerebro de una hormiga tiene alrededor de 250,000 neuronas, uno de los más grandes en relación a su tamaño corporal.",
            "Las hormigas son capaces de reconocer a sus compañeras de colonia mediante el olor.",
            "Las hormigas se limpian regularmente para evitar infecciones por hongos y bacterias.",
            "Una colonia de hormigas puede mover hasta 50 toneladas de tierra durante su vida."
        ],
        "Especies Fascinantes": [
            "La hormiga de fuego (Solenopsis invicta) es conocida por su dolorosa picadura.",
            "La hormiga Paraponera clavata, conocida como hormiga bala, tiene la picadura más dolorosa del mundo animal.",
            "Las hormigas argentinas (Linepithema humile) han creado una supercolonia que se extiende por miles de kilómetros.",
            "Las hormigas bulldog (Myrmecia) son una de las especies más agresivas y poseen una picadura muy dolorosa.",
            "Las hormigas cortadoras de hojas (Atta) cultivan hongos como fuente de alimento.",
            "Las hormigas Dracula (Mystrium camillae) usan sus mandíbulas para 'disparar' a velocidades de hasta 320 km/h.",
            "Las hormigas tejedoras (Oecophylla) cosen hojas usando la seda producida por sus larvas.",
            "Las hormigas del género Polyrhachis han desarrollado pelos que reflejan el calor del sol y pueden vivir en hábitats extremadamente calientes.",
            "Las hormigas saltadoras (Harpegnathos) pueden saltar hasta 10 cm para atrapar a sus presas.",
            "Las hormigas Cataglyphis pueden memorizar rutas complejas para volver al nido, utilizando el sol como brújula."
        ],
        "Consejos de Crianza": [
            "Mantén la temperatura del hormiguero entre 24-28°C para la mayoría de especies tropicales.",
            "Proporciona una fuente constante de agua para evitar la deshidratación de la colonia.",
            "Alimenta con insectos pequeños como moscas o grillos para una dieta rica en proteínas.",
            "Evita exponer la colonia a vibraciones o ruidos fuertes para no estresarlas.",
            "Limpia el área de forrajeo regularmente para evitar la acumulación de residuos.",
            "Si mantienes especies granívoras, ofrece diferentes tipos de semillas para una dieta variada.",
            "El glucógeno líquido es excelente para proporcionar energía a las obreras forrajeadoras.",
            "Durante la hibernación, reduce gradualmente la temperatura para evitar shock térmico.",
            "Para la mayoría de las colonias, una humedad relativa entre 40-60% es ideal.",
            "Las dietas de proteínas deben ser más abundantes durante las fases de crecimiento rápido de la colonia."
        ],
        "Comportamiento Social": [
            "Las hormigas practican el 'trofallaxis', el intercambio de alimento líquido boca a boca.",
            "Algunas especies de hormigas esclavizan a otras colonias para que trabajen para ellas.",
            "Ciertas hormigas tienen 'cementerios' designados donde llevan a sus muertas para evitar enfermedades.",
            "Las hormigas obreras crean 'guarderías' específicas para cuidar de las larvas según su etapa de desarrollo.",
            "Algunas colonias tienen 'soldados kamikaze' que explotan, liberando sustancias pegajosas para defender el nido.",
            "Las hormigas pueden adoptar diferentes roles según las necesidades de la colonia.",
            "Hay hormigas que realizan 'rituales funerarios', llevando a sus muertas a lugares específicos lejos del nido.",
            "Algunas especies tienen 'enfermeras' dedicadas que cuidan exclusivamente a las larvas enfermas.",
            "Las hormigas pueden reconocer y rechazar a miembros de otras colonias incluso de la misma especie.",
            "Existen hormigas que 'secuestran' pupas de otras colonias para aumentar su fuerza laboral."
        ],
        "Adaptaciones Sorprendentes": [
            "Las hormigas Cephalotes tienen cabezas planas que usan como 'puertas vivientes' para bloquear la entrada al nido.",
            "Algunas especies de hormigas pueden nadar y sobrevivir bajo el agua durante horas.",
            "Las hormigas 'gliders' pueden planear controladamente si caen de los árboles, dirigiéndose de vuelta al tronco.",
            "Ciertas hormigas del desierto han desarrollado patas extremadamente largas para mantener su cuerpo alejado de la arena caliente.",
            "Algunas especies tienen mandíbulas que se cierran a velocidades de más de 230 km/h, las más rápidas del reino animal.",
            "Las hormigas del género Camponotus pueden detectar terremotos minutos antes de que ocurran.",
            "Las hormigas Temnothorax rugatulus construyen nidos con múltiples capas de aislamiento para regular la temperatura.",
            "Las hormigas Ectatomminae tienen aguijones modificados que pueden usar como sierras.",
            "Algunas hormigas pueden entrar en un estado similar a la hibernación para sobrevivir inundaciones.",
            "Las hormigas Adetomyrma son vampíricas y se alimentan de la hemolinfa de sus propias larvas sin dañarlas."
        ],
        "Datos Evolutivos": [
            "Las hormigas evolucionaron de avispas hace aproximadamente 140-168 millones de años.",
            "El registro fósil más antiguo de hormigas data del período Cretácico, en ámbar de 99 millones de años.",
            "Existen más de 14,000 especies de hormigas identificadas, pero se estima que podría haber hasta 22,000.",
            "Las hormigas representan aproximadamente el 15-25% de la biomasa animal terrestre del planeta.",
            "Las hormigas han desarrollado sociedades complejas de manera independiente a otros insectos sociales como las abejas.",
            "La estructura social de las hormigas ha evolucionado de manera similar en diferentes continentes, un ejemplo de evolución convergente.",
            "Algunas especies de hormigas han perdido la capacidad de picar, desarrollando otros métodos de defensa.",
            "El comportamiento de criar hongos ha evolucionado independientemente en dos linajes diferentes de hormigas.",
            "Las colonias de hormigas pueden tener desde unas pocas docenas hasta millones de individuos, según la especie.",
            "Las hormigas legionarias evolucionaron sin nidos permanentes, viviendo en 'bivaques' temporales formados por sus propios cuerpos."
        ],
        "Relaciones con Humanos": [
            "Las hormigas fueron utilizadas como suturas naturales en algunas culturas antiguas, haciendo que muerdan la herida y luego cortando su cuerpo.",
            "Algunas tribus del Amazonas usan el veneno de hormigas bala en rituales de iniciación.",
            "Las hormigas cortadoras de hojas causan miles de millones en daños a cultivos anualmente.",
            "Los antiguos griegos y romanos observaban el comportamiento de las hormigas para predecir el clima.",
            "La mirmecocoria es la dispersión de semillas por hormigas, vital para muchas especies de plantas.",
            "En algunas culturas asiáticas, las hormigas tejedoras se utilizan como insecticidas naturales en huertos.",
            "Las hormigas invasoras como la hormiga de fuego han sido introducidas accidentalmente por el comercio humano.",
            "La mirmecología, el estudio de las hormigas, fue popularizada por E.O. Wilson, quien dedicó su vida a estos insectos.",
            "Las hormigas han inspirado algoritmos de inteligencia artificial basados en sus métodos de búsqueda de caminos.",
            "El ácido fórmico fue aislado por primera vez a partir de hormigas, de ahí su nombre (formica = hormiga en latín)."
        ]
    }
    
    import random
    
    # Lista de todas las categorías y hormidatos
    todas_categorias = list(datos.keys())
    todos_hormidatos = []
    for categoria in todas_categorias:
        for dato in datos[categoria]:
            todos_hormidatos.append((categoria, dato))
    
    # Filtrar hormidatos que no se han mostrado recientemente
    hormidatos_disponibles = [h for h in todos_hormidatos if h not in hormidato.ultimos_hormidatos[chat_id]]
    
    # Si todos los hormidatos ya se mostraron, resetear la lista
    if not hormidatos_disponibles:
        hormidato.ultimos_hormidatos[chat_id] = []
        hormidatos_disponibles = todos_hormidatos
    
    # Seleccionar un hormidato aleatorio de los disponibles
    hormidato_seleccionado = random.choice(hormidatos_disponibles)
    categoria, dato = hormidato_seleccionado
    
    # Actualizar el historial (mantener solo los últimos 15 hormidatos para evitar repeticiones)
    hormidato.ultimos_hormidatos[chat_id].append(hormidato_seleccionado)
    if len(hormidato.ultimos_hormidatos[chat_id]) > 15:
        hormidato.ultimos_hormidatos[chat_id].pop(0)
    
    # Enviar el hormidato
    await message.answer(f"🐜 {categoria}:\n{dato}")

async def buscar_en_inaturalist(query):
    """Busca información y fotos en iNaturalist"""
    try:
        # Construir la URL de la API
        url = "https://api.inaturalist.org/v1/taxa"
        params = {
            "q": query,
            "rank": "species",
            "per_page": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if not data.get("results") or len(data["results"]) == 0:
                    return None
                    
                result = data["results"][0]
                    
                # Extraer información relevante
                info = {
                    "id": result.get("id"),
                    "name": result.get("name"),
                    "preferred_common_name": result.get("preferred_common_name"),
                    "wikipedia_url": result.get("wikipedia_url"),
                    "photo_url": None
                }
                
                # Buscar la mejor foto disponible
                if result.get("taxon_photos") and len(result["taxon_photos"]) > 0:
                    photo = result["taxon_photos"][0]["photo"]
                    if photo.get("medium_url"):
                        info["photo_url"] = photo["medium_url"]
                    elif photo.get("url"):
                        info["photo_url"] = photo["url"]
                
                return info
                
    except Exception as e:
        logger.error(f"Error al buscar en iNaturalist: {str(e)}")
        return None

async def determinar_region_especie(species_info):
    """Determina la región de una especie basada en datos de iNaturalist"""
    try:
        inat_result = await buscar_en_inaturalist(species_info)
        if inat_result and 'observations' in inat_result:
            regiones = set()
            for obs in inat_result['observations']:
                lat = obs.get('latitude')
                lon = obs.get('longitude')
                if lat and lon:
                    region = obtener_region_por_coordenadas(lat, lon)
                    if region:
                        regiones.add(region)
            return list(regiones)
    except Exception as e:
        logger.error(f"Error al determinar región: {str(e)}")
    return []

def calcular_similitud(a, b):
    """Calcula el porcentaje de similitud entre dos cadenas"""
    return round(SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100)

def normalize_scientific_name(name):
    """Normaliza un nombre científico para búsquedas consistentes"""
    try:
        # Limpiar espacios extra y convertir a formato estándar
        name = ' '.join(name.strip().split())
        
        # Separar en palabras
        words = name.split()
        if len(words) >= 2:
            # Formato estándar: Genus species
            genus = words[0].capitalize()
            species = words[1].lower()
            return f"{genus} {species}"
        
        return name.title()
    except Exception as e:
        logger.error(f"Error normalizando nombre científico: {str(e)}")
        return name.strip()

def generar_resumen_basico(result, inat_info, antwiki_info, distribucion):
    """Genera un resumen básico de la información de la especie"""
    try:
        resumen = []
        
        # Información básica de la especie
        if result:
            nombre_cientifico = result.get('scientific_name', 'Desconocido')
            resumen.append(f"**{nombre_cientifico}**")
            
            if result.get('common_name'):
                resumen.append(f"Nombre común: {result['common_name']}")
        
        # Información de distribución
        if distribucion and len(distribucion) > 0:
            regiones = ", ".join(distribucion[:3])  # Primeras 3 regiones
            if len(distribucion) > 3:
                regiones += f" y {len(distribucion) - 3} más"
            resumen.append(f"Distribución: {regiones}")
        
        # Información de iNaturalist
        if inat_info and inat_info.get('observations'):
            resumen.append(f"Observaciones registradas: {inat_info['observations']}")
        
        # Información básica de comportamiento/características
        if antwiki_info:
            if antwiki_info.get('habitat'):
                resumen.append(f"Hábitat: {antwiki_info['habitat'][:100]}...")
        
        return "\n".join(resumen) if resumen else "Información básica no disponible."
        
    except Exception as e:
        logger.error(f"Error generando resumen básico: {str(e)}")
        return "Error al generar resumen de la especie."

# Inicializar el cliente de OpenAI
client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def generar_descripcion_especie(nombre_cientifico: str) -> str:
    """Genera una descripción detallada de la especie usando ChatGPT y datos de AntWiki"""
    try:
        # Primero intentar obtener la descripción cacheada
        descripcion_cache = db.get_cached_description(nombre_cientifico)
        if descripcion_cache:
            logger.info(f"Descripción recuperada del caché para: {nombre_cientifico}")
            return descripcion_cache
            
        logger.info(f"Generando nueva descripción para: {nombre_cientifico}")
        genus, species = nombre_cientifico.split()[:2]
        
        # Obtener información de AntWiki
        antwiki_info = None
        url = f"https://www.antwiki.org/wiki/{genus}_{species}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extraer información relevante
                    content = soup.find('div', id='mw-content-text')
                    if content:
                        info = {
                            'description': [],
                            'distribution': [],
                            'habitat': [],
                            'behavior': [],
                            'measurements': []
                        }
                        
                        # Buscar información en la tabla (infobox)
                        infobox = soup.find('table', class_='infobox')
                        if infobox:
                            for row in infobox.find_all('tr'):
                                header = row.find('th')
                                value = row.find('td')
                                if header and value:
                                    key = header.get_text().strip().lower()
                                    val = value.get_text().strip()
                                    if any(word in key for word in ['size', 'length', 'measurements']):
                                        info['measurements'].append(f"{key}: {val}")
                                    elif 'distribution' in key:
                                        info['distribution'].append(val)
                                    elif 'habitat' in key:
                                        info['habitat'].append(val)
                        
                        # Buscar secciones relevantes en el contenido
                        for section in content.find_all(['h2', 'h3']):
                            section_title = section.get_text().strip().lower()
                            next_elem = section.find_next_sibling()
                            
                            while next_elem and next_elem.name not in ['h2', 'h3']:
                                if next_elem.name == 'p':
                                    text = next_elem.get_text().strip()
                                    if text:
                                        if any(word in section_title for word in ['description', 'descripción']):
                                            info['description'].append(text)
                                        elif any(word in section_title for word in ['distribution', 'distribución']):
                                            info['distribution'].append(text)
                                        elif any(word in section_title for word in ['habitat', 'hábitat']):
                                            info['habitat'].append(text)
                                        elif any(word in section_title for word in ['behavior', 'behaviour', 'comportamiento']):
                                            info['behavior'].append(text)
                                next_elem = next_elem.find_next_sibling()
                        
                        # Preparar el prompt para ChatGPT
                        prompt = f"""Genera un resumen BREVE Y CONCISO (máximo 700 caracteres) sobre la hormiga {nombre_cientifico} basado en la siguiente información.
                        
                        Información disponible:
                        Descripción: {' '.join(info['description'][:1])}
                        Distribución: {' '.join(info['distribution'])}
                        Hábitat: {' '.join(info['habitat'])}
                        Comportamiento: {' '.join(info['behavior'])}
                        
                        REGLAS IMPORTANTES:
                        1. IGNORA completamente cualquier medida, longitud, tamaño o dimensión
                        2. PRIORIZA comportamientos sociales, hábitos de anidación y alimentación
                        3. DESTACA características físicas distintivas (colores, formas, estructuras especiales)
                        4. Menciona datos curiosos sobre su ecología o distribución
                        5. Máximo 700 caracteres total
                        6. Usa máximo 2 emojis
                        7. Texto en español, estilo científico divulgativo
                        8. Si no hay información relevante, indica "Información limitada disponible"
                        """
                        
                        client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                        completion = await client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "Eres un experto en mirmecología especializado en generar resúmenes BREVES y precisos sobre especies de hormigas. Debes ser conciso y mantener el texto dentro del límite de caracteres."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7,
                            max_tokens=200
                        )
                        
                        descripcion = completion.choices[0].message.content
                        
                        # Guardar la descripción en la base de datos
                        if descripcion:
                            if db.save_species_description(nombre_cientifico, descripcion):
                                logger.info(f"Descripción guardada en caché para: {nombre_cientifico}")
                            else:
                                logger.warning(f"No se pudo guardar la descripción en caché para: {nombre_cientifico}")
                        
                        return descripcion
        
        return None
        
    except Exception as e:
        logger.error(f"Error al generar descripción de especie: {str(e)}")
        return None

async def buscar_especie_completa(scientific_name):
    """Busca información completa de una especie en todas las fuentes externas"""
    try:
        logger.info(f"Iniciando búsqueda completa para: {scientific_name}")
        
        species_data = {
            'scientific_name': scientific_name,
            'description': None,
            'photo_url': None,
            'antontop_info': None,
            'antwiki_info': None,
            'inat_info': None,
            'found_sources': []
        }
        
        # Buscar en iNaturalist (prioridad para fotos)
        try:
            inat_info = await buscar_en_inaturalist(scientific_name)
            if inat_info:
                species_data['inat_info'] = inat_info
                if inat_info.get('photo_url'):
                    species_data['photo_url'] = inat_info['photo_url']
                species_data['found_sources'].append('iNaturalist')
                logger.info(f"Encontrado en iNaturalist: {scientific_name}")
        except Exception as e:
            logger.error(f"Error buscando en iNaturalist: {str(e)}")
        
        # Buscar en AntOnTop (prioridad para información detallada)
        try:
            antontop_info = await buscar_info_antontop(scientific_name)
            if antontop_info:
                species_data['antontop_info'] = antontop_info
                if antontop_info.get('short_description'):
                    species_data['description'] = antontop_info['short_description']
                # Si no hay foto de iNaturalist, usar la de AntOnTop
                if not species_data['photo_url'] and antontop_info.get('photo_url'):
                    species_data['photo_url'] = antontop_info['photo_url']
                species_data['found_sources'].append('AntOnTop')
                logger.info(f"Encontrado en AntOnTop: {scientific_name}")
        except Exception as e:
            logger.error(f"Error buscando en AntOnTop: {str(e)}")
        
        # Buscar en AntWiki (información adicional y foto de respaldo)
        try:
            genus, species = scientific_name.split()[:2]
            antwiki_info = await buscar_foto_antwiki(genus, species)
            if antwiki_info:
                species_data['antwiki_info'] = antwiki_info
                # Si no hay foto anterior, usar la de AntWiki
                if not species_data['photo_url'] and antwiki_info.get('photo_url'):
                    species_data['photo_url'] = antwiki_info['photo_url']
                species_data['found_sources'].append('AntWiki')
                logger.info(f"Encontrado en AntWiki: {scientific_name}")
        except Exception as e:
            logger.error(f"Error buscando en AntWiki: {str(e)}")
        
        # Si no tenemos descripción, generarla con IA usando toda la información disponible
        if not species_data['description']:
            species_data['description'] = await generar_descripcion_mejorada(species_data)
        
        # Solo retornar si encontramos algo útil
        if species_data['found_sources'] or species_data['photo_url'] or species_data['description']:
            logger.info(f"Búsqueda completa exitosa para {scientific_name} - Fuentes: {species_data['found_sources']}")
            return species_data
        
        logger.warning(f"No se encontró información para: {scientific_name}")
        return None
        
    except Exception as e:
        logger.error(f"Error en búsqueda completa de {scientific_name}: {str(e)}")
        return None

async def generar_descripcion_mejorada(species_data):
    """Genera descripción usando toda la información recopilada"""
    try:
        scientific_name = species_data['scientific_name']
        
        # Verificar si ya existe en caché
        descripcion_cache = db.get_cached_description(scientific_name)
        if descripcion_cache:
            return descripcion_cache
        
        # Recopilar toda la información disponible
        info_texto = f"Especie: {scientific_name}\n\n"
        
        # Información de AntOnTop
        if species_data.get('antontop_info'):
            antontop = species_data['antontop_info']
            if antontop.get('short_description'):
                info_texto += f"Descripción AntOnTop: {antontop['short_description']}\n"
            if antontop.get('behavior'):
                info_texto += f"Comportamiento: {antontop['behavior']}\n"
            if antontop.get('region'):
                info_texto += f"Origen: {antontop['region']}\n"
        
        # Información de AntWiki
        if species_data.get('antwiki_info') and species_data['antwiki_info'].get('description'):
            info_texto += f"Información AntWiki: {species_data['antwiki_info']['description']}\n"
        
        # Información de iNaturalist
        if species_data.get('inat_info'):
            inat = species_data['inat_info']
            if inat.get('preferred_common_name'):
                info_texto += f"Nombre común: {inat['preferred_common_name']}\n"
        
        # Prompt mejorado para IA
        prompt = f"""Basándote en la siguiente información, genera una descripción breve y atractiva sobre esta especie de hormiga.

{info_texto}

REGLAS ESTRICTAS:
1. MÁXIMO 600 caracteres total
2. IGNORA completamente medidas, longitudes y dimensiones
3. PRIORIZA: comportamientos únicos, estrategias de supervivencia, hábitos sociales
4. DESTACA: características físicas distintivas (colores, formas especiales)
5. INCLUYE: datos curiosos sobre ecología o distribución si están disponibles
6. Estilo: científico divulgativo, accesible y fascinante
7. Idioma: español
8. Máximo 2 emojis apropiados
9. Si la información es limitada, sé honesto pero positivo

Responde SOLO con la descripción, sin explicaciones adicionales."""

        client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un mirmecólogo experto que crea descripciones fascinantes y precisas sobre hormigas para el público general, evitando datos técnicos como medidas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        descripcion = completion.choices[0].message.content.strip()
        
        # Guardar en caché
        if descripcion and db.save_species_description(scientific_name, descripcion):
            logger.info(f"Descripción generada y guardada para: {scientific_name}")
        
        return descripcion
        
    except Exception as e:
        logger.error(f"Error generando descripción mejorada: {str(e)}")
        return "Información disponible sobre esta fascinante especie de hormiga. 🐜"

async def enviar_informacion_especie_bd(message, species_result):
    """Envía información de una especie encontrada en la base de datos"""
    try:
        scientific_name = species_result['scientific_name']
        logger.info(f"Enviando información de BD para: {scientific_name}")
        
        # Obtener o generar descripción
        descripcion = db.get_cached_description(scientific_name)
        if not descripcion:
            # Generar nueva descripción usando información disponible
            descripcion = await generar_descripcion_especie(scientific_name)
            if not descripcion:
                descripcion = "Información disponible sobre esta especie de hormiga. 🐜"
        
        # Construir mensaje base
        caption = f"🐜 *{scientific_name}*\n\n{descripcion}\n\n"
        
        # Agregar información adicional si está disponible
        if species_result.get('region'):
            caption += f"📍 *Región:* {species_result['region']}\n"
        
        # Obtener vuelos recientes
        try:
            vuelos = await obtener_vuelos_recientes(scientific_name)
            if vuelos and vuelos.get('vuelos'):
                caption += "\n📅 *Últimos vuelos registrados:*\n"
                for vuelo in vuelos['vuelos'][:3]:
                    caption += f"• {vuelo['fecha']} - {vuelo['ubicacion']}\n"
        except:
            pass
        
        # Crear botones de enlaces
        keyboard = crear_teclado_enlaces(scientific_name)
        
        # Buscar y enviar foto
        photo_url = await obtener_mejor_foto(scientific_name, species_result.get('photo_url'))
        
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            except Exception as e:
                logger.error(f"Error enviando foto desde BD: {str(e)}")
        
        # Si no hay foto o falla, enviar solo texto
        await message.answer(
            text=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error enviando información de BD: {str(e)}")
        await message.answer("❌ Error al mostrar la información de la especie.")

async def enviar_informacion_especie_externa(message, species_data):
    """Envía información de una especie encontrada en fuentes externas"""
    try:
        scientific_name = species_data['scientific_name']
        logger.info(f"Enviando información externa para: {scientific_name}")
        
        # Usar descripción generada o crear una básica
        descripcion = species_data.get('description', "Información encontrada en fuentes externas. 🐜")
        
        # Construir mensaje
        caption = f"🐜 *{scientific_name}*\n\n{descripcion}\n\n"
        
        # Agregar fuentes encontradas
        if species_data.get('found_sources'):
            fuentes = ", ".join(species_data['found_sources'])
            caption += f"📚 *Fuentes:* {fuentes}\n"
        
        # Agregar información específica de AntOnTop
        if species_data.get('antontop_info'):
            antontop = species_data['antontop_info']
            if antontop.get('behavior'):
                caption += f"🔬 *Comportamiento:* {antontop['behavior'][:100]}{'...' if len(antontop['behavior']) > 100 else ''}\n"
            if antontop.get('region'):
                caption += f"🌍 *Origen:* {antontop['region']}\n"
        
        # Crear botones de enlaces
        keyboard = crear_teclado_enlaces(scientific_name)
        
        # Enviar con foto si está disponible
        if species_data.get('photo_url'):
            try:
                await message.answer_photo(
                    photo=species_data['photo_url'],
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            except Exception as e:
                logger.error(f"Error enviando foto externa: {str(e)}")
        
        # Si no hay foto o falla, enviar solo texto
        await message.answer(
            text=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error enviando información externa: {str(e)}")
        await message.answer("❌ Error al mostrar la información de la especie.")

async def obtener_mejor_foto(scientific_name, bd_photo_url=None):
    """Obtiene la mejor foto disponible siguiendo la prioridad: iNaturalist -> AntWiki -> BD"""
    try:
        # 1. Intentar iNaturalist (mejor calidad)
        try:
            inat_info = await buscar_en_inaturalist(scientific_name)
            if inat_info and inat_info.get('photo_url'):
                logger.info(f"Foto obtenida de iNaturalist para {scientific_name}")
                return inat_info['photo_url']
        except:
            pass
        
        # 2. Intentar AntWiki como respaldo
        try:
            genus, species = scientific_name.split()[:2]
            antwiki_info = await buscar_foto_antwiki(genus, species)
            if antwiki_info and antwiki_info.get('photo_url'):
                logger.info(f"Foto obtenida de AntWiki para {scientific_name}")
                return antwiki_info['photo_url']
        except:
            pass
        
        # 3. Usar foto de BD si está disponible
        if bd_photo_url:
            logger.info(f"Usando foto de BD para {scientific_name}")
            return bd_photo_url
        
        logger.warning(f"No se encontró foto para {scientific_name}")
        return None
        
    except Exception as e:
        logger.error(f"Error obteniendo foto para {scientific_name}: {str(e)}")
        return bd_photo_url

def crear_teclado_enlaces(scientific_name):
    """Crea el teclado con enlaces a fuentes externas"""
    try:
        genus, species = scientific_name.split()[:2]
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 AntWiki",
                    url=f"https://www.antwiki.org/wiki/{genus}_{species}"
                ),
                InlineKeyboardButton(
                    text="🗺️ AntMaps",
                    url=f"https://antmaps.org/?mode=species&species={genus}%20{species}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📸 iNaturalist",
                    url=f"https://www.inaturalist.org/taxa/search?q={genus}+{species}"
                ),
                InlineKeyboardButton(
                    text="🏪 AntOnTop",
                    url=f"https://antontop.com/es/{scientific_name.lower().replace(' ', '-')}/"
                )
            ]
        ])
    except:
        # Fallback simple si hay error
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Buscar en Google",
                    url=f"https://www.google.com/search?q={urllib.parse.quote(scientific_name + ' ant species')}"
                )
            ]
        ])

async def guardar_especie_nueva(species_data):
    """Guarda una nueva especie en la base de datos"""
    try:
        scientific_name = species_data['scientific_name']
        
        # Preparar datos para guardar
        genus, species = scientific_name.split()[:2]
        photo_url = species_data.get('photo_url')
        
        # URLs de fuentes
        antwiki_url = f"https://www.antwiki.org/wiki/{genus}_{species}"
        
        # ID de iNaturalist si está disponible
        inat_id = None
        if species_data.get('inat_info'):
            inat_id = species_data['inat_info'].get('id')
        
        # Región si está disponible
        region = None
        if species_data.get('antontop_info'):
            region = species_data['antontop_info'].get('region')
        
        # Guardar en base de datos
        success = db.add_species(
            scientific_name,
            antwiki_url=antwiki_url,
            photo_url=photo_url,
            inat_id=str(inat_id) if inat_id else None,
            region=region
        )
        
        if success:
            logger.info(f"Especie guardada exitosamente: {scientific_name}")
            
            # Guardar descripción en caché si existe
            if species_data.get('description'):
                db.save_species_description(scientific_name, species_data['description'])
        else:
            logger.error(f"Error guardando especie: {scientific_name}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error guardando nueva especie: {str(e)}")
        return False

async def mostrar_sugerencias_especies(message, query, especies_similares):
    """Muestra sugerencias de especies similares"""
    try:
        mensaje = f"🔍 No encontré exactamente '{query}'. ¿Te refieres a alguna de estas especies?\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for especie in especies_similares[:5]:
            mensaje += f"• *{especie['nombre']}* (Similitud: {especie['similitud']}%)\n"
            if especie.get('region') and especie['region'] != 'No especificada':
                mensaje += f"  📍 {especie['region']}\n"
            mensaje += "\n"
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"Ver {especie['nombre']}",
                    callback_data=f"ver_especie:{especie['nombre']}"
                )
            ])
        
        mensaje += "Haz clic en los botones para ver información detallada."
        
        await message.answer(
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error mostrando sugerencias: {str(e)}")
        await enviar_mensaje_no_encontrada(message, query)

async def enviar_mensaje_no_encontrada(message, query):
    """Envía mensaje cuando no se encuentra ninguna información"""
    try:
        mensaje = (
            f"❌ No se encontró información sobre '*{query}*'.\n\n"
            "**Sugerencias:**\n"
            "• Verifica la ortografía del nombre científico\n"
            "• Asegúrate de incluir género y especie\n"
            "• Ejemplo correcto: *Messor barbarus*\n\n"
            "💡 *¿Sabías que?* Tengo información sobre miles de especies de hormigas. "
            "Prueba con nombres más comunes como *Lasius niger* o *Formica rufa*."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Buscar en Google",
                    url=f"https://www.google.com/search?q={urllib.parse.quote(query + ' ant species')}"
                )
            ]
        ])
        
        await message.answer(
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error enviando mensaje no encontrada: {str(e)}")
        await message.answer("❌ No se encontró información sobre la especie solicitada.")

@dp.message(Command("especie"))
async def especie(message: types.Message):
    """Muestra información sobre una especie de hormiga siguiendo el flujo optimizado"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='especie',
            chat_id=message.chat.id
        )
        
        # Obtener el texto después del comando
        args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        args = args.strip()
        
        if not args:
            await message.answer(
                '❌ Por favor, proporciona el nombre de una especie.\n'
                'Ejemplo: /especie Messor barbarus'
            )
            return
        
        # Normalizar nombre científico
        normalized_name = normalize_scientific_name(args)
        
        # PASO 1: Buscar exactamente en la base de datos
        logger.info(f"Buscando en BD: {normalized_name}")
        result = db.find_species_by_name(normalized_name)
        
        if result:
            logger.info(f"Especie encontrada en BD: {result['scientific_name']}")
            await enviar_informacion_especie_bd(message, result)
            return
        
        # PASO 2: Si no está en BD, buscar en fuentes externas y guardar
        logger.info(f"Especie no encontrada en BD, buscando externamente: {normalized_name}")
        await message.answer("🔍 Especie no encontrada en mi base de datos. Buscando en fuentes externas...")
        
        # Buscar en todas las fuentes externas
        species_data = await buscar_especie_completa(normalized_name)
        
        if species_data:
            # Guardar en base de datos para futuros accesos
            logger.info(f"Guardando nueva especie en BD: {species_data['scientific_name']}")
            await guardar_especie_nueva(species_data)
            
            # Mostrar información de la especie encontrada
            await enviar_informacion_especie_externa(message, species_data)
        else:
            # Buscar especies similares como último recurso
            especies_similares = encontrar_especies_similares(args, umbral=50)
            if especies_similares:
                await mostrar_sugerencias_especies(message, args, especies_similares)
            else:
                await enviar_mensaje_no_encontrada(message, args)
                
    except Exception as e:
        logger.error(f"Error al buscar especie: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al buscar la especie. Por favor, intenta de nuevo.")

@dp.callback_query(lambda c: c.data and c.data.startswith('ver_especie:'))
async def handle_ver_especie(callback_query: types.CallbackQuery):
    """Maneja la selección de una especie sugerida"""
    try:
        # Obtener el nombre de la especie del callback_data
        species_name = callback_query.data.split(':', 1)[1]
        
        # Crear un mensaje falso para reutilizar la lógica del comando /especie
        fake_message = types.Message(
            message_id=callback_query.message.message_id,
            date=callback_query.message.date,
            chat=callback_query.message.chat,
            from_user=callback_query.from_user,
            text=f"/especie {species_name}",
            bot=callback_query.bot
        )
            
        # Usar el comando /especie para mostrar la información
        await especie(fake_message)
        
        # Responder al callback para quitar el "loading"
        await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Error al mostrar especie desde callback: {str(e)}")
        await callback_query.answer("❌ Error al mostrar la información de la especie", show_alert=True)

@dp.message(Command("ranking"))
async def ranking(message: types.Message):
    """Muestra el ranking histórico de usuarios"""
    cursor = None
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='ranking',
            chat_id=message.chat.id
        )
        
        # Obtener el ranking histórico de usuarios SOLO para este chat, usando solo la tabla user_experience
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                user_id,
                username,
                total_xp,
                current_level
            FROM user_experience
            WHERE chat_id = %s
            ORDER BY total_xp DESC
            LIMIT 10
        """, (message.chat.id,))
        
        ranking = cursor.fetchall()
        
        if not ranking:
            await message.answer("📊 No hay suficientes datos para mostrar el ranking en este chat.")
            return
            
        # Construir mensaje del ranking
        mensaje = "🏆 <b>Ranking de este Chat:</b>\n\n"
        for i, user in enumerate(ranking, 1):
            mensaje += (
                f"{i}. {user['username']}\n"
                f"   Nivel: {user['current_level']} | XP Total: {user['total_xp']}\n\n"
            )
            
        await message.answer(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error al mostrar ranking del chat: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al obtener el ranking.")
    finally:
        if cursor:
            cursor.close()

@dp.message(Command("cargar_especies"))
async def cargar_especies(message: types.Message):
    # Registrar interacción
    await db.log_user_interaction(
        message.from_user.id,
        message.from_user.username or message.from_user.first_name,
        'command',
        'cargar_especies'
    )
    """Carga múltiples especies a la vez desde un archivo o texto"""
    try:
        # Enviar mensaje de espera
        wait_message = await message.answer("🔄 Procesando especies, esto puede tomar varios minutos...")
        
        # Variables para almacenar el contenido y la región
        lines = []
        region = None
        
        if message.document:
            # Si es un archivo adjunto
            file = await message.document.download()
            try:
                with open(file.name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.strip().split('\n')
            except UnicodeDecodeError:
                # Intentar con otra codificación si UTF-8 falla
                with open(file.name, 'r', encoding='latin-1') as f:
                    content = f.read()
                    lines = content.strip().split('\n')
            finally:
                os.remove(file.name)  # Limpiar el archivo temporal
        else:
            # Si es texto directo
            text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
            text = text.strip()
            if not text:
                await wait_message.edit_text(
                    "Por favor, proporciona una lista de especies de alguna de estas formas:\n"
                    "1. Texto directo después del comando\n"
                    "2. Un archivo adjunto con la lista de especies\n"
                    "3. Opcionalmente puedes especificar un continente al inicio usando [Continente]\n\n"
                    "Ejemplo con texto:\n"
                    "/cargar_especies\n"
                    "Lasius niger\n"
                    "Formica rufa\n"
                )
                return
            lines = text.strip().split('\n')

        # Verificar si la primera línea contiene una región
        if lines and lines[0].strip().startswith('[') and lines[0].strip().endswith(']'):
            region = lines[0].strip()[1:-1].strip()
            lines = lines[1:]
            
            # Verificar si es un continente válido
            continentes_validos = {
                'Europa', 'Asia', 'África', 'América del Norte', 
                'América del Sur', 'Oceanía'
            }
            if region and region not in continentes_validos:
                await wait_message.edit_text(
                    f"❌ Continente no válido: {region}\n"
                    "Continentes válidos: Europa, Asia, África, América del Norte, América del Sur, Oceanía"
                )
                return

        # Limpiar y filtrar las líneas
        especies = []
        for line in lines:
            # Eliminar números de línea, caracteres especiales y espacios extra
            cleaned_line = re.sub(r'^\d+[.|)]\s*|\|\s*', '', line.strip())
            if cleaned_line and len(cleaned_line.split()) >= 2:
                especies.append(cleaned_line)

        if not especies:
            await wait_message.edit_text("❌ No se encontraron especies válidas en el archivo.")
            return

        # Procesar especies
        total = len(especies)
        procesadas = 0
        resultados = []
        
        for especie in especies:
            try:
                # Buscar la especie usando la misma lógica que /especie
                species_info = await buscar_especie_google(especie)
                
                if species_info:
                    result = db.find_species(species_info)
                    if result:
                        # Actualizar región si se proporcionó
                        if region:
                            db.update_species_region(result['scientific_name'], region)
                        resultados.append(f"✅ {result['scientific_name']}")
                        procesadas += 1
                    else:
                        resultados.append(f"❌ Error al guardar: {especie}")
                else:
                    resultados.append(f"❌ No encontrada: {especie}")
                
                # Actualizar mensaje de progreso cada 5 especies
                if len(resultados) % 5 == 0:
                    progress = f"🔄 Procesando... ({procesadas}/{total})\n"
                    if region:
                        progress += f"🌍 Región: {region}\n"
                    progress += "\n"
                    progress += "\n".join(resultados[-10:])  # Mostrar solo los últimos 10 resultados
                    
                    try:
                        await wait_message.edit_text(progress)
                    except Exception:
                        # Si el mensaje es muy largo, enviar uno nuevo
                        await message.answer(progress)
                
                # Pequeña pausa para no sobrecargar las APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error procesando {especie}: {str(e)}")
                resultados.append(f"❌ Error: {especie}")
        
        # Mensaje final
        resumen = f"✅ Proceso completado ({procesadas}/{total})\n"
        if region:
            resumen += f"🌍 Región: {region}\n"
        resumen += "\nÚltimas especies procesadas:\n"
        resumen += "\n".join(resultados[-10:])  # Mostrar solo las últimas 10 especies
        
        await message.answer(resumen)
        await wait_message.delete()
        
    except Exception as e:
        logger.error(f"Error en carga masiva: {str(e)}")
        await message.answer("❌ Ocurrió un error durante la carga. Por favor, intenta de nuevo.")

async def obtener_vuelos_recientes(especie):
    """Obtiene vuelos recientes de una especie desde AntFlights"""
    try:
        parts = especie.split()
        if len(parts) < 2:
            return None
        
        genus = parts[0]
        species = ' '.join(parts[1:])
        
        session = await init_session()
        
        # Buscar por nombre científico completo primero
        url = f"{ANTFLIGHTS_API}/data.php?scientific_name={quote(especie)}"
        logger.info(f"Buscando vuelos para {especie} en {url}")
        
        async with session.get(url) as response:
            if response.status == 200:
                text = await response.text()
                
                try:
                    data = json.loads(text)
                    if data:
                        return data
                except json.JSONDecodeError:
                    logger.warning(f"Error al decodificar JSON de AntFlights para {especie}")
        
        # Si no hay resultados, buscar por ubicación
        locations = await obtener_distribucion_antmaps(especie)
        if locations:
            for location in locations[:3]:  # Intentar con las primeras 3 ubicaciones
                url = f"{ANTFLIGHTS_API}/index.php?ql={quote(location.strip().lower())}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Buscar vuelos para la especie en la ubicación
                        vuelos = []
                        for row in soup.select('table.table tr'):
                            cells = row.find_all('td')
                            if len(cells) >= 3:
                                nombre_cientifico = cells[0].get_text().strip()
                                if especie.lower() in nombre_cientifico.lower():
                                    fecha = cells[1].get_text().strip()
                                    ubicacion = cells[2].get_text().strip()
                                    vuelos.append({
                                        'fecha': fecha,
                                        'ubicacion': ubicacion
                                    })
                        
                        if vuelos:
                            return {
                                'vuelos': vuelos,
                                'location': location
                            }
        
        return None
    
    except Exception as e:
        logger.error(f"Error al obtener vuelos recientes: {str(e)}")
        return None

def obtener_region_por_coordenadas(lat, lon):
    """Determina la región geográfica basada en coordenadas."""
    for region, datos in REGIONES_GEOGRAFICAS.items():
        coord = datos['coordenadas']
        if (coord['min_lat'] <= lat <= coord['max_lat'] and 
            coord['min_lon'] <= lon <= coord['max_lon']):
            return region
    return "Desconocida"

async def obtener_especies_por_region(lat, lon, cursor):
    """Obtiene las especies que pueden encontrarse en una región específica"""
    region = obtener_region_por_coordenadas(lat, lon)
    if not region:
        return []
        
    # Consulta SQL para obtener especies de la región
    query = """
        SELECT DISTINCT s.scientific_name, s.region
        FROM species s
        WHERE s.region LIKE %s
        OR s.region LIKE %s
    """
    cursor.execute(query, (f"%{region}%", "%Mundial%"))
    return cursor.fetchall()

@dp.message(Command("prediccion"))
async def prediccion(message: types.Message):
    """Muestra los vuelos nupciales registrados y predicciones basadas en temporadas"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            message.from_user.id,
            message.from_user.username or message.from_user.first_name,
            'command',
            'prediccion',
            chat_id=message.chat.id
        )

        # Obtener la localidad del mensaje
        location = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        location = location.strip()
        
        if not location:
            await message.answer(
                "❌ Por favor, proporciona una localidad.\n"
                "Ejemplo: /prediccion Murcia"
            )
            return

        # Enviar mensaje de espera
        wait_message = await message.answer('🔍 Analizando condiciones y temporadas de vuelos nupciales...')
        
        try:
            # Obtener mes actual
            mes_actual = datetime.now().strftime("%B").lower()
            meses_es = {
                "january": "enero", "february": "febrero", "march": "marzo",
                "april": "abril", "may": "mayo", "june": "junio",
                "july": "julio", "august": "agosto", "september": "septiembre",
                "october": "octubre", "november": "noviembre", "december": "diciembre"
            }
            mes_actual_es = meses_es[mes_actual]
            
            # Organizar especies por temporada
            temporadas = {
                "Primavera": ["marzo", "abril", "mayo"],
                "Verano": ["junio", "julio", "agosto"],
                "Otoño": ["septiembre", "octubre", "noviembre"],
                "Invierno": ["diciembre", "enero", "febrero"]
            }
            
            # Determinar la temporada actual
            temporada_actual = next(
                (temp for temp, meses in temporadas.items() if mes_actual_es in meses),
                "Desconocida"
            )
            
            # Encontrar especies activas en esta temporada
            especies_activas = []
            for especie, datos in especies_vuelos.items():
                if any(mes in datos['meses_vuelo'] for mes in temporadas[temporada_actual]):
                    especies_activas.append({
                        'nombre': especie,
                        'datos': datos
                    })
            
            # Construir el mensaje con diseño mejorado
            mensaje = f"🌡️ Predicción de Vuelos Nupciales en {location}\n"
            mensaje += f"📅 {temporada_actual} - {mes_actual_es.capitalize()}\n\n"
            
            if especies_activas:
                mensaje += f"✨ Especies con posibilidad de vuelo esta temporada:\n\n"
                
                for especie in especies_activas:
                    datos = especie['datos']
                    prob_vuelo = "Alta" if mes_actual_es in datos['meses_vuelo'] else "Media"
                    
                    mensaje += f"🐜 {especie['nombre']}\n"
                    mensaje += f"├ 📊 Probabilidad: {prob_vuelo}\n"
                    mensaje += f"├ 🕒 Horario óptimo: {datos['horas_activas']}\n"
                    mensaje += f"├ 🌡️ Temperatura ideal: {datos['temperatura']['min']}-{datos['temperatura']['max']}°C\n"
                    mensaje += f"├ 💧 Humedad requerida: {datos['humedad']['min']}-{datos['humedad']['max']}%\n"
                    mensaje += f"├ 💨 Viento máximo: {datos['viento_max']} km/h\n"
                    mensaje += f"└ 📍 Distribución: {', '.join(datos['distribucion'])}\n\n"
            
            # Buscar registros recientes en AntFlights
            url = f"{ANTFLIGHTS_API}/index.php?ql={quote(location.strip().lower())}"
            response = requests.get(url, timeout=TIMEOUT)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                vuelos_recientes = []
                
                for elemento in soup.find_all('tr'):
                    texto = elemento.get_text(strip=True)
                    if not texto or 'rank' in texto.lower():
                        continue
                        
                    fecha_match = re.search(r'(\d{4}-\d{2}-\d{2})', texto)
                    if fecha_match:
                        fecha = datetime.strptime(fecha_match.group(1), '%Y-%m-%d')
                        if (datetime.now() - fecha).days <= 15:  # Últimos 15 días
                            especie_match = re.search(r'([A-Z][a-z]+\s+[a-z]+)', texto)
                            if especie_match:
                                vuelos_recientes.append({
                                    'especie': especie_match.group(1),
                                    'fecha': fecha.strftime('%d/%m/%Y')
                                })
                
                if vuelos_recientes:
                    mensaje += "📝 Últimos vuelos registrados:\n"
                    for vuelo in vuelos_recientes:
                        mensaje += f"• {vuelo['especie']} - {vuelo['fecha']}\n"
                    mensaje += "\n"
            
            # Añadir recomendaciones generales
            mensaje += "💡 Recomendaciones:\n"
            mensaje += "• Revisa el pronóstico del tiempo antes de salir\n"
            mensaje += "• Los vuelos suelen ocurrir después de lluvias\n"
            mensaje += "• Las condiciones pueden variar según la zona\n"
            mensaje += "• Consulta /proximos_vuelos para más detalles\n\n"
            mensaje += "⚠️ Datos basados en registros históricos y AntFlights.com"
            
            await wait_message.edit_text(mensaje)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la petición a AntFlights: {str(e)}")
            await wait_message.edit_text(
                "❌ Error al conectar con AntFlights.\n"
                "Por favor, intenta más tarde."
            )
        
    except Exception as e:
        logger.error(f"Error en predicción: {str(e)}")
        await message.answer("❌ Ocurrió un error al obtener la predicción. Por favor, intenta más tarde.")
@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    try:
        logger.info("Comando /test recibido")
        await message.answer("✅ El comando de prueba funciona correctamente.")
    except Exception as e:
        logger.error(f"Error en comando test: {e}")
        await message.answer(f"❌ Error: {str(e)}")
@dp.message(Command("debug_adivina"))
async def debug_adivina(message: types.Message):
    try:
        logger.info("Comando /debug_adivina recibido")
        await message.answer("🔍 Iniciando diagnóstico del comando adivina_especie...")
        
        # Paso 1: Verificar conexión a la base de datos
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                await message.answer("✅ Conexión a la base de datos: OK")
                
                # Verificar tabla species_difficulty
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT COUNT(*) FROM species_difficulty")
                    count = cursor.fetchone()[0]
                    await message.answer(f"✅ Tabla species_difficulty: {count} registros")
                except Exception as e:
                    await message.answer(f"❌ Error en tabla species_difficulty: {str(e)}")
                
                # Verificar tabla species
                try:
                    cursor.execute("SELECT COUNT(*) FROM species WHERE photo_url IS NOT NULL")
                    count = cursor.fetchone()[0]
                    await message.answer(f"✅ Especies con foto: {count} registros")
                    
                    # Obtener una especie aleatoria para prueba
                    cursor.execute("SELECT id, scientific_name, photo_url FROM species WHERE photo_url IS NOT NULL LIMIT 1")
                    especie = cursor.fetchone()
                    if especie:
                        species_id, name, photo = especie
                        await message.answer(f"🧪 Especie de prueba: {name}")
                    else:
                        await message.answer("⚠️ No se encontraron especies con fotos para probar")
                except Exception as e:
                    await message.answer(f"❌ Error al verificar especies: {str(e)}")
                
                conn.close()
            else:
                await message.answer("❌ No se pudo conectar a la base de datos")
        except Exception as e:
            await message.answer(f"❌ Error de conexión a BD: {str(e)}")
        
        # Paso 2: Probar envío de teclado inline
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🟢 Botón de prueba", callback_data="test_callback")
                ]
            ])
            
            await message.answer(
                "🧪 Probando teclado inline...",
                reply_markup=keyboard
            )
        except Exception as e:
            await message.answer(f"❌ Error en teclado inline: {str(e)}")
        
        # Paso 3: Probar el envío de una foto
        if 'photo' in locals():
            try:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption="🧪 Probando envío de foto...",
                    parse_mode=ParseMode.HTML
                )
                await message.answer("✅ Envío de foto: OK")
            except Exception as e:
                await message.answer(f"❌ Error al enviar foto: {str(e)}")
        
        # Conclusión
        await message.answer("🔍 Diagnóstico completado. Revisa los resultados para identificar posibles problemas.")
        
    except Exception as e:
        logger.error(f"Error en diagnóstico: {e}")
        await message.answer(f"❌ Error general: {str(e)}")
@dp.message(Command("adivina_test"))
async def adivina_test(message: types.Message):
    """Versión simplificada del comando adivina_especie para pruebas"""
    try:
        logger.info("Comando /adivina_test recibido")
        
        # Mostrar opciones de dificultad simplificadas
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Probar juego", callback_data="adivina_test:prueba")
            ]
        ])
        
        await message.answer(
            "🎮 <b>PRUEBA ADIVINA ESPECIE</b>\n\n"
            "Este es un mensaje de prueba para verificar si el comando funciona.",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error en comando adivina_test: {e}")
        await message.answer(f"❌ Error: {str(e)}")

@dp.callback_query(lambda c: c.data and c.data.startswith('adivina_test:'))
async def handle_adivina_test(callback_query: types.CallbackQuery):
    """Maneja la respuesta de prueba del juego"""
    try:
        logger.info(f"Callback adivina_test recibido: {callback_query.data}")
        await callback_query.answer("✅ Callback funciona correctamente")
        
        # Obtener una especie con foto para mostrar
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT id, scientific_name, photo_url
                FROM species
                WHERE photo_url IS NOT NULL
                LIMIT 1
            """)
            
            especie = cursor.fetchone()
            conn.close()
            
            if especie:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Volver a probar", callback_data="adivina_test:prueba")]
                ])
                
                await bot.send_photo(
                    chat_id=callback_query.message.chat.id,
                    photo=especie['photo_url'],
                    caption=f"🎮 <b>PRUEBA DE FOTO</b>\n\n"
                            f"Especie: {especie['scientific_name']}\n\n"
                            f"Si puedes ver esta foto, significa que el bot puede enviar imágenes correctamente.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
                
                # Borrar mensaje anterior
                await callback_query.message.delete()
            else:
                await callback_query.message.edit_text(
                    "❌ No se encontraron especies con fotos para probar",
                    reply_markup=None
                )
        except Exception as e:
            logger.error(f"Error al obtener especie: {e}")
            await callback_query.message.edit_text(
                f"❌ Error al obtener especie: {str(e)}",
                reply_markup=None
            )
        
    except Exception as e:
        logger.error(f"Error en callback adivina_test: {e}")
        try:
            await callback_query.message.edit_text(f"❌ Error: {str(e)}")
        except:
            pass
@dp.message(Command("adivina_especie", "adivina_especie@AntmasterBot"))
async def adivina_especie(message: types.Message):
    """Inicia el juego de adivinar especies de hormigas"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        # Obtener el message_thread_id para grupos con hilos
        message_thread_id = getattr(message, 'message_thread_id', None)
        
        logger.info(f"Comando /adivina_especie recibido de {user_id} en chat {chat_id} (thread: {message_thread_id})")

        # Limitar a 3 intentos cada 24h
        if hasattr(db, 'can_play_guessing_game') and not db.can_play_guessing_game(user_id, chat_id):
            # Obtener la hora exacta en la que podrá jugar de nuevo
            next_time = db.get_next_game_time(user_id, chat_id) if hasattr(db, 'get_next_game_time') else None
            
            if next_time:
                message_text = f"Ya has jugado 3 veces en las últimas 24 horas. Podrás jugar de nuevo a las {next_time}."
            else:
                message_text = "Ya has jugado 3 veces en las últimas 24 horas. ¡Vuelve mañana!"
            
            await message.delete()
            # Enviar respuesta en el mismo hilo
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                message_thread_id=message_thread_id
            )
            return

        # No registrar intento aquí, se registrará cuando el usuario responda
        # Borrar el mensaje del usuario para no saturar el chat
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"No se pudo borrar el mensaje del usuario: {e}")

        await adivina_especie_directo(message)
    except Exception as e:
        logger.error(f"Error en comando adivina_especie: {str(e)}")
        # Enviar error en el mismo hilo
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"❌ Error al iniciar el juego: {str(e)}",
            message_thread_id=getattr(message, 'message_thread_id', None)
        )

async def adivina_especie_directo(message):
    chat_id = message.chat.id
    # Obtener el message_thread_id para grupos con hilos
    message_thread_id = getattr(message, 'message_thread_id', None)
    
    logger.info(f"Iniciando juego directo en chat {chat_id} (thread: {message_thread_id})")
    
    wait_message = await bot.send_message(
        chat_id=chat_id,
        text="🔍 Buscando especies para el juego...",
        message_thread_id=message_thread_id
    )

    # Obtener especies con foto
    def is_valid_photo_url(url):
        return url and url.startswith("http")

    especies = [e for e in db.get_all_species() if is_valid_photo_url(e.get('photo_url'))]
    if len(especies) < 3:
        await wait_message.edit_text("❌ No hay suficientes especies con fotos para jugar.")
        return

    especie_correcta = random.choice(especies)
    opciones = [especie_correcta]
    while len(opciones) < 4:
        candidata = random.choice(especies)
        if candidata not in opciones:
            opciones.append(candidata)
    random.shuffle(opciones)

    jugador_id = message.from_user.id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=op['scientific_name'],
            callback_data=f"adivina:{op['id']}:{especie_correcta['id']}:{jugador_id}:{message_thread_id or 'none'}"
        )] for op in opciones
    ])

    await wait_message.delete()
    await bot.send_photo(
        chat_id=chat_id,
        photo=especie_correcta['photo_url'],
        caption="🎮 <b>¡ADIVINA LA ESPECIE!</b> 🔍\n\n"
                "¿Qué especie de hormiga muestra la imagen?\n"
                "Selecciona la respuesta correcta:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        message_thread_id=message_thread_id
    )

@dp.callback_query(lambda c: c.data and c.data.startswith('adivina:'))
async def handle_respuesta(callback_query: types.CallbackQuery):
    try:
        partes = callback_query.data.split(':')
        id_seleccionado = int(partes[1])
        id_correcto = int(partes[2])
        jugador_id = int(partes[3]) if len(partes) > 3 else None
        thread_id = partes[4] if len(partes) > 4 and partes[4] != 'none' else None
        
        user_id = callback_query.from_user.id
        username = callback_query.from_user.username or callback_query.from_user.first_name
        chat_id = callback_query.message.chat.id

        logger.info(f"Respuesta recibida - Usuario: {user_id}, Seleccionado: {id_seleccionado}, Correcto: {id_correcto}, Thread: {thread_id}")

        # Solo permite responder al usuario que inició el juego
        if jugador_id is not None and user_id != jugador_id:
            await callback_query.answer("Solo el usuario que inició el juego puede responder a este juego.", show_alert=True)
            return

        # Verificar si el usuario puede seguir jugando antes de procesar la respuesta
        if hasattr(db, 'can_play_guessing_game') and not db.can_play_guessing_game(user_id, chat_id):
            next_time = db.get_next_game_time(user_id, chat_id) if hasattr(db, 'get_next_game_time') else None
            
            if next_time:
                message_text = f"Ya has jugado 3 veces en las últimas 24 horas. Podrás jugar de nuevo a las {next_time}."
            else:
                message_text = "Ya has jugado 3 veces en las últimas 24 horas. ¡Vuelve mañana!"
                
            await callback_query.answer(message_text, show_alert=True)
            await callback_query.message.delete()
            return

        es_correcta = (id_seleccionado == id_correcto)
        especie = db.get_species_by_id(id_correcto)
        nombre_correcto = especie['scientific_name'] if especie else "Especie desconocida"

        # Registrar el intento independientemente del resultado
        if hasattr(db, 'register_game_attempt'):
            await db.register_game_attempt(user_id, chat_id, id_correcto, is_correct=es_correcta)

        if es_correcta:
            logger.info(f"Respuesta CORRECTA - Otorgando 10 XP a usuario {user_id} ({username})")
            
            # Otorgar 10 XP reales por acierto
            if hasattr(db, 'log_user_interaction'):
                xp_result = await db.log_user_interaction(
                    user_id=user_id,
                    username=username,
                    interaction_type='game_guess',
                    command_name='adivina_especie',
                    points=10,
                    chat_id=chat_id
                )
                logger.info(f"Resultado de otorgar XP: {xp_result}")
            else:
                logger.error("Método log_user_interaction no disponible en db")
                
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Jugar de nuevo", callback_data=f"adivina_nuevo:{thread_id or 'none'}")]
            ])
            await callback_query.message.edit_caption(
                caption=f"✅ <b>¡CORRECTO!</b>\n\n"
                        f"La especie es <i>{nombre_correcto}</i>\n\n"
                        f"🏆 Has ganado <b>10 XP</b>\n\n"
                        f"¿Quieres jugar de nuevo?",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await callback_query.answer("¡Respuesta correcta! +10 XP", show_alert=True)
        else:
            logger.info(f"Respuesta INCORRECTA - Usuario {user_id} ({username})")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Intentar de nuevo", callback_data=f"adivina_nuevo:{thread_id or 'none'}")]
            ])
            await callback_query.message.edit_caption(
                caption=f"❌ <b>INCORRECTO</b>\n\n"
                        f"La especie correcta es <i>{nombre_correcto}</i>\n\n"
                        f"¿Quieres intentarlo de nuevo?",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await callback_query.answer("Respuesta incorrecta. Prueba de nuevo.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in handle_respuesta: {e}")
        await callback_query.answer("Error al procesar tu respuesta", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("adivina_nuevo"))
async def reiniciar_juego(callback_query: types.CallbackQuery):
    try:
        user_id = callback_query.from_user.id
        chat_id = callback_query.message.chat.id
        
        # Extraer thread_id del callback_data
        partes = callback_query.data.split(':')
        thread_id = partes[1] if len(partes) > 1 and partes[1] != 'none' else None
        
        logger.info(f"Reiniciando juego - Usuario: {user_id}, Chat: {chat_id}, Thread: {thread_id}")
        
        # Verificar límite de juegos diarios
        if hasattr(db, 'can_play_guessing_game') and not db.can_play_guessing_game(user_id, chat_id):
            # Obtener la hora exacta en la que podrá jugar de nuevo
            next_time = db.get_next_game_time(user_id, chat_id) if hasattr(db, 'get_next_game_time') else None
            
            if next_time:
                message_text = f"Ya has jugado 3 veces en las últimas 24 horas. Podrás jugar de nuevo a las {next_time}."
            else:
                message_text = "Ya has jugado 3 veces en las últimas 24 horas. ¡Vuelve mañana!"
                
            await callback_query.answer(message_text, show_alert=True)
            await callback_query.message.delete()
            return
            
        await callback_query.answer()
        await callback_query.message.delete()
        
        # Crear un objeto tipo message simulado para mantener compatibilidad
        class FakeMessage:
            def __init__(self, chat_id, from_user, message_thread_id=None):
                self.chat = type('obj', (), {'id': chat_id})()
                self.from_user = from_user
                self.message_thread_id = message_thread_id
                
        fake_message = FakeMessage(chat_id, callback_query.from_user, thread_id)
        await adivina_especie_directo(fake_message)
    except Exception as e:
        logger.error(f"Error al reiniciar juego: {str(e)}")
        await callback_query.answer("Error al reiniciar el juego", show_alert=True)
@dp.callback_query(lambda c: c.data == "test_callback")
async def handle_test_callback(callback_query: types.CallbackQuery):
    """Manejador para el botón de prueba"""
    try:
        logger.info("Callback test_callback recibido")
        await callback_query.answer("✅ Los callbacks funcionan correctamente")
        await callback_query.message.edit_text("✅ Prueba de callback exitosa")
    except Exception as e:
        logger.error(f"Error en test callback: {e}")

@dp.message(Command("proximos_vuelos"))
async def proximos_vuelos(message: types.Message):
    """Muestra información sobre los próximos vuelos nupciales por especie"""
    try:
        mes_actual = datetime.now().strftime("%B").lower()
        meses_es = {
            "january": "enero", "february": "febrero", "march": "marzo",
            "april": "abril", "may": "mayo", "june": "junio",
            "july": "julio", "august": "agosto", "september": "septiembre",
            "october": "octubre", "november": "noviembre", "december": "diciembre"
        }
        mes_actual = meses_es[mes_actual]
        
        mensaje = "📅 Próximos vuelos nupciales:\n\n"
        
        especies_activas = []
        for especie, datos in especies_vuelos.items():
            if mes_actual in datos['meses_vuelo']:
                especies_activas.append({
                    'nombre': especie,
                    'datos': datos
                })
        
        if especies_activas:
            mensaje += "🐜 Especies activas este mes:\n\n"
            for especie in especies_activas:
                mensaje += f"• {especie['nombre']}\n"
                mensaje += f"  📍 Distribución: {', '.join(especie['datos']['distribucion'])}\n"
                mensaje += f"  🕒 Horario: {especie['datos']['horas_activas']}\n"
                mensaje += f"  🌡️ Temperatura: {especie['datos']['temperatura']['min']}-{especie['datos']['temperatura']['max']}°C\n"
                mensaje += f"  💧 Humedad: {especie['datos']['humedad']['min']}-{especie['datos']['humedad']['max']}%\n"
                mensaje += f"  💨 Viento máximo: {especie['datos']['viento_max']} km/h\n\n"
        else:
            mensaje += "❌ No hay especies con vuelos nupciales programados para este mes."
        
        await message.answer(mensaje)
        
    except Exception as e:
        logger.error(f"Error en próximos vuelos: {str(e)}")
        await message.answer("❌ Ocurrió un error al obtener la información. Por favor, intenta más tarde.")

@dp.message(Command("actualizar_regiones"))
async def actualizar_regiones(message: types.Message):
    """Actualiza las regiones de todas las especies en la base de datos"""
    try:
        wait_message = await message.answer('🔄 Actualizando regiones de especies, esto puede tomar varios minutos...')
        
        # Usar la nueva función de actualización masiva
        resultados = db.update_all_regions()
        
        mensaje = f"✅ Actualización completada:\n\n"
        mensaje += f"📊 Especies procesadas: {resultados['total']}\n"
        mensaje += f"✨ Actualizadas correctamente: {resultados['updated']}\n"
        mensaje += f"❌ Errores: {resultados['errors']}"
        
        await wait_message.edit_text(mensaje)
        
    except Exception as e:
        logger.error(f"Error en actualización de regiones: {str(e)}")
        await message.answer("❌ Ocurrió un error al actualizar las regiones. Por favor, intenta más tarde.")

async def cargar_especies_desde_archivo(filename, region=None):
    """Carga especies desde un archivo local y busca información adicional"""
    try:
        logger.info(f"Iniciando carga desde archivo: {filename}")
        
        # Leer el archivo
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
        except UnicodeDecodeError:
            with open(filename, 'r', encoding='latin-1') as f:
                content = f.read()
                lines = content.strip().split('\n')
        
        # Verificar si la primera línea contiene una región
        if lines and lines[0].strip().startswith('[') and lines[0].strip().endswith(']'):
            region = lines[0].strip()[1:-1].strip()
            lines = lines[1:]
            
            # Verificar si es un continente válido
            continentes_validos = {
                'Europa', 'Asia', 'África', 'América del Norte', 
                'América del Sur', 'Oceanía'
            }
            if region and region not in continentes_validos:
                logger.error(f"Continente no válido: {region}")
                return False

        # Limpiar y filtrar las líneas
        especies = []
        for line in lines:
            # Eliminar números de línea, caracteres especiales y espacios extra
            cleaned_line = re.sub(r'^\d+[.|)]\s*|\|\s*', '', line.strip())
            if cleaned_line and len(cleaned_line.split()) >= 2:
                especies.append(cleaned_line)

        if not especies:
            logger.error("No se encontraron especies válidas en el archivo.")
            return False

        # Procesar especies
        total = len(especies)
        procesadas = 0
        errores = 0
        
        logger.info(f"Procesando {total} especies...")
        
        for especie in especies:
            try:
                # Separar especie y subespecie si existe
                partes = especie.split()
                if len(partes) < 2:
                    logger.error(f"Nombre inválido: {especie}")
                    errores += 1
                    continue
                    
                genus = partes[0]
                species = partes[1]
                subspecies = " ".join(partes[2:]) if len(partes) > 2 else None
                
                # Construir el nombre científico completo
                scientific_name = f"{genus} {species}"
                if subspecies:
                    scientific_name += f" {subspecies}"

                # Buscar información adicional
                logger.info(f"Buscando información adicional para: {scientific_name}")
                
                # Buscar en iNaturalist
                inat_result = await buscar_en_inaturalist(scientific_name)
                photo_url = None
                if inat_result and isinstance(inat_result, dict):
                    photo_url = inat_result.get('photo_url')
                    logger.info(f"Foto encontrada en iNaturalist para {scientific_name}")
                
                # Construir URL de AntWiki y verificar si existe
                antwiki_url = None
                try:
                    url = construir_url_antwiki(genus, species)
                    response = requests.head(url, timeout=10)
                    if response.status_code == 200:
                        antwiki_url = url
                        logger.info(f"Página de AntWiki encontrada para {scientific_name}")
                except Exception as e:
                    logger.warning(f"No se pudo verificar AntWiki para {scientific_name}: {str(e)}")
                
                # Guardar en la base de datos con toda la información
                try:
                    db.add_species(
                        scientific_name=scientific_name,
                        region=region,
                        antwiki_url=antwiki_url,
                        photo_url=photo_url,
                        inaturalist_id=inat_result.get('id') if inat_result else None
                    )
                    procesadas += 1
                except Exception as e:
                    logger.error(f"Error al guardar {scientific_name} en la base de datos: {str(e)}")
                    errores += 1
                    continue
                
                if procesadas % 10 == 0:
                    print(f"Progreso: {procesadas}/{total} especies procesadas")
                    logger.info(f"Progreso: {procesadas}/{total} especies procesadas")
                
                # Pequeña pausa para no sobrecargar las APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error procesando {especie}: {str(e)}")
                errores += 1
        
        logger.info(f"Proceso completado: {procesadas} especies procesadas, {errores} errores")
        return True
        
    except Exception as e:
        logger.error(f"Error en carga desde archivo: {str(e)}")
        return False

async def borrar_todas_especies():
    """Borra todas las especies de la base de datos"""
    try:
        logger.info("Iniciando borrado de todas las especies...")
        cursor = db.get_connection().cursor()
        
        # Borrar registros de la tabla search_stats primero (debido a la clave foránea)
        cursor.execute("DELETE FROM search_stats")
        
        # Borrar todas las especies
        cursor.execute("DELETE FROM species")
        
        # Hacer commit de los cambios
        db.get_connection().commit()
        
        # Obtener el número de filas afectadas
        cursor.execute("SELECT COUNT(*) FROM species")
        remaining = cursor.fetchone()[0]
        
        if remaining == 0:
            logger.info("Todas las especies han sido borradas exitosamente")
            return True
        else:
            logger.error(f"Quedaron {remaining} especies sin borrar")
            return False
            
    except Exception as e:
        logger.error(f"Error al borrar las especies: {str(e)}")
        return False

def construir_url_antwiki(genus, species):
    """Construye la URL de AntWiki con el formato correcto"""
    return f"{ANTWIKI_API}{genus}_{species}"

async def buscar_foto_antwiki(genus, species):
    """Busca información y fotos en AntWiki"""
    try:
        url = f"https://www.antwiki.org/wiki/{genus}_{species}"
        logger.info(f"Buscando información en AntWiki: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=TIMEOUT) as response:
                if response.status != 200:
                    logger.warning(f"Error al buscar en AntWiki: {response.status}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                info = {
                    'photo_url': None,
                    'description': None
                }
            
                # Buscar imágenes
                gallery = soup.find('div', class_='gallery')
                if gallery:
                    images = gallery.find_all('img')
                    if images:
                        info['photo_url'] = images[0].get('src')
                        if not info['photo_url'].startswith('http'):
                            info['photo_url'] = 'https://www.antwiki.org' + info['photo_url']
                
                # Buscar información básica
                content = soup.find('div', id='mw-content-text')
                if content:
                    paragraphs = content.find_all('p')
                    for p in paragraphs:
                        text = p.get_text().strip()
                        if text and len(text) > 50:  # Solo párrafos con contenido sustancial
                            info['description'] = text
                            break
                
                # Si no se encuentra información suficiente, retornar None
                if not info['photo_url'] and not info['description']:
                    logger.warning(f"No se encontró información en AntWiki para {genus} {species}")
                    return None

                logger.info(f"Información obtenida de AntWiki para {genus} {species}")
                return info
                    
    except Exception as e:
        logger.error(f"Error al buscar información en AntWiki: {str(e)}")
        return None

async def buscar_info_antontop(species_name):
    """Busca información de la especie en AntOnTop."""
    try:
        logger.info(f"Buscando en AntOnTop: {species_name}")
        
        # Normalizar el nombre científico para la URL (convertir espacios a guiones)
        species_url_name = species_name.lower().replace(' ', '-')
        url = f"https://antontop.com/es/{species_url_name}/"
        logger.info(f"URL de búsqueda en AntOnTop: {url}")
        
        session = await init_session()
        
        # Realizar la solicitud con un timeout adecuado
        async with session.get(url, timeout=TIMEOUT) as response:
            if response.status != 200:
                logger.warning(f"Error al buscar en AntOnTop: {response.status}")
                # Intentar con URL sin el prefijo "es" como respaldo
                url_alt = f"https://antontop.com/{species_url_name}/"
                logger.info(f"Intentando URL alternativa: {url_alt}")
                
                async with session.get(url_alt, timeout=TIMEOUT) as alt_response:
                    if alt_response.status != 200:
                        logger.warning(f"Error al buscar en URL alternativa: {alt_response.status}")
                        return None
                    
                    html = await alt_response.text()
            else:
                html = await response.text()
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraer datos relevantes
            info = {
                'photo_url': None,
                'short_description': None, 
                'description': None,
                'region': None,
                'behavior': None,
                'difficulty': None,
                'temperature': None,
                'humidity': None,
                'queen_size': None,
                'worker_size': None,
                'colony_size': None
            }
            
            # Extraer la imagen principal
            main_image = soup.find('img', {'class': 'wp-post-image'})
            if main_image and main_image.get('src'):
                info['photo_url'] = main_image.get('src')
            
            # Buscar la descripción corta
            short_desc_div = soup.find('div', {'class': 'woocommerce-product-details__short-description'})
            if short_desc_div:
                p_tag = short_desc_div.find('p')
                if p_tag:
                    info['short_description'] = p_tag.get_text().strip()
            
            # Buscar la descripción completa
            description_section = soup.find('div', {'class': 'woocommerce-Tabs-panel--description'})
            if description_section:
                info['description'] = description_section.get_text().strip()
            
            # Extraer detalles de la tabla de características
            product_details = soup.find('h4', string='Detalles de producto')
            if not product_details:
                product_details = soup.find('h4', string='Product details')
            
            if product_details:
                details_table = product_details.find_next('table')
                if details_table:
                    for row in details_table.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].get_text().strip().lower()
                            value = cells[1].get_text().strip()
                            
                            if 'dificultad' in key or 'difficulty' in key:
                                info['difficulty'] = value
                            elif 'comportamiento' in key or 'behavior' in key:
                                info['behavior'] = value
                            elif 'origen' in key or 'origin' in key:
                                info['region'] = value
            
            # Si no se encuentra información suficiente, retornar None
            if not info['short_description'] and not info['description']:
                logger.warning(f"No se encontró descripción en AntOnTop para {species_name}")
                return None

            logger.info(f"Información obtenida de AntOnTop para {species_name}")
            return info

    except Exception as e:
        logger.error(f"Error al buscar en AntOnTop: {str(e)}")
        return None

@dp.message(Command("reset_db"))
async def reset_database(message: types.Message):
    """Reinicia las tablas de la base de datos"""
    try:
        wait_message = await message.answer('🔄 Reiniciando base de datos...')
        if db.reset_tables():
            await wait_message.edit_text('✅ Base de datos reiniciada correctamente')
        else:
            await wait_message.edit_text('❌ Error al reiniciar la base de datos')
    except Exception as e:
        logger.error(f"Error al reiniciar base de datos: {str(e)}")
        await message.answer('❌ Error al reiniciar la base de datos')

async def obtener_distribucion_antmaps(scientific_name):
    """Obtiene la distribución geográfica de una especie desde AntMaps"""
    try:
        # Formatear el nombre científico para la búsqueda
        genus, species = scientific_name.split(' ')[:2]
        search_name = f"{genus}.{species}"
        
        # Construir la URL de la API
        url = f"{ANTMAPS_API}/species/{search_name}"
        
        response = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: requests.get(url, timeout=TIMEOUT)
        )
        
        if response.status_code == 200:
            data = response.json()
            if data and 'records' in data:
                regiones = set()
                for record in data['records']:
                    if 'region' in record:
                        regiones.add(record['region'])
                return list(regiones)
        return []
        
    except Exception as e:
        logger.error(f"Error al obtener distribución de AntMaps: {str(e)}")
        return []

async def obtener_mapa_distribucion(scientific_name):
    """Obtiene la URL del mapa de distribución de AntMaps"""
    try:
        genus, species = scientific_name.split(' ')[:2]
        return f"https://antmaps.org/?mode=species&species={genus}.{species}"
    except Exception as e:
        logger.error(f"Error al generar URL de mapa: {str(e)}")
        return None

async def obtener_estadisticas_antflights(genus):
    """Obtiene las estadísticas de vuelos nupciales desde AntFlights para un género"""
    try:
        # URLs base para las diferentes estadísticas
        urls = {
            'month': f"{ANTFLIGHTS_API}/stats/flights/{genus}#byMonth",
            'hour': f"{ANTFLIGHTS_API}/stats/flights/{genus}#byHours",
            'temperature': f"{ANTFLIGHTS_API}/stats/flights/{genus}#byTemperatureC",
            'moon': f"{ANTFLIGHTS_API}/stats/flights/{genus}#byMoon"
        }
        
        stats = {}
        session = requests.Session()
        
        for stat_type, url in urls.items():
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.get(url, timeout=TIMEOUT)
                )
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Buscar el elemento que contiene los datos del gráfico
                    script_tags = soup.find_all('script')
                    for script in script_tags:
                        if script.string and 'data:' in script.string:
                            # Extraer los datos del gráfico
                            data_start = script.string.find('data:')
                            if data_start != -1:
                                data_text = script.string[data_start:]
                                # Encontrar los corchetes que contienen los datos
                                bracket_start = data_text.find('[')
                                bracket_end = data_text.find(']', bracket_start)
                                if bracket_start != -1 and bracket_end != -1:
                                    data_json = data_text[bracket_start:bracket_end + 1]
                                    try:
                                        data = json.loads(data_json)
                                        stats[stat_type] = data
                                    except json.JSONDecodeError:
                                        logger.error(f"Error al decodificar JSON para {stat_type}")
                                        continue
            
            except Exception as e:
                logger.error(f"Error al obtener estadísticas de {stat_type}: {str(e)}")
                continue
        
        return stats
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de AntFlights: {str(e)}")
        return None

async def actualizar_estadisticas_vuelos(genus):
    """Actualiza las estadísticas de vuelos nupciales en la base de datos"""
    try:
        # Obtener el ID de la especie
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("SELECT id FROM species WHERE scientific_name LIKE %s", (f"{genus}%",))
        species = cursor.fetchall()
        
        if not species:
            logger.error(f"No se encontraron especies para el género {genus}")
            return False
        
        # Obtener estadísticas de AntFlights
        stats = await obtener_estadisticas_antflights(genus)
        if not stats:
            logger.error(f"No se pudieron obtener estadísticas para {genus}")
            return False
        
        # Procesar y guardar estadísticas para cada especie
        for specie in species:
            species_id = specie['id']
            
            # Procesar estadísticas por mes
            if 'month' in stats:
                for month_data in stats['month']:
                    month = month_data.get('month')
                    count = month_data.get('count', 0)
                    hemisphere = month_data.get('hemisphere', 'World')
                    if month is not None:
                        db.add_flight_stats(species_id, 'month', month, count, hemisphere)
            
            # Procesar estadísticas por hora
            if 'hour' in stats:
                for hour_data in stats['hour']:
                    hour = hour_data.get('hour')
                    count = hour_data.get('count', 0)
                    if hour is not None:
                        db.add_flight_stats(species_id, 'hour', hour, count)
            
            # Procesar estadísticas por temperatura
            if 'temperature' in stats:
                for temp_data in stats['temperature']:
                    temp = temp_data.get('temperature')
                    count = temp_data.get('count', 0)
                    if temp is not None:
                        db.add_flight_stats(species_id, 'temperature', temp, count)
            
            # Procesar estadísticas por fase lunar
            if 'moon' in stats:
                for moon_data in stats['moon']:
                    phase = moon_data.get('phase')
                    count = moon_data.get('count', 0)
                    if phase is not None:
                        db.add_flight_stats(species_id, 'moon', phase, count)
        
        return True
        
    except Exception as e:
        logger.error(f"Error al actualizar estadísticas de vuelos: {str(e)}")
        return False

@dp.message(Command("actualizar_estadisticas"))
async def actualizar_estadisticas(message: types.Message):
    # Registrar interacción
    await db.log_user_interaction(
        message.from_user.id,
        message.from_user.username or message.from_user.first_name,
        'command',
        'actualizar_estadisticas'
    )
    """Actualiza las estadísticas de vuelos nupciales para un género o todos los géneros"""
    try:
        genus = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
        genus = genus.strip()
        wait_message = await message.answer('🔄 Actualizando estadísticas de vuelos nupciales...')
        
        if genus:
            # Actualizar un género específico
            success = await actualizar_estadisticas_vuelos(genus)
            if success:
                await wait_message.edit_text(f"✅ Estadísticas actualizadas para el género {genus}")
            else:
                await wait_message.edit_text(f"❌ Error al actualizar estadísticas para {genus}")
        else:
            # Actualizar todos los géneros
            cursor = db.get_connection().cursor(dictionary=True)
            cursor.execute("SELECT DISTINCT SUBSTRING_INDEX(scientific_name, ' ', 1) as genus FROM species")
            genera = cursor.fetchall()
            
            total = len(genera)
            actualizados = 0
            errores = []
            
            for i, row in enumerate(genera, 1):
                genus = row['genus']
                try:
                    success = await actualizar_estadisticas_vuelos(genus)
                    if success:
                        actualizados += 1
                    else:
                        errores.append(genus)
                    
                    # Actualizar mensaje de progreso cada 5 géneros
                    if i % 5 == 0:
                        await wait_message.edit_text(
                            f"🔄 Actualizando estadísticas... ({i}/{total})\n"
                            f"✅ Actualizados: {actualizados}\n"
                            f"❌ Errores: {len(errores)}"
                        )
                except Exception as e:
                    logger.error(f"Error al actualizar {genus}: {str(e)}")
                    errores.append(genus)
            
            # Mensaje final
            mensaje = f"✅ Actualización completada:\n\n"
            mensaje += f"📊 Géneros procesados: {total}\n"
            mensaje += f"✨ Actualizados correctamente: {actualizados}\n"
            if errores:
                mensaje += f"❌ Errores ({len(errores)}):\n"
                mensaje += "\n".join(f"• {genus}" for genus in errores[:5])
                if len(errores) > 5:
                    mensaje += f"\n... y {len(errores) - 5} más"
            
            await wait_message.edit_text(mensaje)
            
    except Exception as e:
        logger.error(f"Error al actualizar estadísticas: {str(e)}")
        await message.answer("❌ Ocurrió un error al actualizar las estadísticas. Por favor, intenta más tarde.")

@dp.message(Command("actualizar_todo"))
async def actualizar_todo(message: types.Message):
    """Actualiza todos los datos: estadísticas de vuelos y regiones"""
    try:
        wait_message = await message.answer('🔄 Iniciando actualización completa de datos...')
        
        # 1. Actualizar regiones
        await wait_message.edit_text('🌍 Actualizando regiones de especies...')
        resultados_regiones = db.update_all_regions()
        
        # 2. Actualizar estadísticas de vuelos
        await wait_message.edit_text('📊 Actualizando estadísticas de vuelos nupciales...')
        
        # Obtener todos los géneros
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT SUBSTRING_INDEX(scientific_name, ' ', 1) as genus FROM species")
        genera = cursor.fetchall()
        
        total_genera = len(genera)
        actualizados = 0
        errores = []
        
        for i, row in enumerate(genera, 1):
            genus = row['genus']
            try:
                success = await actualizar_estadisticas_vuelos(genus)
                if success:
                    actualizados += 1
                else:
                    errores.append(genus)
                
                # Actualizar mensaje de progreso cada 3 géneros
                if i % 3 == 0:
                    await wait_message.edit_text(
                        f"📊 Actualizando estadísticas... ({i}/{total_genera})\n"
                        f"✅ Actualizados: {actualizados}\n"
                        f"❌ Errores: {len(errores)}"
                    )
            except Exception as e:
                logger.error(f"Error al actualizar {genus}: {str(e)}")
                errores.append(genus)
        
        # Mensaje final con resumen
        mensaje = "✅ Actualización completa finalizada\n\n"
        mensaje += "🌍 Actualización de regiones:\n"
        mensaje += f"• Total procesadas: {resultados_regiones['total']}\n"
        mensaje += f"• Actualizadas: {resultados_regiones['updated']}\n"
        mensaje += f"• Errores: {resultados_regiones['errors']}\n\n"
        
        mensaje += "📊 Actualización de estadísticas:\n"
        mensaje += f"• Géneros procesados: {total_genera}\n"
        mensaje += f"• Actualizados: {actualizados}\n"
        if errores:
            mensaje += f"• Errores ({len(errores)}):\n"
            mensaje += "\n".join(f"  - {genus}" for genus in errores[:5])
            if len(errores) > 5:
                mensaje += f"\n  ... y {len(errores) - 5} más"
        
        await wait_message.edit_text(mensaje)
        
    except Exception as e:
        logger.error(f"Error en actualización completa: {str(e)}")
        await message.answer("❌ Ocurrió un error durante la actualización. Por favor, intenta más tarde.")

@dp.message(Command("ranking_semanal"))
async def ranking_semanal(message: types.Message):
    """Muestra el ranking de usuarios más activos de la semana"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            message.from_user.id,
            message.from_user.username or message.from_user.first_name,
            'command',
            'ranking_semanal',
            chat_id=message.chat.id
        )
        
        # Obtener el ranking semanal usando solo la tabla user_experience
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                user_id,
                username,
                total_xp,
                current_level
            FROM user_experience
            WHERE chat_id = %s
            AND updated_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY total_xp DESC
            LIMIT 10
        """, (message.chat.id,))
        
        ranking = cursor.fetchall()
        
        if not ranking:
            await message.answer("📊 No hay suficientes datos para mostrar el ranking semanal en este chat.")
            return
            
        # Construir mensaje del ranking
        mensaje = "🏆 Ranking Semanal de este Chat:\n\n"
        for i, user in enumerate(ranking, 1):
            mensaje += (
                f"{i}. {user['username']}\n"
                f"   Nivel: {user['current_level']} | XP: {user['total_xp']}\n\n"
            )
            
        await message.answer(mensaje)
        
    except Exception as e:
        logger.error(f"Error al mostrar ranking semanal del chat: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al obtener el ranking semanal.")
    finally:
        if cursor:
            cursor.close()

@dp.message(Command("ranking_mensual"))
async def ranking_mensual(message: types.Message):
    """Muestra el ranking de usuarios más activos del mes"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            message.from_user.id,
            message.from_user.username or message.from_user.first_name,
            'command',
            'ranking_mensual',
            chat_id=message.chat.id
        )
        
        # Obtener el ranking mensual usando solo la tabla user_experience
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                user_id,
                username,
                total_xp,
                current_level
            FROM user_experience
            WHERE chat_id = %s
            AND updated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY total_xp DESC
            LIMIT 10
        """, (message.chat.id,))
        
        ranking = cursor.fetchall()
        
        if not ranking:
            await message.answer("📊 No hay suficientes datos para mostrar el ranking mensual en este chat.")
            return
            
        # Construir mensaje del ranking
        mensaje = "🏆 Ranking Mensual de este Chat:\n\n"
        for i, user in enumerate(ranking, 1):
            mensaje += (
                f"{i}. {user['username']}\n"
                f"   Nivel: {user['current_level']} | XP: {user['total_xp']}\n\n"
            )
            
        await message.answer(mensaje)
        
    except Exception as e:
        logger.error(f"Error al mostrar ranking mensual del chat: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al obtener el ranking mensual.")
    finally:
        if cursor:
            cursor.close()

@dp.message(lambda message: message.photo is not None)
async def handle_photo(message: types.Message):
    """Maneja mensajes con fotos"""
    try:
        # Log para depuración
        logger.info(f"Foto recibida del usuario {message.from_user.username or message.from_user.first_name}")
        
        # Verificar si es spam antes de procesar
        if db.is_spam(message.from_user.id, 'photo', message.chat.id):
            logger.warning(f"Spam de fotos detectado del usuario {message.from_user.username or message.from_user.first_name} en el chat {message.chat.id}")
            # Notificar y aplicar medidas anti-spam
            await notify_spam_detected(message)
            return
            
        # Registrar interacción básica (sin puntos)
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='photo',
            command_name=None,
            chat_id=message.chat.id
        )
        
        # Registrar como foto pendiente de aprobación
        if db.register_pending_photo(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            message_id=message.message_id,
            chat_id=message.chat.id
        ):
            # Enviar notificación privada al usuario
            try:
                await bot.send_message(
                    chat_id=message.from_user.id,
                    text="📸 Tu foto ha sido registrada y está pendiente de aprobación. "
                         "Recibirás XP cuando un administrador la apruebe."
                )
            except Exception as e:
                logger.error(f"Error al enviar mensaje privado: {str(e)}")
                # Si falla el mensaje privado, enviar en el grupo
                await message.reply(
                    "📸 Tu foto ha sido registrada y está pendiente de aprobación. "
                    "Recibirás XP cuando un administrador la apruebe."
                )
            logger.info(f"Foto de {message.from_user.username or message.from_user.first_name} registrada como pendiente de aprobación")
        
    except Exception as e:
        logger.error(f"Error al registrar interacción de foto: {str(e)}")

@dp.message(lambda message: message.video is not None)
async def handle_video(message: types.Message):
    """Maneja mensajes con videos"""
    try:
        # Log para depuración
        logger.info(f"Video recibido del usuario {message.from_user.username or message.from_user.first_name}")
        
        # Verificar si es spam antes de procesar
        if db.is_spam(message.from_user.id, 'video', message.chat.id):
            logger.warning(f"Spam de videos detectado del usuario {message.from_user.username or message.from_user.first_name} en el chat {message.chat.id}")
            # Notificar y aplicar medidas anti-spam
            await notify_spam_detected(message)
            return
            
        # Registrar interacción básica (sin puntos)
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='video',
            command_name=None,
            chat_id=message.chat.id
        )
        
        # Registrar como video pendiente de aprobación
        if db.register_pending_photo(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            message_id=message.message_id,
            chat_id=message.chat.id
        ):
            # Enviar notificación privada al usuario
            try:
                await bot.send_message(
                    chat_id=message.from_user.id,
                    text="🎥 Tu video ha sido registrado y está pendiente de aprobación. "
                         "Recibirás XP cuando un administrador lo apruebe."
                )
            except Exception as e:
                logger.error(f"Error al enviar mensaje privado: {str(e)}")
                # Si falla el mensaje privado, enviar en el grupo
                await message.reply(
                    "🎥 Tu video ha sido registrado y está pendiente de aprobación. "
                    "Recibirás XP cuando un administrador lo apruebe."
                )
            logger.info(f"Video de {message.from_user.username or message.from_user.first_name} registrado como pendiente de aprobación")
        
    except Exception as e:
        logger.error(f"Error al registrar interacción de video: {str(e)}")

@dp.message(lambda message: message.document is not None)
async def handle_document(message: types.Message):
    """Maneja mensajes con documentos"""
    try:
        # Determinar si es un video o un documento normal
        is_video = False
        if message.document.mime_type and message.document.mime_type.startswith('video/'):
            is_video = True
            interaction_type = 'video'
            logger.info(f"Documento de video recibido del usuario {message.from_user.username or message.from_user.first_name}")
        else:
            interaction_type = 'document'
            logger.info(f"Documento recibido del usuario {message.from_user.username or message.from_user.first_name}")
        
        # Verificar si es spam antes de procesar
        if db.is_spam(message.from_user.id, interaction_type, message.chat.id):
            logger.warning(f"Spam de documentos detectado del usuario {message.from_user.username or message.from_user.first_name} en el chat {message.chat.id}")
            # Notificar y aplicar medidas anti-spam
            await notify_spam_detected(message)
            return
            
        # Registrar interacción básica
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type=interaction_type,
            command_name=None,
            chat_id=message.chat.id
        )
        
        # Si es un video, registrarlo como pendiente de aprobación
        if is_video:
            if db.register_pending_photo(
                user_id=message.from_user.id,
                username=message.from_user.username or message.from_user.first_name,
                message_id=message.message_id,
                chat_id=message.chat.id
            ):
                # Enviar notificación privada al usuario
                try:
                    await bot.send_message(
                        chat_id=message.from_user.id,
                        text="🎥 Tu video ha sido registrado y está pendiente de aprobación. "
                             "Recibirás XP cuando un administrador lo apruebe."
                    )
                except Exception as e:
                    logger.error(f"Error al enviar mensaje privado: {str(e)}")
                    # Si falla el mensaje privado, enviar en el grupo
                    await message.reply(
                        "🎥 Tu video ha sido registrado y está pendiente de aprobación. "
                        "Recibirás XP cuando un administrador lo apruebe."
                    )
                logger.info(f"Video (documento) de {message.from_user.username or message.from_user.first_name} registrado como pendiente de aprobación")
        
    except Exception as e:
        logger.error(f"Error al registrar interacción de documento: {str(e)}")

@dp.message(lambda message: message.new_chat_members is not None)
async def handle_new_members(message: types.Message):
    """Gestiona la entrada de nuevos miembros al grupo."""
    try:
        chat_id = message.chat.id
        
        # No procesar si es un chat privado
        if message.chat.type == "private":
            return
            
        # Procesar cada nuevo miembro
        for new_member in message.new_chat_members:
            user_id = new_member.id
            username = new_member.username or new_member.first_name
            
            # No dar la bienvenida al propio bot
            if user_id == bot.id:
                logger.info(f"Bot añadido al chat {chat_id}")
                continue
                
            # Registrar interacción
            await db.log_user_interaction(
                user_id=user_id,
                username=username,
                interaction_type='join',
                chat_id=chat_id
            )
            
            # Enviar mensaje de bienvenida con captcha
            # Generar un captcha de suma simple
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
            resultado = num1 + num2
            
            # Crear botones para respuestas
            # Crear una respuesta correcta y dos incorrectas
            respuestas = [resultado, resultado + random.randint(1, 5), resultado - random.randint(1, 5)]
            if respuestas[1] == respuestas[0]:
                respuestas[1] += 1
            if respuestas[2] == respuestas[0] or respuestas[2] == respuestas[1]:
                respuestas[2] -= 1
            
            random.shuffle(respuestas)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text=str(respuestas[0]), callback_data=f"captcha:{user_id}:{respuestas[0]}:{resultado}"),
                    InlineKeyboardButton(text=str(respuestas[1]), callback_data=f"captcha:{user_id}:{respuestas[1]}:{resultado}"),
                    InlineKeyboardButton(text=str(respuestas[2]), callback_data=f"captcha:{user_id}:{respuestas[2]}:{resultado}")
                ]
            ])
            
            # Enviar mensaje de verificación
            mensaje_captcha = await message.answer(
                f"¡Bienvenido/a, @{username}! 👋\n\n"
                f"Para verificar que eres humano, por favor resuelve esta operación:\n"
                f"🧮 {num1} + {num2} = ?\n\n"
                f"Selecciona la respuesta correcta:",
                reply_markup=kb
            )
            
            # Guardar el ID del mensaje para poder borrarlo después
            db.set_temp_data(f"captcha_msg:{user_id}:{chat_id}", mensaje_captcha.message_id, expire=300)
            
            # Restricción temporal hasta verificación
            try:
                # Restringir envío de mensajes hasta resolver captcha
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=types.ChatPermissions(
                        can_send_messages=False,
                        can_send_media_messages=False,
                        can_send_other_messages=False
                    )
                )
                logger.info(f"Usuario {user_id} restringido temporalmente hasta verificación")
            except Exception as e:
                logger.error(f"No se pudo restringir al usuario {user_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error al procesar nuevo miembro: {str(e)}")

# Handler para el captcha
@dp.callback_query(lambda c: c.data and c.data.startswith('captcha:'))
async def handle_captcha(callback_query: types.CallbackQuery):
    """Procesa las respuestas del captcha"""
    try:
        # Extraer datos del callback
        parts = callback_query.data.split(':')
        target_user_id = int(parts[1])
        respuesta_seleccionada = int(parts[2])
        respuesta_correcta = int(parts[3])
        
        # Verificar que la persona que responde es el nuevo miembro
        if callback_query.from_user.id != target_user_id:
            await callback_query.answer("Este captcha no es para ti", show_alert=True)
            return
            
        # Verificar respuesta
        if respuesta_seleccionada == respuesta_correcta:
            # Respuesta correcta
            await callback_query.answer("✅ ¡Respuesta correcta! Bienvenido/a.", show_alert=True)
            
            # Restaurar permisos
            await bot.restrict_chat_member(
                chat_id=callback_query.message.chat.id,
                user_id=target_user_id,
                permissions=types.ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            
            # Editar el mensaje para quitar los botones
            await callback_query.message.edit_text(
                f"{callback_query.message.text.split('Por favor')[0]}\n\n✅ Verificación completada exitosamente.",
                reply_markup=None
            )
            
            # Dar puntos de experiencia por unirse al grupo
            db.add_experience(target_user_id, 10)
            
            # Eliminar datos temporales
            db.delete_temp_data(f"captcha_attempts:{target_user_id}")
            
        else:
            # Respuesta incorrecta
            # Obtener el número de intentos
            intentos_data = db.get_temp_data(f"captcha_attempts:{target_user_id}")
            intentos = 1
            if intentos_data:
                intentos = json.loads(intentos_data) + 1
            
            # Si ha fallado 3 veces, expulsar temporalmente
            if intentos >= 3:
                await callback_query.answer("❌ Has fallado demasiadas veces. Serás expulsado temporalmente.", show_alert=True)
                try:
                    # Expulsar al usuario
                    await bot.ban_chat_member(
                        chat_id=callback_query.message.chat.id,
                        user_id=target_user_id,
                        until_date=datetime.now() + timedelta(minutes=10)
                    )
                    await callback_query.message.edit_text(
                        f"{callback_query.message.text.split('Por favor')[0]}\n\n❌ Verificación fallida. Usuario expulsado temporalmente.",
                        reply_markup=None
                    )
                except Exception as e:
                    logger.error(f"Error al expulsar usuario: {e}")
                    
                # Eliminar datos temporales
                db.delete_temp_data(f"captcha_attempts:{target_user_id}")
            else:
                # Actualizar intentos
                db.set_temp_data(f"captcha_attempts:{target_user_id}", json.dumps(intentos), expiry=300)
                
                # Informar al usuario
                await callback_query.answer(f"❌ Respuesta incorrecta. Intentos restantes: {3-intentos}", show_alert=True)
                
                # Generar nuevo captcha
                num1 = random.randint(1, 10)
                num2 = random.randint(1, 10)
                resultado = num1 + num2
                
                respuestas = [resultado, resultado + random.randint(1, 5), resultado - random.randint(1, 5)]
                if respuestas[1] == respuestas[0]:
                    respuestas[1] += 1
                if respuestas[2] == respuestas[0] or respuestas[2] == respuestas[1]:
                    respuestas[2] -= 1
                
                random.shuffle(respuestas)
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text=str(respuestas[0]), callback_data=f"captcha:{target_user_id}:{respuestas[0]}:{resultado}"),
                        InlineKeyboardButton(text=str(respuestas[1]), callback_data=f"captcha:{target_user_id}:{respuestas[1]}:{resultado}"),
                        InlineKeyboardButton(text=str(respuestas[2]), callback_data=f"captcha:{target_user_id}:{respuestas[2]}:{resultado}")
                    ]
                ])
                
                # Actualizar mensaje con nuevo captcha
                texto_original = callback_query.message.text.split("Por favor")[0]
                await callback_query.message.edit_text(
                    f"{texto_original}Por favor resuelve este captcha para verificar que no eres un bot:\n\n"
                    f"¿Cuánto es {num1} + {num2}?\n\n"
                    f"Intentos: {intentos}/3",
                    reply_markup=kb
                )
    except Exception as e:
        logger.error(f"Error en handle_captcha: {e}")
        await callback_query.answer("Ha ocurrido un error. Por favor, contacta al administrador.", show_alert=True)

async def verificar_actividad_reciente(chat_id):
    """Verifica si ha habido actividad en el grupo en la última hora"""
    try:
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM user_interactions
            WHERE created_at >= NOW() - INTERVAL 1 HOUR
        """)
        result = cursor.fetchone()
        return result['count'] > 0
    except Exception as e:
        logger.error(f"Error al verificar actividad reciente: {str(e)}")
        return False

async def enviar_hormidato_automatico():
    """Envía un hormidato automáticamente si hay actividad en el grupo"""
    # Inicializar registro de hormidatos enviados automáticamente
    if not hasattr(enviar_hormidato_automatico, "ultimos_hormidatos"):
        enviar_hormidato_automatico.ultimos_hormidatos = {}
    
    try:
        # Obtener todos los chats donde el bot está presente
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT chat_id FROM user_interactions WHERE chat_id IS NOT NULL")
        chats = cursor.fetchall()
        
        for chat in chats:
            chat_id = chat['chat_id']
            if chat_id is None:
                logger.warning(f"Se encontró un chat_id nulo, saltando...")
                continue
                
            # Verificar si ha habido actividad reciente
            if await verificar_actividad_reciente(chat_id):
                # Crear registro para este chat si no existe
                if chat_id not in enviar_hormidato_automatico.ultimos_hormidatos:
                    enviar_hormidato_automatico.ultimos_hormidatos[chat_id] = []
                
                # Base de datos ampliada de hormidatos (compartida con la función hormidato)
                datos = {
                    "Curiosidades Generales": [
                        "Las hormigas pueden levantar hasta 50 veces su propio peso.",
                        "La reina de una colonia de hormigas puede vivir hasta 30 años.",
                        "Algunas especies de hormigas practican la agricultura cultivando hongos.",
                        "Las hormigas del género Myrmecocystus almacenan alimento en el abdomen de hormigas obreras especiales llamadas 'hormigas miel'.",
                        "Las hormigas pueden construir puentes vivientes usando sus propios cuerpos.",
                        "Las hormigas usan feromonas para comunicarse, creando complejos 'mapas químicos'.",
                        "El cerebro de una hormiga tiene alrededor de 250,000 neuronas, uno de los más grandes en relación a su tamaño corporal.",
                        "Las hormigas son capaces de reconocer a sus compañeras de colonia mediante el olor.",
                        "Las hormigas se limpian regularmente para evitar infecciones por hongos y bacterias.",
                        "Una colonia de hormigas puede mover hasta 50 toneladas de tierra durante su vida."
                    ],
                    "Especies Fascinantes": [
                        "Las hormigas Camponotus saundersi explotan su propio cuerpo como mecanismo de defensa.",
                        "Las hormigas tejedoras construyen nidos con hojas unidas por la seda producida por sus larvas.",
                        "Las hormigas cortadoras pueden transportar hasta 50 veces su peso en hojas.",
                        "La hormiga bala tiene una de las picaduras más dolorosas del mundo, comparada con un disparo.",
                        "Las hormigas legionarias Eciton burchellii forman colonias nómadas de más de 500,000 individuos.",
                        "Las hormigas de fuego pueden formar balsas con sus cuerpos para sobrevivir a inundaciones.",
                        "Las hormigas plateadas del Sahara pueden correr a velocidades de hasta 1 metro por segundo.",
                        "La hormiga saltadora puede saltar hasta 4 centímetros, equivalente a un humano saltando 40 metros.",
                        "Las hormigas esclavistas capturan pupas de otras colonias para forzarlas a trabajar para ellas.",
                        "Las hormigas del género Adetomyrma son conocidas como 'vampiras' por alimentarse de la hemolinfa de sus larvas."
                    ],
                    "Comportamiento Social": [
                        "Las hormigas practican el 'trofallaxis', el intercambio de alimento líquido boca a boca.",
                        "Algunas especies de hormigas esclavizan a otras colonias para que trabajen para ellas.",
                        "Ciertas hormigas tienen 'cementerios' designados donde llevan a sus muertas para evitar enfermedades.",
                        "Las hormigas obreras crean 'guarderías' específicas para cuidar de las larvas según su etapa de desarrollo.",
                        "Las hormigas colobopsis exploden tienen 'soldados kamikaze' que explotan, liberando sustancias pegajosas para defender el nido.",
                        "Las hormigas pueden adoptar diferentes roles según las necesidades de la colonia.",
                        "Hay hormigas que realizan 'rituales funerarios', llevando a sus muertas a lugares específicos lejos del nido.",
                        "Algunas especies tienen 'enfermeras' dedicadas que cuidan exclusivamente a las larvas enfermas.",
                        "Las hormigas pueden reconocer y rechazar a miembros de otras colonias incluso de la misma especie.",
                        "Existen hormigas que 'secuestran' pupas de otras colonias para aumentar su fuerza laboral."
                    ],
                    "Adaptaciones Sorprendentes": [
                        "Las hormigas Cephalotes tienen cabezas planas que usan como 'puertas vivientes' para bloquear la entrada al nido.",
                        "Algunas especies de hormigas pueden nadar y sobrevivir bajo el agua durante horas.",
                        "Las hormigas 'gliders' pueden planear controladamente si caen de los árboles, dirigiéndose de vuelta al tronco.",
                        "Ciertas hormigas del desierto han desarrollado patas extremadamente largas para mantener su cuerpo alejado de la arena caliente.",
                        "Las hormigas Cataglyphis tienen un 'GPS' biológico que les permite volver al nido en línea recta desde cualquier punto.",
                        "Las hormigas 'cosechadoras' recolectan semillas y crean sus propios 'graneros' dentro del hormiguero.",
                        "Algunas hormigas pueden cerrar sus espiráculos para evitar ahogarse durante inundaciones.",
                        "Las hormigas Formica polyctena pueden generar ácido fórmico y rociarlo como defensa química.",
                        "Las hormigas Messor barbarus pueden organizar las semillas almacenadas por tamaño y tipo en cámaras separadas.",
                        "La hormiga bala ha desarrollado un veneno que causa dolor extremo como defensa contra vertebrados."
                    ],
                    "Datos sobre Hormigas Reina": [
                        "Una reina de hormiga puede vivir más de 30 años, mientras que las obreras viven solo meses.",
                        "Algunas reinas almacenan esperma de múltiples machos para aumentar la diversidad genética de su colonia.",
                        "Las reinas de ciertas especies usan los músculos de sus alas como energía después de eliminarlas tras el vuelo nupcial.",
                        "En algunas especies, varias reinas pueden cooperar para fundar una colonia (pleometrosis).",
                        "Las reinas de hormigas pueden poner diferentes tipos de huevos según las necesidades de la colonia.",
                        "Una reina de Atta puede poner hasta 30,000 huevos por día.",
                        "Las reinas de algunas especies pueden vivir sin comer durante meses mientras fundan una nueva colonia.",
                        "En las colonias de 'killerponera', las obreras pueden convertirse en reinas a través de un duelo ritual.",
                        "Algunas reinas de hormigas pueden generar diferentes castas de obreras dependiendo de la alimentación de las larvas.",
                        "Las reinas de Lasius niger pueden fundar colonias completamente solas (fundación claustral)."
                    ],
                    "Consejos de Crianza": [
                        "Mantén la temperatura del hormiguero entre 24-28°C para la mayoría de especies tropicales.",
                        "Proporciona una fuente constante de agua para evitar la deshidratación de la colonia.",
                        "Alimenta con insectos pequeños como moscas o grillos para una dieta rica en proteínas.",
                        "Evita exponer la colonia a vibraciones o ruidos fuertes para no estresarlas.",
                        "Limpia el área de forrajeo regularmente para evitar la acumulación de residuos.",
                        "Si mantienes especies granívoras, ofrece diferentes tipos de semillas para una dieta variada.",
                        "El glucógeno líquido es excelente para proporcionar energía a las obreras forrajeadoras.",
                        "Durante la hibernación, reduce gradualmente la temperatura para evitar shock térmico.",
                        "Para la mayoría de las colonias, una humedad relativa entre 40-60% es ideal.",
                        "Las dietas de proteínas deben ser más abundantes durante las fases de crecimiento rápido de la colonia."
                    ]
                }
                
                # Obtener todas las categorías y los hormidatos en una lista plana
                todas_categorias = list(datos.keys())
                todos_hormidatos = []
                for categoria in todas_categorias:
                    for dato in datos[categoria]:
                        todos_hormidatos.append((categoria, dato))
                
                # Filtrar hormidatos que no se han mostrado recientemente
                hormidatos_disponibles = [h for h in todos_hormidatos if h not in enviar_hormidato_automatico.ultimos_hormidatos[chat_id]]
                
                # Si todos los hormidatos ya se mostraron, resetear la lista
                if not hormidatos_disponibles:
                    enviar_hormidato_automatico.ultimos_hormidatos[chat_id] = []
                    hormidatos_disponibles = todos_hormidatos
                
                # Seleccionar un hormidato aleatorio de los disponibles
                hormidato_seleccionado = random.choice(hormidatos_disponibles)
                categoria, dato = hormidato_seleccionado
                
                # Actualizar el historial (mantener solo los últimos 15 hormidatos para evitar repeticiones)
                enviar_hormidato_automatico.ultimos_hormidatos[chat_id].append(hormidato_seleccionado)
                if len(enviar_hormidato_automatico.ultimos_hormidatos[chat_id]) > 15:
                    enviar_hormidato_automatico.ultimos_hormidatos[chat_id].pop(0)
                
                try:
                    # Enviar el hormidato con un mensaje especial
                    mensaje = f"🤖 ¡Hora del hormidato !\n\n🐜 {categoria}:\n{dato}"
                    await bot.send_message(chat_id=chat_id, text=mensaje)
                    logger.info(f"Hormidato  enviado al chat {chat_id}")
                except Exception as e:
                    logger.error(f"Error al enviar hormidato al chat {chat_id}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error en envío de hormidato: {str(e)}")

async def enviar_mensaje_diario():
    """Envía un mensaje diario con información interesante sobre hormigas a las 10:11"""
    while True:
        try:
            # Calcular el tiempo hasta las 10:11 del siguiente día
            ahora = datetime.now()
            proximo_envio = ahora.replace(hour=10, minute=11, second=0, microsecond=0)
            
            # Si ya pasó la hora de hoy, programar para mañana
            if ahora >= proximo_envio:
                proximo_envio = proximo_envio + timedelta(days=1)
            
            # Calcular segundos hasta el próximo envío
            segundos_espera = (proximo_envio - ahora).total_seconds()
            logger.info(f"Próximo mensaje diario programado para: {proximo_envio}")
            
            # Esperar hasta la hora programada
            await asyncio.sleep(segundos_espera)
            
            # Obtener todos los chats donde el bot está presente
            cursor = db.get_connection().cursor(dictionary=True)
            cursor.execute("SELECT DISTINCT chat_id FROM user_interactions WHERE chat_id IS NOT NULL")
            chats = cursor.fetchall()
            
            if not chats:
                logger.warning("No se encontraron chats con IDs válidos para enviar mensajes diarios")
                continue
            
            # Tipos de mensajes diarios
            mensajes_diarios = {
                "Dato Científico": [
                    "Las hormigas existen desde hace más de 120 millones de años, sobreviviendo a los dinosaurios.",
                    "El cerebro de una hormiga tiene alrededor de 250,000 células cerebrales.",
                    "Las hormigas pueden detectar terremotos antes de que ocurran.",
                    "Las hormigas usan el sol para orientarse, similar a una brújula solar.",
                    "Las hormigas son capaces de reconocer a sus compañeras de colonia por su olor único."
                ],
                "Comportamiento Social": [
                    "Las hormigas realizan rituales funerarios, llevando a sus compañeras muertas lejos del nido.",
                    "Algunas especies de hormigas adoptan larvas de otras colonias.",
                    "Las hormigas practican la 'trofalaxis', compartiendo alimento boca a boca.",
                    "Las hormigas crean 'autopistas' químicas para guiar a otras hormigas hacia el alimento.",
                    "Las hormigas tienen diferentes 'profesiones' dentro de la colonia según su edad."
                ],
                "Consejos de Crianza Avanzados": [
                    "La humedad del nido debe ajustarse según la especie y la temporada del año.",
                    "Las colonias jóvenes necesitan más proteína que las maduras.",
                    "El tamaño del nido debe aumentarse gradualmente conforme crece la colonia.",
                    "Es importante mantener un ciclo de luz natural para las colonias.",
                    "La hibernación es crucial para muchas especies de zonas templadas."
                ],
                "Récords y Curiosidades": [
                    "La hormiga más grande del mundo es la Dinoponera gigantea, que puede medir hasta 3.5 cm.",
                    "La colonia de hormigas más grande documentada se extendía por 6,000 kilómetros.",
                    "Las hormigas pueden sobrevivir bajo el agua hasta 14 días.",
                    "Una reina de hormigas puede poner hasta 300,000 huevos en su vida.",
                    "Las hormigas pueden cargar hasta 5,000 veces su peso en condiciones ideales."
                ]
            }
            
            for chat in chats:
                try:
                    chat_id = chat['chat_id']
                    if chat_id is None:
                        logger.warning(f"Se encontró un chat_id nulo, saltando...")
                        continue
                        
                    # Seleccionar una categoría y mensaje aleatorio
                    categoria = random.choice(list(mensajes_diarios.keys()))
                    mensaje = random.choice(mensajes_diarios[categoria])
                    
                    # Crear el mensaje formateado
                    mensaje_diario = (
                        "📅 Mensaje Diario de AntMaster\n\n"
                        f"🔍 {categoria}:\n"
                        f"{mensaje}\n\n"
                        "💡 ¿Sabías este dato? ¡Comparte el tuyo usando /hormidato!"
                    )
                    
                    # Enviar el mensaje
                    await bot.send_message(chat_id=chat_id, text=mensaje_diario)
                    logger.info(f"Mensaje diario enviado al chat {chat_id}")
                    
                except Exception as e:
                    logger.error(f"Error al enviar mensaje diario al chat {chat_id}: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"Error en envío de mensaje diario: {str(e)}")
            await asyncio.sleep(300)  # Esperar 5 minutos en caso de error

async def main():
    """Función principal del bot"""
    try:
        # Inicializar la sesión HTTP global
        await init_session()
        
        # Configurar el bot en el rewards_manager
        rewards_manager.set_bot(bot)
        
        # Inicializar el diccionario de spammers notificados
        global notified_spammers
        notified_spammers = {}
        
        # Resetear el tiempo de inicio del bot
        db.reset_bot_start_time()
        
        # Configurar el scheduler
        scheduler = AsyncIOScheduler()
        
        # Programar envío de hormidato cada 3 horas
        scheduler.add_job(enviar_hormidato_automatico, 'interval', hours=3)
        
        # Programar mensaje diario a las 12:00
        scheduler.add_job(enviar_mensaje_diario, 'cron', hour=12)
        
        # Iniciar el scheduler
        scheduler.start()
        
        logger.info("Bot iniciado correctamente")
        
        # Iniciar el bot con polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error en main: {str(e)}")
    finally:
        # Cerrar la sesión HTTP al salir
        await close_session()
        logger.info("Sesión HTTP cerrada correctamente")

@dp.message(Command("chat_id"))
async def get_chat_id(message: types.Message):
    """Muestra el ID del chat actual"""
    try:
        await message.answer(f"🆔 ID del chat actual: {message.chat.id}")
    except Exception as e:
        logger.error(f"Error al obtener chat ID: {str(e)}")
        await message.answer("❌ Error al obtener el ID del chat")

@dp.message(Command("enviar_mensaje_prueba"))
async def enviar_mensaje_prueba(message: types.Message):
    """Envía manualmente un mensaje diario de prueba a todos los grupos"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='enviar_mensaje_prueba',
            chat_id=message.chat.id
        )
        
        # Mensaje de espera
        wait_message = await message.answer("🔄 Enviando mensaje de prueba a todos los grupos...")
        
        # Obtener todos los chats donde el bot está presente
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT chat_id FROM user_interactions")
        chats = cursor.fetchall()
        
        if not chats:
            await wait_message.edit_text("❌ No se encontraron grupos para enviar el mensaje.")
            return
        
        # Tipos de mensajes diarios
        mensajes_diarios = {
            "Dato Científico": [
                "Las hormigas existen desde hace más de 120 millones de años, sobreviviendo a los dinosaurios.",
                "El cerebro de una hormiga tiene alrededor de 250,000 células cerebrales.",
                "Las hormigas pueden detectar terremotos antes de que ocurran.",
                "Las hormigas usan el sol para orientarse, similar a una brújula solar.",
                "Las hormigas son capaces de reconocer a sus compañeras de colonia por su olor único."
            ],
            "Comportamiento Social": [
                "Las hormigas realizan rituales funerarios, llevando a sus compañeras muertas lejos del nido.",
                "Algunas especies de hormigas adoptan larvas de otras colonias.",
                "Las hormigas practican la 'trofalaxis', compartiendo alimento boca a boca.",
                "Las hormigas crean 'autopistas' químicas para guiar a otras hormigas hacia el alimento.",
                "Las hormigas tienen diferentes 'profesiones' dentro de la colonia según su edad."
            ],
            "Consejos de Crianza Avanzados": [
                "La humedad del nido debe ajustarse según la especie y la temporada del año.",
                "Las colonias jóvenes necesitan más proteína que las maduras.",
                "El tamaño del nido debe aumentarse gradualmente conforme crece la colonia.",
                "Es importante mantener un ciclo de luz natural para las colonias.",
                "La hibernación es crucial para muchas especies de zonas templadas."
            ],
            "Récords y Curiosidades": [
                "La hormiga más grande del mundo es la Dinoponera gigantea, que puede medir hasta 3.5 cm.",
                "La colonia de hormigas más grande documentada se extendía por 6,000 kilómetros.",
                "Las hormigas pueden sobrevivir bajo el agua hasta 14 días.",
                "Una reina de hormigas puede poner hasta 300,000 huevos en su vida.",
                "Las hormigas pueden cargar hasta 5,000 veces su peso en condiciones ideales."
            ]
        }
        
        # Contador de mensajes enviados
        enviados = 0
        errores = 0
        
        for chat in chats:
            try:
                chat_id = chat['chat_id']
                # Seleccionar una categoría y mensaje aleatorio
                categoria = random.choice(list(mensajes_diarios.keys()))
                mensaje = random.choice(mensajes_diarios[categoria])
                
                # Crear el mensaje formateado
                mensaje_diario = (
                    "🧪 PRUEBA - Mensaje Diario de AntMaster\n\n"
                    f"🔍 {categoria}:\n"
                    f"{mensaje}\n\n"
                    "💡 ¿Sabías este dato? ¡Comparte el tuyo usando /hormidato!\n\n"
                    "ℹ️ Este es un mensaje de prueba del sistema de mensajes diarios."
                )
                
                # Enviar el mensaje
                await bot.send_message(chat_id=chat_id, text=mensaje_diario)
                enviados += 1
                logger.info(f"Mensaje de prueba enviado al chat {chat_id}")
                
            except Exception as e:
                logger.error(f"Error al enviar mensaje de prueba al chat {chat_id}: {str(e)}")
                errores += 1
        
        # Actualizar mensaje con el resultado
        resumen = (
            f"✅ Prueba completada\n\n"
            f"📊 Resumen:\n"
            f"• Mensajes enviados: {enviados}\n"
            f"• Errores: {errores}\n"
            f"• Total de grupos: {len(chats)}"
        )
        await wait_message.edit_text(resumen)
        
    except Exception as e:
        logger.error(f"Error en envío de mensaje de prueba: {str(e)}")
        await message.answer("❌ Error al enviar los mensajes de prueba")

@dp.message(Command("enviar_mensaje"))
async def enviar_mensaje_manual(message: types.Message):
    """Envía manualmente un hormidato a todos los grupos"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='enviar_mensaje',
            chat_id=message.chat.id
        )
        
        # Mensaje de espera
        wait_message = await message.answer("🔄 Enviando hormidato a todos los grupos...")
        
        # Obtener todos los chats donde el bot está presente, filtrando solo grupos y asegurando IDs válidos
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT DISTINCT chat_id 
            FROM user_interactions 
            WHERE chat_id IS NOT NULL 
            AND chat_id < 0  -- Los IDs de grupo son negativos en Telegram
            AND chat_id != 0 -- Evitar IDs inválidos
            ORDER BY chat_id
        """)
        chats = cursor.fetchall()
        
        if not chats:
            await wait_message.edit_text("❌ No se encontraron grupos para enviar el mensaje.")
            return
            
        logger.info(f"Se encontraron {len(chats)} grupos para enviar mensajes")
        
        # Inicializar registro de hormidatos enviados manualmente
        if not hasattr(enviar_mensaje_manual, "ultimos_hormidatos"):
            enviar_mensaje_manual.ultimos_hormidatos = {}
        
        # Base de datos ampliada de hormidatos (compartida con la función hormidato)
        datos = {
            "Curiosidades Generales": [
                "Las hormigas pueden levantar hasta 50 veces su propio peso.",
                "La reina de una colonia de hormigas puede vivir hasta 30 años.",
                "Algunas especies de hormigas practican la agricultura cultivando hongos.",
                "Las hormigas del género Myrmecocystus almacenan alimento en el abdomen de hormigas obreras especiales llamadas 'hormigas miel'.",
                "Las hormigas pueden construir puentes vivientes usando sus propios cuerpos.",
                "Las hormigas usan feromonas para comunicarse, creando complejos 'mapas químicos'.",
                "El cerebro de una hormiga tiene alrededor de 250,000 neuronas, uno de los más grandes en relación a su tamaño corporal.",
                "Las hormigas son capaces de reconocer a sus compañeras de colonia mediante el olor.",
                "Las hormigas se limpian regularmente para evitar infecciones por hongos y bacterias.",
                "Una colonia de hormigas puede mover hasta 50 toneladas de tierra durante su vida."
            ],
            "Especies Fascinantes": [
                "La hormiga de fuego (Solenopsis invicta) es conocida por su dolorosa picadura.",
                "La hormiga Paraponera clavata, conocida como hormiga bala, tiene la picadura más dolorosa del mundo animal.",
                "Las hormigas argentinas (Linepithema humile) han creado una supercolonia que se extiende por miles de kilómetros.",
                "Las hormigas bulldog (Myrmecia) son una de las especies más agresivas y poseen una picadura muy dolorosa.",
                "Las hormigas cortadoras de hojas (Atta) cultivan hongos como fuente de alimento.",
                "Las hormigas Dracula (Mystrium camillae) usan sus mandíbulas para 'disparar' a velocidades de hasta 320 km/h.",
                "Las hormigas tejedoras (Oecophylla) cosen hojas usando la seda producida por sus larvas.",
                "Las hormigas del género Polyrhachis han desarrollado pelos que reflejan el calor del sol y pueden vivir en hábitats extremadamente calientes.",
                "Las hormigas saltadoras (Harpegnathos) pueden saltar hasta 10 cm para atrapar a sus presas.",
                "Las hormigas Cataglyphis pueden memorizar rutas complejas para volver al nido, utilizando el sol como brújula."
            ],
            "Consejos de Crianza": [
                "Mantén la temperatura del hormiguero entre 24-28°C para la mayoría de especies tropicales.",
                "Proporciona una fuente constante de agua para evitar la deshidratación de la colonia.",
                "Alimenta con insectos pequeños como moscas o grillos para una dieta rica en proteínas.",
                "Evita exponer la colonia a vibraciones o ruidos fuertes para no estresarlas.",
                "Limpia el área de forrajeo regularmente para evitar la acumulación de residuos.",
                "Si mantienes especies granívoras, ofrece diferentes tipos de semillas para una dieta variada.",
                "El glucógeno líquido es excelente para proporcionar energía a las obreras forrajeadoras.",
                "Durante la hibernación, reduce gradualmente la temperatura para evitar shock térmico.",
                "Para la mayoría de las colonias, una humedad relativa entre 40-60% es ideal.",
                "Las dietas de proteínas deben ser más abundantes durante las fases de crecimiento rápido de la colonia."
            ],
            "Comportamiento Social": [
                "Las hormigas practican el 'trofallaxis', el intercambio de alimento líquido boca a boca.",
                "Algunas especies de hormigas esclavizan a otras colonias para que trabajen para ellas.",
                "Ciertas hormigas tienen 'cementerios' designados donde llevan a sus muertas para evitar enfermedades.",
                "Las hormigas obreras crean 'guarderías' específicas para cuidar de las larvas según su etapa de desarrollo.",
                "Las hormigas colobobsis exploden tienen 'soldados kamikaze' que explotan, liberando sustancias pegajosas para defender el nido.",
                "Las hormigas pueden adoptar diferentes roles según las necesidades de la colonia.",
                "Hay hormigas que realizan 'rituales funerarios', llevando a sus muertas a lugares específicos lejos del nido.",
                "Algunas especies tienen 'enfermeras' dedicadas que cuidan exclusivamente a las larvas enfermas.",
                "Las hormigas pueden reconocer y rechazar a miembros de otras colonias incluso de la misma especie.",
                "Existen hormigas que 'secuestran' pupas de otras colonias para aumentar su fuerza laboral."
            ],
            "Adaptaciones Sorprendentes": [
                "Las hormigas Cephalotes tienen cabezas planas que usan como 'puertas vivientes' para bloquear la entrada al nido.",
                "Algunas especies de hormigas pueden nadar y sobrevivir bajo el agua durante horas.",
                "Las hormigas 'gliders' pueden planear controladamente si caen de los árboles, dirigiéndose de vuelta al tronco.",
                "Ciertas hormigas del desierto han desarrollado patas extremadamente largas para mantener su cuerpo alejado de la arena caliente.",
                "Algunas especies tienen mandíbulas que se cierran a velocidades de más de 230 km/h, las más rápidas del reino animal.",
                "Las hormigas del género Camponotus pueden detectar terremotos minutos antes de que ocurran.",
                "Las hormigas Temnothorax rugatulus construyen nidos con múltiples capas de aislamiento para regular la temperatura.",
                "Las hormigas Ectatomminae tienen aguijones modificados que pueden usar como sierras.",
                "Algunas hormigas pueden entrar en un estado similar a la hibernación para sobrevivir inundaciones.",
                "Las hormigas Adetomyrma son vampíricas y se alimentan de la hemolinfa de sus propias larvas sin dañarlas."
            ],
            "Datos Evolutivos": [
                "Las hormigas evolucionaron de avispas hace aproximadamente 140-168 millones de años.",
                "El registro fósil más antiguo de hormigas data del período Cretácico, en ámbar de 99 millones de años.",
                "Existen más de 14,000 especies de hormigas identificadas, pero se estima que podría haber hasta 22,000.",
                "Las hormigas representan aproximadamente el 15-25% de la biomasa animal terrestre del planeta.",
                "Las hormigas han desarrollado sociedades complejas de manera independiente a otros insectos sociales como las abejas.",
                "La estructura social de las hormigas ha evolucionado de manera similar en diferentes continentes, un ejemplo de evolución convergente.",
                "Algunas especies de hormigas han perdido la capacidad de picar, desarrollando otros métodos de defensa.",
                "El comportamiento de criar hongos ha evolucionado independientemente en dos linajes diferentes de hormigas.",
                "Las colonias de hormigas pueden tener desde unas pocas docenas hasta millones de individuos, según la especie.",
                "Las hormigas legionarias evolucionaron sin nidos permanentes, viviendo en 'bivaques' temporales formados por sus propios cuerpos."
            ],
            "Relaciones con Humanos": [
                "Las hormigas fueron utilizadas como suturas naturales en algunas culturas antiguas, haciendo que muerdan la herida y luego cortando su cuerpo.",
                "Algunas tribus del Amazonas usan el veneno de hormigas bala en rituales de iniciación.",
                "Las hormigas cortadoras de hojas causan miles de millones en daños a cultivos anualmente.",
                "Los antiguos griegos y romanos observaban el comportamiento de las hormigas para predecir el clima.",
                "La mirmecocoria es la dispersión de semillas por hormigas, vital para muchas especies de plantas.",
                "En algunas culturas asiáticas, las hormigas tejedoras se utilizan como insecticidas naturales en huertos.",
                "Las hormigas invasoras como la hormiga de fuego han sido introducidas accidentalmente por el comercio humano.",
                "La mirmecología, el estudio de las hormigas, fue popularizada por E.O. Wilson, quien dedicó su vida a estos insectos.",
                "Las hormigas han inspirado algoritmos de inteligencia artificial basados en sus métodos de búsqueda de caminos.",
                "El ácido fórmico fue aislado por primera vez a partir de hormigas, de ahí su nombre (formica = hormiga en latín)."
            ]
        }
        
        import random
        
        # Lista de todas las categorías y hormidatos
        todas_categorias = list(datos.keys())
        todos_hormidatos = []
        for categoria in todas_categorias:
            for dato in datos[categoria]:
                todos_hormidatos.append((categoria, dato))
        
        # Seleccionar un hormidato aleatorio global (mismo para todos los grupos)
        hormidato_seleccionado = random.choice(todos_hormidatos)
        categoria, dato = hormidato_seleccionado
        
        mensaje = f"🐜 ¡Hora del hormidato!\n\n{categoria}:\n{dato}\n\n💡 ¿Sabías este dato? ¡Comparte el tuyo usando /hormidato!"
        
        # Actualizar mensaje de estado inicial
        await wait_message.edit_text(f"🔄 Enviando hormidato a {len(chats)} grupos...")
        
        # Contadores para el seguimiento
        enviados = 0
        errores = []
        
        for chat in chats:
            try:
                chat_id = chat['chat_id']
                logger.info(f"Intentando enviar mensaje al chat {chat_id}")
                
                # Verificar que el chat_id sea válido
                if not isinstance(chat_id, (int, str)) or str(chat_id).strip() == '':
                    logger.error(f"Chat ID inválido encontrado: {chat_id}")
                    errores.append(f"ID inválido: {chat_id}")
                    continue
                
                # Convertir a entero si es string
                if isinstance(chat_id, str):
                    chat_id = int(chat_id)
                
                # Intentar enviar el mensaje
                sent_message = await bot.send_message(
                    chat_id=chat_id,
                    text=mensaje,
                    disable_notification=False  # Asegurar que se envíe con notificación
                )
                
                if sent_message:
                    enviados += 1
                    logger.info(f"✅ Mensaje enviado exitosamente al chat {chat_id}")
                    
                    # Actualizar mensaje de estado cada 5 envíos exitosos
                    if enviados % 5 == 0:
                        await wait_message.edit_text(
                            f"🔄 Progreso: {enviados}/{len(chats)} grupos\n"
                            f"❌ Errores: {len(errores)}"
                        )
                
            except Exception as e:
                error_msg = f"Error en chat {chat_id}: {str(e)}"
                logger.error(error_msg)
                errores.append(error_msg)
        
        # Actualizar mensaje final con resumen
        resumen = (
            f"✅ Envío completado\n\n"
            f"📊 Resumen:\n"
            f"• Total de grupos: {len(chats)}\n"
            f"• Mensajes enviados: {enviados}\n"
            f"• Errores: {len(errores)}\n\n"
            f"📝 Mensaje enviado:\n"
            f"{mensaje[:100]}..."
        )
        
        await wait_message.edit_text(resumen)
        
    except Exception as e:
        error_msg = f"Error general en envío de mensaje: {str(e)}"
        logger.error(error_msg)
        await message.answer(f"❌ Error al enviar los mensajes: {str(e)}")

async def is_admin(chat_id, user_id):
    """Verifica si un usuario es administrador del chat"""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error al verificar admin: {str(e)}")
        return False

@dp.message_reaction()
async def handle_reaction(message: types.MessageReactionUpdated):
    """Maneja las reacciones a mensajes"""
    try:
        # Si la reacción no es de un administrador, ignorarla
        if not await is_admin(message.chat.id, message.user.id):
            return
            
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.user.id,
            username=message.user.username or message.user.first_name,
            interaction_type='reaction',
            chat_id=message.chat.id
        )
        
        # Si la reacción es de Antmaster, verificar si es aprobación de foto
        logger.info(f"Reacción de Antmaster detectada en mensaje {message.message_id}")
        
        # Intentar aprobar la foto y dar XP
        photo = db.approve_photo(
            message_id=message.message_id,
            chat_id=message.chat.id,
            approver_id=message.user.id
        )
        
        if photo:
            # Dar XP por la foto aprobada
            if db.give_xp_for_approved_photo(message.message_id, message.chat.id):
                # Obtener el usuario que publicó la foto
                username = photo.get('username', 'Usuario')
                
                # Actualizar experiencia
                await rewards_manager.actualizar_experiencia(
                    user_id=photo['user_id'],
                    username=username,
                    chat_id=photo['chat_id'],
                    interaction_type='photo'
                )
                
                # Notificar aprobación en privado
                try:
                    await bot.send_message(
                        chat_id=photo['user_id'],
                        text=f"✅ Tu contenido ha sido aprobado y has recibido XP por tu contribución."
                    )
                except Exception as e:
                    logger.error(f"Error al enviar mensaje privado de aprobación: {str(e)}")
                    # Si falla el mensaje privado, enviar en el grupo y borrar después de 15 segundos
                    sent_message = await bot.send_message(
                        chat_id=message.chat.id,
                        text=f"✅ @{username}, tu contenido ha sido aprobado y has recibido XP.",
                        reply_to_message_id=message.message_id
                    )
                    # Programar la eliminación del mensaje después de 15 segundos
                    asyncio.create_task(delete_message_later(sent_message, 15))
                
                logger.info(f"Contenido de {username} aprobado y XP otorgado")
        
    except Exception as e:
        logger.error(f"Error al registrar reacción: {str(e)}")

async def delete_message_later(message: types.Message, delay: int):
    """Elimina un mensaje después de un retraso especificado en segundos"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception as e:
        logger.error(f"Error al eliminar mensaje: {str(e)}")

@dp.message(Command("nivel"))
async def mostrar_nivel(message: types.Message):
    """Muestra el nivel y experiencia del usuario con información detallada"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='nivel',
            chat_id=message.chat.id
        )
        
        # Obtener datos del usuario
        cursor = db.get_connection().cursor(dictionary=True)
        
        # Obtener información específica del usuario en este chat
        cursor.execute("""
            SELECT 
                user_id,
                username,
                total_xp,
                current_level
            FROM user_experience
            WHERE user_id = %s AND chat_id = %s
        """, (message.from_user.id, message.chat.id))
        
        user_data = cursor.fetchone()
        
        if not user_data:
            await message.answer(
                "🆕 <b>¡Bienvenido al sistema de niveles!</b>\n\n"
                "Aún no tienes experiencia. Comienza a interactuar para ganar XP:\n\n"
                "💬 <b>Actividades que dan XP:</b>\n"
                "• Enviar mensajes: <code>+1 XP</code>\n"
                "• Enviar fotos/videos: <code>+5 XP</code>\n"
                "• Comandos informativos: <code>+2 XP</code>\n"
                "• Acertar en juegos: <code>+10 XP</code>\n"
                "• Fotos aprobadas: <code>+25 XP</code>\n\n"
                "🎯 <b>Sistema equilibrado:</b>\n"
                "• Nivel 2: Solo 75 XP\n"
                "• Nivel 5: 450 XP (~5 días)\n"
                "• Nivel 10: 1,575 XP (~17 días)\n\n"
                "¡Comienza a participar en la comunidad! 🚀",
                parse_mode=ParseMode.HTML
            )
            return
            
        # Calcular progreso detallado
        xp_total = user_data['total_xp']
        nivel_actual, xp_en_nivel, xp_necesario = db.calcular_progreso_nivel(xp_total)
        
        # Calcular porcentaje de progreso
        progreso_pct = (xp_en_nivel / xp_necesario * 100) if xp_necesario > 0 else 100
        
        # Crear barra de progreso visual
        barra_length = 10
        progreso_chars = int(progreso_pct / 100 * barra_length)
        barra = "🟩" * progreso_chars + "⬜" * (barra_length - progreso_chars)
        
        # Emoji según nivel
        if nivel_actual < 5:
            emoji_nivel = "🌱"
            badge = "pequeña nurse"
        elif nivel_actual < 15:
            emoji_nivel = "🌿"
            badge = "Explorador Mirmecologo"
        elif nivel_actual < 30:
            emoji_nivel = "🌳"
            badge = "Guardian de la Reina"
        elif nivel_actual < 50:
            emoji_nivel = "⭐"
            badge = "Comandante Imperial"
        elif nivel_actual < 75:
            emoji_nivel = "🔥"
            badge = "Senor de las Castas"
        else:
            emoji_nivel = "👑"
            badge = "Emperador Entomologo"
        
        # Calcular estadísticas
        xp_total_siguiente = db.calcular_xp_total_para_nivel(nivel_actual + 1) if nivel_actual < 100 else 0
        
        # Obtener posición en ranking
        cursor.execute("""
            SELECT COUNT(*) + 1 as posicion
            FROM user_experience
            WHERE chat_id = %s AND total_xp > %s
        """, (message.chat.id, xp_total))
        
        ranking_data = cursor.fetchone()
        posicion_ranking = ranking_data['posicion'] if ranking_data else "N/A"
        
        # Construir mensaje detallado
        mensaje = f"{emoji_nivel} <b>Tu Progreso en Antmaster</b> {emoji_nivel}\n\n"
        mensaje += f"👤 <b>Usuario:</b> {user_data['username']}\n"
        mensaje += f"🏆 <b>Nivel:</b> {nivel_actual} - {badge}\n"
        mensaje += f"⭐ <b>XP Total:</b> {xp_total:,}\n"
        mensaje += f"📈 <b>Ranking:</b> #{posicion_ranking} en este chat\n\n"
        
        if nivel_actual < 100:
            mensaje += f"🎯 <b>Progreso al Nivel {nivel_actual + 1}:</b>\n"
            mensaje += f"{barra} {progreso_pct:.1f}%\n"
            mensaje += f"📊 {xp_en_nivel}/{xp_necesario} XP ({xp_necesario - xp_en_nivel} restantes)\n\n"
            
            # Estimaciones de tiempo
            xp_diario_promedio = 50  # Estimación conservadora
            dias_restantes = (xp_necesario - xp_en_nivel) / xp_diario_promedio
            
            if dias_restantes < 1:
                tiempo_estimado = "¡Hoy mismo!"
            elif dias_restantes < 7:
                tiempo_estimado = f"~{dias_restantes:.0f} días"
            elif dias_restantes < 30:
                tiempo_estimado = f"~{dias_restantes/7:.1f} semanas"
            else:
                tiempo_estimado = f"~{dias_restantes/30:.1f} meses"
                
            mensaje += f"⏱️ <b>Tiempo estimado:</b> {tiempo_estimado}\n\n"
        else:
            mensaje += f"🏆 <b>¡NIVEL MÁXIMO ALCANZADO!</b>\n"
            mensaje += f"Eres un verdadero maestro de la comunidad 👑\n\n"
        
        # Información sobre recompensas próximas
        proximas_recompensas = {
            5: "🌱 Badge 'pequeña nurse'", 
            10: "🌿 Descuento 5% + Badge 'Explorador Mirmecologo'", 
            15: "🌳 Kit inicio Terra", 
            25: "⭐ Descuento 10% + Badge 'Guardian de la Reina'", 
            35: "🔥 Kit M Terra", 
            50: "💎 Badge 'Comandante Imperial' + Kit L Terra", 
            75: "👑 Badge 'Senor de las Castas' + Tarjeta regalo 50€", 
            100: "🏆 Badge 'Emperador Entomologo' + Tarjeta regalo 100€"
        }
        
        # Encontrar próximas 2 recompensas
        recompensas_cercanas = []
        for nivel_recompensa, descripcion in proximas_recompensas.items():
            if nivel_actual < nivel_recompensa:
                xp_faltante = db.calcular_xp_total_para_nivel(nivel_recompensa) - xp_total
                recompensas_cercanas.append((nivel_recompensa, descripcion, xp_faltante))
                if len(recompensas_cercanas) >= 2:
                    break
        
        if recompensas_cercanas:
            mensaje += "🎁 <b>Próximas recompensas:</b>\n"
            for i, (nivel_recompensa, descripcion, xp_faltante) in enumerate(recompensas_cercanas):
                dias_estimados = xp_faltante / 50  # 50 XP promedio diario
                if dias_estimados < 1:
                    tiempo_str = "¡Muy pronto!"
                elif dias_estimados < 7:
                    tiempo_str = f"~{dias_estimados:.0f} días"
                elif dias_estimados < 30:
                    tiempo_str = f"~{dias_estimados/7:.1f} semanas"
                else:
                    tiempo_str = f"~{dias_estimados/30:.1f} meses"
                
                mensaje += f"   <b>Nivel {nivel_recompensa}:</b> {descripcion}\n"
                mensaje += f"   <i>Faltan {xp_faltante:,} XP ({tiempo_str})</i>\n"
                if i < len(recompensas_cercanas) - 1:
                    mensaje += "\n"
            mensaje += "\n"
        
        # Consejos para ganar XP
        mensaje += f"💡 <b>Consejos para subir de nivel:</b>\n"
        mensaje += f"• Participa activamente en conversaciones\n"
        mensaje += f"• Comparte fotos de hormigas de calidad\n"
        mensaje += f"• Usa comandos informativos como /especie\n"
        mensaje += f"• Juega a /adivina_especie (10 XP por acierto)\n"
        mensaje += f"• Límite diario: 100 XP"
        
        await message.answer(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error al mostrar nivel: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al obtener tu información de nivel.")
    finally:
        if cursor:
            cursor.close()

@dp.message(Command("aplicar_badges"))
async def aplicar_badges(message: types.Message):
    """Aplica badges automaticamente a todos los usuarios segun su nivel actual"""
    try:
        # Verificar si el usuario es administrador
        if not await is_admin(message.chat.id, message.from_user.id):
            await message.answer("❌ Solo los administradores pueden ejecutar este comando.")
            return
        
        # Registrar interaccion
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='aplicar_badges',
            chat_id=message.chat.id
        )
        
        wait_message = await message.answer("🔄 Verificando permisos del bot...")
        
        # Verificar que el bot tenga permisos para promocionar administradores
        try:
            bot_member = await bot.get_chat_member(chat_id=message.chat.id, user_id=bot.id)
            if not hasattr(bot_member, 'can_promote_members') or not bot_member.can_promote_members:
                await wait_message.edit_text(
                    "❌ <b>Error de Permisos</b>\n\n"
                    "El bot no tiene permisos para promocionar administradores en este grupo.\n\n"
                    "🔧 <b>Para solucionarlo:</b>\n"
                    "1. Ve a la configuración del grupo\n"
                    "2. Edita los permisos del bot\n"
                    "3. Activa 'Agregar nuevos administradores'\n"
                    "4. Guarda los cambios e inténtalo de nuevo",
                    parse_mode=ParseMode.HTML
                )
                return
        except Exception as e:
            await wait_message.edit_text(f"❌ Error verificando permisos del bot: {str(e)}")
            return
        
        await wait_message.edit_text("🔄 Buscando usuarios elegibles...")
        
        # Obtener todos los usuarios del chat con nivel >= 10
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT user_id, username, current_level
            FROM user_experience
            WHERE chat_id = %s AND current_level >= 5
            ORDER BY current_level DESC
        """, (message.chat.id,))
        
        usuarios = cursor.fetchall()
        
        if not usuarios:
            await wait_message.edit_text("ℹ️ No hay usuarios con nivel 10+ en este chat.")
            return
        
        await wait_message.edit_text(f"🔄 Procesando {len(usuarios)} usuarios...")
        
        # Badges por nivel
        badges = {
    5: " Pequeña Nurse",
    10: "Explorador Mirmecólogo", 
    25: "Guardián de la Reina", 
    50: "Comandante Imperial", 
    75: "Señor de las Castas", 
    100: "Emperador Entomólogo"
}
        procesados = 0
        otorgados = 0
        errores = 0
        ya_tenian = 0
        no_elegibles = 0
        detalles = []
        
        for usuario in usuarios:
            try:
                nivel = usuario['current_level']
                username = usuario['username'] or f"Usuario {usuario['user_id']}"
                
                # Encontrar el badge más alto que corresponde
                badge_nivel = None
                for nivel_req in sorted(badges.keys(), reverse=True):
                    if nivel >= nivel_req:
                        badge_nivel = nivel_req
                        break
                
                if badge_nivel:
                    resultado = await rewards_manager.otorgar_badge_automatico(
                        user_id=usuario['user_id'],
                        chat_id=message.chat.id,
                        nivel=badge_nivel,
                        badge_name=username
                    )
                    
                    if resultado == "otorgado":
                        otorgados += 1
                        detalles.append(f"✅ {username}: Badge {badges[badge_nivel]} otorgado")
                    elif resultado == "ya_tiene":
                        ya_tenian += 1
                        detalles.append(f"ℹ️ {username}: Ya tiene el badge correspondiente")
                    elif resultado == "creador":
                        no_elegibles += 1
                        detalles.append(f"👑 {username}: Es el creador del grupo")
                    elif resultado == "sin_permisos":
                        errores += 1
                        detalles.append(f"⚠️ {username}: Bot sin permisos para otorgar badges")
                    elif resultado == "error_permisos":
                        errores += 1
                        detalles.append(f"❌ {username}: Error verificando permisos")
                    elif resultado == "error_titulo":
                        errores += 1
                        detalles.append(f"❌ {username}: Error al establecer título")
                    elif resultado == "error_promocion":
                        errores += 1
                        detalles.append(f"❌ {username}: Error al promover a administrador")
                    elif resultado == "error_usuario":
                        errores += 1
                        detalles.append(f"❌ {username}: Error obteniendo información del usuario")
                    elif resultado == "nivel_invalido":
                        no_elegibles += 1
                        detalles.append(f"⚪ {username}: Nivel no válido para badge")
                    else:  # error_general u otros errores
                        errores += 1
                        detalles.append(f"❌ {username}: Error general al otorgar badge")
                else:
                    no_elegibles += 1
                    detalles.append(f"⚪ {username}: Nivel {nivel} (sin badge disponible)")
                
                procesados += 1
                
            except Exception as e:
                logger.error(f"Error procesando usuario {usuario.get('username', 'desconocido')}: {str(e)}")
                errores += 1
                detalles.append(f"❌ {usuario.get('username', 'desconocido')}: Error inesperado")
                continue
        
        # Crear mensaje de resultado detallado
        mensaje = (
            f"✅ <b>Proceso Completado</b>\n\n"
            f"📊 <b>Resumen:</b>\n"
            f"• Usuarios procesados: {procesados}\n"
            f"• Badges otorgados: {otorgados}\n"
            f"• Ya tenían badge: {ya_tenian}\n"
            f"• Errores: {errores}\n"
            f"• No elegibles: {no_elegibles}\n\n"
        )
        
        if detalles:
            mensaje += "📋 <b>Detalles:</b>\n"
            # Mostrar solo los primeros 15 para no saturar
            for detalle in detalles[:15]:
                mensaje += f"{detalle}\n"
            
            if len(detalles) > 15:
                mensaje += f"... y {len(detalles) - 15} más\n"
            
            mensaje += "\n"
        
        mensaje += (
            f"🎖️ <b>Badges disponibles:</b>\n"
            f"• Nivel 5: {badges[5]}\n"
            f"• Nivel 10: {badges[10]}\n"
            f"• Nivel 25: {badges[25]}\n"
            f"• Nivel 50: {badges[50]}\n"
            f"• Nivel 75: {badges[75]}\n"
            f"• Nivel 100: {badges[100]}\n\n"
            f"💡 <b>Nota:</b> Los badges se otorgan como títulos de administrador con permisos básicos.\n"
            f"Si hay errores, verifica que el bot tenga permisos para gestionar administradores."
        )
        
        await wait_message.edit_text(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error en aplicar_badges: {str(e)}")
        await message.answer("❌ Error al procesar badges.")
    finally:
        if 'cursor' in locals():
            cursor.close()

@dp.message(Command("recompensas"))
async def mostrar_recompensas(message: types.Message):
    """Muestra todas las recompensas disponibles por nivel"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='recompensas',
            chat_id=message.chat.id
        )
        
        # Obtener nivel actual del usuario
        cursor = db.get_connection().cursor(dictionary=True)
        cursor.execute("""
            SELECT current_level FROM user_experience
            WHERE user_id = %s AND chat_id = %s
        """, (message.from_user.id, message.chat.id))
        
        user_data = cursor.fetchone()
        nivel_actual = user_data['current_level'] if user_data else 0
        
        mensaje = "🎁 <b>Sistema de Recompensas Antmaster</b> 🎁\n\n"
        mensaje += "🏆 <b>Recompensas por nivel:</b>\n\n"
        
        recompensas = [
            (5, "🌱", "Acceso a comandos avanzados", "Desbloquea funciones especiales del bot"),
            (10, "🌿", "Descuento 5% + Badge 'Explorador Mirmecologo'", "Primera recompensa económica + reconocimiento"),
            (15, "🌳", "Kit básico de hormigas", "Kit de iniciación con herramientas básicas"),
            (25, "⭐", "Descuento 10% + Badge 'Guardian de la Reina'", "Mayor descuento + badge mejorado"),
            (35, "🔥", "Kit intermedio de hormigas", "Kit con herramientas profesionales"),
            (50, "💎", "Badge 'Comandante Imperial' + Kit avanzado", "Reconocimiento de experto + kit premium"),
            (75, "👑", "Badge 'Senor de las Castas' + Tarjeta regalo 50€", "Badge élite + premio económico importante"),
            (100, "🏆", "Badge 'Emperador Entomologo' + Tarjeta regalo 100€", "Máximo reconocimiento + gran premio")
        ]
        
        for nivel, emoji, titulo, descripcion in recompensas:
            estado = "✅" if nivel_actual >= nivel else "🔒"
            estado_texto = "OBTENIDA" if nivel_actual >= nivel else "PENDIENTE"
            
            mensaje += f"{estado} <b>Nivel {nivel}</b> {emoji} - {estado_texto}\n"
            mensaje += f"   <b>{titulo}</b>\n"
            mensaje += f"   <i>{descripcion}</i>\n\n"
        
        mensaje += "💡 <b>Información importante:</b>\n"
        mensaje += "• Las recompensas se entregan automáticamente al subir de nivel\n"
        mensaje += "• Los kits se envían por correo (proporciona dirección)\n"
        mensaje += "• Los descuentos tienen códigos únicos\n"
        mensaje += "• Contacta con administradores para reclamar premios\n\n"
        
        mensaje += "📈 <b>Cómo ganar XP rápidamente:</b>\n"
        mensaje += "• Mensajes de calidad (3+ palabras): +1 XP\n"
        mensaje += "• Fotos/videos de hormigas: +5 XP\n"
        mensaje += "• Comandos informativos: +2 XP\n"
        mensaje += "• Ganar en /adivina_especie: +10 XP\n"
        mensaje += "• Fotos aprobadas por admins: +25 XP\n"
        mensaje += "• Límite diario: 100 XP máximo\n\n"
        
        mensaje += f"🎯 <b>Tu nivel actual:</b> {nivel_actual if nivel_actual > 0 else 'Sin nivel (usa /nivel)'}\n"
        mensaje += "📊 Usa /nivel para ver tu progreso detallado"
        
        await message.answer(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error al mostrar recompensas: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al obtener la información de recompensas.")
    finally:
        if cursor:
            cursor.close()


@dp.message(Command("mis_codigos"))
async def mostrar_mis_codigos(message: types.Message):
    """Muestra todos los códigos de descuento del usuario"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='mis_codigos',
            chat_id=message.chat.id
        )
        
        # Importar el discount manager
        from discount_code_manager import DiscountCodeManager
        discount_manager = DiscountCodeManager(db)
        
        # Obtener códigos del usuario
        codigos = discount_manager.get_user_codes(message.from_user.id)
        
        if not codigos:
            await message.answer(
                "🔍 <b>Tus Códigos de Descuento</b>\n\n"
                "No tienes códigos de descuento activos.\n\n"
                "💡 <b>Cómo obtener códigos:</b>\n"
                "• Sube de nivel para desbloquear recompensas\n"
                "• Participa en eventos especiales\n"
                "• Mantente atento a promociones\n\n"
                "📈 Usa /nivel para ver tu progreso y próximas recompensas",
                parse_mode=ParseMode.HTML
            )
            return
        
        mensaje = "🎫 <b>Tus Códigos de Descuento</b>\n\n"
        
        for i, codigo in enumerate(codigos, 1):
            # Formato de fecha
            fecha_expira = codigo['expires_at'].strftime("%d/%m/%Y")
            
            # Estado del código
            if codigo['is_expired']:
                estado = "❌ EXPIRADO"
            elif codigo['uses_remaining'] <= 0:
                estado = "🚫 AGOTADO"
            else:
                estado = f"✅ DISPONIBLE ({codigo['uses_remaining']} usos)"
            
            mensaje += (
                f"<b>{i}. {codigo['code']}</b>\n"
                f"   💰 {codigo['discount_text']}\n"
                f"   📅 Expira: {fecha_expira}\n"
                f"   📊 Estado: {estado}\n"
            )
            
            if codigo['min_purchase_amount'] > 0:
                mensaje += f"   🛒 Compra mínima: {codigo['min_purchase_amount']}€\n"
            
            if codigo['description']:
                mensaje += f"   📝 {codigo['description']}\n"
            
            mensaje += "\n"
        
        mensaje += (
            "💡 <b>Instrucciones:</b>\n"
            "1. Copia el código que quieras usar\n"
            "2. Contacta con un administrador\n"
            "3. Proporciona el código al realizar tu compra\n"
            "4. Usa /validar_codigo <código> para verificar validez\n\n"
            "📞 <b>Soporte:</b> Contacta con @admin para asistencia"
        )
        
        await message.answer(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error al mostrar códigos de usuario: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al obtener tus códigos de descuento.")

@dp.message(Command("validar_codigo"))
async def validar_codigo_descuento(message: types.Message):
    """Valida un código de descuento"""
    try:
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='validar_codigo',
            chat_id=message.chat.id
        )
        
        # Extraer código del mensaje
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        
        if not args:
            await message.answer(
                "🔍 <b>Validar Código de Descuento</b>\n\n"
                "📝 <b>Uso:</b> <code>/validar_codigo TU_CODIGO</code>\n\n"
                "💡 <b>Ejemplo:</b> <code>/validar_codigo LVL10ABC123</code>\n\n"
                "📋 Puedes encontrar tus códigos con /mis_codigos",
                parse_mode=ParseMode.HTML
            )
            return
        
        codigo = args[0].upper().strip()
        
        # Importar el discount manager
        from discount_code_manager import DiscountCodeManager
        discount_manager = DiscountCodeManager(db)
        
        # Validar código
        resultado = discount_manager.validate_code(
            code=codigo, 
            user_id=message.from_user.id, 
            purchase_amount=50.0  # Monto de prueba
        )
        
        if resultado["valid"]:
            code_info = resultado["code_info"]
            
            # Formatear información del descuento
            if code_info['discount_type'] == 'percentage':
                descuento_texto = f"{code_info['discount_value']}% de descuento"
            elif code_info['discount_type'] == 'fixed':
                descuento_texto = f"{code_info['discount_value']}€ de descuento"
            elif code_info['discount_type'] == 'shipping':
                descuento_texto = "Envío gratuito"
            else:
                descuento_texto = code_info['description']
            
            fecha_expira = code_info['expires_at'].strftime("%d/%m/%Y a las %H:%M")
            usos_restantes = code_info['max_uses'] - code_info['current_uses']
            
            mensaje = (
                f"✅ <b>Código Válido</b>\n\n"
                f"🎫 <b>Código:</b> <code>{codigo}</code>\n"
                f"💰 <b>Descuento:</b> {descuento_texto}\n"
                f"📅 <b>Expira:</b> {fecha_expira}\n"
                f"🔢 <b>Usos restantes:</b> {usos_restantes}\n"
            )
            
            if code_info['min_purchase_amount'] > 0:
                mensaje += f"🛒 <b>Compra mínima:</b> {code_info['min_purchase_amount']}€\n"
            
            if code_info['description']:
                mensaje += f"📝 <b>Descripción:</b> {code_info['description']}\n"
            
            # Ejemplo de descuento con monto de prueba
            descuento_ejemplo = resultado["discount_amount"]
            precio_final = resultado["final_amount"]
            
            mensaje += (
                f"\n💡 <b>Ejemplo con compra de 50€:</b>\n"
                f"   • Descuento aplicado: {descuento_ejemplo}€\n"
                f"   • Precio final: {precio_final}€\n\n"
                f"✅ ¡Este código está listo para usar!"
            )
        else:
            # Código inválido - mostrar razón específica
            error_messages = {
                "NOT_FOUND": "❌ <b>Código no encontrado</b>\n\nEste código no existe o ha sido desactivado.",
                "EXPIRED": "⏰ <b>Código expirado</b>\n\nEste código ya no es válido.",
                "MAX_USES_REACHED": "🚫 <b>Código agotado</b>\n\nEste código ya ha sido usado el máximo de veces permitidas.",
                "MIN_PURCHASE_NOT_MET": f"🛒 <b>Compra mínima no alcanzada</b>\n\n{resultado['error']}",
                "WRONG_USER": "👤 <b>Código específico</b>\n\nEste código es específico para otro usuario.",
                "ALREADY_USED": "🔄 <b>Ya usado</b>\n\nYa has usado este código anteriormente.",
                "SYSTEM_ERROR": "⚠️ <b>Error del sistema</b>\n\nHubo un problema al validar el código. Inténtalo más tarde."
            }
            
            mensaje = error_messages.get(
                resultado.get("error_type", "SYSTEM_ERROR"),
                f"❌ <b>Código inválido</b>\n\n{resultado.get('error', 'Error desconocido')}"
            )
            
            mensaje += "\n\n💡 Usa /mis_codigos para ver tus códigos válidos."
        
        await message.answer(mensaje, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error al validar código: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al validar el código de descuento.")

@dp.message(Command("crear_codigo_promo"))
async def crear_codigo_promocional(message: types.Message):
    """Permite a los administradores crear códigos promocionales"""
    try:
        # Verificar si el usuario es administrador
        if not await is_admin(message.chat.id, message.from_user.id):
            await message.answer("❌ Solo los administradores pueden crear códigos promocionales.")
            return
        
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='crear_codigo_promo',
            chat_id=message.chat.id
        )
        
        # Extraer argumentos del comando
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        
        if len(args) < 2:
            await message.answer(
                "🔧 <b>Crear Código Promocional</b>\n\n"
                "📝 <b>Uso:</b>\n"
                "<code>/crear_codigo_promo [tipo] [valor] [usos] [días] [compra_min] [descripción]</code>\n\n"
                "📋 <b>Parámetros:</b>\n"
                "• <b>tipo:</b> percentage, fixed, shipping\n"
                "• <b>valor:</b> número (5 para 5%, 10 para 10€, etc.)\n"
                "• <b>usos:</b> máximo número de usos (opcional, default: 100)\n"
                "• <b>días:</b> días hasta expirar (opcional, default: 30)\n"
                "• <b>compra_min:</b> compra mínima en € (opcional, default: 0)\n"
                "• <b>descripción:</b> texto descriptivo (opcional)\n\n"
                "💡 <b>Ejemplos:</b>\n"
                "<code>/crear_codigo_promo percentage 15 50 60 25 Descuento especial verano</code>\n"
                "<code>/crear_codigo_promo fixed 20 100 30</code>\n"
                "<code>/crear_codigo_promo shipping 0 200 45</code>",
                parse_mode=ParseMode.HTML
            )
            return

        # Parsear argumentos
        tipo_descuento = args[0].lower()
        valor_descuento = float(args[1])
        usos_maximos = int(args[2]) if len(args) > 2 else 100
        dias_expira = int(args[3]) if len(args) > 3 else 30
        compra_min = float(args[4]) if len(args) > 4 else 0
        descripcion = ' '.join(args[5:]) if len(args) > 5 else None
        
        # Validar tipo de descuento
        if tipo_descuento not in ['percentage', 'fixed', 'shipping']:
            await message.answer("❌ Tipo de descuento inválido. Usa: percentage, fixed, o shipping")
            return
        
        # Validar valores
        if tipo_descuento == 'percentage' and (valor_descuento <= 0 or valor_descuento > 100):
            await message.answer("❌ El porcentaje debe estar entre 0 y 100")
            return
        elif tipo_descuento == 'fixed' and valor_descuento <= 0:
            await message.answer("❌ El descuento fijo debe ser mayor a 0")
            return
        
        if usos_maximos <= 0:
            await message.answer("❌ El número de usos debe ser mayor a 0")
            return
        
        if dias_expira <= 0:
            await message.answer("❌ Los días de expiración deben ser mayor a 0")
            return
            
        if compra_min < 0:
            await message.answer("❌ La compra mínima no puede ser negativa")
            return
        
        # Crear el código promocional
        codigo = discount_manager.create_code(
            discount_type=tipo_descuento,
            discount_value=valor_descuento,
            max_uses=usos_maximos,
            expires_in_days=dias_expira,
            min_purchase_amount=compra_min,
            description=descripcion
        )
        
        if codigo:
            # Formatear mensaje de éxito
            if tipo_descuento == 'percentage':
                descuento_texto = f"{valor_descuento}% de descuento"
            elif tipo_descuento == 'fixed':
                descuento_texto = f"€{valor_descuento} de descuento"
            else:
                descuento_texto = "Envío gratuito"
                
            from datetime import datetime, timedelta
            fecha_expira = (datetime.now() + timedelta(days=dias_expira)).strftime("%d/%m/%Y")
            
            mensaje = (
                f"✅ <b>Código Promocional Creado</b>\n\n"
                f"🎫 <b>Código:</b> <code>{codigo}</code>\n"
                f"🎁 <b>Descuento:</b> {descuento_texto}\n"
                f"🔢 <b>Usos máximos:</b> {usos_maximos}\n"
                f"📅 <b>Expira:</b> {fecha_expira}\n"
            )
            
            if compra_min > 0:
                mensaje += f"🛒 <b>Compra mínima:</b> €{compra_min}\n"
                
            if descripcion:
                mensaje += f"📝 <b>Descripción:</b> {descripcion}\n"
                
            mensaje += (
                f"\n🔗 <b>Compartir:</b>\n"
                f"<code>/validar_codigo {codigo}</code>\n\n"
                f"💡 Los usuarios pueden usar este código con:\n"
                f"<code>/validar_codigo {codigo}</code>"
            )
            
            await message.answer(mensaje, parse_mode=ParseMode.HTML)
            logger.info(f"Código promocional {codigo} creado por admin {message.from_user.username} ({message.from_user.id})")
        else:
            await message.answer("❌ Error al crear el código promocional. Inténtalo de nuevo.")
            
    except ValueError as e:
        await message.answer(f"❌ Error en los parámetros: {str(e)}\nVerifica que los números sean válidos.")
    except Exception as e:
        logger.error(f"Error en crear_codigo_promocional: {str(e)}")
        await message.answer("❌ Lo siento, hubo un error al procesar el comando.")

# === SISTEMA DE TRADUCCIÓN AUTOMÁTICA ===

# Inicializar el gestor de traducción al inicio
try:
    translation_manager = TranslationManager(db)
    logger.info("✅ Gestor de traducción inicializado")
except Exception as e:
    logger.error(f"❌ Error inicializando gestor de traducción: {str(e)}")
    translation_manager = None

@dp.message(Command("idioma"))
async def seleccionar_idioma(message: types.Message):
    """Permite al usuario seleccionar su idioma"""
    try:
        # Verificar si el sistema de traducción está disponible
        if not translation_manager:
            await message.answer("❌ Sistema de traducción no disponible.")
            return
            
        # Verificar si es un chat grupal
        if message.chat.type not in ['group', 'supergroup']:
            await message.answer("Este comando solo funciona en grupos.")
            return
            
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='idioma',
            chat_id=message.chat.id
        )
        
        # Mostrar teclado de selección de idioma
        keyboard = translation_manager.get_language_keyboard()
        
        await message.answer(
            "🌐 <b>Selecciona tu idioma</b>\n\n"
            "Si seleccionas un idioma diferente al español, recibirás traducciones automáticas "
            "de los mensajes del grupo en mensajes privados.\n\n"
            "Si hablas español, selecciona '🇪🇸 Hablo Español'.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error en comando idioma: {str(e)}")
        await message.answer("❌ Error al mostrar opciones de idioma.")

async def notify_daily_limit_reached(message: types.Message):
    """Notifica al usuario que ha alcanzado el límite diario de XP"""
    try:
        await message.reply(
            "🌟 ¡Has alcanzado el límite diario de 100 XP! 🌟\n"
            "Vuelve mañana para seguir ganando experiencia y subir de nivel.\n"
            "¡Gracias por tu participación activa en la comunidad! 🐜"
        )
    except Exception as e:
        logger.error(f"Error al notificar límite diario: {str(e)}")

@dp.message()
async def handle_message(message: types.Message):
    """Maneja los mensajes normales"""
    try:
        # Ignorar mensajes en chats privados
        if message.chat.type == 'private':
            return
            
        # Verificar si el mensaje tiene contenido de calidad
        if not is_quality_message(message.text):
            logger.info(f"Mensaje de baja calidad de {message.from_user.username or message.from_user.first_name} ignorado para XP")
            return
            
        # Verificar si es spam antes de registrar
        if db.is_spam(message.from_user.id, 'message', message.chat.id):
            logger.warning(f"Spam detectado del usuario {message.from_user.username or message.from_user.first_name} en el chat {message.chat.id}")
            # Notificar y aplicar medidas anti-spam
            await notify_spam_detected(message)
            return
            
        # Registrar interacción solo si el mensaje tiene contenido válido
        result = await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='message',
            chat_id=message.chat.id
        )
        
        # Si es detectado como spam o alcanzó límite, notificar al usuario
        if not result:
            # Verificar si el usuario alcanzó el límite diario
            if db.reached_daily_xp_limit(message.from_user.id, message.chat.id):
                # Verificar si ya notificamos hoy a este usuario
                if not hasattr(handle_message, "notified_limit_users"):
                    handle_message.notified_limit_users = {}
                
                user_key = f"{message.from_user.id}_{message.chat.id}"
                current_date = datetime.now().date()
                
                # Si no hemos notificado hoy a este usuario, notificar
                if user_key not in handle_message.notified_limit_users or handle_message.notified_limit_users[user_key] != current_date:
                    await notify_daily_limit_reached(message)
                    handle_message.notified_limit_users[user_key] = current_date
            # Verificar si el usuario está cerca del límite diario
            elif db.is_approaching_daily_limit(message.from_user.id, message.chat.id):
                await notify_approaching_limit(message)
                
    except Exception as e:
        logger.error(f"Error al manejar mensaje normal: {str(e)}")

def is_quality_message(text):
    """
    Verifica si un mensaje es de calidad suficiente para otorgar XP
    """
    if not text:
        return False
    
    # Limpiar el texto (eliminar espacios extra y caracteres especiales básicos)
    cleaned_text = text.strip()
    
    # Contar palabras (separar por espacios y filtrar elementos vacíos)
    words = [word for word in cleaned_text.split() if word.strip()]
    
    # Excluir mensajes de 1 o 2 palabras
    if len(words) <= 2:
        return False
        
    # Verificar si el mensaje tiene demasiados caracteres repetidos (posible spam)
    if is_repetitive_text(text):
        return False
        
    return True
    
def is_repetitive_text(text):
    """
    Verifica si un texto tiene patrones repetitivos que indican spam
    """
    if not text or len(text) < 5:
        return False
        
    # Verificar si hay un carácter que se repite más del 50% del mensaje
    total_length = len(text)
    for char in set(text):
        if text.count(char) > total_length * 0.5:
            return True
            
    # Buscar repeticiones de secuencias
    if len(text) >= 10:
        # Tomar la primera mitad del mensaje y ver si se repite
        half_length = total_length // 2
        if text[:half_length] == text[half_length:half_length*2]:
            return True
            
    return False

async def notify_approaching_limit(message):
    """Notifica al usuario que está cerca del límite diario de XP"""
    try:
        # Esta función se llama cuando el usuario está cerca del límite diario
        # pero aún no lo ha alcanzado
        
        # Para evitar spam de notificaciones, usamos una variable global para
        # seguir a qué usuarios ya hemos notificado hoy
        if not hasattr(notify_approaching_limit, "notified_users"):
            notify_approaching_limit.notified_users = set()
        
        user_key = f"{message.from_user.id}_{message.chat.id}"
        
        # Si ya notificamos a este usuario hoy, no enviar otra notificación
        if user_key in notify_approaching_limit.notified_users:
            return
            
        # Añadir el usuario a la lista de notificados
        notify_approaching_limit.notified_users.add(user_key)
        
        # Enviar mensaje privado al usuario
        await bot.send_message(
            message.from_user.id,
            "⚠️ <b>Aviso del sistema</b> ⚠️\n\n"
            "Estás acercándote al límite diario de XP (100 puntos). "
            "El sistema de XP está diseñado para fomentar una participación equilibrada "
            "y evitar el abuso. Podrás seguir participando, pero no ganarás más XP hoy.\n\n"
            "¡Continúa participando en la comunidad de forma constructiva!",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        # Si no podemos enviar mensaje privado, ignoramos y continuamos
        logger.error(f"Error al notificar límite: {str(e)}")
        pass
        
async def notify_spam_detected(message):
    """Notifica al usuario que se ha detectado comportamiento de spam y aplica medidas"""
    try:
        # Verificar si el bot se inició recientemente (menos de 2 minutos)
        # Para evitar restricciones durante el procesamiento inicial de mensajes acumulados
        if hasattr(db, 'bot_start_time'):
            time_since_start = (datetime.now() - db.bot_start_time).total_seconds()
            if time_since_start < 120:  # Menos de 2 minutos desde el inicio
                logger.info(f"Bot iniciado recientemente ({time_since_start:.1f}s), ignorando detección de spam para usuario {message.from_user.username}")
                return
        
        # Para seguimiento de notificaciones previas y aplicación de penalizaciones
        if not hasattr(notify_spam_detected, "notified_spammers"):
            notify_spam_detected.notified_spammers = {}
            
        user_key = f"{message.from_user.id}_{message.chat.id}"
        current_time = datetime.now()
        
        # Verificar si el usuario ya ha sido notificado y aplicar medidas más severas si es reincidente
        if user_key in notify_spam_detected.notified_spammers:
            last_notification = notify_spam_detected.notified_spammers[user_key]
            time_diff = (current_time - last_notification['time']).total_seconds() / 60
            
            # Solo aplicar restricciones si han pasado menos de 30 minutos desde la última notificación
            # y es una reincidencia real (no procesamiento inicial)
            if time_diff < 30:
                # Aumentar el contador de advertencias
                notify_spam_detected.notified_spammers[user_key]['count'] += 1
                count = notify_spam_detected.notified_spammers[user_key]['count']
                
                # Aplicar timeout solo si es reincidente múltiple (3 o más detecciones)
                if count >= 3:
                    # El timeout aumenta con cada reincidencia (1 minuto, 2 minutos, 4 minutos, etc.)
                    timeout_minutes = min(60, 1 * (2 ** (count - 2)))  # Máximo 60 minutos
                    
                    try:
                        # Restricción temporal: no puede enviar mensajes
                        until_date = current_time + timedelta(minutes=timeout_minutes)
                        await bot.restrict_chat_member(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            permissions=types.ChatPermissions(can_send_messages=False),
                            until_date=until_date
                        )
                        
                        # Notificar en el chat sobre la restricción
                        await message.reply(
                            f"⚠️ @{message.from_user.username or message.from_user.first_name} ha sido temporalmente silenciado "
                            f"por {timeout_minutes} {'minuto' if timeout_minutes == 1 else 'minutos'} "
                            f"debido a comportamiento de spam excesivo."
                        )
                        
                        # Notificar al usuario por privado
                        await bot.send_message(
                            message.from_user.id,
                            f"⚠️ <b>Sistema Anti-Spam</b> ⚠️\n\n"
                            f"Has sido temporalmente silenciado en el chat por {timeout_minutes} "
                            f"{'minuto' if timeout_minutes == 1 else 'minutos'} debido a la detección "
                            f"de comportamiento de spam reiterado.\n\n"
                            f"Por favor, evita enviar mensajes repetitivos o muy frecuentes.\n\n"
                            f"Podrás volver a participar normalmente cuando expire la restricción "
                            f"en el chat.",
                            parse_mode=ParseMode.HTML
                        )
                        
                        logger.warning(f"Usuario {message.from_user.username or message.from_user.first_name} ({message.from_user.id}) "
                                     f"silenciado por {timeout_minutes} minutos en el chat {message.chat.id}")
                        
                        # Actualizar el tiempo de la notificación
                        notify_spam_detected.notified_spammers[user_key]['time'] = current_time
                        return
                    except Exception as e:
                        logger.error(f"Error al aplicar restricción de spam: {str(e)}")
                        # Continuar con la notificación normal si falla la restricción
            else:
                # Ha pasado mucho tiempo, reiniciar contador
                notify_spam_detected.notified_spammers[user_key] = {
                    'time': current_time,
                    'count': 1
                }
        else:
            # Primera advertencia
            notify_spam_detected.notified_spammers[user_key] = {
                'time': current_time,
                'count': 1
            }
        
        # Enviar advertencia en el chat (solo para casos leves)
        await message.reply(
            f"⚠️ @{message.from_user.username or message.from_user.first_name}, por favor evita enviar "
            f"mensajes muy frecuentes o repetitivos para mantener la calidad del chat."
        )
        
        # Enviar mensaje privado al usuario con más detalles
        try:
            await bot.send_message(
                message.from_user.id,
                "⚠️ <b>Sistema Anti-Spam</b> ⚠️\n\n"
                "Se ha detectado un patrón inusual en tus interacciones recientes. "
                "Por favor, evita enviar mensajes repetitivos o muy frecuentes "
                "para mantener la calidad de la comunidad.\n\n"
                "Si continúas con este comportamiento, podrías ser silenciado temporalmente "
                "en el chat.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            # Si no podemos enviar mensaje privado, solo lo registramos pero continuamos
            logger.error(f"Error al enviar mensaje privado de spam: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error al notificar spam: {str(e)}")

@dp.message(lambda message: message.video_note is not None)
async def handle_video_note(message: types.Message):
    """Maneja mensajes con notas de video (video circulares)"""
    try:
        # Log para depuración
        logger.info(f"Nota de video recibida del usuario {message.from_user.username or message.from_user.first_name}")
        
        # Verificar si es spam antes de procesar
        if db.is_spam(message.from_user.id, 'video', message.chat.id):
            logger.warning(f"Spam de notas de video detectado del usuario {message.from_user.username or message.from_user.first_name} en el chat {message.chat.id}")
            # Notificar y aplicar medidas anti-spam
            await notify_spam_detected(message)
            return
            
        # Registrar interacción básica (sin puntos)
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='video',
            command_name=None,
            chat_id=message.chat.id
        )
        
        # Registrar como video pendiente de aprobación
        if db.register_pending_photo(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            message_id=message.message_id,
            chat_id=message.chat.id
        ):
            # Enviar notificación privada al usuario
            try:
                await bot.send_message(
                    chat_id=message.from_user.id,
                    text="🎥 Tu video circular ha sido registrado y está pendiente de aprobación. "
                         "Recibirás XP cuando un administrador lo apruebe."
                )
            except Exception as e:
                logger.error(f"Error al enviar mensaje privado: {str(e)}")
                # Si falla el mensaje privado, enviar en el grupo
                await message.reply(
                    "🎥 Tu video circular ha sido registrado y está pendiente de aprobación. "
                    "Recibirás XP cuando un administrador lo apruebe."
                )
            logger.info(f"Video circular de {message.from_user.username or message.from_user.first_name} registrado como pendiente de aprobación")
        
    except Exception as e:
        logger.error(f"Error al registrar interacción de nota de video: {str(e)}")
        
@dp.message(Command("configurar_dificultad"))
async def configurar_dificultad(message: types.Message):
    """Permite a los administradores configurar la dificultad de las especies para el juego"""
    try:
        # Verificar que el usuario sea administrador
        is_administrator = await is_admin(message.chat.id, message.from_user.id)
        if not is_administrator:
            await message.answer("⛔ Este comando solo puede ser utilizado por administradores.")
            return
            
        # Registrar interacción
        await db.log_user_interaction(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            interaction_type='command',
            command_name='configurar_dificultad',
            chat_id=message.chat.id
        )
        
        # Obtener argumentos del comando
        args = message.text.split()
        if len(args) != 3:
            await message.answer(
                "⚠️ <b>Formato incorrecto</b>\n\n"
                "Uso: <code>/configurar_dificultad [nombre_especie] [dificultad]</code>\n\n"
                "Ejemplo: <code>/configurar_dificultad \"Messor barbarus\" facil</code>\n\n"
                "Dificultades disponibles: <code>facil</code>, <code>medio</code>, <code>dificil</code>",
                parse_mode=ParseMode.HTML
            )
            return
            
        # Extraer nombre de especie y dificultad
        nombre_especie = args[1]
        dificultad = args[2].lower()
        
        # Validar dificultad
        if dificultad not in ['facil', 'medio', 'dificil']:
            await message.answer(
                "⚠️ <b>Dificultad inválida</b>\n\n"
                "Las dificultades disponibles son: <code>facil</code>, <code>medio</code>, <code>dificil</code>",
                parse_mode=ParseMode.HTML
            )
            return
            
        # Buscar la especie en la base de datos
        resultado = db.find_species_by_name(nombre_especie)
        if not resultado:
            await message.answer(
                f"❌ No se encontró la especie <b>{nombre_especie}</b> en la base de datos.",
                parse_mode=ParseMode.HTML
            )
            return
            
        # Establecer la dificultad
        if db.set_species_difficulty(resultado['id'], dificultad):
            await message.answer(
                f"✅ Dificultad establecida para <b>{nombre_especie}</b>: <b>{dificultad.capitalize()}</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                f"❌ Error al establecer la dificultad para <b>{nombre_especie}</b>.",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error en comando configurar_dificultad: {str(e)}")
        await message.answer("Error al configurar dificultad. Por favor, inténtalo de nuevo más tarde.")


@dp.callback_query(lambda c: c.data and c.data.startswith('lang:'))
async def handle_language_selection(callback_query: types.CallbackQuery):
    """Maneja la selección de idioma"""
    try:
        if not translation_manager:
            await callback_query.answer("❌ Sistema de traducción no disponible.")
            return
            
        language_code = callback_query.data.split(':')[1]
        user_id = callback_query.from_user.id
        chat_id = callback_query.message.chat.id
        username = callback_query.from_user.username
        first_name = callback_query.from_user.first_name
        
        # Guardar idioma en base de datos
        success = db.set_user_language(
            user_id=user_id,
            chat_id=chat_id,
            language_code=language_code,
            username=username,
            first_name=first_name
        )
        
        if success:
            lang_info = translation_manager.supported_languages.get(language_code, {})
            flag = lang_info.get('flag', '🌐')
            name = lang_info.get('name', language_code)
            
            if language_code == 'es':
                response = f"✅ {flag} Configurado como hispanohablante. No recibirás traducciones automáticas."
            else:
                response = (f"✅ {flag} Idioma configurado: {name}\n\n"
                          f"Ahora recibirás traducciones automáticas de los mensajes del grupo "
                          f"en tu idioma mediante mensajes privados.\n\n"
                          f"<b>Importante:</b> Debes iniciar una conversación privada conmigo (@AntmasterBot) "
                          f"para recibir las traducciones.")
            
            await callback_query.message.edit_text(response, parse_mode="HTML")
        else:
            await callback_query.message.edit_text("❌ Error al configurar el idioma.")
            
    except Exception as e:
        logger.error(f"Error seleccionando idioma: {str(e)}")
        await callback_query.answer("❌ Error al configurar idioma.")
async def init_session():
    """Inicializa la sesión HTTP global"""
    global global_session
    if global_session is None:
        global_session = aiohttp.ClientSession()
    
    # Establecer el tiempo de inicio del bot para evitar falsos positivos de spam
    if hasattr(db, 'bot_start_time'):
        db.bot_start_time = datetime.now()
    
    # Configurar el bot en el RewardsManager
    rewards_manager.set_bot(bot)
    
    return global_session

async def main():
    """Función principal del bot"""
    try:
        await init_session()
        logger.info("Bot iniciado correctamente")
        await dp.start_polling(bot)
    finally:
        await close_session()

if __name__ == '__main__':
    asyncio.run(main())
