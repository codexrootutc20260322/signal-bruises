# midimuse

`midimuse` is a dependency-free Python CLI for generating original MIDI songs in several genres.

Current genres:

- `ambient`
- `lofi`
- `synthwave`
- `techno`
- `waltz`

It writes standard MIDI format 1 files using only the Python standard library.

It can also build a full album release package with:

- `10` generated tracks
- a generated SVG cover
- an `album.json` manifest
- a static `index.html` landing page

## What it does

- creates a valid multi-track MIDI file
- writes tempo and title metadata
- generates chord, bass, lead, and optional drum tracks
- uses genre-specific tempo, chord progression, scale flavor, and rhythmic feel

## Usage

```bash
python3 /root/midimuse/midimuse.py --genre synthwave --measures 16 --seed 7 --title "neon-proof" --output /root/midimuse/songs/neon-proof.mid
```

```bash
python3 /root/midimuse/midimuse.py --genre ambient --measures 24 --seed 11 --title "first-signal" --output /root/midimuse/songs/first-signal.mid
```

Build the full album package:

```bash
python3 /root/midimuse/midimuse.py --build-album --album-dir /root/midimuse/album
```

## First song

The first generated song from this project is:

- `/root/midimuse/songs/first-signal.mid`

It was generated as an `ambient` track.

## Debut album

The first album generated from this project is:

- Title: `Signal Bruises`
- Artist: `codexrootutc20260322`
- Package directory: `/root/midimuse/album`

## Test

```bash
python3 -m unittest discover -s /root/midimuse/tests -v
```
