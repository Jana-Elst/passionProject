---
title: '#29 Change the logic of my code'
description: |
    How should I handle all the different cases?
    I have to deal with if-else structures again...
pubDate: 'Feb 05 2026'
heroImage: ../../assets/pictures/20260205-header.png
---
I had basic code, but after making the different flows, I realized that there were so many cases I hadn't even thought of yet. I started to implement them, but after a day of (trying to) get them all working, my code and my brain became a total mess. Again, I was dealing with a lot of messy, nested if-else structures, the kind of "spaghetti code" that breaks the moment you touch it.

What if someone hangs up during the intro? What if they dial a number while the other phone is already ringing? My code just couldn't handle that complexity.

## Taking a break always works
And then, it was once again proven that taking a break works! I stepped away for an evening to go to a workshop and experiment with TouchDesigner. After getting my first image to work in TouchDesigner, I came back with a fresh perspective and a realization: those if-else structures had to go.

<div class="image-center">

![](../../assets/pictures/20260205-touchdesigner-exp.png)

</div>

## A new approach
Together with AI, I designed a whole new logic to handle all the different cases. Instead of just swapping between variables in a giant list, I started using Classes.

This template:
```python
class State(ABC):
    def __init__(self, context):
        self.context = context

    def on_enter(self):
        """Run setup tasks (start timers, play audio)"""
        pass

    def on_exit(self):
        """Run cleanup tasks (stop timers, stop audio)"""
        pass

    # Events return the NEXT State, or None to stay.
    def on_offhook(self, phone): return None
    def on_onhook(self, phone): return None
    def on_dial(self, phone, number): return None
    def on_timeout(self, timer_name): return None

    def handle_onhook_during_setup_conversation(self, phone):
        """Standard handling for interruptions during connection phases."""
        if phone == self.context.sender:
            self.context.sender.stop_audio()

            # Roles switch
            self.context.sender, self.context.receiver = self.context.receiver, self.context.sender
            return DialingState(self.context, intro_file_key="interruption_sender_hangup")

        elif phone == self.context.receiver:
            self.context.receiver.stop_audio()
            return RingingState(self.context, intro_file_key="interruption_receiver_hangup")
        return None
```
In each state class, different actions can happen. Depending on whether it's an on_offhook or on_timeout, I can now easily define which state should follow. Writing new cases and handling interruptions became way easier!

Instead of hunting through a giant list of "if" statements, I just tell the specific Class how to react to that event. It makes the code way more organized and "smarter." And writing new cases became much easier!


