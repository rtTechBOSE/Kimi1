# -*- coding: utf-8 -*-
from cat9555 import CAT9555
from soft_i2c import SoftI2CBus


__author__ = 'Ming@rtTech'
__version__ = '0.1'

class ByteRegister(object):
    __slot__ = ['address', 'value']

    def __init__(self, address, value):
        self.address = address
        self.value = value

    def _bitwise_not(self, value, bit_length=8):
        # 取反并限制在 bit_length 位范围内
        return ~value & ((1 << bit_length) - 1)

    def _reverse_bits_bitwise(self, value, bit_length=8):
        reversed_value = 0
        for i in range(bit_length):
            # 将最低位移到目标位置
            reversed_value |= ((value >> i) & 1) << (bit_length - 1 - i)
        return reversed_value

    def get_bytes(self):
        res =  [self.value & 0xff, self.value >> 8]
        # res =  [self._reverse_bits_bitwise(self.value & 0xff, 8), self._reverse_bits_bitwise(self.value >> 8, 8)]
        print("[{:08b}, {:08b}]".format(res[0], res[1]))
        return res

    def get_bytes_4(self):
        res = [self.value & 0xff, self.value >> 8 & 0xff, self.value >> 16 & 0xff, self.value >> 24 & 0xff]
        print("[{:08b}, {:08b}, {:08b}, {:08b}]".format(res[0], res[1], res[2], res[3]))
        return res

class BitsRegister(object):
    __slot__ = ['masks', 'bit_offset', 'val_mask']
    masks = [
        0x0,
        0x1,
        0x3,
        0x7,
        0xf,
        0x1f,
        0x3f,
        0x7f,
        0xff,
        0x1ff,
        0x3ff,
        0x7ff,
        0xfff,
        0x1fff,
        0x3fff,
        0x7fff,
        0xffff,
        0x1ffff,
        0x3ffff,
        0x7ffff,
        0xfffff,
        0x1fffff,
        0x3fffff,
        0x7fffff,
        0xffffff,
        0x1ffffff,
        0x3ffffff,
        0x7ffffff,
        0xfffffff,
        0x1fffffff,
        0x3fffffff,
        0x7fffffff
    ]

    def __init__(self, bit_width, bit_offset):
        self.bit_offset = bit_offset
        self.bit_mask = self.masks[bit_width]
        self.val_mask = self.bit_mask << bit_offset

    def __set__(self, obj, v):
        origin = obj.value
        obj.value = (origin & ~self.val_mask) | ((v & self.bit_mask) << self.bit_offset)

    def __get__(self, obj, obj_type):
        return (obj.value & self.val_mask) >> self.bit_offset



class IOMUXRegisters(ByteRegister):
    LED0 = BitsRegister(3, 0)
    LED1 = BitsRegister(3, 3)
    LED2 = BitsRegister(3, 6)
    LED3 = BitsRegister(3, 9)
    # LED4 = BitsRegister(3, 12)
    # LED5 = BitsRegister(3, 15)
    # LED6 = BitsRegister(3, 18)
    # LED7 = BitsRegister(3, 21)
    # LED8 = BitsRegister(3, 24)
    # LED9 = BitsRegister(3, 27)

class LEDBoard:
    _led_state_value = {
            "r": 0b001,
            "g": 0b010,
            "b": 0b100,
            "off": 0b0
    }
    def __init__(self, i2c=SoftI2CBus(scl=22, sda=23)):
        self._i2c = i2c
        self._REG = IOMUXRegisters(0, 0)  # 初始化地址和值都为0
        # self._muxs = [CAT9555(0x20, i2c), CAT9555(0x21, i2c)]
        self._muxs = [CAT9555(0x20, i2c)]
        self.init()

    def init(self):
        self._REG.value = 0b0
        values = self._REG.get_bytes_4()
        self._muxs[0].set_ports(values[0:2])
        # self._muxs[1].set_ports(values[2::])
        # set output
        for mux in self._muxs:
            mux.set_pins_dir([0x00, 0x00])

    def write_register(self, data):
        self._muxs[0].set_ports(data[0:2])
        # self._muxs[1].set_ports(data[2::])
        return True

    def setState(self, slot, state):
        assert slot in range(10)
        assert state in ("r", "g", "b", 'off')
        setattr(self._REG, "LED{}".format(slot), LEDBoard._led_state_value[state])
        return self.write_register(self._REG.get_bytes_4())

    def setStates(self, states):
        """
        states = {0: "r", 1: "g", 2: "b", 3: "off", 4: "r", 5: "g", 6: "b", 7: "off", 8: "r", 9: "g"}
        """

        for slot, state in states.items():
            assert slot in range(10)
            assert state in ("r", "g", "b", 'off')
            setattr(self._REG, "LED{}".format(slot), LEDBoard._led_state_value[state])
        return self.write_register(self._REG.get_bytes_4())

    def reset(self):
        return self.write_register([0x00, 0x00, 0x00, 0x00])