import re
import time
from machine import Pin, UART, PWM
from led_board import LEDBoard
import json
from machine import Timer, WDT


class UARTManager:

    def __init__(self):
        self.uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
        self.buffer = bytearray()
        self._running = True
        
    def process(self):
        if self.uart.any() > 0:
            time.sleep_ms(20)
            data = self.uart.read()
            for byte in data:
                self.buffer.append(byte)
                if byte == 0x0A:  # 检测换行符
                    cmd = bytes(self.buffer).strip()
                    self._execute_cmd(cmd)
                    self.buffer = bytearray()

    def stop(self):
        self._running = False
        if self.uart:
            self.uart = None
                
    def _execute_cmd(self, command):
        command = command.decode().lower()  # 将字节类型转换为字符串并转换为小写
        cmd_list = command.split(" ")
        func_name = cmd_list.pop(0)
        args = list()
        if len(cmd_list) > 0:
            for i in cmd_list:
                args.append(self._parse_value(i))
        func = getattr(self, func_name, None)
        if callable(func):
            if len(args) > 0:
                try:
                    if func(*args):
                        self.uart.write(b"{} [OK]\n".format(func_name))
                    else:
                        self.uart.write(b"{} [ERR]\n".format(func_name))
                except Exception as e:
                    self.uart.write(b"[ERR] " + str(e).encode() + b"\n")
            else:
                try:
                    if func():
                        self.uart.write(b"{} [OK]\n".format(func_name))
                    else:
                        self.uart.write(b"{} [ERR]\n".format(func_name))
                except Exception as e:
                    self.uart.write(b"[ERR] " + str(e).encode() + b"\n")
        else:
            #not found function
            self.uart.write(b"not found function [ERR]\n")

    def _parse_value(self, value):

        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value


class OutputDev:
    def __init__(self, pin, asserted=1):
        self.pin = Pin(pin, Pin.OUT, Pin.PULL_DOWN)
        self.asserted = asserted
        self.dev = []

    def on(self):
        self.pin.value(self.asserted)

    def off(self):
        self.pin.value(0 if self.asserted else 1)

    def stop(self):
        self.pin.value(0)

    def bind(self, dev):
        self.dev.append(dev)

    def unbind(self):
        self.dev.clear()


class LED(OutputDev):
    def __init__(self, pin, asserted=0):
        super().__init__(pin, asserted)


class Cylinder:

    def __init__(self):
        self.dev = []

    def bind(self, dev):
        self.dev.append(dev)

    def unbind(self):
        self.dev = []

    def on(self):
        [dev.on() for dev in self.dev]

    def off(self): 
        [dev.off() for dev in self.dev]

    def stop(self):
        [dev.stop() for dev in self.dev]


class InputDev:
    mode = {
        "IRQ_FALLING": Pin.IRQ_FALLING,
        "IRQ_RISING": Pin.IRQ_RISING,
        "IRQ_RISING_FALLING": Pin.IRQ_FALLING | Pin.IRQ_RISING
    }

    def __init__(self, pin, pull_up=True):
        self.pin = Pin(pin, Pin.IN, Pin.PULL_UP if pull_up else Pin.PULL_DOWN)
        if pull_up:
            self.last_state = 1
        else:
            self.last_state = 0
        # self.last_state = self.pin.value()
        self.dev = []

    def read(self):
        if self.pin.value() != self.last_state:
            return True
        return False

    def bind(self, dev, mode):
        self.dev.append(dev)
        self.pin.irq(handler=self.callback, trigger=InputDev.mode[mode])
        
    def unbind(self):
        self.dev = []
        self.pin.irq(None)

    def callback(self, _pin):
        current_state = _pin.value()
        if current_state == 0:  # 按钮被按下
            [dev.on() for dev in self.dev]
        else:  # 按钮被释放
            [dev.off() for dev in self.dev]
        self.last_state = current_state

class Button(InputDev):
    def __init__(self, pin, pull_up=True, long_press=1500):
        super().__init__(pin, pull_up)
        self.long_press = long_press
        self.last_time = None
        self.state = 0

    def read_status(self):
        current_state = self.pin.value()
        current_time = time.ticks_ms()
        # 对于上拉按钮，0表示按下，1表示释放
        if current_state == 0:  # 按钮被按下
            if self.last_time is None:  # 首次按下时记录时间
                self.last_time = current_time
            if time.ticks_diff(current_time, self.last_time) >= self.long_press:
                self.state = 2  # 长按
            else:
                self.state = 1  # 短按
        else:
            self.last_time = None
            self.state = 0
        return self.state


