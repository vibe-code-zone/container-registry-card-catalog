#!/usr/bin/env python3
"""
Container Card Catalog TUI

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

import argparse
import asyncio
import logging
import sys
from typing import List, Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static, Header, Footer, Button, Input
from textual.screen import Screen
from textual.events import MouseDown
from textual.message import Message

from mock_data import mock_registry
from registry_client import registry_manager
from local_container_client import LocalContainerClient
from debug_console import DebugConsoleScreen
from tags_view import TagsScreen
from registry_config_modal import RegistryConfigModal


class TUIDebugLogger:
    """Debug logger for TUI operations"""
    
    def __init__(self, enabled: bool = False, verbose: bool = False, debug_file_path: str = None):
        self.enabled = enabled
        self.verbose = verbose
        if enabled:
            # Use provided path or default
            if debug_file_path is None:
                debug_file_path = '/tmp/container-registry-tui-debug.log'
            
            # Set up file logging for debug mode (file only, no console output)
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s [TUI-DEBUG] %(name)s: %(message)s',
                handlers=[
                    logging.FileHandler(debug_file_path)
                ]
            )
            
            # Configure specific logger levels to reduce noise
            if not verbose:
                # Silence noisy HTTP libraries unless verbose mode
                logging.getLogger('httpcore').setLevel(logging.WARNING)
                logging.getLogger('httpx').setLevel(logging.WARNING)
                logging.getLogger('urllib3').setLevel(logging.WARNING)
                logging.getLogger('requests').setLevel(logging.WARNING)
                
            self.logger = logging.getLogger('TUI-Operations')
            mode_text = "VERBOSE" if verbose else "STANDARD"
            self.logger.info(f"=== TUI Debug Mode ({mode_text}) Enabled - Logging to: {debug_file_path} ===")
        else:
            self.logger = None
    
    def _mask_sensitive_data(self, key: str, value: str) -> str:
        """Mask sensitive data like passwords, tokens, and auth headers"""
        sensitive_keywords = [
            # Passwords and passphrases
            'password', 'passwd', 'pass', 'passphrase', 'pwd',
            # Actual tokens and credentials (but not metadata about them)
            'cached_token', 'access_token', 'refresh_token', 'bearer_token',
            'credential', 'cred', 'creds', 'credentials',
            # Authentication secrets (but not types like auth_type)
            'authorization', 'authenticate', 
            # API keys and secrets
            'secret', 'private', 'api_key', 'apikey', 'access_key',
            # Robot and service accounts
            'robot_token', 'service_token', 'service_key',
            # OAuth and JWT actual tokens
            'oauth_token', 'jwt_token',
            # Registry specific tokens
            'registry_token', 'docker_token', 'quay_token',
            # Headers that contain auth
            'x-auth', 'www-authenticate'
        ]
        
        # Check if key contains sensitive keywords
        if any(keyword in key.lower() for keyword in sensitive_keywords):
            if isinstance(value, str) and len(value) > 0:
                if len(value) <= 8:
                    return "[REDACTED]"
                else:
                    # Show first 3 and last 3 characters for identification
                    return f"{value[:3]}...{value[-3:]}"
            else:
                return "[REDACTED]"
        
        return str(value)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with optional context"""
        if self.enabled and self.logger:
            # Mask sensitive data in kwargs
            safe_kwargs = {k: self._mask_sensitive_data(k, v) for k, v in kwargs.items()}
            context = ", ".join(f"{k}={v}" for k, v in safe_kwargs.items())
            full_message = f"{message}" + (f" | {context}" if context else "")
            self.logger.debug(full_message)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if self.enabled and self.logger:
            # Mask sensitive data in kwargs
            safe_kwargs = {k: self._mask_sensitive_data(k, v) for k, v in kwargs.items()}
            context = ", ".join(f"{k}={v}" for k, v in safe_kwargs.items())
            full_message = f"{message}" + (f" | {context}" if context else "")
            self.logger.info(full_message)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        if self.enabled and self.logger:
            # Mask sensitive data in kwargs
            safe_kwargs = {k: self._mask_sensitive_data(k, v) for k, v in kwargs.items()}
            context = ", ".join(f"{k}={v}" for k, v in safe_kwargs.items())
            full_message = f"{message}" + (f" | {context}" if context else "")
            self.logger.error(full_message)


# Global debug logger instance
debug_logger = TUIDebugLogger()


class RegistryDetailsPanel(Vertical):
    """Right panel showing detailed registry information with configure button"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.registry_info = None
        self.parent_app = None
    
    def compose(self) -> ComposeResult:
        """Create the layout with details and button"""
        yield Static("Select a registry to view details", id="registry_details_text")
        yield Button("Configure Registry", id="configure_button", variant="primary", classes="config_button")
    
    def set_parent_app(self, app):
        """Set reference to parent app for button actions"""
        self.parent_app = app
    
    def update_registry_info(self, registry_info: dict):
        """Update the displayed registry information"""
        self.registry_info = registry_info
        details_text = self.query_one("#registry_details_text", Static)
        configure_button = self.query_one("#configure_button", Button)
        
        if registry_info:
            base_url = registry_info.get('url', 'Unknown')
            registry_hash = registry_info.get('registry_hash', 'Unknown')
            
            # Handle different registry types
            if base_url.startswith('local://'):
                runtime = base_url.split('://')[1]
                details = f"""🏠 Local Runtime: {runtime.title()}
📡 Endpoint: {base_url}
🛠️ Commands: {runtime} images, {runtime} inspect
👤 User: {registry_info.get('username', 'Current system user')}
🔐 Auth: {registry_info.get('auth_type', 'System access')}
🕐 Last Checked: {registry_info.get('last_checked', 'Just now')}
⚡ Response Time: {registry_info.get('response_time', 'N/A')}
📦 Repositories: {registry_info.get('repo_count', 'Unknown')}
🏷️ API Version: {registry_info.get('api_version', 'Local Cache')}
🔗 Connection: {registry_info.get('connection_status', 'Local filesystem')}
🔗 Runtime Hash: {registry_hash}"""
            elif base_url.startswith('mock://'):
                details = f"""🧪 Mock Registry: {base_url.split('://')[-1].title()}
📡 Endpoint: {base_url}
🌐 API Check: Mock API simulation
👤 User: {registry_info.get('username', 'Mock user')}
🔐 Auth: {registry_info.get('auth_type', 'Mock authentication')}
🕐 Last Checked: {registry_info.get('last_checked', 'Mock time')}
⚡ Response Time: {registry_info.get('response_time', 'Mock timing')}
📦 Repositories: {registry_info.get('repo_count', 'Unknown')}
🏷️ API Version: {registry_info.get('api_version', 'v2 (Mock)')}
🔗 Connection: {registry_info.get('connection_status', 'Mock')}
🔗 Registry Hash: {registry_hash}"""
            else:
                # Standard HTTP registry
                details = f"""📡 Endpoint: {base_url}
🌐 API Check: {base_url}/v2/
👤 User: {registry_info.get('username', 'Anonymous')}
🔐 Auth: {registry_info.get('auth_type', 'None')}
🕐 Last Checked: {registry_info.get('last_checked', 'Never')}
⚡ Response Time: {registry_info.get('response_time', 'N/A')}
📦 Repositories: {registry_info.get('repo_count', 'Unknown')}
🏷️ API Version: {registry_info.get('api_version', 'Unknown')}
🔗 Connection: {registry_info.get('connection_status', 'Unknown')}
🔗 Registry Hash: {registry_hash}"""
            # TODO: Add SSL status validation once SSL verification is implemented
            
            details_text.update(details)
            configure_button.disabled = False
        else:
            details_text.update("Select a registry to view details")
            configure_button.disabled = True
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle configure button press"""
        if event.button.id == "configure_button" and self.parent_app:
            # Trigger the configure action on the parent app
            self.parent_app.action_configure_registry()


