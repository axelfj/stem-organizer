# name=Stem Organizer
"""
Stem Organizer for FL Studio.

Gives every sound in the Channel Rack its own Mixer insert, so that
"Split mixer tracks" on export renders one clean stem per sound instead of
several sounds bounced together.

What it does when you run organize():
  * Every instrument / sample / audio-clip channel that shares a Mixer insert
    with other channels, or goes straight to Master, gets a free insert of its
    own, named and colored like the channel.
  * If the shared insert had effects on it (a drum bus, a reverb bus...), the
    new insert is routed INTO that old insert, so the sound you hear does not
    change. The old insert becomes a bus.
  * Inserts that already hold exactly one channel and still have a default
    name ("Insert 12") are renamed after that channel.
  * Nothing is deleted. One undo step ("Stem Organizer") reverts it all.

How to run it: see fl-studio/README.md. In short, assign this script to any
MIDI input, open VIEW > Script output > Interpreter and type:
    preview()     # shows the plan, changes nothing
    organize()    # applies it

License: MIT (see LICENSE at the repository root).
"""

# Channel type constants (midi.CT_*), copied so the planner has no FL imports.
CT_SAMPLER = 0
CT_HYBRID = 1
CT_GENPLUG = 2
CT_LAYER = 3
CT_AUDIOCLIP = 4
CT_AUTOCLIP = 5

# Layers and automation clips make no sound of their own.
SILENT_TYPES = (CT_LAYER, CT_AUTOCLIP)

MASTER = 0
MAX_FX_SLOTS = 10
MAX_NAME = 32


# --------------------------------------------------------------------------
# Planning (pure Python, no FL Studio modules: unit-tested outside FL)
# --------------------------------------------------------------------------

def is_default_track_name(name, index):
    name = (name or "").strip()
    return name == "" or name == "Insert %d" % index


def build_plan(channels, tracks):
    """Decide what to change.

    channels: list of dicts {index, name, color, type, target}
    tracks:   list of dicts {index, name, has_fx, has_inputs}
              covering the usable inserts (Master excluded).

    Returns a dict:
      moves:   [{channel, name, color, new_track, route_to}]  route_to = bus or MASTER
      renames: [{track, name, color}]
      skipped: [{channel, name, reason}]
      warnings: [str]
    """
    by_track = {}
    skipped = []
    for ch in channels:
        if ch["type"] in SILENT_TYPES:
            continue
        by_track.setdefault(ch["target"], []).append(ch)

    track_info = {t["index"]: t for t in tracks}

    def is_free(t):
        return (t["index"] not in by_track
                and not t["has_fx"]
                and not t["has_inputs"]
                and is_default_track_name(t["name"], t["index"]))

    free = [t["index"] for t in sorted(tracks, key=lambda t: t["index"]) if is_free(t)]

    moves, renames, warnings = [], [], []

    for target in sorted(by_track):
        group = sorted(by_track[target], key=lambda c: c["index"])
        info = track_info.get(target)

        if target != MASTER and len(group) == 1 and info is not None:
            ch = group[0]
            if info and is_default_track_name(info["name"], target):
                renames.append({"track": target, "name": clean_name(ch["name"]),
                                "color": ch["color"]})
            continue

        # Shared insert (or Master). If the shared insert is untouched (no FX,
        # default name), the first channel can simply keep it.
        keep_first = (target != MASTER and info is not None
                      and not info["has_fx"]
                      and is_default_track_name(info["name"], target))
        if keep_first:
            first = group[0]
            renames.append({"track": target, "name": clean_name(first["name"]),
                            "color": first["color"]})
            group = group[1:]
            route_to = MASTER
        elif info is None:
            # Master, or a track outside the usable inserts.
            route_to = MASTER
        else:
            # Keep whatever processing the shared insert does by feeding it.
            route_to = target

        for ch in group:
            if not free:
                skipped.append({"channel": ch["index"], "name": ch["name"],
                                "reason": "no free mixer inserts left"})
                continue
            moves.append({"channel": ch["index"], "name": clean_name(ch["name"]),
                          "color": ch["color"], "new_track": free.pop(0),
                          "route_to": route_to})

        if route_to != MASTER and group:
            warnings.append(
                "Insert %d (%s) is now a bus fed by %d sound(s); it will also "
                "render as its own stem. Send both, or mute the bus stem."
                % (target, (info or {}).get("name") or "Insert %d" % target, len(group)))

    if skipped:
        warnings.append("%d channel(s) could not get their own insert: the "
                        "mixer is full. Free some inserts and run again." % len(skipped))

    return {"moves": moves, "renames": renames, "skipped": skipped,
            "warnings": warnings}


