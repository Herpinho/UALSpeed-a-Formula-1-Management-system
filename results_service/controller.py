from flask import Blueprint, request, jsonify
import psycopg2
import os
import math
import fastf1
import requests
from model import Race, RaceResult, Lap, Standing, Driver, Team

results_blueprint = Blueprint('results', __name__)

DB_MASTER_HOST = os.getenv('DB_MASTER_HOST', 'postgres-results-master')
DB_SLAVE_HOST  = os.getenv('DB_SLAVE_HOST', 'postgres-results-slave')
DB_PORT        = os.getenv('DB_PORT', '5432')
DB_NAME        = os.getenv('DB_NAME', 'ualspeed_results')
DB_USER        = os.getenv('DB_USER', 'postgres')
DB_PASSWORD    = os.getenv('DB_PASSWORD', 'postgres')

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
            password=DB_PASSWORD,
            connect_timeout=2
        )
    except Exception as e:
        print(f"error: {e}, falling back to master")
        return get_write_connection()


DEMO_RACE_NAME = os.getenv('DEMO_RACE_NAME', 'UALSpeed Demo Race')
DEMO_RACE_CIRCUIT = os.getenv('DEMO_RACE_CIRCUIT', 'UALSpeed Circuit')
DEMO_RACE_COUNTRY = os.getenv('DEMO_RACE_COUNTRY', 'Portugal')
DEMO_RACE_DATE = os.getenv('DEMO_RACE_DATE', '2026-05-25')
DEMO_RACE_TOTAL_LAPS = int(os.getenv('DEMO_RACE_TOTAL_LAPS', '5'))

DEMO_RESULTS = [
    {'driver_id': 44, 'driver_name': 'Alex Martins', 'team': 'Red Falcon', 'position': 1, 'points': 25, 'fastest_lap': '1:29.824', 'total_time': '00:45:12.421', 'status': 'finished'},
    {'driver_id': 16, 'driver_name': 'Sofia Pereira', 'team': 'Blue Arrow', 'position': 2, 'points': 18, 'fastest_lap': '1:30.102', 'total_time': '00:45:18.775', 'status': 'finished'},
    {'driver_id': 11, 'driver_name': 'Tomás Costa', 'team': 'Silver Pulse', 'position': 3, 'points': 15, 'fastest_lap': '1:30.488', 'total_time': '00:45:25.110', 'status': 'finished'},
]

DEMO_LAPS = [
    (44, 'Alex Martins', 1, '1:31.200', '0:31.000', '0:30.200', '0:30.000', 1),
    (44, 'Alex Martins', 2, '1:30.980', '0:30.920', '0:30.100', '0:29.960', 1),
    (44, 'Alex Martins', 3, '1:30.620', '0:30.780', '0:29.980', '0:29.860', 1),
    (44, 'Alex Martins', 4, '1:30.112', '0:30.510', '0:29.820', '0:29.782', 1),
    (44, 'Alex Martins', 5, '1:29.824', '0:30.300', '0:29.700', '0:29.824', 1),
    (16, 'Sofia Pereira', 1, '1:31.740', '0:31.220', '0:30.310', '0:30.210', 2),
    (16, 'Sofia Pereira', 2, '1:31.060', '0:30.940', '0:30.090', '0:30.030', 2),
    (16, 'Sofia Pereira', 3, '1:30.740', '0:30.800', '0:29.950', '0:29.990', 2),
    (16, 'Sofia Pereira', 4, '1:30.332', '0:30.640', '0:29.850', '0:29.842', 2),
    (16, 'Sofia Pereira', 5, '1:30.102', '0:30.420', '0:29.760', '0:29.922', 2),
    (11, 'Tomás Costa', 1, '1:32.010', '0:31.500', '0:30.300', '0:30.210', 3),
    (11, 'Tomás Costa', 2, '1:31.480', '0:31.180', '0:30.140', '0:30.160', 3),
    (11, 'Tomás Costa', 3, '1:31.040', '0:30.950', '0:30.020', '0:30.070', 3),
    (11, 'Tomás Costa', 4, '1:30.720', '0:30.710', '0:29.930', '0:30.080', 3),
    (11, 'Tomás Costa', 5, '1:30.488', '0:30.620', '0:29.910', '0:29.958', 3),
]

DEMO_WEATHER = {
    'air_temp_avg': 24.8,
    'air_temp_min': 23.9,
    'air_temp_max': 25.6,
    'track_temp_avg': 31.5,
    'track_temp_min': 30.7,
    'track_temp_max': 32.2,
    'humidity_avg': 41.2,
    'pressure_avg': 1011.4,
    'wind_speed_avg': 11.7,
    'wind_dir_avg': 184.0,
    'rainfall': False,
}


