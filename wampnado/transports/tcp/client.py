from warnings import warn

from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient

from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL
from wampnado.transports import Transport
from wampnado.transports.tcp import TCPSocketPeer, HandshakeError

class TCPSocketClientTransport(TCPSocketPeer):
    """
    A class representing a single connection to the transport.  It's generated on connection made with TCPClientConneciton.
    """
    async def handshake(self, serializer=BINARY_PROTOCOL):
        """
        Run the client handshake.  The handshake consists of a 4-byte (8-nibble) header:

        N0-N1: 0x7f - A magic number to idenitfy the beginning of the WAMP protocol
        N2: The maximum message length the client will accept.  Values are 2**(n+9)
        N3: Serializer selector.  0 - undefined, 1 - JSON, 2 - MessagePack, 3-15 Reserved
        N4-N7: Reserved, must be 0.

        The response is also 8 nibbles:
        N0-N1: 0x7f
        N2: 
        """

        if serializer == JSON_PROTOCOL:
            serializer_code = 1
        elif serializer == BINARY_PROTOCOL:
            serializer_code = 2

        await self.stream.write(b''.join([b'\x7f', bytes([0xf0 + serializer_code]), b'\0\0']))

        error = HandshakeError.NoError

        magic = await self.stream.read_bytes(1)
        if magic != b'\x7f':
            error = HandshakeError.UnknownOption

        selector = await self.stream.read_bytes(1)
        length_part = (selector[0] & 0xf0) >> 4

        # This shouldn't happen.
        serializer_echo_code = selector[0] & 0xf
        if serializer_echo_code == 0:
            error = HandshakeError(length_part)
        else:
            self.max_length = 2**(9 + length_part)

        if serializer_code == 1:
            self.protocol = JSON_PROTOCOL
        elif serializer_code == 2:
            self.protocol = BINARY_PROTOCOL
        else:
            error = HandshakeError.SerializerUnsupported

        if await self.stream.read_bytes(2) != b'\0\0':
            error = HandshakeError.UnknownOption

        if error == HandshakeError.NoError:
            return True
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
        else:
            warn('handshake failed.')




class TCPConnectorClient(TCPClient):
    """
    The class that makes the connection.  It will generate a TCPSocketClientTransport.
    """
    def __init__(self, port, host='localhost', transport_cls=TCPSocketClientTransport):
        self.port = port
        self.host = host
        self.transport_cls = transport_cls
        super().__init__()

    async def connect(self):
        stream = await super().connect(self.host, self.port)
        return self.transport_cls(stream)

