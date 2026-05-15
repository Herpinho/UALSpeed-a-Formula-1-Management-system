from flask import Blueprint, request, jsonify
import psycopg2
import psycopg2.extras
import os
import time
from model import Car
import requests

OPENF1 = "https://api.openf1.org/v1"
RESULTS_SERVICE = os.getenv('RESULTS_SERVICE', 'http://results-service:5002')

ERROR_RESPONSE_DATA = {'error': 'Error getting data, retry or contact support if problem persists.'}
ERROR_STATUS_CODE = 500

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

@data_blueprint.route('/', methods=['GET'])
def health_check():
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


@data_blueprint.route('/cars/<race_id>/latest', methods=['GET'])
def get_cars_latest(race_id):
    """Obtém o último estado de cada carro em pista"""
    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            SELECT DISTINCT ON (driver_id)
                car_id, race_id, driver_id, speed, rpm, throttle, brake, drs, gear, lap, data_time, created_at
            FROM cars
            WHERE race_id = %s
            ORDER BY driver_id, data_time DESC
        """, (race_id,))
        rows = cursor.fetchall()
        cursor.close()
        db.close()

        cars = [Car(*row).to_json() for row in rows]
        return jsonify({'cars': cars, 'count': len(cars)}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@data_blueprint.route('/simulate/<race_id>', methods=['POST'])
def simulate_race(race_id):
    try:
        race = requests.get(
            f"{RESULTS_SERVICE}/results/races/{race_id}").json()

        race_country = race['country']
        race_name = race['name']
        race_year = race['date'][:4] # Obtém apenas o ano da data
        
        # Na OpenF1 o nome da sessão de corrida é sempre 'Race'
        api_session = requests.get(f"{OPENF1}/sessions?country_name={race_country}&session_name=Race&year={race_year}").json()
        if api_session:
            session_key = api_session[0]['session_key']
        else:
            return jsonify(ERROR_RESPONSE_DATA), ERROR_STATUS_CODE

        car_data = requests.get(f"{OPENF1}/car_data?session_key={session_key}").json()
        db = get_db_connection()
        cursor = db.cursor()
        data_to_insert = []
        for entry in car_data:
            if entry.get('n_gear') is None:
                continue
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
        inserted = len(data_to_insert)
        cursor.close()
        db.close()
    
        return jsonify({'message': 'Simulation complete', 'data saved': inserted}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500