import asyncio
import aiohttp
import logging
import json
import time
import os
import requests
from typing import Dict, List, Optional, Tuple
from database import AntDatabase
from bs4 import BeautifulSoup
import backoff
from urllib.parse import quote
from deep_translator import GoogleTranslator

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes
TIMEOUT = 30
MAX_CONCURRENT_REQUESTS = 5
RETRY_DELAY = 5
BATCH_SIZE = 10
INATURALIST_API = 'https://api.inaturalist.org/v1/taxa?q='
ANTWIKI_API = 'https://www.antwiki.org/wiki/'
ANTMAPS_API = 'https://antmaps.org/api/v01'
ANTFLIGHTS_API = 'https://antflights.com'

# Crear semáforo para limitar solicitudes concurrentes
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# Inicializar la base de datos
db = AntDatabase('localhost', 'root', 'BFXNH2Ncj1kh@23', 'antmaster')

@backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=3)
async def make_request(session: aiohttp.ClientSession, url: str, params: Optional[Dict] = None, is_json: bool = True) -> Optional[Dict]:
    """Realiza una solicitud HTTP con reintentos automáticos
    
    Args:
        session: Sesión HTTP
        url: URL a la que hacer la solicitud
        params: Parámetros de la solicitud
        is_json: Si es True, intenta parsear la respuesta como JSON. Si es False, devuelve el texto.
    """
    async with semaphore:  # Limitar solicitudes concurrentes
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    if is_json:
                        return await response.json()
                    else:
                        return await response.text()
                elif response.status == 429:  # Too Many Requests
                    retry_after = int(response.headers.get('Retry-After', RETRY_DELAY))
                    print(f"Rate limit alcanzado. Esperando {retry_after} segundos...")
                    await asyncio.sleep(retry_after)
                    return await make_request(session, url, params, is_json)  # Reintentar
                elif response.status == 404:
                    print(f"Recurso no encontrado: {url}")
                    return None
                else:
                    print(f"Error en la solicitud: {response.status} - {url}")
                    return None
        except asyncio.TimeoutError:
            print(f"Timeout en la solicitud a {url}")
            return None
        except aiohttp.ClientError as e:
            print(f"Error en la solicitud: {str(e)} - {url}")
            return None
        except Exception as e:
            print(f"Error inesperado: {str(e)} - {url}")
            return None

async def buscar_en_inaturalist(query):
    """Busca información de la especie en iNaturalist."""
    try:
        logger.info(f"Buscando en iNaturalist: {query}")
        url = f"{INATURALIST_API}{quote(query)}&rank=species"
        
        async with aiohttp.ClientSession() as session:
            data = await make_request(session, url)
            
            if data and data.get('total_results', 0) > 0 and data.get('results'):
                result = data['results'][0]
                
                # Obtener más detalles usando el ID de la especie
                details_url = f"https://api.inaturalist.org/v1/taxa/{result['id']}"
                details_data = await make_request(session, details_url)
                
                # Traducir la descripción si está en inglés y limpiar etiquetas HTML
                description = None
                if details_data and details_data.get('results', [{}])[0].get('wikipedia_summary'):
                    description = details_data['results'][0]['wikipedia_summary']
                    # Limpiar etiquetas HTML
                    soup = BeautifulSoup(description, 'html.parser')
                    description = ' '.join(soup.stripped_strings)
                    
                    if any(char in description for char in 'abcdefghijklmnopqrstuvwxyz'):
                        try:
                            translator = GoogleTranslator(source='en', target='es')
                            description = translator.translate(description)
                        except Exception as e:
                            logger.error(f"Error al traducir descripción: {str(e)}")

                # Obtener la foto principal
                photo_url = None
                if result.get('default_photo'):
                    photo_url = result['default_photo'].get('medium_url')
                elif result.get('photos'):
                    photo_url = result['photos'][0].get('medium_url')

                # Limpiar cualquier texto HTML en otros campos
                def clean_html(text):
                    if text:
                        soup = BeautifulSoup(text, 'html.parser')
                        return ' '.join(soup.stripped_strings)
                    return text

                # Limpiar características si existen
                characteristics = []
                if result.get('characteristics'):
                    characteristics = [clean_html(char) for char in result.get('characteristics', [])]

                return {
                    'id': str(result.get('id')),
                    'photo_url': photo_url,
                    'observations': result.get('observations_count', 0),
                    'description': description,
                    'measurements': {
                        'queen_size': clean_html(result.get('measurements', {}).get('queen_size')),
                        'worker_size': clean_html(result.get('measurements', {}).get('worker_size')),
                        'colony_size': clean_html(result.get('measurements', {}).get('colony_size'))
                    },
                    'characteristics': characteristics,
                    'habitat': clean_html(result.get('habitat')),
                    'behavior': clean_html(result.get('behavior'))
                }
        return None
    except Exception as e:
        logger.error(f"Error en búsqueda de iNaturalist: {str(e)}")
        return None

