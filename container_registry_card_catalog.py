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
from config_manager import config_manager
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


# Global debug logger instance (disabled by default, enabled in main() if --debug flag provided)
debug_logger = TUIDebugLogger(enabled=False)


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
            
            # Determine if configuration is available for this registry type
            is_local_runtime = base_url.startswith('local://')
            
            # Handle different registry types
            if is_local_runtime:
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
            
            # Add monitored repositories info if configured
            monitored_repos = registry_info.get('monitored_repos', [])
            if monitored_repos:
                details += f"\n\n📌 Monitored Repositories: {len(monitored_repos)}"
                for repo in monitored_repos[:3]:  # Show first 3
                    details += f"\n   ⭐ {repo}"
                if len(monitored_repos) > 3:
                    details += f"\n   ... and {len(monitored_repos) - 3} more"
            
            # TODO: Add SSL status validation once SSL verification is implemented
            
            details_text.update(details)
            
            # Disable configuration for local runtimes (podman/docker)
            if is_local_runtime:
                configure_button.disabled = True
                configure_button.label = "Local Runtime - No Config"
            else:
                configure_button.disabled = False
                configure_button.label = "Configure Registry"
        else:
            details_text.update("Select a registry to view details")
            configure_button.disabled = True
            configure_button.label = "Configure Registry"
    
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
    
    def __init__(self, registry_info: dict, registry_config: dict = None, mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.registry_info = registry_info
        self.registry_config = registry_config or {}
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
    
    def apply_filter(self, preserve_cursor: bool = False) -> None:
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
        self.rebuild_repository_table(preserve_cursor=preserve_cursor)
        
        # Update title to show filter status
        self.update_title()
    
    def rebuild_repository_table(self, preserve_cursor: bool = False) -> None:
        """Rebuild the repository table with current filtered data"""
        repo_table = self.query_one("#repository_list", DataTable)
        
        # Save current cursor position if preserving
        saved_cursor = None
        if preserve_cursor and hasattr(repo_table, 'cursor_coordinate') and repo_table.cursor_coordinate:
            saved_cursor = repo_table.cursor_coordinate
        
        repo_table.clear()
        
        for repo_data in self.filtered_repository_data:
            # Use different emoji for monitored vs catalog repos
            if repo_data.get('is_monitored', False):
                if repo_data.get('is_error', False):
                    icon = "❌"  # Error fetching monitored repo
                else:
                    icon = "⭐"  # Successfully fetched monitored repo
            else:
                icon = "📦"  # Regular catalog repo
            
            repo_table.add_row(
                icon,
                self.registry_info.get('name', 'Unknown'),
                repo_data["name"],
                str(repo_data.get("tag_count", "Unknown")),
                repo_data.get("recent_tags_display", "Unknown"),
                repo_data.get("last_updated", "Unknown")
            )
        
        # Restore cursor position or auto-select first row
        if preserve_cursor and saved_cursor and saved_cursor[0] < len(self.filtered_repository_data):
            repo_table.cursor_coordinate = saved_cursor
            self.update_details_for_row(saved_cursor[0])
        elif self.filtered_repository_data:
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
            
            # Get monitored repositories first (like real registry mode)
            monitored_repos = self.registry_config.get('monitored_repos', []) if self.registry_config else []
            monitored_repo_data = []
            
            debug_logger.debug("Mock mode: Loading monitored repositories first",
                              monitored_repos_count=len(monitored_repos),
                              monitored_repos=monitored_repos)
            
            # Process monitored repositories first
            for repo_name in monitored_repos:
                tags_response = mock_registry.get_tags(mock_url, repo_name)
                if tags_response["status_code"] == 200:
                    all_tags = tags_response["json"]["tags"]
                    tag_count = len(all_tags)
                    
                    # Get recent tags (exclude 'latest', take up to 3)
                    recent_tags = [tag for tag in all_tags if tag != "latest"][:3]
                    recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
                    
                    monitored_repo_data.append({
                        "name": repo_name,
                        "tag_count": tag_count,
                        "recent_tags": recent_tags,
                        "recent_tags_display": recent_tags_display,
                        "last_updated": "Mock time",
                        "is_monitored": True  # Mark as monitored for display
                    })
                    
                    debug_logger.debug("Mock mode: Monitored repo processed",
                                      repo=repo_name,
                                      tag_count=tag_count)
            
            # Get repositories from mock data catalog
            catalog_response = mock_registry.get_catalog(mock_url)
            if catalog_response["status_code"] == 200:
                all_repositories = catalog_response["json"]["repositories"]
                
                # Respect the current limit for auto-loading behavior
                repositories = all_repositories[:self.current_limit]
                
                # Check if we've loaded all available repositories
                if len(repositories) >= len(all_repositories):
                    self.all_repositories_loaded = True
                
                # Process catalog repositories (excluding monitored ones to avoid duplicates)
                monitored_repo_names = {repo['name'] for repo in monitored_repo_data}
                catalog_repo_data = []
                
                for repo_name in repositories:
                    if repo_name in monitored_repo_names:
                        continue  # Skip monitored repos to avoid duplicates
                        
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
                    
                    catalog_repo_data.append({
                        "name": repo_name,
                        "tag_count": tag_count,
                        "recent_tags": recent_tags,
                        "recent_tags_display": recent_tags_display,
                        "last_updated": "Mock time"
                    })
                
                # Combine: monitored repos first, then catalog repos (like real registry mode)
                self.repository_data = monitored_repo_data + catalog_repo_data
                
                debug_logger.debug("Mock mode: Repository data assembled",
                                  total_repos=len(self.repository_data),
                                  monitored_repos=len(monitored_repo_data),
                                  catalog_repos=len(catalog_repo_data))
                
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
        
        # Re-sort existing repository data with monitored repos always at top
        monitored_repos = [repo for repo in self.repository_data if repo.get('is_monitored', False)]
        catalog_repos = [repo for repo in self.repository_data if not repo.get('is_monitored', False)]
        
        # Sort each group separately 
        monitored_repos.sort(key=lambda x: x['name'].lower(), reverse=self.sort_reversed)
        catalog_repos.sort(key=lambda x: x['name'].lower(), reverse=self.sort_reversed)
        
        # Combine with monitored repos always first
        self.repository_data = monitored_repos + catalog_repos
        
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
        
        # Get registry config for this registry and determine actual limit
        registry_config = self.registry_config
        actual_limit = limit
        
        debug_logger.debug("Determining repository limit", 
                          input_limit=limit,
                          has_registry_config=bool(registry_config),
                          registry_config_max_repos=registry_config.get('max_repos') if registry_config else 'NO_REGISTRY_CONFIG',
                          monitored_repos_count=len(registry_config.get('monitored_repos', [])) if registry_config else 0,
                          monitored_repos=registry_config.get('monitored_repos', []) if registry_config else 'NO_REGISTRY_CONFIG')
        
        if registry_config and 'max_repos' in registry_config:
            actual_limit = registry_config['max_repos']
            debug_logger.debug("Using registry config max_repos", 
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
            
            result = await registry_manager.get_repositories(registry_url, actual_limit, registry_config)
            
            # Handle new pagination response format
            if isinstance(result, dict) and "repositories" in result:
                repositories = result["repositories"]
                pagination_info = result["pagination"]
                monitored_status = result.get("monitored_repos_status", {})
                
                # Handle monitored repository status and notifications
                if monitored_status.get("failed"):
                    failed_repos = monitored_status["failed"]
                    for failed_repo in failed_repos:
                        self.notify(f"⚠️ Monitored repo '{failed_repo['name']}' failed: {failed_repo['error']}", 
                                   severity="warning", timeout=5)
                
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
            # Debug log each repo as it's added
            if repo_data.get('is_monitored', False):
                debug_logger.debug("Added monitored repository to UI", 
                                  repo_name=repo_data['name'],
                                  tag_count=repo_data.get('tag_count', 'Unknown'),
                                  is_error=repo_data.get('is_error', False))
        
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
        
        # Apply filter to update table with new data (preserve cursor during auto-loading)
        self.apply_filter(preserve_cursor=True)
        
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
        
        # Get registry config for this registry
        registry_config = self.registry_config
        
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
                registry_config=registry_config,
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
                    registry_config=registry_config
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
                registry_config=registry_config
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
        
        # Apply filter to update table with new data (preserve cursor during auto-loading)
        self.apply_filter(preserve_cursor=True)
        
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
        debug_logger.debug("Repository refresh triggered", 
                          screen_type="RepositoryScreen",
                          current_repo_count=len(self.repository_data),
                          has_registry_config=bool(self.registry_config),
                          monitored_repos_count=len(self.registry_config.get('monitored_repos', [])) if self.registry_config else 0,
                          monitored_repos=self.registry_config.get('monitored_repos', []) if self.registry_config else [])
        
        self.notify("Refreshing repositories...")
        
        # Save current cursor position to restore after refresh
        repo_table = self.query_one("#repository_list", DataTable)
        cursor_row = 0
        if hasattr(repo_table, 'cursor_coordinate') and repo_table.cursor_coordinate:
            cursor_row = repo_table.cursor_coordinate[0]
        
        # Clear existing data
        repo_table.clear()
        self.repository_data = []
        self.filtered_repository_data = []
        
        # Reset pagination state
        self.current_offset = 0
        self.current_limit = 50
        self.all_repositories_loaded = False
        
        debug_logger.debug("Repository data cleared, reloading...", 
                          preserved_cursor_row=cursor_row)
        
        # Reload repositories
        self.load_repositories()
        
        # Restore cursor position after data loads
        if cursor_row > 0:
            self.call_later(lambda: self._restore_cursor_position(cursor_row))
    
    def _restore_cursor_position(self, cursor_row: int) -> None:
        """Restore cursor position after refresh"""
        try:
            repo_table = self.query_one("#repository_list", DataTable)
            if len(self.repository_data) > cursor_row:
                repo_table.cursor_coordinate = (cursor_row, 0)
                self.update_details_for_row(cursor_row)
                debug_logger.debug("Cursor position restored", 
                                  restored_row=cursor_row)
            elif len(self.repository_data) > 0:
                # Fallback to first row if original position is out of bounds
                repo_table.cursor_coordinate = (0, 0)
                self.update_details_for_row(0)
                debug_logger.debug("Cursor position fallback", 
                                  original_row=cursor_row,
                                  fallback_row=0)
        except Exception as e:
            debug_logger.debug("Failed to restore cursor position", 
                              error=str(e),
                              target_row=cursor_row)
    
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
    
    async def on_registry_config_modal_config_saved(self, message: RegistryConfigModal.ConfigSaved) -> None:
        """Handle configuration saved from modal in repository screen"""
        config = message.registry_config
        registry_url = config['registry_url']
        
        debug_logger.debug("Repository screen received config update", 
                          screen_type="RepositoryScreen",
                          registry_url=registry_url,
                          current_registry=self.registry_info.get('url'),
                          monitored_repos_count=len(config.get('monitored_repos', [])),
                          monitored_repos=config.get('monitored_repos', []),
                          is_for_current_registry=(registry_url == self.registry_info.get('url')))
        
        # Check if this config update is for our current registry
        if registry_url == self.registry_info.get('url'):
            # Update our local registry config
            self.registry_config = {
                'username': config.get('username', ''),
                'password': config.get('password', ''),
                'auth_type': config.get('auth_type', 'none'),
                'registry_type': config.get('registry_type', 'auto'),
                'auth_scope': config.get('auth_scope', 'registry:catalog:*'),
                'max_repos': config.get('max_repos', 100),
                'cache_ttl': config.get('cache_ttl', 900),
                'monitored_repos': config.get('monitored_repos', [])
            }
            
            debug_logger.debug("Registry config updated in repository screen", 
                              monitored_repos=config.get('monitored_repos', []),
                              triggering_refresh=True)
            
            self.notify(f"✅ Configuration updated - refreshing repositories...")
            
            # Trigger a repository refresh to fetch new monitored repos
            self.action_refresh()
        else:
            debug_logger.debug("Config update ignored - not for current registry", 
                              config_registry=registry_url,
                              current_registry=self.registry_info.get('url'))

    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()


class ContainerCardCatalog(App):
    """Main TUI application for browsing container registries"""
    
    TITLE = "Container Registry Card Catalog - Beta"
    
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
        self.registry_config = {}  # In-memory registry config storage: {registry_url: {username, password, auth_type, monitored_repos, etc}}
        
        # Load saved configuration on startup
        self._load_saved_configuration()
    
    def _load_saved_configuration(self) -> None:
        """Load saved registry configurations from file"""
        try:
            saved_config = config_manager.load_config()
            
            debug_logger.debug("Loading saved configuration", 
                              registry_count=len(saved_config.get('registries', [])),
                              config_version=saved_config.get('version', 'unknown'))
            
            # Load registry configurations into memory
            for registry_config in saved_config.get('registries', []):
                registry_url = registry_config.get('url')
                if registry_url:
                    # Convert saved config to in-memory format (Phase 1: no credentials)
                    self.registry_config[registry_url] = {
                        'username': '',  # Phase 1: credentials not persisted yet
                        'password': '',  # Phase 1: credentials not persisted yet
                        'auth_type': 'none',  # Phase 1: auth not persisted yet
                        'registry_type': 'auto',
                        'auth_scope': registry_config.get('settings', {}).get('auth_scope', 'registry:catalog:*'),
                        'max_repos': registry_config.get('settings', {}).get('max_repos', 100),
                        'cache_ttl': registry_config.get('settings', {}).get('cache_ttl', 900),
                        'monitored_repos': registry_config.get('monitored_repos', [])
                    }
            
            if self.registry_config:
                total_monitored = sum(len(config.get('monitored_repos', [])) for config in self.registry_config.values())
                debug_logger.debug("Saved configuration loaded", 
                                  loaded_registries=len(self.registry_config),
                                  total_monitored_repos=total_monitored)
            else:
                debug_logger.debug("No saved registry configurations found")
                
        except Exception as e:
            debug_logger.error(f"Failed to load saved configuration: {e}")
        
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
    
    def on_screen_resume(self) -> None:
        """Called when returning to this screen - sync details panel with cursor"""
        debug_logger.debug("Registry screen resume called")
        # Use call_later to ensure the screen is fully active before syncing
        self.call_later(lambda: self._sync_details_with_cursor())
    
    def on_focus(self) -> None:
        """Called when screen gets focus - also sync details panel"""
        debug_logger.debug("Registry screen focus gained")
        self._sync_details_with_cursor()
        
    def _sync_details_with_cursor(self) -> None:
        """Helper method to sync details panel with current cursor position"""
        try:
            registry_table = self.query_one("#registry_list", DataTable)
            if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
                current_row = registry_table.cursor_coordinate[0]
                debug_logger.debug("Syncing registry details panel with cursor",
                                  current_cursor_row=current_row,
                                  total_registries=len(self.registry_data),
                                  force_update=True)
                self.update_details_for_row(current_row)
                
                # Force focus on the table to ensure events are properly wired
                registry_table.focus()
            else:
                debug_logger.debug("No cursor coordinate found, using row 0")
                self.update_details_for_row(0)
        except Exception as e:
            debug_logger.debug("Details panel sync failed, fallback to row 0",
                              error=str(e))
            # Fallback to first row if cursor sync fails
            self.update_details_for_row(0)
        
    def load_registries(self) -> None:
        """Load and populate registry data"""
        registry_table = self.query_one("#registry_list", DataTable)
        
        # Use provided registries or sample data
        if self.registries:
            # Use the registries passed from command line
            all_registries = []
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
                        catalog_repos = mock_registry.registries[mock_url]["repositories"]
                        catalog_count = len(catalog_repos)
                        
                        # Check for monitored repos from loaded config
                        registry_config = self.registry_config.get(registry_url, {})
                        monitored_repos = registry_config.get('monitored_repos', [])
                        
                        if monitored_repos and len(monitored_repos) > 0:
                            # Count how many monitored repos are NOT in the catalog
                            monitored_not_in_catalog = [repo for repo in monitored_repos if repo not in catalog_repos]
                            total_repos = catalog_count + len(monitored_not_in_catalog)
                            repo_count = f"{total_repos}({len(monitored_repos)})"
                        else:
                            repo_count = catalog_count
                    else:
                        repo_count = 0
                else:
                    repo_count = "Checking..."
                
                all_registries.append({
                    "status": status,
                    "name": name,
                    "url": registry_url,
                    "repo_count": repo_count,
                    "api_version": api_version
                })
        else:
            # Fallback sample data for development
            if self.mock_mode:
                all_registries = [
                    {"status": "🧪", "name": "Public Registry", "url": "mock://public-registry", "repo_count": 10, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Quay.io Mock", "url": "mock://quay-io", "repo_count": 5, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "GCR Mock", "url": "mock://gcr-io", "repo_count": 5, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Local Dev", "url": "mock://local-dev", "repo_count": 7, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Enterprise", "url": "mock://enterprise", "repo_count": 6, "api_version": "v2 (Mock)"},
                    {"status": "🧪", "name": "Massive Test", "url": "mock://massive-registry", "repo_count": 603, "api_version": "v2 (Mock)"},
                ]
            else:
                all_registries = [
                    {"status": "⏳", "name": "Registry One", "url": "registry-1.example.io", "repo_count": "Checking...", "api_version": "Checking..."},
                    {"status": "⏳", "name": "Red Hat Quay", "url": "quay.io", "repo_count": "Checking...", "api_version": "Checking..."},
                ]
        
        # Smart sorting: local:// first (podman before docker), then localhost/IPs/http://, then https://
        def registry_sort_key(registry):
            url = registry["url"].lower()
            
            # Priority 1: Local runtimes (local://) - podman before docker
            if url.startswith("local://"):
                if "podman" in url:
                    return (1, 0, url)  # podman first
                elif "docker" in url:
                    return (1, 1, url)  # docker second
                else:
                    return (1, 2, url)  # other local runtimes after
            
            # Priority 2: Local network (localhost, 127.0.0.1, private IPs, http://)
            elif (url.startswith("localhost") or 
                  url.startswith("127.0.0.1") or 
                  url.startswith("192.168.") or 
                  url.startswith("10.") or 
                  url.startswith("172.") or
                  url.startswith("http://")):
                return (2, 0, url)
            
            # Priority 3: Remote HTTPS registries
            else:
                return (3, 0, url)
        
        all_registries.sort(key=registry_sort_key, reverse=self.sort_reversed)
            
        for registry in all_registries:
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
        debug_logger.debug("Registry details update requested", 
                          row_index=row_index,
                          total_registries=len(self.registry_data),
                          registry_name=self.registry_data[row_index]["name"] if row_index < len(self.registry_data) else "OUT_OF_BOUNDS")
        
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
            
            # Get monitored repos from auth config if available
            registry_config = self.registry_config.get(registry_url, {}) if hasattr(self, 'registry_config') else {}
            monitored_repos = registry_config.get('monitored_repos', [])
            
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
                    "registry_hash": f"local:{runtime}{hash(registry_url) % 1000:03d}",
                    "monitored_repos": monitored_repos
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
                    "registry_hash": f"sha256:reg{hash(registry_url) % 1000000:06d}",
                    "monitored_repos": monitored_repos
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
                    "registry_hash": registry.get("registry_hash", "Unknown"),
                    "monitored_repos": monitored_repos
                }
            
            details_panel.update_registry_info(detailed_info)
    
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle registry row highlighting (auto-select)"""
        # Only process registry highlighting when this is the main app (not a sub-screen)
        screen_stack_length = len(self.app.screen_stack)
        is_main_screen = screen_stack_length <= 1  # Main screen or no screens pushed
        
        if is_main_screen:
            debug_logger.debug("Registry row highlighted - processing (main screen active)",
                              cursor_row=event.cursor_row,
                              total_registries=len(self.registry_data),
                              screen_stack_length=screen_stack_length)
            self.update_details_for_row(event.cursor_row)
        else:
            debug_logger.debug("Registry row highlighted - ignoring (sub-screen active)",
                              cursor_row=event.cursor_row,
                              total_registries=len(self.registry_data),
                              screen_stack_length=screen_stack_length,
                              current_screen=str(type(self.app.screen).__name__))
    
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
        
        # Pass the registry config to the repository screen
        registry_config = self.registry_config.get(registry["url"], {})
        repo_screen = RepositoryScreen(registry_info=registry_info, registry_config=registry_config, mock_mode=self.mock_mode)
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
                    registry_config = self.registry_config.get(registry_url)
                    status_info = await registry_manager.check_registry_status(registry_url, registry_config)
                
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
                registry_url = registry.get('url', '')
                
                # Check if this registry type supports configuration
                if registry_url.startswith('local://'):
                    self.notify("Local runtimes don't require configuration", severity="info")
                    return
                
                # Get saved auth data for this registry
                saved_config = self.registry_config.get(registry_url, {})
                
                # Create registry data for modal
                registry_data = {
                    'name': registry.get('name', 'Unknown'),
                    'url': registry_url,
                    'username': saved_config.get('username', ''),
                    'auth_type': saved_config.get('auth_type', 'bearer'),
                    'registry_type': saved_config.get('registry_type', ''),
                    'auth_scope': saved_config.get('auth_scope', 'registry:catalog:*'),
                    'max_repos': saved_config.get('max_repos', 100),
                    'cache_ttl': saved_config.get('cache_ttl', 900),
                    'monitored_repos': saved_config.get('monitored_repos', [])
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
                          max_repos=config.get('max_repos', 100),
                          monitored_repos_count=len(config.get('monitored_repos', [])),
                          monitored_repos=config.get('monitored_repos', []))
        
        # Store auth credentials in memory
        self.registry_config[registry_url] = {
            'username': config.get('username', ''),
            'password': config.get('password', ''),
            'auth_type': config.get('auth_type', 'none'),
            'registry_type': config.get('registry_type', 'auto'),
            'auth_scope': config.get('auth_scope', 'registry:catalog:*'),
            'max_repos': config.get('max_repos', 100),
            'cache_ttl': config.get('cache_ttl', 900),
            'monitored_repos': config.get('monitored_repos', [])
        }
        
        # Save to persistent storage (Phase 1: monitored repos and settings only, no credentials)
        try:
            settings = {
                'max_repos': config.get('max_repos', 100),
                'cache_ttl': config.get('cache_ttl', 900),
                'auth_scope': config.get('auth_scope', 'registry:catalog:*')
            }
            
            success = config_manager.save_registry_config(
                registry_url=registry_url,
                registry_name=config.get('registry_name', 'Unknown Registry'),
                monitored_repos=config.get('monitored_repos', []),
                settings=settings
            )
            
            if success:
                debug_logger.debug("Registry configuration persisted to file", 
                                  registry_url=registry_url,
                                  monitored_repos_count=len(config.get('monitored_repos', [])))
            else:
                debug_logger.warning("Failed to persist registry configuration to file")
                
        except Exception as e:
            debug_logger.error(f"Error saving registry configuration to file: {e}")
        
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
        
        self.notify(f"✅ {config['registry_name']} configuration saved")
        
        debug_logger.debug("Registry config stored in memory", 
                          registry_count=len(self.registry_config),
                          has_credentials=bool(config.get('username')))
        
        # Automatically refresh this registry's status
        if not self.mock_mode:
            debug_logger.debug("Triggering registry status refresh", registry_url=registry_url)
            self.run_worker(self._refresh_single_registry(registry_url), exclusive=False)
            self.notify("🔄 Refreshing registry status...")
        else:
            debug_logger.debug("Triggering mock mode registry refresh", registry_url=registry_url)
            self._refresh_mock_registry_count(registry_url)
            self.notify("✅ Registry configuration updated")
    
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
        registry_config = self.registry_config.get(registry_url)
        debug_logger.debug("Using registry config for refresh", 
                          has_registry_config=bool(registry_config),
                          auth_type=registry_config.get('auth_type') if registry_config else 'none')
        
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
                               has_registry_config=bool(registry_config))
            
            status_info = await registry_manager.check_registry_status(registry_url, registry_config)
        
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
    
    def _refresh_mock_registry_count(self, registry_url: str) -> None:
        """Refresh repository count display for mock registry after config changes"""
        debug_logger.debug("Starting mock registry count refresh", registry_url=registry_url)
        registry_table = self.query_one("#registry_list", DataTable)
        
        # Find the registry in our data
        registry_row_index = None
        for idx, registry_data in enumerate(self.registry_data):
            if registry_data["url"] == registry_url:
                registry_row_index = idx
                break
        
        if registry_row_index is None:
            debug_logger.error("Registry not found in data for mock refresh", 
                              registry_url=registry_url,
                              available_registries=[r.get('url') for r in self.registry_data])
            return
        
        debug_logger.debug("Found registry for mock refresh", 
                          registry_index=registry_row_index,
                          registry_name=self.registry_data[registry_row_index].get('name', 'Unknown'))
        
        # Recalculate repository count with updated monitored repos
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
            catalog_repos = mock_registry.registries[mock_url]["repositories"]
            catalog_count = len(catalog_repos)
            
            # Check for updated monitored repos from config
            registry_config = self.registry_config.get(registry_url, {})
            monitored_repos = registry_config.get('monitored_repos', [])
            
            if monitored_repos and len(monitored_repos) > 0:
                # Count how many monitored repos are NOT in the catalog
                monitored_not_in_catalog = [repo for repo in monitored_repos if repo not in catalog_repos]
                total_repos = catalog_count + len(monitored_not_in_catalog)
                updated_repo_count = f"{total_repos}({len(monitored_repos)})"
                
                debug_logger.debug("Mock registry count calculation details", 
                                  catalog_count=catalog_count,
                                  monitored_total=len(monitored_repos),
                                  monitored_not_in_catalog=len(monitored_not_in_catalog),
                                  monitored_not_in_catalog_names=monitored_not_in_catalog,
                                  final_total=total_repos)
            else:
                updated_repo_count = str(catalog_count)
            
            debug_logger.debug("Mock registry count recalculated", 
                              registry_url=registry_url,
                              catalog_count=catalog_count,
                              monitored_count=len(monitored_repos),
                              updated_display=updated_repo_count)
            
            # Update the registry data
            self.registry_data[registry_row_index]["repo_count"] = updated_repo_count
            
            # Update the table row
            registry_table.update_cell_at((registry_row_index, 3), updated_repo_count)
            
            debug_logger.debug("Mock registry table updated", 
                              row_index=registry_row_index,
                              new_count=updated_repo_count)
            
            # If this row is currently selected, update details
            if hasattr(registry_table, 'cursor_coordinate') and registry_table.cursor_coordinate:
                if registry_table.cursor_coordinate[0] == registry_row_index:
                    debug_logger.debug("Updating details panel for refreshed mock registry")
                    self.update_details_for_row(registry_row_index)
        else:
            debug_logger.debug("Mock registry not found in mock data", 
                              mock_url=mock_url,
                              registry_url=registry_url)
    
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
