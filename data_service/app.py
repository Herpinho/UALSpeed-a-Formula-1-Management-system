from flask import Flask
from flask_cors import CORS
from controller import data_blueprint
import os

app = Flask(__name__)

app.config['JSON_SORT_KEYS'] = False

CORS(app)

app.register_blueprint(data_blueprint, url_prefix='/data')

if __name__ == '__main__':
    port = int(os.getenv('DPORT', 5003))
    app.run(debug=True, host='0.0.0.0', port=port)