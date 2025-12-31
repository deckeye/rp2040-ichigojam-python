# 🍓 rp2040-ichigojam-python

RP2040 (Raspberry Pi Pico等) の MicroPython 環境で、**IchigoJam BASIC の直感的な操作感**を再現するための関数ライブラリです。

Python の強力な機能を利用しつつ、IchigoJam ユーザーが迷わず電子工作を始められる環境を提供します。

---

## 🚀 クイックスタート

`ichigojam.py` をボードに保存して、REPL またはスクリプトで以下を打ち込むだけです。

```python
from ichigojam import *

# LEDを点滅させ、ドの音を鳴らす
LED(1)
BEEP(261, 30) # 261Hz(Do)を0.5秒
WAIT(60)       # 1秒待機
LED(0)

# 困ったらヘルプ！
HELP("OUT")    # OUTコマンドの使い方を表示
PINS()         # 今使っているボードのピン情報を表示
```

---

## ✨ 主な特徴

- **IchigoJam 体験の再現**: `LED()`, `WAIT()`, `OUT()`, `ANA()` など、すべて大文字の関数で IchigoJam BASIC と同等の操作が可能です。
- **PIO (Programmable I/O) 活用**: 高精度な `BEEP`, `PWM`, `WS_LED` 等の実装。Python の処理待ちに影響されない安定した信号を生成します。
- **親切なエラーガイド**: 非対応ピンや競合ピンを指定した際、単にエラーを出すのではなく「代わりにこのピンが使えます」といったガイドを表示します。
- **IoT / 高度な機能**: `IOT_GET` (HTTPSリダイレクト対応), `CORE2` (マルチコア並列処理), `USB_MOUSE` 等、最新の IchigoJam P の構想を先取りしています。

---

## 📋 対応ハードウェア

| ボード | 自動検知 | 特徴 |
|:---|:---:|:---|
| **Raspberry Pi Pico** | ✅ | 標準モデル。GPIO 26本すべて利用可能。 |
| **Raspberry Pi Pico W** | ✅ | WiFi対応。`WIFI()` 命令や内部LED制御を自動最適化。 |
| **Seeed Studio XIAO RP2040** | ✅ | 超小型。フルカラーLED (WS2812) 搭載。 |

---

## 📖 ドキュメント

プロジェクトの詳細は以下のドキュメントを参照してください。

- **[ハードウェア別セットアップ & 比較ガイド](docs/hardware_manual.md)**: 始め方と機種ごとの違い。
- **[IchigoJam 総合リファレンス](docs/ichigojam_reference_jp.md)**: BASIC 1.5 対応のコマンド・構文。
- **[Python版 互換関数セット仕様](docs/rp2040_ichigojam_python_spec.md)**: 設計思想と関数定義。
- **[プロジェクト完成報告 (Walkthrough)](docs/walkthrough.md)**: 実装のハイライトとデモ。

---

## 🛠 将来の展望 (Roadmap)

本プロジェクトは継続的な改善を計画しています。現在の課題や新機能の提案は [GitHub Issues](https://github.com/deckeye/rp2040-ichigojam-python/issues) をご覧ください。

- [ ] MML 再生エンジン (`PLAY` コマンド)
- [ ] USB HID (キーボード/ゲームパッド) の完全エミュレート
- [ ] 液晶ディスプレイでのスプライト描画

---

## ⚖️ ライセンス

MIT License
