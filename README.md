# Interval Trainer

An ear-training tool for intervals from a minor 2nd up to an octave. You pick an
interval, and the program keeps playing it on random root notes until you stop it
or pick another one.

Each round plays:

1. the low note
2. the high note
3. both notes together, three times, with a short pause between each
4. the high note
5. the low note

The low note is chosen at random between C2 and C6 (middle C ± 2 octaves) and is
never the same twice in a row.

## Requirements

- macOS, Linux or Windows with Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) for package management

If you don't have uv yet:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Running

```
cd /Volumes/SSD/ClaudeWork/interval-trainer
uv run IntervalTrainer.py
```

The first run installs the dependencies (pygame-ce, numpy, pyfluidsynth) into
`.venv` automatically. A window opens; click it so it has keyboard focus, then
press an interval key.

## Controls

| Key | Interval    | Semitones |
|-----|-------------|-----------|
| 1   | Minor 2nd   | 1         |
| 2   | Major 2nd   | 2         |
| 3   | Minor 3rd   | 3         |
| 4   | Major 3rd   | 4         |
| 5   | Perfect 4th | 5         |
| 6   | Tritone     | 6         |
| 7   | Perfect 5th | 7         |
| 8   | Minor 6th   | 8         |
| 9   | Major 6th   | 9         |
| 0   | Minor 7th   | 10        |
| -   | Major 7th   | 11        |
| =   | Octave      | 12        |

| Key   | Action                                   |
|-------|------------------------------------------|
| Space | Stop / resume playing                    |
| ↑     | Faster (shorter notes, down to 0.3 s)    |
| ↓     | Slower (longer notes, up to 2.0 s)       |
| Esc   | Quit                                     |

Pressing a different interval key switches immediately. The window shows the
selected interval, the two notes currently playing (e.g. `E3 – G#3`), the
speed and which sound engine is in use.

The `-` and `=` keys are the ones to the right of `0` on a US keyboard layout.
On other layouts use whichever keys produce `-` and `=`.

## Sound

By default the program uses a built-in synthesized tone. If a piano soundfont
and FluidSynth are available it uses real piano sound instead.

### Setting up piano sound (optional)

1. Install FluidSynth:

   ```
   brew install fluid-synth
   ```

   On Linux use your package manager, e.g. `sudo apt install fluidsynth`.

2. Get a piano or General MIDI `.sf2` soundfont (for example *Salamander Grand
   Piano*, *FluidR3_GM* or *GeneralUser GS*) and put it in a `soundfonts`
   folder inside the project:

   ```
   mkdir soundfonts
   mv ~/Downloads/YourPiano.sf2 soundfonts/
   ```

3. Run the program again. The bottom of the window should say
   `Sound: Piano (YourPiano.sf2)`.

The program looks for a soundfont in this order:

1. the file named by the `INTERVAL_SF2` environment variable, e.g.
   `INTERVAL_SF2=~/sounds/piano.sf2 uv run IntervalTrainer.py`
2. `soundfonts/*.sf2` in the project folder
3. `~/Library/Audio/Sounds/Banks/*.sf2`
4. `/opt/homebrew/share/soundfonts/`, `/usr/local/share/soundfonts/`,
   `/usr/share/sounds/sf2/`

It uses the first instrument (bank 0, program 0) of the soundfont, which is
Acoustic Grand Piano in General MIDI soundfonts.

### Troubleshooting

- **Still says "Simple synth" after installing FluidSynth:** pyfluidsynth finds
  Homebrew's library through the `HOMEBREW_PREFIX` environment variable. Make sure
  your shell profile contains `eval "$(/opt/homebrew/bin/brew shellenv)"`, or run
  with `HOMEBREW_PREFIX=/opt/homebrew uv run IntervalTrainer.py`. The reason the
  piano could not be loaded is printed in the terminal.
- **Keys do nothing:** click the window first so it has keyboard focus.
- **No sound:** check the system output device and volume; the program plays
  through the default audio output.

## Project layout

```
IntervalTrainer.py    the whole program (sound engines, UI, main loop)
pyproject.toml        project metadata and dependencies (managed by uv)
uv.lock               locked dependency versions
soundfonts/           optional: put .sf2 files here
```

To add or update dependencies use `uv add <package>`.
