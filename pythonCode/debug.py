from mix.driver.ic.SC89620 import SC89620
from mix.driver.bus.soft_i2c import rtSoftI2CBus
import machine as m
from mix.driver.ic.cat9555 import CAT9555
from mix.driver.ic.om70201wv import OM70201WV

class XL9555GPIO(object):

    def __init__(self, gpio0, gpio1):
        self.mux0 = gpio0
        self.mux1 = gpio1

    def reset(self):
        self.mux0.set_pins_dir([0x00, 0x00])
        self.mux0.set_ports([0x00, 0x00])
        self.mux1.set_pins_dir([0x00, 0x00])
        self.mux1.set_ports([0x00, 0x00])
        return True

    def switch_charge(self, slot, enable=False):
        #1, 4, 7, 10
        assert 0 <= slot <= 3
        self.mux0.set_pin(slot*3+1, 1 if enable else 0)

    def switch_discharge(self, slot, enable=False):
        #2, 5, 8, 11
        assert 0 <= slot <= 3
        self.mux0.set_pin(slot*3+2, 1 if enable else 0)

    def switch_oqn(self, slot, enable=False):
        #3, 6, 9, 12
        assert 0 <= slot <= 3
        self.mux0.set_pin(slot*3, 1 if enable else 0)

    def led_ctl(self, slot, color, enable=False):
        assert 0 <= slot <= 3
        assert color in ['blue', 'green', 'red']
        _pinnum = self._get_slot_color(slot, color)
        if slot == 0:
            self.mux0.set_pin(_pinnum, 1 if enable else 0)
        elif slot == 1 and color == 'red':
            self.mux0.set_pin(_pinnum, 1 if enable else 0)
        else:
            self.mux1.set_pin(_pinnum, 1 if enable else 0)

    def _get_slot_color(self, slot, color):
        assert 0 <= slot <= 3
        assert color in ['blue', 'green', 'red']
        if color == 'red':
            return (12+ slot*3 + 0) % 16
        elif color == 'green':
            return (12+ slot*3 + 1) % 16
        elif color == 'blue':
            return (12+ slot*3 + 2) % 16

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

i2c_ch0 = rtSoftI2CBus(9, 8, 100000)
# print(i2c_ch0.scan())
i2c_ch1 = rtSoftI2CBus(7, 6, 100000)
# print(i2c_ch1.scan())
i2c_ch2 = rtSoftI2CBus(5, 4, 100000)
# print(i2c_ch2.scan())
i2c_ch3 = rtSoftI2CBus(3, 2, 100000)
# print(i2c_ch3.scan())
base_i2c = rtSoftI2CBus(15, 14, 100000)
# print(base_i2c.scan())
# int_ch0 = m.Pin(10, m.Pin.IN, m.Pin.PULL_UP)
# int_ch1 = m.Pin(11, m.Pin.IN, m.Pin.PULL_UP)
# int_ch2 = m.Pin(12, m.Pin.IN, m.Pin.PULL_UP)
# int_ch3 = m.Pin(13, m.Pin.IN, m.Pin.PULL_UP)

slot0 = SC89620(0x6B, i2c_ch0)
slot1 = SC89620(0x6B, i2c_ch1)
slot2 = SC89620(0x6B, i2c_ch2)
slot3 = SC89620(0x6B, i2c_ch3)
soc_3 = OM70201WV(0x38, i2c_ch3)



com_gpio0 = CAT9555(0x20, base_i2c)
com_gpio1 = CAT9555(0x21, base_i2c)
ctl = XL9555GPIO(com_gpio0, com_gpio1)
ctl.reset()
ctl.switch_charge(3, True) # turn charge  switch on


def write_read(client, reg, start_bit, value):
    """
    修改寄存器的特定位，其他位保持不变
    
    参数:
    client: I2C客户端对象
    reg: 寄存器地址
    start_bit: 要修改的位位置 (0-7)
    value: 要设置的值 (0或1)
    """
    # 读取当前寄存器值
    current_value = 0x00#client.read_register(reg)
    if value == 1:
        # 将指定位置1，其他位不变
        new_value = current_value | (1 << start_bit)
    else:
        # 将指定位置0，其他位不变
        new_value = current_value & ~(1 << start_bit)
    # 写回新值
    # client.write_register(reg, new_value)
    print(f"寄存器0x{reg:02X}: 0x{current_value:02X} -> 0x{new_value:02X} (bit{start_bit}={value})")
    return new_value

