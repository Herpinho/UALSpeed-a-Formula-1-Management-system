from flask import Blueprint, request, jsonify
import psycopg2
import psycopg2.extras
import os
import time
import math
from datetime import datetime, timedelta, timezone
import fastf1
from model import Car, CarPerformance, Stint
import requests

OPENF1 = "https://api.openf1.org/v1"
RESULTS_SERVICE = os.getenv('RESULTS_SERVICE', 'http://results-service:5002')
CACHE_DIR = os.getenv('FASTF1_CACHE', '/tmp/fastf1_cache')
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

ERROR_RESPONSE_DATA = {'error': 'Error getting data, retry or contact support if problem persists.'}
ERROR_STATUS_CODE = 500

DEMO_PERFORMANCE = [
    {'driver_id': 44, 'driver_name': 'Alex Martins', 'max_speed': 332.0, 'max_rpm': 12850, 'avg_throttle': 78.4, 'avg_brake': 16.2, 'drs_time': 18.6, 'best_lap_time': '1:29.824', 'total_laps': 5},
    {'driver_id': 16, 'driver_name': 'Sofia Pereira', 'max_speed': 329.4, 'max_rpm': 12790, 'avg_throttle': 76.8, 'avg_brake': 17.9, 'drs_time': 16.2, 'best_lap_time': '1:30.102', 'total_laps': 5},
    {'driver_id': 11, 'driver_name': 'Tomás Costa', 'max_speed': 326.8, 'max_rpm': 12690, 'avg_throttle': 74.5, 'avg_brake': 18.7, 'drs_time': 14.9, 'best_lap_time': '1:30.488', 'total_laps': 5},
]

DEMO_STINTS = [
    {'driver_id': 44, 'driver_name': 'Alex Martins', 'stint_number': 1, 'compound': 'SOFT', 'lap_start': 1, 'lap_end': 3, 'tyre_age': 0, 'is_fresh': True},
    {'driver_id': 44, 'driver_name': 'Alex Martins', 'stint_number': 2, 'compound': 'MEDIUM', 'lap_start': 4, 'lap_end': 5, 'tyre_age': 2, 'is_fresh': False},
    {'driver_id': 16, 'driver_name': 'Sofia Pereira', 'stint_number': 1, 'compound': 'SOFT', 'lap_start': 1, 'lap_end': 2, 'tyre_age': 0, 'is_fresh': True},
    {'driver_id': 16, 'driver_name': 'Sofia Pereira', 'stint_number': 2, 'compound': 'MEDIUM', 'lap_start': 3, 'lap_end': 5, 'tyre_age': 2, 'is_fresh': False},
    {'driver_id': 11, 'driver_name': 'Tomás Costa', 'stint_number': 1, 'compound': 'SOFT', 'lap_start': 1, 'lap_end': 3, 'tyre_age': 0, 'is_fresh': True},
    {'driver_id': 11, 'driver_name': 'Tomás Costa', 'stint_number': 2, 'compound': 'HARD', 'lap_start': 4, 'lap_end': 5, 'tyre_age': 1, 'is_fresh': False},
]

DEMO_CARS = [
    {'driver_id': 44, 'speed': 332, 'rpm': 12850, 'throttle': 82, 'brake': 8, 'drs': True, 'gear': 8, 'lap': 5},
    {'driver_id': 16, 'speed': 329, 'rpm': 12790, 'throttle': 79, 'brake': 10, 'drs': True, 'gear': 8, 'lap': 5},
    {'driver_id': 11, 'speed': 327, 'rpm': 12690, 'throttle': 75, 'brake': 12, 'drs': False, 'gear': 7, 'lap': 5},
]

data_blueprint = Blueprint('data', __name__)