def construir_url_antwiki(genus: str, species: str) -> str:
    """Construye la URL para buscar en AntWiki"""
    return f"https://www.antwiki.org/wiki/{genus}_{species}"

async def buscar_foto_antwiki(genus, species):
    """Busca información detallada de la especie en AntWiki"""
    try:
        url = construir_url_antwiki(genus, species)
        logger.info(f"Buscando información en AntWiki: {url}")
        
        # Aumentar el timeout a 30 segundos
        response = requests.get(url, timeout=30)
        
        if response.status_code == 404:
            # Intentar con variante del nombre
            url_alt = url.replace("_nigrocinta", "_nigrocincta")
            if url != url_alt:
                logger.info(f"URL original no encontrada, intentando con: {url_alt}")
                response = requests.get(url_alt, timeout=30)
        
        info = {
            'photo_url': None,
            'queen_size': None,
            'worker_size': None,
            'colony_size': None,
            'characteristics': [],
            'habitat': None,
            'behavior': None
        }
        
        def clean_html(text):
            if text:
                soup = BeautifulSoup(text, 'html.parser')
                return ' '.join(soup.stripped_strings)
            return text
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscar foto en la tabla de información (infobox)
            infobox = soup.find('table', {'class': 'infobox'})
            if infobox:
                # Buscar foto
                for img in infobox.find_all('img'):
                    src = img.get('src', '')
                    if src and not src.endswith(('.svg', '.png')) and 'icon' not in src.lower():
                        if src.startswith('//'):
                            info['photo_url'] = f"https:{src}"
                        elif src.startswith('/'):
                            info['photo_url'] = f"https://www.antwiki.org{src}"
                        else:
                            info['photo_url'] = src
                        break
                
                # Buscar información en la tabla
                for row in infobox.find_all('tr'):
                    header = row.find('th')
                    value = row.find('td')
                    if header and value:
                        header_text = clean_html(header.get_text()).lower()
                        value_text = clean_html(value.get_text())
                        
                        if 'queen' in header_text and ('size' in header_text or 'length' in header_text):
                            info['queen_size'] = value_text
                        elif 'worker' in header_text and ('size' in header_text or 'length' in header_text):
                            info['worker_size'] = value_text
                        elif 'colony' in header_text and 'size' in header_text:
                            info['colony_size'] = value_text
                        elif 'habitat' in header_text:
                            info['habitat'] = value_text
            
            # Buscar características en el contenido principal
            content = soup.find('div', {'id': 'mw-content-text'})
            if content:
                # Buscar secciones relevantes
                sections = ['Description', 'Descripción', 'Biology', 'Biología', 'Behavior', 'Comportamiento']
                for section in sections:
                    section_header = content.find(['h2', 'h3'], string=section)
                    if section_header:
                        next_elem = section_header.find_next_sibling()
                        while next_elem and next_elem.name not in ['h2', 'h3']:
                            if next_elem.name == 'p':
                                text = clean_html(next_elem.get_text())
                                if text:
                                    # Traducir si está en inglés
                                    if any(char in text.lower() for char in 'abcdefghijklmnopqrstuvwxyz'):
                                        try:
                                            translator = GoogleTranslator(source='en', target='es')
                                            text = translator.translate(text)
                                        except Exception as e:
                                            logger.error(f"Error al traducir texto: {str(e)}")
                                    info['characteristics'].append(text)
                            next_elem = next_elem.find_next_sibling()
            
            # Si no se encontró foto en infobox, buscar en otros lugares
            if not info['photo_url']:
                # Buscar en la galería
                gallery = soup.find('div', {'class': 'gallery'})
                if gallery:
                    for img in gallery.find_all('img'):
                        src = img.get('src', '')
                        if src and not src.endswith(('.svg', '.png')) and 'icon' not in src.lower():
                            if src.startswith('//'):
                                info['photo_url'] = f"https:{src}"
                            elif src.startswith('/'):
                                info['photo_url'] = f"https://www.antwiki.org{src}"
                            else:
                                info['photo_url'] = src
                            break
            
            # Buscar en cualquier parte de la página
            if not info['photo_url']:
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if src and not src.endswith(('.svg', '.png')) and 'icon' not in src.lower():
                        if src.startswith('//'):
                            info['photo_url'] = f"https:{src}"
                        elif src.startswith('/'):
                            info['photo_url'] = f"https://www.antwiki.org{src}"
                        else:
                            info['photo_url'] = src
                            break
                
        return info
                    
    except Exception as e:
        logger.error(f"Error al buscar información en AntWiki: {str(e)}")
        return None

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

