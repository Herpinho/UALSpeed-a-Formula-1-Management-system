from flask import Blueprint, request, jsonify
import psycopg2
import os
import fastf1
import requests
from model import Race, RaceResult, Lap, Standing, Driver, Team

results_blueprint = Blueprint('results', __name__)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'ualspeed'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

def get_db_connection():
    """Cria conexão com a base de dados"""
    return psycopg2.connect(**DB_CONFIG)



@results_blueprint.route('/', methods=['GET'])
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
        conn = get_db_connection()
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
        conn = get_db_connection()
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

        conn = get_db_connection()
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

        conn = get_db_connection()
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
        conn = get_db_connection()
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
        conn = get_db_connection()
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

        conn = get_db_connection()
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

        conn = get_db_connection()
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
        conn = get_db_connection()
        cur = conn.cursor()
        
        status = request.args.get('status')  
        
        if status:
            cur.execute(
                "SELECT race_id, name, circuit, country, date, total_laps, status FROM races WHERE status = %s ORDER BY date DESC",
                (status,)
            )
        else:
            cur.execute(
                "SELECT race_id, name, circuit, country, date, total_laps, status FROM races ORDER BY date DESC"
            )
        
        rows = cur.fetchall()
        races = []
        
        for row in rows:
            race = Race(*row)
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
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT race_id, name, circuit, country, date, total_laps, status FROM races WHERE race_id = %s",
            (race_id,)
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
            return jsonify({"error": "Race not found"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@results_blueprint.route('/classification/<int:race_id>', methods=['GET'])
def get_classification(race_id):
    """Obter classificação atual de uma corrida (resultados ordenados por posição)"""
    try:
        conn = get_db_connection()
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
        
        conn = get_db_connection()
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



@results_blueprint.route('/races/<int:race_id>/status', methods=['PUT'])
def update_race_status(race_id):
    """Atualizar o status de uma corrida (scheduled, live, completed)"""
    try:
        data = request.get_json()
        status = data.get('status')

        conn = get_db_connection()
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
        
        conn = get_db_connection()
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
        conn = get_db_connection()
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
        conn = get_db_connection()
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
        
        conn = get_db_connection()
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
        conn = get_db_connection()
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
        
        conn = get_db_connection()
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
        conn = get_db_connection()
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
        conn = get_db_connection()
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
        conn = get_db_connection()
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
        
        conn = get_db_connection()
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
        conn = get_db_connection()
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


@results_blueprint.route('/import/fastf1', methods=['POST'])
def import_fastf1():
    """
    Importa dados históricos reais de uma corrida usando FastF1.
    Body JSON: { "year": 2024, "round": 1 }
    Exemplo: year=2024, round=1 → Grande Prémio do Bahrain 2024
    """
    try:
        data  = request.get_json()
        year  = data.get('year', 2024)
        round_number = data.get('round', 1)

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
            return jsonify({'error': 'Não foi possível carregar a sessão do FastF1'}), 500

        conn = get_db_connection()
        cur  = conn.cursor()

        # ── 1. Inserir a corrida ─────────────────────────────────────────────
        event      = session.event
        race_name  = str(event['EventName'])
        circuit    = str(event['Location'])
        country    = str(event['Country'])
        race_date  = str(event['EventDate'].date())
        total_laps = int(session.laps['LapNumber'].max()) if not session.laps.empty else 50

        cur.execute(
            """INSERT INTO races (name, circuit, country, date, total_laps, status)
               VALUES (%s, %s, %s, %s, %s, 'completed')
               ON CONFLICT DO NOTHING
               RETURNING race_id""",
            (race_name, circuit, country, race_date, total_laps)
        )
        row = cur.fetchone()
        if not row:
            # Já existia — vai buscar o id
            cur.execute("SELECT race_id FROM races WHERE name=%s AND date=%s", (race_name, race_date))
            row = cur.fetchone()
        race_id = row[0]

        import math
        def safe_int(val, default=0):
            try:
                f = float(val)
                return default if math.isnan(f) else int(f)
            except (TypeError, ValueError):
                return default 

        def safe_str(val):
            if val is None:
                return None
            s = str(val)
            return None if s in ('', 'nan', 'NaT', 'None') else s

        # ── 2. Inserir resultados finais ─────────────────────────────────────
        results_inserted = 0
        if session.results is not None and not session.results.empty:
            for _, driver_row in session.results.iterrows():
                driver_id   = safe_int(driver_row.get('DriverNumber'), 0)
                driver_name = str(driver_row.get('FullName', 'Unknown'))
                team        = str(driver_row.get('TeamName', 'Unknown'))
                position    = safe_int(driver_row.get('Position'), 0)
                points      = safe_int(driver_row.get('Points'), 0)
                status      = 'finished' if driver_row.get('Status') == 'Finished' else 'dnf'
                fastest_lap = safe_str(driver_row.get('FastestLapTime'))
                total_time  = safe_str(driver_row.get('Time'))

                if driver_id == 0:
                    continue

                cur.execute(
                    """INSERT INTO race_results
                       (race_id, driver_id, driver_name, team, position, points, fastest_lap, total_time, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT DO NOTHING""",
                    (race_id, driver_id, driver_name, team, position, points,
                     fastest_lap, total_time, status)
                )
                results_inserted += 1

        # ── 3. Inserir voltas ────────────────────────────────────────────────
        laps_inserted = 0
        if not session.laps.empty:
            for _, lap_row in session.laps.iterrows():
                driver_id   = safe_int(lap_row.get('DriverNumber'), 0)
                driver_name = str(lap_row.get('Driver', 'Unknown'))
                lap_number  = safe_int(lap_row.get('LapNumber'), 0)
                lap_time    = safe_str(lap_row.get('LapTime'))
                sector1     = safe_str(lap_row.get('Sector1Time'))
                sector2     = safe_str(lap_row.get('Sector2Time'))
                sector3     = safe_str(lap_row.get('Sector3Time'))
                position    = safe_int(lap_row.get('Position'), None)

                if not lap_time or driver_id == 0 or lap_number == 0:
                    continue

                cur.execute(
                    """INSERT INTO laps
                       (race_id, driver_id, driver_name, lap_number, lap_time, sector1, sector2, sector3, position)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (race_id, driver_id, lap_number) DO NOTHING""",
                    (race_id, driver_id, driver_name, lap_number,
                     lap_time, sector1, sector2, sector3, position)
                )
                laps_inserted += 1

        # 4. Inserir meteorologia
        weather_inserted = False
        try:
            if hasattr(session, 'weather_data') and session.weather_data is not None and not session.weather_data.empty:
                wd = session.weather_data
                import math
                def sf(val):
                    try:
                        f = float(val)
                        return None if math.isnan(f) else f
                    except:
                        return None
                cur.execute(
                    "INSERT INTO weather (race_id, air_temp_avg, air_temp_min, air_temp_max, track_temp_avg, track_temp_min, track_temp_max, humidity_avg, pressure_avg, wind_speed_avg, wind_dir_avg, rainfall) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (race_id) DO UPDATE SET air_temp_avg=EXCLUDED.air_temp_avg, track_temp_avg=EXCLUDED.track_temp_avg, rainfall=EXCLUDED.rainfall",
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
        cur.close()
        conn.close()

        return jsonify({
            "message": "FastF1 import complete",
            "race_id": race_id,
            "race_name": race_name,
            "results_inserted": results_inserted,
            "laps_inserted": laps_inserted,
            "weather_inserted": weather_inserted,
            "data_imported": data_imported,
            "perf_inserted": perf_inserted,
            "stint_inserted": stint_inserted
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

        conn = get_db_connection()
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