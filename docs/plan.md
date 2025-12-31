# 計画: RP2040 Python版IchigoJam互換ライブラリ

## 目的
IchigoJam BASICの直感的な操作感をRP2040（MicroPython）で再現する。

## 基本方針
1. **大文字関数に統一**: `LED(1)`, `OUT(1, 1)` 等
2. **PIOの動的活用**: `OUT`, `BEEP`, `PWM`, `WS_LED`, `I2C`, `UART`
3. **寛容なエラーハンドリング**: PRINT→LED+BEEP 15秒警告→処理継続

## 実装優先度

| 優先度 | 対象コマンド |
|:---|:---|
| **v1.0** | `LED`, `WAIT`, `OUT`, `IN`, `BEEP`, `HELP`, `PINS` |
| **v1.1** | `PWM`, `WS_LED`, `ANA`, `RND`, `BTN`, `SAVE`, `LOAD` |
| **v2.0+** | `CORE2`, `USB_*`, `SPRITE`, `IOT_*`, `WIFI` |

## 詳細仕様
→ [rp2040_ichigojam_python_spec.md](file:///C:/Users/user/.gemini/antigravity/brain/d51397c8-c5ac-490b-a9bc-eda09566bed7/rp2040_ichigojam_python_spec.md)
