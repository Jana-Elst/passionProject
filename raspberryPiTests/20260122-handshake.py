import serial
import serial.tools.list_ports
import time

def find_arduinos():
    found_devices = {}
    # 1. Get a list of all available serial ports
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        # We only care about USB serial ports
        if "USB" in port.description or "ACM" in port.device:
            try:
                # 2. Open the serial connection
                # Note: Arduino resets when we open the port, so we must wait
                ser = serial.Serial(port.device, 9600, timeout=2)
                time.sleep(2) # Vital: Give Arduino time to reboot
                
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

# Example: How to use the map
if "MOTOR_CONTROLLER" in arduino_map:
    motor_port = arduino_map["MOTOR_CONTROLLER"]
    print(f"Connecting to Motors at {motor_port}...")
    # ser_motor = serial.Serial(motor_port, 9600)