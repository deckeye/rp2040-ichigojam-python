# RP2040 Python版IchigoJam 互換関数セット仕様案

IchigoJam BASICのコマンドを、RP2040のMicroPython環境で「関数」として使いやすく再定義した仕様案です。

---

## 1. 制御構文の扱い（Python標準へ移行）

Pythonのリザーブドワード（予約語）と衝突するため、またPython本来の強力な構造化機能を活かすため、以下の構文はPython標準の書き方に置き換えます。

| IchigoJam (BASIC) | Python (MicroPython) | 備考 |
| :--- | :--- | :--- |
| `IF ... THEN ... ELSE` | `if ... : ... else:` | インデントによるブロック構造を利用 |
| `FOR I=1 TO 10 ... NEXT` | `for i in range(1, 11):` | 終了値が +1 必要になる点に注意 |
| `GOTO 10` | (関数呼出 または 制御構文) | Pythonに `goto` は存在しません |
| `GOSUB 100` ... `RETURN` | `def func():` ... `func()` | 関数定義と呼び出しで構造化 |
| `END` | `sys.exit()` | または単にループを抜ける |

---

## 2. 互換関数セット (Basic I/O & System)

すべてのコマンドを大文字の関数 `FUNCTION()` 形式に統一します。

### ストレージ・ファイル
- **`SAVE(target)`** / **`LOAD(target)`**: 数値スロットまたはファイル名を指定可能。
- **`FILES()`**: 保存されているファイル名の一覧を返す。

### ハードウェア制御
- **`LED(val)`**: `0`(消灯), `1`(点灯), `-1`(反転)
- **`WAIT(time, unit="frame")`**: 単位は `"frame"`, `"ms"`, `"sec"`
- **`OUT(num1, num2=None)`**: PIOを動的に使用。マルチピンの一括操作をサポート。
- **`IN(pin)`**: デジタル入力。戻り値は 0 または 1。
- **`BTN(id=None, callback=None)`**: イベント駆動（IRQ）に対応。
- **`ANA(pin, volt=False)`**: `volt=True` で電圧値を返す。
- **`PWM(pin, freq, duty, pulse=None)`**: PIOを使用して正確なパルスを生成。
- **`PULSIN(pin, state)`**: PIOを使用してパルス幅を計測。
- **`WS_LED(data, pin=LED_PIN, order="RGB", brightness=1.0)`**: PIOでWS2812Bを駆動。

### 外部通信・メモリ
- **`I2CW(addr, data, scl=None, sda=None)`** / **`I2CR(addr, size, ...)`**: PIOでI2Cを駆動。
- **`UART(baudrate, tx=None, rx=None)`**: PIOでUARTを実装。
- **`POKE(addr, data)`** / **`PEEK(addr, size=1)`**: バルク書き込み対応。
- **`RND(a, b=None)`**: 範囲指定（例: `RND(1, 7)`）に対応。

### 画面・文字制御
- **`CLS()`** / **`LC(x, y)`** / **`PUTC(code)`**
- **`SPRITE(id, data, x, y)`**: PIO/DMAによる高速描画を想定。

### システム・マルチコア
- **`CORE2(func)`**: 第2コアで関数を並列実行。
- **`OK()`**: 実行成功後に `OK` を表示（演出用）。
- **`HELP(cmd=None)`**: 引数なしでコマンド一覧、引数ありでその詳細を表示。
- **`PINS()`**: 各ピンの現在の役割（機能割り当て）を一覧表示。
- **`TEMP()`**: RP2040内蔵温度計の摂氏温度を返す。
- **`DRAW_BUFFER(data)`**: DMAを活用した一括高速描画。

### 周辺機器・USB
- **`USB_KEYBOARD(text)`**: キー入力をエミュレート。
- **`USB_MOUSE(x, y, click=0)`**: マウス操作（移動・クリック）をエミュレート。
- **`USB_JOYPAD(buttons, axis_x=0, axis_y=0)`**: ゲームパッド入力をエミュレート。

### ネットワーク・IoT（Pico W / GAS連携）
- **`WIFI(ssid, password)`**
- **`IOT_GET(url)`** / **`IOT_POST(url, data)`**: HTTPSおよびリダイレクトに完全対応。
- **`HTTP_GET(url)`**: リダイレクト追従なしの高速版。

### サウンド
- **`BEEP(note, duration=10)`**: PIOで正確な音程生成。音名文字列（`"C4"`等）対応。
- **`PLAY(mml_string, loop=False)`**: バックグラウンド再生。

---

## 3. 設計ポリシー

### コマンドの実装優先度

| 優先度 | 対象コマンド |
|:---|:---|
| **v1.0 (必須)** | `LED`, `WAIT`, `OUT`, `IN`, `BEEP`, `HELP`, `PINS` |
| **v1.1 (推奨)** | `PWM`, `WS_LED`, `ANA`, `RND`, `BTN`, `SAVE`, `LOAD` |
| **v2.0+ (将来)** | `CORE2`, `USB_*`, `SPRITE`, `IOT_*`, `WIFI` |

### エラーハンドリングポリシー

「寛容なエラー処理」を採用し、初心者が混乱しないよう配慮します。

1. **エラー検出時**: `PRINT` でエラー内容を画面に表示。
2. **ユーザーへの通知**: LEDとBEEPで約15秒間警告（点滅＋警告音）。
3. **処理継続**: エラーを無視して次の处理へ進む。

これにより、プログラムが途中で止まらず、誰が見ても「何かおかしい」とわかる状態になります。

### 命名の一貫性

- HTTP通信は `IOT_GET` / `IOT_POST` に統一。
- `HTTP_GET` は廃止予定（`IOT_GET(url, follow=False)` で代替）。

---

## 4. 数値・文字列・データの扱い（Pythonの活用）

- **変数**: 1文字制限なし。
- **型**: 浮動小数点数が標準で可能。
- **リスト/辞書**: Python標準の `list`, `dict` を活用。
- **JSON処理**: Python標準の `json.loads()` / `json.dumps()` を推奨。

---

## 5. 特殊表記の対応

- **16進数**: `0xFF` (Python標準)
- **2進数**: `0b1111` (Python標準)

---

## 6. PIOリソース管理と競合回避

- **SMの動的管理**: 空いているSM (0〜7) を自動割り当て・解放。
- **命令メモリの共有**: 同一プログラムをSM間で共有。
- **ピン専有検知**: 競合を検知して警告。
- **フォールバック**: リソース不足時は標準GPIO処理へ切り替え。

---

## 7. 設計上の課題

- **ピン番号のマッピング**: GPIO番号と IchigoJam の論理番号の対応。
- **非同期処理**: `asyncio` を用いた `PLAY()` や `IOT` コマンドの実装検討。
