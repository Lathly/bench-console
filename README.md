# bench-console

Simple TUI for benchmarking local GGUF models: edit all `llama-server` and
`llama-benchy` parameters in one form, press **Run**, and the tool:

1. Automatically stops `llama.service` if it's
   running, since the GPU only has room for one model at a time.
2. Starts `llama-server` with your parameters.
3. Waits until the server responds on `/health`.
4. Writes a header with all the llama.cpp parameters at the top of the log
   window.
5. Automatically starts `llama-benchy` against it, with results scrolling
   down in the same log window.
6. Saves the full transcript (header + server log + benchy results) to
   `results/<preset>_<timestamp>.txt` for easy comparison later.

`llama.service` is **not** automatically restarted afterward — run
`systemctl --user start llama.service` when you're done benchmarking.

## Running

```bash
cd ~/bench-console
.venv/bin/bench-console
# or: uv run bench-console
```

## Presets

Settings are saved as JSON files under `presets/`. Pick a preset from the
dropdown at the top — selecting it loads it automatically — or save the form
you've edited by typing a name in "Save as" and pressing Ctrl+S.
`presets/example.json` is a starting point.

## Shortcuts

- `Ctrl+R`: Run
- `Ctrl+X`: Stop (kills any running processes)
- `Ctrl+S`: Save preset
- `q`: Quit

## Environment variables

- `LLAMA_SERVER_BIN`: path to `llama-server` (default:
  `~/ai/llama.cpp/build/bin/llama-server`)
- `BENCHY_BIN`: path to `llama-benchy` (default:
  `~/ai/llama-benchy/.venv/bin/llama-benchy`)
- `BENCH_CONSOLE_READY_TIMEOUT`: seconds to wait for the server to become
  ready (default 180)
