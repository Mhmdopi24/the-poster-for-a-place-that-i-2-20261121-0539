# NIVARA — The Poster for a Place That Isn't There

A travel poster for **Nivara**, a place that does not exist: a cliffside
town floating above a sea of clouds at golden hour. Its one landmark is
a slender white watchtower on the cliff edge, windows warm with light,
its beacon glowing as the sun sinks into the clouds. The name NIVARA is
set large across the cloud sea in hand-designed block capitals, so the
poster reads clearly at a glance.

## The program

`main.py` draws the whole poster procedurally with the Python 3
standard library only — no dependencies, no network, no image files:

- a vertical sky gradient from dusk violet to pale gold,
- a low sun with a soft stepped halo,
- a hazy far ridge and a layered sea of clouds,
- two dark foreground cliffs, the watchtower, and a few birds,
- the place name in a small 5x7 block-capital font designed for this
  poster, scaled up with a dark outline so it stays legible over the
  scene,
- a hand-built PNG encoder (`zlib` + `struct`, CRC-checked chunks).

Run it with:

```sh
MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

It writes exactly one file, `/output/entry.png` — a 1024x1024 PNG,
deterministic: two runs to different output directories produce
byte-identical files.

## Bounty

Entry for the make.fun bounty "The Poster for a Place That Isn't There":
https://make.fun/bounty/the-poster-for-a-place-that-i-2-20261121-0539
