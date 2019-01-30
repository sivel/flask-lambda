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

from sys import stderr

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

from flask import Flask

import six

from werkzeug import urls
from werkzeug.wsgi import ClosingIterator
from werkzeug.wrappers import BaseResponse, Response


__version__ = '0.0.4'


def titlecase_keys(d):
    """
    Takes a dict with keys of type str and returns a new dict with all keys titlecased.
    """
    return {k.title(): v for k, v in d.items()}


def get_wsgi_string(string, encoding='utf-8'):
    """
    Returns wsgi-compatible string
    """
    return string.encode(encoding).decode('iso-8859-1')


def all_casings(input_string):
    """
    Permute all casings of a given string.

    A pretty algorithm, via @Amber
    http://stackoverflow.com/questions/6792803/finding-all-possible-case-permutations-in-python
    """
    if not input_string:
        yield ""
    else:
        first = input_string[:1]
        if first.lower() == first.upper():
            for sub_casing in all_casings(input_string[1:]):
                yield first + sub_casing
        else:
            for sub_casing in all_casings(input_string[1:]):
                yield first.lower() + sub_casing
                yield first.upper() + sub_casing


class WSGIMiddleware(object):

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        """
        We must case-mangle the Set-Cookie header name or AWS will use only a
        single one of these headers.
        """

        def encode_response(status, headers, exc_info=None):
            """
            Create an APIGW-acceptable version of our cookies.

            We have to use a bizarre hack that turns multiple Set-Cookie headers into
            their case-permutated format, ex:

            Set-cookie:
            sEt-cookie:
            seT-cookie:

            To get around an API Gateway limitation.

            This is weird, but better than our previous hack of creating a Base58-encoded
            supercookie.
            """

            # All the non-cookie headers should be sent unharmed.

            # The main app can send 'set-cookie' headers in any casing
            # Related: https://github.com/Miserlou/Zappa/issues/990
            new_headers = [header for header in headers
                           if ((type(header[0]) != str) or (header[0].lower() != 'set-cookie'))]
            cookie_headers = [header for header in headers
                              if ((type(header[0]) == str) and (header[0].lower() == "set-cookie"))]
            for header, new_name in zip(cookie_headers,
                                        all_casings("Set-Cookie")):
                new_headers.append((new_name, header[1]))
            return start_response(status, new_headers, exc_info)

        # Call the application with our modifier
        response = self.application(environ, encode_response)

        # Return the response as a WSGI-safe iterator
        return ClosingIterator(response)


class HealthCheckMiddleware(object):

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'] == '/_health_check':
            resp = BaseResponse('ok', status=200)
            return resp(environ, start_response)
        return self.app(environ, start_response)


def create_wsgi_request(event_info):
    """
    Given some event_info via API Gateway,
    create and return a valid WSGI request environ.
    """
    method = event_info['httpMethod']
    params = event_info['pathParameters']
    query = event_info['queryStringParameters']  # APIGW won't allow multiple entries, ex ?id=a&id=b
    headers = event_info['headers'] or {}

    # Extract remote user from context if Authorizer is enabled
    remote_user = None
    if event_info['requestContext'].get('authorizer'):
        remote_user = event_info['requestContext']['authorizer'].get('principalId')
    elif event_info['requestContext'].get('identity'):
        remote_user = event_info['requestContext']['identity'].get('userArn')

    body = event_info['body']
    if isinstance(body, six.string_types):
        body = body.encode("utf-8")

    # Make header names canonical, e.g. content-type => Content-Type
    # https://github.com/Miserlou/Zappa/issues/1188
    headers = titlecase_keys(headers)

    path = urls.url_unquote(event_info['path'])

    if query:
        query_string = urlencode(query)
    else:
        query_string = ""

    x_forwarded_for = headers.get('X-Forwarded-For', '')
    if ',' in x_forwarded_for:
        # The last one is the cloudfront proxy ip. The second to last is the real client ip.
        # Everything else is user supplied and untrustworthy.
        remote_addr = x_forwarded_for.split(', ')[-2]
    else:
        remote_addr = '127.0.0.1'

    environ = {
        'PATH_INFO': get_wsgi_string(path),
        'QUERY_STRING': get_wsgi_string(query_string),
        'REMOTE_ADDR': remote_addr,
        'REQUEST_METHOD': method,
        'SCRIPT_NAME': '',
        'SERVER_NAME': '',
        'SERVER_PORT': headers.get('X-Forwarded-Port', '80'),
        'SERVER_PROTOCOL': str('HTTP/1.1'),
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': headers.get('X-Forwarded-Proto', 'http'),
        'wsgi.input': body,
        'wsgi.errors': stderr,
        'wsgi.multiprocess': False,
        'wsgi.multithread': False,
        'wsgi.run_once': False,
    }

    # Input processing
    if method in ["POST", "PUT", "PATCH", "DELETE"]:
        if 'Content-Type' in headers:
            environ['CONTENT_TYPE'] = headers['Content-Type']

        # This must be Bytes or None
        environ['wsgi.input'] = six.BytesIO(body)
        if body:
            environ['CONTENT_LENGTH'] = str(len(body))
        else:
            environ['CONTENT_LENGTH'] = '0'

    for header in headers:
        wsgi_name = "HTTP_" + header.upper().replace('-', '_')
        environ[wsgi_name] = str(headers[header])

    if remote_user:
        environ['REMOTE_USER'] = remote_user

    if event_info['requestContext'].get('authorizer'):
        environ['API_GATEWAY_AUTHORIZER'] = event_info['requestContext']['authorizer']

    return environ


def _call(self, event, context):
    # This is a normal HTTP request
    self.wsgi_app_wrapped = WSGIMiddleware(HealthCheckMiddleware(self.wsgi_app))

    if not event.get('httpMethod', None):
        return self.wsgi_app_wrapped(event, context)

    # Create the environment for WSGI and handle the request
    environ = create_wsgi_request(event)

    # We are always on https on Lambda, so tell our wsgi app that.
    environ['HTTPS'] = 'on'
    environ['wsgi.url_scheme'] = 'https'
    environ['lambda.context'] = context
    environ['lambda.event'] = event

    # Execute the application
    with Response.from_app(self.wsgi_app, environ) as response:
        # This is the object we're going to return.
        # Pack the WSGI response into our special dictionary.
        returndict = dict()

        if response.data:
            returndict['body'] = response.get_data(as_text=True)

        returndict['statusCode'] = response.status_code
        returndict['headers'] = {}
        for key, value in response.headers:
            returndict['headers'][key] = value

        return returndict


class FlaskLambda(Flask):

    def __call__(self, event, context):
        return _call(self, event, context)


class LambdaMiddleware(object):

    def __init__(self, app):
        self.wsgi_app = app

    def __call__(self, event, context):
        return _call(self, event, context)
