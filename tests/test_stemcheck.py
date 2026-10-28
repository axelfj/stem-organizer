import json
import os
import struct
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "stemcheck"))
import stemcheck  # noqa: E402


def write_wav(path, data, rate=44100, bits=24, fmt_float=False):
    data = np.atleast_2d(np.asarray(data, dtype=np.float64))
    if data.shape[0] < data.shape[1]:
        data = data.T
    frames, ch = data.shape
    if fmt_float:
        raw = data.astype("<f4").tobytes()
        tag, bits = 3, 32
    elif bits == 16:
        raw = np.clip(np.round(data * 32767), -32768, 32767).astype("<i2").tobytes()
        tag = 1
    else:
        v = np.clip(np.round(data * 8388607), -8388608, 8388607).astype(np.int32).ravel()
        b = np.empty((v.size, 3), np.uint8)
        b[:, 0], b[:, 1], b[:, 2] = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
        raw, tag = b.tobytes(), 1
    align = ch * bits // 8
    fmt = struct.pack("<HHIIHH", tag, ch, rate, rate * align, align, bits)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(raw)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"LIST" + struct.pack("<I", 4) + b"INFO")  # extra chunk to skip
        f.write(b"data" + struct.pack("<I", len(raw)) + raw)


def tone(n=4410, amp=0.5, freq=440, rate=44100, seed=0):
    t = np.arange(n) / rate
    return amp * np.sin(2 * np.pi * freq * t + seed)


class StemCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def p(self, name):
        return os.path.join(self.dir, name)

    def levels(self, problems, level):
        return [p for p in problems if p["level"] == level]

    def test_clean_set_is_ready(self):
        write_wav(self.p("01_Kick.wav"), np.stack([tone(), tone(seed=1)]))
        write_wav(self.p("02_Bass.wav"), np.stack([tone(freq=55), tone(freq=55, seed=1)]))
        write_wav(self.p("03_Lead.wav"), np.stack([tone(freq=880), tone(freq=880, seed=2)]),
                  fmt_float=True)
        stems, problems = stemcheck.check_folder(self.dir)
        self.assertEqual(len(stems), 3)
        self.assertEqual([p for p in problems if p["level"] != "info"], [])
        self.assertAlmostEqual(stems[0]["peak_dbfs"], -6.02, delta=0.05)

    def test_length_and_rate_mismatch_are_errors(self):
        write_wav(self.p("01_Kick.wav"), tone(4410))
        write_wav(self.p("02_Bass.wav"), tone(2000))
        write_wav(self.p("03_Pad.wav"), tone(4410), rate=48000)
        _, problems = stemcheck.check_folder(self.dir)
        msgs = " ".join(p["message"] for p in self.levels(problems, "error"))
        self.assertIn("mixed sample rates", msgs)
        self.assertIn("differs", msgs)

    def test_quality_warnings(self):
        write_wav(self.p("01_Hat.wav"), np.zeros(4410))
        write_wav(self.p("02_Clap.wav"), np.ones(4410))
        write_wav(self.p("03_Snare.wav"), tone(), bits=16)
        write_wav(self.p("04_Snare copy.wav"), tone(), bits=16)
        write_wav(self.p("Audio 3.wav"), tone(seed=3))
        write_wav(self.p("06_Vox.wav"), np.stack([tone(), tone()]))
        write_wav(self.p("07_Full Mix.wav"), tone(seed=5))
        with open(self.p("08_Bass.mp3"), "wb") as f:
            f.write(b"ID3")
        _, problems = stemcheck.check_folder(self.dir)
        by_file = {}
        for p in problems:
            by_file.setdefault(p["file"], []).append(p["message"])
        self.assertTrue(any("silent" in m for m in by_file["01_Hat.wav"]))
        self.assertTrue(any("clipping" in m for m in by_file["02_Clap.wav"]))
        self.assertTrue(any("16-bit" in m for m in by_file["03_Snare.wav"]))
        self.assertTrue(any("identical to 03_Snare.wav" in m for m in by_file["04_Snare copy.wav"]))
        self.assertTrue(any("generic name" in m for m in by_file["Audio 3.wav"]))
        self.assertTrue(any("no order number" in m for m in by_file["Audio 3.wav"]))
        self.assertTrue(any("mono" in m for m in by_file["06_Vox.wav"]))
        self.assertTrue(any("full mix" in m for m in by_file["07_Full Mix.wav"]))
        self.assertTrue(any("WAV, not MP3" in m for m in by_file["08_Bass.mp3"]))

    def test_cli_exit_code_and_json(self):
        write_wav(self.p("01_Kick.wav"), tone(4410))
        write_wav(self.p("02_Bass.wav"), tone(100))
        out = os.path.join(tempfile.mkdtemp(), "r.json")
        self.assertEqual(stemcheck.main([self.dir, "--json", out]), 1)
        with open(out) as f:
            self.assertEqual(len(json.load(f)["stems"]), 2)

    def test_empty_folder(self):
        _, problems = stemcheck.check_folder(self.dir)
        self.assertEqual(problems[0]["level"], "error")


if __name__ == "__main__":
    unittest.main()


class CorruptAudioTest(unittest.TestCase):
    def test_truncated_wav_fails_folder_and_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, '01_Kick.wav')
            write_wav(path, tone(n=88200))
            with open(path, 'r+b') as f:
                f.truncate(os.path.getsize(path) - 132300)
            with self.assertRaises(stemcheck.WavError):
                stemcheck.analyze(path)
            _, problems = stemcheck.check_folder(folder)
            self.assertTrue(any(p['level'] == 'error' for p in problems))
            self.assertEqual(stemcheck.main([folder]), 1)

    def test_rf64_uses_ds64_not_trailing_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, '01_Kick.wav')
            data = np.arange(100, dtype='<i2').tobytes()
            fmt = struct.pack('<HHIIHH', 1, 1, 44100, 88200, 2, 16)
            ds64 = struct.pack('<QQQI', 0, len(data), 100, 0)
            with open(path, 'wb') as f:
                f.write(b'RF64' + struct.pack('<I', 0xffffffff) + b'WAVE')
                f.write(b'ds64' + struct.pack('<I', len(ds64)) + ds64)
                f.write(b'fmt ' + struct.pack('<I', len(fmt)) + fmt)
                f.write(b'data' + struct.pack('<I', 0xffffffff) + data)
                f.write(b'LIST' + struct.pack('<I', 4) + b'INFO')
            self.assertEqual(stemcheck.analyze(path)['frames'], 100)

    def test_partial_frame_and_nonfinite_float_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, '01_Kick.wav')
            write_wav(path, [float('nan')] * 20, fmt_float=True)
            with self.assertRaises(stemcheck.WavError):
                stemcheck.analyze(path)
            write_wav(path, tone(n=100))
            with open(path, 'r+b') as f:
                f.truncate(os.path.getsize(path) - 1)
            with self.assertRaises(stemcheck.WavError):
                stemcheck.analyze(path)
