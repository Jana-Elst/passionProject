---
title: '#30 Debugging till the end'
description: |
    When you think you're done, you're not done yet.
pubDate: 'Feb 06 2026'
heroImage: ../../assets/pictures/20260206-header.png
---
## Adding all the different voicemail cases
The day started in peace. I just had to fix the logic of the voicemail and my code would be okay... but as I’ve learned: when you think you're done, you're not done yet.

## The hardware is failing... once again
Suddenly, my sound during the intercom stage was gone. I have no idea why, but while I was doing some measurements to find the problem, I broke my capacitor too. I had to quickly swap it out for a new one before I could even get back to the code.

Once the sound was back, I spent time adding some extra sounds, like beeping and dialing tones, and adjusting the pauses between prompts.

## The code is working! But not in real life.
Then I hit a really strange problem. My code worked perfectly when I triggered everything manually through the terminal, but not in "real life" with the phones. It turned out the Arduino was sending ghost signals. I realized the problem was happening during the intercom stage. When the phones are connected via the relay, the electrical circuit changes and the hook-state measurement isn't right anymore. To fix this, I had to change the logic on the Arduino:

- I made sure the Arduino only sends on-hook or off-hook messages to the Python script if the relay is closed.
- If one of the phones goes back on-hook while they are connected, the Arduino now handles closing the relay directly.

By doing this inside the Arduino code rather than waiting for the Python script to send a command back over Serial, the response is instant and the ghost signals disappeared.

## Start the script on boot
The very last step was making sure the project starts automatically. I created a shell script to launch the Python code as soon as the Raspberry Pi boots up, so the installation is completely standalone.

I found a really helpful guide for this here: <a href="https://www.instructables.com/Raspberry-Pi-Launch-Python-script-on-startup/" target="_blank">Raspberry Pi: Launch Python script on startup.</a>

## My code is working, maybe, and that is it.
Maybe my code is still a bit of a mess. Maybe it could be much cleaner, and the logic could be more elegant.

But after five weeks of breaking components, soldering, 2 AM debugging sessions, and wrestling with ghost signals, there is one thing that matters: It actually works!

<iframe src="https://www.instagram.com/reel/DUX4XXeCKLb/embed" width="400" height="710" frameborder="0" scrolling="no" allowtransparency="true" style="margin: 0 auto; display: block; max-width: 100%; border: none; padding: 32px 0"></iframe>