from flask_lambda_http import FlaskLambdaHttp
from flask_lambda_rest import FlaskLambdaRest
from flask import request
import json

app = FlaskLambdaHttp(__name__)


@app.route('foo', methods=['POST', 'GET'])
def foo():
    data = {
        'form': request.form.copy(),
        'args': request.args.copy()
    }
    return (
        json.dumps(data, indent=4, sort_keys=True),
        200,
        {'Content-Type': 'application/json'}
    )


if __name__ == '__main__':
    app.run(debug=True)