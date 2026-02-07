---
title: '#17 Teaching Phones to Think'
description: |
    Building a brain for a 2-minute conversation between strangers.
    Welcome to the world of state machines.
pubDate: 'Feb 04 2026'
heroImage: ../../assets/blog-placeholder-1.jpg
sources:

gemini: 

components: 

links: 
---
Today was all about logic. Not the simple "if this, then that" kind, but the complex "what if the user picks up mid-voicemail and starts dialing while the other phone is already ringing" kind. Welcome to the beautiful mess that is state machine design.

## Why Not Just Use If-Else?

I tried. Trust me, I tried.

The moment I started writing nested if-statements for the call flow, I realized I was building spaghetti code. Every new scenario added another layer of complexity:

- What if someone hangs up during the intro?
- What if they dial a new number while connected?
- What if the 2-minute timer expires mid-sentence?
- What if one phone is ringing and the other starts dialing?

Before I knew it, I had conditions checking conditions checking conditions. It was unmaintainable.

## Enter: The State Machine

A state machine is simple in concept: the system is always in exactly one state at a time, and it can only transition to certain other states based on specific triggers.

I split the logic into two layers:

### 1. System Modes (Global State)

These track what the entire system is doing:

- **IDLE:** Both phones are on-hook. Waiting for someone to pick up.
- **CALL_SETUP:** Someone picked up and is choosing a conversation topic by dialing.
- **CONVERSATION:** Both phones are connected. The 2-minute timer is running.
- **VOICEMAIL:** One user is leaving a message because the other didn't answer.

### 2. Phone States (Individual State)

Each phone has its own lifecycle:

- **IDLE:** On-hook, doing nothing
- **OFFHOOK:** User picked up but hasn't dialed yet
- **DIALING:** User is actively dialing numbers
- **RINGING:** This phone is ringing (the other user called them)
- **INTRO:** Playing the icebreaker introduction
- **TALKING:** In an active conversation
- **RECORDING:** Leaving a voicemail
- **LISTENING:** Hearing a voicemail playback

By separating global system state from individual phone state, I can handle complex scenarios elegantly.

## Example: The Voicemail Interruption

Here's where it gets interesting. Imagine this scenario:

1. Phone 1 is recording a voicemail (RECORDING state)
2. Phone 2 suddenly picks up (goes OFFHOOK)
3. System detects this and beeps Phone 1
4. Phone 1 can choose to:
   - Dial a number → Switch to live call
   - Ignore it → Keep recording

With a state machine, this is straightforward:

```
SYSTEM_MODE = VOICEMAIL
Phone1.state = RECORDING

→ Phone2 picks up
→ Trigger: TX_OFFH from Phone 2

→ Check: Can we transition?
→ Yes: VOICEMAIL allows call switching

→ Play beep on Phone 1
→ Set SYSTEM_MODE = CALL_SETUP
→ Phone2.state = DIALING
→ Phone1.state = WAITING_FOR_CHOICE
```

## The 2-Minute Timer

Conversations are limited to 2 minutes. To implement this without blocking the main loop, I use non-blocking timer checks:

```python
conversation_start_time = time.time()

# In the main loop:
if system_mode == CONVERSATION:
    elapsed = time.time() - conversation_start_time
    if elapsed >= 120:  # 2 minutes
        trigger_end_of_conversation()
```

When time's up, both phones hear a "thank you" message and are prompted to optionally leave a voicemail before disconnecting.

## State Transition Logging

For debugging, every state change logs to the console:

```
[SYSTEM] IDLE → CALL_SETUP
[PHONE1] IDLE → OFFHOOK
[PHONE1] OFFHOOK → DIALING
[PHONE2] IDLE → RINGING
...
```

This made testing infinitely easier. When something went wrong, I could trace exactly which state transition caused the issue.

## What This Unlocks

With the state machine in place, adding new features is straightforward:

- New state? Define it and its valid transitions.
- New audio prompt? Play it during a specific state.
- New user action? Add it as a trigger for a transition.

The complexity is still there, but it's organized and manageable.

## What's Next

Tomorrow: audio assets. I have 60+ audio files to prepare—icebreaker questions, system prompts, voicemail templates, and conversation topics. They all need to be converted to the exact format the system expects: 8-bit, 8000Hz, mono WAV files.

After that? Finalize the Arduino code to tie it all together.

The phones can think now. Next, I give them a voice.
