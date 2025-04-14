#  SDC Reactive Transfers Bot

Este bot automatiza la extracción y notificación de transferencias reactivas entre almacenes logísticos. Ejecuta consultas en una interfaz interna, agrupa los datos y los envía a salas de Amazon Chime a través de webhooks, todo de forma programada y concurrente.

---

##  Objetivo del Bot

- Extraer tablas HTML con datos de transferencias reactivas.
- Agrupar la información por ruta de proceso y almacén destino.
- Generar mensajes en formato Markdown para Amazon Chime.
- Enviar notificaciones automáticas a diferentes sites cada 15 minutos.
- Informar el estado del bot periódicamente a un webhook de monitoreo.

---

##  Tecnologías utilizadas

- Python 3.9+
- Selenium (automatización web)
- Requests (envío de webhooks)
- Pandas (procesamiento de datos)
- schedule (programación de tareas)
- retrying (reintentos automáticos)
- ThreadPoolExecutor (concurrencia)
- ChromeDriver Manager

---

##  Estructura del Proyecto

```bash
reactive_transfers_bot/
└── src/
    └── main.py                  # Script principal
```

---

##  Lógica General del Bot

1. Cada 15 minutos, se ejecuta una tarea programada que:
   - Visita una URL personalizada por site.
   - Extrae una tabla HTML y la convierte a DataFrame.
   - Agrupa los datos por columnas clave.
   - Formatea el resultado como tabla Markdown.
   - Envía la tabla a Amazon Chime vía webhook correspondiente.

2. Se incluye un webhook global de monitoreo para enviar:
   - Estado inicial al arrancar.
   - Estado resumido cada 6 horas.
   - Alertas si hay 4 fallos consecutivos.

---

##  Ejecución del Script

```bash
python src/main.py
```

Esto iniciará el bot, ejecutará el primer ciclo y quedará corriendo indefinidamente.

---

##  Webhooks y configuración

En el script se define la configuración de sites y webhooks de esta forma:

```python
SITES_CONFIG = {
    "sites": ["X123", "Y456"],
    "base_url": "https://internal.amazon.com",
    "webhooks": {
        "X123": "https://hooks.chime.aws/incomingwebhooks/...",
        "Y456": "https://hooks.chime.aws/incomingwebhooks/..."
    }
}
```

El bot verifica al inicio que todos los sites tengan un webhook correspondiente.

---

## 🔧 Reintentos y robustez

- El bot utiliza `@retry` para reintentar peticiones fallidas hasta 3 veces con un intervalo de 2 segundos.
- Si una ejecución tiene más de 4 fallos seguidos, se detiene y notifica vía webhook.
- El bot maneja errores de timeout y de cierre del navegador.

---

## 📑 Ejemplo de mensaje enviado

```markdown
/md ## Reactive Transfers
| Process Path | Destination Warehouse | Need To Ship By Date | Work Pool | Total Quantity |
|--------------|------------------------|-----------------------|-----------|----------------|
| IBToOB       | DQH2                   | 2024-04-14            | DE        | 120            |
| OBToOB       | BCN1                   | 2024-04-15            | FR        | 75             |
```

---
