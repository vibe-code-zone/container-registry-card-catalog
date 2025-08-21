"""
Tag Detail Modal

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
from textual.events import MouseDown


class TagDetailModal(ModalScreen):
    """Modal screen for displaying detailed tag information"""
    
    CSS = """
    TagDetailModal {
        align: center middle;
    }
    
    #modal_container {
        width: 90%;
        height: 85%;
        border: solid $primary;
        background: $surface;
        layout: vertical;
    }
    
    #content_container {
        height: 1fr;
        padding: 1;
        layout: horizontal;
    }
    
    #left_pane {
        width: 50%;
        margin-right: 1;
        layout: vertical;
    }
    
    #right_pane {
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
    
    #layers_table {
        height: 18;
        margin: 1 0;
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
        ("escape", "close", "Close"),
        ("backspace", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+c", "copy_digest", "Copy Digest"),
        ("pageup", "previous_tag", "Previous Tag"),
        ("pagedown", "next_tag", "Next Tag"),
        ("up", "previous_tag", "Previous Tag"),
        ("down", "next_tag", "Next Tag"),
    ]
    
    def __init__(self, tag_info: dict, mock_mode: bool = False, all_tags: list = None, current_index: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.tag_info = tag_info
        self.mock_mode = mock_mode
        self.manifest_data = None
        self.all_tags = all_tags or [tag_info]
        self.current_index = current_index
    
    def compose(self) -> ComposeResult:
        """Create the modal layout"""
        with Vertical(id="modal_container"):
            # Content area with tag details
            with Horizontal(id="content_container"):
                # Left pane - Tag info and manifest
                with Vertical(id="left_pane"):
                    yield Static("TAG DETAILS", classes="pane_title")
                    with ScrollableContainer(classes="pane_content"):
                        yield Static(self._format_tag_details(), id="tag_content")
                
                # Right pane - Layers and technical details
                with Vertical(id="right_pane"):
                    yield Static("MANIFEST & LAYERS", classes="pane_title")
                    with ScrollableContainer(classes="pane_content"):
                        yield Static(self._format_manifest_details(), id="manifest_content")
                        
                        # Layers table
                        layers_table = DataTable(id="layers_table")
                        layers_table.add_columns("Layer", "Media Type", "Digest", "Size")
                        yield layers_table
            
            # Button container at bottom
            with Horizontal(id="button_container"):
                yield Button("Copy Digest", id="copy_btn", variant="default")
                yield Button("Close", id="close_btn", variant="primary")
    
    def on_mount(self) -> None:
        """Initialize the modal"""
        tag_name = self.tag_info.get('tag', 'Unknown')
        if len(self.all_tags) > 1:
            self.title = f"Tag Details - {tag_name} ({self.current_index + 1}/{len(self.all_tags)})"
        else:
            self.title = f"Tag Details - {tag_name}"
        self.load_manifest_data()
        self.populate_layers_table()
    
    def _format_tag_details(self) -> str:
        """Format the basic tag information"""
        tag = self.tag_info
        registry_url = tag.get('registry_url', 'Unknown')
        repo_name = tag.get('repository', 'Unknown')
        tag_name = tag.get('tag', 'Unknown')
        
        content_lines = [
            f"Tag: {tag_name}",
            f"Repository: {repo_name}",
            f"Registry: {registry_url}",
            f"Created: {tag.get('created', 'Unknown')}",
            f"Size: {tag.get('size', 'Unknown')}",
            "",
            "Image Digest:",
            f"{tag.get('digest', 'Unknown')}",
            ""
        ]
        
        # Different commands for local vs remote
        if registry_url.startswith('local://'):
            runtime = registry_url.split('://')[1]
            if tag_name.startswith('sha256:'):
                # Digest-only image
                content_lines.extend([
                    "Inspect Commands:",
                    f"{runtime} inspect {repo_name}@{tag.get('digest', 'unknown')}",
                    f"{runtime} inspect {tag.get('image_id', 'unknown')}",
                    "",
                    "Useful Commands:",
                    f"{runtime} tag {tag.get('image_id', 'unknown')} {repo_name}:latest",
                    f"{runtime} save -o {repo_name.split('/')[-1]}-export.tar {tag.get('image_id', 'unknown')}"
                ])
            else:
                # Normal tagged image
                full_image = f"{repo_name}:{tag_name}"
                content_lines.extend([
                    "Inspect Commands:",
                    f"{runtime} inspect {full_image}",
                    f"{runtime} inspect {tag.get('image_id', 'unknown')}",
                    "",
                    "Useful Commands:",
                    f"{runtime} save -o {repo_name.split('/')[-1]}-{tag_name}.tar {full_image}",
                    f"{runtime} tag {full_image} new-name:tag"
                ])
        else:
            # Remote registry
            content_lines.extend([
                "Pull Commands:",
                f"podman image pull {registry_url}/{repo_name}:{tag_name}",
                f"docker pull {registry_url}/{repo_name}:{tag_name}",
                "",
                "Inspect Commands:",
                f"podman image inspect {registry_url}/{repo_name}:{tag_name}",
                f"skopeo inspect docker://{registry_url}/{repo_name}:{tag_name}",
                "",
                "Manifest API:",
                f"{registry_url}/v2/{repo_name}/manifests/{tag_name}"
            ])
        
        return "\n".join(content_lines)
    
    def _format_manifest_details(self) -> str:
        """Format the manifest and technical details"""
        if self.mock_mode:
            return self._format_mock_manifest()
        else:
            # TODO: Get real manifest data
            return """📋 Manifest Data:
Loading manifest information...

🔍 Note: Real manifest data will be fetched from:
GET /v2/{repo}/manifests/{tag}

This will include:
• Manifest schema version
• Media type
• Configuration blob digest
• Layer information
• Platform details"""
    
    def _format_mock_manifest(self) -> str:
        """Format mock manifest data"""
        tag = self.tag_info
        content_lines = [
            "Manifest Schema: v2",
            "Media Type: application/vnd.docker.distribution.manifest.v2+json",
            f"Config Digest: sha256:config{hash(tag.get('tag', '')) % 1000000:06d}",
            "Architecture: amd64",
            "OS: linux",
            "",
            "Manifest Digest:",
            f"{tag.get('digest', 'sha256:manifest' + str(hash(tag.get('tag', '')) % 1000000).zfill(6))}",
            "",
            "Layer Count: 3",
            f"Total Size: {tag.get('size', '42.3 MB')}",
            f"Last Modified: {tag.get('created', '2 days ago')}"
        ]
        return "\n".join(content_lines)
    
    def load_manifest_data(self) -> None:
        """Load manifest data (mock, local, or real)"""
        if self.mock_mode:
            # Create mock manifest data
            tag_name = self.tag_info.get('tag', 'unknown')
            self.manifest_data = {
                "config": {
                    "digest": f"sha256:config{hash(tag_name) % 1000000:06d}",
                    "size": 1234
                },
                "layers": [
                    {
                        "digest": f"sha256:layer1{hash(tag_name) % 100000:05d}",
                        "size": 5432100,
                        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip"
                    },
                    {
                        "digest": f"sha256:layer2{hash(tag_name + '2') % 100000:05d}",
                        "size": 1234567,
                        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip"
                    },
                    {
                        "digest": f"sha256:layer3{hash(tag_name + '3') % 100000:05d}",
                        "size": 987654,
                        "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip"
                    }
                ]
            }
        elif self.tag_info.get('registry_url', '').startswith('local://'):
            # Start background task to fetch local container manifest data
            self.run_worker(self.fetch_local_manifest_data(), exclusive=True)
        else:
            # Start background task to fetch real HTTP registry manifest data
            self.run_worker(self.fetch_manifest_data(), exclusive=True)
    
    async def fetch_manifest_data(self) -> None:
        """Background task to fetch real manifest data"""
        registry_url = self.tag_info.get('registry_url', '')
        repo_name = self.tag_info.get('repository', '')
        tag_name = self.tag_info.get('tag', '')
        
        if not all([registry_url, repo_name, tag_name]):
            return
        
        from registry_client import registry_manager, RegistryClient
        
        async with RegistryClient(registry_url) as client:
            manifest_response = await client.get_manifest(repo_name, tag_name)
            registry_manager.add_api_call(manifest_response)
            
            if manifest_response["status_code"] == 200 and manifest_response.get("json"):
                manifest_json = manifest_response["json"]
                
                # Extract manifest data based on schema version and media type
                media_type = manifest_json.get("mediaType", "")
                schema_version = manifest_json.get("schemaVersion", 1)
                
                if schema_version >= 2 or "oci.image.manifest" in media_type:
                    # Handle Docker v2 and OCI manifests
                    config_data = manifest_json.get("config", {})
                    layers_data = manifest_json.get("layers", [])
                    
                    self.manifest_data = {
                        "schema_version": schema_version,
                        "media_type": media_type,
                        "config": config_data,
                        "layers": layers_data,
                        "architecture": manifest_json.get("architecture", "unknown"),
                        "os": manifest_json.get("os", "unknown"),
                        "manifest_type": "OCI" if "oci.image" in media_type else "Docker"
                    }
                elif schema_version == 1:
                    # Handle Docker v1 manifests (legacy format)
                    history = manifest_json.get("history", [])
                    fs_layers = manifest_json.get("fsLayers", [])
                    
                    self.manifest_data = {
                        "schema_version": schema_version,
                        "media_type": media_type or "application/vnd.docker.distribution.manifest.v1+json",
                        "config": {"digest": "unknown", "size": 0},
                        "layers": [{"digest": layer.get("blobSum", "unknown"), "size": 0, "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip"} for layer in fs_layers],
                        "architecture": "unknown",
                        "os": "unknown",
                        "manifest_type": "Docker v1"
                    }
                
                # Update the manifest content display
                manifest_content = self.query_one("#manifest_content", Static)
                manifest_content.update(self._format_real_manifest())
                
                # Refresh the layers table
                self.populate_layers_table()
    
    async def fetch_local_manifest_data(self) -> None:
        """Background task to fetch manifest data from local container runtime"""
        registry_url = self.tag_info.get('registry_url', '')
        repo_name = self.tag_info.get('repository', '')
        tag_name = self.tag_info.get('tag', '')
        
        if not all([registry_url, repo_name, tag_name]):
            return
            
        # Extract runtime from registry URL
        runtime = registry_url.split('://')[1] if '://' in registry_url else 'podman'
        
        from local_container_client import LocalContainerClient
        
        client = LocalContainerClient(runtime)
        
        # Get manifest information using the local client
        manifest_result = await client.get_manifest(repo_name, tag_name)
        
        if 'error' not in manifest_result and manifest_result.get('status_code') == 200:
            manifest_data = manifest_result.get('data', {})
            
            if 'manifest' in manifest_data:
                manifest = manifest_data['manifest']
                image_data = manifest_data.get('image_data', {})
                
                # Extract layer information from manifest
                layers = manifest.get('layers', [])
                config = manifest.get('config', {})
                
                # Get architecture and OS from image config
                config_data = image_data.get('Config', {})
                architecture = image_data.get('Architecture', 'unknown')
                os = image_data.get('Os', 'unknown')
                
                self.manifest_data = {
                    "schema_version": manifest.get('schemaVersion', 2),
                    "media_type": manifest.get('mediaType', 'application/vnd.docker.distribution.manifest.v2+json'),
                    "config": config,
                    "layers": layers,
                    "architecture": architecture,
                    "os": os,
                    "manifest_type": "Local Container"
                }
                
                # Update the manifest content display
                manifest_content = self.query_one("#manifest_content", Static)
                manifest_content.update(self._format_real_manifest())
                
                # Refresh the layers table
                self.populate_layers_table()
            else:
                # Fallback to basic information if full manifest not available
                self.manifest_data = {
                    "schema_version": 2,
                    "media_type": "application/vnd.docker.distribution.manifest.v2+json",
                    "config": {"digest": self.tag_info.get('digest', 'unknown'), "size": 0},
                    "layers": [{"digest": self.tag_info.get('digest', 'unknown'), "size": 0, "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip"}],
                    "architecture": "unknown",
                    "os": "unknown", 
                    "manifest_type": "Local Container (Limited)"
                }
                
                # Update the manifest content display
                manifest_content = self.query_one("#manifest_content", Static)
                manifest_content.update(self._format_real_manifest())
                
                # Refresh the layers table
                self.populate_layers_table()
    
    def _format_real_manifest(self) -> str:
        """Format real manifest data"""
        if not self.manifest_data:
            return "Error loading manifest data"
        
        config = self.manifest_data.get("config", {})
        layers = self.manifest_data.get("layers", [])
        
        # Calculate total size
        total_size = sum(layer.get("size", 0) for layer in layers)
        if total_size > 1024 * 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024 * 1024):.1f}GB"
        elif total_size > 1024 * 1024:
            size_str = f"{total_size / (1024 * 1024):.1f}MB"
        else:
            size_str = f"{total_size / 1024:.1f}KB"
        
        manifest_type = self.manifest_data.get('manifest_type', 'Unknown')
        
        content_lines = [
            f"Manifest Type: {manifest_type} v{self.manifest_data.get('schema_version', 'Unknown')}",
            f"Media Type: {self.manifest_data.get('media_type', 'Unknown')}",
            f"Config Digest: {config.get('digest', 'Unknown')}",
            f"Architecture: {self.manifest_data.get('architecture', 'Unknown')}",
            f"OS: {self.manifest_data.get('os', 'Unknown')}",
            "",
            "Config Hash:",
            f"{config.get('digest', 'Unknown')}",
            "",
            f"Layer Count: {len(layers)}",
            f"Total Size: {size_str}",
            "Manifest Retrieved: Just now"
        ]
        return "\n".join(content_lines)
    
    def populate_layers_table(self) -> None:
        """Populate the layers table"""
        layers_table = self.query_one("#layers_table", DataTable)
        
        # Clear existing rows safely
        try:
            while layers_table.row_count > 0:
                # Get the first row key and remove it
                row_keys = list(layers_table._row_locations.keys())
                if row_keys:
                    layers_table.remove_row(row_keys[0])
                else:
                    break
        except Exception:
            # If clearing fails, just clear the entire table and re-add columns
            layers_table.clear()
            try:
                # Check if columns exist by trying to access them
                if not hasattr(layers_table, 'columns') or len(layers_table.columns) == 0:
                    layers_table.add_columns("Layer", "Media Type", "Digest", "Size")
            except:
                # If checking columns fails, just add them
                layers_table.add_columns("Layer", "Media Type", "Digest", "Size")
        
        if self.manifest_data and self.manifest_data.get("layers"):
            for i, layer in enumerate(self.manifest_data["layers"], 1):
                # Format size
                size_bytes = layer.get("size", 0)
                if size_bytes > 1024 * 1024 * 1024:
                    size = f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
                elif size_bytes > 1024 * 1024:
                    size = f"{size_bytes / (1024 * 1024):.1f}MB"
                elif size_bytes > 1024:
                    size = f"{size_bytes / 1024:.1f}KB"
                else:
                    size = f"{size_bytes}B"
                
                # Get media type and format it nicely
                media_type = layer.get("mediaType", "unknown")
                if "docker.image.rootfs.diff.tar.gzip" in media_type:
                    media_display = "gzip"
                elif "docker.image.rootfs.diff.tar" in media_type:
                    media_display = "tar"
                elif "oci.image.layer" in media_type:
                    media_display = "oci"
                else:
                    media_display = media_type.split(".")[-1] if "." in media_type else media_type
                
                # Show full digest for better visibility
                digest = layer.get("digest", "")
                
                layers_table.add_row(
                    f"Layer {i}",
                    media_display,
                    digest,
                    size
                )
        elif not self.mock_mode:
            # Only show loading if we haven't loaded data yet and not in mock mode
            layers_table.add_row("Loading...", "Fetching...", "manifest data...", "...")
    
    def action_copy_digest(self) -> None:
        """Copy the image digest to clipboard"""
        digest = self.tag_info.get('digest', 'No digest available')
        
        if digest == 'No digest available':
            self.notify("No digest available to copy", severity="warning")
            return
        
        try:
            # Try to copy to clipboard using common tools
            import subprocess
            import shutil
            
            # Check if we have clipboard tools available
            if shutil.which('xclip'):
                # Linux with xclip
                process = subprocess.run(['xclip', '-selection', 'clipboard'], 
                                       input=digest, text=True, capture_output=True)
                if process.returncode == 0:
                    self.notify(f"Digest copied to clipboard: {digest[:16]}...")
                else:
                    self.notify(f"Digest: {digest}", timeout=5)
            elif shutil.which('pbcopy'):
                # macOS
                process = subprocess.run(['pbcopy'], input=digest, text=True, capture_output=True)
                if process.returncode == 0:
                    self.notify(f"Digest copied to clipboard: {digest[:16]}...")
                else:
                    self.notify(f"Digest: {digest}", timeout=5)
            elif shutil.which('clip'):
                # Windows
                process = subprocess.run(['clip'], input=digest, text=True, capture_output=True)
                if process.returncode == 0:
                    self.notify(f"Digest copied to clipboard: {digest[:16]}...")
                else:
                    self.notify(f"Digest: {digest}", timeout=5)
            else:
                # No clipboard tool available - just show the digest
                self.notify(f"Digest (no clipboard tool): {digest}", timeout=8)
        
        except Exception:
            # Fallback - just show the digest
            self.notify(f"Digest: {digest}", timeout=8)
    
    def action_close(self) -> None:
        """Close the modal"""
        self.dismiss()
    
    def action_previous_tag(self) -> None:
        """Navigate to previous tag"""
        if len(self.all_tags) > 1 and self.current_index > 0:
            self.current_index -= 1
            self.update_tag_display()
            self.update_parent_selection()
    
    def action_next_tag(self) -> None:
        """Navigate to next tag"""
        if len(self.all_tags) > 1 and self.current_index < len(self.all_tags) - 1:
            self.current_index += 1
            self.update_tag_display()
            self.update_parent_selection()
    
    def on_key(self, event) -> None:
        """Handle key presses in modal"""
        if event.key == "enter":
            # ENTER should close the modal
            self.dismiss()
            event.stop()
            event.prevent_default()
    
    def update_parent_selection(self) -> None:
        """Update the parent screen's tag selection"""
        try:
            # Find the tags screen in the stack
            tags_screen = None
            for screen in self.app.screen_stack:
                if hasattr(screen, '__class__') and screen.__class__.__name__ == 'TagsScreen':
                    tags_screen = screen
                    break
            
            if tags_screen and hasattr(tags_screen, 'tag_data'):
                try:
                    tags_table = tags_screen.query_one("#tags_list", DataTable)
                    if tags_table and hasattr(tags_table, 'cursor_coordinate'):
                        # Ensure we don't go out of bounds and table has rows
                        max_rows = tags_table.row_count
                        if max_rows > 0 and 0 <= self.current_index < max_rows:
                            # Move cursor to the correct row
                            tags_table.move_cursor(row=self.current_index)
                            # Update the details panel
                            if hasattr(tags_screen, 'update_details_for_row'):
                                tags_screen.update_details_for_row(self.current_index)
                except Exception:
                    # Ignore errors - parent might not have the expected structure
                    pass
        except Exception:
            # Silently continue if we can't update the parent
            pass
    
    def update_tag_display(self) -> None:
        """Update the modal to show current tag"""
        if self.current_index < len(self.all_tags):
            self.tag_info = self.all_tags[self.current_index]
            self.manifest_data = None  # Reset manifest data
            
            # Update title
            self.title = f"Tag Details - {self.tag_info.get('tag', 'Unknown')} ({self.current_index + 1}/{len(self.all_tags)})"
            
            # Update tag content
            tag_content = self.query_one("#tag_content", Static)
            tag_content.update(self._format_tag_details())
            
            # Update manifest content
            manifest_content = self.query_one("#manifest_content", Static)
            manifest_content.update(self._format_manifest_details())
            
            # Clear and reload layers table - only remove rows, not columns
            # The populate_layers_table method will handle clearing rows properly
            
            # Reload manifest data for new tag
            self.load_manifest_data()
            self.populate_layers_table()
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press"""
        if event.button.id == "close_btn":
            self.dismiss()
        elif event.button.id == "copy_btn":
            self.action_copy_digest()
