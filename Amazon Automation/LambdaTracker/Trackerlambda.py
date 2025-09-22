import os
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

# ========= Config (Environment Variables) =========
LOG_GROUP       = os.getenv("LOG_GROUP", "/sdc-reactive-transfers-bot")
LOG_REGION      = os.getenv("LOG_REGION", "us-east-1")          # Región del Log Group
WINDOW_MINUTES  = int(os.getenv("WINDOW_MINUTES", "45"))        # Ventana de análisis
EXPECTED_CRON   = int(os.getenv("EXPECTED_CRON_MINUTES", "15")) # Frecuencia esperada del bot
MIN_PAIRS_OK    = int(os.getenv("MIN_PAIRS_OK", "1"))           # Nº mínimo de pares start+completed para "healthy"

DDB_TABLE       = os.getenv("DDB_TABLE", "ct-ob-bots")
DDB_REGION      = os.getenv("DDB_REGION", "eu-central-1")
BOT_NAME        = os.getenv("BOT_NAME", "SDC")
USER_NAME       = os.getenv("USER_NAME", "lambda")

# Deduplicación
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))     # No repetir alerta durante este periodo
CONTROL_PK       = os.getenv("CONTROL_PK", "control")           # prefijo para item de control
CONTROL_SK       = os.getenv("CONTROL_SK", "status")            # sort key fija de control
WRITE_REASON     = os.getenv("WRITE_REASON", "no_pairs_in_window")  # motivo de UNHEALTHY

# ========= Clientes AWS =========
logs = boto3.client("logs", region_name=LOG_REGION)
dynamodb = boto3.resource("dynamodb", region_name=DDB_REGION)
table = dynamodb.Table(DDB_TABLE)


def _now_utc():
    return datetime.now(timezone.utc)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _try_parse_json(s: str):
    try:
        return json.loads(s)
    except Exception:
        return None


def _fetch_events(log_group: str, start_time_ms: int, limit_total: int = 1000):
    """
    Trae eventos del log group desde start_time_ms.
    Para esta verificación, paginamos levemente hasta limit_total.
    """
    events = []
    next_token = None
    fetched = 0

    while True:
        kwargs = {
            "logGroupName": log_group,
            "startTime": start_time_ms,
            "interleaved": True,
            "limit": min(100, limit_total - fetched)  # trae de 100 en 100
        }
        if next_token:
            kwargs["nextToken"] = next_token

        if kwargs["limit"] <= 0:
            break

        try:
            resp = logs.filter_log_events(**kwargs)
        except ClientError as e:
            print(f"[CW] ERROR filter_log_events: {e}")
            break

        batch = resp.get("events", [])
        events.extend(batch)
        fetched += len(batch)
        next_token = resp.get("nextToken")

        if not next_token or fetched >= limit_total:
            break

    # Orden por timestamp por seguridad
    events.sort(key=lambda e: e.get("timestamp", 0))
    return events


def _extract_markers(events):
    """
    A partir de los eventos (CloudWatch), identifica timestamps de:
    - 'Starting job execution'
    - 'Job execution completed'
    - 'Bot stopped manually' (por si quieres usarlo en el futuro)
    Devuelve listas de datetimes.
    """
    starts = []
    completes = []
    stopped = []

    for ev in events:
        ts_ms = ev.get("timestamp")
        msg = ev.get("message", "")
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

        data = _try_parse_json(msg)
        # Tus logs están en JSON; si no, fallback a contains simple
        text = ""
        if data and isinstance(data, dict):
            text = str(data.get("message") or "")
        else:
            text = msg

        if "Starting job execution" == text:
            starts.append(ts)
        elif "Job execution completed" == text:
            completes.append(ts)
        elif "Bot stopped manually" == text:
            stopped.append(ts)

    return starts, completes, stopped


def _count_pairs(starts, completes, window_end):
    """
    Cuenta pares start ➜ completed dentro de la ventana,
    cumpliendo que completed >= start y ambos dentro de la ventana analizada.
    Además, filtra "pares razonables": que 'completed' no sea más tarde de start + 3*EXPECTED_CRON (por si
    hubiera ruido antiguo).
    """
    if not starts or not completes:
        return 0

    # Two-pointer greedy matching
    starts_sorted = sorted(starts)
    completes_sorted = sorted(completes)

    i = j = 0
    pairs = 0
    max_delay = timedelta(minutes=EXPECTED_CRON * 3)

    while i < len(starts_sorted) and j < len(completes_sorted):
        s = starts_sorted[i]
        c = completes_sorted[j]

        if c < s:
            j += 1
        else:
            # c >= s : comprobar si está razonablemente cerca (no infinito después)
            if c - s <= max_delay and c <= window_end:
                pairs += 1
                i += 1
                j += 1
            else:
                # si el completed está demasiado lejos, avanzamos start
                i += 1

    return pairs


