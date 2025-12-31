# RP2040 Python版IchigoJam 互換関数セット仕様案

IchigoJam BASICのコマンドを、RP2040のMicroPython環境で「関数」として使いやすく再定義した仕様案です。

---

## 1. 制御構文の扱い（Python標準へ移行）

Pythonのリザーブドワード（予約語）と衝突するため、またPython本来の強力な構造化機能を活かすため、以下の構文はPython標準の書き方に置き換えます。

| IchigoJam (BASIC) | Python (MicroPython) | 備考 |
| :--- | :--- | :--- |
| `IF ... THEN ... ELSE` | `if ... : ... else:` | インデントによるブロック構造を利用 |
| `FOR I=1 TO 10 ... NEXT` | `for i in range(1, 11):` | 終了値が +1 必要になる点に注意 |
| `GOSUB 100` ... `RETURN` | `def func():` ... `func()` | 関数定義と呼び出しで構造化 |
| `END` | `sys.exit()` | または単にループを抜ける |

---

## 2. 互換関数セット (Basic I/O & System)

すべてのコマンドを大文字の関数 `FUNCTION()` 形式に統一します。

### ストレージ・ファイル
- **`SAVE(target)`** / **`LOAD(target)`**: 数値スロットまたはファイル名を指定可能。
- **`FILES()`**: 保存されているファイル名の一覧を表示・返す。

### ハードウェア制御
- **`LED(val)`**: `0`(消灯), `1`(点灯), `-1`(反転)
- **`WAIT(time, unit="frame")`**: 単位は `"frame"`, `"ms"`, `"sec"`
- **`OUT(pin, val=None)`**: PIOを動的に使用。単一ピンまたはビットバターン。
- **`IN(pin)`**: デジタル入力。戻り値は 0 または 1。
- **`BTN(callback=None)`**: イベント駆動（IRQ）に対応。
- **`ANA(pin, volt=False)`**: `volt=True` で電圧値を返す。
- **`PWM(pin, freq, duty)`**: PIOを使用して正確なパルスを生成。
- **`WS_LED(data, pin=25)`**: PIOでWS2812Bを駆動。

### 外部通信・メモリ
- **`I2CW(addr, data)`** / **`I2CR(addr, size)`**: 内部で I2C ポートを自動管理。
- **`UART(val)`**: ボーレート設定またはデータ送信。
- **`POKE(addr, val)`** / **`PEEK(addr)`**: 仮想メモリまたは直接操作。
- **`RND(a, b=None)`**: 範囲指定に対応。

### 画面・文字制御
- **`CLS()`** / **`LC(x, y)`** / **`OK()`**

### システム・マルチコア
- **`CORE2(func)`**: 第2コアで関数を並列実行。
- **`HELP(cmd=None)`**: 対話的なヘルプ表示。
- **`PINS()`**: ボード別のピン構成を表示。
- **`VERSION()`**: バージョン情報。
- **`FREE()`**: メモリ使用状況。
- **`TICK()`** / **`CLT()`**: ミリ秒タイマー。

### ネットワーク・IoT（Pico W / GAS連携）
- **`WIFI(ssid, password)`**
- **`IOT_GET(url)`** / **`IOT_POST(url, data)`**: HTTPSおよびリダイレクト対応。

### サウンド
- **`BEEP(note, duration=10)`**: PIOで正確な音程生成。音名文字列（`"C4"`等）対応。

---

## 3. 設計ポリシー

### エラーハンドリングポリシー

「寛容なエラー処理」を採用し、初心者が混乱しないよう配慮します。

1. **エラー表示**: コンソールにエラー内容を出力。
2. **警告通知**: LEDとBEEPで約15秒間警告（点滅＋警告音）。
3. **継続実行**: 致命的でない限り、警告後に次の処理へ。
