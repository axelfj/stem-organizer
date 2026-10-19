# Stem Organizer for FL Studio

## Install

1. Create this folder and copy `device_StemOrganizer.py` into it:
   - Windows: `Documents\Image-Line\FL Studio\Settings\Hardware\Stem Organizer\`
   - macOS: `~/Documents/Image-Line/FL Studio/Settings/Hardware/Stem Organizer/`
2. FL Studio only runs scripts attached to a MIDI input. In
   *OPTIONS > MIDI settings*, pick any input (your keyboard, or a virtual port:
   loopMIDI on Windows, the IAC Driver on macOS), enable it, and set
   *Controller type* to **Stem Organizer**.
3. Open *VIEW > Script output*, pick **Stem Organizer**, go to the
   **Interpreter** tab.

## Use

```
preview()     # prints the plan, changes nothing
organize()    # applies it (one Ctrl+Z undoes it)
```

Then *File > Export > WAV file*, tick **Split mixer tracks**, and render.
Each insert becomes one stem, named after the sound.

## What it changes

- Sounds that go straight to **Master**, or share an insert with other sounds,
  get a free insert of their own, named and colored like the channel.
- If the shared insert has effects (a drum bus, a reverb), the new inserts are
  routed **into** it, so the song sounds the same. That insert becomes a bus and
  also renders as its own stem; send it too or leave it out, but don't mix both
  into the final.
- Inserts holding exactly one sound but still called "Insert 12" are renamed.
- Automation clips and Layer channels are ignored (they make no sound).
- It never deletes anything, and never touches inserts that are named, have
  effects or receive sends.

## Limits

- Multi-output instruments (FPC, Kontakt, Battery with several outputs) count
  as one sound. Route their outputs by hand.
- Needs FL Studio 20.7 or later (Python scripting). Channel groups are handled
  on recent versions (scripting API 33+); older versions only see the channels in the current group.
