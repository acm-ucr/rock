"""
This is a WSGI application that directly implements the interface described in
`PEP 333 <http://legacy.python.org/dev/peps/pep-0333/>`_. Though
`PEP 3333 <http://legacy.python.org/dev/peps/pep-3333/>`_ supersedes the older
333 specification, the changes are not significant for the purposes of this
application so always refer to PEP 333.

We implement the WSGI interface directly rather than relying on a library like
Werkzeug because I want to aggresively protect against bit rot. The WSGI
interface isn't going to move out from underneath us, and neither is the
standard library. Further, the needs of this application are small, and future
expansion to the feature-set need not be quick. That being said, every effort
is made to ensure that the code is well-documented and easily understood such
that a careful and studious developer can improve the application when
necessary.

"""

# stdlib
import os
import cgi
import httplib
import logging

# Create a logging object we can use throughout the application
log = logging.getLogger("rock")

# Load the configuration file when the module is imported so everyone has
# access to it.


def error_response(code, start_response):
    """
    Sends a simple error response to the user that includes the error code and
    a generic description of the error.

    :param code: The error code (ex: 404).
    :param start_response: The same ``start_response`` callable provided to
        the WSGI app.

    :returns: An iterable appropriate to return from the WSGI app callable.

    """

    # Get a textual description of the error so we can give it to the user.
    description = httplib.responses[code]

    # The status should look similar to 404 Not Found
    status = "{} {}".format(code, description)

    # Figure out any headers we need
    headers = [("Content-Type", "text/plain")]

    # Figure out the content we're going to send to the user
    content = status

    start_response(status, headers)
    return [content]

def app(environ, start_response):
    """
    The entry point to our application. Every request we receive will start
    here.

    .. seealso::

        http://legacy.python.org/dev/peps/pep-0333/#the-application-framework-side

    """

    # We don't support anything but POST requests so tell them to go away if
    # they try anything else.
    if environ["REQUEST_METHOD"] != "POST":
        # See http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.4.6
        # for more information on this response.
        return error_response(405, start_response)

    # CSRF attacks are very common, and though we do not have the ability to
    # protect against these attacks using the typical token-per-form approach
    # checking the referrer header seems to be a solid approach when done
    # right. Hopefully I'm doing it right here. For more information on this
    # see https://www.owasp.org/index.php/Cross-Site_Request_Forgery_%28CSRF%29_Prevention_Cheat_Sheet#Checking_The_Referer_Header
    print environ["REFERRER"]

    # Associate paths with different handling functions
    ROUTE_TABLE = {}

    # Grab the path they're trying to hit (like /check or /join)
    path_info = environ["PATH_INFO"]
    if path_info not in ROUTE_TABLE:
        return error_response(404, start_response)

    # Let the cgi module parse out the form data we received.
    form_data_storage = cgi.FieldStorage(
        fp = environ["wsgi.input"],
        environ = environ,
        keep_blank_values = True
    )

    # Convert the form data into a more convenient dictionary. We also decode
    # the text here. We expect the text to be encoded using UTF-8 because
    # browsers should default to using the encoding that the document is
    # encoded in (which is UTF-8 for our site). All the keys and values in
    # this dictionary will be unicode objects.
    form_data = {}
    for i in form_data_storage.keys():
        key = i.decode("utf_8")
        value = form_data_storage[i].value.decode("utf_8")
        form_data[key] = value


    status = '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return ['Hello world!\n']
