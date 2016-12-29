flask-lambda
============

Python module to make Flask compatible with AWS Lambda for creating RESTful applications.

Installation
------------

::

    pip install flask-lambda

Usage
-----

This module works pretty much just like Flask. This allows you to run and develop this applicaiton locally just like you would in Flask.  When ready deploy to Lambda, and configure the handler as::

    my_python_file.app

Here is an example of what ``my_python_file.py`` would look like::

    from flask_lambda import FlaskLambda

    app = FlaskLambda(__name__)


    @app.route('/foo', methods=['GET', 'POST'])
    def foo():
        data = {
            'form': request.form.copy(),
            'args': request.args.copy(),
            'json': request.json
        }
        return (
            json.dumps(data, indent=4, sort_keys=True),
            200,
            {'Content-Type': 'application/json'}
        )


    if __name__ == '__main__':
        app.run(debug=True)

Flask-RESTful
-------------

Nothing special here, this module works without issue with Flask-RESTful as well.

API Gateway
-----------

Configure your API Gateway with a ``{proxy+}`` resource with an ``ANY`` method. Your "Method Response" should likely include an ``application/json`` "Response Body for 200" that uses the ``Empty`` model.

Deploying
---------

Consider using `python-mu <https://github.com/sivel/mu>`_.

Lambda Test Event
-----------------

If you wish to use the "Test" functionality in Lambda for your function, you will need a "API Gateway AWS Proxy" event.  Below is an event to test the above sample application::

    {
      "body": "{\"test\":\"body\"}",
      "resource": "/{proxy+}",
      "requestContext": {
        "resourceId": "123456",
        "apiId": "1234567890",
        "resourcePath": "/{proxy+}",
        "httpMethod": "POST",
        "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
        "accountId": "123456789012",
        "identity": {
          "apiKey": null,
          "userArn": null,
          "cognitoAuthenticationType": null,
          "caller": null,
          "userAgent": "Custom User Agent String",
          "user": null,
          "cognitoIdentityPoolId": null,
          "cognitoIdentityId": null,
          "cognitoAuthenticationProvider": null,
          "sourceIp": "127.0.0.1",
          "accountId": null
        },
        "stage": "prod"
      },
      "queryStringParameters": {
        "foo": "bar"
      },
      "headers": {
        "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
        "Accept-Language": "en-US,en;q=0.8",
        "CloudFront-Is-Desktop-Viewer": "true",
        "CloudFront-Is-SmartTV-Viewer": "false",
        "CloudFront-Is-Mobile-Viewer": "false",
        "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
        "CloudFront-Viewer-Country": "US",
        "Accept": "application/json",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-Port": "443",
        "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
        "X-Forwarded-Proto": "https",
        "X-Amz-Cf-Id": "cDehVQoZnx43VYQb9j2-nvCh-9z396Uhbp027Y2JvkCPNLmGJHqlaA==",
        "CloudFront-Is-Tablet-Viewer": "false",
        "Cache-Control": "max-age=0",
        "User-Agent": "Custom User Agent String",
        "CloudFront-Forwarded-Proto": "https",
        "Accept-Encoding": "gzip, deflate, sdch",
        "Content-Type": "application/json"
      },
      "pathParameters": {
        "proxy": "foo"
      },
      "httpMethod": "POST",
      "stageVariables": {
        "baz": "qux"
      },
      "path": "/foo"
    }

To update your test event, click "Actions" -> "Configure test event".