def seed_demo_race(conn, race_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM race_results WHERE race_id = %s", (race_id,))
    cur.execute("DELETE FROM laps WHERE race_id = %s", (race_id,))
    cur.execute("DELETE FROM weather WHERE race_id = %s", (race_id,))

    for result in DEMO_RESULTS:
        cur.execute(
            """INSERT INTO race_results
               (race_id, driver_id, driver_name, team, position, points, fastest_lap, total_time, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (race_id, result['driver_id'], result['driver_name'], result['team'], result['position'], result['points'], result['fastest_lap'], result['total_time'], result['status'])
        )

    for driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position in DEMO_LAPS:
        cur.execute(
            """INSERT INTO laps
               (race_id, driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (race_id, driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position)
        )

    cur.execute(
        """INSERT INTO weather
           (race_id, air_temp_avg, air_temp_min, air_temp_max, track_temp_avg, track_temp_min, track_temp_max, humidity_avg, pressure_avg, wind_speed_avg, wind_dir_avg, rainfall)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (race_id) DO UPDATE SET
               air_temp_avg=EXCLUDED.air_temp_avg,
               air_temp_min=EXCLUDED.air_temp_min,
               air_temp_max=EXCLUDED.air_temp_max,
               track_temp_avg=EXCLUDED.track_temp_avg,
               track_temp_min=EXCLUDED.track_temp_min,
               track_temp_max=EXCLUDED.track_temp_max,
               humidity_avg=EXCLUDED.humidity_avg,
               pressure_avg=EXCLUDED.pressure_avg,
               wind_speed_avg=EXCLUDED.wind_speed_avg,
               wind_dir_avg=EXCLUDED.wind_dir_avg,
               rainfall=EXCLUDED.rainfall""",
        (race_id, DEMO_WEATHER['air_temp_avg'], DEMO_WEATHER['air_temp_min'], DEMO_WEATHER['air_temp_max'], DEMO_WEATHER['track_temp_avg'], DEMO_WEATHER['track_temp_min'], DEMO_WEATHER['track_temp_max'], DEMO_WEATHER['humidity_avg'], DEMO_WEATHER['pressure_avg'], DEMO_WEATHER['wind_speed_avg'], DEMO_WEATHER['wind_dir_avg'], DEMO_WEATHER['rainfall'])
    )

    conn.commit()
    cur.close()


def import_fastf1_race(year, round_number, race_name_override=None, status='completed'):
    """Importa uma corrida FastF1 para a base de dados e devolve os metadados."""
    conn = get_read_connection()
    cur = conn.cursor()
    
    # Verificar se a corrida já existe
    cur.execute(
        "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races WHERE year = %s AND round = %s",
        (year, round_number)
    )
    existing_race = cur.fetchone()
    cur.close()
    conn.close()
    if existing_race:
        return {
            "race_id": existing_race[0],
            "race": Race(existing_race[0], existing_race[1], existing_race[2], existing_race[3], existing_race[4], existing_race[5], existing_race[6], existing_race[7], existing_race[8]).to_json(),
            "results_inserted": 0,
            "laps_inserted": 0,
            "weather_inserted": False,
            "data_imported": False,
            "perf_inserted": 0,
            "stint_inserted": 0,
            "error": f"Corrida {year} R{round_number} já existe na base de dados"
        }
    
    session = fastf1.get_session(year, round_number, 'R')
    loaded = False
    for load_args in [
        {'laps': True, 'results': True, 'telemetry': False},
        {'laps': True, 'results': True},
        {},
    ]:
        try:
            session.load(**load_args)
            loaded = True
            break
        except Exception:
            continue
    if not loaded:
        raise RuntimeError('Não foi possível carregar a sessão do FastF1')

    event = session.event
    race_name = race_name_override or str(event['EventName'])
    circuit = str(event['Location'])
    country = str(event['Country'])
    race_date = str(event['EventDate'].date())
    total_laps = int(session.laps['LapNumber'].max()) if not session.laps.empty else 50
    conn = get_write_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO races (name, circuit, country, date, total_laps, round, year, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING race_id""",
        (race_name, circuit, country, race_date, total_laps, round_number, year, status)
    )
    race_id = cur.fetchone()[0]

    def safe_int(val, default=0):
        try:
            f = float(val)
            return default if math.isnan(f) else int(f)
        except Exception:
            return default

    def safe_str(val):
        if val is None:
            return None
        s = str(val)
        return None if s in ('', 'nan', 'NaT', 'None') else s

    results_inserted = 0
    if session.results is not None and not session.results.empty:
        for _, driver_row in session.results.iterrows():
            driver_id = safe_int(driver_row.get('DriverNumber'), 0)
            driver_name = str(driver_row.get('FullName', 'Unknown'))
            team = str(driver_row.get('TeamName', 'Unknown'))
            position = safe_int(driver_row.get('Position'), 0)
            points = safe_int(driver_row.get('Points'), 0)
            
            # Lógica para detetar o estado real do piloto (Finished, DNS, DNF, DSQ)
            f1_status = str(driver_row.get('Status', '')).strip()
            
            # Verificar se o piloto tem voltas registadas (quem é DNS não tem voltas nem telemetria)
            has_laps = False
            if session.laps is not None and not session.laps.empty:
                has_laps = not session.laps[session.laps['DriverNumber'].astype(str) == str(driver_id)].empty

            if f1_status == 'Finished' or f1_status.startswith('+'):
                status_value = 'finished'
            elif f1_status == 'Disqualified':
                status_value = 'dsq'
            elif f1_status == 'DNS' or not has_laps:
                # Se não tem voltas e não terminou/foi desqualificado, é DNS
                status_value = 'dns'
            else:
                # Se tem voltas mas não terminou, é DNF
                status_value = 'dnf'

            fastest_lap = safe_str(driver_row.get('FastestLapTime'))
            total_time = safe_str(driver_row.get('Time'))

            if driver_id == 0:
                continue

            cur.execute(
                """INSERT INTO race_results
                   (race_id, driver_id, driver_name, team, position, points, fastest_lap, total_time, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (race_id, driver_id, driver_name, team, position, points, fastest_lap, total_time, status_value)
            )
            results_inserted += 1

    laps_inserted = 0
    if not session.laps.empty:
        for _, lap_row in session.laps.iterrows():
            driver_id = safe_int(lap_row.get('DriverNumber'), 0)
            driver_name = str(lap_row.get('Driver', 'Unknown'))
            lap_number = safe_int(lap_row.get('LapNumber'), 0)
            lap_time = safe_str(lap_row.get('LapTime'))
            sector1 = safe_str(lap_row.get('Sector1Time'))
            sector2 = safe_str(lap_row.get('Sector2Time'))
            sector3 = safe_str(lap_row.get('Sector3Time'))
            position = safe_int(lap_row.get('Position'), None)

            if not lap_time or driver_id == 0 or lap_number == 0:
                continue

            cur.execute(
                """INSERT INTO laps
                   (race_id, driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (race_id, driver_id, lap_number) DO NOTHING""",
                (race_id, driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position)
            )
            laps_inserted += 1

    weather_inserted = False
    try:
        if hasattr(session, 'weather_data') and session.weather_data is not None and not session.weather_data.empty:
            wd = session.weather_data

            def sf(val):
                try:
                    f = float(val)
                    return None if math.isnan(f) else f
                except Exception:
                    return None

            cur.execute(
                """INSERT INTO weather
                   (race_id, air_temp_avg, air_temp_min, air_temp_max, track_temp_avg, track_temp_min, track_temp_max, humidity_avg, pressure_avg, wind_speed_avg, wind_dir_avg, rainfall)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (race_id) DO UPDATE SET
                       air_temp_avg=EXCLUDED.air_temp_avg,
                       track_temp_avg=EXCLUDED.track_temp_avg,
                       rainfall=EXCLUDED.rainfall""",
                (race_id, sf(wd['AirTemp'].mean()), sf(wd['AirTemp'].min()), sf(wd['AirTemp'].max()),
                 sf(wd['TrackTemp'].mean()), sf(wd['TrackTemp'].min()), sf(wd['TrackTemp'].max()),
                 sf(wd['Humidity'].mean()), sf(wd['Pressure'].mean()),
                 sf(wd['WindSpeed'].mean()), sf(wd['WindDirection'].mean()),
                 bool(wd['Rainfall'].any()))
            )
            weather_inserted = True
    except Exception as we:
        print(f"Erro meteorologia: {we}")

    data_imported = False
    perf_inserted = 0
    stint_inserted = 0
    try:
        data_service_url = os.getenv('DATA_SERVICE', 'http://data-service:5003')
        data_resp = requests.post(
            f"{data_service_url}/data/import/fastf1",
            json={"year": year, "round": round_number, "race_id": race_id},
            timeout=120
        )
        if data_resp.ok:
            data_payload = data_resp.json()
            data_imported = True
            perf_inserted = data_payload.get('perf_inserted', 0)
            stint_inserted = data_payload.get('stint_inserted', 0)
    except Exception as data_error:
        print(f"Erro ao importar dados FastF1 para o data service: {data_error}")

    conn.commit()

    cur.execute(
        "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races WHERE race_id = %s",
        (race_id,)
    )
    race_row = cur.fetchone()
    cur.close()
    conn.close()

    return {
        "race_id": race_id,
        "race": Race(race_row[0], race_row[1], race_row[2], race_row[3], race_row[4], race_row[5], race_row[6], race_row[7], race_row[8]).to_json() if race_row else None,
        "results_inserted": results_inserted,
        "laps_inserted": laps_inserted,
        "weather_inserted": weather_inserted,
        "data_imported": data_imported,
        "perf_inserted": perf_inserted,
        "stint_inserted": stint_inserted,
    }



@results_blueprint.route('/health', methods=['GET'])
def health_check():
    """Health check do serviço"""
    return jsonify({
        "service": "UALSpeed Results Service",
        "status": "running",
        "version": "1.0.0"
    }), 200


# ─── Equipas ──────────────────────────────────────────────────────────────────

@results_blueprint.route('/teams', methods=['GET'])
def get_teams():
    """Obter todas as equipas"""
    try:
        conn = get_read_connection()
        cur  = conn.cursor()

        cur.execute("SELECT team_id, name, nationality, car_model FROM teams ORDER BY name")
        rows = cur.fetchall()

        teams = [Team(*row).to_json() for row in rows]

        cur.close()
        conn.close()
        return jsonify(teams), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/teams/<int:team_id>', methods=['GET'])
def get_team(team_id):
    """Obter detalhes de uma equipa"""
    try:
        conn = get_read_connection()
        cur  = conn.cursor()

        cur.execute("SELECT team_id, name, nationality, car_model FROM teams WHERE team_id = %s", (team_id,))
        row = cur.fetchone()

        cur.close()
        conn.close()

        if row:
            return jsonify(Team(*row).to_json()), 200
        return jsonify({"error": "Team not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/teams', methods=['POST'])
def create_team():
    """Criar nova equipa"""
    try:
        data = request.get_json()

        conn = get_write_connection()
        cur  = conn.cursor()

        cur.execute(
            """INSERT INTO teams (name, nationality, car_model)
               VALUES (%s, %s, %s) RETURNING team_id""",
            (data['name'], data.get('nationality'), data.get('car_model'))
        )

        team_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Team created successfully", "team_id": team_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/teams/<int:team_id>', methods=['PUT'])
def update_team(team_id):
    """Atualizar equipa"""
    try:
        data = request.get_json()

        conn = get_write_connection()
        cur  = conn.cursor()

        cur.execute(
            """UPDATE teams SET name=%s, nationality=%s, car_model=%s
               WHERE team_id=%s""",
            (data['name'], data.get('nationality'), data.get('car_model'), team_id)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Team updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Pilotos ──────────────────────────────────────────────────────────────────

@results_blueprint.route('/drivers', methods=['GET'])
def get_drivers():
    """Obter todos os pilotos"""
    try:
        conn = get_read_connection()
        cur  = conn.cursor()

        cur.execute("""
            SELECT d.driver_id, d.name, d.nationality, d.number, d.team_id, t.name
            FROM drivers d
            LEFT JOIN teams t ON t.team_id = d.team_id
            ORDER BY d.number
        """)
        rows = cur.fetchall()

        drivers = [Driver(*row).to_json() for row in rows]

        cur.close()
        conn.close()
        return jsonify(drivers), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/drivers/<int:driver_id>', methods=['GET'])
def get_driver(driver_id):
    """Obter detalhes de um piloto"""
    try:
        conn = get_read_connection()
        cur  = conn.cursor()

        cur.execute("""
            SELECT d.driver_id, d.name, d.nationality, d.number, d.team_id, t.name
            FROM drivers d
            LEFT JOIN teams t ON t.team_id = d.team_id
            WHERE d.driver_id = %s
        """, (driver_id,))
        row = cur.fetchone()

        cur.close()
        conn.close()

        if row:
            return jsonify(Driver(*row).to_json()), 200
        return jsonify({"error": "Driver not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/drivers', methods=['POST'])
def create_driver():
    """Criar novo piloto"""
    try:
        data = request.get_json()

        conn = get_write_connection()
        cur  = conn.cursor()

        cur.execute(
            """INSERT INTO drivers (name, nationality, number, team_id)
               VALUES (%s, %s, %s, %s) RETURNING driver_id""",
            (data['name'], data.get('nationality'), data['number'], data.get('team_id'))
        )

        driver_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Driver created successfully", "driver_id": driver_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/drivers/<int:driver_id>', methods=['PUT'])
def update_driver(driver_id):
    """Atualizar piloto"""
    try:
        data = request.get_json()

        conn = get_write_connection()
        cur  = conn.cursor()

        cur.execute(
            """UPDATE drivers SET name=%s, nationality=%s, number=%s, team_id=%s
               WHERE driver_id=%s""",
            (data['name'], data.get('nationality'), data['number'],
             data.get('team_id'), driver_id)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Driver updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races', methods=['GET'])
def get_races():
    """Obter todas as corridas"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        status = request.args.get('status')  
        
        if status:
            cur.execute(
                "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races WHERE status = %s ORDER BY date DESC",
                (status,)
            )
        else:
            cur.execute(
                "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races ORDER BY date DESC"
            )
        
        rows = cur.fetchall()
        races = []
        
        for row in rows:
            race = Race(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
            races.append(race.to_json())
        
        cur.close()
        conn.close()
        
        return jsonify(races), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/<int:race_id>', methods=['GET'])
def get_race(race_id):
    """Obter detalhes de uma corrida específica"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races WHERE race_id = %s",
            (race_id,)
        )
        
        row = cur.fetchone()
        
        if row:
            race = Race(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
            cur.close()
            conn.close()
            return jsonify(race.to_json()), 200
        else:
            cur.close()
            conn.close()
            return jsonify({"error": "Race not found"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/classification/<int:race_id>', methods=['GET'])
def get_classification(race_id):
    """Obter classificação atual de uma corrida (resultados ordenados por posição)"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()

        top_speeds = {}
        try:
            data_service_url = os.getenv('DATA_SERVICE', 'http://data-service:5003')
            import requests as req
            cars_resp = req.get(f"{data_service_url}/data/cars/{race_id}/latest", timeout=2)
            if cars_resp.status_code == 200:
                for car in cars_resp.json().get('cars', []):
                    top_speeds[car['driver_id']] = car.get('top_speed') or car.get('speed', 0)
        except Exception:
            pass

        cur.execute("""
            SELECT driver_id, driver_name, team, position, points, fastest_lap, total_time, status
            FROM race_results
            WHERE race_id = %s
            ORDER BY position ASC
        """, (race_id,))
        rows = cur.fetchall()

        if rows:
            def fmt_time(t):
                if not t:
                    return None
                s = str(t)
                s = s.replace('0 days ', '')
                if '.' in s:
                    s = s[:s.index('.') + 4]  
                return s

            # Tempo do 1º classificado para calcular diferenças
            leader_time_str = str(rows[0][6]) if rows[0][6] else None

            classification = []
            prev_secs = 0
            last_lap_ref = 0
            laps_down = 0
            for i, row in enumerate(rows):
                driver_id  = row[0]
                total_time = fmt_time(row[6])
                fastest    = fmt_time(row[5])

                def to_seconds(t):
                    try:
                        t = str(t).replace('0 days ', '')
                        parts = t.split(':')
                        h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
                        return h * 3600 + m * 60 + s
                    except:
                        return None

                def seconds_to_str(secs):
                    if secs is None:
                        return None
                    h = int(secs // 3600)
                    m = int((secs % 3600) // 60)
                    s = secs % 60
                    return f"{h:02d}:{m:02d}:{s:06.3f}"

                # Calcula tempo total real para todos os pilotos
                leader_secs = to_seconds(rows[0][6]) if rows[0][6] else None
                current_secs = to_seconds(row[6]) if row[6] else None

                if i == 0:
                    gap = 'Líder'
                    real_total = total_time
                    prev_secs = 0        
                    last_lap_ref = 0     
                    laps_down = 0
                elif leader_secs is not None and current_secs is not None:
                    if current_secs < 600:
                        if laps_down == 0:
                            if current_secs >= prev_secs:
                                gap = f'+{current_secs:.3f}s'
                                real_total = seconds_to_str(leader_secs + current_secs)
                                prev_secs = current_secs
                            else:
                                # Primeira volta em atraso
                                laps_down = 1
                                last_lap_ref = current_secs
                                gap = '+1 Lap'
                                real_total = '—'
                        else:
                            # Já há voltas em atraso — deteta novo salto
                            if current_secs < last_lap_ref:
                                laps_down += 1
                                last_lap_ref = current_secs
                                gap = f'+{laps_down} Laps'
                                real_total = '—'
                            else:
                                # Mesmo grupo de voltas em atraso
                                last_lap_ref = current_secs
                                gap = f'+{laps_down} Lap' if laps_down == 1 else f'+{laps_down} Laps'
                                real_total = '—'
                    elif current_secs < leader_secs:
                        laps_down += 1
                        gap = f'+{laps_down} Lap' if laps_down == 1 else f'+{laps_down} Laps'
                        real_total = '—'
                    else:
                        diff = current_secs - leader_secs
                        gap = f'+{diff:.3f}s' if diff > 0 else 'Líder'
                        real_total = total_time
                        prev_secs = diff
                else:
                    gap = '—'
                    real_total = total_time

                classification.append({
                    "driver_id":     driver_id,
                    "driver_name":   row[1],
                    "team_name":     row[2],
                    "position":      row[3],
                    "points":        row[4],
                    "fastest_lap":   fastest,
                    "total_time":    real_total,
                    "status":        row[7],
                    "top_speed":     top_speeds.get(driver_id, 0),
                    "gap_to_leader": gap,
                    "driver_number": driver_id
                })
            cur.close()
            conn.close()
            return jsonify({
                "race_id": race_id,
                "source": "results",
                "classification": classification
            }), 200

        # Se não houver resultados finais, usa as voltas
        cur.execute("""
            SELECT DISTINCT ON (driver_id)
                driver_id,
                driver_name,
                MAX(lap_number) OVER (PARTITION BY driver_id) AS current_lap,
                MIN(lap_time)   OVER (PARTITION BY driver_id) AS best_lap
            FROM laps
            WHERE race_id = %s
            ORDER BY driver_id, lap_number DESC
        """, (race_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        classification = []
        for i, row in enumerate(sorted(rows, key=lambda x: -(x[2] or 0))):
            driver_id = row[0]
            classification.append({
                "driver_id":   driver_id,
                "driver_name": row[1],
                "team_name":   "—",
                "current_lap": row[2],
                "best_lap":    row[3],
                "position":    i + 1,
                "top_speed":   top_speeds.get(driver_id, 0)
            })

        return jsonify({
            "race_id": race_id,
            "source": "laps",
            "classification": classification
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races', methods=['POST'])
def create_race():
    """Criar nova corrida"""
    try:
        data = request.get_json()
        
        conn = get_write_connection()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO races (name, circuit, country, date, total_laps, status) 
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING race_id""",
            (data['name'], data['circuit'], data['country'], 
             data.get('date'), data['total_laps'], data.get('status', 'scheduled'))
        )
        
        race_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Race created successfully", "race_id": race_id}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@results_blueprint.route('/races/<int:race_id>', methods=['DELETE'])
def delete_race(race_id):
    """Eliminar uma corrida e todos os seus dados associados"""
    try:
        conn = get_write_connection()
        cur = conn.cursor()

        # Eliminar dados dependentes primeiro para respeitar a integridade referencial
        cur.execute("DELETE FROM race_results WHERE race_id = %s", (race_id,))
        cur.execute("DELETE FROM laps WHERE race_id = %s", (race_id,))
        cur.execute("DELETE FROM weather WHERE race_id = %s", (race_id,))
        
        # Finalmente, eliminar a corrida
        cur.execute("DELETE FROM races WHERE race_id = %s", (race_id,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": f"Corrida {race_id} eliminada com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@results_blueprint.route('/races/delete-multiple', methods=['POST'])
def delete_multiple_races():
    """Eliminar várias corridas e os seus dados associados de uma só vez"""
    try:
        data = request.get_json()
        race_ids = data.get('race_ids', [])
        if not race_ids:
            return jsonify({"message": "Nenhuma corrida selecionada"}), 200

        conn = get_write_connection()
        cur = conn.cursor()
        ids_tuple = tuple(race_ids)

        # Eliminar dados dependentes em cascata manual para as corridas selecionadas
        cur.execute("DELETE FROM race_results WHERE race_id IN %s", (ids_tuple,))
        cur.execute("DELETE FROM laps WHERE race_id IN %s", (ids_tuple,))
        cur.execute("DELETE FROM weather WHERE race_id IN %s", (ids_tuple,))
        cur.execute("DELETE FROM races WHERE race_id IN %s", (ids_tuple,))

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": f"{len(race_ids)} corrida(s) eliminada(s) com sucesso"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/demo', methods=['POST'])
def create_demo_race():
    """Cria ou reutiliza a corrida demo persistida na base de dados."""
    try:
        conn = get_write_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races WHERE name = %s ORDER BY created_at DESC LIMIT 1",
            (DEMO_RACE_NAME,)
        )
        row = cur.fetchone()

        if row:
            cur.execute("SELECT COUNT(*) FROM race_results WHERE race_id = %s", (row[0],))
            results_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM laps WHERE race_id = %s", (row[0],))
            laps_count = cur.fetchone()[0]

            race = Race(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
            if results_count > 0 and laps_count > 0:
                try:
                    data_service_url = os.getenv('DATA_SERVICE', 'http://data-service:5003')
                    requests.post(
                        f"{data_service_url}/data/demo/seed",
                        json={"race_id": race.race_id},
                        timeout=10
                    )
                    # Depois de semear a demo, copia telemetria do piloto fonte (ex: Leclerc) para os outros
                    try:
                        requests.post(
                            f"{data_service_url}/data/demo/copy-telemetry",
                            json={"race_id": race.race_id},
                            timeout=10
                        )
                    except Exception as copy_err:
                        print(f"Erro ao copiar telemetria da demo: {copy_err}")
                except Exception as seed_error:
                    print(f"Erro ao preparar demo no data service: {seed_error}")

                cur.close()
                conn.close()
                return jsonify({
                    "created": False,
                    "race_id": race.race_id,
                    "race": race.to_json()
                }), 200

            race_id = race.race_id
        else:
            cur.execute(
                """INSERT INTO races (name, circuit, country, date, total_laps, round, year, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING race_id""",
                (DEMO_RACE_NAME, DEMO_RACE_CIRCUIT, DEMO_RACE_COUNTRY, DEMO_RACE_DATE, DEMO_RACE_TOTAL_LAPS, 999, 2026, 'live')
            )
            race_id = cur.fetchone()[0]
            conn.commit()

        seed_demo_race(conn, race_id)

        try:
            data_service_url = os.getenv('DATA_SERVICE', 'http://data-service:5003')
            requests.post(
                f"{data_service_url}/data/demo/seed",
                json={"race_id": race_id},
                timeout=10
            )
            # Copiar telemetria do piloto fonte para os outros após semear
            try:
                requests.post(
                    f"{data_service_url}/data/demo/copy-telemetry",
                    json={"race_id": race_id},
                    timeout=10
                )
            except Exception as copy_err:
                print(f"Erro ao copiar telemetria da demo: {copy_err}")
        except Exception as seed_error:
            print(f"Erro ao preparar demo no data service: {seed_error}")

        cur.execute(
            "SELECT race_id, name, circuit, country, date, total_laps, status, round, year FROM races WHERE race_id = %s",
            (race_id,)
        )
        seeded_row = cur.fetchone()
        cur.close()
        conn.close()

        return jsonify({
            "created": True,
            "race_id": race_id,
            "race": Race(seeded_row[0], seeded_row[1], seeded_row[2], seeded_row[3], seeded_row[4], seeded_row[5], seeded_row[6], seeded_row[7], seeded_row[8]).to_json() if seeded_row else None,
            "results_inserted": len(DEMO_RESULTS),
            "laps_inserted": len(DEMO_LAPS),
            "weather_inserted": True,
            "data_imported": True,
            "perf_inserted": 3,
            "stint_inserted": 6
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/races/<int:race_id>/status', methods=['PUT'])
def update_race_status(race_id):
    """Atualizar o status de uma corrida (scheduled, live, completed)"""
    try:
        data = request.get_json()
        status = data.get('status')

        conn = get_write_connection()
        cur = conn.cursor()

        cur.execute(
            "UPDATE races SET status = %s WHERE race_id = %s",
            (status, race_id)
        )
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": f"Race {race_id} status updated to {status}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/<int:race_id>', methods=['PUT'])
def update_race(race_id):
    """Atualizar corrida"""
    try:
        data = request.get_json()
        
        conn = get_write_connection()
        cur = conn.cursor()
        
        cur.execute(
            """UPDATE races SET name = %s, circuit = %s, country = %s, 
               date = %s, total_laps = %s, status = %s 
               WHERE race_id = %s""",
            (data['name'], data['circuit'], data['country'], 
             data.get('date'), data['total_laps'], data.get('status'), race_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Race updated successfully"}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/current', methods=['GET'])
def get_current_race():
    """Obter corrida atual (status = live)"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT race_id, name, circuit, country, date, total_laps, status FROM races WHERE status = 'live' LIMIT 1"
        )
        
        row = cur.fetchone()
        
        if row:
            race = Race(*row)
            cur.close()
            conn.close()
            return jsonify(race.to_json()), 200
        else:
            cur.execute(
                "SELECT race_id, name, circuit, country, date, total_laps, status FROM races WHERE status = 'scheduled' ORDER BY date LIMIT 1"
            )
            row = cur.fetchone()
            
            if row:
                race = Race(*row)
                cur.close()
                conn.close()
                return jsonify(race.to_json()), 200
            else:
                cur.close()
                conn.close()
                return jsonify({"error": "No current or upcoming race"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/races/<int:race_id>/results', methods=['GET'])
def get_race_results(race_id):
    """Obter resultados de uma corrida"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        cur.execute(
            """SELECT result_id, race_id, driver_id, driver_name, team, 
               position, points, fastest_lap, total_time, status 
               FROM race_results WHERE race_id = %s ORDER BY position""",
            (race_id,)
        )
        
        rows = cur.fetchall()
        results = []
        
        for row in rows:
            result = RaceResult(*row)
            results.append(result.to_json())
        
        cur.close()
        conn.close()
        
        return jsonify(results), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/<int:race_id>/results', methods=['POST'])
def create_race_result(race_id):
    """Adicionar resultado de um piloto numa corrida"""
    try:
        data = request.get_json()
        
        conn = get_write_connection()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO race_results 
               (race_id, driver_id, driver_name, team, position, points, fastest_lap, total_time, status) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING result_id""",
            (race_id, data['driver_id'], data['driver_name'], data['team'],
             data['position'], data.get('points', 0), data.get('fastest_lap'),
             data.get('total_time'), data.get('status', 'finished'))
        )
        
        result_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Result created successfully", "result_id": result_id}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/races/<int:race_id>/laps', methods=['GET'])
def get_race_laps(race_id):
    """Obter todas as voltas de uma corrida"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        driver_id = request.args.get('driver_id')  
        
        if driver_id:
            cur.execute(
                """SELECT lap_id, race_id, driver_id, driver_name, lap_number, 
                   lap_time, sector1, sector2, sector3, position 
                   FROM laps WHERE race_id = %s AND driver_id = %s ORDER BY lap_number""",
                (race_id, driver_id)
            )
        else:
            cur.execute(
                """SELECT lap_id, race_id, driver_id, driver_name, lap_number, 
                   lap_time, sector1, sector2, sector3, position 
                   FROM laps WHERE race_id = %s ORDER BY lap_number, position""",
                (race_id,)
            )
        
        rows = cur.fetchall()
        laps = []
        
        for row in rows:
            lap = Lap(*row)
            laps.append(lap.to_json())
        
        cur.close()
        conn.close()
        
        return jsonify(laps), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/<int:race_id>/laps', methods=['POST'])
def create_lap(race_id):
    """Registar uma volta"""
    try:
        data = request.get_json()
        
        conn = get_write_connection()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO laps 
               (race_id, driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
               ON CONFLICT (race_id, driver_id, lap_number) 
               DO UPDATE SET lap_time = EXCLUDED.lap_time, 
                           sector1 = EXCLUDED.sector1,
                           sector2 = EXCLUDED.sector2,
                           sector3 = EXCLUDED.sector3,
                           position = EXCLUDED.position
               RETURNING lap_id""",
            (race_id, data['driver_id'], data['driver_name'], data['lap_number'],
             data['lap_time'], data.get('sector1'), data.get('sector2'), 
             data.get('sector3'), data.get('position'))
        )
        
        lap_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Lap recorded successfully", "lap_id": lap_id}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/races/<int:race_id>/fastest-lap', methods=['GET'])
def get_fastest_lap(race_id):
    """Obter a volta mais rápida de uma corrida"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        cur.execute(
            """SELECT lap_id, race_id, driver_id, driver_name, lap_number, 
               lap_time, sector1, sector2, sector3, position 
               FROM laps WHERE race_id = %s 
               ORDER BY lap_time LIMIT 1""",
            (race_id,)
        )
        
        row = cur.fetchone()
        
        if row:
            lap = Lap(*row)
            cur.close()
            conn.close()
            return jsonify(lap.to_json()), 200
        else:
            cur.close()
            conn.close()
            return jsonify({"error": "No laps found for this race"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/standings', methods=['GET'])
def get_standings():
    """Obter classificação geral dos pilotos"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        cur.execute(
            """SELECT standing_id, driver_id, driver_name, team, position, 
               points, wins, podiums, fastest_laps 
               FROM standings ORDER BY position"""
        )
        
        rows = cur.fetchall()
        standings = []
        
        for row in rows:
            standing = Standing(*row)
            standings.append(standing.to_json())
        
        cur.close()
        conn.close()
        
        return jsonify(standings), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/standings/<int:driver_id>', methods=['GET'])
def get_driver_standing(driver_id):
    """Obter classificação de um piloto específico"""
    try:
        conn = get_read_connection()
        cur = conn.cursor()
        
        cur.execute(
            """SELECT standing_id, driver_id, driver_name, team, position, 
               points, wins, podiums, fastest_laps 
               FROM standings WHERE driver_id = %s""",
            (driver_id,)
        )
        
        row = cur.fetchone()
        
        if row:
            standing = Standing(*row)
            cur.close()
            conn.close()
            return jsonify(standing.to_json()), 200
        else:
            cur.close()
            conn.close()
            return jsonify({"error": "Driver not found in standings"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/standings', methods=['POST'])
def update_standings():
    """Atualizar ou criar entrada na classificação"""
    try:
        data = request.get_json()
        
        conn = get_write_connection()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO standings 
               (driver_id, driver_name, team, position, points, wins, podiums, fastest_laps) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
               ON CONFLICT (driver_id) 
               DO UPDATE SET driver_name = EXCLUDED.driver_name,
                           team = EXCLUDED.team,
                           position = EXCLUDED.position,
                           points = EXCLUDED.points,
                           wins = EXCLUDED.wins,
                           podiums = EXCLUDED.podiums,
                           fastest_laps = EXCLUDED.fastest_laps,
                           updated_at = CURRENT_TIMESTAMP
               RETURNING standing_id""",
            (data['driver_id'], data['driver_name'], data['team'], data['position'],
             data['points'], data.get('wins', 0), data.get('podiums', 0), 
             data.get('fastest_laps', 0))
        )
        
        standing_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Standing updated successfully", "standing_id": standing_id}), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500




# Cache local para o FastF1 
CACHE_DIR = os.getenv("FASTF1_CACHE", "/tmp/fastf1_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)



@results_blueprint.route('/weather/<int:race_id>', methods=['GET'])
def get_weather(race_id):
    try:
        conn = get_read_connection()
        cur  = conn.cursor()
        cur.execute("SELECT air_temp_avg, air_temp_min, air_temp_max, track_temp_avg, track_temp_min, track_temp_max, humidity_avg, pressure_avg, wind_speed_avg, wind_dir_avg, rainfall FROM weather WHERE race_id = %s", (race_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Sem dados meteorologicos"}), 404
        return jsonify({
            "race_id": race_id, "air_temp_avg": row[0], "air_temp_min": row[1], "air_temp_max": row[2],
            "track_temp_avg": row[3], "track_temp_min": row[4], "track_temp_max": row[5],
            "humidity_avg": row[6], "pressure_avg": row[7], "wind_speed_avg": row[8],
            "wind_dir_avg": row[9], "rainfall": row[10]
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/calendar/<int:year>', methods=['GET'])
def get_calendar(year):
    """Devolve o calendário de corridas de um ano via FastF1"""
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        races = []
        for _, event in schedule.iterrows():
            races.append({
                "round":   int(event['RoundNumber']),
                "name":    str(event['EventName']),
                "circuit": str(event['Location']),
                "country": str(event['Country']),
                "date":    str(event['EventDate'].date()),
            })
        return jsonify({"year": year, "races": races}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/import/fastf1', methods=['POST'])
def import_fastf1():
    """Importa dados históricos reais de uma corrida usando FastF1."""
    try:
        data = request.get_json() or {}
        year = data.get('year', 2024)
        round_number = data.get('round', 1)

        payload = import_fastf1_race(year, round_number)
        return jsonify({
            "message": "FastF1 import complete",
            **payload
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@results_blueprint.route('/import/fastf1/standings', methods=['POST'])
def import_fastf1_standings():
    """
    Importa os standings reais de um ano usando FastF1.
    Body JSON: { "year": 2024 }
    """
    try:
        data = request.get_json()
        year = data.get('year', 2024)

        schedule = fastf1.get_event_schedule(year, include_testing=False)

        driver_points = {}  

        conn = get_write_connection()
        cur  = conn.cursor()

        cur.execute("""
            SELECT driver_id, driver_name, team,
                   SUM(points) AS total_points,
                   COUNT(*) FILTER (WHERE position = 1) AS wins,
                   COUNT(*) FILTER (WHERE position <= 3) AS podiums
            FROM race_results
            GROUP BY driver_id, driver_name, team
            ORDER BY total_points DESC
        """)
        rows = cur.fetchall()

        position = 1
        for row in rows:
            driver_id, driver_name, team, points, wins, podiums = row
            cur.execute(
                """INSERT INTO standings
                   (driver_id, driver_name, team, position, points, wins, podiums, fastest_laps)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                   ON CONFLICT (driver_id) DO UPDATE SET
                       position     = EXCLUDED.position,
                       points       = EXCLUDED.points,
                       wins         = EXCLUDED.wins,
                       podiums      = EXCLUDED.podiums,
                       updated_at   = CURRENT_TIMESTAMP""",
                (driver_id, driver_name, team, position, int(points or 0),
                 int(wins or 0), int(podiums or 0))
            )
            position += 1

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "Standings updated successfully",
            "drivers_updated": len(rows)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500