async def buscar_info_antontop(species_name):
    """Busca información de la especie en AntOnTop."""
    try:
        logger.info(f"Buscando en AntOnTop: {species_name}")
        
        # Normalizar el nombre científico para la URL (convertir espacios a guiones)
        species_url_name = species_name.lower().replace(' ', '-')
        url = f"https://antontop.com/es/{species_url_name}/"
        logger.info(f"URL de búsqueda en AntOnTop: {url}")
        
        def clean_html(text):
            if text:
                soup = BeautifulSoup(text, 'html.parser')
                return ' '.join(soup.stripped_strings)
            return text
        
        # Realizar la solicitud con un timeout adecuado
        async with aiohttp.ClientSession() as session:
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
                    info['short_description'] = clean_html(short_desc_div.get_text())
                
                # Buscar la descripción completa
                description_section = soup.find('div', {'class': 'woocommerce-Tabs-panel--description'})
                if description_section:
                    info['description'] = clean_html(description_section.get_text())
                
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
                                key = clean_html(cells[0].get_text()).lower()
                                value = clean_html(cells[1].get_text())
                                
                                if 'dificultad' in key or 'difficulty' in key:
                                    info['difficulty'] = value
                                elif 'comportamiento' in key or 'behavior' in key:
                                    info['behavior'] = value
                                elif 'origen' in key or 'origin' in key:
                                    info['region'] = value
                                elif 'temperatura' in key or 'temperature' in key:
                                    info['temperature'] = value
                                elif 'humedad' in key or 'humidity' in key:
                                    info['humidity'] = value
                                elif 'reina' in key or 'queen' in key:
                                    info['queen_size'] = value
                                elif 'obrera' in key or 'worker' in key:
                                    info['worker_size'] = value
                                elif 'colonia' in key or 'colony' in key:
                                    info['colony_size'] = value
                
                # Si no se encuentra información suficiente, retornar None
                if not info['short_description'] and not info['description']:
                    logger.warning(f"No se encontró descripción en AntOnTop para {species_name}")
                    return None
                
                logger.info(f"Información obtenida de AntOnTop para {species_name}")
                return info
    
    except Exception as e:
        logger.error(f"Error al buscar en AntOnTop: {str(e)}")
        return None

