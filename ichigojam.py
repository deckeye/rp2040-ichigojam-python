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
try:
    import framebuf
except ImportError:
    framebuf = None

# 実機でのキーボード/マウスエミュレーション用
try:
    import usb_hid
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.mouse import Mouse
    _HID_AVAILABLE = True
except ImportError:
    _HID_AVAILABLE = False

from typing import Optional, Union, Any, List, Tuple, Callable

# --- PIO Resource Manager ---

class PIOManager:
    """PIO状態マシンと命令メモリのマネージャー。"""
    def __init__(self):
        self._sm_used = [False] * 8
        self._programs = {} # (pio_idx, prog_name) -> offset (オフセット)
        
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
        """両方のPIOブロックをリセットし、プログラムキャッシュをクリアします。"""
        for pio_idx in [0, 1]:
            pio = rp2.PIO(pio_idx)
            # Remove all programs if possible
            for prog_id, offset in list(self._programs.items()):
                if prog_id[0] == pio_idx:
                    del self._programs[prog_id]
            # 状態マシンのリセット
            for i in range(4):
                pio.active(i, 0)
        self._sm_used = [False] * 8

# --- 内部定数とヘルパー ---

class _Required:
    def __repr__(self): return "<required>"
_REQ = _Required()

# --- 音声用のPIOプログラム ---

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def _beep_program():
    """標準の矩形波 (50% duty)"""
    pull(noblock)
    mov(x, osr)
    label("loop")
    nop()           .side(1) [1]
    mov(y, x)
    label("high")
    jmp(y_dec, "high")
    nop()           .side(0) [1]
    mov(y, x)
    label("low")
    jmp(y_dec, "low")
    jmp("loop")

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def _pulse_program():
    """パルス波 (12.5% duty)"""
    pull(noblock)
    mov(x, osr)
    label("loop")
    nop()           .side(1) [1]
    mov(y, x)
    label("high")
    jmp(y_dec, "high")
    
    # Lowタイム (Highの7倍) - 'z'レジスタを避けるためにアンロール
    nop()           .side(0) [1]
    mov(y, x); label("l1"); jmp(y_dec, "l1")
    mov(y, x); label("l2"); jmp(y_dec, "l2")
    mov(y, x); label("l3"); jmp(y_dec, "l3")
    mov(y, x); label("l4"); jmp(y_dec, "l4")
    mov(y, x); label("l5"); jmp(y_dec, "l5")
    mov(y, x); label("l6"); jmp(y_dec, "l6")
    mov(y, x); label("l7"); jmp(y_dec, "l7")
    jmp("loop")

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def _noise_program():
    """擬似ノイズ (簡易トグル版)"""
    pull(noblock)
    mov(x, osr)
    label("loop")
    # 高速にトグルし、xの値で周波数を制御
    nop()           .side(1)
    mov(y, x)
    label("n1")
    jmp(y_dec, "n1")
    nop()           .side(0)
    mov(y, x)
    label("n2")
    # わずかに長さを変えてノイズ感を出す
    nop()
    jmp(y_dec, "n2")
    jmp("loop")

