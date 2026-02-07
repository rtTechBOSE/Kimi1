# -*- coding: utf-8 -*-
import sys
from machine import SoftI2C, Pin


__author__ = 'Clark@Prm'
__version__ = '0.1'

class MPYI2CBusException(Exception):
    def __init__(self,dev_name,err_str):
        self._err_resason = '[%s]: %s.' % (dev_name, err_str)

    def __str__(self):
        return self._err_resason

class SoftI2CBus(object):
    '''
    MPYSoftI2CBus(SW) function class which provide function to control
    i2c slave device, most of normal I/O can support this class

    :param scl: str, the pin name of pyboard("PB8")
    :param sda: str, the pin name of pyboard("PB9")
    :param freq: int(100000~400000), i2c baud rate default is 100k

    .. code-block:: python

        address = 0x20
        i2c = MPYSoftI2CBus(scl="PB8", sda="PB9", freq=100000)

        # read data from i2c device
        buf = i2c.read(address, [0x00], 1)
        print("register date: {}".format(buf[0]))
        buf = i2c.recv(address, 2)
        print("the 16 byte date is {}".format(buf[0]<<8|buf[1]))

        # write data to i2c device
        i2c.write(address, [0x00])
        i2c.write(address, [0x00, 0x01])
        i2c.send(address, [0x00, 0x25])

        # scan i2c address from i2c bus and check i2c device is ready
        address_list = i2c.scan()
        bool = i2c.is_ready(address)
        print("there are {} slave device on current i2c bus".format(address_list))
        print("current i2c device is ready?{}".format(bool))
    '''
    rpc_public_api = [
        "read", "write", "send", "write_and_read", "scan", "is_ready"
    ]

    def __init__(self, scl, sda, freq=100000):

        self._scl = scl
        self._sda = sda
        self._freq = freq
        self._ps_i2c = None
        self.open()

    def __del__(self):
        self.close()

    def open(self):
        '''
        Instance a new I2C class

        :return: None
        '''
        self._ps_i2c = SoftI2C(scl=Pin(self._scl), sda=Pin(self._sda), freq=self._freq)
        if not self._ps_i2c:
            raise OSError("Open device fail SCL: {} SDA: {}".format(self._scl, self._sda))

    def close(self):
        '''
        Deinit i2c device

        :return: None
        '''
        # machine I2C have not deinit api
        # self._ps_i2c.deinit()
        del self._ps_i2c
        self._ps_i2c = None

    def read(self, addr, rd_data, length, addrsize=8):
        '''
        Read value from i2c slave

        :param addr: int(0x00~0xff), i2c slave address
        :param rd_data: list, register address
        :param length: int, length of data you want to read
        :return: list
        '''
        assert 0 <= addr <= 0xFF
        assert length > 0
        buffer = self._ps_i2c.readfrom_mem(addr, rd_data, length, addrsize=addrsize)
        return list(buffer)

    def write(self, addr, data, addrsize=8):
        '''
        Write data to i2c slave device

        :param addr: int(0x00~0xff), i2c slave address
        :param data: list, if specify reg then the first is reg address
        :return: None
        '''
        assert 0 <= addr <= 0xFF
        assert len(data) > 0
        if len(data) > 1:
            if addrsize == 8:
                wr_data = bytearray(data[1::])
                mem_addr = data[0]
            else:
                wr_data = bytearray(data[2::])
                mem_addr = data[0] << 8 | data[1]
            self._ps_i2c.writeto_mem(addr, mem_addr, wr_data, addrsize=addrsize)
        else:
            self._ps_i2c.writeto(addr, bytearray(data))

    def recv(self, addr, length):
        '''
        Read value from i2c slave
        :param addr: int(0x00~0xff), i2c slave address
        :param length: int, length of data you want to read
        :return: list
        '''
        assert 0 <= addr <= 0xFF
        assert length > 0
        buffer = self._ps_i2c.readfrom(addr, length)
        return list(buffer)

    def send(self, addr, data):
        '''
        Send data to i2c slave device

        :param addr: int(0x00~0xff), i2c slave address
        :param data: list, if specify reg then the first is reg address
        :return: None
        '''
        assert 0 <= addr <= 0xFF
        assert isinstance(data, list)
        self._ps_i2c.writeto(addr, bytearray(data))

    def write_and_read(self, addr, wr_data, length, addrsize=8):
        '''
        Write data to register and then read data from it

        :param addr:  int(0x00~0xff), i2c slave address
        :param wr_data: list, if specify reg then the first is reg address
        :param length: int, length of data you want to read
        :return: list
        '''
        assert 0 <= addr <= 0xFF
        assert len(wr_data) > 0
        assert length > 0
        if addrsize==8:
            mem_addr = wr_data[0]
            data = bytearray(wr_data[1::])
        else:
            mem_addr = wr_data[0] <<8 |wr_data[1]
            data = bytearray(wr_data[2::])
        if data:
            self._ps_i2c.writeto_mem(addr, mem_addr, data, addrsize=addrsize)
        return self.read(addr, mem_addr, length, addrsize)

    def scan(self):
        '''
        Scan the slave address of i2c bus

        :return: list, all the device address are in it
        '''
        return self._ps_i2c.scan()

    def is_ready(self, addr):
        '''
        Check if addr is ready to control

        :return: bool, is ready if True else not ready
        '''

        addr_list = self.scan()
        return True if addr in addr_list else False

