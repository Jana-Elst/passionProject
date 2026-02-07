# (Dis)connect
> **"Sometimes we need to downgrade our technology to upgrade our connections."** >

(Dis)connect is an interactive installation created for a 5-week passion project. It uses two vintage rotary phones to facilitate a private, 2-minute conversation between two strangers in separate spaces.

[Read the full process on my blog →](https://www.janaelst.be/passionProject)

## The Concept
This installation aims to break the "smartphone bubble" by using obsolete technology to facilitate meaningful micro-interactions.

- **The Interaction:**<br> Two rotary phones are placed in different locations.

- **The Trigger:**<br> When a user dials a number on either phone, the other phone begins to ring.

- **The Connection:**<br> Once picked up, a voice-over icebreaker introduces a prompt, allowing two strangers to share a private, unrecorded 2-minute moment.

## Directories
- **arduino:** Hardware source code. Organized into iterative scripts that showcase the project's evolution and various prototyping stages.
- **blog:** Source files for the project documentation website.

## Tech Stack
- **Hardware:**
    - 2 Vintage Rotary Phones
    - Arduino
- **Software:**
    - C++ (Arduino)
    - HTML/CSS (Blog)

## Branches
- **main:** stable, exhibition-ready code
- **dev:** active experimentation
- **arduino**: the process of my arduino code
- **blog**: the process of my blog

## Planning
### Week 1 (5 - 11 jan)
**How does the telephone work? Create a basis setup.**
- ~~Are the phones working~~
- ~~How can I call with it~~
- ~~Are the bells working~~
- ~~Can I connect the two phones~~
- ~~Can I send music from an arduino to the phone(s)~~

### Week 2 (12 - 18 jan)
**Make the final hardware setup**
- Create a user flow. -> Tuesday
- ~~Sound & talking circuit -> Tuesday~~
    - ~~Is the whole sound circuit working?~~
    - ~~Check what's wrong if two sounds are playing at the same time.~~
    - ~~Where is the noise coming from during the talking status?~~
- Check if the phone is off hook. -> Tuesday/Wednesday
- Voice mails -> Wednesday
    - Can I make a voice mail?
    - Can I play a voice mail?
- ~~The dail -> Thursday~~
    - ~~How does it work?~~
    - ~~Detect which number is dialed~~
- The bells -> Friday
    - Connect them to the circuit
    - Let  the bells ring at the right moments

### Week 3 (19 - 25 jan)
**Write the software**
- calculate the voltages, voltages spikes, and current in the whole circuit
- ~~write the whole arduino logic (Pro micro)~~
- ~~write the basic python code~~
- ~~add the dial to the circuit~~
- ~~detect on/off hook~~
- connect the bells
- write code to record a voice mail
- ~~find a workflow between the pi, and the code~~

### Week 4 (26 - 1 feb)
**Scenografie + test the installation**
- ~~wirte the whole python logic (Monday)~~
- ~~debug the python logic (Tuesday)~~
  - ~~test if its working on the Pi~~
  - create detailed scripts
  - ~~send instructions to the arduino to open & close the relais at the right moments~~
- ~~add relais for the bell to the circuit~~
    - ~~write extra arduino code~~
-~~change sound system to the usbcards (instead of the arduino) (Wednesday)~~

- Make a nice scenografie
- Test the installation

- ~~Solder everything together~~

- add extra's
  - setup system
    - add option to record new questions
    - language?
    - ...

### Week 5 (2 - 8 feb)
**Create presentation + final touches**
- Create a presentation
- Final touches

### Week 6 (9 - 15 feb)
**Presentation**
- Create a presentation






