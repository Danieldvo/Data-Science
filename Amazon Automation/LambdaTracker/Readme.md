# 🛠️ Reactive Transfers Bot Monitor (AWS Lambda)

Este proyecto implementa una **Lambda en AWS** que monitoriza la salud de un bot (ejemplo: `sdc-reactive-transfers-bot`) a partir de los **CloudWatch Logs**.  
La Lambda comprueba si en una ventana de tiempo se han producido ejecuciones completas (`Starting job execution` ➜ `Job execution completed`).  
En caso contrario, marca el bot como **UNHEALTHY** en DynamoDB y lo registra como detenido.

---

## 📌 Arquitectura

- **AWS Lambda**: ejecuta el script de verificación.  
- **Amazon CloudWatch Logs**: fuente de eventos del bot a monitorizar.  
- **Amazon DynamoDB**: almacena  
  - eventos de tipo `stopped` cuando se detecta fallo,  
  - un **control item** para evitar alertas repetidas (cooldown).  
- **Amazon EventBridge**: planifica la ejecución periódica de la Lambda (ejemplo: cada 15 min).  

---

## ⚙️ Flujo de funcionamiento

1. **EventBridge** invoca la Lambda según la frecuencia configurada (p. ej. `cron(0/15 * * * ? *)`).  
2. La Lambda consulta los eventos recientes en **CloudWatch Logs** (`LOG_GROUP`) durante una ventana (`WINDOW_MINUTES`).  
3. Se extraen los marcadores:
   - `"Starting job execution"`
   - `"Job execution completed"`
4. Se cuentan los pares válidos (`start` ➜ `completed`).  
5. Resultado:  
   - ✅ Si hay pares suficientes → `HEALTHY`.  
   - ⚠️ Si no, se comprueba el **cooldown** en DynamoDB:  
     - Dentro del cooldown → no se genera alerta.  
     - Fuera del cooldown → se inserta un evento `stopped` en DynamoDB.  

---

## 🔧 Variables de entorno

| Variable                | Default                | Descripción |
|-------------------------|------------------------|-------------|
| `LOG_GROUP`             | `/sdc-reactive-transfers-bot` | Nombre del CloudWatch Log Group a monitorizar |
| `LOG_REGION`            | `us-east-1`            | Región del Log Group |
| `WINDOW_MINUTES`        | `45`                   | Ventana de análisis en minutos |
| `EXPECTED_CRON_MINUTES` | `15`                   | Frecuencia esperada del bot |
| `MIN_PAIRS_OK`          | `1`                    | Nº mínimo de ejecuciones completas requeridas |
| `DDB_TABLE`             | `ct-ob-bots`           | Tabla DynamoDB destino |
| `DDB_REGION`            | `eu-central-1`         | Región de DynamoDB |
| `BOT_NAME`              | `SDC`                  | Nombre del bot que se monitoriza |
| `USER_NAME`             | `lambda`               | Identificador del emisor de alertas |
| `COOLDOWN_MINUTES`      | `60`                   | Periodo de gracia para evitar spam |
| `CONTROL_PK`            | `control`              | Prefijo de PK para item de control |
| `CONTROL_SK`            | `status`               | Sort key para item de control |
| `WRITE_REASON`          | `no_pairs_in_window`   | Motivo de evento `stopped` |

---

## 📂 Estructura DynamoDB

- **Tabla:** `ct-ob-bots`  
- **Claves principales:**  
  - PK: `bot`  
  - SK: `status`  

### Ejemplos de items

🔹 **Evento de control (cooldown):**
```json
{
  "bot": "control#SDC",
  "status": "status",
  "last_unhealthy_ts": 1727081221.12,
  "last_unhealthy_iso": "2025-09-22T13:47:01Z",
  "last_reason": "no_pairs_in_window"
}
