"""
Methods common to all TCP transports.
"""
from enum import Enum
from warnings import warn
from datetime import datetime

from wampnado.serializer import JSON_PROTOCOL, BINARY_PROTOCOL, NONE_PROTOCOL
from wampnado.messages import Message

class HandshakeError(Enum):
    NoError=0
    SerializerUnsupported=1
    MessageSizeRejected=2
    UnknownOption=3
    ConnectionCountLimit=4

class MessageType(Enum):
    Regular=0
    Ping=1
    Pong=2

class EncodedMessage(bytearray):

    def __init__(self, type, payload=b''):
        self.insert(0, type.value)

        length = len(payload)

        if length > 0xffffff:
            raise ValueError('Message length must be less than 0xffffff')

        self.insert(1, (length & 0xff0000) >> 16)
        self.insert(2, (length & 0xff00) >> 8) 
        self.insert(3, length & 0xff)
        self.extend(payload)

class TCPSocketPeer:
    """
    Contains the side-agnostic bits of the socket communication.
    """
    supported_protocols = {
        JSON_PROTOCOL: True,
        BINARY_PROTOCOL: True,
    }

    def __init__(self, stream):
        self.protocol = JSON_PROTOCOL
        self.stream = stream
        self.max_length = 0 # Until negotiated otherwise

    def pong(self):
        """
        Respond to a ping.
        """
        self.stream.write(b'\x02\0\0\0')

    def ping(self):
        """
        Send a ping.
        """
        self.stream.write(b'\x01\0\0\0')

    def write_message(self, msg, **kwargs):
        """
        Takes a WAMP message, puts the correct header around it, and sends it to the client iff it is within the negotiated max_length using the negotiated serializer.
        """
        if self.protocol == JSON_PROTOCOL:
            serialized_msg = msg.json.encode()
        elif self.protocol == BINARY_PROTOCOL:
            serialized_msg = msg.msgpack

        if len(serialized_msg) > self.max_length:
            warn('Message of length {} exceeded negotiated max length {}.'.format(len(serialized_msg), self.max_length))
            return False

        full_msg = EncodedMessage(MessageType.Regular, serialized_msg)

        self.stream.write(full_msg)

    async def read_message(self):
        msg_type = MessageType((await self.stream.read_bytes(1))[0])

        if msg_type == MessageType.Regular:
            length_bytes = await self.stream.read_bytes(3)
            length = (length_bytes[0] << 16) + (length_bytes[1] << 8) + length_bytes[2]

            data = await self.stream.read_bytes(length)
            if self.protocol == JSON_PROTOCOL:
                msg = Message.from_text(data)
            elif self.protocol == BINARY_PROTOCOL:
                msg = Message.from_bin(data)
            else:
                warn('unknown protocol ' + self.protocol)

            return msg
            
        elif msg_type == MessageType.Ping:
            self.pong()
        elif msg_type == MessageType.Pong:
            warn('{} got ping response'.format(datetime.now()))
        else:
            warn('got unknown message type {}' + msg_type.value)
