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

# --- Board Detection & Default Pins ---
_machine_name = os.uname().machine
IS_PICO_W = "Pico W" in _machine_name
IS_XIAO = "XIAO RP2040" in _machine_name

PIN_LED = "LED" if IS_PICO_W else 25
PIN_BUZZER = 15
PIN_BUTTON = 14
PIN_SCL = 9 if not IS_XIAO else 5 # XIAO D5
PIN_SDA = 8 if not IS_XIAO else 4 # XIAO D4

# --- PIO Resource Manager ---

class PIOManager:
    """PIO state machine and instruction memory manager."""
    def __init__(self):
        self._sm_used = [False] * 8
        self._programs = {} # (pio_idx, prog_name) -> offset
        
    def get_sm(self):
        for i in range(8):
            if not self._sm_used[i]:
                self._sm_used[i] = True
                return i
        return -1

    def free_sm(self, sm_id):
        if 0 <= sm_id < 8:
            self._sm_used[sm_id] = False

    def load_program(self, sm_id, program):
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

pio_mgr = PIOManager()

# --- Internal Constants & Helpers ---

class _Required:
    def __repr__(self): return "<required>"
_REQ = _Required()

def _check_args(cmd_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if _REQ in args or _REQ in kwargs.values():
                print(f"Usage: {_HELP_DATA.get(cmd_name, 'No help available.')}")
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator

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
    "USB_KEYBOARD": "USB_KEYBOARD(text): Emulate keyboard typing.",
    "USB_MOUSE": "USB_MOUSE(x, y, click): Emulate mouse movement.",
    "USB_JOYPAD": "USB_JOYPAD(buttons, axis_x, axis_y): Emulate gamepad.",
    "I2CW": "I2CW(addr, data): I2C Write to address.",
    "I2CR": "I2CR(addr, size): I2C Read from address.",
    "UART": "UART(data_or_rate): Send string or set baud rate.",
    "FILES": "FILES(): List files in current directory.",
    "FREE": "FREE(): Show memory usage information.",
    "TICK": "TICK(): Get millisecond tick count.",
    "CLT": "CLT(): Reset tick count (pseudo).",
    "PEEK": "PEEK(addr): Read memory (if supported) or dictionary.",
    "POKE": "POKE(addr, val): Write memory (if supported) or dictionary.",
    "VERSION": "VERSION(): Returns library version 2.0.",
    "CLS": "CLS(): Clear screen.",
    "LC": "LC(x, y): Locate cursor.",
    "OK": "OK(): Displays 'OK'.",
    "HELP": "HELP(cmd=None): Shows help.",
    "PINS": "PINS(): Show pin configuration.",
}

_NOTE_MAP = {
    "C4": 262, "C#4": 277, "D4": 294, "D#4": 311, "E4": 330, "F4": 349,
    "F#4": 370, "G4": 392, "G#4": 415, "A4": 440, "A#4": 466, "B4": 494,
    "C5": 523, "C#5": 554, "D5": 587, "D#5": 622, "E5": 659, "F5": 698,
}

# --- Error Handling ---

def _warn_error(msg):
    """Display error and blink LED for warning."""
    print(f"ERROR: {msg}")
    led = machine.Pin(PIN_LED, machine.Pin.OUT)
    for _ in range(10): 
        led.value(1); utime.sleep_ms(100)
        led.value(0); utime.sleep_ms(100)

# --- Global State ---
_led_pin = None
_active_pwm = {}

# --- Commands ---

@_check_args("LED")
def LED(val=_REQ):
    """Control onboard LED: 1=ON, 0=OFF, -1=Toggle. Pico W uses 'LED' internally."""
    global _led_pin
    try:
        if _led_pin is None:
            _led_pin = machine.Pin(PIN_LED, machine.Pin.OUT)
        if val == -1:
            try: _led_pin.value(not _led_pin.value())
            except: pass
        else:
            _led_pin.value(1 if val else 0)
    except Exception as e:
        _warn_error(f"LED: {e}")

def _validate_gpio(pin, cmd):
    """Internal helper to validate GPIO pin range (0-28)."""
    valid_range = range(0, 29)
    if pin not in valid_range:
        _warn_error(f"{cmd}: Pin {pin} is out of range. Use GPIO 0-28.")
        return False
    return True

@_check_args("WAIT")
def WAIT(time=_REQ, unit="frame"):
    """Wait for specified time. Units: frame (1/60s), ms, sec."""
    if unit == "frame": 
        utime.sleep_ms(int(time * 16.6))
    elif unit == "ms": 
        utime.sleep_ms(time)
    else: 
        utime.sleep(time)

