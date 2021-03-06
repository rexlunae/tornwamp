
WAMPnado
========

This Python module implements parts of `WAMP <https://wamp-proto.org/>`_
(Web Application Messaging Protocol).  It is both a free-standing WAMP
router and also a library for embedding a WAMP router within projects
using the `Tornado <http://www.tornadoweb.org/>`_ asynchronous networking library and web framework.

The main wampnado module, especially the ApplicationServer class provides
a reference implementation.

WAMPnado provides means of having an API which interacts with WAMP-clients
(e.g. `Autobahn <http://autobahn.ws/>`_).

WAMP originally used `JSON <https://www.json.org/>`_ for serialization.
While this is easy, it makes for inefficient use of space with binary data.
Therefore, WAMP introducted an ability to negotiate other serialization formats,
most prominently `MessagePack <https://msgpack.org/index.html>`_.  This library
defaults to MessagePack when clients announce their support, but this default
can be changed in implementing libraries, and it can also be overriden on instantiation.

While the goal of this project is to implement a fairly complete set of WAMP router
functionality, there's a lot that doesn't exist yet, and there's a lot of boilerplate,
and there are even cases where it advertises features that it definitely does not have
(but hopefully will soon).

While the standard useage of WAMP is for a router to be just that, the mediator of
communications but not a participant, it is my intention to fully support both that
behavior, and also a sort of hybrid router/client mode where the router responds directly
to RPCs and pub/sub functions.  This could greatly cut down network traffic in some 
circumstances.

WAMPnado is based upon `Tornwamp <http://github.com/ef-ctx/tornwamp>`_.

This software is at a very early stage of development.  While it may be suitable for certain
tasks, the API may change at any time without warning.

How to install
==============

Using `pip <https://pip.pypa.io/>`_ (to be available soon):

This doesn't work yet.  Stay tuned.

.. code :: bash

    pip install wampnado

Or from the source-code:

.. code :: bash

    git clone https://github.com/rexlunae/wampnado.git
    cd wampnado
    python setup.py install

This library requires Python 3.  It may install under Python 2, but it will not work.  You
can ensure that it is installed under the correct version by specifically running python3.

This library can coexist on the same Tornado router as other things.  This means that you can
use it to develop WebSocket and RESTful HTTP applications listening on the same set of ports.



Running
=======

The default reference implementation of the router can be run as follows:

.. code :: bash

    wampnado

By default, it will be run on port 8080, bound only to localhost.  For a list of parameters, do
this:

.. code :: bash

    wampnado -h

There is also a debugging mode.  It can be run like this:

.. code :: bash

    wampnado -d

All parameters supported in the non-debug mode will work in debug mode.


Example of usage
================

An example of how to build a server using WAMPnado:

This basically hooks the read and write functions of the parent class in order
to display them.  If you don't want that, you can get the same effect with the
base WAMPHandler class.

.. code :: python
    """
    WAMPnado: Web Application Messaging Protocol for Tornado (Python)
    """
    from argparse import ArgumentParser
    from sys import exit, argv

    from tornado import web, ioloop

    from wampnado.handler import WAMPMetaHandler, WAMPMetaHandlerDebug
    from wampnado.transports import WebSocketTransport


    class ApplicationServer:
        
        def __init__(self, path, *listener_parameters, handler_class=WAMPMetaHandler):
            self.listener_parameters = listener_parameters
            self.path_maps = [(path, handler_class.factory(WebSocketTransport))]

        def run(self):
            self.app = web.Application(self.path_maps)
            for params in self.listener_parameters:
                self.app.listen(params.port, address=params.address)
            ioloop.IOLoop.instance().start()

    class ListenerParameters:
        def __init__(self, port=None, ssl_options=None, address='localhost'):
            if port is None:
                if ssl_options is None:
                    port = 80
                else:
                    port = 443

            self.port = port
            self.ssl_options = ssl_options
            self.address = address


    lp = ListenerParameters(
        port=8080
    )


    def parse_args():
        argparser = ArgumentParser()

        argparser.add_argument('-d', '--debug', help="Run in debug mode.  Display all messages to STDOUT", action='store_true', default=False)
        argparser.add_argument('-p', '--port', help="Port to listen on.", default=lp.port)
        argparser.add_argument('-a', '--address', help="Address to listen on.", default=lp.address)
        argparser.add_argument('-u', '--url', help="URL for the WebSocket.  This should only be the path part of the URL (e.g.: /ws)", default='/ws')

        args = argparser.parse_args()

        url = args.url
        del args.url
        debug = args.debug
        del args.debug

        return url, args, debug

    # Called during regular execution.
    def main():
        url, args, debug = parse_args()

        if debug:
            server = ApplicationServer(url, args, handler_class=WAMPMetaHandlerDebug)
        else:
            server = ApplicationServer(url, args)
        server.run()

    if __name__ == "__main__":
        main()


Which can be run:

.. code :: bash

    python3 wamp.py


From the client perspective, you'd be able to use Autobahn JavaScript library
to connect to the server using:

.. code :: javascript

  var connection = new autobahn.Connection({
    url: "ws://0.0.0.0:8888/ws",
    realm: "sample"
  });


License
=======

   Copyright 2015, Education First

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