DB_CONFIG = {
    'host': os.getenv('DDB_HOST', 'postgres-data'),
    'port': os.getenv('DDB_PORT', '5432'),
    'database': os.getenv('DDB_NAME', 'ualspeed_data'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def safe_float(val):
    try:
        f = float(val)
        return None if math.isnan(f) else round(f, 3)
    except:
        return None


def safe_int(val):
    try:
        f = float(val)
        return None if math.isnan(f) else int(f)
    except:
        return None


def safe_str(val):
    if val is None:
        return None
    s = str(val)
    return None if s in ('', 'nan', 'NaT', 'None') else s


_demo_failure_until = 0.0


def is_demo_failure_active():
    return time.time() < _demo_failure_until

@data_blueprint.route('/', methods=['GET'])
def health_check():
    if is_demo_failure_active():
        return jsonify({
            "service": "UALSpeed Data Service",
            "status": "offline",
            "version": "1.0.0",
            "error": "Simulated failure active"
        }), 503

    try:
        start = time.time()
        db = get_db_connection()
        db.close()
        db_ping = round((time.time() - start) * 1000, 2)
        db_status = 'running'
    except:
        db_ping = ''
        db_status = 'ERROR'
    return jsonify({
        "service": "UALSpeed Data Service",
        "status": "running",
        "version": "1.0.0",
        "database": db_status,
        "ping": db_ping
    }), 200


@data_blueprint.route('/demo/failure', methods=['POST'])
def demo_failure():
    """Ativa um modo de falha temporário para demonstração."""
    global _demo_failure_until
    try:
        body = request.get_json(silent=True) or {}
        seconds = int(body.get('seconds', 20))
        seconds = max(1, min(seconds, 120))
        reason = body.get('reason', 'Simulated outage for class demo')

        _demo_failure_until = time.time() + seconds

        return jsonify({
            'message': 'Demo failure activated',
            'duration_seconds': seconds,
            'reason': reason,
            'active_until_epoch': _demo_failure_until
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@data_blueprint.route('/demo/seed', methods=['POST'])
def seed_demo_metrics():
    """Cria dados sintéticos da demo para telemetria e estratégia."""
    try:
        body = request.get_json(silent=True) or {}
        race_id = body.get('race_id')
        if not race_id:
            return jsonify({'error': 'race_id é obrigatório'}), 400

        db = get_db_connection()
        cur = db.cursor()

        cur.execute("DELETE FROM cars WHERE race_id = %s", (race_id,))
        cur.execute("DELETE FROM car_performance WHERE race_id = %s", (race_id,))
        cur.execute("DELETE FROM stints WHERE race_id = %s", (race_id,))

        base_time = datetime.now(timezone.utc)
        for index, car in enumerate(DEMO_CARS):
            cur.execute(
                """INSERT INTO cars
                   (race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (race_id, car['driver_id'], car['speed'], car['rpm'], car['throttle'], car['brake'], car['drs'], car['gear'], car['lap'], base_time + timedelta(seconds=index))
            )

        for perf in DEMO_PERFORMANCE:
            cur.execute(
                """INSERT INTO car_performance
                   (race_id, driver_id, driver_name, max_speed, max_rpm, avg_throttle, avg_brake, drs_time, best_lap_time, total_laps)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (race_id, driver_id) DO UPDATE SET
                       driver_name = EXCLUDED.driver_name,
                       max_speed = EXCLUDED.max_speed,
                       max_rpm = EXCLUDED.max_rpm,
                       avg_throttle = EXCLUDED.avg_throttle,
                       avg_brake = EXCLUDED.avg_brake,
                       drs_time = EXCLUDED.drs_time,
                       best_lap_time = EXCLUDED.best_lap_time,
                       total_laps = EXCLUDED.total_laps""",
                (race_id, perf['driver_id'], perf['driver_name'], perf['max_speed'], perf['max_rpm'], perf['avg_throttle'], perf['avg_brake'], perf['drs_time'], perf['best_lap_time'], perf['total_laps'])
            )

        for stint in DEMO_STINTS:
            cur.execute(
                """INSERT INTO stints
                   (race_id, driver_id, driver_name, stint_number, compound, lap_start, lap_end, tyre_age, is_fresh)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (race_id, stint['driver_id'], stint['driver_name'], stint['stint_number'], stint['compound'], stint['lap_start'], stint['lap_end'], stint['tyre_age'], stint['is_fresh'])
            )

        db.commit()
        cur.close()
        db.close()

        return jsonify({
            'message': 'demo metrics seeded',
            'race_id': race_id,
            'cars_inserted': len(DEMO_CARS),
            'perf_inserted': len(DEMO_PERFORMANCE),
            'stint_inserted': len(DEMO_STINTS)
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@data_blueprint.route('/demo/copy-telemetry', methods=['POST'])
def copy_demo_telemetry():
    """Copia a telemetria do piloto fonte (por defeito 'Leclerc' na corrida) para os restantes pilotos da mesma corrida."""
    try:
        body = request.get_json(silent=True) or {}
        race_id = body.get('race_id')
        source_driver_id = body.get('source_driver_id')

        if not race_id:
            return jsonify({'error': 'race_id é obrigatório'}), 400

        db = get_db_connection()
        cur = db.cursor()

        # Encontrar piloto fonte: procura por driver_name contendo 'leclerc' se source_driver_id não for fornecido
        source = None
        if source_driver_id:
            cur.execute("SELECT driver_id, driver_name, max_speed, max_rpm, avg_throttle, avg_brake, drs_time, best_lap_time, total_laps FROM car_performance WHERE race_id = %s AND driver_id = %s", (race_id, source_driver_id))
            source = cur.fetchone()

        if not source:
            cur.execute("SELECT driver_id, driver_name, max_speed, max_rpm, avg_throttle, avg_brake, drs_time, best_lap_time, total_laps FROM car_performance WHERE race_id = %s AND driver_name ILIKE %s LIMIT 1", (race_id, '%leclerc%'))
            source = cur.fetchone()

        # fallback: primeiro piloto encontrado
        if not source:
            cur.execute("SELECT driver_id, driver_name, max_speed, max_rpm, avg_throttle, avg_brake, drs_time, best_lap_time, total_laps FROM car_performance WHERE race_id = %s ORDER BY driver_id LIMIT 1", (race_id,))
            source = cur.fetchone()

        if not source:
            cur.close()
            db.close()
            return jsonify({'error': 'Fonte de telemetria não encontrada para esta corrida'}), 404

        (s_driver_id, s_driver_name, s_max_speed, s_max_rpm, s_avg_throttle, s_avg_brake, s_drs_time, s_best_lap_time, s_total_laps) = source

        # obter último estado do carro fonte
        cur.execute("SELECT speed, rpm, throttle, brake, drs, gear, lap, data_time FROM cars WHERE race_id = %s AND driver_id = %s ORDER BY data_time DESC LIMIT 1", (race_id, s_driver_id))
        last_car = cur.fetchone()

        # listar pilotos alvo
        # 1) pilotos já existentes em car_performance
        cur.execute("SELECT driver_id, driver_name FROM car_performance WHERE race_id = %s AND driver_id != %s", (race_id, s_driver_id))
        targets_map = {int(did): (name or f"#{did}") for did, name in cur.fetchall()}

        # 2) completar com todos os pilotos da classificação no results_service
        try:
            results_service_url = os.getenv('RESULTS_SERVICE', 'http://results-service:5002')
            classification_resp = requests.get(
                f"{results_service_url}/results/classification/{race_id}",
                timeout=5
            )
            if classification_resp.ok:
                payload = classification_resp.json() or {}
                for item in payload.get('classification', []):
                    driver_id = item.get('driver_id')
                    if driver_id is None:
                        continue
                    driver_id = int(driver_id)
                    if driver_id == s_driver_id:
                        continue
                    driver_name = item.get('driver_name') or targets_map.get(driver_id) or f"#{driver_id}"
                    targets_map[driver_id] = driver_name
        except Exception:
            # Se o results_service falhar, segue com os pilotos já conhecidos no data_service.
            pass

        targets = sorted(targets_map.items(), key=lambda x: x[0])

        cars_inserted = 0
        perf_updated = 0
        stints_copied = 0

        now = datetime.now(timezone.utc)
        for idx, (t_driver_id, t_driver_name) in enumerate(targets):
            # atualizar car_performance para o piloto alvo
            cur.execute(
                """
                INSERT INTO car_performance (race_id, driver_id, driver_name, max_speed, max_rpm, avg_throttle, avg_brake, drs_time, best_lap_time, total_laps)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (race_id, driver_id) DO UPDATE SET
                    max_speed=EXCLUDED.max_speed, max_rpm=EXCLUDED.max_rpm,
                    avg_throttle=EXCLUDED.avg_throttle, avg_brake=EXCLUDED.avg_brake,
                    drs_time=EXCLUDED.drs_time, best_lap_time=EXCLUDED.best_lap_time,
                    total_laps=EXCLUDED.total_laps
                """,
                (race_id, t_driver_id, t_driver_name, s_max_speed, s_max_rpm, s_avg_throttle, s_avg_brake, s_drs_time, s_best_lap_time, s_total_laps)
            )
            perf_updated += 1

            # inserir estado de carro mais recente do fonte para o alvo (1 registo por piloto)
            if last_car:
                (s_speed, s_rpm, s_throttle, s_brake, s_drs, s_gear, s_lap, s_data_time) = last_car
                insert_time = now + timedelta(seconds=idx)
                cur.execute(
                    "INSERT INTO cars (race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (race_id, t_driver_id, s_speed, s_rpm, s_throttle, s_brake, s_drs, s_gear, s_lap, insert_time)
                )
                cars_inserted += 1

            # copiar stints do fonte para o alvo (remover stints existentes do alvo primeiro)
            cur.execute("DELETE FROM stints WHERE race_id = %s AND driver_id = %s", (race_id, t_driver_id))
            cur.execute("SELECT stint_number, compound, lap_start, lap_end, tyre_age, is_fresh FROM stints WHERE race_id = %s AND driver_id = %s ORDER BY stint_number", (race_id, s_driver_id))
            s_stints = cur.fetchall()
            for s in s_stints:
                cur.execute(
                    "INSERT INTO stints (race_id, driver_id, driver_name, stint_number, compound, lap_start, lap_end, tyre_age, is_fresh) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (race_id, t_driver_id, t_driver_name, s[0], s[1], s[2], s[3], s[4], s[5])
                )
                stints_copied += 1

        db.commit()
        cur.close()
        db.close()

        return jsonify({
            'message': 'Telemetry copied',
            'race_id': race_id,
            'source_driver_id': s_driver_id,
            'source_driver_name': s_driver_name,
            'targets': len(targets),
            'cars_inserted': cars_inserted,
            'perf_updated': perf_updated,
            'stints_copied': stints_copied
        }), 200

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@data_blueprint.route('/race/<race_id>/start', methods=['PUT'])
def start_race(race_id):
    try:
        response = requests.put(
            f"{os.getenv('RESULTS_SERVICE','http://results-service:5002')}/results/races/{race_id}/status",
            json={'status': 'live'}
        )
        if response.status_code == 200:
            return jsonify({'message': f'Race {race_id} Started.'}), 200
        else:
            return jsonify(ERROR_RESPONSE_DATA), ERROR_STATUS_CODE
    except Exception as e:
        return jsonify({'error': str(e)}), 500  

@data_blueprint.route('/race/<race_id>/stop', methods=['POST'])
def stop_race(race_id):
    try:
        response = requests.put(
            f"{RESULTS_SERVICE}/results/races/{race_id}/status",
            json={'status': 'completed'}
        )
        if response.status_code == 200:
            return jsonify({'message': f'Race {race_id} Stopped.'}), 200
        else:
            return jsonify(ERROR_RESPONSE_DATA), ERROR_STATUS_CODE
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@data_blueprint.route('/cars/<race_id>', methods=['GET'])
def get_cars(race_id):
    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT car_id, race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time, created_at
            FROM cars
            WHERE race_id = %s
            ORDER BY data_time ASC, driver_id ASC
        """, (race_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()
        cars = []
        for row in rows:
            car = Car(*row)
            cars.append(car.to_json())
        return jsonify({'cars': cars}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500



_driver_names_cache = {}

@data_blueprint.route('/drivers/<race_id>/names', methods=['GET'])
def get_driver_names(race_id):
    """Vai buscar nomes dos pilotos à OpenF1 e guarda em cache"""
    global _driver_names_cache
    try:
        race_resp = requests.get(f"{RESULTS_SERVICE}/results/races/{race_id}", timeout=3)
        if race_resp.status_code != 200:
            return jsonify({}), 200
        race = race_resp.json()
        race_country = race.get('country', '')
        race_year = race.get('date', '2024')[:4]

        session_resp = requests.get(
            f"{OPENF1}/sessions?country_name={race_country}&session_name=Race&year={race_year}",
            timeout=5
        )
        if session_resp.status_code != 200 or not session_resp.json():
            return jsonify({}), 200

        session_key = session_resp.json()[0]['session_key']
        drivers_resp = requests.get(f"{OPENF1}/drivers?session_key={session_key}", timeout=5)
        if drivers_resp.status_code != 200:
            return jsonify({}), 200

        names = {}
        for d in drivers_resp.json():
            if isinstance(d, dict):
                num = d.get('driver_number')
                name = d.get('full_name') or d.get('broadcast_name') or f"#{num}"
                names[num] = name

        _driver_names_cache[race_id] = names
        return jsonify(names), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@data_blueprint.route('/cars/<race_id>/latest', methods=['GET'])
def get_cars_latest(race_id):
    """Obtém o último estado de cada carro em pista"""
    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Último registo por piloto
        cursor.execute("""
            SELECT c.car_id, c.race_id, c.driver_id, c.speed, c.rpm,
                   c.throttle, c.brake, c.drs, c.gear, c.lap, c.data_time, c.created_at
            FROM cars c
            INNER JOIN (
                SELECT driver_id, MAX(data_time) as max_time
                FROM cars
                WHERE race_id = %s
                GROUP BY driver_id
            ) latest ON c.driver_id = latest.driver_id AND c.data_time = latest.max_time
            WHERE c.race_id = %s
            ORDER BY c.driver_id
        """, (race_id, race_id))
        rows = cursor.fetchall()

        cursor.execute("""
            SELECT driver_id, MAX(speed) as top_speed, MAX(lap) as max_lap
            FROM cars
            WHERE race_id = %s
            GROUP BY driver_id
        """, (race_id,))
        stats = {row[0]: {'top_speed': row[1], 'max_lap': row[2]} for row in cursor.fetchall()}

        cursor.close()
        db.close()

        driver_names = _driver_names_cache.get(race_id, {})

        cars = []
        for row in rows:
            car = Car(*row).to_json()
            car['driver_name'] = driver_names.get(car['driver_id'], f"#{car['driver_id']}")
            car['top_speed']   = stats.get(car['driver_id'], {}).get('top_speed', 0)
            car['max_lap']     = stats.get(car['driver_id'], {}).get('max_lap', 0)
            cars.append(car)

        return jsonify({'cars': cars, 'count': len(cars)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_blueprint.route('/simulate/<race_id>', methods=['POST'])
def simulate_race(race_id):
    """
    Importa telemetria real da OpenF1 e divide em 3 fases:
    - Fase 1: primeiro terço da corrida (início)
    - Fase 2: segundo terço (meio)
    - Fase 3: último terço (final)
    """
    try:
        race = requests.get(f"{RESULTS_SERVICE}/results/races/{race_id}").json()
        race_country = race['country']
        race_year = race['date'][:4]

        api_session = requests.get(
            f"{OPENF1}/sessions?country_name={race_country}&session_name=Race&year={race_year}"
        ).json()
        if not api_session:
            return jsonify(ERROR_RESPONSE_DATA), ERROR_STATUS_CODE
        session_key = api_session[0]['session_key']

        drivers_resp = requests.get(f"{OPENF1}/drivers?session_key={session_key}").json()
        if not drivers_resp or not isinstance(drivers_resp, list):
            return jsonify({'error': 'No drivers found'}), 404

        driver_numbers = [d['driver_number'] for d in drivers_resp if isinstance(d, dict)][:20]

        lap_map = {}  
        try:
            for driver_number in driver_numbers:
                laps_resp = requests.get(
                    f"{OPENF1}/laps?session_key={session_key}&driver_number={driver_number}",
                    timeout=15
                )
                if laps_resp.status_code == 200:
                    for lap in laps_resp.json():
                        if isinstance(lap, dict):
                            date_start = lap.get('date_start', '')[:16]  # YYYY-MM-DDTHH:MM
                            lap_map[(driver_number, date_start)] = lap.get('lap_number', 0)
        except Exception:
            pass

        valid_data = []
        for driver_number in driver_numbers:
            for attempt in range(3):  
                try:
                    resp = requests.get(
                        f"{OPENF1}/car_data?session_key={session_key}&driver_number={driver_number}",
                        timeout=30
                    )
                    driver_data = resp.json()
                    if isinstance(driver_data, list):
                        for e in driver_data:
                            if isinstance(e, dict) and e.get('n_gear') is not None:
                                date_prefix = e.get('date', '')[:16]
                                e['lap'] = lap_map.get((driver_number, date_prefix), 0)
                                valid_data.append(e)
                    break  # sucesso, sai do retry
                except Exception:
                    if attempt == 2:
                        print(f"⚠️ Falha ao buscar dados do piloto {driver_number} após 3 tentativas")
                    continue

        if not valid_data:
            return jsonify({'error': 'No valid telemetry data found'}), 404

        valid_data.sort(key=lambda x: x.get('date', ''))

        race_data = [
            e for e in valid_data
            if e.get('speed', 0) > 50
            and -1 <= e.get('n_gear', 0) <= 8
        ]
        if not race_data:
            race_data = [
                e for e in valid_data
                if (e.get('speed', 0) > 0 or e.get('rpm', 0) > 0)
                and -1 <= e.get('n_gear', 0) <= 8
            ]

        total = len(race_data)
        laps = sorted(set(e.get('lap', 0) for e in race_data if e.get('lap', 0) > 0))
        if laps:
            total_laps = len(laps)
            lap_split1 = laps[total_laps // 3]
            lap_split2 = laps[(total_laps * 2) // 3]
            phases = {
                1: [e for e in race_data if e.get('lap', 0) <= lap_split1],
                2: [e for e in race_data if lap_split1 < e.get('lap', 0) <= lap_split2],
                3: [e for e in race_data if e.get('lap', 0) > lap_split2]
            }
        else:
            phase_size = total // 3
            phases = {
                1: race_data[:phase_size],
                2: race_data[phase_size:phase_size*2],
                3: race_data[phase_size*2:]
            }

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("DELETE FROM cars WHERE race_id = %s", (race_id,))

        phase = 1
        data_to_insert = []
        for entry in phases[phase]:
            data_to_insert.append((
                race_id,
                entry.get('driver_number'),
                entry.get('speed'),
                entry.get('rpm'),
                entry.get('throttle'),
                entry.get('brake'),
                entry.get('drs', 0) > 0,
                entry.get('n_gear'),
                entry.get('lap', 0),
                entry.get('date')
            ))

        insert_query = """
            INSERT INTO cars (race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time)
            VALUES %s
        """
        psycopg2.extras.execute_values(cursor, insert_query, data_to_insert)

        cursor.execute("DELETE FROM race_phases WHERE race_id = %s", (race_id,))
        for phase_num, phase_data in phases.items():
            cursor.execute(
                "INSERT INTO race_phases (race_id, phase, data) VALUES (%s, %s, %s)",
                (race_id, phase_num, psycopg2.extras.Json(phase_data))
            )

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            'message': 'Simulation ready',
            'total_entries': total,
            'phase_1': len(phases[1]),
            'phase_2': len(phases[2]),
            'phase_3': len(phases[3]),
            'current_phase': 1
        }), 200

    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@data_blueprint.route('/simulate/<race_id>/phase/<int:phase>', methods=['POST'])
def set_phase(race_id, phase):
    """
    Avança para uma fase da corrida (1, 2 ou 3).
    Substitui os dados de telemetria actuais pelos da fase escolhida.
    """
    try:
        if phase not in [1, 2, 3]:
            return jsonify({'error': 'Fase inválida. Use 1, 2 ou 3'}), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "SELECT data FROM race_phases WHERE race_id = %s AND phase = %s",
            (race_id, phase)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            db.close()
            return jsonify({'error': 'Fase não encontrada. Corre /simulate primeiro'}), 404

        phase_data = row[0]

        cursor.execute("DELETE FROM cars WHERE race_id = %s", (race_id,))
        data_to_insert = []
        for entry in phase_data:
            data_to_insert.append((
                race_id,
                entry.get('driver_number'),
                entry.get('speed'),
                entry.get('rpm'),
                entry.get('throttle'),
                entry.get('brake'),
                entry.get('drs', 0) > 0,
                entry.get('n_gear'),
                entry.get('lap', 0),
                entry.get('date')
            ))

        insert_query = """
            INSERT INTO cars (race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time)
            VALUES %s
        """
        psycopg2.extras.execute_values(cursor, insert_query, data_to_insert)
        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            'message': f'Fase {phase} activada',
            'phase': phase,
            'entries': len(data_to_insert)
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500



@data_blueprint.route('/import/fastf1', methods=['POST'])
def import_fastf1():
    """
    Importa dados de performance e stints de uma corrida via FastF1.
    Body JSON: { "year": 2024, "round": 1 }
    Chamado automaticamente pelo results_service após importar uma corrida.
    """
    try:
        data = request.get_json() or {}
        year = data.get('year', 2024)
        round_number = data.get('round', 1)
        race_id = data.get('race_id')

        if not race_id:
            return jsonify({'error': 'race_id é obrigatório'}), 400

        session = fastf1.get_session(year, round_number, 'R')
        loaded = False
        for args in [{'laps': True, 'telemetry': True}, {'laps': True}, {}]:
            try:
                session.load(**args)
                loaded = True
                break
            except:
                continue
        if not loaded:
            return jsonify({'error': 'Não foi possível carregar a sessão'}), 500

        db = get_db_connection()
        cur = db.cursor()

        perf_inserted = 0
        stint_inserted = 0

        if not session.laps.empty:
            for driver_num in session.laps['DriverNumber'].unique():
                driver_laps = session.laps[session.laps['DriverNumber'] == driver_num]
                driver_name = str(driver_laps['Driver'].iloc[0]) if not driver_laps.empty else 'Unknown'

                max_speed = None
                max_rpm = None
                avg_throttle = None
                avg_brake = None
                drs_time = None

                try:
                    tel = driver_laps.get_telemetry()
                    if tel is not None and not tel.empty:
                        max_speed = safe_float(tel['Speed'].max())
                        max_rpm = safe_int(tel['RPM'].max())
                        avg_throttle = safe_float(tel['Throttle'].mean())
                        avg_brake = safe_float(tel['Brake'].astype(float).mean() * 100)
                        if 'DRS' in tel.columns:
                            drs_open_count = len(tel[tel['DRS'] > 9])
                            drs_time = safe_float(drs_open_count * 0.1)
                except Exception as e:
                    print(f"⚠️ Telemetria do piloto {driver_num}: {e}")

                best_lap_time = None
                try:
                    fastest = driver_laps.pick_fastest()
                    if fastest is not None:
                        lt = fastest['LapTime']
                        if lt is not None and str(lt) not in ('nan', 'NaT', 'None'):
                            total_secs = lt.total_seconds()
                            mins = int(total_secs // 60)
                            secs = total_secs % 60
                            best_lap_time = f"{mins:02d}:{secs:06.3f}"
                except:
                    pass

                total_laps = safe_int(driver_laps['LapNumber'].max())

                cur.execute(
                    """
                    INSERT INTO car_performance
                        (race_id, driver_id, driver_name, max_speed, max_rpm,
                         avg_throttle, avg_brake, drs_time, best_lap_time, total_laps)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (race_id, driver_id) DO UPDATE SET
                        max_speed=EXCLUDED.max_speed, max_rpm=EXCLUDED.max_rpm,
                        avg_throttle=EXCLUDED.avg_throttle, avg_brake=EXCLUDED.avg_brake,
                        drs_time=EXCLUDED.drs_time, best_lap_time=EXCLUDED.best_lap_time,
                        total_laps=EXCLUDED.total_laps
                    """,
                    (race_id, safe_int(driver_num), driver_name,
                     max_speed, max_rpm, avg_throttle, avg_brake,
                     drs_time, best_lap_time, total_laps)
                )
                perf_inserted += 1

        if not session.laps.empty and 'Compound' in session.laps.columns:
            cur.execute("DELETE FROM stints WHERE race_id = %s", (race_id,))

            for driver_num in session.laps['DriverNumber'].unique():
                driver_laps = session.laps[session.laps['DriverNumber'] == driver_num].copy()
                driver_name = str(driver_laps['Driver'].iloc[0])
                driver_id = safe_int(driver_num)

                if 'Stint' not in driver_laps.columns:
                    continue

                for stint_num in driver_laps['Stint'].unique():
                    stint_laps = driver_laps[driver_laps['Stint'] == stint_num]
                    if stint_laps.empty:
                        continue

                    compound = safe_str(stint_laps['Compound'].iloc[0])
                    lap_start = safe_int(stint_laps['LapNumber'].min())
                    lap_end = safe_int(stint_laps['LapNumber'].max())
                    tyre_age = safe_int(stint_laps['TyreLife'].iloc[0]) if 'TyreLife' in stint_laps.columns else None
                    is_fresh = bool(stint_laps['FreshTyre'].iloc[0]) if 'FreshTyre' in stint_laps.columns else True

                    cur.execute(
                        """
                        INSERT INTO stints
                            (race_id, driver_id, driver_name, stint_number,
                             compound, lap_start, lap_end, tyre_age, is_fresh)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (race_id, driver_id, driver_name, safe_int(stint_num),
                         compound, lap_start, lap_end, tyre_age, is_fresh)
                    )
                    stint_inserted += 1

        db.commit()
        cur.close()
        db.close()

        return jsonify({
            "message": "FastF1 data import complete",
            "race_id": race_id,
            "perf_inserted": perf_inserted,
            "stint_inserted": stint_inserted
        }), 201

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500


@data_blueprint.route('/performance/<int:race_id>', methods=['GET'])
def get_race_performance(race_id):
    """Retorna performance de todos os pilotos de uma corrida"""
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("""
            SELECT perf_id, race_id, driver_id, driver_name,
                   max_speed, max_rpm, avg_throttle, avg_brake,
                   drs_time, best_lap_time, total_laps, created_at
            FROM car_performance WHERE race_id = %s
            ORDER BY driver_id
        """, (race_id,))
        rows = cur.fetchall()
        cur.close()
        db.close()
        return jsonify([CarPerformance(*r).to_json() for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_blueprint.route('/performance/<int:race_id>/<int:driver_id>', methods=['GET'])
def get_driver_performance(race_id, driver_id):
    """Retorna performance de um piloto específico"""
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("""
            SELECT perf_id, race_id, driver_id, driver_name,
                   max_speed, max_rpm, avg_throttle, avg_brake,
                   drs_time, best_lap_time, total_laps, created_at
            FROM car_performance WHERE race_id = %s AND driver_id = %s
        """, (race_id, driver_id))
        row = cur.fetchone()
        cur.close()
        db.close()
        if not row:
            return jsonify({"error": "Sem dados para este piloto"}), 404
        return jsonify(CarPerformance(*row).to_json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_blueprint.route('/stints/<int:race_id>', methods=['GET'])
def get_race_stints(race_id):
    """Retorna todos os stints de uma corrida"""
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("""
            SELECT stint_id, race_id, driver_id, driver_name,
                   stint_number, compound, lap_start, lap_end,
                   tyre_age, is_fresh, created_at
            FROM stints WHERE race_id = %s
            ORDER BY driver_id, stint_number
        """, (race_id,))
        rows = cur.fetchall()
        cur.close()
        db.close()
        return jsonify([Stint(*r).to_json() for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_blueprint.route('/stints/<int:race_id>/<int:driver_id>', methods=['GET'])
def get_driver_stints(race_id, driver_id):
    """Retorna stints de um piloto específico"""
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute("""
            SELECT stint_id, race_id, driver_id, driver_name,
                   stint_number, compound, lap_start, lap_end,
                   tyre_age, is_fresh, created_at
            FROM stints WHERE race_id = %s AND driver_id = %s
            ORDER BY stint_number
        """, (race_id, driver_id))
        rows = cur.fetchall()
        cur.close()
        db.close()
        return jsonify([Stint(*r).to_json() for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500