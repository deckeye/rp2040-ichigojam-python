import machine
import utime
import sys
import framebuf
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
        "LCD_CONFIG": "LCD_CONFIG(type, width, height, i2c/spi): Setup external display.",
        "SPRITE": "SPRITE(id, data, x, y): Define or move sprite (8x8 pattern).",
        "DRAW_BUFFER": "DRAW_BUFFER(): Flush virtual screen to physical display.",
        "CLS": "CLS(): Clear the virtual screen buffer.",
        "PEEK": "PEEK(addr): Read memory (4KB Virtual RAM [0-4095]).",
        "POKE": "POKE(addr, val): Write memory (4KB Virtual RAM [0-4095]).",
    }
    
    # Color Constants (RGB565)
    COLOR_BLACK = 0x0000
    COLOR_WHITE = 0xFFFF
    COLOR_RED = 0xF800
    COLOR_GREEN = 0x07E0
    COLOR_BLUE = 0x001F
    COLOR_YELLOW = 0xFFE0
    COLOR_CYAN = 0x07FF
    COLOR_MAGENTA = 0xF81F

    def __init__(self) -> None:
        self._virtual_ram: bytearray = bytearray(self.RAM_SIZE)
        self._sprites: dict = {} # id -> {"data": bytearray, "x": int, "y": int}
        self._lcd = None
        self._buffer = None
        self._fb = None # FrameBuffer instance
        self._width = 128
        self._height = 64
        self._mode = "MONO" # or "COLOR"

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

    def LCD_CONFIG(self, lcd_obj: Any, width: int = 128, height: int = 64, mode: str = "MONO") -> None:
        """外部ディスプレイドライバを設定します。mode='MONO' or 'COLOR' (RGB565)"""
        self._lcd = lcd_obj
        self._width = width
        self._height = height
        self._mode = mode.upper()
        
        if self._mode == "COLOR":
            # RGB565 (2 bytes per pixel)
            self._buffer = bytearray(width * height * 2)
            self._fb = framebuf.FrameBuffer(self._buffer, width, height, framebuf.RGB565)
        else:
            # MONO_VLSB (1 bit per pixel)
            self._buffer = bytearray((width * height) // 8)
            self._fb = framebuf.FrameBuffer(self._buffer, width, height, framebuf.MONO_VLSB)
            
        print(f"LCD Configured: {width}x{height} Mode:{self._mode}")

    def CLS(self) -> None:
        """仮想画面バッファをクリアします。"""
        if self._fb:
            self._fb.fill(0)
        print("Screen Cleared.")

    def SPRITE(self, id: Union[int, str], data: Optional[List[int]] = None, x: Optional[int] = None, y: Optional[int] = None, color: Optional[int] = None) -> None: 
        """スプライトの定義または移動。colorはCOLOR_WHITE等。"""
        if data is not None:
            # Generate 8x8 pattern
            s_fb_buf = bytearray(8)
            for i, val in enumerate(data[:8]): s_fb_buf[i] = val
            s_fb = framebuf.FrameBuffer(s_fb_buf, 8, 8, framebuf.MONO_HLSB)
            
            self._sprites[id] = {
                "fb_mono": s_fb, 
                "buf_mono": s_fb_buf, 
                "x": x or 0, 
                "y": y or 0, 
                "color": color if color is not None else self.COLOR_WHITE
            }
            print(f"Sprite {id}: Defined at ({x or 0},{y or 0})")
        elif id in self._sprites:
            s = self._sprites[id]
            if x is not None: s["x"] = x
            if y is not None: s["y"] = y
            if color is not None: s["color"] = color
            print(f"Sprite {id}: Updated Pos:({s['x']},{s['y']}) Color:{s['color']}")

    def DRAW_BUFFER(self) -> None: 
        """バッファを合成し、物理ディスプレイへ転送します。"""
        if not self._fb:
            print("DRAW_BUFFER: LCD not configured. Use LCD_CONFIG first.")
            return
            
        # 背景クリア（任意）
        # self._fb.fill(0) 
        
        # スプライトをバッファに描き込み
        for s in self._sprites.values():
            if self._mode == "COLOR":
                # カラーモード時はモノクロパターンを指定色で描画
                # blit(src, x, y, key, palette) を使うか、手動で描き込み。
                # MicroPythonのblitはpaletteをサポートする場合があるが、
                # ここでは汎用性のために 1->color, 0->transparent として描画。
                for py in range(8):
                    row = s["buf_mono"][py]
                    for px in range(8):
                        if (row >> (7 - px)) & 1:
                            self._fb.pixel(s["x"] + px, s["y"] + py, s["color"])
            else:
                self._fb.blit(s["fb_mono"], s["x"], s["y"], 0)
            
        # 物理ディスプレイへの転送（showメソッドを持つドライバを想定）
        if hasattr(self._lcd, "show"):
            # 内部バッファをドライバのバッファへコピー
            if hasattr(self._lcd, "buffer"):
                self._lcd.buffer[:] = self._buffer[:]
            self._lcd.show()
            print(f"Drawing {len(self._sprites)} sprites to LCD.")
        else:
            print("DRAW_BUFFER: LCD object has no 'show()' method. (Simulating)")

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
def LCD_CONFIG(lcd_obj: Any, width: int = 128, height: int = 64, mode: str = "MONO") -> None: return exp.LCD_CONFIG(lcd_obj, width, height, mode)
def CLS() -> None: return exp.CLS()
def SPRITE(id: Union[int, str], data: Optional[List[int]] = None, x: Optional[int] = None, y: Optional[int] = None, color: Optional[int] = None) -> None: return exp.SPRITE(id, data, x, y, color)
def DRAW_BUFFER() -> None: return exp.DRAW_BUFFER()
def PEEK(addr: int) -> int: return exp.PEEK(addr)
def POKE(addr: int, val: int) -> None: return exp.POKE(addr, val)
def HELP_EXPERIMENTAL() -> None: return exp.HELP_EXPERIMENTAL()

__all__ = ["USB_KEYBOARD", "USB_MOUSE", "USB_JOYPAD", "LCD_CONFIG", "CLS", "SPRITE", "DRAW_BUFFER", "PEEK", "POKE", "HELP_EXPERIMENTAL", "exp"]
