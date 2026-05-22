from flask import Flask
from flask_cors import CORS
from controller import metrics_blueprint, start_background_checker
import os

app = Flask(__name__)

app.config['JSON_SORT_KEYS'] = False

CORS(app)

app.register_blueprint(metrics_blueprint, url_prefix='/metrics')

if __name__ == '__main__':
    start_background_checker()
    port = int(os.getenv('MPORT', 5004))
    app.run(debug=True, host='0.0.0.0', port=port)