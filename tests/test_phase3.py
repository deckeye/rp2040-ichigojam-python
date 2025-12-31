import sys
import os
from unittest.mock import MagicMock

# Add current directory to path
sys.path.append(os.getcwd())

# Mock MicroPython modules
mock_machine = MagicMock()
mock_rp2 = MagicMock()
mock_network = MagicMock()
mock_utime = MagicMock()
mock_socket = MagicMock()
mock_ssl = MagicMock()
mock_thread = MagicMock()

sys.modules["machine"] = mock_machine
sys.modules["rp2"] = mock_rp2
sys.modules["network"] = mock_network
sys.modules["utime"] = mock_utime
sys.modules["usocket"] = mock_socket
sys.modules["ussl"] = mock_ssl
sys.modules["_thread"] = mock_thread

# Now import the libraries
import ichigojam
import ichigojam_experimental

def test_constants():
    print("Testing Constants...")
    ij = ichigojam.ij
    assert ij.DEFAULT_BAUD == 115200
    assert ij.BAUD_MAP[5] == 31250
    assert ij.PIN_BUZZER_DEFAULT == 15
    print("OK: Constants verified.")

def test_uart_logic():
    print("Testing UART logic...")
    ij = ichigojam.ij
    # Set baud rate 7 (9600)
    ij.UART(7)
    mock_machine.UART.assert_called_with(0, baudrate=9600, tx=mock_machine.Pin(0), rx=mock_machine.Pin(1))
    
    # Send string
    ij.UART("Hello")
    ij._uart.write.assert_called_with("Hello")
    print("OK: UART logic verified.")

def test_virtual_ram():
    print("Testing Virtual RAM...")
    from ichigojam_experimental import PEEK, POKE, RAM_SIZE
    
    POKE(10, 123)
    assert PEEK(10) == 123
    
    POKE(4095, 255)
    assert PEEK(4095) == 255
    
    # Out of range
    POKE(5000, 10) # Should print error but not crash
    assert PEEK(5000) == 0
    print("OK: Virtual RAM verified.")

def test_usb_hid_stub():
    print("Testing USB HID stubs...")
    from ichigojam_experimental import USB_KEYBOARD, USB_MOUSE
    # Should just print unless HID is available (which it won't be in this mock)
    USB_KEYBOARD("Test")
    USB_MOUSE(10, 10)
    print("OK: USB HID stubs verified.")

if __name__ == "__main__":
    try:
        test_constants()
        test_uart_logic()
        test_virtual_ram()
        test_usb_hid_stub()
        print("\nAll Phase 3 tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
