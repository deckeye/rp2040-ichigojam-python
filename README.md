# 🍓 rp2040-ichigojam-python

RP2040 (Raspberry Pi Pico等) の MicroPython 環境で、**IchigoJam BASIC の直感的な操作感**を再現するための関数ライブラリです。

Python の強力な機能を利用しつつ、IchigoJam ユーザーが迷わず電子工作を始められる環境を提供します。

---

## 🚀 クイックスタート

`ichigojam.py` をボードに保存して、REPL またはスクリプトで以下を書き込むだけです。

```python
from ichigojam import *

# LEDを点滅させ、MMLを再生する
LED(1)
PLAY("CDE2 CDE2 GFEDC2$") # ループ再生対応
WAIT(120)
LED(0)
PLAY() # 停止

# 困ったらヘルプ！
HELP("OUT")    # OUTコマンドの使い方を表示
PINS()         # 今使っているボードのピン情報を表示

# グラフィックス（スプライト）やUSB HIDも標準で利用可能です
HELP("LCD_CONFIG")
```

### 液晶ディスプレイの接続と描画
外部ディスプレイを接続してスプライトを描画できます。

#### 1. モノクロ OLED (SSD1306 / I2C)
| IchigoJam P | SSD1306 | 説明 |
|:---:|:---:|:---|
| GP4 (SDA) | SDA | データ |
| GP5 (SCL) | SCL | クロック |
| 3V3 / GND | VCC/GND | 電源 |

```python
from ichigojam import *
from ssd1306 import SSD1306_I2C # 別途ドライバが必要

i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5))
oled = SSD1306_I2C(128, 64, i2c)

LCD_CONFIG(oled, 128, 64, mode="MONO")
SPRITE(1, [0x3C, 0x42, 0x95, 0xA1, 0xA1, 0x95, 0x42, 0x3C], 60, 30) # カオ
DRAW_BUFFER()
```

#### 2. カラー LCD (ST7789 / ATM0130B3 / SPI)
| IchigoJam P | ST7789 | 説明 |
|:---:|:---:|:---|
| GP18 (SCK) | SCL/SCK | クロック |
| GP19 (TX) | SDA/MOSI | データ |
| GP16 (DC) | DC/RS | コマンド/データ選択 |
| GP17 (CS) | CS | チップセレクト |
| GP20 (RES) | RES/RST | リセット |

```python
from ichigojam import *
import st7789 # 別途ドライバが必要

spi = machine.SPI(0, baudrate=40000000, sck=machine.Pin(18), mosi=machine.Pin(19))
tft = st7789.ST7789(spi, 240, 240, reset=machine.Pin(20), dc=machine.Pin(16))

LCD_CONFIG(tft, 240, 240, mode="COLOR")
SPRITE(2, [0xFF]*8, 100, 100, color=COLOR_RED)
DRAW_BUFFER()
```

---

## ✨ 主な特徴

- **IchigoJam 体験の再現**: `LED()`, `WAIT()`, `OUT()`, `ANA()` など、すべて大文字の関数で IchigoJam BASIC と同等の操作が可能です。
- **リソース管理の最適化**: `PIO (Programmable I/O)` を活用し、`BEEP`, `PWM`, `WS_LED` 等を実装。Python の処理に左右されない安定した信号を生成します。
- • 定数ベースの設計: マジックナンバーを排除し、 BAUD_9600 など可読性の高いコード記述をサポート。
  • MML再生エンジン: 標準の PLAY コマンドに加え、オブジェクト指向の MMLPlayer を使ったマルチトラック・ポリリズム演奏、音色変更 (@n) が可能です。
  • ボード自動検知: Pico, Pico W, XIAO RP2040 を自動判別し、LEDピンや I2Cピンを最適化します。
- **IoT 対応**: `IOT_GET` (HTTPSリダイレクト対応) や `WIFI()`、さらには `CORE2` によるマルチコア並列処理もサポート。
- **プラグイン不要の全機能統合**: USB HID エミュレーションやグラフィックスエンジンも本体に統合され、安定性と使いやすさが向上しました。

---

## 📋 対応ハードウェア

| ボード | 自動検知 | 特徴 |
|:---|:---:|:---|
| **Raspberry Pi Pico** | ✅ | 標準モデル。GPIO 26本。 |
| **Raspberry Pi Pico W** | ✅ | WiFi対応。`WIFI()` 命令や内部LEDを自動制御。 |
| **Seeed Studio XIAO RP2040** | ✅ | 超小型。RGB LED搭載。 |

---

## 📖 ドキュメント (日本語)

- **[ハードウェア別セットアップガイド](docs/hardware_manual.md)**: 始め方と機種ごとの違い。
- **[IchigoJam 総合リファレンス](docs/ichigojam_reference_jp.md)**: BASIC 互換コマンドの解説。
- **[Python版 仕様書](docs/rp2040_ichigojam_python_spec.md)**: 各機能の詳細な定義。
- **[開発の歩み (Walkthrough)](docs/walkthrough.md)**: フェーズごとの実装詳細。

---

## 🛠 今後のロードマップ

GitHub Issues を通じて管理しています： [GitHub Issues](https://github.com/deckeye/rp2040-ichigojam-python/issues)

- [x] マジックナンバーの定数化 (#18)
- [x] スタブ機能の分離 (#10)
- [x] PIOリソースのクリーンアップ機構 (#11)
- [ ] MML 再生エンジン (`PLAY` コマンド)
- [ ] 液晶ディスプレイでのスプライト描画の本格対応

---

## ⚖️ ライセンス

MIT License
