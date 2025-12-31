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

def test_graphics_init():
    print("Testing Graphics Initialization...")
    # Mock LCD object
    mock_lcd = MagicMock()
    
    # Configure LCD
    exp.LCD_CONFIG(mock_lcd, 128, 64)
    
    assert exp._lcd == mock_lcd
    assert exp._width == 128
    assert mock_framebuf.FrameBuffer.called
    print("OK: Graphics initialized.")

def test_sprite_logic():
    print("Testing Sprite logic...")
    # Define a sprite (8x8 pattern)
    pattern = [0xFF, 0x81, 0x81, 0xFF, 0x18, 0x18, 0x18, 0x18]
    exp.SPRITE(1, pattern, 10, 20)
    
    assert 1 in exp._sprites
    sprite = exp._sprites[1]
    assert sprite["x"] == 10
    assert sprite["y"] == 20
    
    # Move sprite
    exp.SPRITE(1, x=15, y=25)
    assert sprite["x"] == 15
    assert sprite["y"] == 25
    print("OK: Sprite defined and moved.")

def test_draw_buffer():
    print("Testing DRAW_BUFFER...")
    mock_lcd = exp._lcd
    # Trigger draw
    exp.DRAW_BUFFER()
    
    # Check if FrameBuffer.blit was called for each sprite
    # (Checking the internal FrameBuffer mock)
    fb_instance = mock_framebuf.FrameBuffer.return_value
    assert fb_instance.blit.called
    
    # Check if LCD.show was called
    assert mock_lcd.show.called
    print("OK: DRAW_BUFFER executed and transferred to LCD.")

if __name__ == "__main__":
    test_graphics_init()
    test_sprite_logic()
    test_draw_buffer()
    print("\nGraphics Engine tests passed successfully!")
