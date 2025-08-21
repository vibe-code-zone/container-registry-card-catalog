"""
Debug Console Screen

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
from textual.containers import Horizontal
from textual.widgets import DataTable, Static, Header, Footer
from textual.screen import Screen
from textual.events import MouseDown


class ApiCallDetailsPanel(Static):
    """Right panel showing detailed API call information"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_info = None
    
    def update_call_info(self, call_info: dict):
        """Update the displayed API call information"""
        self.call_info = call_info
        if call_info:
            # Escape opening markup bracket
            url = str(call_info.get('url', 'Unknown')).replace('[', '\\[')
            method = str(call_info.get('method', 'UNKN'))
            status_code = call_info.get('status_code', 0)
            duration = str(call_info.get('duration_ms', 'Unknown'))
            size_bytes = str(call_info.get('size_bytes', 'Unknown'))
            timestamp = str(call_info.get('timestamp', 'Unknown'))
            
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
            
            # Use preview content (first 500 chars) for debug view
            if method == 'LOCAL':
                # LOCAL commands use 'response_content' for first 500 chars
                content_display = str(call_info.get('response_content', 'No content')).replace('[', '\\[')
            else:
                # HTTP requests use 'content_preview' for first 500 chars
                content_display = str(call_info.get('content_preview', 'No content')).replace('[', '\\[')
            
            # Different labels for local vs HTTP
            if method == 'LOCAL':
                details = f"""Method: {method}
Command: {url}
{status_emoji} {status_text}
Duration: {duration}ms
Size: {size_bytes} bytes
Time: {timestamp}
"""
            else:
                details = f"""Method: {method}
URL: {url}
{status_emoji} {status_text}
Duration: {duration}ms
Size: {size_bytes} bytes
Time: {timestamp}
"""
            
            # Handle command vs curl differently
            if method == 'LOCAL':
                details += f"""
Local Command:
{url}

Command Output:
{content_display}"""
            else:
                details += f"""
cURL Command:
curl -X {method} -i "{url}"

Response Preview:
{content_display}"""
            
            self.update(details)
        else:
            self.update("Select an API call to view details")
    
    def _format_headers(self, headers: dict) -> str:
        """Format headers for display"""
        if not headers:
            return "No headers"
        
        formatted = []
        for key, value in list(headers.items())[:5]:  # Show first 5 headers
            formatted.append(f"{key}: {value}")
        
        if len(headers) > 5:
            formatted.append(f"... and {len(headers) - 5} more")
        
        return "\n".join(formatted)