class RepositoryDetailsPanel(Static):
    """Right panel showing detailed repository information"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repository_info = None
    
    def update_repository_info(self, repository_info: dict):
        """Update the displayed repository information"""
        self.repository_info = repository_info
        if repository_info:
            registry_url = repository_info.get('registry_url', 'Unknown')
            repo_name = repository_info.get('name', 'Unknown')
            recent_tags = repository_info.get('recent_tags', [])
            
            # Build pull commands for recent tags
            pull_commands = ""
            if recent_tags:
                if registry_url.startswith('local://'):
                    # For local containers, show tag/copy commands instead of pull
                    runtime = registry_url.split('://')[1]
                    pull_commands = f"\n\n🏷️ Local {runtime.title()} Commands:\n"
                    tag_details = repository_info.get('tag_details', {})
                    for i, tag in enumerate(recent_tags):
                        if i > 0:  # Add separator between different images
                            pull_commands += "\n"
                        
                        if tag.startswith('sha256:'):
                            # Digest-only image - use full digest
                            full_digest = tag_details.get(tag, {}).get('full_digest', tag)
                            pull_commands += f"{runtime} inspect {repo_name}@{full_digest}\n"
                            pull_commands += f"{runtime} tag {repo_name}@{full_digest} {repo_name}:latest\n"
                        else:
                            # Normal tag
                            pull_commands += f"{runtime} inspect {repo_name}:{tag}\n"
                            pull_commands += f"{runtime} save -o {repo_name}-{tag}.tar {repo_name}:{tag}\n"
                else:
                    # For remote registries, show normal pull commands
                    pull_commands = "\n\n📥 Pull Commands:\n"
                    for tag in recent_tags:
                        full_image = f"{registry_url}/{repo_name}:{tag}"
                        pull_commands += f"podman image pull {full_image}\n"
            
            latest_hash = repository_info.get('latest_hash', 'Unknown')
            
            # Different details for local vs remote registries
            if registry_url.startswith('local://'):
                runtime = registry_url.split('://')[1]
                details = f"""📦 Repository: {repo_name}
🏠 Runtime: {runtime.title()}
🔍 Base Command: {runtime} images --format json
🏷️ Filter Command: {runtime} images --format json | jq '.[] | select((.RepoTags[]? | contains("{repo_name}")) or (.RepoDigests[]? | contains("{repo_name}")) or (.Names[]? | contains("{repo_name}")))'
🏷️ Total Tags: {repository_info.get('tag_count', 'Unknown')}
📅 Last Tag Push: {repository_info.get('last_updated', 'Unknown')}
📏 Size: {repository_info.get('size', 'Unknown')}
📋 Description: {repository_info.get('description', 'No description')}
🔗 Latest Hash: {latest_hash}
🏢 Registry: {registry_url}{pull_commands}"""
            else:
                details = f"""📦 Repository: {repo_name}
