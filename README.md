# 🐜 AntMasterBot

Un bot de Telegram especializado en mirmecología (estudio de las hormigas), desarrollado con Python y aiogram.

## ✨ Características Principales

- 🔍 **Búsqueda de Especies**: Información detallada sobre especies de hormigas
- 🎮 **Juegos Interactivos**: Adivina la especie de hormiga
- 📊 **Sistema de Ranking**: Puntuaciones y niveles de usuarios
- 🌍 **Múltiples Fuentes**: Integración con iNaturalist, AntWiki, AntMaps y AntOnTop
- 🤖 **IA Integrada**: Descripciones generadas con OpenAI
- 🎁 **Sistema de Recompensas**: Códigos de descuento y badges
- 🌐 **Multiidioma**: Soporte para múltiples idiomas

## 🛠️ Tecnologías Utilizadas

- **Python 3.8+**
- **aiogram 3.x** - Framework para bots de Telegram
- **MySQL** - Base de datos
- **OpenAI API** - Generación de descripciones con IA
- **aiohttp** - Peticiones HTTP asíncronas
- **BeautifulSoup4** - Web scraping

## 📋 Comandos Disponibles

### 🔍 Información y Búsqueda
- `/especie [nombre]` - Buscar información sobre especies de hormigas
- `/hormidato` - Dato curioso aleatorio sobre hormigas
- `/prediccion [ubicación]` - Predicción de vuelos nupciales

### 🎮 Juegos
- `/adivina_especie` - Juego para adivinar especies de hormigas

### 📊 Rankings y Estadísticas
- `/ranking` - Ver el ranking general de usuarios
- `/ranking_semanal` - Ver el ranking semanal
- `/ranking_mensual` - Ver el ranking mensual
- `/nivel` - Ver tu nivel y puntos

### 🎁 Recompensas
- `/recompensas` - Ver las recompensas disponibles
- `/mis_codigos` - Ver tus códigos de descuento
- `/validar_codigo [código]` - Validar un código de descuento

## 🚀 Instalación y Configuración

### Prerrequisitos
- Python 3.8 o superior
- MySQL Server
- Token de bot de Telegram
- API Keys de OpenAI y Google (opcional)

### Configuración

1. **Clonar el repositorio**
```bash
git clone https://github.com/inklord/Botantmaster.git
cd Botantmaster
```

2. **Crear entorno virtual**
```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

5. **Configurar base de datos**
```bash
mysql -u root -p < create_database.sql
python setup_db.py
```

6. **Ejecutar el bot**
```bash
python AntmasterBot.py
```

## 📁 Estructura del Proyecto

```
Botantmaster/
├── AntmasterBot.py          # Archivo principal del bot
├── database.py              # Gestión de base de datos
├── requirements.txt         # Dependencias Python
├── create_database.sql      # Script de creación de BD
├── translation_manager.py   # Gestión de idiomas
├── rewards_manager.py       # Sistema de recompensas
├── handlers/               # Manejadores de eventos
└── README.md              # Este archivo
```

## 🌐 APIs Integradas

- **iNaturalist** - Fotos y observaciones de especies
- **AntWiki** - Información enciclopédica
- **AntMaps** - Distribución geográfica
- **AntOnTop** - Información de cría
- **OpenAI** - Generación de descripciones
- **Google Custom Search** - Búsquedas web

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Para cambios importantes:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## 📞 Contacto

- **Proyecto**: [https://github.com/inklord/Botantmaster](https://github.com/inklord/Botantmaster)
- **Issues**: [https://github.com/inklord/Botantmaster/issues](https://github.com/inklord/Botantmaster/issues)

---

*Desarrollado con ❤️ para la comunidad mirmecológica* 