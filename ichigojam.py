import machine
import rp2
import utime
import sys

# --- PIO Resource Manager ---

class PIOManager:
    """PIO state machine and instruction memory manager."""
    def __init__(self):
        self.programs = {}  # program_name -> (offset, program)
        self.claimed_sm = [False] * 8
        self.pin_usage = {} # pin_num -> purpose_string
        
    def claim_sm(self):
        """Find and claim an empty state machine (0-7)."""
        for i in range(8):
            if not self.claimed_sm[i]:
                self.claimed_sm[i] = True
                return i
        return None

    def release_sm(self, sm_id):
        """Release a claimed state machine."""
        if 0 <= sm_id < 8:
            self.claimed_sm[sm_id] = False

    def load_program(self, pio_instance, program):
        """Load a PIO program if not already present in memory."""
        # Simple management: check if program is in the instance
        try:
            return pio_instance.add_program(program)
        except OSError:
            # Handle memory full or other errors
            return None

pio_manager = PIOManager()

# --- Error Handling ---

def _warn_error(msg):
    """BEEP and LED warning for 15 seconds, then continue."""
    print(f"ERROR: {msg}")
    led_pin = machine.Pin(25, machine.Pin.OUT) # System LED (Pico)
    # Note: BEEP is not yet implemented, will use PWM for now if needed
    start_time = utime.ticks_ms()
    while utime.ticks_diff(utime.ticks_ms(), start_time) < 15000:
        led_pin.value(1)
        utime.sleep_ms(100)
        led_pin.value(0)
        utime.sleep_ms(100)

# --- Basic I/O ---

def LED(val):
    """LED(val): 1=ON, 0=OFF, -1=Toggle."""
    try:
        pin = machine.Pin(25, machine.Pin.OUT) # Default Pico LED
        if val == -1:
            pin.value(not pin.value())
        else:
            pin.value(1 if val else 0)
    except Exception as e:
        _warn_error(f"LED: {e}")

def WAIT(time, unit="frame"):
    """WAIT(time, unit): Default 1/60s (frame)."""
    try:
        if unit == "frame":
            utime.sleep_ms(int(time * 1000 / 60))
        elif unit == "ms":
            utime.sleep_ms(time)
        elif unit == "sec":
            utime.sleep(time)
        else:
            raise ValueError("Unknown unit")
    except Exception as e:
        _warn_error(f"WAIT: {e}")

def IN(pin_num):
    """IN(pin): Digital input."""
    try:
        p = machine.Pin(pin_num, machine.Pin.IN, machine.Pin.PULL_UP)
        return p.value()
    except Exception as e:
        _warn_error(f"IN: {e}")
        return 0

def OUT(num1, num2=None):
    """OUT(pin, val) or OUT(bit_pattern)."""
    # Placeholder: Initial implementation uses standard Pin for single pin control
    # PIO integration will be added in Issue #1 later
    try:
        if num2 is not None:
            # Single pin mode
            p = machine.Pin(num1, machine.Pin.OUT)
            p.value(1 if num2 else 0)
        else:
            # Bit pattern mode (Simplify for v1.0 MVP)
            print(f"Info: OUT bit-pattern {num1} not yet fully PIO-driven.")
    except Exception as e:
        _warn_error(f"OUT: {e}")

def OK():
    """IchigoJam signature."""
    print("OK")

# Expose all functions to the user
__all__ = ['LED', 'WAIT', 'IN', 'OUT', 'OK', 'HELP', 'PINS']

# Placeholder for HELP/PINS (Issue #2)
def HELP(cmd=None):
    print("rp2040-ichigojam-python Library")
    print("Try HELP('LED') or HELP('OUT') for command details.")

def PINS():
    print("Pin usage information not yet available.")
