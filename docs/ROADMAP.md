# Roadmap

## What each DAW lets a tool do

A normal audio plugin (VST3/AU/CLAP) lives inside one track and cannot see or
change the project, so "a plugin for every DAW" is not possible. Each DAW needs
its own small integration, plus one shared checker for the exported files.

| DAW | Scripting | Can reorganize tracks | Can trigger export | Plan |
|---|---|---|---|---|
| FL Studio | Python (MIDI scripting API) | Yes: route channels to inserts, name, color, route | No | **Done**: `fl-studio/` |
| Ableton Live | Python Remote Scripts, Max for Live (Live API) | Partly: rename, color, create tracks; moving clips out of racks is hard | No | Next: M4L device that audits the set (racks with several sounds, tracks on Master, generic names) and renames/colors; user exports with *All Individual Tracks* |
| REAPER | ReaScript (Lua/Python), full API | Yes | Yes (render stems) | Later: one-click organize + render |
| Logic, Bitwig, Studio One, Cubase | Limited or none for this | No | No | Covered by `stemcheck` |

## Next steps

1. Test `fl-studio/` on real projects (drum kits on one insert, FPC, groups).
2. Ableton Max for Live auditor.
3. Package `stemcheck` as a double-click app (no Python needed).
4. REAPER script.
