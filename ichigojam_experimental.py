import machine
import utime
import sys
try:
    import framebuf
except ImportError:
    framebuf = None
from typing import Optional, Union, Any, List, Tuple

# 実機でのキーボード/マウスエミュレーション用
try:
    import usb_hid
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.mouse import Mouse
    # from adafruit_hid.gamepad import Gamepad
    _HID_AVAILABLE = True
except ImportError:
    _HID_AVAILABLE = False

# IchigoJam Python ライブラリ用 実験的機能
class ExperimentalFeatures:
    """実験的機能（スプライト、仮想RAM、USB HID）を管理するクラス。"""
    
    RAM_SIZE = 4096
    
    HELP_DATA = {
        "USB_KEYBOARD": "USB_KEYBOARD(text): キーボード入力をエミュレート（利用可能な場合）。",
        "USB_MOUSE": "USB_MOUSE(x, y, click): マウス操作をエミュレート（利用可能な場合）。",
        "USB_JOYPAD": "USB_JOYPAD(buttons, axis_x, axis_y): ゲームパッドをエミュレート（スタブ）。",
        "LCD_CONFIG": "LCD_CONFIG(type, width, height, i2c/spi): 外部ディスプレイの設定。",
        "SPRITE": "SPRITE(id, data, x, y): スプライトの定義・移動（8x8パターン）。",
        "DRAW_BUFFER": "DRAW_BUFFER(): 仮想画面を物理ディスプレイに書き出し。",
        "CLS": "CLS(): 仮想画面バッファをクリア。",
        "PEEK": "PEEK(addr): メモリ読み出し (4KB 仮想RAM [0-4095])。",
        "POKE": "POKE(addr, val): メモリ書き込み (4KB 仮想RAM [0-4095])。",
    }
    
    # カラー定数 (RGB565)
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
        self._fb = None # FrameBuffer インスタンス
        self._width = 128
        self._height = 64
        self._mode = "MONO" # または "COLOR"

    def USB_KEYBOARD(self, text: str) -> None: 
        """USBキーボード入力をエミュレートします。"""
        if _HID_AVAILABLE:
            try:
                kbd = Keyboard(usb_hid.devices)
                kbd.write(text)
                return
            except: pass
        print(f"USB キーボード [シミュレーション]: '{text}' を入力中")

    def USB_MOUSE(self, x: int, y: int, click: int = 0) -> None: 
        """USBマウス操作をエミュレートします。"""
        if _HID_AVAILABLE:
            try:
                m = Mouse(usb_hid.devices)
                m.move(x=x, y=y)
                return
            except: pass
        print(f"USB マウス [シミュレーション]: 移動({x},{y}) クリック:{click}")

    def USB_JOYPAD(self, buttons: int, axis_x: int = 0, axis_y: int = 0) -> None: 
        """USBゲームパッドのエミュレーション（スタブ）。"""
        print(f"USB ジョイパッド [HID]: ボタン:{bin(buttons)} 軸:({axis_x},{axis_y})")

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
            
        print(f"LCD 設定完了: {width}x{height} モード:{self._mode}")

    def CLS(self) -> None:
        """仮想画面バッファをクリアします。"""
        if self._fb:
            self._fb.fill(0)
        print("仮想画面をクリアしました。")

    def SPRITE(self, id: Union[int, str], data: Optional[List[int]] = None, x: Optional[int] = None, y: Optional[int] = None, color: Optional[int] = None) -> None: 
        """スプライトの定義または移動。colorはCOLOR_WHITE等。"""
        if data is not None:
            # 8x8パターン生成 (モノクロ)
            s_fb_buf = bytearray(8)
            for i, val in enumerate(data[:8]): s_fb_buf[i] = val
            s_fb_mono = framebuf.FrameBuffer(s_fb_buf, 8, 8, framebuf.MONO_HLSB) if framebuf else None
            
            # カラーパターン (RGB565 キャッシュ)
            s_fb_color = None
            if self._mode == "COLOR" and framebuf:
                c_buf = bytearray(8 * 8 * 2)
                c_fb = framebuf.FrameBuffer(c_buf, 8, 8, framebuf.RGB565)
                c_color = color if color is not None else self.COLOR_WHITE
                # 事前レンダリング
                for py in range(8):
                    row = s_fb_buf[py]
                    for px in range(8):
                        if (row >> (7 - px)) & 1:
                            c_fb.pixel(px, py, c_color)
                s_fb_color = c_fb
            
            self._sprites[id] = {
                "fb_mono": s_fb_mono, 
                "fb_color": s_fb_color,
                "buf_mono": s_fb_buf, 
                "x": x or 0, 
                "y": y or 0, 
                "color": color if color is not None else self.COLOR_WHITE
            }
            print(f"スプライト {id}: ({x or 0},{y or 0}) に定義されました")
        elif id in self._sprites:
            s = self._sprites[id]
            if x is not None: s["x"] = x
            if y is not None: s["y"] = y
            if color is not None:
                s["color"] = color
                # 色が変更された場合、カラーキャッシュを再描画
                if self._mode == "COLOR" and framebuf:
                    c_buf = bytearray(8 * 8 * 2)
                    c_fb = framebuf.FrameBuffer(c_buf, 8, 8, framebuf.RGB565)
                    for py in range(8):
                        row = s["buf_mono"][py]
                        for px in range(8):
                            if (row >> (7 - px)) & 1:
                                c_fb.pixel(px, py, color)
                    s["fb_color"] = c_fb
            print(f"スプライト {id}: 位置更新:({s['x']},{s['y']}) 色:{s['color']}")

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
                if s["fb_color"]:
                    self._fb.blit(s["fb_color"], s["x"], s["y"], 0) # 透明色 0 を使用
                else:
                    # フォールバック (低速)
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
            print(f"{len(self._sprites)} 個のスプライトを液晶に描画しました。")
        else:
            print("DRAW_BUFFER: 液晶オブジェクトに 'show()' メソッドがありません。(シミュレーション中)")

    def PEEK(self, addr: int) -> int:
        """指定したアドレスから読み出します (4KB 仮想RAM)。"""
        if 0 <= addr < self.RAM_SIZE:
            return self._virtual_ram[addr]
        print(f"PEEK: アドレス {addr} が範囲外です。")
        return 0

    def POKE(self, addr: int, val: int) -> None:
        """指定したアドレスに書き込みます (4KB 仮想RAM)。"""
        if 0 <= addr < self.RAM_SIZE:
            self._virtual_ram[addr] = val & 0xFF
        else:
            print(f"POKE: アドレス {addr} が範囲外です。")

    def HELP_EXPERIMENTAL(self) -> None:
        """実験的機能のヘルプを表示します。"""
        print("実験的コマンド (Phase 3):")
        if not _HID_AVAILABLE:
            print("注意: USB HID ハードウェアサポートが検出されませんでした。シミュレーションにフォールバックします。")
        for cmd, desc in sorted(self.HELP_DATA.items()):
            print(f"{cmd}: {desc}")

# --- グローバルインスタンスとラッパー ---
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
