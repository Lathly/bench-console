"""Small reusable widgets: labeled input rows and the model-file picker modal."""

from __future__ import annotations

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

DEFAULT_MODELS_DIR = os.path.expanduser("~/ai/models")


def discover_models(base: str = DEFAULT_MODELS_DIR) -> list[str]:
    root = Path(base)
    if not root.exists():
        return []
    return sorted(str(p) for p in root.rglob("*.gguf") if p.is_file())


def field_row(field_id: str, label: str, value: str = "") -> ComposeResult:
    yield Label(label, classes="field-label")
    yield Input(value=value, id=field_id, classes="field-input")


class ModelListItem(ListItem):
    def __init__(self, path: str) -> None:
        super().__init__(Static(path))
        self.model_path = path


class ModelPickerScreen(ModalScreen[str | None]):
    """Filterable list of discovered .gguf files under ~/ai/models."""

    DEFAULT_CSS = """
    ModelPickerScreen {
        align: center middle;
    }
    #picker-box {
        width: 90%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._all_models = discover_models()

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Label("Select a model (Esc to cancel)")
            yield Input(placeholder="filter...", id="filter-input")
            with VerticalScroll():
                yield ListView(*(ModelListItem(m) for m in self._all_models), id="model-list")

    def on_input_changed(self, event: Input.Changed) -> None:
        needle = event.value.lower()
        matches = [m for m in self._all_models if needle in m.lower()]
        list_view = self.query_one("#model-list", ListView)
        list_view.clear()
        for m in matches:
            list_view.append(ModelListItem(m))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.model_path)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
