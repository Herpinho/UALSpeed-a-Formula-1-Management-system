from flask import Flask
from controller import results_blueprint
import os

app = Flask(__name__)

#pedir ao flask para nao alterar a ordem dos dados
app.config['JSON_SORT_KEYS'] = False

app.register_blueprint(results_blueprint, url_prefix="/results")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5002))
    app.run(debug=True, host="0.0.0.0", port=port)
