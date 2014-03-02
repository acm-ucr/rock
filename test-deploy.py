#!/usr/bin/env python

"""
This script will serve both the static portion of the website and the dynamic
(WSGI) portion of the site. It doesn't require any dependencies outside of the
standard library so it should serve as useful tool in development or demoing.

You can see how to use the script by typing ``python test-deploy.py -h`` into
your shell of choice.

.. warning::

    Do not use this in a production environment to deploy the site. Ignoring
    the fact that it will be very slow, this is not a secure application.

"""

# We won't be able to figure out where we are in the file system using our
# method below if we are imported, so make sure to error appropriately if
# someone tried to import us.
if __name__ != "__main__":
    raise ImportError("This script should not be imported.")

# stdlib
import sys
import os
import mimetypes
import wsgiref
import wsgiref.simple_server

# internal
import signup_server.main

DEFAULT_PORT = 8000
"""The default port to listen on if no port is provided on the command line."""

DEFAULT_ADDRESS = "localhost"
"""The default address to listen on if no address is provided."""

SCRIPT_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
"""The directory the script is running within."""

STATIC_DIR = os.path.join(SCRIPT_DIR, "main_site")
"""The directory containing the static portions of the site."""

def proxy_app(environ, start_response):
    """
    This is a WSGI application according to the
    `PEP 333 <http://legacy.python.org/dev/peps/pep-0333/>`_ standard and will
    perform very rudimentary routing between the static portion of our site
    and our dynamic WSGI portion. There is a little bit of security checking
    that is done but try to avoid exposing this application to the outside
    world as it is not battle-hardened by any means.

    """

    # Figure out what path the user is requesting (so if they hit
    # localhost:8000/taco/time.htm, then /taco/time.htm would be in path_info).
    path_info = environ.get("PATH_INFO", "")

    # If the user didn't specify a path explicitly, give them the index
    if path_info == "/":
        path_info = "index.htm"
    # Otherwise, cut off any leading slash so we can treat it as a relative
    # file path later.
    elif path_info.startswith("/"):
        path_info = path_info[1:]

    # Figure out the path of the file they're requesting (if they're
    # requesting a static file). The realpath function will resolve symbolic
    # links which is important for the security check next.
    file_path = os.path.realpath(os.path.join(STATIC_DIR, path_info))

    # Make sure the file requested is within the static directory. This will
    # only fail if they used any .. strings in their path or if they found any
    # other symbolic links out of the directory.
    if not file_path.startswith(STATIC_DIR):
        start_response("403 FORBIDDEN", [])
        return ["GO AWAY\n"]

    if os.path.isfile(file_path):
        # We have to tell the user what kind of file we're giving it (text,
        # image, cupcakes). The simplest way to do this is to look at the
        # extension of the file we're about to serve and guess at the data
        # inside using that information. The mimtypes module has a function
        # that does the guessing for us. The encoding has to do with whether
        # or not the files are compressed or otherwise transformed, we don't
        # use it.
        mime_type, encoding = mimetypes.guess_type(file_path)

        # Send the headers to the user that tell them we're serving them a page
        # and that tell them the type of page we're serving.
        start_response("200 OK", [("Content-type", mime_type)])

        # Wrap the file in something that will transform it into a list-like
        # object and then return it.
        return wsgiref.util.FileWrapper(open(file_path, "rb"))
    else:
        # If we're not serving a status file we want to let our application
        # code handle it, so just call our main wsgi app to deal with the
        # rest.
        return signup_server.main.app(environ, start_response)

def main():
    # Grab all of the arguments the user gave us, ignoring the first argument
    # (which is typically the relative path of the script).
    arguments = sys.argv[1:]

    # Print out the usage text if the user asked for it
    if "-h" in arguments or "--help" in arguments:
        print "Usage: {} [PORT={}] [ADDRESS={}]".format(
            sys.argv[0], DEFAULT_PORT, DEFAULT_ADDRESS)
        return 0

    # The first argument is the port number
    if len(arguments) >= 1:
        port = arguments[0]
    else:
        port = DEFAULT_PORT

    # The next is the address
    if len(arguments) >= 2:
        address = arguments[1]
    else:
        address = DEFAULT_ADDRESS

    # Serve the application until our process is killed
    httpd = wsgiref.simple_server.make_server(address, port, proxy_app)
    httpd.serve_forever()

# We make sure the script is not being imported above so we don't have to
# have the typical if __name__ ==... magic here.
sys.exit(main())
