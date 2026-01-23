import serial
import serial.tools.list_ports
import time

def find_arduinos():
    found_devices = {}

    # 1. Get a list of all available serial ports
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        if "USB" in port.description or "ACM" in port.device:
            try:
                # 2. Open the serial connection
                ser = serial.Serial(port.device, 9600, timeout=2)
                time.sleep(2) # Give Arduino time to reboot
                
                # 3. Send the Handshake command
                ser.write(b"IDENTIFY\n")
                
                # 4. Read the response
                response = ser.readline().decode('utf-8').strip()
                
                if response:
                    found_devices[response] = port.device
                    print(f"Found {response} on {port.device}")
                
                ser.close()
            except Exception as e:
                print(f"Could not connect to {port.device}: {e}")
                
    return found_devices

# Execute the search
arduino_map = find_arduinos()