async def procesar_especie(db: AntDatabase, especie: str, region: Optional[str] = None) -> tuple:
    """Procesa una especie y la agrega a la base de datos."""
    try:
        # Separar nombre científico y subespecie
        partes = especie.split(' ')
        if len(partes) < 2:
            logger.error(f"Nombre de especie inválido: {especie}")
            return False, {}
            
        nombre_cientifico = ' '.join(partes[:2])
        subespecie = ' '.join(partes[2:]) if len(partes) > 2 else None
        
        # Verificar si la especie ya existe
        if db.get_species(nombre_cientifico):
            logger.info(f"La especie {nombre_cientifico} ya existe en la base de datos")
            return True, {}
            
        # Recopilar información de todas las fuentes
        info = {}
        
        # Buscar en iNaturalist
        inaturalist_info = await buscar_en_inaturalist(nombre_cientifico)
        if inaturalist_info:
            info.update(inaturalist_info)
            if inaturalist_info.get('photo_url'):
                info['inaturalist_photo'] = inaturalist_info['photo_url']
        
        # Buscar en AntWiki
        genus, species = nombre_cientifico.split(' ')
        antwiki_info = await buscar_foto_antwiki(genus, species)
        if antwiki_info and antwiki_info.get('photo_url'):
            info['antwiki_photo'] = antwiki_info['photo_url']
            
        # Buscar en AntMaps
        antmaps_info = await obtener_distribucion_antmaps(nombre_cientifico)
        if antmaps_info:
            info['distribution'] = antmaps_info
            
        # Buscar en AntOnTop
        antontop_info = await buscar_info_antontop(nombre_cientifico)
        if antontop_info:
            info.update(antontop_info)
            if antontop_info.get('photo_url'):
                info['antontop_photo'] = antontop_info['photo_url']
        
        # Preparar datos para la base de datos
        species_data = {
            'scientific_name': nombre_cientifico,
            'subspecies': subespecie,
            'description': info.get('description'),
            'habitat': info.get('habitat'),
            'behavior': info.get('behavior'),
            'distribution': info.get('distribution'),
            'photo_url': info.get('inaturalist_photo') or info.get('antwiki_photo') or info.get('antontop_photo'),
            'queen_size': info.get('measurements', {}).get('queen_size'),
            'worker_size': info.get('measurements', {}).get('worker_size'),
            'colony_size': info.get('measurements', {}).get('colony_size'),
            'region': region
        }
        
        # Agregar la especie a la base de datos
        if db.add_species(species_data):
            logger.info(f"Especie {nombre_cientifico} agregada exitosamente")
            return True, info
        else:
            logger.error(f"Error al agregar la especie {nombre_cientifico}")
            return False, info
            
    except Exception as e:
        logger.error(f"Error procesando especie {especie}: {str(e)}")
        return False, {}

async def cargar_especies_desde_archivo(filename: str, start_line: int = 1, region: Optional[str] = None):
    """Carga y procesa especies desde un archivo línea por línea."""
    try:
        if not os.path.exists(filename):
            logger.error(f"El archivo {filename} no existe")
            return

        with open(filename, 'r', encoding='utf-8') as file:
            especies = file.readlines()

        # Filtrar especies desde la línea inicial
        especies = [esp.strip() for esp in especies[start_line-1:] if esp.strip()]
        total_especies = len(especies)
        procesadas = 0
        exitosas = 0
        fallidas = 0

        logger.info(f"Cargando {total_especies} especies desde el archivo {filename}, comenzando desde la línea {start_line}")

        for especie in especies:
            procesadas += 1
            logger.info(f"\nProcesando especie {procesadas}/{total_especies}: {especie}")
            
            try:
                success, info = await procesar_especie(db, especie, region)
                
                if success:
                    exitosas += 1
                    # Mostrar enlaces de imágenes si están disponibles
                    if info.get('inaturalist_photo'):
                        print(f"Foto iNaturalist: {info['inaturalist_photo']}")
                    if info.get('antwiki_photo'):
                        print(f"Foto AntWiki: {info['antwiki_photo']}")
                    if info.get('antontop_photo'):
                        print(f"Foto AntOnTop: {info['antontop_photo']}")
                else:
                    fallidas += 1
                    logger.warning(f"No se pudo procesar la especie: {especie}")
                
                # Pequeña pausa para evitar sobrecargar las APIs
                await asyncio.sleep(1)
                
            except Exception as e:
                fallidas += 1
                logger.error(f"Error procesando {especie}: {str(e)}")
                continue

            # Mostrar progreso
            if procesadas % 10 == 0:
                logger.info(f"Progreso: {procesadas}/{total_especies} especies procesadas. Exitosas: {exitosas}, Fallidas: {fallidas}")

        logger.info(f"\nProceso completado. Total procesadas: {procesadas}")
        logger.info(f"Exitosas: {exitosas}")
        logger.info(f"Fallidas: {fallidas}")

    except Exception as e:
        logger.error(f"Error al cargar especies desde archivo: {str(e)}")

async def main():
    """Función principal"""
    start_time = time.time()
    
    # Cargar especies desde el archivo
    await cargar_especies_desde_archivo("especies_hormigas.txt", start_line=2)
    
    end_time = time.time()
    print(f"\nTiempo total de ejecución: {end_time - start_time:.2f} segundos")

if __name__ == "__main__":
    asyncio.run(main()) 