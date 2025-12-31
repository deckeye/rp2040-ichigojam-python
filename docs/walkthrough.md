# 実装完了：RP2040版IchigoJam Pythonライブラリ

IchigoJam BASICの操作感を継承しつつ、RP2040のパワーを最大限に引き出す Python ライブラリ `ichigojam.py` の実装を完了しました。

## 実装されたハイライト

### 1. ユーザビリティの革新
- **対話的ヘルプ**: 引数を忘れて実行しても、その場で使い方が表示されます。
- **REPL最適化**: `from ichigojam import *` で、すべての命令が即座に使用可能です。
- **親切なガイド**: 非対応ピンや競合ピンを指定した際、具体的に「どのピンが使えるか」を案内します。

### 2. ハードウェア制御 (PIO/DMA活用)
- **高精度 BEEP/PWM**: PIOによる安定した周波数生成。
- **一括出力 OUT**: 複数ピンのビットパターン制御。GPIO 1-6 を推奨値としました。
- **直感的なPWM停止**: `OUT(pin, 0)` または `PWM(pin, freq, 0)` で即座に停止可能。
- **WS2812B対応**: `WS_LED` 命令でフルカラーLEDを直感的に制御。

### 3. 高度な連携機能
- **IoT連携**: Google Apps Script (GAS) 等で多用される **HTTPSリダイレクト** に標準対応。
- **マルチコア**: `CORE2(func)` により、別コアでの並列処理を一行で開始。
- **ボード自動検知**: Pico, Pico W, XIAO を自動判別し、LED等の構成を最適化。

## リポジトリと成果物
- **GitHub**: [deckeye/rp2040-ichigojam-python](https://github.com/deckeye/rp2040-ichigojam-python)
- **ライブラリ本体**: `ichigojam.py`
- **マニュアル**: `docs/hardware_manual.md` にセットアップ手順と比較表を完備。
