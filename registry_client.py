"""
Real HTTP Registry Client

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

import asyncio
import time
import base64
from typing import Dict, List, Any, Optional
import httpx
from urllib.parse import urljoin


def sort_tags_by_timestamp(tags_list, manifest_metadata=None):
    """Sort tags by timestamp (newest first) using manifest metadata if available"""
    if not manifest_metadata:
        # Fallback to alphabetical sorting
        return sorted(tags_list, key=str.lower)
    
    # Build tag-to-timestamp mapping
    tag_timestamps = {}
    for manifest_sha, manifest_data in manifest_metadata.items():
        tags_for_manifest = manifest_data.get("tag", [])
        time_uploaded = manifest_data.get("timeUploadedMs", "0")
        time_created = manifest_data.get("timeCreatedMs", "0")
        
        # Use upload time if available, otherwise creation time
        timestamp = int(time_uploaded) if time_uploaded != "0" else int(time_created)
        
        for tag in tags_for_manifest:
            tag_timestamps[tag] = timestamp
    
    # Sort by timestamp (newest first), then alphabetically
    def tag_sort_key(tag_name):
        timestamp = tag_timestamps.get(tag_name, 0)
        return (-timestamp, tag_name.lower())
    
    return sorted(tags_list, key=tag_sort_key)


class RegistryClient:
    """HTTP client for Docker Registry API v2 with authentication support"""
    
    def __init__(self, base_url: str, timeout: int = 30, username: str = None, password: str = None, auth_type: str = "bearer", auth_scope: str = "registry:catalog:*", tui_debug_logger=None):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = None
        self.username = username
        self.password = password
        self.auth_type = auth_type  # "bearer", "basic", or "none"
        self.auth_scope = auth_scope  # Default scope for token requests
        self.tui_debug_logger = tui_debug_logger  # For file-based auth/cache debug logging
        # Token authentication cache
        self.cached_token = None
        self.token_expires_at = None
        self.token_scope = None
        self.auth_service = None
        self.auth_realm = None
    
    def _filter_response_headers(self, headers: dict) -> dict:
        """Filter response headers to exclude potentially sensitive information
        
        Excludes: Set-Cookie, Authorization, custom X- headers with auth/token/key/secret
        Includes: Content headers, Link (pagination), Docker headers, rate limiting, WWW-Authenticate
        """
        # Safe headers to include in debug logs
        safe_headers = {
            'content-type', 'content-length', 'content-encoding',
            'date', 'cache-control', 'expires', 'last-modified',
            'link', 'location',  # Important for pagination
            'docker-content-digest', 'docker-distribution-api-version',
            'x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-reset',  # Rate limiting info
            'www-authenticate',  # Auth challenge info (public by design)
            'access-control-allow-origin', 'access-control-allow-methods',  # CORS
            'strict-transport-security', 'x-content-type-options',  # Security headers (safe to log)
        }
        
        # Filter headers case-insensitively
        filtered = {}
        sensitive_headers_found = []
        
        for key, value in headers.items():
            if key.lower() in safe_headers:
                filtered[key] = value
            elif key.lower().startswith('x-') and not any(sensitive in key.lower() for sensitive in ['auth', 'token', 'key', 'secret']):
                # Include custom headers unless they look auth-related
                filtered[key] = value
            else:
                # Track filtered headers for debugging
                sensitive_headers_found.append(key.lower())
        
        # Log if we filtered any headers (for debugging the filtering itself)
        if sensitive_headers_found and self.tui_debug_logger:
            self.tui_debug_logger.debug("Response headers filtered for security", 
                                      filtered_headers=sensitive_headers_found,
                                      total_headers=len(headers),
                                      safe_headers_included=len(filtered))
        
        return filtered
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = httpx.AsyncClient(
            timeout=self.timeout,
            verify=False,  # TODO: Make SSL verification configurable
            follow_redirects=True,
            headers={
                "User-Agent": "Container-Card-Catalog/0.1.0 (https://github.com/anthropics/claude-code)"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.aclose()
    
    def _get_basic_auth_header(self) -> Dict[str, str]:
        """Generate basic auth header"""
        if not self.username or not self.password:
            return {}
        
        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {credentials}"}
    
    def _get_bearer_auth_header(self) -> Dict[str, str]:
        """Generate bearer auth header"""
        if self.auth_type == "bearer" and self.password:
            # Try different bearer token formats
            if self.username and self.password:
                # Some registries expect base64 encoded username:token
                credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                return {"Authorization": f"Bearer {credentials}"}
            else:
                # Standard bearer token (could be base64 encoded already)
                return {"Authorization": f"Bearer {self.password}"}
        return {}
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get appropriate authentication headers"""
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("Getting auth headers", 
                                      auth_type=self.auth_type,
                                      has_username=bool(self.username),
                                      has_cached_token=bool(self.cached_token))
        
        if self.auth_type == "basic":
            return self._get_basic_auth_header()
        elif self.auth_type == "bearer":
            return self._get_bearer_auth_header()
        elif self.auth_type == "token" and self.cached_token:
            # Check if token is expired
            if self.token_expires_at and time.time() >= self.token_expires_at:
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Token expired - cache miss", 
                                              token_age_seconds=int(time.time() - (self.token_expires_at - 300)))
                self.cached_token = None  # Clear expired token
                return {}
            
            # Token is valid, log cache hit
            if self.tui_debug_logger:
                time_until_expiry = self.token_expires_at - time.time() if self.token_expires_at else None
                self.tui_debug_logger.debug("Token cache hit", 
                                          expires_in_seconds=int(time_until_expiry) if time_until_expiry else "unknown",
                                          token_scope=self.token_scope)
            return {"Authorization": f"Bearer {self.cached_token}"}
        return {}  # No auth
    
    async def _parse_www_authenticate(self, www_auth_header: str) -> Dict[str, str]:
        """Parse WWW-Authenticate header to extract realm, service, scope"""
        auth_params = {}
        
        # Log raw WWW-Authenticate header for debugging
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("WWW-Authenticate header discovered", 
                                      header=www_auth_header)
        
        if 'Bearer' in www_auth_header:
            # Extract parameters from: Bearer realm="...",service="...",scope="..."
            import re
            pattern = r'(\w+)="([^"]*)"'
            matches = re.findall(pattern, www_auth_header)
            auth_params = dict(matches)
            
            # Log parsed parameters (realm is safe to log)
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("WWW-Authenticate parsed", 
                                          realm=auth_params.get('realm', 'not_found'),
                                          service=auth_params.get('service', 'not_found'),
                                          scope_provided='scope' in auth_params)
        
        return auth_params
    
    async def _get_registry_token(self, scope: str = None) -> Optional[str]:
        """Get authentication token from registry auth service"""
        if not self.username or not self.password:
            return None
        
        # Use provided scope or default to configured scope
        if scope is None:
            scope = self.auth_scope
            
        # First, try to get auth challenge if we don't have realm/service
        if not self.auth_realm or not self.auth_service:
            try:
                response = await self.session.get(f"{self.base_url}/v2/")
                if response.status_code == 401:
                    www_auth = response.headers.get('WWW-Authenticate', '')
                    if www_auth:
                        auth_params = await self._parse_www_authenticate(www_auth)
                        self.auth_realm = auth_params.get('realm')
                        self.auth_service = auth_params.get('service')
                        if 'scope' in auth_params:
                            scope = auth_params['scope']
            except Exception:
                return None
        
        if not self.auth_realm:
            return None
            
        try:
            # Request token from auth service
            token_url = self.auth_realm
            auth_data = {
                'service': self.auth_service or 'registry',
                'scope': scope
            }
            
            # Use basic auth for token request
            basic_credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers = {"Authorization": f"Basic {basic_credentials}"}
            
            # Debug token request
            if self.tui_debug_logger:
                safe_auth_data = {k: v for k, v in auth_data.items() if k != 'password'}
                self.tui_debug_logger.debug("Token request initiated", 
                                          token_url=token_url,
                                          auth_data=safe_auth_data,
                                          has_basic_auth=bool(self.username))
            
            response = await self.session.post(
                token_url, 
                data=auth_data,
                headers=headers
            )
            
            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get('token') or token_data.get('access_token')
                if token:
                    self.cached_token = token
                    self.token_scope = scope
                    
                    # Handle token expiration
                    import time
                    from datetime import datetime, timedelta
                    
                    expires_in = token_data.get('expires_in')  # seconds from now
                    issued_at = token_data.get('issued_at')    # ISO timestamp
                    
                    if expires_in:
                        # Token expires in X seconds from now
                        self.token_expires_at = time.time() + int(expires_in)
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Token expiration set", 
                                                      expires_in_seconds=expires_in)
                    elif issued_at:
                        # Parse issued_at and assume default expiration (usually 5-60 minutes)
                        # Default to 5 minutes if no expires_in provided
                        self.token_expires_at = time.time() + 300  # 5 minutes
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Token expiration assumed", 
                                                      issued_at=issued_at, 
                                                      assumed_expires_seconds=300)
                    else:
                        # No expiration info - assume short lived (5 minutes)
                        self.token_expires_at = time.time() + 300
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Token expiration defaulted", 
                                                      default_expires_seconds=300)
                    
                    return token
                    
        except Exception as e:
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Token request failed", 
                                          error=str(e))
            
        return None
    
    
    async def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make HTTP request and return response data"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        start_time = time.time()
        
        # Get authentication headers if configured
        auth_headers = self._get_auth_headers()
        
        try:
            response = await self.session.get(url, headers=auth_headers)
            
            # If we get 401 and have credentials, try token auth
            if response.status_code == 401:
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Received 401 Unauthorized", 
                                              has_username=bool(self.username),
                                              has_password=bool(self.password),
                                              auth_type=self.auth_type)
                
                if self.username and self.password and self.auth_type != "basic":
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("Attempting token authentication")
                    
                    # Try to get a token
                    token = await self._get_registry_token()
                    if token:
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Token acquired, retrying request")
                        auth_headers = {"Authorization": f"Bearer {token}"}
                        response = await self.session.get(url, headers=auth_headers)
                    else:
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Token acquisition failed")
                else:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("No credentials for token auth - continuing with 401")
            
            duration = int((time.time() - start_time) * 1000)  # ms
            
            
            # Prepare response data
            response_data = {
                "url": url,
                "method": response.request.method,
                "status_code": response.status_code,
                "duration_ms": duration,
                "size_bytes": len(response.content),
                "headers": self._filter_response_headers(dict(response.headers)),
                "content_preview": response.text[:500] if response.text else "",
                "response_content_full": response.text if response.text else "",
                "timestamp": time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}"
            }
            
            # Add JSON data if available
            if response.status_code == 200:
                try:
                    response_data["json"] = response.json()
                except Exception:
                    response_data["json"] = None
            
            return response_data
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            
            # Provide more detailed error information for debugging
            error_details = f"Error: {str(e)}"
            if "gcr.io" in url or "googleapis.com" in url:
                error_details += " (Note: Google registries require authentication)"
            elif "certificate" in str(e).lower() or "ssl" in str(e).lower():
                error_details += " (TLS/SSL certificate issue)"
            elif "permission" in str(e).lower() or "unauthorized" in str(e).lower():
                error_details += " (Authentication required)"
            
            return {
                "url": url,
                "method": "GET",  # Known method for error case
                "status_code": 0,
                "duration_ms": duration,
                "size_bytes": 0,
                "headers": {},
                "content_preview": error_details,
                "response_content_full": error_details,
                "timestamp": time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}",
                "error": str(e)
            }
    
    async def check_api_version(self) -> Dict[str, Any]:
        """Check registry API version (GET /v2/)"""
        return await self._make_request('/v2/')
    
    async def get_catalog(self, n: int = None, last: str = None, next_page: str = None) -> Dict[str, Any]:
        """Get repository catalog (GET /v2/_catalog) with pagination support"""
        endpoint = '/v2/_catalog'
        params = []
        if n:
            params.append(f'n={n}')
        if last:
            params.append(f'last={last}')
        if next_page:
            params.append(f'next_page={next_page}')
        if params:
            endpoint += '?' + '&'.join(params)
        return await self._make_request(endpoint)
    
    async def get_tags(self, repository: str) -> Dict[str, Any]:
        """Get tags for repository (GET /v2/{name}/tags/list)"""
        return await self._make_request(f'/v2/{repository}/tags/list')
    
    async def get_manifest(self, repository: str, tag: str) -> Dict[str, Any]:
        """Get manifest for specific tag (GET /v2/{name}/manifests/{tag})"""
        url = urljoin(self.base_url + '/', f'/v2/{repository}/manifests/{tag}')
        start_time = time.time()
        
        try:
            # Accept multiple manifest formats + auth headers
            headers = {
                "Accept": ", ".join([
                    "application/vnd.docker.distribution.manifest.v2+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json", 
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.v1+json"
                ])
            }
            # Add auth headers if configured
            headers.update(self._get_auth_headers())
            
            response = await self.session.get(url, headers=headers)
            duration = int((time.time() - start_time) * 1000)
            
            response_data = {
                "url": url,
                "method": response.request.method,
                "status_code": response.status_code,
                "duration_ms": duration,
                "size_bytes": len(response.content),
                "headers": self._filter_response_headers(dict(response.headers)),
                "content_preview": response.text[:500] if response.text else "",
                "timestamp": time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}"
            }
            
            if response.status_code == 200:
                try:
                    response_data["json"] = response.json()
                except Exception:
                    response_data["json"] = None
            
            return response_data
            
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            
            # Provide more detailed error information for debugging
            error_details = f"Error: {str(e)}"
            if "gcr.io" in url or "googleapis.com" in url:
                error_details += " (Note: Google registries require authentication)"
            elif "certificate" in str(e).lower() or "ssl" in str(e).lower():
                error_details += " (TLS/SSL certificate issue)"
            elif "permission" in str(e).lower() or "unauthorized" in str(e).lower():
                error_details += " (Authentication required)"
            
            return {
                "url": url,
                "method": "GET",  # Known method for error case
                "status_code": 0,
                "duration_ms": duration,
                "size_bytes": 0,
                "headers": {},
                "content_preview": error_details,
                "response_content_full": error_details,
                "timestamp": time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}",
                "error": str(e)
            }


