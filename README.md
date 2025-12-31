# rp2040-ichigojam-python

RP2040 (Raspberry Pi Pico等) の MicroPython 環境で、IchigoJam BASIC の操作感を再現するための関数ライブラリです。

## 特徴
- **大文字関数形式**: `LED(1)`, `WAIT(60)` など IchigoJam ユーザーになじみ深い形式
- **PIOの活用**: シビアなタイミング制御 (WS2812B, BEEP等) に PIO を使用し、Python環境でも安定した動作を実現
- **最新機能の統合**: IoT (HTTPS/GAS連携), USBデバイス化, マルチコア対応など
- **自習支援**: `HELP()` や `PINS()` コマンドによる対話的な学習サポート

## ドキュメント
- [互換関数セット仕様案](docs/spec.md)
- [IchigoJam BASIC 1.5 リファレンス (日本語版)](docs/reference_jp.md)
- [実装計画書](docs/plan.md)

## 使い方 (予定)
`ichigojam.py` を Pico 等にコピーし、`from ichigojam import *` で開始します。
