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
from typing import List, Optional
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Static, Header, Footer
from textual.screen import Screen
from textual.events import MouseDown
from textual.message import Message

from mock_data import mock_registry
from registry_client import registry_manager
from local_container_client import LocalContainerClient
from debug_console import DebugConsoleScreen
from tags_view import TagsScreen


class RegistryDetailsPanel(Static):
    """Right panel showing detailed registry information"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.registry_info = None
    
    def update_registry_info(self, registry_info: dict):
        """Update the displayed registry information"""
        self.registry_info = registry_info
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
🔒 Security: {registry_info.get('ssl_status', 'Local filesystem')}
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
🔒 SSL: {registry_info.get('ssl_status', 'Mock SSL')}
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
🔒 SSL: {registry_info.get('ssl_status', 'Unknown')}
🔗 Registry Hash: {registry_hash}"""
            
            self.update(details)
        else:
            self.update("Select a registry to view details")


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
    
    #repository_list {
        width: 60%;
        border: solid $primary;
        margin: 1;
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
    
    def compose(self) -> ComposeResult:
        """Create the repository view layout"""
        yield Header()
        with Horizontal():
            # Left panel - Repository list
            repo_table = DataTable(id="repository_list", cursor_type="row")
            repo_table.add_columns("📦", "Registry", "Repository Name", "Tags", "Recent Tags", "Last Tag Push")
            yield repo_table
            
            # Right panel - Repository details
            yield RepositoryDetailsPanel(id="repository_details")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the repository view"""
        self.update_title()
        self.load_repositories()
        # Show initial details
        details_panel = self.query_one("#repository_details", RepositoryDetailsPanel)
        details_panel.update("Select a repository to view details")
    
    def update_title(self):
        """Update the title to show loading state"""
        registry_name = self.registry_info.get('name', 'Unknown Registry')
        repo_count = len(self.repository_data)
        
        if self.all_repositories_loaded:
            self.title = f"Repositories - {registry_name} ({repo_count} total)"
        elif repo_count > 0:
            self.title = f"Repositories - {registry_name} ({repo_count} loaded, more available...)"
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
                    
                    repo_table.add_row(
                        "📦",
                        self.registry_info.get('name', 'Unknown'),
                        repo_data["name"],
                        str(repo_data["tag_count"]),
                        repo_data["recent_tags_display"],
                        repo_data["last_updated"]
                    )
                    self.repository_data.append(repo_data)
            else:
                # Fallback if registry not found in mock data
                details_panel.update(f"No repositories found for {registry_url}")
                return
        else:
            # Real registry mode - start background task to load repositories
            self.run_worker(self.load_real_repositories(self.current_limit), exclusive=True)
        
        # Update title after loading
        self.update_title()
        
        # Auto-select first row if data exists
        if self.repository_data:
            repo_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
    
    def update_details_for_row(self, row_index: int) -> None:
        """Update details panel for given row index"""
        details_panel = self.query_one("#repository_details", RepositoryDetailsPanel)
        
        if row_index < len(self.repository_data):
            repo = self.repository_data[row_index]
            
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
        if not self.all_repositories_loaded:
            current_row = event.cursor_row
            total_rows = len(self.repository_data)
            
            # Load more when within 10 rows of the bottom
            if total_rows - current_row <= 10:
                self.current_limit += 100
                self.notify(f"📦 Loading more repositories... ({total_rows} → {self.current_limit})", timeout=2)
                if self.mock_mode:
                    self.load_more_mock_repositories()
                else:
                    self.run_worker(self.load_more_repositories(), exclusive=True)
    
    def on_message(self, message: Message) -> None:
        """Handle scroll messages for auto-loading"""
        # Check if this is a scroll message from the repository table
        if hasattr(message, 'sender') and hasattr(message.sender, 'id') and message.sender.id == "repository_list":
            if not self.all_repositories_loaded and str(type(message).__name__) == "Scroll":
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
                            self.current_limit += 100
                            self.notify(f"📦 Loading more repositories... ({total_rows} → {self.current_limit})", timeout=2)
                            if self.mock_mode:
                                self.load_more_mock_repositories()
                            else:
                                self.run_worker(self.load_more_repositories(), exclusive=True)
    

    def on_key(self, event) -> None:
        """Handle key presses"""
        if event.key == "enter":
            # Get currently selected repository and navigate to tags view
            repo_table = self.query_one("#repository_list", DataTable)
            if hasattr(repo_table, 'cursor_coordinate') and repo_table.cursor_coordinate:
                row_index = repo_table.cursor_coordinate[0]
                if row_index < len(self.repository_data):
                    repo = self.repository_data[row_index]
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
        
        # Rebuild table
        repo_table = self.query_one("#repository_list", DataTable)
        repo_table.clear()
        
        for repo_data in self.repository_data:
            repo_table.add_row(
                "📦",
                self.registry_info.get('name', 'Unknown'),
                repo_data["name"],
                str(repo_data.get("tag_count", "Unknown")),
                repo_data.get("recent_tags_display", "Unknown"),
                repo_data.get("last_updated", "Unknown")
            )
    
    # def on_mouse_down(self, event: MouseDown) -> None:
    #     """Handle mouse button events"""
    #     # Mouse back button (button 3 or 4 depending on system)
    #     if hasattr(event, 'button') and event.button in [3, 4]:
    #         self.action_back()
    
    def action_back(self) -> None:
        """Go back to registry list"""
        self.app.pop_screen()
    
    async def load_real_repositories(self, limit: int = 50) -> None:
        """Background task to load real repository data"""
        repo_table = self.query_one("#repository_list", DataTable)
        registry_url = self.registry_info.get('url', '')
        
        if not registry_url:
            return
        
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
            repositories = await registry_manager.get_repositories(registry_url, limit)
        
        # Check if we got fewer repositories than requested (indicates we've loaded all)
        if len(repositories) < limit:
            self.all_repositories_loaded = True
        
        for repo_data in repositories:
            repo_table.add_row(
                "📦",
                self.registry_info.get('name', 'Unknown'),
                repo_data["name"],
                str(repo_data.get("tag_count", "Unknown")),
                repo_data.get("recent_tags_display", "Unknown"),
                repo_data.get("last_updated", "Unknown")
            )
            self.repository_data.append(repo_data)
        
        # Update title after loading
        self.update_title()
        
        # Auto-select first row if data exists
        if self.repository_data:
            repo_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
    
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
            
            repo_table.add_row(
                "📦",
                self.registry_info.get('name', 'Unknown'),
                repo_data["name"],
                str(repo_data["tag_count"]),
                repo_data["recent_tags_display"],
                repo_data["last_updated"]
            )
            self.repository_data.append(repo_data)
        
        # Check if we've loaded everything
        if len(self.repository_data) >= len(all_repositories):
            self.all_repositories_loaded = True
        
        # Update title to reflect current state
        self.update_title()
        self.notify(f"📦 Loaded {len(new_repositories)} more repositories", timeout=1.5)

    async def load_more_repositories(self) -> None:
        """Load additional repositories beyond current limit"""
        registry_url = self.registry_info.get('url', '')
        if not registry_url:
            return
        
        # Get the next batch starting from current length
        current_count = len(self.repository_data)
        additional_repositories = await registry_manager.get_repositories(
            registry_url, 
            limit=self.current_limit
        )
        
        # Only add repositories we don't already have
        new_repos = additional_repositories[current_count:]
        
        if not new_repos:
            self.all_repositories_loaded = True
            self.notify("✅ All repositories loaded", timeout=2)
            self.update_title()
            return
        
        repo_table = self.query_one("#repository_list", DataTable)
        
        for repo_data in new_repos:
            repo_table.add_row(
                "📦",
                self.registry_info.get('name', 'Unknown'),
                repo_data["name"],
                str(repo_data.get("tag_count", "Unknown")),
                repo_data.get("recent_tags_display", "Unknown"),
                repo_data.get("last_updated", "Unknown")
            )
            self.repository_data.append(repo_data)
        
        # Check if we've loaded everything
        if len(additional_repositories) < self.current_limit:
            self.all_repositories_loaded = True
        
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
        
        # Reload repositories
        self.load_repositories()
    
    def action_load_more(self) -> None:
        """Load more repositories"""
        if not self.all_repositories_loaded:
            self.current_limit += 100
            self.notify(f"Loading more repositories (up to {self.current_limit})...")
            
            if self.mock_mode:
                self.load_more_mock_repositories()
            else:
                # Clear existing data and reload with higher limit for real mode
                repo_table = self.query_one("#repository_list", DataTable)
                repo_table.clear()
                self.repository_data = []
                self.all_repositories_loaded = False
                
                self.run_worker(self.load_real_repositories(self.current_limit), exclusive=True)
        else:
            self.notify("All repositories already loaded", severity="warning")
    
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
    }
    """
    
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("f5", "refresh", "Refresh"),
        ("r", "reverse_sort", "Reverse Sort"),
        ("ctrl+d", "debug_console", "Debug Console"),
    ]
    
    def __init__(self, registries: List[str], mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.registries = registries
        self.mock_mode = mock_mode
        self.registry_data = []
        self.last_click_time = 0
        self.last_clicked_row = -1
        self.sort_reversed = False
        
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
        # Show initial details
        details_panel = self.query_one("#registry_details", RegistryDetailsPanel)
        details_panel.update("Select a registry to view details")
        
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
                    "ssl_status": registry.get("ssl_status", "Local filesystem"),
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
                    "ssl_status": "Mock SSL",
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
                    "ssl_status": registry.get("ssl_status", "Unknown"),
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
        self.notify("Refreshing registries...")
        
        if not self.mock_mode and self.registries:
            # Re-check real registries
            self.run_worker(self.check_real_registries(), exclusive=True)
        else:
            # In mock mode, just reload the data
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
                    status_info = await registry_manager.check_registry_status(registry_url)
                
                # Update the registry data
                self.registry_data[registry_row_index].update({
                    "status": status_info["status"],
                    "api_version": status_info["api_version"],
                    "repo_count": status_info["repo_count"],
                    "response_time": status_info["response_time"],
                    "ssl_status": status_info["ssl_status"],
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
    
    def action_quit(self) -> None:
        """Quit the application"""
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
        "--version",
        action="version", 
        version="Container Card Catalog 0.1.0"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Handle registry and mock mode logic
    registries = args.registries or []
    local_runtimes = args.local or []
    mock_mode = args.mock
    
    # Add local runtimes to registry list
    for runtime in local_runtimes:
        registries.append(f"local://{runtime}")
    
    # If --mock is specified, use mock registries even if --registry was provided
    if mock_mode and not registries:
        # Default mock registries when --mock is used without --registry
        pass  # Will be set below
    elif mock_mode and registries:
        # --mock flag with --registry should override to use mock data
        pass  # Keep provided registries but run in mock mode
    elif not mock_mode and not registries:
        # No flags - default to mock mode
        mock_mode = True
    
    if mock_mode and not registries:
        registries = ["mock://public-registry", "mock://quay-io", "mock://gcr-io", "mock://local-dev", "mock://enterprise", "mock://massive-registry"]
    
    app = ContainerCardCatalog(registries=registries, mock_mode=mock_mode)
    app.run()


if __name__ == "__main__":
    main()
