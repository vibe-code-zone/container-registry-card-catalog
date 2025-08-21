"""
API Detail Modal

AI Attribution (AIA): EAI Hin R Claude Code v1.0
Full: AIA Entirely AI, Human-initiated, Reviewed, Claude Code v1.0
Expanded: This work was entirely AI-generated. AI was prompted for its contributions, 
or AI assistance was enabled. AI-generated content was reviewed and approved. 
The following model(s) or application(s) were used: Claude Code.
Interpretation: https://aiattribution.github.io/interpret-attribution
More: https://aiattribution.github.io/
Vibe-Coder: Andrew Potozniak <potozniak@redhat.com>
Session Date: 2025-08-15
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Button, DataTable
from textual.screen import ModalScreen


class ApiDetailModal(ModalScreen):
    """Modal screen for displaying full API call details with navigation"""
    
    CSS = """
    ApiDetailModal {
        align: center middle;
    }
    
    #modal_container {
        width: 90%;
        height: 80%;
        border: solid $primary;
        background: $surface;
        layout: vertical;
    }
    
    #panes_container {
        height: 1fr;
        padding: 1;
        layout: horizontal;
    }
    
    #request_pane {
        width: 50%;
        margin-right: 1;
        layout: vertical;
    }
    
    #response_pane {
        width: 50%;
        layout: vertical;
    }
    
    .pane_title {
        height: 1;
        text-align: center;
        background: $boost;
        color: $text;
        border: solid $accent;
    }
    
    .pane_content {
        height: 1fr;
        padding: 1;
        border: solid $accent;
        border-top: none;
        overflow-y: auto;
    }
    
    #button_container {
        height: 3;
        dock: bottom;
        align: center middle;
    }
    
    Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        ("pageup", "prev_call", "Previous Call"),
        ("pagedown", "next_call", "Next Call"),
        ("up", "prev_call", "Previous Call"),
        ("down", "next_call", "Next Call"),
        ("escape", "close", "Close"),
        ("backspace", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self, api_calls_data: list, current_index: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.api_calls_data = api_calls_data
        self.current_index = current_index
    
    def compose(self) -> ComposeResult:
        """Create the modal layout"""
        with Vertical(id="modal_container"):
            # Two panes for request and response
            with Horizontal(id="panes_container"):
                # Request pane
                with Vertical(id="request_pane"):
                    yield Static("REQUEST", classes="pane_title")
                    with ScrollableContainer(classes="pane_content"):
                        yield Static(self._format_request(), id="request_content")
                
                # Response pane
                with Vertical(id="response_pane"):
                    yield Static("RESPONSE", classes="pane_title")
                    with ScrollableContainer(classes="pane_content"):
                        yield Static(self._format_response(), id="response_content")
            
            # Button container at bottom
            with Horizontal(id="button_container"):
                yield Button("OK", id="ok_btn", variant="primary")
    
    def _get_title(self) -> str:
        """Get modal title with navigation info"""
        current_call = self.api_calls_data[self.current_index]
        total = len(self.api_calls_data)
        return f"API Call {self.current_index + 1} of {total} - {current_call.get('url', 'Unknown')} | PageUp/PageDown to navigate"
    
    def _format_request(self) -> str:
        """Format the request details"""
        call = self.api_calls_data[self.current_index]
        
        method = call.get('method', 'UNKN')
        url = call.get('url', 'Unknown')
        
        # Escape opening markup bracket
        escaped_url = str(url).replace('[', '\\[')
        
        # Different labels for local vs HTTP
        if method == 'LOCAL':
            content_lines = [
                f"Method: {method}",
                f"Command: {escaped_url}",
                f"Timestamp: {call.get('timestamp', 'Unknown')}",
                ""
            ]
            content_lines.extend([
                "Local Command:",
                f"{escaped_url}",
                ""
            ])
        else:
            content_lines = [
                f"Method: {method}",
                f"URL: {escaped_url}",
                f"Timestamp: {call.get('timestamp', 'Unknown')}",
                ""
            ]
            content_lines.extend([
                "cURL Command:",
                f"curl -X {method} -i \"{escaped_url}\""
            ])
        
        return "\n".join(content_lines)
    
    def _format_response(self) -> str:
        """Format the response details"""
        call = self.api_calls_data[self.current_index]
        
        status_code = call.get("status_code", 0)
        method = call.get('method', 'UNKN')
        
        # Different status handling for local vs HTTP
        if method == 'LOCAL':
            if status_code == 0:
                status_emoji = "✅"
                status_text = f"Exit Code: 0 (Success)"
            else:
                status_emoji = "❌"
                status_text = f"Exit Code: {status_code} (Error)"
        else:
            status_emoji = "✅" if status_code == 200 else "❌"
            status_text = f"HTTP Status: {status_code}"
        
        content_lines = [
            f"{status_emoji} {status_text}",
            f"Duration: {call.get('duration_ms', 'Unknown')}ms",
            f"Size: {call.get('size_bytes', 'Unknown')} bytes",
            ""
        ]
        
        # Show full response content if available, otherwise fall back to preview
        full_content = call.get('response_content_full')
        if full_content:
            # Escape opening markup bracket
            escaped_content = str(full_content).replace('[', '\\[')
            if method == 'LOCAL':
                content_lines.extend([
                    "Command Output:",
                    f"{escaped_content}"
                ])
            else:
                content_lines.extend([
                    "Response Body:",
                    f"{escaped_content}"
                ])
        else:
            # Fallback to preview
            escaped_preview = str(call.get('content_preview', 'No content available')).replace('[', '\\[')
            content_lines.extend([
                "Response Body (Preview):",
                f"{escaped_preview}"
            ])
        
        # Add error info if available
        if call.get('error'):
            content_lines.extend(["", "Error Details:", f"{call.get('error')}"])
        
        return "\n".join(content_lines)
    
    def _update_content(self):
        """Update the modal content for current index"""
        # Update request content
        request_widget = self.query_one("#request_content", Static)
        request_widget.update(self._format_request())
        
        # Update response content
        response_widget = self.query_one("#response_content", Static)
        response_widget.update(self._format_response())
    
    def action_prev_call(self) -> None:
        """Navigate to previous API call"""
        if self.current_index > 0:
            self.current_index -= 1
            self._update_content()
            self._update_parent_selection()
    
    def action_next_call(self) -> None:
        """Navigate to next API call"""
        if self.current_index < len(self.api_calls_data) - 1:
            self.current_index += 1
            self._update_content()
            self._update_parent_selection()
    
    def _update_parent_selection(self) -> None:
        """Update the parent debug console selection"""
        try:
            # Find the debug console screen in the stack
            debug_screen = None
            for screen in self.app.screen_stack:
                if hasattr(screen, '__class__') and screen.__class__.__name__ == 'DebugConsoleScreen':
                    debug_screen = screen
                    break
            
            if debug_screen and hasattr(debug_screen, 'api_call_data'):
                try:
                    # Update the cursor position in the API call list
                    api_table = debug_screen.query_one("#api_call_list", DataTable)
                    if api_table:
                        # Ensure we don't go out of bounds and table has rows
                        max_rows = api_table.row_count
                        data_length = len(debug_screen.api_call_data)
                        
                        if max_rows > 0 and 0 <= self.current_index < min(max_rows, data_length):
                            # Set cursor coordinate directly (move_cursor might not work in all cases)
                            api_table.cursor_coordinate = (self.current_index, 0)
                            # Update the details panel
                            if hasattr(debug_screen, 'update_details_for_row'):
                                debug_screen.update_details_for_row(self.current_index)
                except Exception as e:
                    # For debugging - uncomment to see errors
                    # self.notify(f"Parent update error: {str(e)}", severity="error")
                    pass
        except Exception:
            pass
    
    def action_close(self) -> None:
        """Close the modal"""
        self.dismiss()
    
    def on_key(self, event) -> None:
        """Handle key presses in modal"""
        if event.key == "enter":
            # ENTER should close the modal
            self.dismiss()
            event.stop()
            event.prevent_default()
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press"""
        if event.button.id == "ok_btn":
            self.dismiss()
