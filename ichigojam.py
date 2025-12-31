import machine
import rp2
import utime
import sys
import random
import network
import usocket as socket
import ussl as ssl
import _thread
import os
import gc
from typing import Optional, Union, Any, List, Tuple, Callable

# --- PIO Resource Manager ---

class PIOManager:
    """PIO state machine and instruction memory manager."""
    def __init__(self):
        self._sm_used = [False] * 8
        self._programs = {} # (pio_idx, prog_name) -> offset
        
    def get_sm(self) -> int:
        for i in range(8):
            if not self._sm_used[i]:
                self._sm_used[i] = True
                return i
        return -1

    def free_sm(self, sm_id: int):
        if 0 <= sm_id < 8:
            self._sm_used[sm_id] = False

    def load_program(self, sm_id: int, program):
        pio_idx = 0 if sm_id < 4 else 1
        prog_id = (pio_idx, str(program))
        if prog_id in self._programs:
            return self._programs[prog_id]
        
        pio = rp2.PIO(pio_idx)
        try:
            offset = pio.add_program(program)
            self._programs[prog_id] = offset
            return offset
        except OSError:
            return -1

    def clear_all(self):
        """Reset both PIO blocks and clear program cache."""
        for pio_idx in [0, 1]:
            pio = rp2.PIO(pio_idx)
            # Remove all programs if possible
            for prog_id, offset in list(self._programs.items()):
                if prog_id[0] == pio_idx:
                    del self._programs[prog_id]
            # Reset state machines
            for i in range(4):
                pio.active(i, 0)
        self._sm_used = [False] * 8

# --- Internal Constants & Helpers ---

class _Required:
    def __repr__(self): return "<required>"
_REQ = _Required()

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def _beep_program():
    pull(noblock) .side(0)
    mov(x, osr)
    label("loop")
    jmp(x_dec, "loop") .side(1)
    pull(noblock) .side(1)
    mov(x, osr)
    label("loop2")
    jmp(x_dec, "loop2") .side(0)

