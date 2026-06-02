from flask import Blueprint, request, jsonify
import psycopg2
import psycopg2.extras
import os
import time
import threading
import requests
from model import Service, ServiceCheck

metrics_blueprint = Blueprint('metrics', __name__)

DB_MASTER_HOST = os.getenv('MDB_MASTER_HOST', 'postgres-metrics-master')
DB_SLAVE_HOST  = os.getenv('MDB_SLAVE_HOST', 'postgres-metrics-slave')
DB_PORT        = os.getenv('MDB_PORT', '5432')
DB_NAME        = os.getenv('MDB_NAME', 'ualspeed_metrics')
DB_USER        = os.getenv('DB_USER', 'postgres')
DB_PASSWORD    = os.getenv('DB_PASSWORD', 'postgres')

CHECK_INTERVAL   = int(os.getenv('CHECK_INTERVAL', 30))   # segundos entre checks
LATENCY_WARN_MS  = float(os.getenv('LATENCY_WARN_MS', 500))  # acima disto -> degraded
REQUEST_TIMEOUT  = float(os.getenv('REQUEST_TIMEOUT', 5))

ERROR_RESPONSE = {'error': 'Error getting data, retry or contact support if problem persists.'}


def get_write_connection():
    return psycopg2.connect(
        host=DB_MASTER_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
def get_read_connection():
    try:
        return psycopg2.connect(
            host=DB_SLAVE_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Exception as e:
        print(f"error:{e}, falling back to master for reads")
        return psycopg2.connect(
            host=DB_MASTER_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )

# ---------------------------------------------------------------------------
# Lógica de check de um serviço
# ---------------------------------------------------------------------------

def check_service(url: str) -> dict:
    """Pinga um URL e devolve status, latência e status_code."""
    try:
        start = time.time()
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        latency = round((time.time() - start) * 1000, 2)

        if resp.status_code >= 500:
            return {'status': 'offline', 'latency_ms': latency,
                    'status_code': resp.status_code, 'error_msg': f'HTTP {resp.status_code}'}
        if latency > LATENCY_WARN_MS:
            return {'status': 'degraded', 'latency_ms': latency,
                    'status_code': resp.status_code, 'error_msg': 'High latency'}
        return {'status': 'online', 'latency_ms': latency,
                'status_code': resp.status_code, 'error_msg': None}

    except requests.exceptions.ConnectionError:
        return {'status': 'offline', 'latency_ms': None,
                'status_code': None, 'error_msg': 'Connection refused'}
    except requests.exceptions.Timeout:
        return {'status': 'offline', 'latency_ms': None,
                'status_code': None, 'error_msg': 'Timeout'}
    except Exception as e:
        return {'status': 'offline', 'latency_ms': None,
                'status_code': None, 'error_msg': str(e)}


def run_all_checks():
    """Faz check a todos os serviços registados e guarda na BD."""
    try:
        db = get_read_connection()
        cursor = db.cursor()

        cursor.execute("SELECT service_id, name, url FROM services")
        services = cursor.fetchall()
        cursor.close()
        db.close()
        db = get_write_connection()
        cursor = db.cursor()
        

        for service_id, name, url in services:
            result = check_service(url)
            cursor.execute("""
                INSERT INTO service_checks (service_id, status, latency_ms, status_code, error_msg)
                VALUES (%s, %s, %s, %s, %s)
            """, (service_id, result['status'], result['latency_ms'],
                  result['status_code'], result['error_msg']))
            # Also record a basic event for throughput monitoring (one per check)
            try:
                cursor.execute(
                    "INSERT INTO events (service_id, event_type) VALUES (%s, %s)",
                    (service_id, 'service_check')
                )
            except Exception:
                # ignore errors inserting events to avoid breaking checks
                pass

        # Apaga checks com mais de 24h para não acumular lixo
        cursor.execute("""
            DELETE FROM service_checks
            WHERE checked_at < NOW() - INTERVAL '24 hours'
        """)

        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"[metrics] Erro no check automático: {e}")


# ---------------------------------------------------------------------------
# Background thread — corre checks periodicamente
# ---------------------------------------------------------------------------

def _background_loop():
    while True:
        run_all_checks()
        time.sleep(CHECK_INTERVAL)


def start_background_checker():
    t = threading.Thread(target=_background_loop, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@metrics_blueprint.route('/health', methods=['GET'])
def health_check():
    try:
        start = time.time()
        db = get_read_connection()
        db.close()
        db_ping = round((time.time() - start) * 1000, 2)
        db_status = 'running'
    except Exception:
        db_ping = None
        db_status = 'ERROR'

    return jsonify({
        "service": "UALSpeed Metrics Service",
        "status": "running",
        "version": "1.0.0",
        "database": db_status,
        "ping": db_ping
    }), 200


@metrics_blueprint.route('/services', methods=['GET'])
def get_services_status():
    """Estado atual de cada serviço (último check de cada um)."""
    try:
        db = get_read_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT sc.check_id, sc.service_id, s.name, sc.status,
                   sc.latency_ms, sc.status_code, sc.error_msg, sc.checked_at
            FROM service_checks sc
            JOIN services s ON s.service_id = sc.service_id
            WHERE sc.checked_at = (
                SELECT MAX(sc2.checked_at)
                FROM service_checks sc2
                WHERE sc2.service_id = sc.service_id
            )
            ORDER BY s.name
        """)
        rows = cursor.fetchall()

        # Conta totais
        cursor.execute("SELECT COUNT(*) FROM services")
        total = cursor.fetchone()[0]

        cursor.close()
        db.close()

        results = []
        for row in rows:
            check = ServiceCheck(*row)
            results.append(check.to_json())

        online  = sum(1 for r in results if r['status'] == 'online')
        offline = sum(1 for r in results if r['status'] == 'offline')
        degraded = sum(1 for r in results if r['status'] == 'degraded')

        latencies = [r['latency_ms'] for r in results if r['latency_ms'] is not None]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None

        return jsonify({
            "total": total,
            "online": online,
            "offline": offline,
            "degraded": degraded,
            "avg_latency_ms": avg_latency,
            "services": results
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/latency', methods=['GET'])
def get_latency_history():
    """Histórico de latência das últimas N horas (default 1h)."""
    try:
        hours = request.args.get('hours', 1, type=int)
        service_id = request.args.get('service_id', type=int)

        db = get_read_connection()
        cursor = db.cursor()

        query = """
            SELECT sc.check_id, sc.service_id, s.name, sc.status,
                   sc.latency_ms, sc.status_code, sc.error_msg, sc.checked_at
            FROM service_checks sc
            JOIN services s ON s.service_id = sc.service_id
            WHERE sc.checked_at >= NOW() - INTERVAL '%s hours'
        """
        params = [hours]

        if service_id:
            query += " AND sc.service_id = %s"
            params.append(service_id)

        query += " ORDER BY sc.checked_at ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        history = [ServiceCheck(*row).to_json() for row in rows]

        return jsonify({
            "hours": hours,
            "count": len(history),
            "history": history
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/check', methods=['POST'])
def trigger_check():
    """Força um check imediato a todos os serviços."""
    try:
        run_all_checks()
        return jsonify({"message": "Check concluído"}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/services', methods=['POST'])
def register_service():
    """Regista um novo serviço para monitorizar."""
    try:
        body = request.get_json()
        name = body.get('name')
        url  = body.get('url')

        if not name or not url:
            return jsonify({'error': 'name e url são obrigatórios'}), 400

        db = get_write_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO services (name, url) VALUES (%s, %s) RETURNING service_id",
            (name, url)
        )
        service_id = cursor.fetchone()[0]
        db.commit()
        cursor.close()
        db.close()

        return jsonify({"service_id": service_id, "name": name, "url": url}), 201

    except psycopg2.errors.UniqueViolation:
        return jsonify({'error': 'Serviço já existe'}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    """Remove um serviço da monitorização."""
    try:
        db = get_write_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM services WHERE service_id = %s", (service_id,))
        db.commit()
        cursor.close()
        db.close()
        return jsonify({"message": f"Serviço {service_id} removido"}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/status', methods=['GET'])
def status_summary():
    """Return a simplified status summary used by the frontend.

    Expected shape:
    {
      "services": [ { "service_id":..., "name":..., "status":"up|down|degraded", "latency": <ms|null> }, ... ],
      "timestamp": "2024-01-01T12:00:00"  # last check time
    }
    """
    try:
        db = get_read_connection()
        cursor = db.cursor()

        # For each service get the latest check (if any)
        cursor.execute("""
            SELECT s.service_id, s.name, sc.status, sc.latency_ms, sc.checked_at
            FROM services s
            LEFT JOIN LATERAL (
                SELECT status, latency_ms, checked_at
                FROM service_checks sc2
                WHERE sc2.service_id = s.service_id
                ORDER BY sc2.checked_at DESC
                LIMIT 1
            ) sc ON true
            ORDER BY s.name
        """)

        rows = cursor.fetchall()
        cursor.close()
        db.close()

        services = []
        latest_ts = None
        for service_id, name, status, latency_ms, checked_at in rows:
            # map internal statuses to frontend-friendly ones
            if status == 'online':
                mapped = 'up'
            elif status == 'offline':
                mapped = 'down'
            elif status == 'degraded':
                mapped = 'degraded'
            else:
                mapped = 'down' if status is None else status

            services.append({
                'service_id': service_id,
                'name': name,
                'status': mapped,
                'latency': float(latency_ms) if latency_ms is not None else None
            })

            if checked_at:
                if latest_ts is None or checked_at > latest_ts:
                    latest_ts = checked_at

        timestamp = latest_ts.isoformat() if latest_ts else None

        return jsonify({
            'services': services,
            'timestamp': timestamp
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/events', methods=['POST'])
def post_event():
    """Record an event for throughput monitoring.

    Body: { "service_id": <int|null>, "event_type": "name" }
    """
    try:
        body = request.get_json() or {}
        service_id = body.get('service_id')
        event_type = body.get('event_type', 'generic')

        db = get_write_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO events (service_id, event_type) VALUES (%s, %s)",
            (service_id, event_type)
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'message': 'event recorded'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/events/bulk', methods=['POST'])
def post_events_bulk():
    """Insert many events quickly to demonstrate higher throughput."""
    try:
        body = request.get_json(silent=True) or {}
        count = int(body.get('count', 100))
        service_id = body.get('service_id')
        event_type = body.get('event_type', 'burst')
        count = max(1, min(count, 5000))

        rows = [(service_id, event_type)] * count

        db = get_write_connection()
        cursor = db.cursor()
        psycopg2.extras.execute_values(
            cursor,
            "INSERT INTO events (service_id, event_type) VALUES %s",
            rows
        )
        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            'message': 'bulk events recorded',
            'count': count,
            'service_id': service_id,
            'event_type': event_type
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_blueprint.route('/throughput', methods=['GET'])
def get_throughput():
    """Return throughput (events per minute) for the last N minutes.

    Query params: minutes (default 10)
    Response: {minutes: N, total: X, per_minute: [{minute: 'HH:MM', count: n}, ...]}
    """
    try:
        minutes = request.args.get('minutes', 10, type=int)

        db = get_read_connection()
        cursor = db.cursor()

        cursor.execute(
            """
            SELECT date_trunc('minute', occurred_at) AS minute, COUNT(*)
            FROM events
            WHERE occurred_at >= NOW() - INTERVAL %s
            GROUP BY 1
            ORDER BY 1 ASC
            """,
            (f"{minutes} minutes",)
        )
        rows = cursor.fetchall()

        # Build a map minute->count and also compute total
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())

        # Create per-minute list for the full range so chart shows empty slots
        per_minute = []
        for i in range(minutes, 0, -1):
            ts = (time.time() - (i-1)*60)
            # convert to minute aligned timestamp
            minute_ts = time.localtime(time.time() - (i-1)*60)
            minute_label = time.strftime('%H:%M', minute_ts)
            # We can't easily map original datetime objects here; instead query by minute string
            per_minute.append({'minute': minute_label, 'count': 0})

        # Fill counts (simpler approach: re-query with text-formatted minute strings)
        cursor.execute(
            """
            SELECT to_char(date_trunc('minute', occurred_at), 'HH24:MI') as minute_label, COUNT(*)
            FROM events
            WHERE occurred_at >= NOW() - INTERVAL %s
            GROUP BY 1
            ORDER BY 1 ASC
            """,
            (f"{minutes} minutes",)
        )
        rows2 = cursor.fetchall()
        cursor.close()
        db.close()

        label_map = {r[0]: r[1] for r in rows2}
        per_minute = []
        for i in range(minutes-1, -1, -1):
            ts = time.time() - i*60
            minute_label = time.strftime('%H:%M', time.localtime(ts))
            per_minute.append({'minute': minute_label, 'count': label_map.get(minute_label, 0)})

        avg_per_min = round(total / minutes, 2) if minutes else 0

        return jsonify({
            'minutes': minutes,
            'total': total,
            'avg_per_min': avg_per_min,
            'per_minute': per_minute
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500