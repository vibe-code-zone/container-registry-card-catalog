"""
Tags View Screen

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
from textual.message import Message
from textual.events import MouseDown
from local_container_client import LocalContainerClient
from registry_client import sort_tags_by_timestamp


class TagDetailsPanel(Static):
    """Right panel showing detailed tag information"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tag_info = None
    
    def update_tag_info(self, tag_info: dict):
        """Update the displayed tag information"""
        self.tag_info = tag_info
        if tag_info:
            registry_url = tag_info.get('registry_url', 'Unknown')
            repo_name = tag_info.get('repository', 'Unknown')
            tag_name = tag_info.get('tag', 'Unknown')
            image_id = tag_info.get('image_id', 'Unknown')
            digest = tag_info.get('digest_short', tag_info.get('digest', 'Unknown'))
            
            # Handle local images differently
            if registry_url.startswith('local://'):
                runtime = registry_url.split('://')[1]
                
                if repo_name == '<orphaned>':
                    details = f"""🏷️ Tag: {tag_name}
📦 Repository: {repo_name} (orphaned image)
🆔 Image ID: {image_id}
📅 Created: {tag_info.get('created', 'Unknown')}
📏 Size: {tag_info.get('size', 'Unknown')}
🔗 Digest: {digest}
🏠 Runtime: {runtime.title()}

⚠️ Orphaned Image - No Pull Command Available
🗑️ Cleanup Commands:
{runtime} rmi {image_id}
{runtime} image prune"""
                
                elif tag_name.startswith('sha256:'):
                    # Image pulled by digest
                    details = f"""🏷️ Tag: {tag_name} (digest-only)
📦 Repository: {repo_name}
🆔 Image ID: {image_id}
📅 Created: {tag_info.get('created', 'Unknown')}
📏 Size: {tag_info.get('size', 'Unknown')}
🔗 Digest: {digest}
🏠 Runtime: {runtime.title()}

🔍 Inspect Commands:
{runtime} inspect {image_id}
{runtime} inspect {repo_name}@{tag_info.get('digest', digest)}

🔧 Useful Commands:
{runtime} tag {image_id} {repo_name}:latest
{runtime} save -o image.tar {image_id}"""
                
                else:
                    # Normal tagged image
                    full_image = f"{repo_name}:{tag_name}"
                    details = f"""🏷️ Tag: {tag_name}
📦 Repository: {repo_name}
🆔 Image ID: {image_id}
📅 Created: {tag_info.get('created', 'Unknown')}
📏 Size: {tag_info.get('size', 'Unknown')}
🔗 Digest: {digest}
🏠 Runtime: {runtime.title()}

🔍 Inspect Commands:
{runtime} inspect {full_image}
{runtime} inspect {image_id}

🔧 Useful Commands:
{runtime} save -o image.tar {full_image}
{runtime} tag {image_id} new-name:tag"""
            
            else:
                # Remote registry
                full_image = f"{registry_url}/{repo_name}:{tag_name}"
                details = f"""🏷️ Tag: {tag_name}
📦 Repository: {repo_name}
🌐 Manifest API: {registry_url}/v2/{repo_name}/manifests/{tag_name}
📅 Created: {tag_info.get('created', 'Unknown')}
📏 Size: {tag_info.get('size', 'Unknown')}
🔗 Digest: {digest}
🏢 Registry: {registry_url}

📥 Pull Command:
podman image pull {full_image}

🔧 Alternative Commands:
docker pull {full_image}
skopeo copy docker://{full_image} oci:local-{tag_name}"""
            
            self.update(details)
        else:
            self.update("Select a tag to view details")