🌐 Catalog API: {registry_url}/v2/_catalog
🏷️ Tags API: {registry_url}/v2/{repo_name}/tags/list
🏷️ Total Tags: {repository_info.get('tag_count', 'Unknown')}
📅 Last Tag Push: {repository_info.get('last_updated', 'Unknown')}
📏 Size: {repository_info.get('size', 'Unknown')}
🔄 Pulls: {repository_info.get('pulls', 'Unknown')}
📋 Description: {repository_info.get('description', 'No description')}
🔗 Latest Hash: {latest_hash}
🏢 Registry: {registry_url}{pull_commands}"""
            self.update(details)
        else:
            self.update("Select a repository to view details")


class RepositoryScreen(Screen):
    """Screen for browsing repositories within a selected registry"""
    
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    .left_panel {
        width: 60%;
    }
    
    #repository_filter {
        border: solid $primary;
        margin: 1;
        height: 3;
    }
    
    #repository_list {
        border: solid $primary;
        margin: 1;
        height: 1fr;
    }
    
    #repository_details {
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
        ("ctrl+d", "debug_console", "Debug Console"),
        ("ctrl+f", "focus_filter", "Focus Filter"),
        ("tab", "toggle_focus", "Toggle Focus"),
        ("f5", "refresh", "Refresh"),
        ("r", "reverse_sort", "Reverse Sort"),
        ("l", "load_more", "Load More"),
    ]
    
    def __init__(self, registry_info: dict, mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.registry_info = registry_info
        self.mock_mode = mock_mode
        self.repository_data = []
        self.current_limit = 1000
        self.all_repositories_loaded = False
        self.last_scroll_load_time = 0
        self.last_click_time = 0
        self.last_clicked_row = -1
        self.sort_reversed = False
        # Pagination state tracking for Link header continuation
        self.next_page_token = None
        self.last_page_size = 100
        self.pagination_method = "unknown"  # "link_header" or "offset_based"
        # Filtering state
        self.filter_text = ""
        self.filtered_repository_data = []  # Filtered view of repository_data
    
    def is_filter_active(self) -> bool:
        """Check if repository filter is currently active"""
        return bool(self.filter_text.strip())
    
    def apply_filter(self) -> None:
        """Apply current filter to repository data and update table"""
        if not self.filter_text.strip():
            # No filter - show all repositories
            self.filtered_repository_data = self.repository_data.copy()
        else:
            # Filter by repository name (case-insensitive substring match)
            filter_lower = self.filter_text.lower()
            self.filtered_repository_data = [
                repo for repo in self.repository_data 
                if filter_lower in repo["name"].lower()
            ]
        
        # Rebuild table with filtered data
        self.rebuild_repository_table()
        
        # Update title to show filter status
        self.update_title()
    
    def rebuild_repository_table(self) -> None:
        """Rebuild the repository table with current filtered data"""
        repo_table = self.query_one("#repository_list", DataTable)
        repo_table.clear()
        
        for repo_data in self.filtered_repository_data:
            repo_table.add_row(
                "📦",
                self.registry_info.get('name', 'Unknown'),
                repo_data["name"],
                str(repo_data.get("tag_count", "Unknown")),
                repo_data.get("recent_tags_display", "Unknown"),
                repo_data.get("last_updated", "Unknown")
            )
        
        # Auto-select first row if data exists
        if self.filtered_repository_data:
            repo_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
            # Focus table after filtering unless filter input has focus
            filter_input = self.query_one("#repository_filter", Input)
            if not filter_input.has_focus:
                repo_table.focus()
    
    def compose(self) -> ComposeResult:
        """Create the repository view layout"""
        yield Header()
        with Horizontal():
            # Left panel - Repository list with filter
            with Vertical(classes="left_panel"):
                yield Input(placeholder="Filter repository names...", id="repository_filter")
                repo_table = DataTable(id="repository_list", cursor_type="row")
                repo_table.add_columns("📦", "Registry", "Repository Name", "Tags", "Recent Tags", "Last Tag Push")
                yield repo_table
            
            # Right panel - Repository details
            yield RepositoryDetailsPanel(id="repository_details")
        yield Footer()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle repository filter input changes"""
        if event.input.id == "repository_filter":
            self.filter_text = event.value
            self.apply_filter()
    
    def on_mount(self) -> None:
        """Initialize the repository view"""
        self.update_title()
        self.load_repositories()
        # Show initial details
        details_panel = self.query_one("#repository_details", RepositoryDetailsPanel)
        details_panel.update("Select a repository to view details")
    
    def update_title(self):
        """Update the title to show loading state and filter status"""
        registry_name = self.registry_info.get('name', 'Unknown Registry')
        total_loaded = len(self.repository_data)
        
        if self.is_filter_active():
            # Show filter status
            filtered_count = len(self.filtered_repository_data)
            self.title = f"Repositories - {registry_name} ({filtered_count} matches from {total_loaded} loaded)"
        else:
            # Show normal loading status
            if self.all_repositories_loaded:
                self.title = f"Repositories - {registry_name} ({total_loaded} total)"
            elif total_loaded > 0:
                self.title = f"Repositories - {registry_name} ({total_loaded} loaded, more available...)"
            else:
                self.title = f"Repositories - {registry_name} (loading...)"
    
    def load_repositories(self) -> None:
        """Load repositories for the selected registry"""
        repo_table = self.query_one("#repository_list", DataTable)
        details_panel = self.query_one("#repository_details", Static)
        
        registry_url = self.registry_info.get('url', '')
        
        if self.mock_mode and registry_url:
            # Map any registry URL to a mock registry when in mock mode
            if registry_url.startswith("mock://"):
                mock_url = registry_url
            else:
                # Map real registry URLs to mock equivalents
                if "quay.io" in registry_url:
                    mock_url = "mock://quay-io"
                elif "gcr.io" in registry_url:
                    mock_url = "mock://gcr-io"
                else:
                    mock_url = "mock://public-registry"  # Default fallback
            
            # Get repositories from mock data based on mapped registry
            catalog_response = mock_registry.get_catalog(mock_url)
            if catalog_response["status_code"] == 200:
                all_repositories = catalog_response["json"]["repositories"]
                
                # Respect the current limit for auto-loading behavior
                repositories = all_repositories[:self.current_limit]
                
                # Check if we've loaded all available repositories
                if len(repositories) >= len(all_repositories):
                    self.all_repositories_loaded = True
                
                for repo_name in repositories:
                    # Get mock tag data for each repository using the mapped mock URL
                    tags_response = mock_registry.get_tags(mock_url, repo_name)
                    if tags_response["status_code"] == 200:
                        all_tags = tags_response["json"]["tags"]
                        tag_count = len(all_tags)
                        
                        # Get recent tags (exclude 'latest', take up to 3)
                        recent_tags = [tag for tag in all_tags if tag != "latest"][:3]
                        recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
                    else:
                        tag_count = 0
                        recent_tags = []
                        recent_tags_display = "Unknown"
                    
                    repo_data = {
                        "name": repo_name,
                        "tag_count": tag_count,
                        "recent_tags": recent_tags,
                        "recent_tags_display": recent_tags_display,
                        "last_updated": "Mock time"
                    }
                    
                    self.repository_data.append(repo_data)
                
                # Apply filter to populate table
                self.apply_filter()
            else:
                # Fallback if registry not found in mock data
                details_panel.update(f"No repositories found for {registry_url}")
                return
        else:
            # Real registry mode - start background task to load repositories
            self.run_worker(self.load_real_repositories(), exclusive=True)
    
    def update_details_for_row(self, row_index: int) -> None:
        """Update details panel for given row index"""
        details_panel = self.query_one("#repository_details", RepositoryDetailsPanel)
        
        # Use filtered data for display, fallback to full data if filter not applied
        data_to_use = self.filtered_repository_data if self.filtered_repository_data else self.repository_data
        
        if row_index < len(data_to_use):
            repo = data_to_use[row_index]
            
            # Create detailed info for selected repository
            detailed_info = {
                "name": repo["name"],
                "tag_count": repo.get("tag_count", repo.get("tags", "Unknown")),
                "recent_tags": repo.get("recent_tags", []),
                "tag_details": repo.get("tag_details", {}),  # Include tag details with full digests
                "last_updated": repo["last_updated"],
                "size": "42.3 MB" if self.mock_mode else repo.get("size", "Unknown"),
                "description": f"Mock {repo['name']} container" if self.mock_mode else repo.get("description", "No description available"),
                "registry_url": self.registry_info.get('url', 'Unknown'),
                "latest_hash": f"sha256:mock{hash(repo['name']) % 1000000:06d}" if self.mock_mode else repo.get("latest_hash", "Unknown")
            }
            
            details_panel.update_repository_info(detailed_info)
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle repository selection and double-click detection"""
        # Only handle events if this is the RepositoryScreen
        if not isinstance(self, RepositoryScreen):
            return
            
        import time
        current_time = time.time()
        
        # Double-click detection (within 500ms of previous click on same row)
        if (current_time - self.last_click_time < 0.5 and 
            self.last_clicked_row == event.cursor_row and
            event.cursor_row < len(self.repository_data)):
            
            # Double-click detected - navigate to tags
            repo = self.repository_data[event.cursor_row]
            self.navigate_to_tags(repo)
            event.stop()  # Prevent event bubbling
        else:
            # Single click - update details
            self.update_details_for_row(event.cursor_row)
        
        # Update click tracking and stop event bubbling
        self.last_click_time = current_time
        self.last_clicked_row = event.cursor_row
        event.stop()  # Prevent event bubbling
    
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle repository row highlighting (auto-select)"""
        self.update_details_for_row(event.cursor_row)
        
        # Auto-load more repositories when approaching the bottom
        current_row = event.cursor_row
        total_rows = len(self.repository_data)
        rows_from_bottom = total_rows - current_row
        
        debug_logger.debug("Row highlighted - checking auto-load trigger", 
                          current_row=current_row,
                          total_rows=total_rows,
                          rows_from_bottom=rows_from_bottom,
                          all_loaded=self.all_repositories_loaded,
                          has_next_token=bool(self.next_page_token),
                          pagination_method=self.pagination_method)
        
        if not self.all_repositories_loaded and not self.is_filter_active():
            # Load more when within 10 rows of the bottom (but not when filter is active)
            if rows_from_bottom <= 10:
                debug_logger.debug("AUTO-LOAD TRIGGERED - Row highlighting", 
                                  trigger_reason="within_10_rows_of_bottom",
                                  current_row=current_row,
                                  total_rows=total_rows)
                self.notify(f"📦 Loading more repositories... ({total_rows} loaded)", timeout=2)
                if self.mock_mode:
                    self.load_more_mock_repositories()
                else:
                    self.run_worker(self.load_more_repositories(), exclusive=True)
            else:
                debug_logger.debug("Auto-load NOT triggered - not close enough to bottom", 
                                  rows_from_bottom=rows_from_bottom,
                                  threshold=10)
    
    def on_message(self, message: Message) -> None:
        """Handle scroll messages for auto-loading"""
        # Check if this is a scroll message from the repository table
        if hasattr(message, 'sender') and hasattr(message.sender, 'id') and message.sender.id == "repository_list":
            if not self.all_repositories_loaded and not self.is_filter_active() and str(type(message).__name__) == "Scroll":
                import time
                current_time = time.time()
                
                # Throttle scroll-based loading to prevent excessive requests (2 second cooldown)
                if current_time - self.last_scroll_load_time < 2:
                    return
                
                repo_table = self.query_one("#repository_list", DataTable)
                
                # Get scroll information
                if hasattr(repo_table, 'scroll_offset'):
                    scroll_y = repo_table.scroll_offset.y
                    total_height = repo_table.virtual_size.height
                    visible_height = repo_table.size.height
                    
                    # Check if we're scrolled near the bottom (within 90% of total scroll)
                    if total_height > 0 and (scroll_y + visible_height) / total_height > 0.9:
                        total_rows = len(self.repository_data)
                        if total_rows > 0:  # Only load if we have data
                            self.last_scroll_load_time = current_time
                            self.notify(f"📦 Loading more repositories... ({total_rows} loaded)", timeout=2)
                            if self.mock_mode:
                                self.load_more_mock_repositories()
                            else:
                                self.run_worker(self.load_more_repositories(), exclusive=True)
    

    def on_key(self, event) -> None:
        """Handle key presses"""
        if event.key == "escape":
            # Enhanced escape behavior for filter
            filter_input = self.query_one("#repository_filter", Input)
            repo_table = self.query_one("#repository_list", DataTable)
            
            if filter_input.has_focus:
                if self.filter_text.strip():
                    # Clear filter if it has content
                    filter_input.value = ""
                    self.filter_text = ""
                    self.apply_filter()
                    self.notify("Filter cleared")
                else:
                    # Move focus back to table if filter is empty
                    repo_table.focus()
                event.stop()
                return
            else:
                # Default escape behavior (go back)
                self.action_back()
                event.stop()
                return
                
        elif event.key == "enter":
            # Get currently selected repository and navigate to tags view
            repo_table = self.query_one("#repository_list", DataTable)
            if hasattr(repo_table, 'cursor_coordinate') and repo_table.cursor_coordinate:
                row_index = repo_table.cursor_coordinate[0]
                # Use filtered data for navigation
                data_to_use = self.filtered_repository_data if self.filtered_repository_data else self.repository_data
                if row_index < len(data_to_use):
                    repo = data_to_use[row_index]
                    self.navigate_to_tags(repo)
                event.stop()  # Prevent event bubbling
    
    def navigate_to_tags(self, repo: dict) -> None:
        """Navigate to tags view for selected repository"""
        repo_info = {
            "name": repo["name"],
            "registry_url": self.registry_info.get('url', 'Unknown')
        }
        tags_screen = TagsScreen(repository_info=repo_info, mock_mode=self.mock_mode)
        self.app.push_screen(tags_screen)
    
    def action_debug_console(self) -> None:
        """Open debug console"""
        debug_screen = DebugConsoleScreen(mock_mode=self.mock_mode)
        self.app.push_screen(debug_screen)
    
    def action_reverse_sort(self) -> None:
        """Reverse the current sort order"""
        self.sort_reversed = not self.sort_reversed
        sort_direction = "Z→A" if self.sort_reversed else "A→Z"
        self.notify(f"Repository sort: {sort_direction}")
        
        # Re-sort existing repository data
        self.repository_data.sort(key=lambda x: x['name'].lower(), reverse=self.sort_reversed)
        
        # Apply filter to rebuild table with sorted data
        self.apply_filter()
    
    # def on_mouse_down(self, event: MouseDown) -> None:
    #     """Handle mouse button events"""
    #     # Mouse back button (button 3 or 4 depending on system)
    #     if hasattr(event, 'button') and event.button in [3, 4]:
    #         self.action_back()
    
    def action_back(self) -> None:
        """Go back to registry list"""
        self.app.pop_screen()
    
    async def load_real_repositories(self, limit: int = None) -> None:
        """Background task to load real repository data"""
        repo_table = self.query_one("#repository_list", DataTable)
        registry_url = self.registry_info.get('url', '')
        
        if not registry_url:
            return
        
        # Get auth config for this registry and determine actual limit
        auth_config = self.app.registry_auth.get(registry_url) if hasattr(self.app, 'registry_auth') else None
        actual_limit = limit
        
        debug_logger.debug("Determining repository limit", 
                          input_limit=limit,
                          has_auth_config=bool(auth_config),
                          auth_config_max_repos=auth_config.get('max_repos') if auth_config else 'NO_AUTH_CONFIG')
        
        if auth_config and 'max_repos' in auth_config:
            actual_limit = auth_config['max_repos']
            debug_logger.debug("Using auth config max_repos", 
                              actual_limit=actual_limit)
        elif limit is None:
            actual_limit = 100  # Default fallback
            debug_logger.debug("Using default fallback limit", 
                              actual_limit=actual_limit)
        else:
            debug_logger.debug("Using input limit", 
                              actual_limit=actual_limit)
        
        # Handle local container runtimes
        if registry_url.startswith("local://"):
            runtime = registry_url.split("://")[1]
            client = LocalContainerClient(runtime)
            result = await client.get_repositories()
            
            if 'error' in result:
                self.notify(f"❌ Error loading {runtime} repositories: {result['error']}", severity="error")
                return
            
            repositories = result.get('data', [])
        else:
            debug_logger.debug("Loading repositories from remote registry", 
                              registry_name=self.registry_info["name"],
                              limit=actual_limit)
            
            result = await registry_manager.get_repositories(registry_url, actual_limit, auth_config)
            
            # Handle new pagination response format
            if isinstance(result, dict) and "repositories" in result:
                repositories = result["repositories"]
                pagination_info = result["pagination"]
                
                # Store pagination state for Link header continuation
                self.next_page_token = pagination_info.get("next_page_token")
                self.pagination_method = pagination_info.get("method", "unknown")
                self.all_repositories_loaded = not pagination_info.get("has_more", False)
                
                # Log potential token expiration concern
                if self.next_page_token:
                    debug_logger.debug("PAGINATION TOKEN STORED - Expiration risk", 
                                      token_stored=True,
                                      expiration_risk="next_page tokens may expire if user waits too long before scrolling",
                                      mitigation="Auto-loading should happen quickly after initial load")
                
                debug_logger.debug("Repositories loaded with pagination info", 
                                  registry_name=self.registry_info["name"],
                                  repo_count=len(repositories),
                                  pagination_method=self.pagination_method,
                                  has_next_page_token=bool(self.next_page_token),
                                  total_loaded=pagination_info.get("total_loaded", len(repositories)))
            else:
                # Backward compatibility - old format without pagination info
                repositories = result
                self.pagination_method = "legacy"
                debug_logger.debug("Repositories loaded (legacy format)", 
                                  registry_name=self.registry_info["name"],
                                  repo_count=len(repositories))
                
                # Check if we got fewer repositories than requested (indicates we've loaded all)
                if len(repositories) < actual_limit:
                    self.all_repositories_loaded = True
        
        for repo_data in repositories:
            self.repository_data.append(repo_data)
        
        # Apply filter to populate table with new data
        self.apply_filter()
        
        # Update title after loading
        self.update_title()
        
        # Auto-select first row if data exists and focus the table
        if self.repository_data:
            repo_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
        
        # Ensure table has focus on load
        repo_table.focus()
    
    def load_more_mock_repositories(self) -> None:
        """Load additional mock repositories beyond current limit"""
        registry_url = self.registry_info.get('url', '')
        
        if registry_url.startswith("mock://"):
            mock_url = registry_url
        else:
            # Map real registry URLs to mock equivalents
            if "quay.io" in registry_url:
                mock_url = "mock://quay-io"
            elif "gcr.io" in registry_url:
                mock_url = "mock://gcr-io"
            else:
                mock_url = "mock://public-registry"  # Default fallback
        
        # Get all repositories from mock data
        catalog_response = mock_registry.get_catalog(mock_url)
        if catalog_response["status_code"] != 200:
            return
            
        all_repositories = catalog_response["json"]["repositories"]
        current_count = len(self.repository_data)
        
        # Get the next batch of repositories
        new_repositories = all_repositories[current_count:self.current_limit]
        
        if not new_repositories:
            self.all_repositories_loaded = True
            self.notify(f"✅ All repositories loaded ({len(all_repositories)} total)", timeout=2)
            self.update_title()
            return
        
        repo_table = self.query_one("#repository_list", DataTable)
        
        for repo_name in new_repositories:
            # Get mock tag data for each new repository
            tags_response = mock_registry.get_tags(mock_url, repo_name)
            if tags_response["status_code"] == 200:
                all_tags = tags_response["json"]["tags"]
                tag_count = len(all_tags)
                
                # Get recent tags (exclude 'latest', take up to 3)
                recent_tags = [tag for tag in all_tags if tag != "latest"][:3]
                recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
            else:
                tag_count = 0
                recent_tags = []
                recent_tags_display = "Unknown"
            
            repo_data = {
                "name": repo_name,
                "tag_count": tag_count,
                "recent_tags": recent_tags,
                "recent_tags_display": recent_tags_display,
                "last_updated": "Mock time"
            }
            
            self.repository_data.append(repo_data)
        
        # Apply filter to update table with new data
        self.apply_filter()
        
        # Check if we've loaded everything
        if len(self.repository_data) >= len(all_repositories):
            self.all_repositories_loaded = True
        
        # Update title to reflect current state
        self.update_title()
        self.notify(f"📦 Loaded {len(new_repositories)} more repositories", timeout=1.5)

    async def load_more_repositories(self) -> None:
        """Load additional repositories using proper pagination method"""
        registry_url = self.registry_info.get('url', '')
        if not registry_url:
            return
        
        current_count = len(self.repository_data)
        batch_size = 100  # Load 100 more at a time
        
        # Get auth config for this registry
        auth_config = self.app.registry_auth.get(registry_url) if hasattr(self.app, 'registry_auth') else None
        
        # Choose pagination method based on available state
        if self.next_page_token and self.pagination_method == "link_header":
            debug_logger.debug("Auto-loading more repositories using Link header continuation", 
                              current_count=current_count,
                              batch_size=batch_size,
                              method="LINK_HEADER_CONTINUATION",
                              has_next_page_token=bool(self.next_page_token))
            
            # Use Link header continuation
            result = await registry_manager.continue_repositories_pagination(
                registry_url, 
                self.next_page_token,
                auth_config=auth_config,
                page_size=batch_size
            )
            
            # Extract repositories and update pagination state
            new_repos = result.get("repositories", [])
            pagination_info = result.get("pagination", {})
            
            # Check for token expiration
            if pagination_info.get("token_expired", False):
                debug_logger.debug("PAGINATION TOKEN EXPIRED - Falling back to offset method", 
                                  token_expired=True,
                                  error=pagination_info.get("error", "Unknown"),
                                  fallback_action="Switching to offset-based pagination")
                
                # Clear expired token and fall back to offset-based pagination
                self.next_page_token = None
                self.pagination_method = "offset_fallback_due_to_expiration"
                
                # Retry with offset-based pagination
                result = await registry_manager.get_repositories(
                    registry_url, 
                    limit=batch_size,
                    offset=current_count,
                    auth_config=auth_config
                )
                
                # Handle fallback response
                if isinstance(result, dict) and "repositories" in result:
                    new_repos = result["repositories"]
                    pagination_info = result["pagination"]
                else:
                    new_repos = result
                    
                self.notify("⚠️ Pagination token expired, switched to offset method", timeout=3)
            
            # Update pagination state for next load
            self.next_page_token = pagination_info.get("next_page_token")
            has_more_from_pagination = pagination_info.get("has_more", False)
            self.all_repositories_loaded = not has_more_from_pagination
            
            debug_logger.debug("Link header continuation completed", 
                              new_repo_count=len(new_repos),
                              total_count=current_count + len(new_repos),
                              has_more_pages=bool(self.next_page_token),
                              pagination_method=self.pagination_method,
                              has_more_from_pagination=has_more_from_pagination,
                              all_repositories_loaded_set_to=self.all_repositories_loaded)
        else:
            debug_logger.debug("Auto-loading more repositories using offset fallback", 
                              current_count=current_count,
                              batch_size=batch_size,
                              method="OFFSET_BASED_FALLBACK",
                              reason="No next_page_token available or pagination method not link_header")
            
            # Fallback to offset-based pagination
            result = await registry_manager.get_repositories(
                registry_url, 
                limit=batch_size,
                offset=current_count,
                auth_config=auth_config
            )
            
            # Handle response format
            if isinstance(result, dict) and "repositories" in result:
                new_repos = result["repositories"]
                pagination_info = result["pagination"]
                self.next_page_token = pagination_info.get("next_page_token")
                self.all_repositories_loaded = not pagination_info.get("has_more", False)
            else:
                new_repos = result
                # Legacy response format - estimate completion
                if len(new_repos) < batch_size:
                    self.all_repositories_loaded = True
            
            debug_logger.debug("Offset fallback completed", 
                              new_repo_count=len(new_repos),
                              total_count=current_count + len(new_repos))
        
        if not new_repos:
            debug_logger.debug("NO NEW REPOS - Setting all_repositories_loaded=True", 
                              new_repos_count=len(new_repos),
                              reason="Empty new_repos list")
            self.all_repositories_loaded = True
            self.notify("✅ All repositories loaded", timeout=2)
            self.update_title()
            return
        
        debug_logger.debug("NEW REPOS RECEIVED - Proceeding with UI update", 
                          new_repos_count=len(new_repos),
                          all_repositories_loaded=self.all_repositories_loaded)
        
        for repo_data in new_repos:
            self.repository_data.append(repo_data)
        
        # Apply filter to update table with new data
        self.apply_filter()
        
        # Note: all_repositories_loaded is already set correctly based on pagination metadata above
        # No need to override it with legacy current_limit logic
        debug_logger.debug("Repository loading completed", 
                          final_all_repositories_loaded=self.all_repositories_loaded,
                          final_next_page_token_available=bool(self.next_page_token),
                          final_total_repos=len(self.repository_data))
        
        # Update title to reflect current state
        self.update_title()
        self.notify(f"📦 Loaded {len(new_repos)} more repositories", timeout=1.5)
    
    def action_refresh(self) -> None:
        """Refresh repositories"""
        self.notify("Refreshing repositories...")
        # Clear existing data
        repo_table = self.query_one("#repository_list", DataTable)
        repo_table.clear()
        self.repository_data = []
        self.filtered_repository_data = []
        
        # Reload repositories
        self.load_repositories()
    
    def action_load_more(self) -> None:
        """Load more repositories"""
        if not self.all_repositories_loaded and not self.is_filter_active():
            current_count = len(self.repository_data)
            self.notify(f"Loading more repositories ({current_count} loaded)...")
            
            if self.mock_mode:
                self.load_more_mock_repositories()
            else:
                # Use the improved pagination-aware loading
                self.run_worker(self.load_more_repositories(), exclusive=True)
        else:
            self.notify("All repositories already loaded", severity="warning")
    
    def action_focus_filter(self) -> None:
        """Focus the repository filter input"""
        filter_input = self.query_one("#repository_filter", Input)
        filter_input.focus()
    
    def action_toggle_focus(self) -> None:
        """Toggle focus between filter input and repository table"""
        filter_input = self.query_one("#repository_filter", Input)
        repo_table = self.query_one("#repository_list", DataTable)
        
        if filter_input.has_focus:
            repo_table.focus()
        else:
            filter_input.focus()
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()


