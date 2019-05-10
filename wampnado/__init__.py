"""
WAMPnado: Web Application Messaging Protocol for Tornado (Python)
"""
from argparse import ArgumentParser
from sys import exit, argv

from tornado import web, ioloop

from wampnado.handler import WAMPMetaHandler, WAMPMetaHandlerDebug
from wampnado.transports import WebSocketTransport

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


class ApplicationServer:
    
    def __init__(self, path, *listener_parameters, handler_class=WAMPMetaHandler):
        self.listener_parameters = listener_parameters
        self.path_maps = [(path, handler_class.factory(WebSocketTransport))]

    def run(self):
        self.app = web.Application(self.path_maps)
        for params in self.listener_parameters:
            self.app.listen(params.port, address=params.address)
        ioloop.IOLoop.instance().start()

lp = ListenerParameters(
    port=8080
)


def parse_args():
    argparser = ArgumentParser()

    argparser.add_argument('-p', '--port', help="Port to listen on.", default=lp.port)
    argparser.add_argument('-a', '--address', help="Address to listen on.", default=lp.address)
    argparser.add_argument('-u', '--url', help="URL for the WebSocket", default='/ws')

    args = argparser.parse_args()

    url = args.url
    del args.url
    return url, args




# Called during testing.
def debug():
    url, args = parse_args()
    api = ApplicationServer(url, args, handler_class=WAMPMetaHandlerDebug)
    api.run()

# Called during regular execution.
def main():
    url, args = parse_args()

    api = ApplicationServer(url, args)
    api.run()

if __name__ == "__main__":
    main()
