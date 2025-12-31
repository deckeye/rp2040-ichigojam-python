import sys
import os
from unittest.mock import MagicMock, patch

# パス追加
sys.path.append(os.getcwd())

# Mock MicroPython modules
mock_machine = MagicMock()
mock_rp2 = MagicMock()
mock_utime = MagicMock()

sys.modules["machine"] = mock_machine
sys.modules["rp2"] = mock_rp2
sys.modules["utime"] = mock_utime
sys.modules["network"] = MagicMock()
sys.modules["usocket"] = MagicMock()
sys.modules["ussl"] = MagicMock()
sys.modules["_thread"] = MagicMock()

import ichigojam
from ichigojam import ij

def test_led_logic():
    print("Testing LED logic...")
    # Reset mock
    mock_machine.Pin.reset_mock()
    
    ij.LED(1)
    # Pin(25, Pin.OUT) が呼ばれ、value(1) が呼ばれるはず
    mock_machine.Pin.assert_any_call(ij.PIN_LED, mock_machine.Pin.OUT)
    ij._led_pin.value.assert_called_with(1)
    
    ij.LED(0)
    ij._led_pin.value.assert_called_with(0)
    print("OK: LED logic verified.")

def test_in_logic():
    print("Testing IN logic...")
    mock_machine.Pin.reset_mock()
    
    # Mock return value
    mock_pin_instance = MagicMock()
    mock_pin_instance.value.return_value = 1
    mock_machine.Pin.return_value = mock_pin_instance
    
    val = ij.IN(10)
    mock_machine.Pin.assert_called_with(10, mock_machine.Pin.IN, mock_machine.Pin.PULL_UP)
    assert val == 1
    print("OK: IN logic verified.")

def test_pwm_logic():
    print("Testing PWM logic...")
    # PWM(pin=2, freq=1000, duty=0.5)
    # SM周波数は1MHz。1000Hz周期は1000us。50%なら high=500, low=500
    ij.PWM(2, 1000, 0.5)
    
    # StateMachineの初期化確認
    mock_rp2.StateMachine.assert_called()
    args, kwargs = mock_rp2.StateMachine.call_args
    assert kwargs['freq'] == 1000000
    
    # put() に渡される値の確認 (high_us, low_us)
    # 一番最近のSM取得
    sm_instance = ij._active_pwm[2][1]
    sm_instance.put.assert_any_call(500)
    
    # 停止テスト
    ij.PWM(2, 1000, 0)
    sm_instance.active.assert_called_with(0)
    assert 2 not in ij._active_pwm
    print("OK: PWM logic verified.")

def test_ana_logic():
    print("Testing ANA logic...")
    mock_machine.ADC.reset_mock()
    mock_adc_instance = MagicMock()
    mock_adc_instance.read_u16.return_value = 32768 # 50% (read_u16 is 0-65535)
    mock_machine.ADC.return_value = mock_adc_instance
    
    # 32768 >> 6 = 512
    val = ij.ANA(26)
    mock_machine.ADC.assert_called_with(26)
    assert val == 512
    
    # 電圧モード (512 / 1023 * 3.3 = 1.65)
    volt = ij.ANA(26, volt=True)
    assert 1.6 < volt < 1.7
    print("OK: ANA logic verified.")

def test_deinit_logic():
    print("Testing System Deinit...")
    # 前のテストで残ったPWMを停止
    ij.PWM(3, 1000, 0.5)
    sm_instance = ij._active_pwm[3][1]
    
    ij.deinit()
    sm_instance.active.assert_called_with(0)
    assert len(ij._active_pwm) == 0
    print("OK: Deinit logic verified.")

if __name__ == "__main__":
    try:
        test_led_logic()
        test_in_logic()
        test_pwm_logic()
        test_ana_logic()
        test_deinit_logic()
        print("\nCore function tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
