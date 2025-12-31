import machine
import rp2
import utime
import sys

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
    "PWM": "PWM(pin, freq, duty): Precise PIO PWM.",
    "WS_LED": "WS_LED(data, pin=LED_PIN): Drives WS2812B LEDs.",
    "RND": "RND(n): Random 0 to n-1. RND(a, b): Random a to b-1.",
    "BTN": "BTN(callback=None): Returns button state or sets callback.",
    "SAVE": "SAVE(target): Save to slot (0-3) or filename.",
    "LOAD": "LOAD(target): Load from slot (0-3) or filename.",
    "OK": "OK(): Displays 'OK'.",
    "HELP": "HELP(cmd=None): Shows help.",
}

_NOTE_MAP = {
    "C4": 262, "C#4": 277, "D4": 294, "D#4": 311, "E4": 330, "F4": 349,
    "F#4": 370, "G4": 392, "G#4": 415, "A4": 440, "A#4": 466, "B4": 494,
    "C5": 523, "C#5": 554, "D5": 587, "D#5": 622, "E5": 659, "F5": 698,
}

# --- Error Handling ---

def _warn_error(msg):
    print(f"ERROR: {msg}")
    led = machine.Pin(25, machine.Pin.OUT)
    # Simple alert pattern
    for _ in range(10): 
        led.value(1); utime.sleep_ms(100)
        led.value(0); utime.sleep_ms(100)

# --- Commands ---

@_check_args("LED")
def LED(val=_REQ):
    try:
        machine.Pin(25, machine.Pin.OUT).value(1 if val == 1 else 0 if val == 0 else not machine.Pin(25).value() if val == -1 else 0)
    except: pass

@_check_args("WAIT")
def WAIT(time=_REQ, unit="frame"):
    if unit == "frame": utime.sleep_ms(int(time * 16.6))
    elif unit == "ms": utime.sleep_ms(time)
    else: utime.sleep(time)

@_check_args("IN")
def IN(pin=_REQ):
    return machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP).value()

_OUT_PINS = [2, 3, 4, 5, 6, 7] # IchigoJam OUT1-6 mapping candidate

@_check_args("OUT")
def OUT(pin=_REQ, val=None):
    try:
        if val is not None:
            # Single pin mode
            machine.Pin(pin, machine.Pin.OUT).value(1 if val else 0)
        else:
            # Bit pattern mode (PIO)
            sm_id = pio_mgr.get_sm()
            if sm_id < 0: return
            # Default to Pico Pins 2-7 for OUT1-6
            pio_pins = [machine.Pin(p, machine.Pin.OUT) for p in _OUT_PINS]
            offset = pio_mgr.load_program(sm_id, _out_program)
            sm = rp2.StateMachine(sm_id, _out_program, freq=1000000, out_base=pio_pins[0])
            sm.active(1)
            sm.put(pin) # In this case pin is the pattern
            utime.sleep_ms(1)
            sm.active(0)
            sm.restart() # Reset pins
            pio_mgr.free_sm(sm_id)
    except Exception as e:
        _warn_error(f"OUT: {e}")

def BEEP(note=440, duration=10):
    try:
        freq = _NOTE_MAP.get(note, note) if isinstance(note, str) else note
        if freq <= 0: return
        cycle_us = 1000000 // freq
        sm_id = pio_mgr.get_sm()
        if sm_id < 0: return
        
        offset = pio_mgr.load_program(sm_id, _beep_program)
        sm = rp2.StateMachine(sm_id, _beep_program, freq=2000000, sideset_base=machine.Pin(15)) # Default buzzer pin
        sm.active(1)
        sm.put(cycle_us)
        utime.sleep_ms(duration * 16) # IchigoJam frame unit approx
        sm.active(0)
        pio_mgr.free_sm(sm_id)
    except Exception as e:
        _warn_error(f"BEEP: {e}")

def HELP(cmd=None):
    if cmd:
        print(_HELP_DATA.get(cmd.upper(), "Unknown command."))
    else:
        print("Available Commands:")
        print(", ".join(_HELP_DATA.keys()))

def PINS():
    print("Default Config: LED=25, BUZZER=15, I2C=SCL:9,SDA:8")

@_check_args("ANA")
def ANA(pin=_REQ, volt=False):
    try:
        adc = machine.ADC(pin)
        val = adc.read_u16() >> 6 # 10-bit compat
        return val / 1023.0 * 3.3 if volt else val
    except Exception as e:
        _warn_error(f"ANA: {e}")
        return 0

