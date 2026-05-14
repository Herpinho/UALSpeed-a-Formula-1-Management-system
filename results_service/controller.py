from flask import Blueprint, request, jsonify
import psycopg2
import os
from model import Race, RaceResult, Lap, Standing

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


@results_blueprint.route('/races', methods=['GET'])
def get_races():
    """Obter todas as corridas"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        status = request.args.get('status')  # Filtrar por status
        
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
            # Se não houver corrida live, retornar a próxima agendada
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
        
        driver_id = request.args.get('driver_id')  # Filtrar por piloto
        
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