@_check_args("IN")
def IN(pin=_REQ):
    """Read digital input from pin (GPIO 0-28)."""
    if not _validate_gpio(pin, "IN"): return 0
    return machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP).value()

_OUT_PINS = [1, 2, 3, 4, 5, 6] # Align OUT1-6 with GPIO 1-6

@_check_args("OUT")
def OUT(pin=_REQ, val=None):
    """Output to pin. OUT(pin, val) for single pin (0-28), OUT(pattern) for bit pattern."""
    global _active_pwm
    try:
        if val is not None:
            if not _validate_gpio(pin, "OUT"): return
            # Stop PWM on this pin if active
            if pin in _active_pwm:
                sm_id, sm = _active_pwm.pop(pin)
                sm.active(0)
                pio_mgr.free_sm(sm_id)
            # Single pin mode
            machine.Pin(pin, machine.Pin.OUT).value(1 if val else 0)
        else:
            # Bit pattern mode (PIO)
            sm_id = pio_mgr.get_sm()
            if sm_id < 0: return
            pio_pins = [machine.Pin(p, machine.Pin.OUT) for p in _OUT_PINS]
            offset = pio_mgr.load_program(sm_id, _out_program)
            sm = rp2.StateMachine(sm_id, _out_program, freq=1000000, out_base=pio_pins[0])
            sm.active(1)
            sm.put(pin)
            utime.sleep_ms(1)
            sm.active(0)
            sm.restart()
            pio_mgr.free_sm(sm_id)
    except Exception as e:
        _warn_error(f"OUT: {e}")

def BEEP(note=440, duration=10):
    """Play sound. note: Hz or string like 'C4', duration: frames."""
    try:
        freq = _NOTE_MAP.get(note, note) if isinstance(note, str) else note
        if freq <= 0: return
        cycle_us = 1000000 // freq
        sm_id = pio_mgr.get_sm()
        if sm_id < 0: return
        
        offset = pio_mgr.load_program(sm_id, _beep_program)
        sm = rp2.StateMachine(sm_id, _beep_program, freq=2000000, sideset_base=machine.Pin(PIN_BUZZER))
        sm.active(1)
        sm.put(cycle_us)
        utime.sleep_ms(duration * 16)
        sm.active(0)
        pio_mgr.free_sm(sm_id)
    except Exception as e:
        _warn_error(f"BEEP: {e}")

def HELP(cmd=None):
    """Show help for commands."""
    if cmd:
        print(_HELP_DATA.get(cmd.upper(), "Unknown command."))
    else:
        print("Available Commands:")
        print(", ".join(sorted(_HELP_DATA.keys())))

def PINS():
    """Show default pin configuration."""
    print(f"Board detected: {_machine_name}")
    print(f"Default I/O: LED={PIN_LED}, BUZZER={PIN_BUZZER}, BTN={PIN_BUTTON}")
    print(f"Communications: I2C(SCL:{PIN_SCL}, SDA:{PIN_SDA}), UART(TX:0, RX:1)")

@_check_args("ANA")
def ANA(pin=_REQ, volt=False):
    """Read analog input. ADC is on pins 26-28. ANA(26) reads ADC0."""
    try:
        # Check if pin is ADC capable (RP2040: 26, 27, 28)
        if pin not in [26, 27, 28]:
            _warn_error(f"ANA: Pin {pin} is not ADC capable. Use GPIO 26, 27, or 28 for analog input.")
            return 0
        adc = machine.ADC(pin)
        val = adc.read_u16() >> 6 # 10-bit compat
        return val / 1023.0 * 3.3 if volt else val
    except Exception as e:
        _warn_error(f"ANA: {e}")
        return 0

@_check_args("PWM")
def PWM(pin=_REQ, freq=_REQ, duty=_REQ):
    """Start PIO-based PWM on pin (0-28). duty: 0.0-1.0. Set duty=0 to stop."""
    global _active_pwm
    if not _validate_gpio(pin, "PWM"): return
    try:
        # Stop PWM if duty is 0
        if duty == 0:
            if pin in _active_pwm:
                sm_id, sm = _active_pwm.pop(pin)
                sm.active(0)
                pio_mgr.free_sm(sm_id)
                machine.Pin(pin, machine.Pin.OUT).value(0)
            return
        
        # Stop existing PWM on this pin
        if pin in _active_pwm:
            old_sm_id, old_sm = _active_pwm[pin]
            old_sm.active(0)
            pio_mgr.free_sm(old_sm_id)
        
        sm_id = pio_mgr.get_sm()
        if sm_id < 0: return
        cycle_us = 1000000 // freq
        high_us = int(cycle_us * duty)
        low_us = cycle_us - high_us
        offset = pio_mgr.load_program(sm_id, _pwm_program)
        sm = rp2.StateMachine(sm_id, _pwm_program, freq=1000000, sideset_base=machine.Pin(pin))
        sm.active(1)
        sm.put(high_us)
        sm.put(low_us)
        _active_pwm[pin] = (sm_id, sm)
    except Exception as e: 
        _warn_error(f"PWM: {e}")

