import struct

class UnsignedN:
    """ struct-like class for packing and unpacking unsigned integers of arbitrary width.
    The width must be a multiple of 8 and must be between 8 and 64.
    """
    def __init__(self, width: int):
        self.width = width
        if width % 8 != 0:
            raise ValueError("Width must be a multiple of 8")
        if width <= 0 or width > 64:
            raise ValueError("Invalid width for UnsignedN")
        elif width <= 8:
            self.__st = struct.Struct("B")
        elif width <= 16:
            self.__st = struct.Struct("<H")
        elif width <= 32:
            self.__st = struct.Struct("<L")
        elif width <= 64:
            self.__st = struct.Struct("<Q")

    def unpack(self, __buffer):
        return self.__st.unpack(__buffer + b'\x00' * (self.__st.size - self.size))

    def pack(self, *v):
        return self.__st.pack(*v)[:self.size]

    @property
    def size(self):
        return self.width // 8


class IntegerN:
    """ struct-like class for packing and unpacking integers of arbitrary width.
    The width must be a multiple of 8 and must be between 8 and 64.
    """
    def __init__(self, width: int):
        self.width = width
        if width % 8 != 0:
            raise ValueError("Width must be a multiple of 8")
        if width <= 0 or width > 64:
            raise ValueError("Invalid width for IntegerN")
        elif width <= 8:
            self.__st = struct.Struct("b")
        elif width <= 16:
            self.__st = struct.Struct("<h")
        elif width <= 32:
            self.__st = struct.Struct("<l")
        elif width <= 64:
            self.__st = struct.Struct("<q")

    def unpack(self, __buffer):
        mask = 0x80
        neg = (__buffer[self.size - 1] & mask) > 0
        return self.__st.unpack(__buffer + (b'\xff' if neg else b'\x00') * (self.__st.size - self.size))

    def pack(self, *v):
        return self.__st.pack(*v)[:self.size]

    @property
    def size(self):
        return self.width // 8
