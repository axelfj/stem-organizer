"""Tests for the FL Studio script, with FL's modules replaced by a fake project."""
import importlib.util
import os
import sys
import types
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "device_StemOrganizer", os.path.join(HERE, "..", "fl-studio", "device_StemOrganizer.py"))
so = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(so)


def ch(i, name, target, ctype=so.CT_GENPLUG, color=0x112233):
    return {"index": i, "name": name, "color": color, "type": ctype, "target": target}


def tracks(n=10, named=None, fx=(), inputs=()):
    named = named or {}
    return [{"index": t, "name": named.get(t, "Insert %d" % t),
             "has_fx": t in fx, "has_inputs": t in inputs} for t in range(1, n + 1)]


class PlanTest(unittest.TestCase):
    def test_already_organized_only_renames_default_names(self):
        plan = so.build_plan([ch(0, "Kick", 1), ch(1, "Bass", 2)], tracks(named={2: "BASS"}))
        self.assertEqual(plan["moves"], [])
        self.assertEqual([(r["track"], r["name"]) for r in plan["renames"]], [(1, "Kick")])

    def test_channels_on_master_get_own_inserts(self):
        plan = so.build_plan([ch(0, "Kick", 0), ch(1, "Clap", 0)], tracks())
        self.assertEqual([(m["name"], m["new_track"], m["route_to"]) for m in plan["moves"]],
                         [("Kick", 1, 0), ("Clap", 2, 0)])

    def test_shared_plain_insert_first_channel_keeps_it(self):
        plan = so.build_plan([ch(0, "Kick", 1), ch(1, "Clap", 1), ch(2, "Hat", 1)], tracks())
        self.assertEqual(plan["renames"][0]["track"], 1)
        self.assertEqual([(m["name"], m["new_track"], m["route_to"]) for m in plan["moves"]],
                         [("Clap", 2, 0), ("Hat", 3, 0)])
        self.assertEqual(plan["warnings"], [])

    def test_shared_insert_with_fx_becomes_bus(self):
        plan = so.build_plan([ch(0, "Kick", 1), ch(1, "Clap", 1)],
                             tracks(named={1: "Drums"}, fx={1}))
        self.assertEqual([(m["name"], m["new_track"], m["route_to"]) for m in plan["moves"]],
                         [("Kick", 2, 1), ("Clap", 3, 1)])
        self.assertIn("bus", plan["warnings"][0])

    def test_free_inserts_skip_used_ones(self):
        plan = so.build_plan([ch(0, "A", 0), ch(1, "B", 5)],
                             tracks(n=6, named={2: "Reverb"}, fx={3}, inputs={4}))
        self.assertEqual(plan["moves"][0]["new_track"], 1)
        self.assertEqual([r["track"] for r in plan["renames"]], [5])
        plan = so.build_plan([ch(0, "A", 0), ch(1, "B", 0), ch(2, "C", 5)],
                             tracks(n=6, named={2: "Reverb"}, fx={3}, inputs={4}))
        self.assertEqual([m["new_track"] for m in plan["moves"]], [1, 6])

    def test_silent_channels_ignored_and_full_mixer(self):
        plan = so.build_plan([ch(0, "Auto", 0, so.CT_AUTOCLIP), ch(1, "Layer", 0, so.CT_LAYER),
                              ch(2, "Kick", 0), ch(3, "Bass", 0)], tracks(n=1))
        self.assertEqual([m["name"] for m in plan["moves"]], ["Kick"])
        self.assertEqual(plan["skipped"][0]["name"], "Bass")
        self.assertIn("mixer is full", plan["warnings"][-1])


class FakeFL:
    """A tiny fake of FL Studio's channels/mixer/plugins/general modules."""

    def __init__(self, chans, n_inserts, fx=(), names=None):
        self.chans = chans
        self.n = n_inserts
        self.fx = set(fx)
        self.names = dict(names or {})
        self.colors = {}
        self.routes = {t: {0} for t in range(1, n_inserts + 1)}
        self.undo = []

        c = types.ModuleType("channels")
        c.channelCount = lambda g=False: len(self.chans)
        c.getChannelName = lambda i, g=False: self.chans[i]["name"]
        c.getChannelColor = lambda i, g=False: self.chans[i]["color"]
        c.getChannelType = lambda i, g=False: self.chans[i]["type"]
        c.getTargetFxTrack = lambda i, g=False: self.chans[i]["target"]

        def set_target(i, t, g=False):
            self.chans[i]["target"] = t
        c.setTargetFxTrack = set_target

        m = types.ModuleType("mixer")
        m.trackCount = lambda: self.n + 2
        m.getTrackName = lambda t: self.names.get(t, "Insert %d" % t)
        m.setTrackName = lambda t, s: self.names.__setitem__(t, s)
        m.setTrackColor = lambda t, col: self.colors.__setitem__(t, col)
        m.getRouteSendActive = lambda s, d: d in self.routes.get(s, ())

        def set_route(s, d, v, ui=False):
            (self.routes[s].add if v else self.routes[s].discard)(d)
        m.setRouteTo = set_route
        m.afterRoutingChanged = lambda: None

        p = types.ModuleType("plugins")
        p.isValid = lambda t, s=-1, g=False: (t, s) in self.fx

        gm = types.ModuleType("general")
        gm.saveUndo = lambda name, flags, update=True: self.undo.append(name)
        self.modules = {"channels": c, "mixer": m, "plugins": p, "general": gm}

    def __enter__(self):
        sys.modules.update(self.modules)
        return self

    def __exit__(self, *a):
        for k in self.modules:
            sys.modules.pop(k, None)


class AdapterTest(unittest.TestCase):
    def test_organize_end_to_end(self):
        chans = [ch(0, "Kick", 1), ch(1, "Clap", 1), ch(2, "Bass", 0), ch(3, "Pad", 4),
                 ch(4, "Filter auto", 0, so.CT_AUTOCLIP)]
        with FakeFL(chans, 8, fx={(1, 0)}, names={1: "Drums", 4: "PAD"}) as fl:
            plan = so.organize()
            self.assertEqual(fl.undo, ["Stem Organizer"])
            # Kick and Clap left the Drums insert but still feed it.
            self.assertNotEqual(chans[0]["target"], chans[1]["target"])
            for c in chans[:2]:
                self.assertEqual(fl.routes[c["target"]], {1})
                self.assertEqual(fl.names[c["target"]], c["name"])
            self.assertEqual(fl.routes[chans[2]["target"]], {0})
            self.assertEqual(chans[3]["target"], 4)
            self.assertEqual(chans[4]["target"], 0)
            # Running again finds nothing left to do.
            again = so.build_plan(*so._read_project())
            self.assertEqual(again["moves"], [])
        self.assertEqual(len(plan["moves"]), 3)


if __name__ == "__main__":
    unittest.main()
