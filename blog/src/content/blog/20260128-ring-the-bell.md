---
title: '#23 Ring the bell'
description: |
    Today i burned my transformator...
pubDate: 'Jan 28 2026'
heroImage: ../../assets/notes/20260120-circuit8-1.png
sources:

gemini: 

components: 

links: 
---
# The search for the right cable
Today I spended some time to find the right cable to connect my aux screw pin with my sound card. Because twe aux screws where not fitting together in the sound card. But after buying a male to female aux cable, I faced exactly the same problem then before...
At the end by removing some rubber, I was able to connect both the in and out at the same moment!

# Let's try to ring the bell
My whole DC circuit is working, my whole code for this part is working. So the only thing that I proposed to do was to connect the AC circuit togheter with the DC circuit.
After adding the double-sided relays and some new wiring and ... staring at what I did wrong (I forgot to connect the GND). My NC circuit, where the DC is flowing trough worked again!

And also by opening the relays, by phone started to ring!

And then suddenly, my transformator burned...

## A burned transformator, what did I do wrong?
What I really did wrong, I genually don't know. Suddendly nothing was wroking anymore and my transformator was really really hot... Since I don't want to let it happen again with a new transformator, I started to try to find what i did wrong.

### 1. was my DC connected to the AC?
Since only my transfomator was burned and nothing else this seemed as not a logical answer. If this would happen, my arduino probably died.

### 2. did I make a short circuit?
This could be possible since somethings weren't working. So maybe i made per ongeluk a short circuit

### 3. A big inductive spike?
Since I'm using relays close by the transformator and open and closed them. They can create some inductive spikes.

### 4. I just was asking for to much current.
But I think the most logical answer is that I just was asking for to much current. Both my AC circuits and my DC circuit was connected to the same transformator output.