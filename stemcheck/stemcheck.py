#!/usr/bin/env python3
"""
stemcheck: checks a folder of exported stems before it goes to mixdown.

Works with stems from any DAW. Point it at the folder you are about to send:

    python stemcheck.py path/to/stems
    python stemcheck.py path/to/stems --json report.json

Exit code is 1 when something must be fixed before sending, 0 otherwise.

License: MIT (see LICENSE at the repository root).
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys

import numpy as np

CHUNK_FRAMES = 1 << 18
SILENCE_DBFS = -90.0
CLIP_LINEAR = 0.9999

GENERIC_NAME = re.compile(
    r"^(audio|track|insert|sampler|channel|mixer|untitled|new|stem|bus)"
    r"[\s_-]*\d*$", re.I)
NUMBERED = re.compile(r"^\d{2,3}[\s_-]")
FULL_MIX = re.compile(r"(^|[\s_-])(master|mixdown|full[\s_-]?mix|premaster|2[\s_-]?track)"
                      r"([\s_-]|$)", re.I)


class WavError(Exception):
    pass


def read_header(f):
    riff, _size, wave = struct.unpack("<4sI4s", f.read(12))
    if riff not in (b"RIFF", b"RF64") or wave != b"WAVE":
        raise WavError("not a WAV file")
    fmt = None
    rf64_data_size = None
    while True:
        head = f.read(8)
        if len(head) < 8:
            raise WavError("no audio data chunk")
        cid, size = struct.unpack("<4sI", head)
        if cid == b"ds64":
            if riff != b"RF64" or size < 28:
                raise WavError("broken RF64 size chunk")
            body = f.read(28)
            if len(body) != 28:
                raise WavError("truncated RF64 size chunk")
            _, rf64_data_size, _, _ = struct.unpack("<QQQI", body)
            f.seek(size - 28 + (size & 1), os.SEEK_CUR)
        elif cid == b"fmt ":
            body = f.read(size + (size & 1))
            tag, ch, sr, _br, _align, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack("<H", body[24:26])[0]
            fmt = {"tag": tag, "channels": ch, "rate": sr, "bits": bits}
        elif cid == b"data":
            if fmt is None:
                raise WavError("data before format chunk")
            if size == 0xFFFFFFFF:
                if rf64_data_size is None:
                    raise WavError("RF64 data requires a ds64 size chunk")
                size = rf64_data_size
            here = f.tell()
            f.seek(0, os.SEEK_END)
            available = f.tell() - here
            f.seek(here)
            if size > available:
                raise WavError("truncated WAV audio data")
            return fmt, size
        else:
            f.seek(size + (size & 1), os.SEEK_CUR)


def decode(raw, fmt):
    bits, tag = fmt["bits"], fmt["tag"]
    if tag == 3 and bits == 32:
        return np.frombuffer(raw, "<f4").astype(np.float64)
    if tag == 3 and bits == 64:
        return np.frombuffer(raw, "<f8")
    if tag != 1:
        raise WavError("unsupported WAV encoding (format tag %d)" % tag)
    if bits == 16:
        return np.frombuffer(raw, "<i2") / 32768.0
    if bits == 24:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v & 0x800000, v - 0x1000000, v)
        return v / 8388608.0
    if bits == 32:
        return np.frombuffer(raw, "<i4") / 2147483648.0
    if bits == 8:
        return (np.frombuffer(raw, np.uint8).astype(np.float64) - 128) / 128.0
    raise WavError("unsupported bit depth %d" % bits)


def analyze(path):
    with open(path, "rb") as f:
        fmt, size = read_header(f)
        frame_bytes = fmt["channels"] * fmt["bits"] // 8
        if fmt["channels"] < 1 or fmt["rate"] <= 0 or fmt["bits"] not in (8, 16, 24, 32, 64):
            raise WavError("unsupported WAV layout")
        if frame_bytes == 0:
            raise WavError("broken format chunk")
        if size % frame_bytes:
            raise WavError("partial WAV audio frame")
        frames = size // frame_bytes
        peak = 0.0
        dual_mono = fmt["channels"] == 2
        digest = hashlib.sha1()
        left = frames
        while left > 0:
            n = min(left, CHUNK_FRAMES)
            raw = f.read(n * frame_bytes)
            if len(raw) != n * frame_bytes:
                raise WavError("truncated WAV audio data")
            digest.update(raw)
            x = decode(raw, fmt).reshape(-1, fmt["channels"])
            if not np.isfinite(x).all():
                raise WavError("non-finite WAV samples")
            if x.size:
                peak = max(peak, float(np.abs(x).max()))
                if dual_mono and not np.array_equal(x[:, 0], x[:, 1]):
                    dual_mono = False
            left -= n
    peak_db = 20 * np.log10(peak) if peak > 0 else float("-inf")
    return {
        "file": os.path.basename(path),
        "rate": fmt["rate"],
        "bits": fmt["bits"],
        "float": fmt["tag"] == 3,
        "channels": fmt["channels"],
        "frames": int(frames),
        "seconds": round(frames / fmt["rate"], 3) if fmt["rate"] else 0,
        "peak_dbfs": round(float(peak_db), 2) if peak > 0 else None,
        "clipping": bool(peak >= CLIP_LINEAR),
        "silent": bool(peak == 0 or peak_db < SILENCE_DBFS),
        "dual_mono": bool(dual_mono),
        "hash": digest.hexdigest(),
    }


def check_folder(folder):
    names = sorted(n for n in os.listdir(folder)
                   if not n.startswith(".") and os.path.isfile(os.path.join(folder, n)))
    stems, problems = [], []

    def add(level, file, msg):
        problems.append({"level": level, "file": file, "message": msg})

    for n in names:
        if not n.lower().endswith((".wav", ".wave")):
            if n.lower().endswith((".mp3", ".m4a", ".aac", ".ogg", ".flac", ".aif", ".aiff")):
                add("error", n, "send stems as WAV, not %s" % n.rsplit(".", 1)[-1].upper())
            continue
        try:
            stems.append(analyze(os.path.join(folder, n)))
        except (WavError, struct.error, ValueError) as e:
            add("error", n, "could not read: %s" % e)

    if not stems:
        add("error", None, "no WAV stems found in this folder")
        return stems, problems

    # The whole set must line up: same rate, same length.
    rates = sorted({s["rate"] for s in stems})
    if len(rates) > 1:
        add("error", None, "mixed sample rates %s: export all stems at the "
            "project rate" % ", ".join("%d Hz" % r for r in rates))
    lengths = {s["frames"] for s in stems}
    if len(lengths) > 1:
        longest = max(stems, key=lambda s: s["frames"])
        for s in stems:
            if s["frames"] != longest["frames"]:
                add("error", s["file"], "length %.3fs differs from %.3fs: export every "
                    "stem from bar 1 to the same end point"
                    % (s["seconds"], longest["seconds"]))
    depths = sorted({(s["bits"], s["float"]) for s in stems})
    if len(depths) > 1:
        add("info", None, "mixed bit depths: %s"
            % ", ".join("%d-bit%s" % (b, " float" if fl else "") for b, fl in depths))

    seen = {}
    for s in stems:
        f = s["file"]
        base = os.path.splitext(f)[0]
        if s["bits"] < 24 and not s["float"]:
            add("warning", f, "%d-bit: export at 24-bit or 32-bit float" % s["bits"])
        if s["silent"]:
            add("warning", f, "stem is silent: remove it or check the routing")
        if s["clipping"]:
            add("warning", f, "peaks at 0 dBFS (clipping): lower the track and re-export")
        if s["dual_mono"]:
            add("info", f, "left and right are identical: this could be a mono file")
        if s["hash"] in seen:
            add("warning", f, "identical to %s: the same sound was exported twice"
                % seen[s["hash"]])
        else:
            seen[s["hash"]] = f
        stripped = NUMBERED.sub("", base)
        if GENERIC_NAME.match(stripped.strip()):
            add("warning", f, "generic name: rename it after the sound (Kick, Lead Synth...)")
        if FULL_MIX.search(base):
            add("info", f, "looks like a full mix: send it as a separate reference, "
                "not inside the stems")
        if not NUMBERED.match(base):
            add("info", f, "no order number: '01_Kick.wav' keeps stems in order")

    return stems, problems


def format_report(folder, stems, problems):
    out = ["stemcheck: %s" % folder, ""]
    if stems:
        out.append("%-36s %7s %6s %3s %9s %9s" % ("FILE", "RATE", "BITS", "CH", "LENGTH", "PEAK"))
        for s in stems:
            peak = "-inf" if s["peak_dbfs"] is None else "%.1f" % s["peak_dbfs"]
            out.append("%-36s %7d %6s %3d %8.2fs %9s" % (
                s["file"][:36], s["rate"], "%d%s" % (s["bits"], "f" if s["float"] else ""),
                s["channels"], s["seconds"], peak))
        out.append("")
    order = {"error": 0, "warning": 1, "info": 2}
    for p in sorted(problems, key=lambda p: order[p["level"]]):
        out.append("%-8s %s%s" % (p["level"].upper(), (p["file"] + ": ") if p["file"] else "",
                                  p["message"]))
    errors = sum(p["level"] == "error" for p in problems)
    warnings = sum(p["level"] == "warning" for p in problems)
    out.append("")
    if errors:
        out.append("NOT READY: %d error(s), %d warning(s)." % (errors, warnings))
    else:
        out.append("READY to send: %d stem(s), %d warning(s)." % (len(stems), warnings))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check exported stems before mixdown.")
    ap.add_argument("folder")
    ap.add_argument("--json", metavar="FILE", help="also write the report as JSON")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.folder):
        ap.error("not a folder: %s" % args.folder)
    stems, problems = check_folder(args.folder)
    print(format_report(args.folder, stems, problems))
    if args.json:
        with open(args.json, "w") as f:
            json.dump({"stems": stems, "problems": problems}, f, indent=2)
    return 1 if any(p["level"] == "error" for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())

