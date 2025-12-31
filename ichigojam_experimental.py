import machine
import utime
import sys
from typing import Optional, Union, Any, List, Tuple

# Try to import USB HID for actual keyboard/mouse emulation
try:
    import usb_hid
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.mouse import Mouse
    # from adafruit_hid.gamepad import Gamepad
    _HID_AVAILABLE = True
except ImportError:
    _HID_AVAILABLE = False

# Experimental Features for IchigoJam Python Library
class ExperimentalFeatures:
    """実験的機能（スプライト、仮想RAM、USB HID）を管理するクラス。"""
    
    RAM_SIZE = 4096
    
    HELP_DATA = {
        "USB_KEYBOARD": "USB_KEYBOARD(text): Emulate keyboard typing (Real if available).",
        "USB_MOUSE": "USB_MOUSE(x, y, click): Emulate mouse movement (Real if available).",
        "USB_JOYPAD": "USB_JOYPAD(buttons, axis_x, axis_y): Emulate gamepad (Stub).",
        "SPRITE": "SPRITE(id, data, x, y): Sprite drawing (Stub).",
        "DRAW_BUFFER": "DRAW_BUFFER(data): DMA buffer drawing (Stub).",
        "PEEK": "PEEK(addr): Read memory (4KB Virtual RAM [0-4095]).",
        "POKE": "POKE(addr, val): Write memory (4KB Virtual RAM [0-4095]).",
    }

    def __init__(self) -> None:
        self._virtual_ram: bytearray = bytearray(self.RAM_SIZE)
        self._sprite_buf: dict = {} # id -> (data, x, y)

    def USB_KEYBOARD(self, text: str) -> None: 
        """Emulate USB keyboard typing."""
        if _HID_AVAILABLE:
            try:
                kbd = Keyboard(usb_hid.devices)
                kbd.write(text)
                return
            except: pass
        print(f"USB Keyboard [SIM]: Typing '{text}'")

    def USB_MOUSE(self, x: int, y: int, click: int = 0) -> None: 
        """Emulate USB mouse movement."""
        if _HID_AVAILABLE:
            try:
                m = Mouse(usb_hid.devices)
                m.move(x=x, y=y)
                return
            except: pass
        print(f"USB Mouse [SIM]: Move({x},{y}) Click:{click}")

    def USB_JOYPAD(self, buttons: int, axis_x: int = 0, axis_y: int = 0) -> None: 
        """Emulate USB gamepad (stub)."""
        print(f"USB Joypad [HID]: Buttons:{bin(buttons)} Axes:({axis_x},{axis_y})")

    def SPRITE(self, id: Union[int, str], data: Optional[List[int]] = None, x: Optional[int] = None, y: Optional[int] = None) -> None: 
        """Sprite drawing and management (prototype)."""
        if data is not None:
            self._sprite_buf[id] = {"data": data, "x": x or 0, "y": y or 0}
            print(f"Sprite {id}: Data set, Pos:({x},{y})")
        elif id in self._sprite_buf:
            s = self._sprite_buf[id]
            if x is not None: s["x"] = x
            if y is not None: s["y"] = y
            print(f"Sprite {id}: Moved to ({s['x']},{s['y']})")

    def DRAW_BUFFER(self) -> None: 
        """Flush virtual buffer to display (stub)."""
        print(f"Drawing {len(self._sprite_buf)} sprites to screen...")

    def PEEK(self, addr: int) -> int:
        """Read from address (4KB Virtual RAM)."""
        if 0 <= addr < self.RAM_SIZE:
            return self._virtual_ram[addr]
        print(f"PEEK: Address {addr} out of range.")
        return 0

    def POKE(self, addr: int, val: int) -> None:
        """Write to address (4KB Virtual RAM)."""
        if 0 <= addr < self.RAM_SIZE:
            self._virtual_ram[addr] = val & 0xFF
        else:
            print(f"POKE: Address {addr} out of range.")

    def HELP_EXPERIMENTAL(self) -> None:
        """Show help for experimental commands."""
        print("Experimental Commands (Phase 3):")
        if not _HID_AVAILABLE:
            print("NOTE: USB HID hardware support not detected. Falling back to Simulation.")
        for cmd, desc in sorted(self.HELP_DATA.items()):
            print(f"{cmd}: {desc}")

# --- Global Instance and Wrappers ---
exp = ExperimentalFeatures()
RAM_SIZE = exp.RAM_SIZE

def USB_KEYBOARD(text: str) -> None: return exp.USB_KEYBOARD(text)
def USB_MOUSE(x: int, y: int, click: int = 0) -> None: return exp.USB_MOUSE(x, y, click)
def USB_JOYPAD(buttons: int, axis_x: int = 0, axis_y: int = 0) -> None: return exp.USB_JOYPAD(buttons, axis_x, axis_y)
def SPRITE(id: Union[int, str], data: Optional[List[int]] = None, x: Optional[int] = None, y: Optional[int] = None) -> None: return exp.SPRITE(id, data, x, y)
def DRAW_BUFFER() -> None: return exp.DRAW_BUFFER()
def PEEK(addr: int) -> int: return exp.PEEK(addr)
def POKE(addr: int, val: int) -> None: return exp.POKE(addr, val)
def HELP_EXPERIMENTAL() -> None: return exp.HELP_EXPERIMENTAL()

__all__ = ["USB_KEYBOARD", "USB_MOUSE", "USB_JOYPAD", "SPRITE", "DRAW_BUFFER", "PEEK", "POKE", "HELP_EXPERIMENTAL", "exp"]
