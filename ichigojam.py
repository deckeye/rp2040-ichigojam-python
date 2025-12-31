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

_HELP_DATA = {
    "LED": "LED(val): 1=ON, 0=OFF, -1=Toggle. Controls the onboard LED.",
    "WAIT": "WAIT(time, unit='frame'): frame(1/60s), ms, or sec.",
    "IN": "IN(pin): Returns digital value (0 or 1) of the pin.",
    "OUT": "OUT(pin, val): Sets signal to the pin. OUT(val): Bit pattern (TBD).",
    "BEEP": "BEEP(note, duration): Plays a sound. 'note' can be Hz or string like 'C4'.",
    "OK": "OK(): Displays the signature 'OK'.",
    "HELP": "HELP(cmd): Shows this help message.",
}

_NOTE_MAP = {
    "C4": 262, "C#4": 277, "D4": 294, "D#4": 311, "E4": 330, "F4": 349,
    "F#4": 370, "G4": 392, "G#4": 415, "A4": 440, "B4": 494,
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

def OUT(pin, val=None):
    if val is not None:
        machine.Pin(pin, machine.Pin.OUT).value(1 if val else 0)

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

def OK():
    print("OK")