class ContainerCardCatalog(App):
    """Main TUI application for browsing container registries"""
    
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    #registry_list {
        width: 60%;
        border: solid $primary;
        margin: 1;
    }
    
    #registry_details {
        width: 40%;
        border: solid $secondary;
        margin: 1;
        padding: 1;
        layout: vertical;
    }
    
    #registry_details_text {
        height: 1fr;
    }
    
    .config_button {
        height: 3;
        margin-top: 1;
        dock: bottom;
    }
    """
    
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("f5", "refresh", "Refresh"),
        ("r", "reverse_sort", "Reverse Sort"),
        ("ctrl+d", "debug_console", "Debug Console"),
        ("c", "configure_registry", "Configure Registry"),
    ]
    
    def __init__(self, registries: List[str], mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.registries = registries
        self.mock_mode = mock_mode
        self.registry_data = []
        self.last_click_time = 0
        self.last_clicked_row = -1
        self.sort_reversed = False
        self.registry_auth = {}  # In-memory auth storage: {registry_url: {username, password, auth_type}}
        
    def compose(self) -> ComposeResult:
        """Create the TUI layout"""
        yield Header()
        with Horizontal():
            # Left panel - Registry list
            registry_table = DataTable(id="registry_list", cursor_type="row")
            registry_table.add_columns("Status", "Name", "Registry URL", "Repos", "API Version")
            yield registry_table
            
            # Right panel - Registry details
            yield RegistryDetailsPanel(id="registry_details")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the application"""
        self.load_registries()
        # Show initial details and set parent reference
        details_panel = self.query_one("#registry_details", RegistryDetailsPanel)
        details_panel.set_parent_app(self)
        
        # Start background task to check real registries
        if not self.mock_mode and self.registries:
            self.run_worker(self.check_real_registries(), exclusive=True)
        
    def load_registries(self) -> None:
        """Load and populate registry data"""
        registry_table = self.query_one("#registry_list", DataTable)
        
        # Use provided registries or sample data
        if self.registries:
            # Use the registries passed from command line
            sample_registries = []
            for registry_url in self.registries:
                if registry_url.startswith("mock://"):
                    status = "🧪"
                    api_version = "v2 (Mock)"
                    name = f"Mock {registry_url.split('://')[-1].title()}"
                elif registry_url.startswith("local://"):
                    runtime = registry_url.split("://")[1]
                    status = "🏠" if runtime == "podman" else "🐳"
                    api_version = f"{runtime} (unknown)"
                    name = f"Local {runtime.title()} Cache"
                else:
                    status = "⏳"
                    api_version = "Checking..."
                    name = registry_url.replace("https://", "").replace("http://", "")
                
                # Get repo count for this registry
                if registry_url.startswith("local://"):
                    repo_count = "Scanning..."
                elif self.mock_mode:
                    from mock_data import mock_registry
                    if registry_url.startswith("mock://"):
                        mock_url = registry_url
                    else:
                        # Map real registry URLs to mock equivalents
                        if "quay.io" in registry_url:
                            mock_url = "mock://quay-io"
                        elif "gcr.io" in registry_url:
                            mock_url = "mock://gcr-io"
                        else:
                            mock_url = "mock://public-registry"  # Default fallback
                    
                    if mock_url in mock_registry.registries:
                        repo_count = len(mock_registry.registries[mock_url]["repositories"])
                    else:
                        repo_count = 0
                else:
                    repo_count = "Checking..."
                
                sample_registries.append({
                    "status": status,
                    "name": name,
                    "url": registry_url,
                    "repo_count": repo_count,
                    "api_version": api_version
                })
        else:
            # Fallback sample data for development
            if self.mock_mode:
                sample_registries = [
                    {"status": "🧪", "name": "Public Registry", "url": "mock://public-registry", "repo_count": 10, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Quay.io Mock", "url": "mock://quay-io", "repo_count": 5, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "GCR Mock", "url": "mock://gcr-io", "repo_count": 5, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Local Dev", "url": "mock://local-dev", "repo_count": 7, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Enterprise", "url": "mock://enterprise", "repo_count": 6, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Massive Test", "url": "mock://massive-registry", "repo_count": 603, "api_version": "v2 (Mock)"},
                ]
            else:
                sample_registries = [
                    {"status": "⏳", "name": "Registry One", "url": "registry-1.example.io", "repo_count": "Checking...", "api_version": "Checking..."},
                    {"status": "⏳", "name": "Red Hat Quay", "url": "quay.io", "repo_count": "Checking...", "api_version": "Checking..."},
                ]
        
        # Sort registries by name (alphabetical)
        sample_registries.sort(key=lambda x: x["name"].lower(), reverse=self.sort_reversed)
            
        for registry in sample_registries:
            registry_table.add_row(
                registry["status"],
                registry["name"], 
                registry["url"],
                str(registry["repo_count"]),
                registry["api_version"]
            )
            self.registry_data.append(registry)
        
        # Auto-select first row if data exists
        if self.registry_data:
            registry_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
    
    def update_details_for_row(self, row_index: int) -> None:
        """Update details panel for given row index"""
        details_panel = self.query_one("#registry_details", RegistryDetailsPanel)
        
        if row_index < len(self.registry_data):
            registry = self.registry_data[row_index]
            
            # Get actual repository count
            if self.mock_mode:
                from mock_data import mock_registry
                registry_url = registry["url"]
                if registry_url in mock_registry.registries:
                    repo_count = len(mock_registry.registries[registry_url]["repositories"])
                else:
                    repo_count = 0
            else:
                # For real mode, use the count from registry data if available
                repo_count = registry.get("repo_count", "Unknown")
            
            # Create detailed info for selected registry
            registry_url = registry["url"]
            
            if registry_url.startswith("local://"):
                # Local runtime details
                runtime = registry_url.split("://")[1]
                import getpass
                detailed_info = {
                    "url": registry_url,
                    "username": getpass.getuser(),
                    "auth_type": "System access",
                    "last_checked": "Real-time",
                    "response_time": "Local",
                    "repo_count": str(repo_count),
                    "api_version": registry["api_version"],
                    "connection_status": registry.get("connection_status", "Local filesystem"),
                    "registry_hash": f"local:{runtime}{hash(registry_url) % 1000:03d}"
                }
            elif registry_url.startswith("mock://"):
                # Mock registry details
                detailed_info = {
                    "url": registry_url,
                    "username": "mock-user",
                    "auth_type": "Mock Auth",
                    "last_checked": "Mock Time",
                    "response_time": "1ms",
                    "repo_count": str(repo_count),
                    "api_version": registry["api_version"],
                    "connection_status": "Mock",
                    "registry_hash": f"sha256:reg{hash(registry_url) % 1000000:06d}"
                }
            else:
                # Real HTTP registry details
                detailed_info = {
                    "url": registry_url,
                    "username": registry.get("username", "Anonymous"),
                    "auth_type": registry.get("auth_type", "Anonymous"),
                    "last_checked": registry.get("last_checked", "Unknown"),
                    "response_time": registry.get("response_time", "Unknown"),
                    "repo_count": str(repo_count),
                    "api_version": registry["api_version"],
                    "connection_status": registry.get("connection_status", "Unknown"),
                    "registry_hash": registry.get("registry_hash", "Unknown")
                }
            
            details_panel.update_registry_info(detailed_info)
    
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle registry row highlighting (auto-select)"""
        self.update_details_for_row(event.cursor_row)
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle registry selection and double-click detection"""
        # Only handle events if this is the ContainerCardCatalog (main app)
        if not isinstance(self, ContainerCardCatalog):
            return
            
        import time
        current_time = time.time()
        
        # Double-click detection (within 500ms of previous click on same row)
        if (current_time - self.last_click_time < 0.5 and 
            self.last_clicked_row == event.cursor_row and
            event.cursor_row < len(self.registry_data)):
            
            # Double-click detected - navigate to repositories
            registry = self.registry_data[event.cursor_row]
            self.navigate_to_repositories(registry)
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
        if event.key == "enter":
            # Get currently selected registry and navigate to repository view
            registry_table = self.query_one("#registry_list", DataTable)
            if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
                row_index = registry_table.cursor_coordinate[0]
                if row_index < len(self.registry_data):
                    registry = self.registry_data[row_index]
                    self.navigate_to_repositories(registry)
                event.stop()  # Prevent event bubbling
    
    def navigate_to_repositories(self, registry: dict) -> None:
        """Navigate to repository view for selected registry"""
        debug_logger.debug("Navigating to repository view", 
                          registry_name=registry["name"],
                          mock_mode=self.mock_mode)
        
        registry_info = {
            "name": registry["name"],
            "url": registry["url"],
            "api_version": registry["api_version"],
            "status": registry["status"]
        }
        repo_screen = RepositoryScreen(registry_info=registry_info, mock_mode=self.mock_mode)
        self.app.push_screen(repo_screen)
    
    def action_refresh(self) -> None:
        """Refresh registry status"""
        debug_logger.debug("Manual registry refresh triggered", 
                          mock_mode=self.mock_mode,
                          registry_count=len(self.registries))
        self.notify("Refreshing registries...")
        
        if not self.mock_mode and self.registries:
            # Re-check real registries
            debug_logger.debug("Starting real registry status checks")
            self.run_worker(self.check_real_registries(), exclusive=True)
        else:
            # In mock mode, just reload the data
            debug_logger.debug("Reloading mock registry data")
            registry_table = self.query_one("#registry_list", DataTable)
            registry_table.clear()
            self.registry_data = []
            self.load_registries()
    
    async def check_real_registries(self) -> None:
        """Background task to check real registry status"""
        registry_table = self.query_one("#registry_list", DataTable)
        
        for registry_url in self.registries:
            if not registry_url.startswith("mock://"):
                # Find the correct row index in the sorted registry_data
                registry_row_index = None
                for idx, registry_data in enumerate(self.registry_data):
                    if registry_data["url"] == registry_url:
                        registry_row_index = idx
                        break
                
                if registry_row_index is None:
                    continue  # Skip if not found
                # Check registry status
                if registry_url.startswith("local://"):
                    # Handle local container runtime health check
                    runtime = registry_url.split("://")[1]
                    client = LocalContainerClient(runtime)
                    health_info = await client.check_health()
                    
                    import time
                    current_time = time.strftime("%H:%M:%S")
                    
                    if health_info['status'] == 'healthy':
                        version = health_info.get('version', 'Unknown')
                        
                        # Get actual repository count
                        try:
                            client = LocalContainerClient(runtime)
                            repos_result = await client.get_repositories()
                            if 'error' not in repos_result:
                                repo_count = repos_result.get('total_repositories', 0)
                            else:
                                repo_count = "Error"
                        except:
                            repo_count = "Unknown"
                        
                        status_info = {
                            "status": "🏠" if runtime == "podman" else "🐳",
                            "api_version": f"{runtime} {version}",
                            "repo_count": str(repo_count),
                            "response_time": f"{health_info.get('response_time', 0)}ms",
                            "connection_status": "Local",
                            "last_checked": current_time
                        }
                    else:
                        status_info = {
                            "status": "❌",
                            "api_version": f"{runtime} (Error)",
                            "repo_count": "Error",
                            "response_time": "N/A",
                            "connection_status": f"Error: {health_info.get('error', 'Unknown')}",
                            "last_checked": current_time
                        }
                else:
                    # Get auth config for this registry
                    auth_config = self.registry_auth.get(registry_url)
                    status_info = await registry_manager.check_registry_status(registry_url, auth_config)
                
                # Update the registry data
                self.registry_data[registry_row_index].update({
                    "status": status_info["status"],
                    "api_version": status_info["api_version"],
                    "repo_count": status_info["repo_count"],
                    "response_time": status_info["response_time"],
                    "connection_status": status_info["connection_status"],
                    "last_checked": status_info.get("last_checked", "Unknown")
                })
                
                # Update the table row
                registry_table.update_cell_at(
                    (registry_row_index, 0), status_info["status"]
                )
                registry_table.update_cell_at(
                    (registry_row_index, 3), str(status_info["repo_count"])
                )
                registry_table.update_cell_at(
                    (registry_row_index, 4), status_info["api_version"]
                )
                
                # If this row is currently selected, update details
                if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
                    if registry_table.cursor_coordinate[0] == registry_row_index:
                        self.update_details_for_row(registry_row_index)
    
    def action_debug_console(self) -> None:
        """Open debug console"""
        debug_screen = DebugConsoleScreen(mock_mode=self.mock_mode)
        self.app.push_screen(debug_screen)
    
    def action_reverse_sort(self) -> None:
        """Reverse the current sort order"""
        self.sort_reversed = not self.sort_reversed
        sort_direction = "Z→A" if self.sort_reversed else "A→Z"
        self.notify(f"Registry sort: {sort_direction}")
        
        # Re-sort existing registry data (preserving health check results)
        self.registry_data.sort(key=lambda x: x["name"].lower(), reverse=self.sort_reversed)
        
        # Rebuild table with sorted data
        registry_table = self.query_one("#registry_list", DataTable)
        registry_table.clear()
        
        for registry in self.registry_data:
            registry_table.add_row(
                registry["status"],
                registry["name"], 
                registry["url"],
                str(registry["repo_count"]),
                registry["api_version"]
            )
        
        # Auto-select first row if data exists
        if self.registry_data:
            registry_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
    
    def action_configure_registry(self) -> None:
        """Open configuration modal for selected registry"""
        registry_table = self.query_one("#registry_list", DataTable)
        if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
            row_index = registry_table.cursor_coordinate[0]
            if row_index < len(self.registry_data):
                registry = self.registry_data[row_index]
                
                # Get saved auth data for this registry
                registry_url = registry.get('url', '')
                saved_auth = self.registry_auth.get(registry_url, {})
                
                # Create registry data for modal
                registry_data = {
                    'name': registry.get('name', 'Unknown'),
                    'url': registry_url,
                    'username': saved_auth.get('username', ''),
                    'auth_type': saved_auth.get('auth_type', 'bearer'),
                    'registry_type': saved_auth.get('registry_type', ''),
                    'auth_scope': saved_auth.get('auth_scope', 'registry:catalog:*'),
                    'max_repos': saved_auth.get('max_repos', 100),
                    'cache_ttl': saved_auth.get('cache_ttl', 900)
                }
                
                # Open configuration modal
                config_modal = RegistryConfigModal(registry_data)
                self.app.push_screen(config_modal)
                
                self.notify(f"Configure {registry['name']}")
            else:
                self.notify("No registry selected", severity="warning")
        else:
            self.notify("No registry selected", severity="warning")
    
    async def on_registry_config_modal_config_saved(self, message: RegistryConfigModal.ConfigSaved) -> None:
        """Handle configuration saved from modal"""
        config = message.registry_config
        registry_url = config['registry_url']
        
        debug_logger.debug("Registry configuration saved", 
                          registry_name=config.get('registry_name', 'Unknown'),
                          auth_type=config.get('auth_type', 'none'),
                          username=config.get('username', ''),
                          password=config.get('password', ''),  # Will be masked
                          max_repos=config.get('max_repos', 100))
        
        # Store auth credentials in memory
        self.registry_auth[registry_url] = {
            'username': config.get('username', ''),
            'password': config.get('password', ''),
            'auth_type': config.get('auth_type', 'none'),
            'registry_type': config.get('registry_type', 'auto'),
            'auth_scope': config.get('auth_scope', 'registry:catalog:*'),
            'max_repos': config.get('max_repos', 100),
            'cache_ttl': config.get('cache_ttl', 900)
        }
        
        # Update registry data with auth info for display
        for registry in self.registry_data:
            if registry.get('url') == registry_url:
                registry['username'] = config.get('username', 'Anonymous')
                registry['auth_type'] = config.get('auth_type', 'None')
                break
        
        # Refresh the details panel if this registry is currently selected
        registry_table = self.query_one("#registry_list", DataTable)
        if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
            current_row = registry_table.cursor_coordinate[0]
            self.update_details_for_row(current_row)
        
        self.notify(f"✅ {config['registry_name']} authentication configured")
        
        debug_logger.debug("Auth config stored in memory", 
                          registry_count=len(self.registry_auth),
                          has_credentials=bool(config.get('username')))
        
        # Automatically refresh this registry's status
        if not self.mock_mode:
            debug_logger.debug("Triggering registry status refresh", registry_url=registry_url)
            self.run_worker(self._refresh_single_registry(registry_url), exclusive=False)
            self.notify("🔄 Refreshing registry status...")
        else:
            debug_logger.debug("Skipping registry refresh in mock mode")
    
    async def _refresh_single_registry(self, registry_url: str) -> None:
        """Refresh status for a single registry"""
        debug_logger.debug("Starting single registry refresh", registry_url=registry_url)
        registry_table = self.query_one("#registry_list", DataTable)
        
        # Find the registry in our data
        registry_row_index = None
        for idx, registry_data in enumerate(self.registry_data):
            if registry_data["url"] == registry_url:
                registry_row_index = idx
                break
        
        if registry_row_index is None:
            debug_logger.error("Registry not found in data for refresh", 
                              registry_url=registry_url,
                              available_registries=[r.get('url') for r in self.registry_data])
            return
        
        debug_logger.debug("Found registry for refresh", 
                          registry_index=registry_row_index,
                          registry_name=self.registry_data[registry_row_index].get('name', 'Unknown'))
        
        # Get auth config and check status
        auth_config = self.registry_auth.get(registry_url)
        debug_logger.debug("Using auth config for refresh", 
                          has_auth_config=bool(auth_config),
                          auth_type=auth_config.get('auth_type') if auth_config else 'none')
        
        if registry_url.startswith("local://"):
            # Handle local container runtime
            runtime = registry_url.split("://")[1]
            client = LocalContainerClient(runtime)
            health_info = await client.check_health()
            
            import time
            current_time = time.strftime("%H:%M:%S")
            
            if health_info['status'] == 'healthy':
                version = health_info.get('version', 'Unknown')
                try:
                    repos_result = await client.get_repositories()
                    repo_count = repos_result.get('total_repositories', 0) if 'error' not in repos_result else "Error"
                except:
                    repo_count = "Unknown"
                
                status_info = {
                    "status": "🏠" if runtime == "podman" else "🐳",
                    "api_version": f"{runtime} {version}",
                    "repo_count": str(repo_count),
                    "response_time": f"{health_info.get('response_time', 0)}ms",
                    "ssl_status": "Local",
                    "last_checked": current_time
                }
            else:
                status_info = {
                    "status": "❌",
                    "api_version": f"{runtime} (Error)",
                    "repo_count": "Error",
                    "response_time": "N/A",
                    "ssl_status": f"Error: {health_info.get('error', 'Unknown')}",
                    "last_checked": current_time
                }
        else:
            debug_logger.debug("Checking remote registry status", 
                               registry_url=registry_url,
                               has_auth=bool(auth_config))
            
            status_info = await registry_manager.check_registry_status(registry_url, auth_config)
        
        debug_logger.debug("Registry status check completed", 
                          registry_url=registry_url,
                          status=status_info["status"],
                          repo_count=status_info["repo_count"])
        
        # Update the registry data
        self.registry_data[registry_row_index].update({
            "status": status_info["status"],
            "api_version": status_info["api_version"],
            "repo_count": status_info["repo_count"],
            "response_time": status_info["response_time"],
            "connection_status": status_info["connection_status"],
            "last_checked": status_info.get("last_checked", "Unknown")
        })
        
        # Update the table row
        registry_table.update_cell_at((registry_row_index, 0), status_info["status"])
        registry_table.update_cell_at((registry_row_index, 3), str(status_info["repo_count"]))
        registry_table.update_cell_at((registry_row_index, 4), status_info["api_version"])
        
        debug_logger.debug("Registry table updated", 
                          row_index=registry_row_index,
                          status_updated=True)
        
        # If this row is currently selected, update details
        if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
            if registry_table.cursor_coordinate[0] == registry_row_index:
                debug_logger.debug("Updating details panel for refreshed registry")
                self.update_details_for_row(registry_row_index)
    
    def action_quit(self) -> None:
        """Quit the application"""
        debug_logger.debug("Application quit requested")
        self.exit()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Container Card Catalog - TUI for browsing container registries")
    
    parser.add_argument(
        "--registry", 
        action="append", 
        dest="registries",
        help="Container registry URL (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock registry data for development/testing"
    )
    
    parser.add_argument(
        "--local", 
        action="append", 
        choices=['docker', 'podman'],
        help="Add local container runtime (can be specified multiple times)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable TUI operations debug logging (separate from API debug console)"
    )
    
    parser.add_argument(
        "--verbose-debug",
        action="store_true",
        help="Enable verbose debug logging including HTTP libraries (httpcore, httpx, etc.)"
    )
    
    parser.add_argument(
        "--debug-location",
        type=str,
        default="/tmp/container-registry-tui-debug.log",
        help="File path for TUI debug logging (default: /tmp/container-registry-tui-debug.log)"
    )
    
    parser.add_argument(
        "--version",
        action="version", 
        version="Container Card Catalog 0.1.0"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Initialize debug logging if requested
    global debug_logger
    debug_enabled = args.debug or args.verbose_debug
    debug_logger = TUIDebugLogger(enabled=debug_enabled, verbose=args.verbose_debug, debug_file_path=args.debug_location)
    
    debug_logger.debug("Starting Container Registry Card Catalog", 
                      debug_enabled=debug_enabled,
                      verbose_debug=args.verbose_debug)
    
    # Handle registry and mock mode logic
    registries = args.registries or []
    local_runtimes = args.local or []
    mock_mode = args.mock
    
    debug_logger.debug("Configuration parsed", 
                      registries=registries, 
                      local_runtimes=local_runtimes, 
                      mock_mode=mock_mode)
    
    # Add local runtimes to registry list
    for runtime in local_runtimes:
        registries.append(f"local://{runtime}")
        debug_logger.debug("Added local runtime", runtime=runtime, url=f"local://{runtime}")
    
    # If --mock is specified, use mock registries even if --registry was provided
    if mock_mode and not registries:
        # Default mock registries when --mock is used without --registry
        pass  # Will be set below
    elif mock_mode and registries:
        # --mock flag with --registry should override to use mock data
        debug_logger.debug("Mock mode enabled with custom registries")
        pass  # Keep provided registries but run in mock mode
    elif not mock_mode and not registries:
        # No flags - default to mock mode
        debug_logger.debug("No registries specified, defaulting to mock mode")
        mock_mode = True
    
    if mock_mode and not registries:
        registries = ["mock://public-registry", "mock://quay-io", "mock://gcr-io", "mock://local-dev", "mock://enterprise", "mock://massive-registry"]
        debug_logger.debug("Using default mock registries", count=len(registries))
    
    debug_logger.debug("Initializing TUI application", 
                      final_registries=registries, 
                      mock_mode=mock_mode)
    
    # Set the TUI debug logger on the registry manager for auth/cache logging
    registry_manager.set_tui_debug_logger(debug_logger)
    
    app = ContainerCardCatalog(registries=registries, mock_mode=mock_mode)
    app.run()


if __name__ == "__main__":
    main()
