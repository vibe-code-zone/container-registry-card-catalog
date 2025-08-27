"""
Registry Configuration Modal

AI Attribution (AIA): EAI Hin R Claude Code v1.0
Full: AIA Entirely AI, Human-initiated, Reviewed, Claude Code v1.0
Expanded: This work was entirely AI-generated. AI was prompted for its contributions, 
or AI assistance was enabled. AI-generated content was reviewed and approved. 
The following model(s) or application(s) were used: Claude Code.
Interpretation: https://aiattribution.github.io/interpret-attribution
More: https://aiattribution.github.io/
Vibe-Coder: Andrew Potozniak <potozniak@redhat.com>
Session Date: 2025-08-25
"""

import time
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Button, Input, Select
from textual.screen import ModalScreen
from textual.message import Message
import aiohttp


class RegistryConfigModal(ModalScreen):
    """Modal screen for configuring registry settings with live testing"""
    
    CSS = """
    RegistryConfigModal {
        align: center middle;
    }
    
    #config_container {
        width: 70%;
        height: 80%;
        border: solid $primary;
        background: $surface;
        layout: vertical;
    }
    
    #config_form {
        padding: 2;
        height: 1fr;
    }
    
    .section_title {
        height: 1;
        text-align: left;
        background: $boost;
        color: $text;
        margin: 1 0 0 0;
        padding: 0 1;
    }
    
    .form_input {
        margin: 0 0 1 0;
    }
    
    #test_status {
        height: 8;
        border: solid $accent;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
    }
    
    #button_row {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    Button {
        margin: 0 1;
    }
    
    .modal_title {
        height: 1;
        text-align: center;
        background: $primary;
        color: $text;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    """
    
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("backspace", "cancel", "Cancel"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+s", "save", "Save"),
        ("ctrl+t", "test", "Test"),
    ]
    
    class ConfigSaved(Message):
        """Message sent when configuration is saved"""
        def __init__(self, registry_config: dict) -> None:
            self.registry_config = registry_config
            super().__init__()
    
    def __init__(self, registry_data: dict, **kwargs):
        super().__init__(**kwargs)
        self.registry_data = registry_data
        self.test_client: Optional[aiohttp.ClientSession] = None
    
    def compose(self) -> ComposeResult:
        """Create the modal layout"""
        registry_name = self.registry_data.get('name', 'Unknown Registry')
        
        with Vertical(id="config_container"):
            yield Static(f"Configure Registry: {registry_name}", classes="modal_title")
            
            with ScrollableContainer(id="config_form"):
                # Registry Type section
                yield Static("🏢 Registry Type", classes="section_title")
                registry_type_select = Select([
                    ("Auto-detect", "auto"),
                    ("Docker Hub", "docker_hub"),
                    ("Quay.io", "quay"),
                    ("Harbor", "harbor"),
                    ("Google GCR", "gcr"),
                    ("Amazon ECR", "ecr"),
                    ("Azure ACR", "acr"),
                    ("Generic Registry", "generic")
                ], id="registry_type", classes="form_input")
                yield registry_type_select
                
                # Authentication section
                yield Static("🔧 Authentication", classes="section_title")
                yield Input(
                    placeholder="Username", 
                    id="username", 
                    value=self.get_current_username(),
                    classes="form_input"
                )
                yield Input(
                    placeholder="Password/Token", 
                    password=True, 
                    id="password",
                    classes="form_input"
                )
                auth_select = Select([
                    ("Token Auth (Docker v2)", "token"),
                    ("Bearer Token", "bearer"), 
                    ("Basic Auth", "basic"), 
                    ("No Authentication", "none")
                ], id="auth_type", classes="form_input")
                yield auth_select
                
                # Scope settings
                yield Static("🎯 Authorization Scope", classes="section_title")
                yield Input(
                    placeholder="Auth scope (e.g., repository:namespace/repo:pull, registry:catalog:*)", 
                    id="auth_scope", 
                    value=self.get_current_auth_scope(),
                    classes="form_input"
                )
                
                # Pagination settings
                yield Static("📄 Repository Limits", classes="section_title")
                yield Input(
                    placeholder="Max repositories to fetch (default: 100)", 
                    id="max_repos", 
                    value=str(self.get_current_max_repos()),
                    classes="form_input"
                )
                
                # Cache settings
                yield Static("🕒 Caching", classes="section_title")
                yield Input(
                    placeholder="Cache TTL (seconds, 0=no cache)", 
                    id="cache_ttl", 
                    value=str(self.get_current_cache_ttl()),
                    classes="form_input"
                )
                
                # Test status area
                yield Static("🧪 Test Results", classes="section_title")
                with ScrollableContainer(id="test_status"):
                    yield Static("Press Test to verify connection...", id="test_output")
            
            # Buttons (fixed at bottom)
            with Horizontal(id="button_row"):
                yield Button("Cancel", id="cancel")
                yield Button("Test Connection", id="test", variant="success")
                yield Button("Save", id="save", variant="primary")
    
    def on_mount(self) -> None:
        """Set initial values after widgets are mounted"""
        # Set initial auth type value
        auth_select = self.query_one("#auth_type", Select)
        auth_select.value = self.get_current_auth_type()
        
        # Set initial registry type value (saved or auto-detected)
        registry_type_select = self.query_one("#registry_type", Select)
        registry_type_select.value = self.get_current_registry_type()
    
    def get_current_username(self) -> str:
        """Get current username from registry data"""
        return self.registry_data.get('username', '')
    
    def get_current_auth_type(self) -> str:
        """Get current auth type from registry data"""
        return self.registry_data.get('auth_type', 'bearer')
    
    def get_current_cache_ttl(self) -> int:
        """Get current cache TTL from registry data"""
        return self.registry_data.get('cache_ttl', 900)  # Default 15 minutes
    
    def get_current_registry_type(self) -> str:
        """Get current registry type from registry data"""
        saved_type = self.registry_data.get('registry_type', '')
        if saved_type and saved_type != '':
            return saved_type
        return self.detect_registry_type()
    
    def get_current_auth_scope(self) -> str:
        """Get current auth scope from registry data"""
        return self.registry_data.get('auth_scope', 'registry:catalog:*')
    
    def get_current_max_repos(self) -> int:
        """Get current max repos from registry data"""
        return self.registry_data.get('max_repos', 100)
    
    def detect_registry_type(self) -> str:
        """Auto-detect registry type based on URL"""
        url = self.registry_data.get('url', '').lower()
        
        if 'docker.io' in url or 'registry-1.docker.io' in url:
            return 'docker_hub'
        elif 'quay.io' in url:
            return 'quay'
        elif 'gcr.io' in url or 'googleapis.com' in url:
            return 'gcr'
        elif 'azurecr.io' in url:
            return 'acr'
        elif '.amazonaws.com' in url or 'ecr' in url:
            return 'ecr'
        elif 'harbor' in url:
            return 'harbor'
        else:
            return 'auto'
    
    def get_registry_hints(self, registry_type: str, username: str) -> str:
        """Get registry-specific authentication hints"""
        hints = {
            'quay': {
                'username_format': 'namespace+robotname (e.g., myorg+myrobot)',
                'auth_method': 'Token Auth (Docker v2) recommended',
                'username_check': '✅ Correct format' if '+' in username else '❌ Missing + separator',
                'notes': 'Robot accounts need read permissions. Scope: repository:namespace/repo:pull or registry:catalog:*'
            },
            'docker_hub': {
                'username_format': 'Docker Hub username',
                'auth_method': 'Bearer Token recommended',
                'username_check': '✅ Standard username' if username and '+' not in username else '⚠️  Check format',
                'notes': 'Use personal access token as password'
            },
            'harbor': {
                'username_format': 'Harbor username or robot account',
                'auth_method': 'Basic Auth or Bearer Token',
                'username_check': '✅ Standard format' if username else '❌ Username required',
                'notes': 'Robot accounts: robot$projectname+robotname'
            },
            'gcr': {
                'username_format': '_token or _json_key',
                'auth_method': 'Basic Auth with OAuth token',
                'username_check': '✅ Correct format' if username in ['_token', '_json_key'] else '❌ Use _token or _json_key',
                'notes': 'Use Google OAuth token as password'
            },
            'ecr': {
                'username_format': 'AWS',
                'auth_method': 'Basic Auth with ECR token',
                'username_check': '✅ Correct format' if username == 'AWS' else '❌ Use AWS as username',
                'notes': 'Use aws ecr get-login-password output'
            }
        }
        
        if registry_type in hints:
            hint = hints[registry_type]
            return f"\n🔍 {registry_type.upper()} Registry:\n   Username: {hint['username_format']}\n   Auth: {hint['auth_method']}\n   Current: {hint['username_check']}\n   Note: {hint['notes']}"
        
        return ""
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the modal"""
        if event.button.id == "test":
            await self.test_connection()
        elif event.button.id == "save":
            await self.save_configuration()
        elif event.button.id == "cancel":
            self.action_cancel()
    
    def on_key(self, event) -> None:
        """Handle key presses in modal"""
        if event.key == "enter":
            # Enter key saves the configuration (like a form submit)
            self.run_action("save")
            event.stop()
            event.prevent_default()
        elif event.key == "ctrl+enter":
            # Ctrl+Enter tests the connection
            self.run_action("test") 
            event.stop()
            event.prevent_default()
    
    def action_save(self) -> None:
        """Action handler for save"""
        self.run_worker(self.save_configuration())
    
    def action_test(self) -> None:
        """Action handler for test"""
        self.run_worker(self.test_connection())
    
    async def test_connection(self) -> None:
        """Test the registry connection with current form values and log to debug console"""
        test_output = self.query_one("#test_output", Static)
        test_button = self.query_one("#test", Button)
        
        # Get form values
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value
        auth_type_widget = self.query_one("#auth_type", Select)
        auth_type = auth_type_widget.value
        registry_type_widget = self.query_one("#registry_type", Select)
        registry_type = registry_type_widget.value
        auth_scope = self.query_one("#auth_scope", Input).value
        
        # Get registry-specific hints
        registry_hints = self.get_registry_hints(registry_type, username)
        
        test_output.update(f"🔍 Form values:\nRegistry Type: '{registry_type}'\nAuth type: '{auth_type}'\nUsername: '{username}'\nPassword: {'***' if password else 'empty'}{registry_hints}")
        registry_url = self.registry_data.get('url', '')
        
        # Skip test for local registries
        if registry_url.startswith('local://') or registry_url.startswith('mock://'):
            test_output.update("Test skipped for local/mock registries\n\nLocal and mock registries don't require\nconnection testing.")
            test_button.variant = "success"
            test_button.label = "✅ Test Skipped"
            self.set_timer(3.0, self.reset_test_button)
            return
        
        # Log test start to debug console
        await self.log_to_debug("TEST", f"Testing registry configuration for {registry_url}", {
            "registry": registry_url,
            "registry_type": registry_type,
            "username": username,
            "auth_type": auth_type,
            "password_provided": bool(password)
        })
        
        test_button.disabled = True
        test_button.label = "Testing..."
        
        try:
            test_output.update("🔍 Testing connection...")
            results = []
            
            # Create test client
            timeout = aiohttp.ClientTimeout(total=10)
            self.test_client = aiohttp.ClientSession(timeout=timeout)
            
            # Test 1: Basic connectivity (check WWW-Authenticate header)
            test_output.update("🔍 Testing basic connectivity...")
            try:
                start_time = time.time()
                response = await self.test_client.get(f"{registry_url}/v2/")
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Check for WWW-Authenticate header to understand auth requirements
                www_auth = response.headers.get('WWW-Authenticate', 'None')
                test_output.update(f"🔍 WWW-Authenticate header: {www_auth}")
                
                # Log to debug console
                await self.log_to_debug("GET", f"{registry_url}/v2/", {
                    "status_code": response.status,
                    "duration_ms": duration_ms,
                    "test_type": "basic_connectivity"
                })
                
                if response.status == 200:
                    results.append("✅ Basic connectivity: OK")
                elif response.status == 401:
                    results.append("✅ Basic connectivity: OK (auth required)")
                else:
                    results.append(f"⚠️  Basic connectivity: HTTP {response.status}")
                    
            except Exception as e:
                # Log error to debug console
                await self.log_to_debug("GET", f"{registry_url}/v2/", {
                    "error": str(e),
                    "test_type": "basic_connectivity"
                })
                results.append(f"❌ Basic connectivity: {str(e)}")
            
            # Test 2: Authentication (if configured)
            if auth_type != "none" and (username or password):
                test_output.update("🔍 Testing authentication...")
                try:
                    headers = {}
                    
                    # Registry-specific auth header generation
                    if auth_type == "token" and username and password:
                        # Token Auth (Docker Registry v2) - will be handled by RegistryClient
                        test_output.update(f"🔍 Token Auth: Will request token from auth server...")
                        # Don't set headers here - let the client handle token flow
                        
                    elif auth_type == "basic" and username and password:
                        import base64
                        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                        headers["Authorization"] = f"Basic {credentials}"
                        test_output.update(f"🔍 Sending Basic auth header: Basic {credentials[:30]}...")
                        
                    elif auth_type == "bearer" and password:
                        if registry_type == "quay":
                            # Quay bearer tokens - try both formats
                            if username and password:
                                # Format 1: base64(username:token) 
                                import base64
                                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                                headers["Authorization"] = f"Bearer {credentials}"
                                test_output.update(f"🔍 Quay Bearer (base64): Bearer {credentials[:30]}...")
                            else:
                                # Format 2: raw token
                                headers["Authorization"] = f"Bearer {password}"
                                test_output.update(f"🔍 Quay Bearer (raw): Bearer {password[:30]}...")
                        elif registry_type == "docker_hub":
                            # Docker Hub uses raw token
                            headers["Authorization"] = f"Bearer {password}"
                            test_output.update(f"🔍 Docker Hub Bearer: Bearer {password[:30]}...")
                        else:
                            # Generic bearer token handling
                            if username and password:
                                # Some registries expect base64 encoded username:token
                                import base64
                                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                                headers["Authorization"] = f"Bearer {credentials}"
                                test_output.update(f"🔍 Generic Bearer (base64): Bearer {credentials[:30]}...")
                            else:
                                # Standard bearer token
                                headers["Authorization"] = f"Bearer {password}"
                                test_output.update(f"🔍 Generic Bearer (raw): Bearer {password[:30]}...")
                    else:
                        test_output.update(f"🔍 No auth header generated (auth_type={auth_type}, username={bool(username)}, password={bool(password)})")
                    
                    start_time = time.time()
                    
                    if auth_type == "token":
                        # Use RegistryClient for token auth flow
                        from registry_client import RegistryClient
                        async with RegistryClient(
                            base_url=registry_url,
                            username=username,
                            password=password,
                            auth_type="token"
                        ) as registry_client:
                            catalog_response_data = await registry_client.get_catalog()
                            duration_ms = int((time.time() - start_time) * 1000)
                            
                            # Convert to aiohttp-like response format for compatibility
                            class MockResponse:
                                def __init__(self, data):
                                    self.status = data["status_code"]
                                    self.headers = data.get("headers", {})
                                    self._json_data = data.get("json")
                                    self._text_data = data.get("response_content_full", "")
                                
                                async def json(self):
                                    return self._json_data
                                
                                async def text(self):
                                    return self._text_data
                            
                            catalog_response = MockResponse(catalog_response_data)
                    else:
                        # Use direct aiohttp for basic/bearer auth
                        catalog_response = await self.test_client.get(f"{registry_url}/v2/_catalog", headers=headers)
                        duration_ms = int((time.time() - start_time) * 1000)
                    
                    # Log authentication test  
                    auth_header = headers.get("Authorization", "")
                    error_response = ""
                    response_headers = {}
                    if catalog_response.status != 200:
                        try:
                            error_response = await catalog_response.text()
                            response_headers = dict(catalog_response.headers)
                        except Exception as e:
                            error_response = f"Could not read error response: {str(e)}"
                    
                    await self.log_to_debug("GET", f"{registry_url}/v2/_catalog", {
                        "status_code": catalog_response.status,
                        "duration_ms": duration_ms,
                        "test_type": "authentication",
                        "auth_type": auth_type,
                        "auth_header_sent": bool(auth_header),
                        "auth_format": auth_header[:30] + "..." if len(auth_header) > 30 else auth_header,
                        "username_provided": bool(username),
                        "password_provided": bool(password),
                        "error_response": error_response[:200] if error_response else None,
                        "full_error_response": error_response,
                        "response_headers": response_headers
                    })
                    
                    if catalog_response.status == 200:
                        data = await catalog_response.json()
                        repo_count = len(data.get('repositories', []))
                        results.append("✅ Authentication: Valid credentials")
                        results.append(f"📦 Catalog access: {repo_count} repositories found")
                        
                        # Log catalog data
                        await self.log_to_debug("DATA", "catalog_response", {
                            "repository_count": repo_count,
                            "sample_repos": data.get('repositories', [])[:5],  # First 5 repos
                            "test_type": "catalog_access"
                        })
                    elif catalog_response.status == 401:
                        results.append("❌ Authentication: Invalid credentials")
                        if error_response:
                            results.append(f"   Server Error: {error_response[:150]}")
                        # Show WWW-Authenticate header if present
                        www_auth = response_headers.get('WWW-Authenticate', '')
                        if www_auth:
                            results.append(f"   Expected Auth: {www_auth}")
                    elif catalog_response.status == 403:
                        results.append("⚠️  Authentication: Valid credentials, insufficient permissions")
                        if error_response:
                            results.append(f"   Server Error: {error_response[:150]}")
                    else:
                        results.append(f"❌ Authentication: HTTP {catalog_response.status}")
                        if error_response:
                            results.append(f"   Server Error: {error_response[:150]}")
                        www_auth = response_headers.get('WWW-Authenticate', '')
                        if www_auth:
                            results.append(f"   Expected Auth: {www_auth}")
                            
                except Exception as e:
                    await self.log_to_debug("GET", f"{registry_url}/v2/_catalog", {
                        "error": str(e),
                        "test_type": "authentication"
                    })
                    results.append(f"❌ Authentication: {str(e)}")
            else:
                results.append("Authentication: None configured")
                await self.log_to_debug("INFO", "authentication_skipped", {
                    "reason": "auth_type is none or no credentials"
                })
            
            # Test 3: Performance benchmark
            test_output.update("🔍 Testing performance...")
            try:
                # Multiple requests for average
                response_times = []
                for i in range(3):
                    start_time = time.time()
                    async with self.test_client.get(f"{registry_url}/v2/") as perf_response:
                        response_times.append(int((time.time() - start_time) * 1000))
                    
                avg_response_time = sum(response_times) // len(response_times)
                results.append(f"📊 Response time: {avg_response_time}ms avg")
                
                # Log performance data
                await self.log_to_debug("PERF", "performance_test", {
                    "response_times_ms": response_times,
                    "average_ms": avg_response_time,
                    "test_type": "performance"
                })
                
            except Exception as e:
                await self.log_to_debug("PERF", "performance_test", {
                    "error": str(e),
                    "test_type": "performance"
                })
                results.append(f"⚠️  Performance test failed: {str(e)}")
            
            # Display all results
            final_output = "\n".join(results)
            test_output.update(final_output)
            
            # Force a refresh of the display
            self.refresh()
            
            success = any("✅" in result for result in results)
            
            # Log test completion
            await self.log_to_debug("TEST", f"Configuration test completed for {registry_url}", {
                "success": success,
                "total_checks": len(results),
                "registry": registry_url,
                "test_summary": results
            })
            
            if success:
                test_button.variant = "success"
                test_button.label = "✅ Test Passed"
            else:
                test_button.variant = "error" 
                test_button.label = "❌ Test Failed"
                
        except Exception as e:
            error_msg = f"❌ Test failed: {str(e)}"
            test_output.update(error_msg)
            
            # Log critical test failure
            await self.log_to_debug("ERROR", "test_connection_failed", {
                "error": str(e),
                "registry": registry_url,
                "critical": True
            })
            
            test_button.variant = "error"
            test_button.label = "❌ Test Failed"
        finally:
            if self.test_client:
                await self.test_client.close()
                self.test_client = None
            test_button.disabled = False
            self.set_timer(3.0, self.reset_test_button)
    
    async def log_to_debug(self, method: str, url: str, details: dict) -> None:
        """Log test operation to debug console"""
        try:
            # Add to global registry manager for debug console
            from registry_client import registry_manager
            
            log_entry = {
                "method": method,
                "url": url,
                "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "status_code": details.get("status_code", 0),
                "duration_ms": details.get("duration_ms", 0),
                "size_bytes": 0,
                "content_preview": f"TEST: {str(details)[:200]}",
                "response_content_full": f"TEST OPERATION: {str(details)}",
                "error": details.get("error"),
                "test_operation": True
            }
            
            registry_manager.add_api_call(log_entry)
            
        except Exception as e:
            # Add a simple notification if debug fails
            try:
                self.app.notify(f"Debug log failed: {str(e)}", severity="warning")
            except:
                pass
    
    def reset_test_button(self) -> None:
        """Reset test button to original state"""
        try:
            test_button = self.query_one("#test", Button)
            test_button.variant = "success"
            test_button.label = "Test Connection"
        except Exception:
            pass
    
    async def save_configuration(self) -> None:
        """Save the configuration and close modal"""
        # Get form values
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value
        auth_type = self.query_one("#auth_type", Select).value
        registry_type = self.query_one("#registry_type", Select).value
        auth_scope = self.query_one("#auth_scope", Input).value or "registry:catalog:*"
        try:
            max_repos = int(self.query_one("#max_repos", Input).value or "100")
        except ValueError:
            max_repos = 100  # Default fallback
        try:
            cache_ttl = int(self.query_one("#cache_ttl", Input).value or "900")
        except ValueError:
            cache_ttl = 900  # Default fallback
        
        # Create configuration dict
        config = {
            "registry_url": self.registry_data.get('url', ''),
            "registry_name": self.registry_data.get('name', ''),
            "username": username,
            "password": password,
            "auth_type": auth_type,
            "registry_type": registry_type,
            "auth_scope": auth_scope,
            "max_repos": max_repos,
            "cache_ttl": cache_ttl,
        }
        
        # Log configuration save
        await self.log_to_debug("CONFIG", f"Saving configuration for {config['registry_name']}", {
            "registry": config['registry_url'],
            "registry_type": registry_type,
            "username": username,
            "auth_type": auth_type,
            "cache_ttl": cache_ttl,
            "password_provided": bool(password)
        })
        
        # Send message to parent with configuration
        self.post_message(self.ConfigSaved(config))
        self.dismiss()
    
    def action_cancel(self) -> None:
        """Cancel and close the modal"""
        self.dismiss()
    
    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()