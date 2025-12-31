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

# 実験的機能（スプライト、USB HID等）を使いたい場合
from ichigojam_experimental import *
HELP_EXPERIMENTAL()
```

---

## ✨ 主な特徴

- **IchigoJam 体験の再現**: `LED()`, `WAIT()`, `OUT()`, `ANA()` など、すべて大文字の関数で IchigoJam BASIC と同等の操作が可能です。
- **リソース管理の最適化**: `PIO (Programmable I/O)` を活用し、`BEEP`, `PWM`, `WS_LED` 等を実装。Python の処理に左右されない安定した信号を生成します。
- • 定数ベースの設計: マジックナンバーを排除し、 BAUD_9600 など可読性の高いコード記述をサポート。
  • MML再生エンジン: 標準の PLAY コマンドに加え、オブジェクト指向の MMLPlayer を使ったマルチトラック・ポリリズム演奏、音色変更 (@n) が可能です。
  • ボード自動検知: Pico, Pico W, XIAO RP2040 を自動判別し、LEDピンや I2Cピンを最適化します。
- **IoT 対応**: `IOT_GET` (HTTPSリダイレクト対応) や `WIFI()`、さらには `CORE2` によるマルチコア並列処理もサポート。
- **実験的機能の分離**: 未実装のスタブや TinyUSB 依存の機能は `ichigojam_experimental.py` に隔離され、メインライブラリの安定性を保っています。

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
