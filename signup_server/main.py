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
import sys
import cgi
import httplib
import logging
import ConfigParser
import wsgiref
import sqlite3
import datetime

# internal
import database

# Create a logging object we can use throughout the application
log = logging.getLogger("rock")

CONFIG_PATH_VAR = "ROCK_CONFIG"
"""
The name of the enviornmental variable to check for the path of the
configuration file to load.

"""

DEFAULT_CONFIG_PATH = "/etc/rock/config.ini"
"""
If the environmental variable named by ``CONFIG_PATH_VAR`` is not set, this
is the configuration file that will be loaded.

"""

# This will hold a dictionary containing our configuration options
config = None

# This will hold our sqlite3.Connection object we'll use to query our database
db = None

# Load the configuration file when the module is imported so everyone has
# access to it.
def initialize():
    """
    This performs any initialization logic for our application. It will be run
    once per WSGI process.

    """

    # Let the user know how the configuration file is going to be loaded
    if CONFIG_PATH_VAR in os.environ:
        print ("Environmental variable {} set. Loading configuration at "
            "{}.".format(CONFIG_PATH_VAR, os.environ[CONFIG_PATH_VAR]))
    else:
        print ("Environmental variable {} not set. Loading default "
            "configuration at {}.".format(
                CONFIG_PATH_VAR, DEFAULT_CONFIG_PATH))

    # Actually load the configuration file
    config_file_path = os.environ.get(CONFIG_PATH_VAR, DEFAULT_CONFIG_PATH)
    config_file = open(config_file_path, "r")

    # Parse the configuration file
    config_parser = ConfigParser.RawConfigParser()
    config_parser.readfp(config_file)

    # This will grab all of the configuration options under the rock section
    # in the ini file and put them in our config dictionary.
    global config
    config = dict(config_parser.items("rock"))

    global db
    db = sqlite3.connect(config["db_file"])

# Run our initialization code. This will occur when this module is first
# imported.
initialize()

def error_response(code, start_response):
    """
    Sends a simple error response to the user that includes the error code and
    a generic description of the error.

    .. note::

        This function should be used to serve every error response, but it does
        not know how to properly do that necessarily. When serving an error
        that isn't served anywhere else, make sure to modify this function
        as needed.

    :param code: The error code (ex: 404).
    :param start_response: The same ``start_response`` callable provided to
        the WSGI app.

    :returns: An iterable appropriate to return from the WSGI app callable.

    """

    # Get a textual description of the error so we can give it to the user
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

    The environ parameter contains a lot of information and figuring out where
    the information you want is can be confusing. You should consult the
    `environ Variables <http://legacy.python.org/dev/peps/pep-0333/#environ-variables>`_
    section of the spec in  such situations.

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

    # This will grab the url of our application. For example,
    # http://localhost:8000 or http://acm.cs.ucr.edu might be the value here
    app_url = wsgiref.util.application_uri(environ)
    if not environ.get("HTTP_REFERER", "").startswith(app_url):
        # There's not really an ideal status code to return here but
        # unauthorized seemed like the best fit.
        return error_response(401, start_response)

    # Associate paths with different handling functions
    ROUTE_TABLE = {"/join": handle_join, "/check": handle_check}

    # Grab the path they're trying to hit (like /check or /join)
    path_info = environ["PATH_INFO"]
    if path_info not in ROUTE_TABLE:
        return error_response(404, start_response)
    handler = ROUTE_TABLE[path_info]

    # Let the cgi module parse out the form data we received
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

    return handler(form_data, start_response)

def handle_join(form_data, start_response):
    # This ensures that the member table is created and that it has the exact
    # columns we expect it to.
    database.Member.create_table(db)

    # Add the member to the database
    new_member = database.Member(
        joined = datetime.datetime.today(),
        email = form_data["email"],
        name = form_data["name"],
        shirt_size = form_data["shirt-size"],
        paid_on = None
    )
    try:
        new_member.insert(db)
    except sqlite3.IntegrityError:
        # This will occur if the email that was provided was not unique or some
        # other contraint was violated. We will assume the case is the former,
        # but check the logs for the actual exception if users are reporting
        # difficulties joining.
        log.info("Could not add user with email %r to database.",
            exc_info = True)

    status = "200 OK"
    response_headers = [("Content-type", "text/plain")]
    start_response(status, response_sheaders)
    return ["I am a teapot."]

def handle_check(form_data, start_response):
    status = "200 OK"
    response_headers = [("Content-type", "text/plain")]
    start_response(status, response_headers)
    return [repr(form_data)]
