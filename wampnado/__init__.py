"""
WAMPnado: Web Application Messaging Protocol for Tornado (Python)
"""
from argparse import ArgumentParser
from sys import exit, argv

from tornado import web, ioloop

from wampnado.agent.server import WAMPMetaServerHandler, WAMPMetaServerHandlerDebug
from wampnado.agent.client import WAMPMetaClientHandler, WAMPMetaClientHandlerDebug

from wampnado.transports import WebSocketTransport


class ApplicationServer:
    
    def __init__(self, path, *listener_parameters, handler_class=WAMPMetaServerHandler):
        self.listener_parameters = listener_parameters
        self.path_maps = [(path, handler_class.factory(WebSocketTransport))]

    def run(self):
        self.app = web.Application(self.path_maps)
        for params in self.listener_parameters:
            self.app.listen(params.port, address=params.address)
        ioloop.IOLoop.instance().start()



class ListenerParameters:
    def __init__(self, port=None, ssl_options=None, address='localhost', url='/ws'):
        if port is None:
            if ssl_options is None:
                port = 80
            else:
                port = 443

        self.port = port
        self.ssl_options = ssl_options
        self.address = address
        self.url=url


def parse_args(*add_args, default_params=ListenerParameters()):
    argparser = ArgumentParser()

    argparser.add_argument('-d', '--debug', help="Run in debug mode.  Display all messages to STDOUT", action='store_true', default=False)
    argparser.add_argument('-p', '--port', help="Port number.", default=default_params.port)
    argparser.add_argument('-a', '--address', help="IP address on.", default=default_params.address)
    argparser.add_argument('-u', '--url', help="URL for the WebSocket.  This should only be the path part of the URL (e.g.: /ws)", default=default_params.url)

    for arg_list in add_args:
        argparser.add_argument(*(arg_list['args']), **(arg_list['kwargs']))

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
        server = ApplicationServer(url, args, handler_class=WAMPMetaServerHandlerDebug)
    else:
        server = ApplicationServer(url, args)
    server.run()

if __name__ == "__main__":
    main()
