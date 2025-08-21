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
from typing import Dict, List, Any, Optional
import httpx
from urllib.parse import urljoin


class RegistryClient:
    """HTTP client for Docker Registry API v2"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = None
    
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
    
    async def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make HTTP request and return response data"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        start_time = time.time()
        
        try:
            response = await self.session.get(url)
            duration = int((time.time() - start_time) * 1000)  # ms
            
            # Prepare response data
            response_data = {
                "url": url,
                "method": response.request.method,
                "status_code": response.status_code,
                "duration_ms": duration,
                "size_bytes": len(response.content),
                "headers": dict(response.headers),
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
    
    async def get_catalog(self) -> Dict[str, Any]:
        """Get repository catalog (GET /v2/_catalog)"""
        return await self._make_request('/v2/_catalog')
    
    async def get_tags(self, repository: str) -> Dict[str, Any]:
        """Get tags for repository (GET /v2/{name}/tags/list)"""
        return await self._make_request(f'/v2/{repository}/tags/list')
    
    async def get_manifest(self, repository: str, tag: str) -> Dict[str, Any]:
        """Get manifest for specific tag (GET /v2/{name}/manifests/{tag})"""
        url = urljoin(self.base_url + '/', f'/v2/{repository}/manifests/{tag}')
        start_time = time.time()
        
        try:
            # Accept multiple manifest formats
            headers = {
                "Accept": ", ".join([
                    "application/vnd.docker.distribution.manifest.v2+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json", 
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.v1+json"
                ])
            }
            response = await self.session.get(url, headers=headers)
            duration = int((time.time() - start_time) * 1000)
            
            response_data = {
                "url": url,
                "method": response.request.method,
                "status_code": response.status_code,
                "duration_ms": duration,
                "size_bytes": len(response.content),
                "headers": dict(response.headers),
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
        
    def add_api_call(self, call_data: Dict[str, Any]):
        """Add API call to debug log"""
        self.api_call_log.append(call_data)
        # Keep only last 100 calls
        if len(self.api_call_log) > 100:
            self.api_call_log = self.api_call_log[-100:]
    
    async def check_registry_status(self, registry_url: str) -> Dict[str, Any]:
        """Check if registry is accessible and get basic info"""
        async with RegistryClient(registry_url) as client:
            version_response = await client.check_api_version()
            self.add_api_call(version_response)
            
            if version_response["status_code"] == 200:
                # Try to get catalog for repo count
                catalog_response = await client.get_catalog()
                self.add_api_call(catalog_response)
                
                repo_count = "Unknown"
                if catalog_response["status_code"] == 200 and catalog_response.get("json"):
                    repos = catalog_response["json"].get("repositories", [])
                    repo_count = str(len(repos))
                
                return {
                    "status": "✅",
                    "api_version": "v2",
                    "repo_count": repo_count,
                    "response_time": f"{version_response['duration_ms']}ms",
                    "ssl_status": "Connected" # TODO: Better SSL status checking
                }
            else:
                return {
                    "status": "❌",
                    "api_version": "Unknown",
                    "repo_count": "Unknown", 
                    "response_time": f"{version_response['duration_ms']}ms",
                    "ssl_status": f"Error {version_response['status_code']}"
                }
    
    async def get_repositories(self, registry_url: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get repositories for a registry"""
        async with RegistryClient(registry_url) as client:
            catalog_response = await client.get_catalog()
            self.add_api_call(catalog_response)
            
            if catalog_response["status_code"] != 200:
                return []
            
            repositories = catalog_response.get("json", {}).get("repositories", [])
            repo_data = []
            
            # Get tag info for each repository (limited for performance)
            for repo_name in repositories[:limit]:
                tags_response = await client.get_tags(repo_name)
                self.add_api_call(tags_response)
                
                if tags_response["status_code"] == 200:
                    all_tags = tags_response.get("json", {}).get("tags", [])
                    tag_count = len(all_tags)
                    
                    # Get recent tags (exclude 'latest', take up to 3)
                    recent_tags = [tag for tag in all_tags if tag != "latest"][:3]
                    recent_tags_display = ", ".join(recent_tags) if recent_tags else "No recent tags"
                else:
                    tag_count = 0
                    recent_tags = []
                    recent_tags_display = "Error loading tags"
                
                repo_data.append({
                    "name": repo_name,
                    "tag_count": tag_count,
                    "recent_tags": recent_tags,
                    "recent_tags_display": recent_tags_display,
                    "last_updated": "Unknown"  # TODO: Parse from manifest
                })
            
            # Sort repositories by name (alphabetical)
            repo_data.sort(key=lambda x: x['name'].lower())
            
            return repo_data


# Global registry manager instance
registry_manager = RegistryManager()