def clean_name(name):
    name = (name or "").strip() or "Untitled"
    return name[:MAX_NAME]


def format_plan(plan):
    lines = []
    if not plan["moves"] and not plan["renames"]:
        lines.append("Nothing to do: every sound already has its own insert.")
    for m in plan["moves"]:
        dest = "Master" if m["route_to"] == MASTER else "Insert %d (bus)" % m["route_to"]
        lines.append("MOVE   %-24s -> Insert %3d  (routed to %s)"
                     % (m["name"], m["new_track"], dest))
    for r in plan["renames"]:
        lines.append("NAME   Insert %3d -> %s" % (r["track"], r["name"]))
    for s in plan["skipped"]:
        lines.append("SKIP   %-24s (%s)" % (s["name"], s["reason"]))
    for w in plan["warnings"]:
        lines.append("NOTE   " + w)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# FL Studio adapter (only runs inside FL Studio)
# --------------------------------------------------------------------------

def _read_project():
    import channels
    import mixer
    import plugins

    def chan_call(fn, i):
        # useGlobalIndex arrived in API v33; older FL only sees the current group.
        try:
            return fn(i, True)
        except TypeError:
            return fn(i)

    try:
        count = channels.channelCount(True)
    except TypeError:
        count = channels.channelCount()

    chans = []
    for i in range(count):
        try:
            ctype = chan_call(channels.getChannelType, i)
        except AttributeError:
            ctype = CT_GENPLUG
        chans.append({
            "index": i,
            "name": chan_call(channels.getChannelName, i),
            "color": chan_call(channels.getChannelColor, i),
            "type": ctype,
            "target": chan_call(channels.getTargetFxTrack, i),
        })

    # Track 0 is Master and the last one is the "Current" track.
    last = mixer.trackCount() - 2
    inserts = range(1, last + 1)
    tracks = []
    for t in inserts:
        has_fx = any(plugins.isValid(t, s) for s in range(MAX_FX_SLOTS))
        has_inputs = any(mixer.getRouteSendActive(src, t)
                         for src in inserts if src != t)
        tracks.append({"index": t, "name": mixer.getTrackName(t),
                       "has_fx": has_fx, "has_inputs": has_inputs})
    return chans, tracks


def _apply(plan):
    import channels
    import general
    import mixer

    general.saveUndo("Stem Organizer", 0)

    for m in plan["moves"]:
        t = m["new_track"]
        try:
            channels.setTargetFxTrack(m["channel"], t, True)
        except TypeError:
            channels.setTargetFxTrack(m["channel"], t)
        mixer.setTrackName(t, m["name"])
        mixer.setTrackColor(t, m["color"])
        if m["route_to"] != MASTER:
            mixer.setRouteTo(t, MASTER, False)
            mixer.setRouteTo(t, m["route_to"], True)

    for r in plan["renames"]:
        mixer.setTrackName(r["track"], r["name"])
        mixer.setTrackColor(r["track"], r["color"])

    mixer.afterRoutingChanged()


def preview():
    """Print what organize() would do. Changes nothing."""
    plan = build_plan(*_read_project())
    print(format_plan(plan))
    return plan


def organize():
    """Give every sound its own mixer insert. Undo with Ctrl+Z."""
    plan = build_plan(*_read_project())
    _apply(plan)
    print(format_plan(plan))
    print("Done. Now export with File > Export > WAV and tick "
          "'Split mixer tracks'. Ctrl+Z undoes everything.")
    return plan


def OnInit():
    print("Stem Organizer loaded. Type preview() or organize() in the "
          "Interpreter tab.")