@rp2.asm_pio(out_init=(rp2.PIO.OUT_LOW,) * 6, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _out_program():
    pull()
    out(pins, 6)

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def _pwm_program():
    pull(noblock)
    mov(x, osr) # High duration
    pull(noblock)
    mov(y, osr) # Low duration
    label("high")
    jmp(x_dec, "high") .side(1)
    label("low")
    jmp(y_dec, "low") .side(0)

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
def _ws_led_program():
    wrap_target()
    out(x, 1)
    jmp(not_x, "do_zero")
    nop()           .side(1) [6]
    nop()           .side(0) [1]
    jmp("wrap_up")
    label("do_zero")
    nop()           .side(1) [2]
    nop()           .side(0) [5]
    label("wrap_up")
    wrap()

_HELP_DATA = {
    "LED": "LED(val): 1=ON, 0=OFF, -1=Toggle.",
    "WAIT": "WAIT(time, unit='frame'): frame, ms, or sec.",
    "IN": "IN(pin): Returns digital value (0 or 1).",
    "OUT": "OUT(pin, val): Single pin. OUT(val): Bit pattern.",
    "BEEP": "BEEP(note=440, duration=10): Plays sound. 'note' can be Hz or string like 'C4'.",
    "ANA": "ANA(pin, volt=False): Analog input (0-1023 or voltage).",
    "PWM": "PWM(pin, freq, duty): Precise PIO PWM. duty=0 to stop.",
    "WS_LED": "WS_LED(data, pin=25): Drives WS2812B LEDs.",
    "RND": "RND(n): Random 0 to n-1. RND(a, b): Random a to b-1.",
    "BTN": "BTN(callback=None): Returns button state or sets callback.",
    "SAVE": "SAVE(target): Save to slot (0-3) or filename.",
    "LOAD": "LOAD(target): Load from slot (0-3) or filename.",
    "WIFI": "WIFI(ssid, password): Connect to WiFi network.",
    "IOT_GET": "IOT_GET(url): HTTP GET with HTTPS/redirect support.",
    "IOT_POST": "IOT_POST(url, data): HTTP POST with HTTPS/redirect support.",
    "CORE2": "CORE2(func): Run function on second core.",
    "VERSION": "VERSION(): Returns library version 2.1.",
    "CLS": "CLS(): Clear screen.",
    "LC": "LC(x, y): Locate cursor.",
    "OK": "OK(): Displays 'OK'.",
    "HELP": "HELP(cmd=None): Shows help.",
    "PINS": "PINS(): Show pin configuration.",
    "I2CW": "I2CW(addr, data): I2C Write to address.",
    "I2CR": "I2CR(addr, size): I2C Read from address.",
    "UART": "UART(data_or_rate): Send string or set baud rate.",
    "FILES": "FILES(): List files in current directory.",
    "FREE": "FREE(): Show memory usage information.",
    "TICK": "TICK(): Get millisecond tick count.",
    "CLT": "CLT(): Reset tick count (pseudo).",
    "PR": "PR(*args): Alias for print(). Shortcut for IchigoJam '?' command.",
    "P": "P(*args): Even shorter alias for print().",
}

# --- 配置・定数 ---

BAUD_115200 = 115200
BAUD_57600  = 57600
BAUD_38400  = 38400
BAUD_31250  = 31250
BAUD_19200  = 19200
BAUD_9600   = 9600
BAUD_4800   = 4800
BAUD_2400   = 2400

NOTE_C4 = 262
NOTE_D4 = 294
NOTE_E4 = 330
NOTE_F4 = 349
NOTE_G4 = 392
NOTE_A4 = 440
NOTE_B4 = 494
NOTE_C5 = 523

_NOTE_MAP = {
    "C4": NOTE_C4, "C#4": 277, "D4": NOTE_D4, "D#4": 311, "E4": NOTE_E4, "F4": NOTE_F4,
    "F#4": 370, "G4": NOTE_G4, "G#4": 415, "A4": NOTE_A4, "A#4": 466, "B4": NOTE_B4,
    "C5": NOTE_C5, "C#5": 554, "D5": 587, "D#5": 622, "E5": 659, "F5": 698,
}

# --- IchigoJam Core Class ---

class IchigoJam:
    """IchigoJam compatibility layer for RP2040."""
    # Common GPIO Assignments
    # --- Configuration Constants ---
    DEFAULT_BAUD = BAUD_115200
    WAIT_FRAME_MS = 16.6
    ERROR_BLINK_MS = 50
    ERROR_BLINK_COUNT = 6
    WIFI_TIMEOUT_SEC = 30
    
    # UART Baud Rate Mapping (IchigoJam compatibility)
    BAUD_MAP = {
        1: BAUD_115200, 2: BAUD_115200, 3: BAUD_57600, 4: BAUD_38400, 
        5: BAUD_31250, 6: BAUD_19200, 7: BAUD_9600, 8: BAUD_4800, 9: BAUD_2400
    }
    
    # Default GPIO Configuration
    PIN_BUZZER_DEFAULT = 15
    PIN_BUTTON_DEFAULT = 14
    PIN_LED_DEFAULT = 25
    PIN_I2C_SDA_PICO = 8
    PIN_I2C_SCL_PICO = 9
    PIN_I2C_SDA_XIAO = 4
    PIN_I2C_SCL_XIAO = 5

    def __init__(self):
        # Board Detection
        try:
            self.machine_name = os.uname().machine
        except:
            self.machine_name = "Mocked RP2040"
            
        self.IS_PICO_W = "Pico W" in self.machine_name
        self.IS_XIAO = "XIAO RP2040" in self.machine_name
        
        # Pin Assignments
        self.PIN_LED = "LED" if self.IS_PICO_W else self.PIN_LED_DEFAULT
        self.PIN_BUZZER = self.PIN_BUZZER_DEFAULT
        self.PIN_BUTTON = self.PIN_BUTTON_DEFAULT
        
        if self.IS_XIAO:
            self.PIN_SDA = self.PIN_I2C_SDA_XIAO
            self.PIN_SCL = self.PIN_I2C_SCL_XIAO
        else:
            self.PIN_SDA = self.PIN_I2C_SDA_PICO
            self.PIN_SCL = self.PIN_I2C_SCL_PICO
        
        # Resource Managers
        self.pio_mgr = PIOManager()
        self._led_pin = None
        self._active_pwm = {}
        self._i2c = None
        self._uart: Optional[machine.UART] = None
        self._tick_offset: int = 0
        self.cert_validate: bool = False
        self.ca_file: Optional[str] = None
    
    def deinit(self):
        """すべてのリソースを解放し、PIOをリセットします。"""
        # PWMの停止
        for pin in list(self._active_pwm.keys()):
            self.PWM(pin, 1000, 0)
        
        # UARTの終了
        if self._uart:
            try: self._uart.deinit()
            except: pass
            self._uart = None
            
        # PIOの全停止
        self.pio_mgr.clear_all()
        gc.collect()
        print("IchigoJam System: Deinitialized.")

    def _warn_error(self, msg: str) -> None:
        """Display error and blink LED for warning."""
        print(f"ERROR: {msg}")
        try:
            if self._led_pin is None:
                self._led_pin = machine.Pin(self.PIN_LED, machine.Pin.OUT)
            for _ in range(self.ERROR_BLINK_COUNT): 
                self._led_pin.value(1); utime.sleep_ms(self.ERROR_BLINK_MS)
                self._led_pin.value(0); utime.sleep_ms(self.ERROR_BLINK_MS)
        except: pass

    def _validate_gpio(self, pin: int, cmd: str) -> bool:
        if not isinstance(pin, int) or pin < 0 or pin > 29:
            self._warn_error(f"{cmd}: Pin {pin} is out of range.")
            return False
        return True

    def LED(self, val: int = -1) -> None:
        try:
            if self._led_pin is None:
                self._led_pin = machine.Pin(self.PIN_LED, machine.Pin.OUT)
            if val == -1:
                self._led_pin.value(not self._led_pin.value())
            else:
                self._led_pin.value(1 if val else 0)
        except Exception as e: self._warn_error(f"LED: {e}")

    def WAIT(self, time: int, unit: str = "frame") -> None:
        """Wait for specified time."""
        if unit == "frame": utime.sleep_ms(int(time * self.WAIT_FRAME_MS))
        elif unit == "ms": utime.sleep_ms(time)
        else: utime.sleep(time)

    def IN(self, pin: int) -> int:
        if not self._validate_gpio(pin, "IN"): return 0
        return machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP).value()

    def OUT(self, pin: int, val: Optional[int] = None) -> None:
        try:
            if val is not None:
                if not self._validate_gpio(pin, "OUT"): return
                if pin in self._active_pwm:
                    sm_id, sm = self._active_pwm.pop(pin)
                    sm.active(0); self.pio_mgr.free_sm(sm_id)
                machine.Pin(pin, machine.Pin.OUT).value(1 if val else 0)
            else:
                sm_id = self.pio_mgr.get_sm()
                if sm_id < 0: return
                pio_pins = [machine.Pin(p, machine.Pin.OUT) for p in [1, 2, 3, 4, 5, 6]]
                offset = self.pio_mgr.load_program(sm_id, _out_program)
                sm = rp2.StateMachine(sm_id, _out_program, freq=1000000, out_base=pio_pins[0])
                sm.active(1); sm.put(pin); utime.sleep_ms(1); sm.active(0)
                self.pio_mgr.free_sm(sm_id)
        except Exception as e: self._warn_error(f"OUT: {e}")

    def BEEP(self, note: Union[int, str] = 440, duration: int = 10) -> None:
        try:
            freq = _NOTE_MAP.get(note, note) if isinstance(note, str) else note
            if freq <= 0: return
            cycle_us = 1000000 // freq
            sm_id = self.pio_mgr.get_sm()
            if sm_id < 0: return
            self.pio_mgr.load_program(sm_id, _beep_program)
            sm = rp2.StateMachine(sm_id, _beep_program, freq=2000000, sideset_base=machine.Pin(self.PIN_BUZZER))
            sm.active(1); sm.put(cycle_us); utime.sleep_ms(duration * 16); sm.active(0)
            self.pio_mgr.free_sm(sm_id)
        except Exception as e: self._warn_error(f"BEEP: {e}")

    def ANA(self, pin: int, volt: bool = False) -> float:
        try:
            if not self._validate_gpio(pin, "ANA"): return 0
            adc = machine.ADC(pin); val = adc.read_u16() >> 6
            return val / 1023.0 * 3.3 if volt else val
        except Exception as e: self._warn_error(f"ANA: {e}"); return 0

    def PWM(self, pin: int, freq: int, duty: float) -> None:
        if not self._validate_gpio(pin, "PWM"): return
        try:
            if duty == 0:
                if pin in self._active_pwm:
                    sm_id, sm = self._active_pwm.pop(pin)
                    sm.active(0); self.pio_mgr.free_sm(sm_id)
                    machine.Pin(pin, machine.Pin.OUT).value(0)
                return
            if pin in self._active_pwm:
                old_sm_id, old_sm = self._active_pwm[pin]
                old_sm.active(0); self.pio_mgr.free_sm(old_sm_id)
            sm_id = self.pio_mgr.get_sm()
            if sm_id < 0: return
            cycle_us = 1000000 // freq
            high_us, low_us = int(cycle_us * duty), cycle_us - int(cycle_us * duty)
            self.pio_mgr.load_program(sm_id, _pwm_program)
            sm = rp2.StateMachine(sm_id, _pwm_program, freq=1000000, sideset_base=machine.Pin(pin))
            sm.active(1); sm.put(high_us); sm.put(low_us); self._active_pwm[pin] = (sm_id, sm)
        except Exception as e: self._warn_error(f"PWM: {e}")

    def WS_LED(self, data: List[Union[int, Tuple[int, int, int]]], pin: int = 25) -> None:
        try:
            sm_id = self.pio_mgr.get_sm()
            if sm_id < 0: return
            self.pio_mgr.load_program(sm_id, _ws_led_program)
            sm = rp2.StateMachine(sm_id, _ws_led_program, freq=8000000, sideset_base=machine.Pin(pin))
            sm.active(1)
            for d in data:
                val = (d[1] << 16) | (d[0] << 8) | d[2] if isinstance(d, (tuple, list)) else d
                sm.put(val << 8)
            utime.sleep_ms(1); sm.active(0); self.pio_mgr.free_sm(sm_id)
        except Exception as e: self._warn_error(f"WS_LED: {e}")

    def RND(self, a: int, b: Optional[int] = None) -> int:
        if b is None: return random.getrandbits(16) % a if a > 0 else 0
        return random.randint(a, b - 1)

    def BTN(self, callback: Optional[Callable] = None) -> int:
        try:
            btn_pin = machine.Pin(self.PIN_BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)
            if callback: btn_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=lambda p: callback())
            return not btn_pin.value()
        except Exception as e: self._warn_error(f"BTN: {e}"); return 0

    def SAVE(self, target: Union[int, str]) -> None:
        try:
            fn = f"slot{target}.py" if isinstance(target, int) else target
            with open(fn, "w") as f: f.write("# Saved by IchigoJam Library\n")
            print(f"Saved to {fn}")
        except Exception as e: self._warn_error(f"SAVE: {e}")

    def LOAD(self, target: Union[int, str]) -> str:
        try:
            fn = f"slot{target}.py" if isinstance(target, int) else target
            with open(fn, "r") as f: return f.read()
        except Exception as e: self._warn_error(f"LOAD: {e}"); return ""

    def WIFI(self, ssid: str, password: str) -> None:
        """Connect to WiFi."""
        try:
            wlan = network.WLAN(network.STA_IF); wlan.active(True); wlan.connect(ssid, password)
            print(f"Connecting to {ssid}..."); timeout = self.WIFI_TIMEOUT_SEC
            while not wlan.isconnected() and timeout > 0: utime.sleep(1); timeout -= 1
            if wlan.isconnected(): print("Connected:", wlan.ifconfig()[0])
            else: self._warn_error("WIFI: Connection timeout")
        except Exception as e: self._warn_error(f"WIFI: {e}")

    def CORE2(self, func: Callable) -> None:
        try: _thread.start_new_thread(func, ())
        except Exception as e: self._warn_error(f"CORE2: {e}")

    def CLS(self) -> None: print("\033[2J\033[H")
    def LC(self, x: int, y: int) -> None: print(f"\033[{y};{x}H", end="")
    def OK(self) -> None: print("OK")
    def PR(self, *args, **kwargs) -> None: print(*args, **kwargs)
    def P(self, *args, **kwargs) -> None: print(*args, **kwargs)

    def _get_i2c(self):
        if self._i2c is None: self._i2c = machine.I2C(0, scl=machine.Pin(self.PIN_SCL), sda=machine.Pin(self.PIN_SDA))
        return self._i2c

    def I2CW(self, addr: int, data: Union[int, List[int], bytes]) -> int:
        """I2C Write. Returns 1 on success, 0 on failure."""
        try:
            if isinstance(data, int): data = bytes([data])
            elif isinstance(data, list): data = bytes(data)
            self._get_i2c().writeto(addr, data)
            return 1
        except Exception as e:
            self._warn_error(f"I2CW: {e}")
            return 0

    def I2CR(self, addr: int, size: int) -> list:
        """I2C Read. Returns list of bytes, empty list on failure."""
        try:
            return list(self._get_i2c().readfrom(addr, size))
        except Exception as e:
            self._warn_error(f"I2CR: {e}")
            return []

    def UART(self, val: Union[int, str, bytes]) -> None:
        """Set baud rate or send data. val=1-9: map to baud rate, val>=300: direct baud, str/bytes: send."""
        try:
            if isinstance(val, int):
                # Map 1-9 to specific baud rates, others used directly
                baud = self.BAUD_MAP.get(val, val if val >= 300 else self.DEFAULT_BAUD)
                if val == 0:
                    self._uart = None # De-reference (RP2-port behavior check)
                    return
                # Clean re-initialization
                if self._uart:
                    try: self._uart.deinit()
                    except: pass
                self._uart = machine.UART(0, baudrate=baud, tx=machine.Pin(0), rx=machine.Pin(1))
            else:
                if self._uart is None: self.UART(self.DEFAULT_BAUD)
                self._uart.write(val)
        except Exception as e: self._warn_error(f"UART: {e}")

    def TICK(self) -> int: return utime.ticks_ms() - self._tick_offset
    def CLT(self) -> None: self._tick_offset = utime.ticks_ms()
    
    def FREE(self) -> int:
        gc.collect(); f, a = gc.mem_free(), gc.mem_alloc()
        print(f"Free: {f}, Alloc: {a}, Total: {f+a}"); return f

    def FILES(self) -> None:
        for f in os.listdir(): print(f)

    def HELP(self, cmd: str = None) -> None:
        if cmd: print(_HELP_DATA.get(cmd.upper(), "Unknown command."))
        else: print("Available Commands: " + ", ".join(sorted(_HELP_DATA.keys())))

    def PINS(self) -> None:
        print(f"Board: {self.machine_name}")
        print(f"I/O: LED={self.PIN_LED}, BZ={self.PIN_BUZZER}, BTN={self.PIN_BUTTON}")
        print(f"Comm: I2C(SCL:{self.PIN_SCL}, SDA:{self.PIN_SDA}), UART(TX:0, RX:1)")

    def _iot_request(self, method: str, url: str, data: str = None, follow_redirects: bool = True) -> str:
        try:
            if "://" in url:
                proto, rest = url.split("://", 1)
                proto += ":"
                host, path = rest.split("/", 1) if "/" in rest else (rest, "/")
                if not path.startswith("/"): path = "/" + path
            else:
                proto, host, path = "http:", url, "/"
            
            port = 443 if proto == "https:" else 80
            addr = socket.getaddrinfo(host, port)[0][-1]
            s = socket.socket()
            s.connect(addr)
            if port == 443:
                if self.cert_validate:
                    if self.ca_file:
                        # 証明書検証あり
                        s = ssl.wrap_socket(s, server_hostname=host, cert_reqs=ssl.CERT_REQUIRED, ca_certs=self.ca_file)
                    else:
                        print("WARNING: cert_validate is True but no ca_file specified. Proceeding with host-only verify.")
                        s = ssl.wrap_socket(s, server_hostname=host)
                else:
                    # 検証なし (デフォルト)
                    s = ssl.wrap_socket(s, server_hostname=host)
            
            req = f"{method} {path} HTTP/1.0\r\nHost: {host}\r\n"
            if data: req += f"Content-Length: {len(data)}\r\n\r\n{data}"
            else: req += "\r\n"
            
            s.write(req.encode()); res = s.read(4096).decode('utf-8'); s.close()
            
            if follow_redirects and ("HTTP/1.1 30" in res or "HTTP/1.0 30" in res):
                for line in res.split("\r\n"):
                    if line.startswith("Location:"):
                        return self._iot_request(method, line.split(":", 1)[1].strip(), data, True)
            return res.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in res else res
        except Exception as e: self._warn_error(f"IOT: {e}"); return None

    def IOT_CONFIG(self, cert_validate: Optional[bool] = None, ca_file: Optional[str] = None) -> None:
        """IoT通信のセキュリティ設定を行います。
        cert_validate: Trueで証明書検証を有効化。
        ca_file: 検証に使用する証明書ファイルのパスを指定。
        """
        if cert_validate is not None:
            self.cert_validate = cert_validate
            print(f"IoT Cert Validation: {'ENABLED' if cert_validate else 'DISABLED'}")
        if ca_file is not None:
            self.ca_file = ca_file
            print(f"CA File set to: {ca_file}")

    def IOT_GET(self, url: str) -> Optional[str]: 
        return self._iot_request("GET", url)

    def IOT_POST(self, url: str, data: str) -> Optional[str]: 
        return self._iot_request("POST", url, data)

