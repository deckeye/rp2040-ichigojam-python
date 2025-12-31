from ichigojam import *
import utime

def hardware_self_test():
    ij = IchigoJam()
    print("--- IchigoJam Python Hardware Self-Test ---")
    
    # LED Test
    print("Testing LED: Blinking 3 times...")
    for _ in range(3):
        ij.LED(1); utime.sleep_ms(200)
        ij.LED(0); utime.sleep_ms(200)
    
    # BEEP Test
    print("Testing BEEP: Playing C-E-G...")
    ij.BEEP("C4", 10)
    ij.WAIT(10)
    ij.BEEP("E4", 10)
    ij.WAIT(10)
    ij.BEEP("G4", 10)
    ij.WAIT(30)
    
    # MML Test
    print("Testing MML (PLAY): CDE...")
    ij.PLAY("CDE")
    ij.WAIT(120)
    
    # Button Test
    print("Testing Button: Please press the BOOTSEL/User button (GP24/GP20 based on board).")
    print("Waiting for button press (timeout 5s)...")
    start = utime.ticks_ms()
    pressed = False
    while utime.ticks_diff(utime.ticks_ms(), start) < 5000:
        if ij.BTN():
            print("Button Pressed! OK.")
            pressed = True
            break
        utime.sleep_ms(50)
    if not pressed:
        print("Button test timed out.")

    print("--- Test Finished ---")
    ij.deinit()

if __name__ == "__main__":
    hardware_self_test()
