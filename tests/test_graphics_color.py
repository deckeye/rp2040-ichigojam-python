import sys
import os
from unittest.mock import MagicMock, patch

# パス追加
sys.path.append(os.getcwd())

# Mock MicroPython modules
mock_machine = MagicMock()
mock_framebuf = MagicMock()
mock_utime = MagicMock()

sys.modules["machine"] = mock_machine
sys.modules["framebuf"] = mock_framebuf
sys.modules["utime"] = mock_utime
sys.modules["usb_hid"] = MagicMock()

import ichigojam_experimental
from ichigojam_experimental import exp

def test_color_lcd_config():
    print("Testing Color LCD Config...")
    mock_lcd = MagicMock()
    exp.LCD_CONFIG(mock_lcd, 240, 240, mode="COLOR")
    
    assert exp._mode == "COLOR"
    assert len(exp._buffer) == 240 * 240 * 2
    print("OK: Color LCD configured.")

def test_color_sprite():
    print("Testing Color Sprite...")
    pattern = [0xFF]*8
    exp.SPRITE(100, pattern, 0, 0, color=exp.COLOR_RED)
    
    sprite = exp._sprites[100]
    assert sprite["color"] == exp.COLOR_RED
    print("OK: Sprite with color defined.")

def test_color_draw():
    print("Testing Color DRAW_BUFFER...")
    # Mock pixel call to track drawing
    fb_instance = mock_framebuf.FrameBuffer.return_value
    fb_instance.pixel.reset_mock()
    
    exp.DRAW_BUFFER()
    
    # In color mode, we use pixel() for sprite plotting
    assert fb_instance.pixel.called
    print("OK: Color DRAW_BUFFER used pixel() plotting.")

if __name__ == "__main__":
    test_color_lcd_config()
    test_color_sprite()
    test_color_draw()
    print("\nAll Graphics tests (Mono & Color) passed!")
