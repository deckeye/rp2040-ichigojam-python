import unittest
from unittest.mock import MagicMock, patch
import sys

# Reset mocks to ensure clean state
for mod in ['machine', 'rp2', 'utime', 'network', 'usocket', 'ussl', '_thread', 'os']:
    sys.modules[mod] = MagicMock()

# Configure os.uname specifically before import
import os
os.uname.return_value.machine = "Raspberry Pi Pico"
os.listdir.return_value = []

# Import the class under test
from ichigojam import IchigoJam

class TestIchigoJam(unittest.TestCase):
    def setUp(self):
        # We need to re-mock inside setUp if needed, but the module-level mock should persist
        self.ij = IchigoJam()

    def test_led(self):
        import machine
        self.ij.LED(1)
        # Check if machine.Pin was called. 
        # Note: Depending on how machine is used, we might need to check internal state
        self.assertIsNotNone(self.ij._led_pin)
        self.ij._led_pin.value.assert_called_with(1)

    def test_wait_frame(self):
        import utime
        self.ij.WAIT(60) # 1 second in frames
        utime.sleep_ms.assert_called()
        args, _ = utime.sleep_ms.call_args
        self.assertGreaterEqual(args[0], 990)

    def test_rnd(self):
        val = self.ij.RND(10)
        self.assertLess(val, 10)
        self.assertGreaterEqual(val, 0)

    def test_io_validation(self):
        self.assertFalse(self.ij._validate_gpio(-1, "TEST"))
        self.assertFalse(self.ij._validate_gpio(30, "TEST"))
        self.assertTrue(self.ij._validate_gpio(15, "TEST"))

    def test_clt_tick(self):
        import utime
        utime.ticks_ms.return_value = 1000
        self.ij.CLT()
        self.assertEqual(self.ij._tick_offset, 1000)
        
        utime.ticks_ms.return_value = 1500
        self.assertEqual(self.ij.TICK(), 500)

    def test_pr_alias(self):
        # PR should be available and should call print (which we can't easily mock
        # without patching builtins, but we can check if it exists)
        self.assertTrue(has_pr := hasattr(self.ij, 'PR'))
        if has_pr:
            # Simple smoke test
            self.ij.PR("test")

if __name__ == '__main__':
    unittest.main()
