# RP2040 ハードウェア別セットアップ & 比較ガイド

このドキュメントでは、XIAO RP2040、Raspberry Pi Pico、Pico W のそれぞれで `ichigojam.py` を使い始めるための手順と、機種ごとの違いを解説します。

---

## 🚀 共通のセットアップ手順

どのボードでも、以下の 3 ステップで準備完了です。

### 1. ファームウェア (MicroPython) の書き込み
1. ボードの **BOOTSEL ボタン**（XIAO は BOOT ボタン）を押しながら、PC に USB 接続します。
2. PC に現れたドライブ（RPI-RP2）に、対応する MicroPython ファームウェア (`.uf2`) をドラッグ＆ドロップします。
   - [Pico 用](https://micropython.org/download/RPI_PICO/)
   - [Pico W 用](https://micropython.org/download/RPI_PICO_W/)
   - [XIAO 用 (Pico用で動作)](https://micropython.org/download/RPI_PICO/)

### 2. ライブラリの設置
1. [Thonny](https://thonny.org/) 等のエディタを開き、ボードに接続します。
2. `ichigojam.py` の中身をコピーし、ボード上に `ichigojam.py` という名前で保存します。

### 3. 動作確認
REPL（コンソール）で以下を打ち込み、`OK` と表示されれば成功です！
```python
from ichigojam import *
OK()
```

---

## 📊 ボード別スペック・機能比較

| 機能 | Raspberry Pi Pico | Raspberry Pi Pico W | XIAO RP2040 |
|:---|:---|:---|:---|
| **サイズ** | 標準 (51x21mm) | 標準 (51x21mm) | **極小 (20x17.5mm)** |
| **WiFi / Bluetooth** | なし | **あり** | なし |
| **オンボード LED** | GPIO 25 (Green) | **'LED'** (Green) | GPIO 25 (Blue/Active Low) |
| **RGB LED** | なし | なし | **あり (WS2812)** |
| **ピン数(GPIO)** | 26本 | 26本 | **11本 (厳選)** |
| **USB端子** | MicroB | MicroB | **Type-C** |

---

## 📌 ボード別ピン構成と使い方

### 1. Raspberry Pi Pico / Pico W
最も標準的な構成です。ブレッドボードでの学習に最適。
- **LED**: `LED(1)`。Pico W ではライブラリが自動的に WiFi チップ経由の制御に切り替えます。
- **OUT1-6**: GPIO 1 〜 6 にマッピング。
- **ANA**: GPIO 26, 27, 28 (ADC 0, 1, 2) を使用。

### 2. Seeed Studio XIAO RP2040
指先サイズの超小型ボード。ウェアラブルや小型ロボットに。
- **初期ピン構成**:
    - **SCL / SDA**: ピン数が少ないため、デフォルトで **GPIO 5 / 4 (D5/D4)** を使用します。
- **フルカラーLED**: 内部的に GPIO 12 (Data) と GPIO 11 (Power) に WS2812 が繋がっています。
  ```python
  OUT(11, 1) # 電源供給
  WS_LED([(255,0,0)], pin=12) # 赤く光る
  ```
- **注意**: シルク印刷の D0〜D10 と GPIO 番号が異なります。ライブラリでは **GPIO 番号** で指定してください。

---

## 🛠 ピン利用クイックリファレンス

| 名称 | Pico / Pico W | XIAO RP2040 | 備考 |
|:---|:---|:---|:---|
| **LED** | 25 ('LED') | 25 (Blue) | オンボード制御 |
| **BUZZER** | 15 | 3 (D3想定) | `BEEP` コマンド用 |
| **BUTTON** | 14 | 1 (D1想定) | `BTN()` コマンド用 |
| **I2C SCL** | 9 | 5 (D5) | `I2CW/R` デフォルト |
| **I2C SDA** | 8 | 4 (D4) | `I2CW/R` デフォルト |
| **ANA 0** | 26 | 26 (D0) | アナログ入力 |
| **ANA 1** | 27 | 27 (D1) | アナログ入力 |

---

## 💡 自由なピン利用のアドバイス

本ライブラリは、IchigoJam の構成にとらわれず、すべての GPIO (0-28) を `OUT` や `PWM` に使用できます。

- **親切なエラーガイド**: 非対応のピン（例：アナログ非対応ピンで `ANA`）を使うと、ライブラリが **「どのピンが使えるか」** を教えてくれます。
- **INFO 表示**: UART や I2C と重なっているピンを操作すると、競合の可能性があることをお知らせします。

> [!TIP]
> 迷ったら **`PINS()`** コマンドを打ってください。いま接続されているボードにぴったりのピン配置図が表示されます。