@_check_args("PWM")
def PWM(pin=_REQ, freq=_REQ, duty=_REQ):
    try:
        sm_id = pio_mgr.get_sm()
        if sm_id < 0: return
        cycle_us = 1000000 // freq
        high_us = int(cycle_us * duty)
        low_us = cycle_us - high_us
        offset = pio_mgr.load_program(sm_id, _pwm_program)
        sm = rp2.StateMachine(sm_id, _pwm_program, freq=1000000, sideset_base=machine.Pin(pin))
        sm.active(1)
        sm.put(high_us); sm.put(low_us)
    except Exception as e: _warn_error(f"PWM: {e}")

@_check_args("WS_LED")
def WS_LED(data=_REQ, pin=25):
    try:
        sm_id = pio_mgr.get_sm()
        if sm_id < 0: return
        offset = pio_mgr.load_program(sm_id, _ws_led_program)
        sm = rp2.StateMachine(sm_id, _ws_led_program, freq=8000000, sideset_base=machine.Pin(pin))
        sm.active(1)
        for d in data:
            if isinstance(d, tuple) or isinstance(d, list):
                val = (d[1] << 16) | (d[0] << 8) | d[2]
            else: val = d
            sm.put(val << 8)
        utime.sleep_ms(1); sm.active(0); pio_mgr.free_sm(sm_id)
    except Exception as e: _warn_error(f"WS_LED: {e}")

import random
@_check_args("RND")
def RND(a=_REQ, b=None):
    if b is None: return random.getrandbits(16) % a if a > 0 else 0
    return random.randint(a, b - 1)

def BTN(callback=None):
    try:
        btn_pin = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
        if callback: btn_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=lambda p: callback())
        return not btn_pin.value()
    except Exception as e: _warn_error(f"BTN: {e}"); return 0

@_check_args("SAVE")
def SAVE(target=_REQ):
    try:
        filename = f"slot{target}.py" if isinstance(target, int) else target
        with open(filename, "w") as f: f.write("# Saved by IchigoJam Library\n")
        print(f"Saved to {filename}")
    except Exception as e: _warn_error(f"SAVE: {e}")

@_check_args("LOAD")
def LOAD(target=_REQ):
    try:
        filename = f"slot{target}.py" if isinstance(target, int) else target
        with open(filename, "r") as f: print(f"Loaded {filename}"); return f.read()
    except Exception as e: _warn_error(f"LOAD: {e}")

# --- v2.0+ Advanced Features ---

import network
import usocket as socket
import ussl as ssl

def _iot_request(method, url, data=None, follow_redirects=True):
    try:
        # Simple parser for URL
        proto, _, host, path = (url.split("/") + ["", "", "", ""])[0:4]
        path = "/" + "/".join(url.split("/")[3:])
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
        
        s.write(req)
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
    return _iot_request("GET", url)

@_check_args("IOT_POST")
def IOT_POST(url=_REQ, data=_REQ):
    return _iot_request("POST", url, data)

def WIFI(ssid=_REQ, password=_REQ):
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(ssid, password)
        print(f"Connecting to {ssid}...")
        while not wlan.isconnected(): utime.sleep(1)
        print("Connected:", wlan.ifconfig()[0])
    except Exception as e: _warn_error(f"WIFI: {e}")

import _thread
def CORE2(func=_REQ):
    try:
        _thread.start_new_thread(func, ())
    except Exception as e: _warn_error(f"CORE2: {e}")

# USB/Input Stubs (Require TinyUSB support in firmware)
def USB_KEYBOARD(text): print(f"USB Keyboard Type: {text}")
def USB_MOUSE(x, y, click=0): print(f"USB Mouse Move: {x},{y} Click:{click}")
def USB_JOYPAD(buttons, axis_x=0, axis_y=0): print(f"USB Joypad: {buttons} Axes:{axis_x},{axis_y}")

# Graphics Stubs
def CLS(): print("\033[2J\033[H")
def LC(x, y): print(f"\033[{y};{x}H")
def SPRITE(id, data, x, y): pass
def DRAW_BUFFER(data): pass

def OK():
    print("OK")

__all__ = ["LED", "WAIT", "IN", "OUT", "BEEP", "ANA", "PWM", "WS_LED", "RND", "BTN", "SAVE", "LOAD", 
           "WIFI", "IOT_GET", "IOT_POST", "CORE2", "USB_KEYBOARD", "USB_MOUSE", "USB_JOYPAD",
           "CLS", "LC", "SPRITE", "DRAW_BUFFER", "HELP", "PINS", "OK"]
