from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError

from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL

from wampnado.transports import Transport
from wampnado.transports.tcp import TCPSocketPeer, HandshakeError

class TCPSocketServerTransport(TCPSocketPeer, Transport):
    """
    A class representing a single connection to the transport.
    """

    def __init__(self, stream):
        super(TCPSocketPeer, self).__init__(stream)
        super(Transport, self).__init__()

    async def handshake(self):
        """
        Run the server handshake.  The handshake consists of a 4-byte (8-nibble) header:

        The client writes first upon connect (4 bytes), and then the server writes back a response (4 bytes)

        N0-N1: 0x7f - A magic number to idenitfy the beginning of the WAMP protocol
        N2: The maximum message length the client will accept.  Values are 2**(n+9)
        N3: Serializer selector.  0 - undefined, 1 - JSON, 2 - MessagePack, 3-15 Reserved
        N4-N7: Reserved, must be 0.

        The response is also 8 nibbles:
        N0-N1: 0x7f
        N2: 
        """

        error = HandshakeError.NoError
        magic = await self.stream.read_bytes(1)
        if magic != b'\x7f':
            error = HandshakeError.UnknownOption

        selector = await self.stream.read_bytes(1)
        self.max_length = 2**(9 + ((selector[0] & 0xf0) >> 4))

        serializer_code = selector[0] & 0xf

        if serializer_code == 1:
            self.protocol = JSON_PROTOCOL
        elif serializer_code == 2:
            self.protocol = BINARY_PROTOCOL
        else:
            error = HandshakeError.SerializerUnsupported

        if await self.stream.read_bytes(2) != b'\0\0':
            error = HandshakeError.UnknownOption

        if error == HandshakeError.NoError:
            await self.stream.write(b''.join([b'\x7f', bytes([0xf0 + serializer_code]), b'\0\0']))
            return True
        else:
            await self.stream.write(b''.join([b'\x7f', bytes([error.value << 4]), b'\0\0']))
            return False

    async def run(self):
        success = await self.handshake()
        if success:
            while True:
                try:
                    msg = await self.read_message()
                    await self.handle_message(msg)

                except StreamClosedError:
                    break


class TCPSocketListener(TCPServer):
    """
    The transport for WAMP over a regular TCP socket.

    Note that although it works as a transport from the perspective of things calling it from the outside, within WAMP the TCPSocketServer class is the true transport.
    """
    def __init__(self, sc):
        """
        Pass the class for the handler that you want to use.
        """
        self.SpawnClass = sc
        super().__init__()


    async def handle_stream(self, stream, address):
        SC = self.SpawnClass
        class StreamHandler(TCPSocketServerTransport, SC):
            def __init__(self, stream):
                super(SC, self).__init__()
                super(TCPSocketServerTransport, self).__init__(stream)

        server = StreamHandler(stream)
        await server.run()
