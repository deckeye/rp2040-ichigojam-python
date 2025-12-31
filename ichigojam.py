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
    "LED": "LED(val): 1=ON, 0=OFF, -1=Toggle. Controls the onboard LED.",
    "WAIT": "WAIT(time, unit='frame'): frame(1/60s), ms, or sec.",
    "IN": "IN(pin): Returns digital value (0 or 1) of the pin.",
    "OUT": "OUT(pin, val): Sets signal to the pin. OUT(val): Bit pattern.",
    "BEEP": "BEEP(note, duration): Plays a sound. 'note' can be Hz or string like 'C4'.",
    "ANA": "ANA(pin, volt=False): Analog input (0-1023 or voltage).",
    "PWM": "PWM(pin, freq, duty): Precise PIO-driven PWM.",
    "WS_LED": "WS_LED(data, pin=LED_PIN): Drives WS2812B LEDs.",
    "RND": "RND(n): Random 0 to n-1. RND(a, b): Random a to b-1.",
    "BTN": "BTN(callback): Sets a function to run when button is pressed.",
    "SAVE": "SAVE(target): Save to slot (0-3) or filename.",
    "LOAD": "LOAD(target): Load from slot (0-3) or filename.",
    "OK": "OK(): Displays the signature 'OK'.",
    "HELP": "HELP(cmd): Shows this help message.",
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

def LED(val):
    try:
        machine.Pin(25, machine.Pin.OUT).value(1 if val == 1 else 0 if val == 0 else not machine.Pin(25).value() if val == -1 else 0)
    except: pass

def WAIT(time, unit="frame"):
    if unit == "frame": utime.sleep_ms(int(time * 16.6))
    elif unit == "ms": utime.sleep_ms(time)
    else: utime.sleep(time)

def IN(pin):
    return machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP).value()

_OUT_PINS = [2, 3, 4, 5, 6, 7] # IchigoJam OUT1-6 mapping candidate

def OUT(pin, val=None):
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

def BEEP(note, duration=10):
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

def ANA(pin, volt=False):
    try:
        adc = machine.ADC(pin)
        val = adc.read_u16() >> 6 # 10-bit compat
        return val / 1023.0 * 3.3 if volt else val
    except Exception as e:
        _warn_error(f"ANA: {e}")
        return 0

def PWM(pin, freq, duty):
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

def WS_LED(data, pin=25):
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
def RND(a, b=None):
    if b is None: return random.getrandbits(16) % a if a > 0 else 0
    return random.randint(a, b - 1)

def BTN(callback=None):
    try:
        btn_pin = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
        if callback: btn_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=lambda p: callback())
        return not btn_pin.value()
    except Exception as e: _warn_error(f"BTN: {e}"); return 0

def SAVE(target):
    try:
        filename = f"slot{target}.py" if isinstance(target, int) else target
        with open(filename, "w") as f: f.write("# Saved by IchigoJam Library\n")
        print(f"Saved to {filename}")
    except Exception as e: _warn_error(f"SAVE: {e}")

def LOAD(target):
    try:
        filename = f"slot{target}.py" if isinstance(target, int) else target
        with open(filename, "r") as f: print(f"Loaded {filename}"); return f.read()
    except Exception as e: _warn_error(f"LOAD: {e}")

def OK():
    print("OK")

__all__ = ["LED", "WAIT", "IN", "OUT", "BEEP", "ANA", "PWM", "WS_LED", "RND", "BTN", "SAVE", "LOAD", "HELP", "PINS", "OK"]