class RegistryManager:
    """Manages multiple registry clients"""
    
    def __init__(self):
        self.api_call_log = []  # For debug console
        self.tui_debug_logger = None  # For file-based debug logging
    
    def set_tui_debug_logger(self, debug_logger):
        """Set the TUI debug logger for file-based auth/cache logging"""
        self.tui_debug_logger = debug_logger
    
    def _parse_link_header(self, link_header: str) -> Dict[str, str]:
        """Parse Link header to extract pagination URLs"""
        import re
        links = {}
        
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("Parsing Link header", 
                                      raw_link_header=link_header)
        
        if link_header:
            # Parse: <url>; rel="next", <url2>; rel="prev"
            pattern = r'<([^>]+)>;\s*rel="([^"]+)"'
            matches = re.findall(pattern, link_header)
            
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Link header regex matches", 
                                          pattern=pattern,
                                          matches=matches,
                                          match_count=len(matches))
            
            for url, rel in matches:
                links[rel] = url
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Link header parsed relation", 
                                              relation=rel,
                                              url=url)
        
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("Link header parsing complete", 
                                      parsed_links=links,
                                      has_next=("next" in links))
        
        return links
    
    def _extract_next_page_token(self, next_url: str) -> str:
        """Extract next_page token from URL"""
        import urllib.parse
        
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("Extracting next page token", 
                                      next_url=next_url)
        
        parsed = urllib.parse.urlparse(next_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("URL parsing results", 
                                      parsed_query=parsed.query,
                                      all_params=params,
                                      has_next_page_param=('next_page' in params))
        
        token = params.get('next_page', [''])[0]
        
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("Next page token extracted", 
                                      token=token[:50] + "..." if token and len(token) > 50 else token,
                                      token_length=len(token) if token else 0)
        
        return token
        
    def add_api_call(self, call_data: Dict[str, Any]):
        """Add API call to debug log"""
        self.api_call_log.append(call_data)
        # Keep only last 100 calls
        if len(self.api_call_log) > 100:
            self.api_call_log = self.api_call_log[-100:]
    
    async def check_registry_status(self, registry_url: str, registry_config: Dict[str, str] = None) -> Dict[str, Any]:
        """Check if registry is accessible and get basic info"""
        # Use registry config if provided
        client_kwargs = {'base_url': registry_url, 'tui_debug_logger': self.tui_debug_logger}
        if registry_config:
            client_kwargs.update({
                'username': registry_config.get('username'),
                'password': registry_config.get('password'),
                'auth_type': registry_config.get('auth_type', 'none')
            })
        
        async with RegistryClient(**client_kwargs) as client:
            version_response = await client.check_api_version()
            self.add_api_call(version_response)
            
            # Always try catalog regardless of version response
            catalog_response = await client.get_catalog()
            self.add_api_call(catalog_response)
            
            # Test monitored repositories if configured
            monitored_repo_accessible = False
            monitored_repos = registry_config.get('monitored_repos', []) if registry_config else []
            
            if monitored_repos and self.tui_debug_logger:
                self.tui_debug_logger.debug("Testing monitored repository access for status check", 
                                          monitored_repos_count=len(monitored_repos),
                                          registry_url=registry_url)
            
            if monitored_repos:
                # Test the first monitored repo to see if we have working auth
                test_repo = monitored_repos[0]
                try:
                    test_response = await client.get_tags(test_repo)
                    self.add_api_call(test_response)
                    
                    if test_response["status_code"] == 200:
                        monitored_repo_accessible = True
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Monitored repository access test succeeded", 
                                                      test_repo=test_repo,
                                                      status_code=test_response["status_code"])
                    elif self.tui_debug_logger:
                        self.tui_debug_logger.debug("Monitored repository access test failed", 
                                                  test_repo=test_repo,
                                                  status_code=test_response["status_code"])
                except Exception as e:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("Monitored repository access test exception", 
                                                  test_repo=test_repo,
                                                  error=str(e))
            
            # Determine repo count
            repo_count = "Unknown"
            if catalog_response["status_code"] == 200 and catalog_response.get("json"):
                repos = catalog_response["json"].get("repositories", [])
                catalog_count = len(repos)
                
                # If we also have monitored repos, show total count with monitored in parentheses
                if monitored_repos and len(monitored_repos) > 0:
                    # Count monitored repos that are NOT in catalog (avoid double-counting)
                    monitored_not_in_catalog = [repo for repo in monitored_repos if repo not in repos]
                    total_count = catalog_count + len(monitored_not_in_catalog)
                    repo_count = f"{total_count}({len(monitored_repos)})"
                else:
                    repo_count = str(catalog_count)
            elif monitored_repo_accessible:
                repo_count = f"{len(monitored_repos)}({len(monitored_repos)})"
            
            # Determine overall status based on endpoints, auth config, and monitored repo access
            has_auth = registry_config and (registry_config.get('username') or registry_config.get('password'))
            
            if version_response["status_code"] == 200 and catalog_response["status_code"] == 200:
                # Full access - both version and catalog work
                status = "✅"
                api_version = "v2"
                connection_status = "Connected"
            elif catalog_response["status_code"] == 200:
                # Partial access - catalog works but version endpoint needs auth
                status = "🟡"
                api_version = "v2"
                connection_status = "Partial (auth needed)"
            elif version_response["status_code"] == 200:
                # Version works but catalog restricted - still partial access
                status = "🟡"
                api_version = "v2"
                connection_status = "Partial (catalog restricted)"
            elif monitored_repo_accessible:
                # Monitored repository access works - this is the key test for auth
                status = "🟡"
                api_version = "v2 (auth)"
                connection_status = "Monitored repos accessible"
            elif has_auth and (version_response["status_code"] == 401 or catalog_response["status_code"] == 401):
                # 401s but we have auth configured - potential access
                status = "🟡"
                api_version = "v2 (auth)"
                connection_status = "Auth configured"
            else:
                # No access - endpoints fail and no auth configured
                status = "❌"
                api_version = "Unknown"
                connection_status = f"Error {version_response['status_code']}"
            
            return {
                "status": status,
                "api_version": api_version,
                "repo_count": repo_count,
                "response_time": f"{version_response['duration_ms']}ms",
                "connection_status": connection_status
            }
    
    async def get_repositories(self, registry_url: str, limit: int = 50, registry_config: Dict[str, str] = None, offset: int = 0) -> Dict[str, Any]:
        """Get repositories for a registry"""
        # Use registry config if provided
        client_kwargs = {'base_url': registry_url, 'tui_debug_logger': self.tui_debug_logger}
        if registry_config:
            client_kwargs.update({
                'username': registry_config.get('username'),
                'password': registry_config.get('password'),
                'auth_type': registry_config.get('auth_type', 'none'),
                'auth_scope': registry_config.get('auth_scope', 'registry:catalog:*')
            })
        
        async with RegistryClient(**client_kwargs) as client:
            # First, fetch monitored repositories if configured
            monitored_repos = registry_config.get('monitored_repos', []) if registry_config else []
            monitored_repo_data = []
            failed_monitored_repos = []
            
            if monitored_repos:
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Fetching monitored repositories first", 
                                              monitored_count=len(monitored_repos),
                                              monitored_repos=monitored_repos)
                
                for repo_name in monitored_repos:
                    try:
                        # Always load full tag info for monitored repos
                        tags_response = await client.get_tags(repo_name)
                        self.add_api_call(tags_response)
                        
                        if tags_response["status_code"] == 200:
                            response_json = tags_response.get("json", {})
                            all_tags = response_json.get("tags", [])
                            manifest_metadata = response_json.get("manifest", {})
                            tag_count = len(all_tags)
                            
                            # Get recent tags using timestamp-based sorting
                            sorted_tags = sort_tags_by_timestamp(all_tags, manifest_metadata)
                            recent_tags = sorted_tags[:3]  # Take first 3 (newest)
                            recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
                            
                            monitored_repo_data.append({
                                "name": repo_name,
                                "tag_count": tag_count,
                                "recent_tags": recent_tags,
                                "recent_tags_display": recent_tags_display,
                                "last_updated": "Unknown",
                                "is_monitored": True  # Mark as monitored for display
                            })
                            
                            if self.tui_debug_logger:
                                self.tui_debug_logger.debug("Monitored repo fetched successfully", 
                                                          repo=repo_name,
                                                          tag_count=tag_count)
                        else:
                            # Failed to fetch monitored repo
                            failed_monitored_repos.append({
                                "name": repo_name,
                                "error": f"Status {tags_response['status_code']}"
                            })
                            
                            if self.tui_debug_logger:
                                self.tui_debug_logger.debug("Monitored repo fetch failed", 
                                                          repo=repo_name,
                                                          status_code=tags_response['status_code'])
                    except Exception as e:
                        failed_monitored_repos.append({
                            "name": repo_name,
                            "error": str(e)
                        })
                        
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Monitored repo fetch exception", 
                                                      repo=repo_name,
                                                      error=str(e))
            
            # Now handle regular catalog pagination
            all_repositories = []
            next_page_token = None
            page_size = min(100, limit + offset)  # Get enough to cover offset + limit
            page_count = 0
            
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Starting catalog pagination", 
                                          target_total=offset + limit,
                                          page_size=page_size,
                                          has_next_page_token=bool(next_page_token))
            
            # Fetch pages until we have enough repositories (offset + limit)
            while len(all_repositories) < (offset + limit):
                page_count += 1
                
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Fetching catalog page", 
                                              page_number=page_count,
                                              current_total=len(all_repositories),
                                              target_total=offset + limit,
                                              next_page_token=next_page_token[:50] + "..." if next_page_token and len(next_page_token) > 50 else next_page_token)
                
                catalog_response = await client.get_catalog(n=page_size, next_page=next_page_token)
                self.add_api_call(catalog_response)
                
                if catalog_response["status_code"] != 200:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("Catalog request failed", 
                                                  status_code=catalog_response["status_code"],
                                                  page_number=page_count)
                    break
                
                page_repos = catalog_response.get("json", {}).get("repositories", [])
                if not page_repos:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("No repositories in page - pagination complete", 
                                                  page_number=page_count)
                    break  # No more repositories
                
                all_repositories.extend(page_repos)
                
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Page fetched successfully", 
                                              page_number=page_count,
                                              repos_in_page=len(page_repos),
                                              total_repos=len(all_repositories))
                
                # Check for Link header pagination (try different cases)
                response_headers = catalog_response.get("headers", {})
                link_header = (response_headers.get("Link") or 
                             response_headers.get("link") or 
                             response_headers.get("LINK") or "")
                if link_header:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("Link header found", 
                                                  link_header=link_header)
                    
                    links = self._parse_link_header(link_header)
                    if "next" in links:
                        next_page_token = self._extract_next_page_token(links["next"])
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("Found next page token", 
                                                      next_page_token=next_page_token[:50] + "..." if next_page_token and len(next_page_token) > 50 else next_page_token)
                    else:
                        if self.tui_debug_logger:
                            self.tui_debug_logger.debug("No next page in Link header - pagination complete")
                        break  # No more pages
                else:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("No Link header found - pagination complete", 
                                                  page_number=page_count)
                    break  # No Link header
                
                # Stop if this page was smaller than requested (no more data)
                if len(page_repos) < page_size:
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("Page smaller than requested - no more data", 
                                                  page_repos=len(page_repos),
                                                  page_size=page_size,
                                                  page_number=page_count)
                    break
            
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Catalog pagination completed", 
                                          total_pages=page_count,
                                          total_repositories=len(all_repositories),
                                          requested_offset=offset,
                                          requested_limit=limit)
            
            # Apply offset and limit
            repositories = all_repositories[offset:offset + limit]
            
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Applying offset and limit", 
                                          total_available=len(all_repositories),
                                          offset=offset,
                                          limit=limit,
                                          final_count=len(repositories))
            repo_data = []
            
            # Get basic repo info first, load tags for small lists or local registries
            load_tags = len(repositories) <= 50  # Only load tags if 50 or fewer repos
            
            for repo_name in repositories[:limit]:
                if load_tags:
                    # Load tags for small repository lists
                    tags_response = await client.get_tags(repo_name)
                    self.add_api_call(tags_response)
                    
                    if tags_response["status_code"] == 200:
                        response_json = tags_response.get("json", {})
                        all_tags = response_json.get("tags", [])
                        manifest_metadata = response_json.get("manifest", {})
                        tag_count = len(all_tags)
                        
                        # Get recent tags using timestamp-based sorting
                        sorted_tags = sort_tags_by_timestamp(all_tags, manifest_metadata)
                        recent_tags = sorted_tags[:3]  # Take first 3 (newest)
                        recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
                    else:
                        tag_count = 0
                        recent_tags = []
                        recent_tags_display = "Error loading tags"
                else:
                    # Skip tag loading for large lists
                    tag_count = "Many"
                    recent_tags = []
                    recent_tags_display = "Too many repos - tags not loaded"
                
                repo_data.append({
                    "name": repo_name,
                    "tag_count": tag_count,
                    "recent_tags": recent_tags,
                    "recent_tags_display": recent_tags_display,
                    "last_updated": "Unknown"
                })
            
            # Filter out monitored repos from catalog to avoid duplicates
            monitored_repo_names = {repo['name'] for repo in monitored_repo_data}
            catalog_repo_data = [repo for repo in repo_data if repo['name'] not in monitored_repo_names]
            
            # Add failed monitored repos as error entries (always show them)
            for failed_repo in failed_monitored_repos:
                monitored_repo_data.append({
                    "name": failed_repo["name"],
                    "tag_count": "Error",
                    "recent_tags": [],
                    "recent_tags_display": f"❌ {failed_repo['error']}",
                    "last_updated": "Error",
                    "is_monitored": True,
                    "is_error": True
                })
            
            # Sort monitored repos alphabetically (will be handled by UI for direction)
            monitored_repo_data.sort(key=lambda x: x['name'].lower())
            
            # Sort catalog repos alphabetically
            catalog_repo_data.sort(key=lambda x: x['name'].lower())
            
            # Combine: monitored repos always at top, then catalog repos
            final_repo_data = monitored_repo_data + catalog_repo_data
            
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Final repository data assembled", 
                                          total_repos=len(final_repo_data),
                                          monitored_repos=len(monitored_repo_data),
                                          catalog_repos=len(catalog_repo_data),
                                          failed_monitored=len(failed_monitored_repos),
                                          monitored_names=[repo['name'] for repo in monitored_repo_data],
                                          first_few_repo_types=[f"{repo['name']}:{'⭐' if repo.get('is_monitored') else '📦'}" for repo in final_repo_data[:5]])
            
            # Return repository data with pagination metadata
            return {
                "repositories": final_repo_data,
                "pagination": {
                    "method": "link_header" if next_page_token else "complete",
                    "next_page_token": next_page_token,
                    "total_loaded": len(all_repositories),
                    "page_count": page_count,
                    "has_more": bool(next_page_token),
                    "final_offset": offset,
                    "final_limit": limit
                },
                "monitored_repos_status": {
                    "total_monitored": len(monitored_repos),
                    "successful": len(monitored_repo_data) - len(failed_monitored_repos),
                    "failed": failed_monitored_repos
                }
            }
    
    async def continue_repositories_pagination(self, registry_url: str, next_page_token: str, registry_config: Dict[str, str] = None, page_size: int = 100) -> Dict[str, Any]:
        """Continue repository pagination using next_page token from Link headers"""
        if self.tui_debug_logger:
            self.tui_debug_logger.debug("Continuing pagination with next_page token", 
                                      registry_url=registry_url,
                                      page_size=page_size,
                                      token_length=len(next_page_token) if next_page_token else 0,
                                      method="LINK_HEADER_CONTINUATION")
        
        # Use registry config if provided
        client_kwargs = {'base_url': registry_url, 'tui_debug_logger': self.tui_debug_logger}
        if registry_config:
            client_kwargs.update({
                'username': registry_config.get('username'),
                'password': registry_config.get('password'),
                'auth_type': registry_config.get('auth_type', 'none'),
                'auth_scope': registry_config.get('auth_scope', 'registry:catalog:*')
            })
        
        async with RegistryClient(**client_kwargs) as client:
            # Make single page request with next_page token
            catalog_response = await client.get_catalog(n=page_size, next_page=next_page_token)
            self.add_api_call(catalog_response)
            
            if catalog_response["status_code"] != 200:
                error_msg = f"Status {catalog_response['status_code']}"
                if catalog_response["status_code"] == 400:
                    error_msg += " - Token may have expired"
                elif catalog_response["status_code"] == 401:
                    error_msg += " - Authentication failed, token may be expired"
                
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Pagination continuation failed", 
                                              status_code=catalog_response["status_code"],
                                              error_analysis=error_msg,
                                              token_expiration_likely=(catalog_response["status_code"] in [400, 401]))
                return {
                    "repositories": [],
                    "pagination": {
                        "method": "failed",
                        "next_page_token": None,
                        "has_more": False,
                        "error": error_msg,
                        "token_expired": catalog_response["status_code"] in [400, 401]
                    }
                }
            
            page_repos = catalog_response.get("json", {}).get("repositories", [])
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Pagination page fetched", 
                                          repos_in_page=len(page_repos))
            
            # Check for next Link header
            response_headers = catalog_response.get("headers", {})
            link_header = (response_headers.get("Link") or 
                         response_headers.get("link") or 
                         response_headers.get("LINK") or "")
            
            new_next_page_token = None
            if link_header:
                if self.tui_debug_logger:
                    self.tui_debug_logger.debug("Link header found in continuation", 
                                              link_header=link_header)
                
                links = self._parse_link_header(link_header)
                if "next" in links:
                    new_next_page_token = self._extract_next_page_token(links["next"])
                    if self.tui_debug_logger:
                        self.tui_debug_logger.debug("Found next continuation token", 
                                                  token_length=len(new_next_page_token) if new_next_page_token else 0)
            
            # Process repositories with tag data
            repo_data = []
            load_tags = len(page_repos) <= 50  # Only load tags if 50 or fewer repos
            
            for repo_name in page_repos:
                if load_tags:
                    # Load tags for small repository lists
                    tags_response = await client.get_tags(repo_name)
                    self.add_api_call(tags_response)
                    
                    if tags_response["status_code"] == 200:
                        response_json = tags_response.get("json", {})
                        all_tags = response_json.get("tags", [])
                        manifest_metadata = response_json.get("manifest", {})
                        tag_count = len(all_tags)
                        
                        # Get recent tags using timestamp-based sorting
                        sorted_tags = sort_tags_by_timestamp(all_tags, manifest_metadata)
                        recent_tags = sorted_tags[:3]  # Take first 3 (newest)
                        recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
                    else:
                        tag_count = 0
                        recent_tags = []
                        recent_tags_display = "Error loading tags"
                else:
                    # Skip tag loading for large lists
                    tag_count = "Many"
                    recent_tags = []
                    recent_tags_display = "Too many repos - tags not loaded"
                
                repo_data.append({
                    "name": repo_name,
                    "tag_count": tag_count,
                    "recent_tags": recent_tags,
                    "recent_tags_display": recent_tags_display,
                    "last_updated": "Unknown"
                })
            
            # Sort repositories by name (alphabetical)
            repo_data.sort(key=lambda x: x['name'].lower())
            
            if self.tui_debug_logger:
                self.tui_debug_logger.debug("Pagination continuation complete", 
                                          repos_returned=len(repo_data),
                                          has_more_pages=bool(new_next_page_token))
            
            # Return repository data with pagination metadata
            return {
                "repositories": repo_data,
                "pagination": {
                    "method": "link_header_continuation",
                    "next_page_token": new_next_page_token,
                    "has_more": bool(new_next_page_token),
                    "page_size": page_size,
                    "repos_in_page": len(page_repos)
                }
            }


# Global registry manager instance
registry_manager = RegistryManager()