# --- Global Instance and Wrappers ---

ij = IchigoJam()

def LED(val: int = -1): return ij.LED(val)
def WAIT(time: int, unit: str = "frame"): return ij.WAIT(time, unit)
def IN(pin: int): return ij.IN(pin)
def OUT(pin: int, val: int = None): return ij.OUT(pin, val)
def BEEP(note: int = 440, duration: int = 10): return ij.BEEP(note, duration)
def ANA(pin: int, volt: bool = False): return ij.ANA(pin, volt)
def PWM(pin: int, freq: int, duty: float): return ij.PWM(pin, freq, duty)
def WS_LED(data: list, pin: int = 25): return ij.WS_LED(data, pin)
def RND(a: int, b: int = None): return ij.RND(a, b)
def BTN(callback=None): return ij.BTN(callback)
def SAVE(target): return ij.SAVE(target)
def LOAD(target): return ij.LOAD(target)
def WIFI(ssid: str, password: str): return ij.WIFI(ssid, password)
def IOT_GET(url: str): return ij.IOT_GET(url)
def IOT_POST(url: str, data: str): return ij.IOT_POST(url, data)
def CORE2(func): return ij.CORE2(func)
def CLS(): return ij.CLS()
def LC(x: int, y: int): return ij.LC(x, y)
def I2CW(addr: int, data): return ij.I2CW(addr, data)
def I2CR(addr: int, size: int): return ij.I2CR(addr, size)
def UART(val): return ij.UART(val)
def TICK(): return ij.TICK()
def CLT(): return ij.CLT()
def FREE(): return ij.FREE()
def FILES(): return ij.FILES()
def HELP(cmd: str = None): return ij.HELP(cmd)
def PINS(): return ij.PINS()
def VERSION(): return "IchigoJam Python v2.1 (Class-based)"
def OK(): print("OK")
def IOT_CONFIG(cert_validate: bool = None): return ij.IOT_CONFIG(cert_validate)
def PR(*args, **kwargs): return ij.PR(*args, **kwargs)
def P(*args, **kwargs): return ij.P(*args, **kwargs)

__all__ = ["LED", "WAIT", "IN", "OUT", "BEEP", "ANA", "PWM", "WS_LED", "RND", "BTN", "SAVE", "LOAD", 
           "WIFI", "IOT_GET", "IOT_POST", "IOT_CONFIG", "CORE2", 
           "I2CW", "I2CR", "UART", "FILES", "FREE", "TICK", "CLT", "VERSION",
           "CLS", "LC", "HELP", "PINS", "OK", "PR", "P", "ij",
           "BAUD_115200", "BAUD_57600", "BAUD_38400", "BAUD_31250", "BAUD_19200", "BAUD_9600", "BAUD_4800", "BAUD_2400",
           "NOTE_C4", "NOTE_D4", "NOTE_E4", "NOTE_F4", "NOTE_G4", "NOTE_A4", "NOTE_B4", "NOTE_C5"]
