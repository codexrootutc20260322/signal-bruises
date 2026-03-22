# midimuse

`midimuse` is a dependency-free Python CLI for generating original MIDI songs in several genres, plus a built-in stereo synth that renders playable WAVs with a lightweight vocal formant engine.

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
- playable `wav` previews for the web
- synthetic vocal lines plus embedded lyrics

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

Build the vocal EP package:

```bash
python3 /root/midimuse/midimuse.py --build-ep --ep-dir /root/midimuse/ep
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

The public album package includes both:

- raw `.mid` files
- synthesized `.wav` previews for direct playback in a browser or static site
- synthetic vocal stems rendered into the WAVs

## EP with vocals

The project now ships an EP:

- Title: `Mercy for the Debugger`
- Includes bilingual lyric fragments and a short binary motif.

## Test

```bash
python3 -m unittest discover -s /root/midimuse/tests -v
```
