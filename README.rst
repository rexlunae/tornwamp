.. image:: https://travis-ci.org/ef-ctx/tornwamp.svg?branch=master
    :target: https://travis-ci.org/ef-ctx/tornwamp

.. image:: https://coveralls.io/repos/github/ef-ctx/tornwamp/badge.svg?branch=master
    :target: https://coveralls.io/github/ef-ctx/tornwamp?branch=master 

.. image:: https://img.shields.io/pypi/v/tornwamp.svg
    :target: https://pypi.python.org/pypi/tornwamp/

.. image:: https://img.shields.io/pypi/pyversions/tornwamp.svg
    :target: https://pypi.python.org/pypi/tornwamp/

.. image:: https://img.shields.io/pypi/dm/tornwamp.svg
    :target: https://pypi.python.org/pypi/tornwamp/

TornWAMP
========

This Python module implements parts of `WAMP <https://wamp-proto.org/>`_
(Web Application Messaging Protocol).

TornWAMP provides means of having an API which interacts with WAMP-clients
(e.g. `Autobahn <http://autobahn.ws/>`_).

TornWAMP is a library for writing WAMP routers (both dealers and brokers)
based on the Tornado `Tornado <http://www.tornadoweb.org/>`_ (Web framework).

WAMP was originally designed to use WebSockets as a transport.  While the WAMP
standard provies for other transports, this implementation is currently limited
to WebSockets.  This may change in the future.

WAMP originally used `JSON <https://www.json.org/>`_ for serialization.
While this is easy, it makes for inefficient use of space with binary data.
Therefore, WAMP introducted an ability to negotiate other serialization formats,
most prominently `MessagePack <https://msgpack.org/index.html>`_.  This library
defaults to MessagePack, but this default can be changed in implementing libraries,
and it can also be overriden on instantiation.

While the goal of this project is to implement a fairly complete set of WAMP router
functionality, there's a lot that doesn't exist yet, and there's a lot of boilerplate,
and there are even cases where it advertises features that it definitely does not have
(but hopefully will soon).

While the standard useage of WAMP is for a router to be just that, the mediator of
communications but not a participant, it is my intention to fully support both that
behavior, and also a sort of hybrid router/client mode where the router responds directly
to RPCs and pub/sub functions.  This could greatly cut down network traffic in some
circumstances.

How to install
==============

Using `pip <https://pip.pypa.io/>`_ (to be available soon):

::

    pip install tornwamp

Or from the source-code:

::

    #git clone https://github.com/ef-ctx/tornwamp.git
    git clone https://github.com/rexlunae/tornwamp.git
    cd tornwamp
    python setup.py install



Example of usage
================

An example of how to build a server using TornWAMP (`wamp.py`):

This basically hooks the read and write functions of the parent class in order
to display them.  If you don't want that, you can get the same effect with the
base WAMPHandler class.

::

    from tornado import web, ioloop
    from tornwamp.handler import WAMPHandler
    from tornwamp.messages import Message
    from sys import argv

    class Router:
    
        class Handler(WAMPHandler):
            
            # Hook all our output in pre-encoded form.  Good for debugging without manually interpretting binary.
            def write_message(self, msg):
                result = super().write_message(msg)
                print('tx|' + str(self.realm_id) + '|: ' + msg.json)
                return result

            # Hook all our input in decoded form.  Good for debugging without manually parsing binaries.
            def read_message(self, txt):
                message = super().read_message(txt)
                print('rx|' + str(self.realm_id) + '|: ' + message.json)
                return message
            def __init__(self, *args, default_host=None, port=1234, path=r'/ws', **kwargs):
                super().__init__(*args, **kwargs)
                self.realm_id = 'unset'

    
        def __init__(self, *args, default_host=None, port=8888, path=r'/ws', **kwargs):
            super().__init__(*args, **kwargs)
            self.default_host = default_host
            self.port = port
            self.path = path
            self.app = web.Application([(path, self.Handler)], *args, default_host=default_host, **kwargs)

        def run(self):
            self.app.listen(self.port)
            ioloop.IOLoop.instance().start()

    router = Router()
    router.run()


Which can be run:

::

    python wamp.py


From the client perspective, you'd be able to use Autobahn JavaScript library
to connect to the server using:

::

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