@_check_args("WS_LED")
def WS_LED(data=_REQ, pin=25):
    """Drive WS2812B LEDs. data: list of (R,G,B) tuples or integers."""
    try:
        sm_id = pio_mgr.get_sm()
        if sm_id < 0: return
        offset = pio_mgr.load_program(sm_id, _ws_led_program)
        sm = rp2.StateMachine(sm_id, _ws_led_program, freq=8000000, sideset_base=machine.Pin(pin))
        sm.active(1)
        for d in data:
            if isinstance(d, (tuple, list)):
                val = (d[1] << 16) | (d[0] << 8) | d[2]  # GRB order for WS2812B
            else: 
                val = d
            sm.put(val << 8)
        utime.sleep_ms(1)
        sm.active(0)
        pio_mgr.free_sm(sm_id)
    except Exception as e: 
        _warn_error(f"WS_LED: {e}")

@_check_args("RND")
def RND(a=_REQ, b=None):
    """Random number. RND(n): 0 to n-1. RND(a, b): a to b-1."""
    if b is None: 
        return random.getrandbits(16) % a if a > 0 else 0
    return random.randint(a, b - 1)

def BTN(callback=None):
    """Read button state or set callback for button press."""
    try:
        btn_pin = machine.Pin(PIN_BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)
        if callback: 
            btn_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=lambda p: callback())
        return not btn_pin.value()
    except Exception as e: 
        _warn_error(f"BTN: {e}")
        return 0

@_check_args("SAVE")
def SAVE(target=_REQ):
    """Save to slot (0-3) or filename."""
    try:
        filename = f"slot{target}.py" if isinstance(target, int) else target
        with open(filename, "w") as f: 
            f.write("# Saved by IchigoJam Library\n")
        print(f"Saved to {filename}")
    except Exception as e: 
        _warn_error(f"SAVE: {e}")

@_check_args("LOAD")
def LOAD(target=_REQ):
    """Load from slot (0-3) or filename."""
    try:
        filename = f"slot{target}.py" if isinstance(target, int) else target
        with open(filename, "r") as f: 
            content = f.read()
            print(f"Loaded {filename}")
            return content
    except Exception as e: 
        _warn_error(f"LOAD: {e}")

# --- v2.0+ Advanced Features ---

def _iot_request(method, url, data=None, follow_redirects=True):
    """Internal HTTP/HTTPS request handler with redirect support."""
    try:
        # Improved URL parsing
        if "://" in url:
            proto, rest = url.split("://", 1)
            proto += ":"
            if "/" in rest:
                host, path = rest.split("/", 1)
                path = "/" + path
            else:
                host = rest
                path = "/"
        else:
            proto = "http:"
            host = url
            path = "/"
        
        port = 443 if proto == "https:" else 80
        
        addr = socket.getaddrinfo(host, port)[0][-1]
        s = socket.socket()
        s.connect(addr)
        if port == 443:
            s = ssl.wrap_socket(s, server_hostname=host)
        
        req = f"{method} {path} HTTP/1.0\r\nHost: {host}\r\n"
        if data:
            req += f"Content-Length: {len(data)}\r\n\r\n{data}"
        else:
            req += "\r\n"
        
        s.write(req.encode())
        res = s.read(4096).decode('utf-8')
        s.close()
        
        # Handle Redirects (301, 302, 307)
        if follow_redirects and ("HTTP/1.1 30" in res or "HTTP/1.0 30" in res):
            for line in res.split("\r\n"):
                if line.startswith("Location:"):
                    new_url = line.split(":", 1)[1].strip()
                    return _iot_request(method, new_url, data, follow_redirects)
        
        # Return body
        return res.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in res else res
    except Exception as e:
        _warn_error(f"IOT: {e}")
        return None

@_check_args("IOT_GET")
def IOT_GET(url=_REQ):
    """HTTP GET with HTTPS and redirect support."""
    return _iot_request("GET", url)

@_check_args("IOT_POST")
def IOT_POST(url=_REQ, data=_REQ):
    """HTTP POST with HTTPS and redirect support."""
    return _iot_request("POST", url, data)

