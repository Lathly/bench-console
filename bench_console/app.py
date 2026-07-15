"""Textual TUI: edit llama-server + llama-benchy params, run them together."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Input, Label, RichLog, Select

from bench_console.config import BenchyConfig, ServerConfig
from bench_console.presets import list_presets, load_preset, save_preset
from bench_console.runner import BenchRunner
from bench_console.widgets import ModelPickerScreen, field_row

FLASH_ATTN_OPTIONS = [("on", "on"), ("off", "off"), ("auto", "auto")]
LATENCY_MODE_OPTIONS = [("generation", "generation"), ("api", "api"), ("none", "none")]
FORMAT_OPTIONS = [("md", "md"), ("json", "json"), ("csv", "csv")]

SERVER_TEXT_FIELDS = [
    ("srv_model_path", "Model path (.gguf)"),
    ("srv_alias", "Alias"),
    ("srv_host", "Host"),
    ("srv_port", "Port"),
    ("srv_ctx_size", "ctx-size"),
    ("srv_n_gpu_layers", "n-gpu-layers"),
    ("srv_batch_size", "batch-size"),
    ("srv_ubatch_size", "ubatch-size"),
    ("srv_cache_type_k", "cache-type-k"),
    ("srv_cache_type_v", "cache-type-v"),
    ("srv_parallel", "parallel"),
    ("srv_n_cpu_moe", "n-cpu-moe (optional)"),
    ("srv_threads", "threads (optional)"),
    ("srv_cache_reuse", "cache-reuse (optional)"),
    ("srv_lora_path", "lora path (optional)"),
    ("srv_mmproj_path", "mmproj path (optional)"),
    ("srv_extra_args", "Extra llama-server args"),
]

SERVER_CHECK_FIELDS = [
    ("srv_mlock", "mlock"),
    ("srv_no_mmap", "no-mmap"),
    ("srv_jinja", "jinja"),
]

BENCHY_TEXT_FIELDS = [
    ("bch_pp", "pp (prompt tokens)"),
    ("bch_tg", "tg (gen tokens)"),
    ("bch_depth", "depth"),
    ("bch_runs", "runs"),
    ("bch_concurrency", "concurrency"),
    ("bch_extra_args", "Extra llama-benchy args"),
]

BENCHY_CHECK_FIELDS = [
    ("bch_enable_prefix_caching", "enable-prefix-caching"),
    ("bch_no_cache", "no-cache"),
]


class BenchConsoleApp(App):
    CSS = """
    #form-pane {
        width: 46%;
        border-right: solid $accent;
        padding: 1 2;
    }
    #log {
        width: 54%;
        background: $surface;
    }
    .field-label {
        color: $text-muted;
        padding-top: 1;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        padding-top: 1;
    }
    #status-label {
        padding-top: 1;
        text-style: italic;
    }
    """

    BINDINGS = [
        ("ctrl+r", "run", "Run"),
        ("ctrl+x", "stop", "Stop"),
        ("ctrl+s", "save_preset_action", "Save preset"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.runner = BenchRunner()
        self._current_preset_name = "adhoc"

    def compose(self) -> ComposeResult:
        with Horizontal():
            with VerticalScroll(id="form-pane"):
                yield Label("Preset", classes="section-title")
                yield Select([(p, p) for p in list_presets()], id="preset-select", allow_blank=True, prompt="(none selected)")
                yield from field_row("preset-name-input", "Save as (name)", "adhoc")

                yield Label("llama-server", classes="section-title")
                yield Button("Browse models...", id="browse-btn")
                for field_id, label in SERVER_TEXT_FIELDS:
                    yield from field_row(field_id, label)
                yield Label("flash-attn", classes="field-label")
                yield Select(FLASH_ATTN_OPTIONS, id="srv_flash_attn", value="on")
                for field_id, label in SERVER_CHECK_FIELDS:
                    yield Checkbox(label, id=field_id)

                yield Label("llama-benchy", classes="section-title")
                for field_id, label in BENCHY_TEXT_FIELDS:
                    yield from field_row(field_id, label)
                yield Label("latency-mode", classes="field-label")
                yield Select(LATENCY_MODE_OPTIONS, id="bch_latency_mode", value="generation")
                yield Label("format", classes="field-label")
                yield Select(FORMAT_OPTIONS, id="bch_format", value="md")
                for field_id, label in BENCHY_CHECK_FIELDS:
                    yield Checkbox(label, id=field_id)

                yield Label("Ready.", id="status-label")
            yield RichLog(id="log", wrap=False, highlight=False, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        if list_presets():
            self._load_preset_by_name(list_presets()[0])
        else:
            self._populate_form(ServerConfig(), BenchyConfig())

    # --- form <-> config -------------------------------------------------

    def _populate_form(self, server: ServerConfig, benchy: BenchyConfig) -> None:
        data = {**{k: str(v) for k, v in server.to_dict().items()}, **{k: str(v) for k, v in benchy.to_dict().items()}}
        for field_id, _ in SERVER_TEXT_FIELDS:
            key = field_id.removeprefix("srv_")
            self.query_one(f"#{field_id}", Input).value = data.get(key, "")
        for field_id, _ in BENCHY_TEXT_FIELDS:
            key = field_id.removeprefix("bch_")
            self.query_one(f"#{field_id}", Input).value = data.get(key, "")
        for field_id, _ in SERVER_CHECK_FIELDS:
            key = field_id.removeprefix("srv_")
            self.query_one(f"#{field_id}", Checkbox).value = bool(getattr(server, key))
        for field_id, _ in BENCHY_CHECK_FIELDS:
            key = field_id.removeprefix("bch_")
            self.query_one(f"#{field_id}", Checkbox).value = bool(getattr(benchy, key))
        self.query_one("#srv_flash_attn", Select).value = server.flash_attn
        self.query_one("#bch_latency_mode", Select).value = benchy.latency_mode
        self.query_one("#bch_format", Select).value = benchy.format

    def _read_server_config(self) -> ServerConfig:
        server = ServerConfig()
        server.model_path = self.query_one("#srv_model_path", Input).value
        server.alias = self.query_one("#srv_alias", Input).value or "bench-model"
        server.host = self.query_one("#srv_host", Input).value or "127.0.0.1"
        server.port = int(self.query_one("#srv_port", Input).value or 8090)
        server.ctx_size = int(self.query_one("#srv_ctx_size", Input).value or 8192)
        server.n_gpu_layers = self.query_one("#srv_n_gpu_layers", Input).value or "999"
        server.flash_attn = self.query_one("#srv_flash_attn", Select).value or "on"
        server.batch_size = int(self.query_one("#srv_batch_size", Input).value or 2048)
        server.ubatch_size = int(self.query_one("#srv_ubatch_size", Input).value or 512)
        server.cache_type_k = self.query_one("#srv_cache_type_k", Input).value or "q8_0"
        server.cache_type_v = self.query_one("#srv_cache_type_v", Input).value or "q8_0"
        server.parallel = int(self.query_one("#srv_parallel", Input).value or 1)
        server.n_cpu_moe = self.query_one("#srv_n_cpu_moe", Input).value
        server.threads = self.query_one("#srv_threads", Input).value
        server.cache_reuse = self.query_one("#srv_cache_reuse", Input).value
        server.lora_path = self.query_one("#srv_lora_path", Input).value
        server.mmproj_path = self.query_one("#srv_mmproj_path", Input).value
        server.extra_args = self.query_one("#srv_extra_args", Input).value
        server.mlock = self.query_one("#srv_mlock", Checkbox).value
        server.no_mmap = self.query_one("#srv_no_mmap", Checkbox).value
        server.jinja = self.query_one("#srv_jinja", Checkbox).value
        return server

    def _read_benchy_config(self) -> BenchyConfig:
        benchy = BenchyConfig()
        benchy.pp = self.query_one("#bch_pp", Input).value or "2048"
        benchy.tg = self.query_one("#bch_tg", Input).value or "32"
        benchy.depth = self.query_one("#bch_depth", Input).value or "0"
        benchy.runs = int(self.query_one("#bch_runs", Input).value or 3)
        benchy.concurrency = self.query_one("#bch_concurrency", Input).value or "1"
        benchy.latency_mode = self.query_one("#bch_latency_mode", Select).value or "generation"
        benchy.format = self.query_one("#bch_format", Select).value or "md"
        benchy.extra_args = self.query_one("#bch_extra_args", Input).value
        benchy.enable_prefix_caching = self.query_one("#bch_enable_prefix_caching", Checkbox).value
        benchy.no_cache = self.query_one("#bch_no_cache", Checkbox).value
        return benchy

    def _load_preset_by_name(self, name: str) -> None:
        try:
            server, benchy = load_preset(name)
        except (FileNotFoundError, ValueError) as e:
            self._set_status(f"Could not load preset {name!r}: {e}")
            return
        self._populate_form(server, benchy)
        self._current_preset_name = name
        self.query_one("#preset-name-input", Input).value = name
        self._set_status(f"Loaded preset: {name}")

    def _set_status(self, text: str) -> None:
        self.query_one("#status-label", Label).update(text)

    # --- events ------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "browse-btn":
            self.push_screen(ModelPickerScreen(), self._on_model_picked)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "preset-select" and event.value != Select.BLANK:
            self._load_preset_by_name(str(event.value))

    def _on_model_picked(self, path: str | None) -> None:
        if path:
            self.query_one("#srv_model_path", Input).value = path

    def action_save_preset_action(self) -> None:
        name = self.query_one("#preset-name-input", Input).value.strip() or "adhoc"
        server = self._read_server_config()
        benchy = self._read_benchy_config()
        path = save_preset(name, server, benchy)
        select = self.query_one("#preset-select", Select)
        select.set_options([(p, p) for p in list_presets()])
        select.value = name
        self._current_preset_name = name
        self._set_status(f"Saved preset to {path}")

    def action_run(self) -> None:
        try:
            server = self._read_server_config()
            benchy = self._read_benchy_config()
        except ValueError as e:
            self._set_status(f"Invalid value in form: {e}")
            return
        log = self.query_one("#log", RichLog)
        log.clear()
        self._set_status("Starting...")
        self.run_worker(self._do_run(server, benchy), exclusive=True)

    async def _do_run(self, server: ServerConfig, benchy: BenchyConfig) -> None:
        log = self.query_one("#log", RichLog)

        def emit(line: str) -> None:
            log.write(line)

        self._set_status("Running...")
        result = await self.runner.run(self._current_preset_name, server, benchy, emit)
        if result.success:
            self._set_status(f"Done. Result saved: {result.transcript_path}")
        else:
            self._set_status(f"Failed: {result.error}")

    def action_stop(self) -> None:
        self._set_status("Stopping...")
        self.run_worker(self.runner.stop(), exclusive=False)


def main() -> None:
    BenchConsoleApp().run()


if __name__ == "__main__":
    main()
