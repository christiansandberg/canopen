import struct


class Unsigned24:
    def __init__(self):
        self.__st = struct.Struct("<L")

    def unpack(self, __buffer):
        return self.__st.unpack(__buffer + b'\x00')

    def pack(self, *v):
        return self.__st.pack(*v)[:3]

    @property
    def size(self):
        return 3


class Integer24:
    def __init__(self):
        self.__st = struct.Struct("<l")

    def unpack(self, __buffer):
        mask = 0x80
        neg = (__buffer[2] & mask) > 0
        return self.__st.unpack(__buffer + (b'\xff' if neg else b'\x00'))

    def pack(self, *v):
        return self.__st.pack(*v)[:3]

    @property
    def size(self):
        return 3