def WIFI(ssid=_REQ, password=_REQ):
    """Connect to WiFi network with 30s timeout."""
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(ssid, password)
        print(f"Connecting to {ssid}...")
        timeout = 30
        while not wlan.isconnected() and timeout > 0:
            utime.sleep(1)
            timeout -= 1
        if wlan.isconnected():
            print("Connected:", wlan.ifconfig()[0])
        else:
            _warn_error("WIFI: Connection timeout")
    except Exception as e: 
        _warn_error(f"WIFI: {e}")

def CORE2(func=_REQ):
    """Run function on second core (parallel execution)."""
    try:
        _thread.start_new_thread(func, ())
    except Exception as e: 
        _warn_error(f"CORE2: {e}")

# USB/Input Stubs (Require TinyUSB support in firmware)
def USB_KEYBOARD(text): 
    """Emulate USB keyboard typing (stub)."""
    print(f"USB Keyboard Type: {text}")

def USB_MOUSE(x, y, click=0): 
    """Emulate USB mouse movement (stub)."""
    print(f"USB Mouse Move: {x},{y} Click:{click}")

def USB_JOYPAD(buttons, axis_x=0, axis_y=0): 
    """Emulate USB gamepad (stub)."""
    print(f"USB Joypad: {buttons} Axes:{axis_x},{axis_y}")

# Graphics Stubs
def CLS(): 
    """Clear screen (ANSI escape code)."""
    print("\033[2J\033[H")

def LC(x, y): 
    """Locate cursor (ANSI escape code)."""
    print(f"\033[{y};{x}H", end="")

def SPRITE(id, data, x, y): 
    """Sprite drawing (stub)."""
    pass

def DRAW_BUFFER(data): 
    """DMA buffer drawing (stub)."""
    pass

# --- Communication Commands ---

_i2c = None
def _get_i2c():
    global _i2c
    if _i2c is None:
        _i2c = machine.I2C(0, scl=machine.Pin(PIN_SCL), sda=machine.Pin(PIN_SDA))
    return _i2c

@_check_args("I2CW")
def I2CW(addr=_REQ, data=_REQ):
    """I2C Write. data can be a list of bytes or an integer."""
    try:
        if isinstance(data, int): data = bytes([data])
        elif isinstance(data, list): data = bytes(data)
        _get_i2c().writeto(addr, data)
    except Exception as e: _warn_error(f"I2CW: {e}")

@_check_args("I2CR")
def I2CR(addr=_REQ, size=_REQ):
    """I2C Read. Returns list of bytes."""
    try:
        return list(_get_i2c().readfrom(addr, size))
    except Exception as e: 
        _warn_error(f"I2CR: {e}")
        return []

_uart = None
def UART(val=_REQ):
    """UART Send or Setup. UART(baudrate) or UART(string)."""
    global _uart
    try:
        if isinstance(val, int):
            _uart = machine.UART(0, baudrate=val, tx=machine.Pin(0), rx=machine.Pin(1))
        else:
            if _uart is None: UART(115200) # Default setup
            _uart.write(val)
    except Exception as e: _warn_error(f"UART: {e}")

# --- Memory and Utility Commands ---

_tick_offset = 0
def TICK():
    """Return milliseconds since last CLT or start."""
    return utime.ticks_ms() - _tick_offset

def CLT():
    """Clear tick count (reset offset)."""
    global _tick_offset
    _tick_offset = utime.ticks_ms()

import gc
def FREE():
    """Show free and allocated memory."""
    gc.collect()
    free = gc.mem_free()
    alloc = gc.mem_alloc()
    print(f"Free: {free} bytes, Alloc: {alloc} bytes, Total: {free+alloc} bytes")
    return free

def FILES():
    """List files on the board."""
    for f in os.listdir():
        print(f)

# Virtual memory for PEEK/POKE if direct memory access is not used
_virtual_mem = {}
def PEEK(addr):
    """Read from address (stub for dictionary-based virtual RAM)."""
    return _virtual_mem.get(addr, 0)

def POKE(addr, val):
    """Write to address (stub for dictionary-based virtual RAM)."""
    _virtual_mem[addr] = val & 0xFF

def VERSION():
    """Library Version."""
    return "IchigoJam Python v2.0"

def OK():
    """Display OK message."""
    print("OK")

__all__ = ["LED", "WAIT", "IN", "OUT", "BEEP", "ANA", "PWM", "WS_LED", "RND", "BTN", "SAVE", "LOAD", 
           "WIFI", "IOT_GET", "IOT_POST", "CORE2", "USB_KEYBOARD", "USB_MOUSE", "USB_JOYPAD",
           "I2CW", "I2CR", "UART", "FILES", "FREE", "TICK", "CLT", "PEEK", "POKE", "VERSION",
           "CLS", "LC", "SPRITE", "DRAW_BUFFER", "HELP", "PINS", "OK"]