class TagsScreen(Screen):
    """Screen for browsing tags within a selected repository"""
    
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    #tags_list {
        width: 60%;
        border: solid $primary;
        margin: 1;
    }
    
    #tag_details {
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
    
    def __init__(self, repository_info: dict, mock_mode: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.repository_info = repository_info
        self.mock_mode = mock_mode
        self.tag_data = []
        self.current_limit = 50
        self.all_tags_loaded = False
        self.last_scroll_load_time = 0
        self.last_click_time = 0
        self.last_clicked_row = -1
        self.sort_reversed = False
    
    def compose(self) -> ComposeResult:
        """Create the tags view layout"""
        yield Header()
        with Horizontal():
            # Left panel - Tags list
            tags_table = DataTable(id="tags_list", cursor_type="row")
            tags_table.add_columns("Tag", "Registry", "Repository", "Tag Name", "Size", "Created")
            yield tags_table
            
            # Right panel - Tag details
            yield TagDetailsPanel(id="tag_details")
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the tags view"""
        repo_name = self.repository_info.get('name', 'Unknown')
        self.update_title()
        self.load_tags()
        # Show initial details
        details_panel = self.query_one("#tag_details", TagDetailsPanel)
        details_panel.update("Select a tag to view details")
    
    def update_title(self):
        """Update the title to show loading state"""
        repo_name = self.repository_info.get('name', 'Unknown')
        tag_count = len(self.tag_data)
        
        if self.all_tags_loaded:
            self.title = f"Tags - {repo_name} ({tag_count} total)"
        elif tag_count > 0:
            self.title = f"Tags - {repo_name} ({tag_count} loaded, more available...)"
        else:
            self.title = f"Tags - {repo_name} (loading...)"
    
    def load_tags(self) -> None:
        """Load tags for the selected repository"""
        tags_table = self.query_one("#tags_list", DataTable)
        registry_url = self.repository_info.get('registry_url', '')
        repo_name = self.repository_info.get('name', '')
        
        if self.mock_mode and registry_url and repo_name:
            # Map any registry URL to a mock registry when in mock mode
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
            
            tags_response = mock_registry.get_tags(mock_url, repo_name)
            
            if tags_response["status_code"] == 200:
                all_available_tags = tags_response["json"]["tags"]
                
                # Respect the current limit for auto-loading behavior
                all_tags = all_available_tags[:self.current_limit]
                
                # Check if we've loaded all available tags
                if len(all_tags) >= len(all_available_tags):
                    self.all_tags_loaded = True
                
                for tag_name in all_tags:
                    tag_data = {
                        "tag": tag_name,
                        "repository": repo_name,
                        "registry_url": registry_url,
                        "size": "42.3 MB",  # Mock data
                        "created": "2 days ago",  # Mock data
                        "digest": f"sha256:mock{hash(tag_name) % 1000000:06d}"  # Mock digest
                    }
                    
                    # Extract registry name from URL
                    registry_name = registry_url.replace("https://", "").replace("http://", "").replace("mock://", "Mock ")
                    
                    tags_table.add_row(
                        "Tag",
                        registry_name,
                        repo_name,
                        tag_data["tag"],
                        tag_data["size"],
                        tag_data["created"]
                    )
                    self.tag_data.append(tag_data)
        else:
            # Real registry mode - start background task to load tags
            self.run_worker(self.load_real_tags(), exclusive=True)
        
        # Update title after loading
        self.update_title()
        
        # Auto-select first row if data exists
        if self.tag_data:
            tags_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
    
    async def load_real_tags(self) -> None:
        """Background task to load real tag data"""
        tags_table = self.query_one("#tags_list", DataTable)
        registry_url = self.repository_info.get('registry_url', '')
        repo_name = self.repository_info.get('name', '')
        
        if not registry_url or not repo_name:
            return
        
        # Handle local container runtimes
        if registry_url.startswith("local://"):
            runtime = registry_url.split("://")[1]
            client = LocalContainerClient(runtime)
            tags_response = await client.get_tags(repo_name)
            
            if 'error' in tags_response:
                self.notify(f"❌ Error loading {runtime} tags: {tags_response['error']}", severity="error")
                return
                
            tags_data = tags_response.get('data', {}).get('tags', [])
            self.all_tags_loaded = True  # Local data is always complete
            
            for tag_data in tags_data:
                self.tag_data.append(tag_data)
                
                # Add to table - columns are: Tag, Registry, Repository, Tag Name, Size, Created
                tags_table.add_row(
                    "Tag",
                    f"Local {runtime.title()}",
                    repo_name,
                    tag_data.get("name", "Unknown"),
                    tag_data.get("size", "Unknown"),
                    tag_data.get("created", "Unknown")
                )
            
            # Update title after loading local tags
            self.update_title()
            
            # Auto-select first row if data exists
            if self.tag_data:
                tags_table.cursor_coordinate = (0, 0)
                self.update_details_for_row(0)
            
            return
        
        from registry_client import registry_manager, RegistryClient
        
        async with RegistryClient(registry_url) as client:
            # Get tags list
            tags_response = await client.get_tags(repo_name)
            registry_manager.add_api_call(tags_response)
            
            if tags_response["status_code"] == 200:
                response_json = tags_response.get("json", {})
                all_available_tags = response_json.get("tags", [])
                manifest_metadata = response_json.get("manifest", {})
                
                # Sort tags using timestamp-based sorting
                sorted_available_tags = sort_tags_by_timestamp(all_available_tags, manifest_metadata)
                
                # Build tag-to-timestamp mapping for display dates
                tag_timestamps = {}
                for manifest_sha, manifest_data in manifest_metadata.items():
                    tags_for_manifest = manifest_data.get("tag", [])
                    time_uploaded = manifest_data.get("timeUploadedMs", "0")
                    time_created = manifest_data.get("timeCreatedMs", "0")
                    
                    # Use upload time if available, otherwise creation time
                    timestamp = int(time_uploaded) if time_uploaded != "0" else int(time_created)
                    
                    for tag in tags_for_manifest:
                        tag_timestamps[tag] = timestamp
                
                # Load tag data (limit to current limit for auto-loading)
                all_tags = sorted_available_tags[:self.current_limit]
                
                # Check if we've loaded all available tags
                if len(all_tags) >= len(sorted_available_tags):
                    self.all_tags_loaded = True
                
                for tag_name in all_tags:
                    # Get timestamp and convert to human readable
                    timestamp = tag_timestamps.get(tag_name, 0)
                    if timestamp > 0:
                        import datetime
                        # Convert from milliseconds to seconds for datetime
                        dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                        created_str = dt.strftime("%Y-%m-%d %H:%M")
                    else:
                        created_str = "Unknown"
                    
                    tag_data = {
                        "tag": tag_name,
                        "repository": repo_name,
                        "registry_url": registry_url,
                        "size": "Unknown",  # TODO: Get from manifest
                        "created": created_str,
                        "digest": "Unknown"  # TODO: Get from manifest
                    }
                    
                    # Extract registry name from URL
                    registry_name = registry_url.replace("https://", "").replace("http://", "").replace("mock://", "Mock ")
                    
                    tags_table.add_row(
                        "Tag",
                        registry_name,
                        repo_name,
                        tag_data["tag"],
                        tag_data["size"],
                        tag_data["created"]
                    )
                    self.tag_data.append(tag_data)
        
        # Update title after loading
        self.update_title()
        
        # Auto-select first row if data exists
        if self.tag_data:
            tags_table.cursor_coordinate = (0, 0)
            self.update_details_for_row(0)
    
    def load_more_mock_tags(self) -> None:
        """Load additional mock tags beyond current limit"""
        registry_url = self.repository_info.get('registry_url', '')
        repo_name = self.repository_info.get('name', '')
        
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
        
        # Get all tags from mock data
        from mock_data import mock_registry
        tags_response = mock_registry.get_tags(mock_url, repo_name)
        if tags_response["status_code"] != 200:
            return
            
        all_available_tags = tags_response["json"]["tags"]
        current_count = len(self.tag_data)
        
        # Get the next batch of tags
        new_tags = all_available_tags[current_count:self.current_limit]
        
        if not new_tags:
            self.all_tags_loaded = True
            self.notify("✅ All tags loaded", timeout=2)
            self.update_title()
            return
        
        tags_table = self.query_one("#tags_list", DataTable)
        
        for tag_name in new_tags:
            tag_data = {
                "tag": tag_name,
                "repository": repo_name,
                "registry_url": registry_url,
                "size": "42.3 MB",  # Mock data
                "created": "2 days ago",  # Mock data
                "digest": f"sha256:mock{hash(tag_name) % 1000000:06d}"  # Mock digest
            }
            
            # Extract registry name from URL
            registry_name = registry_url.replace("https://", "").replace("http://", "").replace("mock://", "Mock ")
            
            tags_table.add_row(
                "Tag",
                registry_name,
                repo_name,
                tag_data["tag"],
                tag_data["size"],
                tag_data["created"]
            )
            self.tag_data.append(tag_data)
        
        # Check if we've loaded everything
        if len(self.tag_data) >= len(all_available_tags):
            self.all_tags_loaded = True
        
        # Update title to reflect current state
        self.update_title()
        self.notify(f"🏷️ Loaded {len(new_tags)} more tags", timeout=1.5)

    async def load_more_real_tags(self) -> None:
        """Load additional real tags beyond current limit"""
        registry_url = self.repository_info.get('registry_url', '')
        repo_name = self.repository_info.get('name', '')
        
        if not registry_url or not repo_name:
            return
        
        from registry_client import registry_manager, RegistryClient
        
        async with RegistryClient(registry_url) as client:
            # Get tags list
            tags_response = await client.get_tags(repo_name)
            registry_manager.add_api_call(tags_response)
            
            if tags_response["status_code"] == 200:
                response_json = tags_response.get("json", {})
                all_available_tags = response_json.get("tags", [])
                manifest_metadata = response_json.get("manifest", {})
                
                # Sort all tags using timestamp-based sorting
                sorted_available_tags = sort_tags_by_timestamp(all_available_tags, manifest_metadata)
                
                # Build tag-to-timestamp mapping for display dates
                tag_timestamps = {}
                for manifest_sha, manifest_data in manifest_metadata.items():
                    tags_for_manifest = manifest_data.get("tag", [])
                    time_uploaded = manifest_data.get("timeUploadedMs", "0")
                    time_created = manifest_data.get("timeCreatedMs", "0")
                    
                    # Use upload time if available, otherwise creation time
                    timestamp = int(time_uploaded) if time_uploaded != "0" else int(time_created)
                    
                    for tag in tags_for_manifest:
                        tag_timestamps[tag] = timestamp
                
                current_count = len(self.tag_data)
                
                # Get the next batch of tags from sorted list
                new_tags = sorted_available_tags[current_count:self.current_limit]
                
                if not new_tags:
                    self.all_tags_loaded = True
                    self.notify("✅ All tags loaded", timeout=2)
                    self.update_title()
                    return
                
                tags_table = self.query_one("#tags_list", DataTable)
                
                for tag_name in new_tags:
                    # Get timestamp and convert to human readable
                    timestamp = tag_timestamps.get(tag_name, 0)
                    if timestamp > 0:
                        import datetime
                        # Convert from milliseconds to seconds for datetime
                        dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                        created_str = dt.strftime("%Y-%m-%d %H:%M")
                    else:
                        created_str = "Unknown"
                    
                    tag_data = {
                        "tag": tag_name,
                        "repository": repo_name,
                        "registry_url": registry_url,
                        "size": "Unknown",  # TODO: Get from manifest
                        "created": created_str,
                        "digest": "Unknown"  # TODO: Get from manifest
                    }
                    
                    # Extract registry name from URL
                    registry_name = registry_url.replace("https://", "").replace("http://", "").replace("mock://", "Mock ")
                    
                    tags_table.add_row(
                        "Tag",
                        registry_name,
                        repo_name,
                        tag_data["tag"],
                        tag_data["size"],
                        tag_data["created"]
                    )
                    self.tag_data.append(tag_data)
                
                # Check if we've loaded everything
                if len(self.tag_data) >= len(all_available_tags):
                    self.all_tags_loaded = True
                
                # Update title to reflect current state
                self.update_title()
                self.notify(f"🏷️ Loaded {len(new_tags)} more tags", timeout=1.5)
    
    def update_details_for_row(self, row_index: int) -> None:
        """Update details panel for given row index"""
        details_panel = self.query_one("#tag_details", TagDetailsPanel)
        
        if row_index < len(self.tag_data):
            tag = self.tag_data[row_index]
            details_panel.update_tag_info(tag)
    
    
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle tag row highlighting (auto-select)"""
        self.update_details_for_row(event.cursor_row)
        
        # Auto-load more tags when approaching the bottom
        if not self.all_tags_loaded:
            current_row = event.cursor_row
            total_rows = len(self.tag_data)
            
            # Load more when within 10 rows of the bottom
            if total_rows - current_row <= 10:
                self.current_limit += 50
                self.notify(f"🏷️ Loading more tags... ({total_rows} → {self.current_limit})", timeout=2)
                if self.mock_mode:
                    self.load_more_mock_tags()
                else:
                    self.run_worker(self.load_more_real_tags(), exclusive=True)
    
    def on_message(self, message: Message) -> None:
        """Handle scroll messages for auto-loading"""
        # Check if this is a scroll message from the tags table
        if hasattr(message, 'sender') and hasattr(message.sender, 'id') and message.sender.id == "tags_list":
            if not self.all_tags_loaded and str(type(message).__name__) == "Scroll":
                import time
                current_time = time.time()
                
                # Throttle scroll-based loading to prevent excessive requests (2 second cooldown)
                if current_time - self.last_scroll_load_time < 2:
                    return
                
                tags_table = self.query_one("#tags_list", DataTable)
                
                # Get scroll information
                if hasattr(tags_table, 'scroll_offset'):
                    scroll_y = tags_table.scroll_offset.y
                    total_height = tags_table.virtual_size.height
                    visible_height = tags_table.size.height
                    
                    # Check if we're scrolled near the bottom (within 90% of total scroll)
                    if total_height > 0 and (scroll_y + visible_height) / total_height > 0.9:
                        total_rows = len(self.tag_data)
                        if total_rows > 0:  # Only load if we have data
                            self.last_scroll_load_time = current_time
                            self.current_limit += 50
                            self.notify(f"🏷️ Loading more tags... ({total_rows} → {self.current_limit})", timeout=2)
                            if self.mock_mode:
                                self.load_more_mock_tags()
                            else:
                                self.run_worker(self.load_more_real_tags(), exclusive=True)
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle tag selection and double-click detection"""
        # Only handle events if this is the TagsScreen
        if not isinstance(self, TagsScreen):
            return
            
        import time
        current_time = time.time()
        
        # Double-click detection (within 500ms of previous click on same row)
        if (current_time - self.last_click_time < 0.5 and 
            self.last_clicked_row == event.cursor_row and
            event.cursor_row < len(self.tag_data)):
            
            # Double-click detected - show tag detail modal
            tag = self.tag_data[event.cursor_row]
            self.show_tag_detail_modal(tag)
            event.stop()  # Prevent event bubbling
        else:
            # Single click - update details (let row highlighting handle this)
            pass
        
        # Update click tracking and stop event bubbling
        self.last_click_time = current_time
        self.last_clicked_row = event.cursor_row
        event.stop()  # Prevent event bubbling

    def on_key(self, event) -> None:
        """Handle key presses"""
        if event.key == "enter":
            # Get currently selected tag and show detailed modal
            tags_table = self.query_one("#tags_list", DataTable)
            if hasattr(tags_table, 'cursor_coordinate') and tags_table.cursor_coordinate:
                row_index = tags_table.cursor_coordinate[0]
                if row_index < len(self.tag_data):
                    tag = self.tag_data[row_index]
                    self.show_tag_detail_modal(tag)
                event.stop()  # Prevent event bubbling
    
    def show_tag_detail_modal(self, tag_data: dict) -> None:
        """Show tag details in modal"""
        from tag_detail_modal import TagDetailModal
        
        # Find the index of the selected tag
        current_index = 0
        for i, tag in enumerate(self.tag_data):
            if tag.get('tag') == tag_data.get('tag'):
                current_index = i
                break
        
        modal = TagDetailModal(
            tag_data, 
            mock_mode=self.mock_mode, 
            all_tags=self.tag_data, 
            current_index=current_index
        )
        self.app.push_screen(modal)
    
    def action_debug_console(self) -> None:
        """Open debug console"""
        from debug_console import DebugConsoleScreen
        debug_screen = DebugConsoleScreen(mock_mode=self.mock_mode)
        self.app.push_screen(debug_screen)
    
    def action_reverse_sort(self) -> None:
        """Reverse the current sort order"""
        # Simply reverse the current list order
        self.tag_data.reverse()
        self.notify("Tag sort reversed")
        
        # Rebuild table
        tags_table = self.query_one("#tags_list", DataTable)
        tags_table.clear()
        
        for tag_data in self.tag_data:
            tags_table.add_row(
                "Tag",
                self.repository_info.get('registry_url', 'Unknown').split('//')[-1],
                tag_data.get("tag", tag_data.get("name", "Unknown")),
                tag_data.get("image_id", "Unknown")[:12],
                tag_data.get("size", "Unknown"),
                tag_data.get("created", "Unknown")
            )
    
    # def on_mouse_down(self, event: MouseDown) -> None:
    #     """Handle mouse button events"""
    #     # Mouse back button (button 3 or 4 depending on system)
    #     if hasattr(event, 'button') and event.button in [3, 4]:
    #         self.action_back()
    
    def action_back(self) -> None:
        """Go back to repository list"""
        self.app.pop_screen()
    
    def action_refresh(self) -> None:
        """Refresh tags"""
        self.notify("Refreshing tags...")
        # Clear existing data
        tags_table = self.query_one("#tags_list", DataTable)
        tags_table.clear()
        self.tag_data = []
        
        # Reset state
        self.current_limit = 50
        self.all_tags_loaded = False
        
        # Reload tags
        self.load_tags()
    
    def action_load_more(self) -> None:
        """Load more tags"""
        if not self.all_tags_loaded:
            self.current_limit += 50
            self.notify(f"Loading more tags (up to {self.current_limit})...")
            
            if self.mock_mode:
                self.load_more_mock_tags()
            else:
                self.run_worker(self.load_more_real_tags(), exclusive=True)
        elif self.all_tags_loaded:
            self.notify("All tags already loaded", severity="warning")
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()
