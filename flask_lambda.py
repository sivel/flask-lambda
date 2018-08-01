# -*- coding: utf-8 -*-
# Copyright 2016 Matt Martz
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import sys
import logging
import base64
from werkzeug.wrappers import Response

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

from flask import Flask

try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

from werkzeug.wrappers import BaseRequest


__version__ = '0.0.4'
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def make_environ(event):
    environ = {}
    headers = event['headers'] or {}

    for hdr_name, hdr_value in headers.items():
        hdr_name = hdr_name.replace('-', '_').upper()
        if hdr_name in ['CONTENT_TYPE', 'CONTENT_LENGTH']:
            environ[hdr_name] = hdr_value
            continue

        http_hdr_name = 'HTTP_%s' % hdr_name
        environ[http_hdr_name] = hdr_value

    if 'HTTP_X_FORWARDED_PORT' not in environ:
        environ['HTTP_X_FORWARDED_PORT'] = '443'
    if 'HTTP_X_FORWARDED_PROTO' not in environ:
        environ['HTTP_X_FORWARDED_PROTO'] = 'https'

    qs = event['queryStringParameters']

    environ['REQUEST_METHOD'] = event['httpMethod']
    environ['PATH_INFO'] = event['path']
    environ['QUERY_STRING'] = urlencode(qs) if qs else ''
    environ['REMOTE_ADDR'] = event['requestContext']['identity']['sourceIp']
    environ['HOST'] = '%(HTTP_HOST)s:%(HTTP_X_FORWARDED_PORT)s' % environ
    environ['SCRIPT_NAME'] = ''

    environ['SERVER_PORT'] = environ['HTTP_X_FORWARDED_PORT']
    environ['SERVER_PROTOCOL'] = 'HTTP/1.1'

    if 'isBase64Encoded' in event and event['isBase64Encoded'] is True:
        if 'body' in event and event['body'] is not None and 0 < len(event['body']):
            tmp_body = base64.b64decode(event['body'])
            environ['CONTENT_LENGTH'] = str(len(tmp_body))
            environ['wsgi.input'] = StringIO(tmp_body.decode('utf-8'))
        else:
            environ['CONTENT_LENGTH'] = '0'
            environ['wsgi.input'] = StringIO('')
    else:
        environ['CONTENT_LENGTH'] = str(
            len(event['body']) if event['body'] else ''
        )
        environ['wsgi.input'] = StringIO(event['body'] or '')

    environ['wsgi.url_scheme'] = environ['HTTP_X_FORWARDED_PROTO']
    environ['wsgi.version'] = (1, 0)
    environ['wsgi.errors'] = sys.stderr
    environ['wsgi.multithread'] = False
    environ['wsgi.run_once'] = True
    environ['wsgi.multiprocess'] = False

    if 'Content-Type' in headers:
        environ['CONTENT_TYPE'] = headers['Content-Type']

    BaseRequest(environ)

    return environ


class LambdaResponse(object):
    def __init__(self):
        self.status = None
        self.response_headers = None

    def start_response(self, status, response_headers, exc_info=None):
        _ = exc_info
        self.status = int(status[:3])
        self.response_headers = dict(response_headers)


class FlaskLambda(Flask):
    def __call__(self, event, context):
        global logger
        if 'httpMethod' not in event:
            # In this "context" `event` is `environ` and
            # `context` is `start_response`, meaning the request didn't
            # occur via API Gateway and Lambda
            logger.info('Calling non-lambda flask app')
            return super(FlaskLambda, self).__call__(event, context)

        logger.info('Calling lambda flask app for following event: ' + str(event))

        flask_environment = make_environ(event)
        body = Response.from_app(self.wsgi_app, flask_environment)

        if body.data:
            if body.mimetype.startswith("text/") or body.mimetype.startswith("application/json"):
                response_body = body.get_data(as_text=True)
                is_base64_encoded = False
            else:
                response_body = base64.b64encode(body.data).decode('utf-8')
                is_base64_encoded = True
        else:
            response_body = ""
            is_base64_encoded = False

        ret = {
            'statusCode': body.status_code,
            'headers': {},
            'body': response_body
        }

        if is_base64_encoded:
            ret['isBase64Encoded'] = "true"

        for key, value in body.headers:
            ret['headers'][key] = value

        logger.info('Response of lambda app: ' + str(ret))
        return ret
