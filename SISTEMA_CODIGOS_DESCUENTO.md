# Sistema Automático de Códigos de Descuento - AntmasterBot

## 🎯 Introducción

El sistema automático de códigos de descuento permite generar, validar y gestionar códigos promocionales de manera completamente automatizada. Los usuarios reciben códigos automáticamente al subir de nivel, y los administradores pueden crear códigos promocionales personalizados.

## 🏗️ Arquitectura del Sistema

### Componentes Principales

1. **DiscountCodeManager** - Gestiona toda la lógica de códigos
2. **Tablas de Base de Datos** - Almacenan códigos y usos
3. **Integración con RewardsManager** - Genera códigos automáticamente
4. **Comandos de Usuario** - Interfaz para gestionar códigos
5. **Comandos de Administrador** - Crear códigos promocionales

### Base de Datos

```sql
-- Tabla principal de códigos
CREATE TABLE discount_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    discount_type ENUM('percentage', 'fixed', 'shipping', 'bogo'),
    discount_value DECIMAL(10,2) NOT NULL,
    min_purchase_amount DECIMAL(10,2) DEFAULT 0,
    max_uses INT DEFAULT 1,
    current_uses INT DEFAULT 0,
    user_id BIGINT,                    -- Usuario específico (opcional)
    created_for_level INT,             -- Nivel que otorgó el código
    expires_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT
);

-- Tabla de historial de uso
CREATE TABLE discount_code_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    discount_code_id INT,
    user_id BIGINT NOT NULL,
    username VARCHAR(255),
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    purchase_amount DECIMAL(10,2),
    discount_applied DECIMAL(10,2),
    chat_id BIGINT
);
```

## 🎫 Tipos de Códigos de Descuento

### 1. Códigos de Nivel (Automáticos)
**Generación**: Automática al subir de nivel
**Formato**: `LVL{nivel}{código}`
**Duración**: 6 meses
**Usos**: 1 (personal)

```
Nivel 10:  LVL10ABC123 - 5% descuento
Nivel 25:  LVL25XYZ789 - 10% descuento  
Nivel 50:  LVL50DEF456 - 15% descuento
Nivel 75:  LVL75GHI123 - 50€ descuento fijo
Nivel 100: LVL100JKL789 - 100€ descuento fijo
```

### 2. Códigos Promocionales (Manuales)
**Generación**: Manual por administradores
**Formato**: `{PREFIJO}{código}`
**Duración**: Configurable
**Usos**: Configurable

**Tipos disponibles:**
- **Porcentaje** (`percentage`): 5%, 10%, 20%, etc.
- **Fijo** (`fixed`): 5€, 10€, 20€, etc.
- **Envío gratuito** (`shipping`): Elimina costos de envío
- **Compra uno, lleva otro** (`bogo`): Ofertas especiales

## 🤖 Generación Automática

### Proceso de Generación
1. Usuario sube de nivel (detectado en `rewards_manager.py`)
2. Se verifica si el nivel otorga códigos de descuento
3. Se genera código único con prefijo específico
4. Se almacena en base de datos con expiración de 6 meses
5. Se notifica al usuario públicamente y por privado
6. Se registra en sistema de recompensas

### Código de Ejemplo
```python
# En rewards_manager.py - notificar_subida_nivel()
if nuevo_nivel in [10, 25, 50, 75, 100]:
    codigo_descuento = self.discount_manager.create_level_reward_code(
        user_id=user_id, 
        level=nuevo_nivel, 
        username=username
    )
```

## 👤 Comandos de Usuario

### `/mis_codigos`
**Función**: Muestra todos los códigos del usuario
**Información mostrada**:
- Código único
- Tipo y valor del descuento
- Fecha de expiración
- Estado (disponible/usado/expirado)
- Compra mínima requerida
- Descripción

**Ejemplo de respuesta**:
```
🎫 Tus Códigos de Descuento

1. LVL10ABC123
   💰 5% de descuento
   📅 Expira: 15/11/2025
   📊 Estado: ✅ DISPONIBLE (1 usos)
   📝 Descuento 5% por alcanzar nivel 10

2. WELCOMEXYZ789
   💰 10% de descuento
   📅 Expira: 30/08/2025
   📊 Estado: ✅ DISPONIBLE (1 usos)
   🛒 Compra mínima: 30€
   📝 Código de bienvenida para nuevos usuarios
```

### `/validar_codigo [código]`
**Función**: Valida un código específico
**Parámetros**: Código a validar
**Información mostrada**:
- Validez del código
- Tipo y valor del descuento
- Fecha de expiración
- Usos restantes
- Compra mínima
- Ejemplo de descuento

**Ejemplo de uso**:
```
/validar_codigo LVL10ABC123

✅ Código Válido

🎫 Código: LVL10ABC123
💰 Descuento: 5% de descuento
📅 Expira: 15/11/2025 a las 19:21
🔢 Usos restantes: 1
📝 Descripción: Descuento 5% por alcanzar nivel 10

💡 Ejemplo con compra de 50€:
   • Descuento aplicado: 2.5€
   • Precio final: 47.5€

✅ ¡Este código está listo para usar!
```

## 👑 Comandos de Administrador

### `/crear_codigo_promo`
**Función**: Crear códigos promocionales personalizados
**Formato**: `/crear_codigo_promo [tipo] [valor] [usos] [días] [compra_min] [descripción]`