@rp2.asm_pio(out_init=(rp2.PIO.OUT_LOW,) * 6, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def _out_program():
    pull()
    out(pins, 6)

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def _pwm_program():
    pull(noblock)
    mov(x, osr) # High期間
    pull(noblock)
    mov(y, osr) # Low期間
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
# --- 配置・定数 ---

# モジュールレベルでの利便性のためのエイリアス（実体は IchigoJam クラス内に定義されることを想定）
# しかし循環参照や初期化順序を考慮し、ここでは定数を定義し、クラスがそれを参照する形に整理。
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

# --- MML Engine (PLAY Command) ---

class MMLPlayer:
    """MML再生エンジン。独立したトラックとしての再生をサポート。"""
    
    def __init__(self, pio_mgr: PIOManager, pin: int):
        self.pio_mgr = pio_mgr
        self.pin = pin
        self.tempo = 120
        self.default_len = 4
        self.octave = 3
        self.instrument = 0 # 0: 矩形波, 1: パルス波, 2: ノイズ
        self._playing = False
        self._sm_id = -1
        self._sm = None
        self._current_mml = ""
        self._loop = False
        self._thread_lock = _thread.allocate_lock() # スレッド排他用

    def _get_freq(self, note: str, octave: int) -> int:
        base_map = {
            "C": 261.63, "C#": 277.18, "D": 293.66, "D#": 311.13, 
            "E": 329.63, "F": 349.23, "F#": 369.99, "G": 392.00, 
            "G#": 415.30, "A": 440.00, "A#": 466.16, "B": 493.88
        }
        if note not in base_map: return 0
        freq = base_map[note]
        # IchigoJamのオクターブ3が基準。倍数は 2^(octave-3)
        return int(freq * (2 ** (octave - 3)))

    def _play_note(self, freq: int, duration_ms: int):
        if freq <= 0:
            if self._sm: self._sm.active(0)
            utime.sleep_ms(duration_ms)
            return

        cycle_us = 1000000 // freq
        if self._sm_id < 0:
            self._sm_id = self.pio_mgr.get_sm()
            if self._sm_id < 0: return # 利用可能なSMがない
            
        # 楽器のマッピング
        prog = _beep_program if self.instrument == 0 else \
               _pulse_program if self.instrument == 1 else _noise_program
        
        # ロードと開始
        self.pio_mgr.load_program(self._sm_id, prog)
        self._sm = rp2.StateMachine(self._sm_id, prog, freq=2000000, sideset_base=machine.Pin(self.pin))
        self._sm.active(1)
        self._sm.put(cycle_us)
        utime.sleep_ms(duration_ms)

    def stop(self, wait: bool = False):
        self._playing = False
        if self._sm:
            try: self._sm.active(0)
            except: pass
        if wait:
            # スレッドが終了するのを待機（ロックが取得できる＝スレッド終了）
            self._thread_lock.acquire()
            self._thread_lock.release()
        
        if self._sm_id >= 0:
            self.pio_mgr.free_sm(self._sm_id)
            self._sm_id = -1
            self._sm = None

    def play(self, mml: str, loop: bool = False):
        """MMLを非同期（スレッド）で再生開始します。"""
        self.stop(wait=True) # 旧スレッドの終了を確実に待つ
        self._current_mml = mml.upper().replace(" ", "")
        self._playing = True
        self._loop = loop
        _thread.start_new_thread(self._playback_loop, ())

    def _playback_loop(self):
        with self._thread_lock:
            while self._playing:
            idx = 0
            while idx < len(self._current_mml) and self._playing:
                c = self._current_mml[idx]
                idx += 1
                
                if 'A' <= c <= 'G' or c == 'R':
                    # 音符または休符
                    note = c
                    if idx < len(self._current_mml) and (self._current_mml[idx] in "+#-"):
                        if self._current_mml[idx] in "+#": note += "#"
                        else: note += "-" # IchigoJamではシャープに '+' を使用
                        idx += 1
                    
                    # 長さ
                    num = ""
                    while idx < len(self._current_mml) and self._current_mml[idx].isdigit():
                        num += self._current_mml[idx]
                        idx += 1
                    length = int(num) if num else self.default_len
                    
                    # 付点
                    duration_factor = 1.0
                    if idx < len(self._current_mml) and self._current_mml[idx] == '.':
                        duration_factor = 1.5
                        idx += 1
                    
                    # 長さの計算
                    # テンポ 120 -> 1分 (60000ms) に120個の四分音符。
                    # 四分音符の長さ = 60000 / 120 = 500ms
                    # L4の長さ = (240000 * duration_factor) / (tempo * length)
                    duration_ms = int((240000 * duration_factor) / (self.tempo * length))
                    
                    if note == 'R':
                        self._play_note(0, duration_ms)
                    else:
                        self._play_note(self._get_freq(note, self.octave), duration_ms)
                
                elif c == 'O':
                    num = ""
                    while idx < len(self._current_mml) and self._current_mml[idx].isdigit():
                        num += self._current_mml[idx]
                        idx += 1
                    if num: self.octave = int(num)
                elif c == '<': self.octave += 1
                elif c == '>': self.octave -= 1
                elif c == 'T':
                    num = ""
                    while idx < len(self._current_mml) and self._current_mml[idx].isdigit():
                        num += self._current_mml[idx]
                        idx += 1
                    if num: self.tempo = int(num)
                elif c == 'L':
                    num = ""
                    while idx < len(self._current_mml) and self._current_mml[idx].isdigit():
                        num += self._current_mml[idx]
                        idx += 1
                    if num: self.default_len = int(num)
                elif c == '@':
                    num = ""
                    while idx < len(self._current_mml) and self._current_mml[idx].isdigit():
                        num += self._current_mml[idx]
                        idx += 1
                    if num: self.instrument = int(num)
                elif c == '$':
                    if not self._loop: break # ループ指定がない場合は終了
                elif c == '\'': break # 演奏終了
            
            if not self._loop: break
        self.stop()

# --- IchigoJam コアクラス ---

class IchigoJam:
    """RP2040用のIchigoJam互換レイヤー。"""
    # 一般的なGPIO割り当て
    # --- 設定定数 ---
    DEFAULT_BAUD = BAUD_115200
    WAIT_FRAME_MS = 16.6
    ERROR_BLINK_MS = 50
    ERROR_BLINK_COUNT = 6
    WIFI_TIMEOUT_SEC = 30
    
    # UARTボーレートマッピング (IchigoJam互換)
    BAUD_MAP = {
        1: BAUD_115200, 2: BAUD_115200, 3: BAUD_57600, 4: BAUD_38400, 
        5: BAUD_31250, 6: BAUD_19200, 7: BAUD_9600, 8: BAUD_4800, 9: BAUD_2400
    }
    
    # ヘルプデータ
    HELP_DATA = {
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
        "TICK": "TICK(): ミリ秒単位のティックカウントを取得。",
        "CLT": "CLT(): ティックカウントをリセット（擬似）。",
        "PR": "PR(*args): print() の別名。IchigoJam の '?' コマンドに相当。",
        "P": "P(*args): print() の短い別名。",
        "PLAY": "PLAY(mml, loop=False): MML(Music Macro Language)を再生。PLAY()で停止。",
        "USB_KEYBOARD": "USB_KEYBOARD(text): キーボード入力をエミュレート（利用可能な場合）。",
        "USB_MOUSE": "USB_MOUSE(x, y, click): マウス操作をエミュレート（利用可能な場合）。",
        "USB_JOYPAD": "USB_JOYPAD(buttons, axis_x, axis_y): ゲームパッドをエミュレート（スタブ）。",
        "LCD_CONFIG": "LCD_CONFIG(type, width, height, mode): 外部ディスプレイの設定。",
        "SPRITE": "SPRITE(id, data, x, y): スプライトの定義・移動（8x8パターン）。",
        "DRAW_BUFFER": "DRAW_BUFFER(): 仮想画面を物理ディスプレイに書き出し。",
        "PEEK": "PEEK(addr): メモリ読み出し (4KB 仮想RAM [0-4095])。",
        "POKE": "POKE(addr, val): メモリ書き込み (4KB 仮想RAM [0-4095])。",
    }

    # 音声定数とマップ
    NOTE_C4 = 262
    NOTE_D4 = 294
    NOTE_E4 = 330
    NOTE_F4 = 349
    NOTE_G4 = 392
    NOTE_A4 = 440
    NOTE_B4 = 494
    NOTE_C5 = 523
    
    NOTE_MAP = {
        "C4": NOTE_C4, "C#4": 277, "D4": NOTE_D4, "D#4": 311, "E4": NOTE_E4, "F4": NOTE_F4,
        "F#4": 370, "G4": NOTE_G4, "G#4": 415, "A4": NOTE_A4, "A#4": 466, "B4": NOTE_B4,
        "C5": NOTE_C5, "C#5": 554, "D5": 587, "D#5": 622, "E5": 659, "F5": 698,
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

    # デフォルトのGPIO構成
    PIN_BUZZER_DEFAULT = 15
    PIN_BUTTON_DEFAULT = 14
    PIN_LED_DEFAULT = 25
    PIN_I2C_SDA_PICO = 8
    PIN_I2C_SCL_PICO = 9
    PIN_I2C_SDA_XIAO = 4
    PIN_I2C_SCL_XIAO = 5

    def __init__(self):
        # ボード検出
        try:
            self.machine_name = os.uname().machine
        except:
            self.machine_name = "Mocked RP2040"
            
        self.IS_PICO_W = "Pico W" in self.machine_name
        self.IS_XIAO = "XIAO RP2040" in self.machine_name
        
        # ピン割り当て
        self.PIN_LED = "LED" if self.IS_PICO_W else self.PIN_LED_DEFAULT
        self.PIN_BUZZER = self.PIN_BUZZER_DEFAULT
        self.PIN_BUTTON = self.PIN_BUTTON_DEFAULT
        
        if self.IS_XIAO:
            self.PIN_SDA = self.PIN_I2C_SDA_XIAO
            self.PIN_SCL = self.PIN_I2C_SCL_XIAO
        else:
            self.PIN_SDA = self.PIN_I2C_SDA_PICO
            self.PIN_SCL = self.PIN_I2C_SCL_PICO
        
        # リソースマネージャー
        self.pio_mgr = PIOManager()
        self.mml_player = MMLPlayer(self.pio_mgr, self.PIN_BUZZER_DEFAULT)
        self._led_pin = None
        self._active_pwm = {}
        self._i2c = None
        self._uart: Optional[machine.UART] = None
        self._tick_offset: int = 0
        self.cert_validate: bool = False
        self.ca_file: Optional[str] = None
        
        # 実験的機能から統合されたプロパティ
        self.RAM_SIZE = 4096
        self._virtual_ram: bytearray = bytearray(self.RAM_SIZE)
        self._sprites: dict = {}
        self._lcd = None
        self._buffer = None
        self._fb = None
        self._width = 128
        self._height = 64
        self._graphics_mode = "MONO"
    
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
        print("IchigoJam システム: 終了しました。")

    def _warn_error(self, msg: str) -> None:
        """エラーを表示し、警告のためにLEDを点滅させます。"""
        print(f"エラー: {msg}")
        try:
            if self._led_pin is None:
                self._led_pin = machine.Pin(self.PIN_LED, machine.Pin.OUT)
            for _ in range(self.ERROR_BLINK_COUNT): 
                self._led_pin.value(1); utime.sleep_ms(self.ERROR_BLINK_MS)
                self._led_pin.value(0); utime.sleep_ms(self.ERROR_BLINK_MS)
        except: pass

    def _validate_gpio(self, pin: int, cmd: str) -> bool:
        if not isinstance(pin, int) or pin < 0 or pin > 29:
            self._warn_error(f"{cmd}: ピン {pin} は範囲外です。")
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
        except OSError as e: self._warn_error(f"LED ハードウェアエラー: {e}")
        except Exception as e: self._warn_error(f"LED エラー: {e}")

    def WAIT(self, time: int, unit: str = "frame") -> None:
        """指定された時間だけ待機します。"""
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
        except OSError as e: self._warn_error(f"OUT ハードウェアエラー: {e}")
        except ValueError as e: self._warn_error(f"OUT 値エラー: {e}")
        except Exception as e: self._warn_error(f"OUT エラー: {e}")

    def BEEP(self, note: Union[int, str] = 440, duration: int = 10) -> None:
        try:
            freq = self.NOTE_MAP.get(note, note) if isinstance(note, str) else note
            if freq <= 0: return
            cycle_us = 1000000 // freq
            sm.active(1); sm.put(cycle_us); utime.sleep_ms(duration * 16); sm.active(0)
            self.pio_mgr.free_sm(sm_id)
        except OSError as e: self._warn_error(f"BEEP ハードウェアエラー: {e}")
        except Exception as e: self._warn_error(f"BEEP エラー: {e}")

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
            with open(fn, "w") as f: f.write("# IchigoJamライブラリによって保存されました\n")
            print(f"{fn} に保存しました")
        except Exception as e: self._warn_error(f"SAVE エラー: {e}")

    def LOAD(self, target: Union[int, str]) -> str:
        try:
            fn = f"slot{target}.py" if isinstance(target, int) else target
            with open(fn, "r") as f: return f.read()
        except Exception as e: self._warn_error(f"LOAD エラー: {e}"); return ""

    def WIFI(self, ssid: str, password: str) -> None:
        """WiFiに接続します。"""
        try:
            if self.IS_PICO_W:
                wlan = network.WLAN(network.STA_IF)
                wlan.active(True)
                wlan.connect(ssid, password)
                print(f"{ssid} に接続中..."); timeout = self.WIFI_TIMEOUT_SEC
                while not wlan.isconnected() and timeout > 0: utime.sleep(1); timeout -= 1
                if wlan.isconnected(): print("接続完了:", wlan.ifconfig()[0])
                else: self._warn_error("WIFI: 接続タイムアウト")
        except OSError as e: self._warn_error(f"WIFI ハードウェアエラー: {e}")
        except Exception as e: self._warn_error(f"WIFI エラー: {e}")

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
        """I2C書き込み。成功時に1、失敗時に0を返します。"""
        try:
            if isinstance(data, int): data = bytes([data])
            elif isinstance(data, list): data = bytes(data)
            self._get_i2c().writeto(addr, data)
            return 1
        except Exception as e:
            self._warn_error(f"I2CW: {e}")
            return 0

    def I2CR(self, addr: int, size: int) -> list:
        """I2C読み込み。バイトリストを返します。失敗時は空リストを返します。"""
        try:
            return list(self._get_i2c().readfrom(addr, size))
        except Exception as e:
            self._warn_error(f"I2CR: {e}")
            return []

    def UART(self, val: Union[int, str, bytes]) -> None:
        """ボーレートを設定するかデータを送信します。val=1-9: ボーレートに写像、val>=300: 直接指定、str/bytes: 送信。"""
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
        print(f"空き: {f}, 使用中: {a}, 合計: {f+a}"); return f

    def FILES(self) -> None:
        for f in os.listdir(): print(f)

    def HELP(self, cmd: Optional[str] = None) -> None:
        if cmd: print(self.HELP_DATA.get(cmd.upper(), "不明なコマンドです。"))
        else: print("利用可能なコマンド: " + ", ".join(sorted(self.HELP_DATA.keys())))

    def PLAY(self, mml: str = "", loop: bool = False) -> None:
        """MML (Music Macro Language) を再生します。停止するには PLAY() を使用します。"""
        if not mml:
            self.mml_player.stop()
        else:
            # IchigoJam では $ がループ指定
            if "$" in mml: loop = True
            self.mml_player.play(mml, loop)

    # --- 実験的機能から統合されたメソッド ---

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
        """外部ディスプレイドライバを設定します。mode='MONO' または 'COLOR' (RGB565)"""
        self._lcd = lcd_obj
        self._width = width
        self._height = height
        self._graphics_mode = mode.upper()
        
        if self._graphics_mode == "COLOR" and framebuf:
            # RGB565 (1ピクセルあたり2バイト)
            self._buffer = bytearray(width * height * 2)
            self._fb = framebuf.FrameBuffer(self._buffer, width, height, framebuf.RGB565)
        elif framebuf:
            # MONO_VLSB (1ピクセルあたり1ビット)
            self._buffer = bytearray((width * height) // 8)
            self._fb = framebuf.FrameBuffer(self._buffer, width, height, framebuf.MONO_VLSB)
            
        print(f"LCD 設定完了: {width}x{height} モード:{self._graphics_mode}")

    def SPRITE(self, id: Union[int, str], data: Optional[List[int]] = None, x: Optional[int] = None, y: Optional[int] = None, color: Optional[int] = None) -> None: 
        """スプライトの定義または移動。colorはCOLOR_WHITE等。"""
        if data is not None:
            # 8x8パターン生成 (モノクロ)
            s_fb_buf = bytearray(8)
            for i, val in enumerate(data[:8]): s_fb_buf[i] = val
            s_fb_mono = framebuf.FrameBuffer(s_fb_buf, 8, 8, framebuf.MONO_HLSB) if framebuf else None
            
            # カラーパターン (RGB565 キャッシュ)
            s_fb_color = None
            if self._graphics_mode == "COLOR" and framebuf:
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
                if self._graphics_mode == "COLOR" and framebuf:
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
            print("DRAW_BUFFER: 液晶が設定されていません。先に LCD_CONFIG を使用してください。")
            return
            
        # スプライトをバッファに描き込み
        for s in self._sprites.values():
            if self._graphics_mode == "COLOR":
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

    def PINS(self) -> None:
        print(f"ボード: {self.machine_name}")
        print(f"I/O構成: LED={self.PIN_LED}, ブザー={self.PIN_BUZZER}, ボタン={self.PIN_BUTTON}")
        print(f"通信設定: I2C(SCL:{self.PIN_SCL}, SDA:{self.PIN_SDA}), UART(TX:0, RX:1)")

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
                        print("警告: cert_validate が True ですが、ca_file が指定されていません。ホストのみの検証を続行します。")
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
        """IoT通信のセキュリティ設定を行います。"""
        if cert_validate is not None:
            self.cert_validate = cert_validate
            print(f"IoT 証明書検証: {'有効化' if cert_validate else '無効化'}")
        if ca_file is not None:
            self.ca_file = ca_file
            print(f"CA証明書ファイルをセットしました: {ca_file}")

    def IOT_GET(self, url: str) -> Optional[str]: 
        """HTTP GETリクエストを送信します。"""
        return self._iot_request("GET", url)

    def IOT_POST(self, url: str, data: Union[str, dict]) -> Optional[str]: 
        """HTTP POSTリクエストを送信します。"""
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
def PLAY(mml: str = "", loop: bool = False) -> None: ij.PLAY(mml, loop)
def USB_KEYBOARD(text: str): return ij.USB_KEYBOARD(text)
def USB_MOUSE(x: int, y: int, click: int = 0): return ij.USB_MOUSE(x, y, click)
def USB_JOYPAD(buttons: int, axis_x: int = 0, axis_y: int = 0): return ij.USB_JOYPAD(buttons, axis_x, axis_y)
def LCD_CONFIG(lcd_obj: Any, width: int = 128, height: int = 64, mode: str = "MONO"): return ij.LCD_CONFIG(lcd_obj, width, height, mode)
def SPRITE(id, data=None, x=None, y=None, color=None): return ij.SPRITE(id, data, x, y, color)
def DRAW_BUFFER(): return ij.DRAW_BUFFER()
def PEEK(addr: int): return ij.PEEK(addr)
def POKE(addr: int, val: int): return ij.POKE(addr, val)
def PINS(): return ij.PINS()
def VERSION(): return "IchigoJam Python v2.1 (クラスベース版)"
def OK(): print("OK")
def IOT_CONFIG(cert_validate: bool = None): return ij.IOT_CONFIG(cert_validate)
def PR(*args, **kwargs): return ij.PR(*args, **kwargs)
def P(*args, **kwargs): return ij.P(*args, **kwargs)

__all__ = ["LED", "WAIT", "IN", "OUT", "BEEP", "ANA", "PWM", "WS_LED", "RND", "BTN", "SAVE", "LOAD", 
           "WIFI", "IOT_GET", "IOT_POST", "IOT_CONFIG", "CORE2", 
           "I2CW", "I2CR", "UART", "FILES", "FREE", "TICK", "CLT", "VERSION",
           "CLS", "LC", "HELP", "PINS", "OK", "PR", "P", "ij",
           "USB_KEYBOARD", "USB_MOUSE", "USB_JOYPAD", "LCD_CONFIG", "SPRITE", "DRAW_BUFFER", "PEEK", "POKE",
           "BAUD_115200", "BAUD_57600", "BAUD_38400", "BAUD_31250", "BAUD_19200", "BAUD_9600", "BAUD_4800", "BAUD_2400",
           "NOTE_C4", "NOTE_D4", "NOTE_E4", "NOTE_F4", "NOTE_G4", "NOTE_A4", "NOTE_B4", "NOTE_C5"]
