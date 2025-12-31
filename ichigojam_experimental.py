import machine
import utime
import sys

# Try to import USB HID for actual keyboard/mouse emulation
try:
    import usb_hid
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.mouse import Mouse
    # from adafruit_hid.gamepad import Gamepad
    _HID_AVAILABLE = True
except ImportError:
    _HID_AVAILABLE = False

# Experimental/Stub functions for IchigoJam Python Library
_experimental_help = {
    "USB_KEYBOARD": "USB_KEYBOARD(text): Emulate keyboard typing (Real if available).",
    "USB_MOUSE": "USB_MOUSE(x, y, click): Emulate mouse movement (Real if available).",
    "USB_JOYPAD": "USB_JOYPAD(buttons, axis_x, axis_y): Emulate gamepad (Stub).",
    "SPRITE": "SPRITE(id, data, x, y): Sprite drawing (Stub).",
    "DRAW_BUFFER": "DRAW_BUFFER(data): DMA buffer drawing (Stub).",
    "PEEK": "PEEK(addr): Read memory (4KB Virtual RAM [0-4095]).",
    "POKE": "POKE(addr, val): Write memory (4KB Virtual RAM [0-4095]).",
}

# --- Virtual RAM (4KB) ---
RAM_SIZE = 4096
_virtual_ram = bytearray(RAM_SIZE)
_sprite_buf = {} # id -> (data, x, y)

def USB_KEYBOARD(text): 
    """Emulate USB keyboard typing."""
    if _HID_AVAILABLE:
        try:
            kbd = Keyboard(usb_hid.devices)
            kbd.write(text)
            return
        except: pass
    print(f"USB Keyboard [SIM]: Typing '{text}'")

def USB_MOUSE(x, y, click=0): 
    """Emulate USB mouse movement."""
    if _HID_AVAILABLE:
        try:
            m = Mouse(usb_hid.devices)
            m.move(x=x, y=y)
            # click handling if needed
            return
        except: pass
    print(f"USB Mouse [SIM]: Move({x},{y}) Click:{click}")

def USB_JOYPAD(buttons, axis_x=0, axis_y=0): 
    """Emulate USB gamepad (stub)."""
    print(f"USB Joypad [HID]: Buttons:{bin(buttons)} Axes:({axis_x},{axis_y})")

def SPRITE(id, data=None, x=None, y=None): 
    """Sprite drawing and management (prototype)."""
    if data is not None:
        _sprite_buf[id] = {"data": data, "x": x or 0, "y": y or 0}
        print(f"Sprite {id}: Data set, Pos:({x},{y})")
    elif id in _sprite_buf:
        s = _sprite_buf[id]
        if x is not None: s["x"] = x
        if y is not None: s["y"] = y
        print(f"Sprite {id}: Moved to ({s['x']},{s['y']})")

def DRAW_BUFFER(): 
    """Flush virtual buffer to display (stub)."""
    print(f"Drawing {len(_sprite_buf)} sprites to screen...")

def PEEK(addr):
    """Read from address (4KB Virtual RAM)."""
    if 0 <= addr < RAM_SIZE:
        return _virtual_ram[addr]
    print(f"PEEK: Address {addr} out of range.")
    return 0

def POKE(addr, val):
    """Write to address (4KB Virtual RAM)."""
    if 0 <= addr < RAM_SIZE:
        _virtual_ram[addr] = val & 0xFF
    else:
        print(f"POKE: Address {addr} out of range.")

def HELP_EXPERIMENTAL():
    """Show help for experimental commands."""
    print("Experimental Commands (Phase 3):")
    if not _HID_AVAILABLE:
        print("NOTE: USB HID hardware support not detected. Falling back to Simulation.")
    for cmd, desc in sorted(_experimental_help.items()):
        print(f"{cmd}: {desc}")

__all__ = ["USB_KEYBOARD", "USB_MOUSE", "USB_JOYPAD", "SPRITE", "DRAW_BUFFER", "PEEK", "POKE", "HELP_EXPERIMENTAL"]