**Parámetros**:
- **tipo**: `percentage`, `fixed`, `shipping`, `bogo`
- **valor**: Valor numérico del descuento
- **usos**: Máximo número de usos (default: 100)
- **días**: Días hasta expirar (default: 30)  
- **compra_min**: Compra mínima en € (default: 0)
- **descripción**: Texto descriptivo (opcional)

**Ejemplos de uso**:
```bash
# Descuento del 15% con 50 usos, válido 60 días, compra mín 25€
/crear_codigo_promo percentage 15 50 60 25 Descuento especial verano

# Descuento fijo de 20€ con 100 usos, válido 30 días
/crear_codigo_promo fixed 20 100 30

# Envío gratuito con 200 usos, válido 45 días, compra mín 25€
/crear_codigo_promo shipping 0 200 45 25
```

**Respuesta del sistema**:
```
✅ Código Promocional Creado

🎫 Código: PROMOXYZ123
💰 Descuento: 15% de descuento
🔢 Usos máximos: 50
📅 Expira: 30/07/2025
🛒 Compra mínima: 25€
📝 Descripción: Descuento especial verano

📋 Para compartir:
🎉 ¡Código promocional disponible!
🎫 Código: PROMOXYZ123
💰 15% de descuento
📅 Válido hasta: 30/07/2025
🏃‍♂️ ¡Úsalo antes de que se agote!
```

## 🔧 Validación y Seguridad

### Validaciones Implementadas
1. **Existencia**: Código existe en base de datos
2. **Actividad**: Código está activo
3. **Expiración**: No ha pasado fecha límite
4. **Usos máximos**: No se ha agotado
5. **Usuario específico**: Si es personal, validar propietario
6. **Compra mínima**: Monto cumple requisitos
7. **Uso previo**: Usuario no lo ha usado antes (códigos de un uso)

### Errores Manejados
- `NOT_FOUND`: Código no existe
- `EXPIRED`: Código expirado
- `MAX_USES_REACHED`: Usos agotados
- `MIN_PURCHASE_NOT_MET`: Compra mínima no alcanzada
- `WRONG_USER`: Código para otro usuario
- `ALREADY_USED`: Ya usado anteriormente
- `SYSTEM_ERROR`: Error interno

## 📊 Estadísticas y Monitoreo

### Métricas Disponibles
```python
# Obtener estadísticas de uso
stats = discount_manager.get_usage_stats(days=30)

# Información incluida:
# - Total de códigos usados
# - Descuento total otorgado
# - Descuento promedio
# - Usuarios únicos
# - Códigos más populares
```

### Limpieza Automática
```python
# Limpiar códigos expirados
expired_count = discount_manager.cleanup_expired_codes()
```

## 🚀 Instalación y Configuración

### 1. Instalación Inicial
```bash
python install_discount_system.py
```

### 2. Pruebas del Sistema
```bash
python install_discount_system.py --test
```

### 3. Integración con Bot
El sistema se integra automáticamente al reiniciar el bot después de la instalación.

### 4. Configuración de Variables
Asegurar que las variables de entorno de base de datos estén configuradas en `.env`:
```
DB_HOST=localhost
DB_USER=usuario
DB_PASSWORD=contraseña
DB_NAME=antmaster_db
```

## 📈 Flujo de Trabajo Completo

### Para Usuario Nuevo
1. **Registro**: Primera interacción crea perfil de XP
2. **Progreso**: Gana XP interactuando (mensajes, fotos, juegos)
3. **Nivel 10**: Recibe primer código automáticamente (5% descuento)
4. **Notificación**: Mensaje público + privado con código
5. **Gestión**: Usa `/mis_codigos` para ver códigos disponibles
6. **Validación**: Usa `/validar_codigo` para verificar antes de usar
7. **Uso**: Contacta administrador para aplicar en compra

### Para Administrador
1. **Promociones**: Crea códigos con `/crear_codigo_promo`
2. **Distribución**: Comparte códigos en el grupo
3. **Monitoreo**: Revisa uso y estadísticas
4. **Gestión**: Limpia códigos expirados periódicamente

## 🎁 Beneficios del Sistema

### Para Usuarios
- **Recompensas automáticas** por participación activa
- **Códigos personales** con expiración extendida (6 meses)
- **Validación fácil** antes de usar
- **Gestión centralizada** de todos sus códigos
- **Transparencia total** sobre descuentos disponibles

### Para Administradores
- **Generación automática** sin intervención manual
- **Flexibilidad total** para crear promociones
- **Estadísticas detalladas** de uso
- **Seguridad robusta** contra fraudes
- **Escalabilidad** para crecimiento futuro

### Para el Negocio
- **Aumenta participación** en la comunidad
- **Fomenta compras** con descuentos personalizados
- **Reduce fricción** en proceso de compra
- **Mejora retención** de usuarios activos
- **Proporciona datos** para análisis de comportamiento

## 🔮 Futuras Mejoras

### Características Planificadas
- **Códigos QR** para uso en tienda física
- **Integración directa** con e-commerce
- **Códigos dinámicos** basados en comportamiento
- **Sistema de referidos** con códigos compartibles
- **Gamificación avanzada** con códigos especiales
- **API externa** para validación en tiempo real
- **Dashboard admin** para gestión visual
- **Notificaciones push** para códigos próximos a expirar

### Optimizaciones Técnicas
- **Cache distribuido** para mejor rendimiento
- **Análisis predictivo** de uso de códigos
- **A/B testing** para diferentes tipos de códigos
- **Integración blockchain** para códigos únicos verificables 