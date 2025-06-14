# Sistema de Notificaciones de Nivel - AntmasterBot

## 🎉 Introducción

El bot AntmasterBot cuenta con un sistema completo de notificaciones que alerta a los usuarios cuando suben de nivel y les informa sobre las recompensas disponibles.

## 🔔 Tipos de Notificaciones

### 1. Notificación de Subida de Nivel (Grupo)
Cuando un usuario sube de nivel, **todos** en el grupo ven una notificación pública que incluye:

```
🎉 ¡LEVEL UP! 🎉

🌿 @usuario ha alcanzado el NIVEL 10! 🌿
🏅 Badge: Iniciado
⚡ XP Total: 1,575
🎯 Para Nivel 11: 315 XP restantes

🎁 ¡RECOMPENSA ESPECIAL DESBLOQUEADA! 🎁
📦 🌿 Descuento 5% + Badge 'Iniciado'
📝 Descuento del 5% en la tienda y badge especial
🔑 Código: **ABC123XYZ**

💬 Para reclamar tu recompensa, contacta con un administrador.

🌟 ¡Gracias por tu participación en la comunidad Antmaster! 🌟
```

### 2. Notificación Privada (Solo para Usuario)
Si la recompensa incluye códigos o información sensible, el usuario recibe un mensaje privado detallado:

```
🎉 ¡Felicitaciones por alcanzar el NIVEL 10! 🎉

🎁 RECOMPENSA ESPECIAL DESBLOQUEADA
📦 🌿 Descuento 5% + Badge 'Iniciado'
📝 Descuento del 5% en la tienda y badge especial

🔑 Tu código de recompensa: `ABC123XYZ`

📋 Instrucciones:
1. Copia este código
2. Contacta con un administrador en el grupo
3. Presenta tu código para reclamar la recompensa

🏅 Tu nuevo badge: Iniciado
⚡ XP Total: 1,575

🌟 ¡Gracias por ser parte de la comunidad Antmaster! 🌟
```

## 🏆 Sistema de Recompensas

### Niveles con Recompensas Especiales

| Nivel | Badge | Recompensa | Tipo |
|-------|-------|------------|------|
| 5 | 🌱 Principiante | Acceso a comandos avanzados | Automática |
| 10 | 🌿 Iniciado | Descuento 5% + Badge | Código |
| 15 | 🌳 Experimentado | Kit básico de hormigas | Físico |
| 25 | ⭐ Avanzado | Descuento 10% + Badge | Código |
| 35 | 🔥 Experto | Kit intermedio de hormigas | Físico |
| 50 | 💎 Maestro | Badge + Kit avanzado | Físico Premium |
| 75 | 👑 Elite | Badge + Tarjeta regalo 50€ | Premio Grande |
| 100 | 🏆 Leyenda | Badge + Tarjeta regalo 100€ | Premio Máximo |

### Tipos de Recompensas

1. **Automáticas**: Se activan inmediatamente (ej: acceso a comandos)
2. **Códigos**: Requieren contactar administrador con código único
3. **Físicas**: Kits que se envían por correo postal
4. **Premios**: Tarjetas regalo y beneficios económicos

## 📊 Comandos Relacionados

### `/nivel`
Muestra información detallada del progreso personal:
- Nivel actual y badge
- XP total y progreso al siguiente nivel
- Posición en el ranking del chat
- Próximas 2 recompensas con tiempo estimado
- Consejos para ganar XP

### `/recompensas`
Lista completa del sistema de recompensas:
- Todas las recompensas disponibles por nivel
- Estado (obtenida/pendiente) para el usuario
- Descripción detallada de cada recompensa
- Instrucciones para reclamar premios
- Información sobre cómo ganar XP

### `/ranking`
Muestra el ranking actual del chat con niveles y XP

## 🎮 Cómo Ganar XP

### Actividades que Otorgan XP
- **Mensajes de calidad** (3+ palabras): +1 XP
- **Fotos/videos de hormigas**: +5 XP
- **Comandos informativos** (/especie, /hormidato): +2 XP
- **Ganar en /adivina_especie**: +10 XP
- **Fotos aprobadas por admins**: +25 XP

### Limitaciones y Filtros
- **Límite diario**: Máximo 100 XP por día
- **Filtro de calidad**: Mensajes de 1-2 palabras no otorgan XP
- **Filtro anti-spam**: Mensajes repetitivos se ignoran
- **Cooldown**: Algunas actividades tienen tiempo de espera

## 🔧 Funcionamiento Técnico

### Detección de Subida de Nivel
```python
# En rewards_manager.py - actualizar_experiencia()
if nuevo_nivel > nivel_anterior:
    await self.notificar_subida_nivel(user_id, chat_id, nuevo_nivel)
    await self.verificar_recompensas(user_id, chat_id, nuevo_nivel)
```

### Generación de Códigos
- Códigos únicos de 9 caracteres alfanuméricos
- Se generan automáticamente para recompensas con descuentos
- Se almacenan en la base de datos para verificación

### Base de Datos
- Tabla `user_experience`: XP total, nivel actual, último mensaje
- Tabla `user_rewards`: Recompensas otorgadas y reclamadas
- Tabla `user_interactions`: Historial de actividades para XP

## 🚀 Beneficios del Sistema

### Para Usuarios
- **Motivación constante**: Progreso visible y recompensas regulares
- **Reconocimiento público**: Celebración en el grupo al subir de nivel
- **Recompensas tangibles**: Kits físicos y beneficios económicos
- **Transparencia**: Información clara sobre próximas metas

### Para la Comunidad
- **Mayor participación**: Incentiva actividad de calidad
- **Gamificación saludable**: Competencia amistosa entre miembros
- **Retención de usuarios**: Metas a largo plazo mantienen engagement
- **Calidad del contenido**: Filtros aseguran contribuciones valiosas

## 📈 Métricas y Seguimiento

### KPIs Monitoreados
- Tiempo promedio para alcanzar niveles clave
- Porcentaje de usuarios que alcanzan cada nivel
- Actividad diaria promedio antes/después de subir nivel
- Tasa de retención después de obtener recompensas

### Logs y Depuración
- Todas las notificaciones se registran en logs
- Errores en envío de mensajes privados se manejan graciosamente
- Códigos de recompensa se almacenan para auditoría
- Historial completo de interacciones disponible

## 🔮 Futuras Mejoras

### Características Planificadas
- Notificaciones push para usuarios con la app
- Integración con sistema de puntos de la tienda
- Recompensas estacionales y eventos especiales
- Sistema de badges avanzado con colecciones
- Leaderboards globales entre múltiples grupos

### Optimizaciones Técnicas
- Cache de cálculos de nivel para mejor rendimiento
- Batch processing para notificaciones masivas
- A/B testing para diferentes tipos de notificaciones
- Analytics avanzados sobre comportamiento de usuarios 