class Sensor(InputDev):
    def __init__(self, pin, pull_up=True):
        super().__init__(pin, pull_up)


class ControlBoardManager(UARTManager):
    def __init__(self, config_file):
        super().__init__()
        self.devices = {}
        self.devices['ledboard'] = LEDBoard()
        self.fixture_config = {}
        self.load_config(config_file)
        self.load_fixture_config()
        self.timer = Timer()
        self.duty = 32768
        self.step = 400
        self.pwm = PWM(Pin(29, Pin.OUT), freq=1000, duty_u16=32768)
        self.timer.init(period=10, mode=Timer.PERIODIC, callback=self.breath)
        self.flag = False
        # self.wdt = WDT(timeout=8388)

    def breath(self, t):
        self.pwm.duty_u16(self.duty)
        self.duty += self.step
        if self.duty >= 65535 or self.duty <= 0:
            self.step = -self.step
        # self.devices['ledboard'] = LEDBoard()

    def bind_device(self, source_name, target_name, mode):
        """绑定设备
        Args:
            source_name: 源设备名称
            target_name: 目标设备名称
            mode: 触发模式
        """
        source_dev = self.get_device(source_name)
        target_dev = self.get_device(target_name)
        source_dev.bind(target_dev, mode)

    def create_device(self, name, config):
        # 获取设备类型
        device_class = globals().get(config['class'])
        if not device_class:
            raise ValueError(f"Unknown device class: {config['class']}")
            
        # 创建设备实例
        params = {k: v for k, v in config.items() if k != 'class'}
        device = device_class(**params)
        self.devices[name] = device
        return device

    def load_config(self, config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        # 创建设备
        for name, device_config in config['device'].items():
            self.create_device(name, device_config)
            
        # 处理绑定关系
        for action in config['bindings']:
            try:
                # 解析绑定语句
                source, target, mode = self._parse_bind_action(action)
                if source not in self.devices:
                    print(f"Error: source device '{source}' not found")
                    continue
                if target not in self.devices:
                    print(f"Error: target device '{target}' not found")
                    continue
                source_dev = self.devices[source]
                target_dev = self.devices[target]
                if mode:
                    source_dev.bind(target_dev, mode)
                else:
                    source_dev.bind(target_dev)
            except Exception as e:
                print(f"Error processing action: {action}, Error: {str(e)}")
                continue  # 继续处理下一个绑定，而不是中断整个过程
                
    def _parse_bind_action(self, action):
        # 从字典中直接获取绑定信息
        source = action['source']
        target = action['target']
        # 根据设备类型设置默认的mode
        mode = action.get('mode', None)
        return source, target, mode

    def get_device(self, name):
        device = self.devices.get(name)
        if device is None:
            raise ValueError(f"Device '{name}' not found")
        return device

    def load_fixture_config(self, config_file="fixture_config.json"):
        """加载夹具配置参数
        Args:
            config_file: 配置文件路径
        """
        try:
            with open(config_file, 'r') as f:
                self.fixture_config = json.load(f)
        except Exception as e:
            print(f"Error loading fixture config: {str(e)}")
            self.fixture_config = {}

    def save_fixture_config(self, config_file="fixture_config.json"):
        """保存夹具配置参数
        Args:
            config_file: 配置文件路径
        """
        try:
            self.fixture_config["last_modified"] = time.strftime("%Y-%m-%d")
            with open(config_file, 'w') as f:
                f.write(json.dumps(self.fixture_config))
        except Exception as e:
            print(f"Error saving fixture config: {str(e)}")

    def scan(self):
        reset_button = self.devices.get("reset_button").read_status()
        start_button = self.devices.get("start_button").read_status()
        if reset_button == 2 and not self.flag:
            self.fixture_reset()
            self.flag = True
        elif start_button==2 and reset_button==0 and not self.flag:
            self.fixture_run()
            self.flag = True
        else:
            self.flag = False

    def run(self):

        while self._running:
            self.scan()
            self.process()
            time.sleep_ms(10)
            # self.wdt.feed()

    def fixture_in1(self):
        """
        in_out_cylder
        up_down_cylder
        """     
        key_name_list = ["up_sensor", "down_sensor"]
        if [self.devices[dev].read() for dev in key_name_list] == [True, False]:
            _cylder = self.devices.get("in_out_cylder", None)
            if _cylder is None:
                raise ValueError("Device in_out_cylder not found")
            _cylder.off()
            start_time = time.ticks_ms()
            while (True):
                if not self.devices["scan_sensor"].read():
                    _cylder.stop()
                    return True
                if time.ticks_diff(time.ticks_ms(), start_time) > 3000:
                    return False
            # return self._waite_ready(True, False, True, False, 5000)
        else:
            return False

    def fixture_in(self):
        """
        in_out_cylder
        up_down_cylder
        """
        return self._fix_ctl("in_out_cylder", True, False, True, False, True)




    def fixture_out(self):
        """
        in_out_cylder
        up_down_cylder
        """
        key_name_list = ["up_sensor", "down_sensor"]
        if [self.devices[dev].read() for dev in key_name_list] == [True, False]:
        # return self._fix_ctl("in_out_cylder", "in_sensor", "out_sensor", False, True, True)
            return self._fix_ctl("in_out_cylder", False, True, True, False, False)
        else:
            return False

    def fixture_up(self):
        """
        in_out_cylder
        up_down_cylder
        """
        key_name_list = ["in_sensor", "out_sensor"]
        if [self.devices[dev].read() for dev in key_name_list] == [True, False]:
            return self._fix_ctl("up_down_cylder", True, False, True, False, True)
        else:
            return False


    def fixture_down(self):
        """
        in_out_cylder
        up_down_cylder
        """
        key_name_list = ["in_sensor", "out_sensor"]
        if [self.devices[dev].read() for dev in key_name_list] == [True, False]:
            return self._fix_ctl("up_down_cylder", True, False, False, True, False)
        else:
            return False


    def fixture_reset(self):
        """
        up_sensor  True
        down_sensor False
        """
        # self.ctl_out(0)
        self.fixture_uninsert(1)
        time.sleep_ms(500)
        self._fix_ctl("up_down_cylder", True, False, True, False, True)
        return self._fix_ctl("in_out_cylder", False, True, True, False, False)
        
    def fixture_run(self):
        self.fixture_in()
        self.fixture_down()
        time.sleep_ms(500)
        return self.fixture_uninsert(0)
        # return self.ctl_out(1)
    
    def fixture_uninsert(self, value):
        # r = self._ctl_out(1)
        name_list = ["ctl_out1", "ctl_out2"]
        if value:
            [self.devices[name].off() for name in name_list]
        else:
            [self.devices[name].on() for name in name_list]
        return True
    
    def loop_test(self, num):
        for i in range(num):
            self.fixture_run()
            time.sleep_ms(1000)
            self.fixture_reset()
            time.sleep_ms(1000)
        return True

    def loop_test1(self, num):
        for i in range(num):
            self.fixture_in()
            if not self.fixture_uninsert():
                return False
            time.sleep_ms(1000)
            self.fixture_out()
            time.sleep_ms(1000)
        return True

    def led_state_value(self, slot, value):
        return self.devices["ledboard"].setState(slot, value)
    
    def led_off(self):
        return self.devices["ledboard"].reset()

    def oqc_test(self, _value=1):
        input_pin = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
        output_pin = [2, 3, 4, 5, 6, 7, 8, 9]
        _input_list = []
        for i in input_pin:
            _input_list.append(Pin(i, Pin.IN))
        _output_list = []
        for i,v in enumerate(output_pin):
            _output_list.append(Pin(v, Pin.OUT, Pin.PULL_DOWN))
            _output_list[i].value(_value)
        str_return = ""
        for index, _pin in enumerate(_input_list):
            str_return += "pin_{}: {}\n".format(input_pin[index], _pin.value())
        self.uart.write(str_return)
        return True

    def oqc_get_status(self, pin_num):
        input_pin = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
        output_pin = [2, 3, 4, 5, 6, 7, 8, 9]
        str_return = ""
        if pin_num in input_pin:
            _value = Pin(pin_num, Pin.IN).value()
        elif pin_num in output_pin:
            _value = Pin(pin_num, Pin.OUT, Pin.PULL_DOWN).value()
        else:
            str_return = "pin_num error"
        self.uart.write(str_return)
        return True

    def oqc_set_pin(self, pin_num, value):
        output_pin = [2, 3, 4, 5, 6, 7, 8, 9]
        assert pin_num in output_pin
        assert value in [0, 1]
        Pin(pin_num, Pin.OUT, Pin.PULL_DOWN).value(value)
        return True

    def get_pin_status(self, name):
        dev = self.devices.get(name)
        try:
            if dev:
                self.uart.write("Pin_num{}: {}\n".format(name, dev.pin.value()))
            else:
                self.uart.write("{} Error\n".format(name))
        except Exception as e:
            self.uart.write("{} Have No read\n".format(name))
        return True

    def set_pin_status(self, name, value):
        dev = self.devices.get(name)
        try:
            if dev:
                dev.pin.value(value)
            else:
                self.uart.write("{} Error\n".format(name))
        except Exception as e:
            self.uart.write("{} Have No read\n".format(name))
        return True

    def get_all_status(self):
        key_name_list = ['solenoid_down', 'solenoid_up', 'solenoid_in', 'solenoid_out', 'reset_led', 'start_led', 'start_button', 'reset_button', 'flatness_sensor', 'presence_sensor', 'up_sensor', 'down_sensor', 'in_sensor', 'out_sensor','ctl_out1', 'ctl_out2', 'typec_sensor1', 'typec_sensor2']
        for k in key_name_list:
            dev = self.devices.get(k)
            if dev:
                self.uart.write("{}: {} \n".format(k, dev.pin.value()))
            else:
                self.uart.write("{}: {} \n".format(k, "None"))
        return True
            

    def _get_status(self):
        info = dict()
        for k, v in self.devices.items():
            if isinstance(v, InputDev):
                info[k] = v.read()
        self.uart.write(json.dumps(info))

    def _fixture_para_get(self, key):
        r = self.fixture_config.get(key)
        self.uart.write(json.dumps(r))

    def _fixture_para_set(self, key, value):
        self.fixture_config[key] = value
        self.save_fixture_config()
        self.uart.write("Save   OK")

    def _fix_ctl(self, cylder_name, s1, s2, s3, s4, reverse=False, timeout=5000):
        _cylder = self.devices.get(cylder_name, None)
        if _cylder is None:
            raise ValueError(f"Device '{cylder_name}' not found")
        if not reverse:
            _cylder.on()
        else:
            _cylder.off()
        return self._waite_ready(s1, s2, s3, s4, timeout)

    def _waite_ready(self, s1, s2, s3, s4, timeout=5000):
        """
        up_sensor  True
        down_sensor False
        """
        key_name_list = ["in_sensor", "out_sensor", "up_sensor", "down_sensor"]
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout:
            if [self.devices.get(k).read() for k in key_name_list] == [s1, s2, s3, s4]:
            # k1_sensor = self.devices.get(k1).read()
            # k2_sensor = self.devices.get(k2).read()
            # k3_sensor = self.devices.get(k3).read()
            # k4_sensor = self.devices.get(k4).read()
            # if (k1_sensor, k2_sensor, k3_sensor, k4_sensor) 
                return True
            time.sleep_ms(10)
        return False

    def _ctl_out(self, value):
        name_list = ["ctl_out1", "ctl_out2"]
        sensor_list = ['typec_sensor1', 'typec_sensor2']
        try:
            if value:
                [self.devices[name].on() for name in name_list]
            else:
                [self.devices[name].off() for name in name_list]
            start_time = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start_time) < 2000:
                if value:
                    if [self.devices[name].read() for name in sensor_list] == [True, True]:
                        return True
                else:
                    if [self.devices[name].read() for name in sensor_list] == [False, False]:
                        return True
                time.sleep_ms(10)
            return False
        except Exception as e:
            return False
        


kimi = ControlBoardManager("hw_profile.json")
kimi.run()

# if __name__ == '__main__':
#     kimi = ControlBoardManager("hw_profile.json")
#     kimi.run()
