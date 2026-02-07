#T1 = Telephone 1
#T2 = Telephone 2
#OFFH = Off Hook
#ONH = On Hook
#N0X = Number 01, 02, 03, etc.

import time

def play_sound(track_number, phone_label):
    print(f"--- PLAYING SOUND {track_number} ON {phone_label} ---")
    # Later, you will use a library like pygame or vlc to actually play audio

def main():
    print("System Starting...")
    
    while True: #listen for input for ever, the program don't quit
        # This replaces the Arduino Serial data for now
        command = input("\nArduino Signal: ").strip().lower()

        if command == "quit":
            break

        # Identify Phone
        phone_label = "Unknown Phone"
        command_body = command
        
        if command.startswith("t1"):
            phone_label = "Phone 1"
            command_body = command[2:]
        elif command.startswith("t2"):
            phone_label = "Phone 2"
            command_body = command[2:]

        # Process Command
        if command_body == "offh":
            print(f"Action: {phone_label} lifted!")

            # If the first phone is lifted, play the intro sound
            play_sound('intro', phone_label)

            #first phone dials number

            #when the first phone has dialed a number, play the ring sound on the other phone
            #plays a wait tone on the offHook phone

            #if someone answers on the other phone, play the questionReceiver on the recieverPhone and questionSender on the senderPhone
            
        elif command_body == "onh":
            print(f"Action: {phone_label} hung up.")
            # Stop sounds or reset state here
        
        elif command_body.startswith("n"):
            # format: N01, N02, etc. (lowercased to n01)
            # We take the integer value of the part after 'n' to handle N01 -> 1
            try:
                number_part = command_body[1:]
                digit = int(number_part) # This handles '01' -> 1
                print(f"Action: {phone_label} dialed Number {digit}.")
                play_sound(f"question {digit}", phone_label)
            except ValueError:
                 print(f"Action: Invalid number format '{command}'.")
            
        else:
            print(f"Unknown signal '{command}'.")

if __name__ == "__main__":
    main()