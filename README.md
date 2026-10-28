# Stem Organizer

Get your project in order before it goes to mixdown: one sound, one track, one stem.

Producers often send stems where the kick, clap and hats were bounced together
because they shared a mixer channel, or where half the sounds went straight to
Master. The mix engineer can't fix what was printed together. Stem Organizer
fixes the project **before** export, and checks the stems **after** export.

| Part | What it does | Works with |
|---|---|---|
| [`fl-studio/`](fl-studio/README.md) | Gives every Channel Rack sound its own Mixer insert (named and colored), keeping any bus effects, in one undoable step. Then *Split mixer tracks* renders one clean stem per sound. | FL Studio 20.7+ |
| [`stemcheck/`](stemcheck/stemcheck.py) | Checks a folder of exported WAV stems: same length and sample rate, no clipping, no silent or duplicate stems, no generic names, no full mix hidden among the stems. | Any DAW |

Ableton Live and REAPER versions are on the roadmap (see [docs/ROADMAP.md](docs/ROADMAP.md)).

## Download

Get the app from the [Releases page](https://github.com/axelfj/stem-organizer/releases):
`StemOrganizer.exe` for Windows, `StemOrganizer.dmg` for macOS (Apple silicon).
It has two buttons: **Install FL Studio script** and **Check a stems folder**.

Windows users can also get it from the Microsoft Store (coming soon), which
installs it with no warning. The downloads above are not code-signed yet, so
the first launch shows a warning:
- Windows: *More info > Run anyway*.
- macOS: open it once, then *System Settings > Privacy & Security > Open Anyway*.

How the Store package is built and published: [docs/MICROSOFT_STORE.md](docs/MICROSOFT_STORE.md).

## Quick start (from source)

**FL Studio**: install the script as described in [fl-studio/README.md](fl-studio/README.md),
then in *VIEW > Script output > Interpreter* type `preview()` to see the plan and
`organize()` to apply it.

**Any DAW**: export your stems to a folder, then:

```
pip install numpy
python stemcheck/stemcheck.py "path/to/stems"
```

It prints a report and ends with `READY to send` or `NOT READY`.

## Tests

```
python -m unittest discover -s tests
```

The FL Studio tests run against a fake FL project, so they don't need FL Studio.

## License

MIT. See [LICENSE](LICENSE).