def write_read_multi_bits(client, reg, start_bit, bit_count, value):
    """
    修改寄存器的多个连续位，其他位保持不变
    
    参数:
    client: I2C客户端对象
    reg: 寄存器地址
    start_bit: 起始位位置 (0-7)
    bit_count: 位数量
    value: 要设置的值
    """
    # 读取当前寄存器值
    current_value = client.read_register(reg)
    
    # 创建掩码，清除目标位
    mask = ((1 << bit_count) - 1) << start_bit
    cleared_value = current_value & ~mask
    
    # 设置新值
    new_value = cleared_value | ((value & ((1 << bit_count) - 1)) << start_bit)
    
    # 写回新值
    client.write_register(reg, new_value)
    print(f"寄存器0x{reg:02X}: 0x{current_value:02X} -> 0x{new_value:02X} (bit{start_bit}~{start_bit+bit_count-1}={value})")

    r = client.read_register(reg)
    print(f"readback 寄存器0x{reg:02X}: 0x{r:02X}")



    
    return new_value


def init(client):
    r = client.read_register(0x38)
    print("PN_Information Register 0x38-->: {:02X}".format(r))
    write_read_multi_bits(client, 0x17, 7, 1, 1)
    client.write_register(0x90, 0x08)
    print("寄存器0x90: 0x08")
    client.write_register(0x91, 0x5D)
    print("寄存器0x91: 0x5D")
    client.write_register(0x92, 0x40)
    print("寄存器0x92: 0x40")
    write_read_multi_bits(client, 0x18, 5, 1, 0)
    write_read_multi_bits(client, 0x10, 5, 3, 0b101)
    write_read_multi_bits(client, 0x18, 4, 1, 0)
    # write_read_multi_bits_multi_bits(client, 0x02, 6, )
    write_read_multi_bits(client, 0x10, 0, 5, 0b00001)
    # write_read_multi_bits(client, 0x14, 6, )
    write_read_multi_bits(client, 0x12, 0, 4, 0b0001)
    write_read_multi_bits(client, 0x04, 0, 7, 70)

    write_read_multi_bits(client, 0x14, 4, 2, 0b00)
    write_read_multi_bits(client, 0x14, 0, 1, 0)
    write_read_multi_bits(client, 0x14, 3, 1, 0b1)
    write_read_multi_bits(client, 0x15, 4, 1, 0b0)
    write_read_multi_bits(client, 0x16, 0, 2, 0b00)
    write_read_multi_bits(client, 0x15, 2, 1, 0b1)
    write_read_multi_bits(client, 0x15, 1, 1, 0b0)
    write_read_multi_bits(client, 0x15, 0, 1, 0b0)
    write_read_multi_bits(client, 0x08, 5, 1, 0b0)
    write_read_multi_bits(client, 0x06, 6, 2, 0b01)
    write_read_multi_bits(client, 0x12, 5, 3, 0b011)
    write_read_multi_bits(client, 0x14, 1, 2, 0b00)
    write_read_multi_bits(client, 0x23, 2, 1, 1)
    write_read_multi_bits(client, 0x23, 3, 1, 1)

    write_read_multi_bits(client, 0x15, 6, 1, 0)
    write_read_multi_bits(client, 0x1A, 7, 1, 1)


    # print(hex(client.read_register(0x02)))
    # print(hex(client.read_register(0x04)))

def get_soc():
    soc_3.init_ic()
    r = soc_3.get_soc()
    soc_value = r[0] + (r[1]) / 256.0
    print("SOC: {:.2f}%".format(soc_value))


import time
def init2(client):
    client.write_register(0x02, 0x09)
    print(client.read_register(0x02))
    client.write_register(0x04, 0b01100100)
    print(client.read_register(0x04))
    client.write_register(0x06, 0b00001001)
    print(client.read_register(0x06))
    client.write_register(0x12, 0b01100001)
    print(client.read_register(0x12))















# init(slot3)
init2(slot3)

# print(hex(slot3.read_register(0x04)))