class DebugConsoleScreen(Screen):
    """Screen for viewing API call debug information"""
    
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    #api_call_list {
        width: 60%;
        border: solid $primary;
        margin: 1;
    }
    
    #api_call_details {
        width: 40%;
        border: solid $secondary;
        margin: 1;
        padding: 1;
    }
    """
    
    BINDINGS = [
        ("escape", "back", "Back"),
        ("backspace", "back", "Back"),
        ("ctrl+q", "quit", "Quit"),
        ("f5", "refresh", "Refresh"),
        ("ctrl+x", "purge", "Purge All"),
        ("ctrl+d", "no_action", ""),
    ]
    
    def __init__(self, mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.api_call_data = []
        self.mock_mode = mock_mode
        self.last_click_time = 0
        self.last_clicked_row = -1
    
    def compose(self) -> ComposeResult:
        """Create the debug console layout"""
        yield Header()
        with Horizontal():
            # Left panel - API call list
            api_table = DataTable(id="api_call_list", cursor_type="row")
            api_table.add_columns("Time", "Method", "Base URL", "Endpoint", "Status", "Size", "Duration")
            yield api_table
            
            # Right panel - API call details
            yield ApiCallDetailsPanel(id="api_call_details")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the debug console"""
        self.title = "Debug Console - API Calls"
        self.load_api_calls()
        # Show initial details
        details_panel = self.query_one("#api_call_details", ApiCallDetailsPanel)
        details_panel.update("Select an API call to view details")
    
    def load_api_calls(self) -> None:
        """Load API calls from registry manager"""
        from registry_client import registry_manager
        
        api_table = self.query_one("#api_call_list", DataTable)
        
        # Clear existing data
        api_table.clear()
        self.api_call_data = []
        
        # Load mock data if in mock mode and no real API calls exist
        if self.mock_mode and not registry_manager.api_call_log and not hasattr(registry_manager, '_mock_data_loaded'):
            from mock_data import mock_debug
            registry_manager.api_call_log.extend(mock_debug.get_mock_calls())
            registry_manager._mock_data_loaded = True
        
        # Load API calls from registry manager
        for call in registry_manager.api_call_log:
            # Extract base URL and endpoint from call data
            url = call.get("url", "")
            method = call.get("method", "UNKN")
            
            # For LOCAL commands, use the provided base_url and endpoint fields
            if method == "LOCAL":
                base_url = call.get("base_url", "local://unknown")
                endpoint = call.get("endpoint", url)
            else:
                # For HTTP requests, extract base URL and endpoint from full URL
                base_url = "Unknown"
                endpoint = url
                
                if "/v2/" in url:
                    parts = url.split("/v2/", 1)
                    base_url = parts[0]  # Everything before /v2/
                    endpoint_part = parts[1] if len(parts) > 1 else ""
                    endpoint = "/v2/" + endpoint_part
                else:
                    # If no /v2/, try to extract base URL anyway
                    if "://" in url:
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            base_url = f"{parsed.scheme}://{parsed.netloc}"
                            endpoint = parsed.path
                        except:
                            base_url = url
            
            # Format size
            size_bytes = call.get("size_bytes", 0)
            if size_bytes > 1024:
                size = f"{size_bytes / 1024:.1f}KB"
            else:
                size = f"{size_bytes}B"
            
            # Status with emoji
            status_code = call.get("status_code", 0)
            method = call.get("method", "UNKN")
            
            if method == "LOCAL":
                # For LOCAL commands, 0 is success, anything else is error
                if status_code == 0:
                    status = f"✅ {status_code}"
                else:
                    status = f"❌ {status_code}"
            else:
                # For HTTP requests, 200 is success
                if status_code == 200:
                    status = f"✅ {status_code}"
                elif status_code == 0:
                    status = "❌ ERR"
                else:
                    status = f"⚠ {status_code}"
            
            api_table.add_row(
                call.get("timestamp", "Unknown"),
                call.get("method", "UNKN"),
                base_url,
                endpoint,
                status,
                size,
                f"{call.get('duration_ms', 0):,}ms"
            )
            self.api_call_data.append(call)
        
        # Auto-select last row (most recent call)
        if self.api_call_data:
            last_row = len(self.api_call_data) - 1
            api_table.cursor_coordinate = (last_row, 0)
            self.update_details_for_row(last_row)
    
    def update_details_for_row(self, row_index: int) -> None:
        """Update details panel for given row index"""
        details_panel = self.query_one("#api_call_details", ApiCallDetailsPanel)
        
        if row_index < len(self.api_call_data):
            call = self.api_call_data[row_index]
            details_panel.update_call_info(call)
    
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle API call row highlighting (auto-select)"""
        self.update_details_for_row(event.cursor_row)
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle API call selection and double-click detection"""
        # Only handle events if this is the DebugConsoleScreen
        if not isinstance(self, DebugConsoleScreen):
            return
            
        import time
        current_time = time.time()
        
        # Double-click detection (within 500ms of previous click on same row)
        if (current_time - self.last_click_time < 0.5 and 
            self.last_clicked_row == event.cursor_row and
            event.cursor_row < len(self.api_call_data)):
            
            # Double-click detected - show API detail modal
            self.show_api_detail_modal(self.api_call_data[event.cursor_row])
            event.stop()  # Prevent event bubbling
        else:
            # Single click - update details
            self.update_details_for_row(event.cursor_row)
        
        # Update click tracking and stop event bubbling
        self.last_click_time = current_time
        self.last_clicked_row = event.cursor_row
        event.stop()  # Prevent event bubbling
    
    def on_key(self, event) -> None:
        """Handle key presses"""
        # Only handle ENTER if we're focused on the debug console specifically
        if event.key == "enter":
            # Check if the API table is focused
            api_table = self.query_one("#api_call_list", DataTable)
            if api_table.has_focus and hasattr(api_table, 'cursor_coordinate') and api_table.cursor_coordinate:
                row_index = api_table.cursor_coordinate[0]
                if row_index < len(self.api_call_data):
                    self.show_api_detail_modal(self.api_call_data[row_index])
                event.stop()  # Prevent event bubbling
    
    def show_api_detail_modal(self, call_data: dict) -> None:
        """Show API call details in modal"""
        from api_detail_modal import ApiDetailModal
        
        # Find the index of the selected call
        api_table = self.query_one("#api_call_list", DataTable)
        current_index = api_table.cursor_coordinate[0] if hasattr(api_table, 'cursor_coordinate') and api_table.cursor_coordinate else 0
        
        # Pass all API calls and current index for navigation
        modal = ApiDetailModal(self.api_call_data, current_index)
        self.app.push_screen(modal)
    
    def action_refresh(self) -> None:
        """Refresh API call list"""
        self.load_api_calls()
        self.notify("API call list refreshed")
    
    # def on_mouse_down(self, event: MouseDown) -> None:
    #     """Handle mouse button events"""
    #     # Mouse back button (button 3 or 4 depending on system)
    #     if hasattr(event, 'button') and event.button in [3, 4]:
    #         self.action_back()
    
    def action_back(self) -> None:
        """Go back to previous screen"""
        self.app.pop_screen()
    
    def action_purge(self) -> None:
        """Purge all API call data"""
        from registry_client import registry_manager
        
        # Clear the registry manager's API call log
        registry_manager.api_call_log.clear()
        
        # Reset mock data flag so it can be loaded again if needed
        if hasattr(registry_manager, '_mock_data_loaded'):
            delattr(registry_manager, '_mock_data_loaded')
        
        # If in mock mode, immediately reload mock data after purging
        if self.mock_mode:
            from mock_data import mock_debug
            registry_manager.api_call_log.extend(mock_debug.get_mock_calls())
            registry_manager._mock_data_loaded = True
            self.notify("API call log purged and reseeded with mock data", severity="warning")
        else:
            self.notify("API call log purged", severity="warning")
        
        # Reload the list
        self.load_api_calls()
    
    def action_no_action(self) -> None:
        """Do nothing - prevents Ctrl+D from opening debug console within debug console"""
        pass
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()
