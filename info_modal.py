"""
Info/About Modal for Container Registry Card Catalog

AIA: EAI Hin R Claude Code v1.0
Vibe-Coder: Andrew Potozniak <potozniak@redhat.com>
Session Date: 2025-08-28
"""

from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static
from textual.binding import Binding

import sys
import os

# Check if running as script from source directory
if __name__ == "__main__" or os.path.basename(sys.argv[0]).endswith('.py'):
    app_version = "FROM-SOURCE"
else:
    # Try to get installed version
    try:
        from importlib.metadata import version
        app_version = version("container-registry-card-catalog")
    except Exception:
        app_version = "FROM-SOURCE"


class InfoModal(ModalScreen):
    """Modal screen displaying application information and credits"""
    
    BINDINGS = [
        ("escape", "close", "Close"),
        ("i", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def on_key(self, event) -> None:
        """Handle key presses in modal"""
        if event.key == "enter":
            # ENTER should close the modal
            self.dismiss()
            event.stop()
            event.prevent_default()
    
    def action_close(self) -> None:
        """Close the modal"""
        self.dismiss()
    
    CSS = """
    InfoModal {
        align: center middle;
    }
    
    #info_dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: auto;
        padding: 1 2;
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
    }
    
    .info_label {
        content-align: right middle;
        text-align: right;
        color: $text;
        margin: 0;
        padding-right: 1;
    }
    
    .info_value {
        content-align: left middle; 
        text-align: left;
        color: $accent;
        margin: 0;
        padding-left: 1;
    }
    
    .info_header {
        content-align: center middle;
        text-align: center;
        color: $warning;
        text-style: bold;
        margin: 1 0;
    }
    
    .info_tagline {
        content-align: center middle;
        text-align: center;
        color: $success;
        text-style: italic;
        margin: 1 0;
    }
    
    #info_close_button {
        column-span: 2;
        margin: 1 0;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose the info modal interface"""
        with Center():
            with Middle():
                with Static(id="info_dialog"):
                    yield Label("Container Registry Card Catalog - Beta", classes="info_header")
                    yield Label("Serve the Vibes", classes="info_tagline")
                    
                    yield Label("Version:", classes="info_label")
                    yield Label(app_version, classes="info_value")
                    
                    yield Label("Release Date:", classes="info_label") 
                    yield Label("2025-08-28", classes="info_value")
                    
                    yield Label("Author:", classes="info_label")
                    yield Label("Andrew Potozniak <potozniak@redhat.com>", classes="info_value")
                    
                    yield Label("License:", classes="info_label")
                    yield Label("MIT + VCL-0.1-Experimental", classes="info_value")
                    
                    yield Label("AIA:", classes="info_label")
                    yield Label("[EAI Hin R Claude Code v1.0]", classes="info_value")
                    
                    yield Label("Repository:", classes="info_label")
                    yield Label("github.com/vibe-code-zone/container-registry-card-catalog", classes="info_value")
                    
                    yield Button("Close", variant="primary", id="info_close_button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events"""
        if event.button.id == "info_close_button":
            self.dismiss()
    
    def action_dismiss(self) -> None:
        """Dismiss the modal"""
        self.dismiss()