def _get_control_item():
    """
    Lee el item de control que evita spam durante el cooldown.
    PK = f"{CONTROL_PK}#{BOT_NAME}"
    SK = CONTROL_SK
    """
    try:
        resp = table.get_item(
            Key={
                "bot": f"{CONTROL_PK}#{BOT_NAME}",
                "status": CONTROL_SK
            }
        )
        return resp.get("Item")
    except ClientError as e:
        print(f"[DDB] ERROR GetItem control: {e}")
        return None


def _update_control_item(now_ts_dec: Decimal, last_reason: str):
    """
    Guarda/actualiza el item de control con el timestamp de la última alerta y el motivo.
    """
    try:
        table.put_item(Item={
            "bot": f"{CONTROL_PK}#{BOT_NAME}",  # PK de control
            "status": CONTROL_SK,               # SK de control
            "last_unhealthy_ts": now_ts_dec,
            "last_unhealthy_iso": _now_utc().isoformat(),
            "last_reason": last_reason
        })
        print("[DDB] Control item actualizado")
        return True
    except ClientError as e:
        print(f"[DDB] ERROR PutItem control: {e}")
        return False


def _within_cooldown(ctrl_item, cooldown_minutes: int) -> bool:
    """
    Devuelve True si la última alerta UNHEALTHY está dentro del cooldown.
    """
    if not ctrl_item:
        return False
    try:
        last_ts = ctrl_item.get("last_unhealthy_ts")
        if last_ts is None:
            return False
        # last_ts viene como Decimal (según cómo lo guardemos)
        last_dt = datetime.fromtimestamp(float(last_ts), tz=timezone.utc)
        elapsed = _now_utc() - last_dt
        return elapsed <= timedelta(minutes=cooldown_minutes)
    except Exception as e:
        print(f"[DDB] WARN parsing control timestamp: {e}")
        return False


def _put_stopped_event(reason: str):
    """
    Inserta el item 'stopped' (evento de episodio UNHEALTHY) con PK=BOT_NAME.
    Asume tabla con PK 'bot' y SK 'time' (Decimal), como en tu script.
    """
    now = _now_utc()
    ts_dec = Decimal(str(now.timestamp()))

    item = {
        "bot": BOT_NAME,
        "status": "stopped",
        "time": ts_dec,               # Sort Key (Decimal) según tu patrón
        "user": USER_NAME,
        "chang": Decimal("1"),
        "reason": reason,
        "window_minutes": WINDOW_MINUTES
    }

    try:
        table.put_item(Item=item)
        print(f"[DDB] PutItem STOPPED OK → {json.dumps({'bot': item['bot'], 'status': item['status'], 'time': str(item['time'])})}")
        # Actualizamos control
        _update_control_item(ts_dec, reason)
        return True
    except ClientError as e:
        print(f"[DDB] ERROR PutItem stopped: {e}")
        return False


def lambda_handler(event, context):
    now = _now_utc()
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    start_ms = _ms(window_start)

    print(f"[CHECK] Ventana: {window_start.isoformat()} → {now.isoformat()} | LOG_GROUP={LOG_GROUP} REG={LOG_REGION}")

    # 1) Leer eventos en ventana
    events = _fetch_events(LOG_GROUP, start_ms, limit_total=1000)
    print(f"[CW] Eventos leídos: {len(events)}")

    # 2) Extraer marcadores clave
    starts, completes, stopped = _extract_markers(events)
    print(f"[CW] starts={len(starts)} completes={len(completes)} stopped={len(stopped)}")

    # 3) Contar pares válidos start ➜ completed
    pairs = _count_pairs(starts, completes, now)
    print(f"[HEALTH] Pares start→completed en ventana: {pairs}")

    if pairs >= MIN_PAIRS_OK:
        # Salud OK → no escribir 'stopped', ni tocar cooldown
        result = {
            "status": "HEALTHY",
            "pairs": pairs,
            "action": "none"
        }
        print(f"[RESULT] {json.dumps(result)}")
        return {"statusCode": 200, "body": result}

    # 4) No hay pares suficientes → episodio UNHEALTHY: ¿estamos en cooldown?
    ctrl_item = _get_control_item()
    if _within_cooldown(ctrl_item, COOLDOWN_MINUTES):
        result = {
            "status": "UNHEALTHY",
            "pairs": pairs,
            "action": "cooldown_skip",
            "cooldown_minutes": COOLDOWN_MINUTES
        }
        print(f"[RESULT] {json.dumps(result)}")
        return {"statusCode": 200, "body": result}

    # 5) Fuera de cooldown → escribimos evento 'stopped' y actualizamos control
    ok = _put_stopped_event(WRITE_REASON)
    result = {
        "status": "UNHEALTHY",
        "pairs": pairs,
        "action": "dynamodb_put_stopped",
        "dynamodb_ok": ok
    }
    print(f"[RESULT] {json.dumps(result)}")
    return {"statusCode": 200, "body": result}
