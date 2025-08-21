"""
Mock Registry Data for Development and Testing

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

import json
from typing import Dict, Any


class MockRegistryData:
    """Mock data provider for container registry API responses"""
    
    def __init__(self):
        self.registries = {
            "mock://public-registry": {
                "name": "Public Registry Mock",
                "url": "mock://public-registry",
                "api_version": "v2",
                "status": "healthy",
                "repositories": ["alpine", "nginx", "redis", "postgres", "ubuntu", "debian", "node", "python", "golang", "mysql"],
                "auth_required": False
            },
            "mock://quay-io": {
                "name": "Quay.io Mock", 
                "url": "mock://quay-io",
                "api_version": "v2",
                "status": "healthy",
                "repositories": ["coreos/etcd", "prometheus/prometheus", "grafana/grafana", "jaegertracing/jaeger", "bitnami/kafka"],
                "auth_required": True
            },
            "mock://gcr-io": {
                "name": "Google Container Registry Mock",
                "url": "mock://gcr-io",
                "api_version": "v2",
                "status": "healthy", 
                "repositories": ["distroless/base", "distroless/java", "cloud-sql-proxy", "gke/pause", "tensorflow/tensorflow"],
                "auth_required": True
            },
            "mock://local-dev": {
                "name": "Local Development",
                "url": "mock://local-dev",
                "api_version": "v2",
                "status": "healthy",
                "repositories": ["webapp", "api-server", "database", "cache", "frontend", "worker", "scheduler"],
                "auth_required": False
            },
            "mock://enterprise": {
                "name": "Enterprise Registry",
                "url": "mock://enterprise",
                "api_version": "v2",
                "status": "healthy",
                "repositories": ["microservice-a", "microservice-b", "shared-lib", "base-image", "monitoring", "logging"],
                "auth_required": True
            },
            "mock://massive-registry": {
                "name": "Massive Test Registry",
                "url": "mock://massive-registry", 
                "api_version": "v2",
                "status": "healthy",
                "repositories": self._generate_large_repo_list(),
                "auth_required": False
            }
        }
    
    def _generate_large_repo_list(self):
        """Generate a large list of repositories for testing auto-loading"""
        repos = []
        
        # Base images
        base_images = ["ubuntu", "debian", "alpine", "centos", "fedora", "amazonlinux"]
        for base in base_images:
            for version in ["latest", "20.04", "22.04", "18.04", "bullseye", "bookworm", "3.17", "3.18"]:
                repos.append(f"{base}/{version}")
        
        # Language runtimes
        languages = ["node", "python", "golang", "java", "dotnet", "ruby", "php", "rust"]
        for lang in languages:
            for version in ["latest", "18", "16", "14", "3.11", "3.10", "3.9", "1.20", "1.19", "17", "11", "8"]:
                repos.append(f"{lang}/{version}")
                repos.append(f"{lang}/{version}-alpine")
                repos.append(f"{lang}/{version}-slim")
        
        # Databases
        databases = ["mysql", "postgres", "mongodb", "redis", "elasticsearch", "cassandra"]
        for db in databases:
            for version in ["latest", "8.0", "15", "14", "6.2", "7.0", "8.0"]:
                repos.append(f"{db}/{version}")
                repos.append(f"{db}/{version}-alpine")
        
        # Web servers
        web_servers = ["nginx", "apache", "traefik", "caddy"]
        for server in web_servers:
            for version in ["latest", "1.25", "1.24", "2.4", "stable", "alpine"]:
                repos.append(f"{server}/{version}")
        
        # Microservices (lots of these!)
        services = ["auth-service", "user-service", "order-service", "payment-service", 
                   "notification-service", "catalog-service", "inventory-service",
                   "shipping-service", "analytics-service", "reporting-service"]
        for service in services:
            for env in ["prod", "staging", "dev"]:
                for version in ["v1.0.0", "v1.1.0", "v1.2.0", "v2.0.0", "latest"]:
                    repos.append(f"{service}/{env}-{version}")
        
        # DevOps tools
        tools = ["jenkins", "sonarqube", "nexus", "gitlab", "prometheus", "grafana", "vault"]
        for tool in tools:
            for version in ["latest", "lts", "latest-alpine"]:
                repos.append(f"{tool}/{version}")
        
        return sorted(list(set(repos)))  # Remove duplicates and sort
    
    def get_api_version(self, registry_url: str) -> Dict[str, Any]:
        """Mock response for GET /v2/"""
        if registry_url in self.registries:
            return {
                "status_code": 200,
                "json": {"version": "v2"},
                "headers": {"Docker-Distribution-API-Version": "registry/2.0"}
            }
        return {"status_code": 404, "json": {"error": "registry not found"}}
    
    def get_catalog(self, registry_url: str) -> Dict[str, Any]:
        """Mock response for GET /v2/_catalog"""
        if registry_url in self.registries:
            registry = self.registries[registry_url]
            return {
                "status_code": 200,
                "json": {
                    "repositories": registry["repositories"]
                },
                "headers": {"Content-Type": "application/json"}
            }
        return {"status_code": 404, "json": {"error": "registry not found"}}
    
    def get_tags(self, registry_url: str, repository: str) -> Dict[str, Any]:
        """Mock response for GET /v2/{name}/tags/list"""
        if registry_url in self.registries:
            # Generate mock tags based on repository name with realistic variety
            base_tags = ["latest", "stable"]
            
            # Version tags - create lots for some repositories to test auto-loading
            if any(name in repository for name in ["alpine", "ubuntu", "debian"]):
                base_tags.extend(["3.18", "3.17", "3.16", "jammy", "focal", "bullseye", "slim"])
            elif "nginx" in repository:
                base_tags.extend(["1.25", "1.24", "1.23", "alpine", "mainline", "stable-alpine"])
            elif any(name in repository for name in ["postgres", "mysql"]):
                base_tags.extend(["15", "14", "13", "alpine", "15-alpine", "14-alpine"])
            elif "redis" in repository:
                base_tags.extend(["7.2", "7.0", "6.2", "alpine", "7.2-alpine"])
            elif any(name in repository for name in ["node", "python"]):
                # Add lots of version tags for testing auto-loading
                base_tags.extend(["18", "16", "14", "3.11", "3.10", "3.9", "alpine", "slim"])
                # Add many patch versions
                for major in [16, 17, 18, 19, 20]:
                    for minor in range(10):
                        for patch in range(5):
                            base_tags.append(f"{major}.{minor}.{patch}")
            elif "golang" in repository:
                base_tags.extend(["1.21", "1.20", "1.19", "alpine", "1.21-alpine"])
                # Add many Go versions for testing
                for major in [1]:
                    for minor in range(15, 22):
                        for patch in range(10):
                            base_tags.append(f"{major}.{minor}.{patch}")
            elif any(service in repository for service in ["microservice", "webapp", "auth-service", "user-service", "order-service", "payment-service", "notification-service", "catalog-service", "inventory-service", "shipping-service", "analytics-service", "reporting-service"]):
                base_tags.extend(["v2.1.0", "v2.0.3", "v1.9.8", "dev", "staging", "prod"])
                # Add many build versions for testing
                for major in range(1, 4):
                    for minor in range(10):
                        for patch in range(15):
                            base_tags.append(f"v{major}.{minor}.{patch}")
                            base_tags.append(f"v{major}.{minor}.{patch}-alpha")
                            base_tags.append(f"v{major}.{minor}.{patch}-beta")
            elif "prometheus" in repository or "grafana" in repository:
                base_tags.extend(["v2.45.0", "v2.44.0", "main", "latest-ubuntu"])
            else:
                # Generic service tags
                base_tags.extend(["v1.2.3", "v1.2.2", "v1.1.0", "dev", "test"])
            
            return {
                "status_code": 200,
                "json": {
                    "name": repository,
                    "tags": base_tags
                },
                "headers": {"Content-Type": "application/json"}
            }
        return {"status_code": 404, "json": {"error": "repository not found"}}
    
    def get_manifest(self, registry_url: str, repository: str, tag: str) -> Dict[str, Any]:
        """Mock response for GET /v2/{name}/manifests/{tag}"""
        if registry_url in self.registries:
            # Generate realistic layer sizes and counts based on image type
            layer_count = 3  # Default
            base_size = 5432100  # Default base layer size
            
            if repository in ["alpine", "distroless/base"]:
                layer_count = 1
                base_size = 2500000  # Smaller base images
            elif repository in ["ubuntu", "debian"]:
                layer_count = 4
                base_size = 28000000  # Larger base images
            elif repository in ["node", "python", "golang"]:
                layer_count = 6
                base_size = 45000000  # Runtime images
            elif "microservice" in repository or "webapp" in repository:
                layer_count = 8
                base_size = 12000000  # Application images
            
            # Generate realistic layer hierarchy
            layers = []
            for i in range(layer_count):
                if i == 0:  # Base layer is typically largest
                    size = base_size
                elif i == layer_count - 1:  # App layer is typically smallest
                    size = base_size // 10
                else:  # Middle layers vary
                    size = base_size // (2 + i)
                
                layers.append({
                    "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                    "size": size,
                    "digest": f"sha256:{hash(f'{repository}:{tag}:layer{i}'):064x}"[:64]
                })
            
            # Use OCI manifest format for some registries to test compatibility
            if "gcr-io" in registry_url or "quay-io" in registry_url:
                media_type = "application/vnd.oci.image.manifest.v1+json"
                config_media_type = "application/vnd.oci.image.config.v1+json"
            else:
                media_type = "application/vnd.docker.distribution.manifest.v2+json"
                config_media_type = "application/vnd.docker.container.image.v1+json"
            
            manifest_digest = f"sha256:{hash(f'{repository}:{tag}:manifest'):064x}"[:64]
            config_digest = f"sha256:{hash(f'{repository}:{tag}:config'):064x}"[:64]
            
            return {
                "status_code": 200,
                "json": {
                    "schemaVersion": 2,
                    "mediaType": media_type,
                    "config": {
                        "mediaType": config_media_type,
                        "size": 1234 + hash(repository) % 5000,  # Vary config size
                        "digest": config_digest
                    },
                    "layers": layers
                },
                "headers": {
                    "Content-Type": media_type,
                    "Docker-Content-Digest": manifest_digest
                }
            }
        return {"status_code": 404, "json": {"error": "manifest not found"}}
    
    def get_registry_info(self, registry_url: str) -> Dict[str, Any]:
        """Get mock registry information for display"""
        if registry_url in self.registries:
            registry = self.registries[registry_url]
            return {
                "name": registry["name"],
                "url": registry["url"],
                "api_version": registry["api_version"],
                "status": "✅" if registry["status"] == "healthy" else "❌",
                "auth_required": registry["auth_required"],
                "repository_count": len(registry["repositories"]),
                "last_checked": "Mock Time",
                "response_time": "1ms",
                "ssl_status": "Mock SSL"
            }
        return None


class MockDebugData:
    """Mock debug/API call data for testing the debug console"""
    
    def __init__(self):
        self.mock_api_calls = []
        self._generate_mock_calls()
    
    def _generate_mock_calls(self):
        """Generate realistic mock API calls"""
        import time
        
        base_time = time.time() - 300  # 5 minutes ago
        
        # Mock API calls with realistic patterns
        calls = [
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(base_time)),
                "method": "GET",
                "url": "mock://public-registry/v2/",
                "status_code": 200,
                "duration_ms": 45,
                "size_bytes": 123,
                "content_preview": '{"version": "v2"}',
                "response_content_full": '{"version": "v2"}',
                "headers": {"Docker-Distribution-API-Version": "registry/2.0"}
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(base_time + 10)),
                "method": "GET", 
                "url": "mock://public-registry/v2/_catalog",
                "status_code": 200,
                "duration_ms": 78,
                "size_bytes": 456,
                "content_preview": '{"repositories": ["alpine", "nginx", "redis"...]}',
                "response_content_full": '{"repositories": ["alpine", "nginx", "redis", "postgres", "ubuntu", "debian", "node", "python", "golang", "mysql"]}',
                "headers": {"Content-Type": "application/json"}
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(base_time + 25)),
                "method": "GET",
                "url": "mock://public-registry/v2/alpine/tags/list",
                "status_code": 200,
                "duration_ms": 123,
                "size_bytes": 789,
                "content_preview": '{"name": "alpine", "tags": ["latest", "3.18", "3.17"...]}',
                "response_content_full": '{"name": "alpine", "tags": ["latest", "3.18", "3.17", "3.16", "3.15", "edge"]}',
                "headers": {"Content-Type": "application/json"}
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(base_time + 45)),
                "method": "GET",
                "url": "mock://quay-io/v2/prometheus/prometheus/manifests/latest",
                "status_code": 200,
                "duration_ms": 234,
                "size_bytes": 2048,
                "content_preview": '{"schemaVersion": 2, "mediaType": "application/vnd.docker..."}',
                "response_content_full": '{"schemaVersion": 2, "mediaType": "application/vnd.docker.distribution.manifest.v2+json", "config": {"mediaType": "application/vnd.docker.container.image.v1+json", "size": 1234, "digest": "sha256:abcd1234"}, "layers": [{"mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip", "size": 5678, "digest": "sha256:layer1"}, {"mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip", "size": 9012, "digest": "sha256:layer2"}]}',
                "headers": {"Content-Type": "application/vnd.docker.distribution.manifest.v2+json"}
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(base_time + 60)),
                "method": "GET",
                "url": "mock://enterprise/v2/microservice-a/tags/list",
                "status_code": 404,
                "duration_ms": 89,
                "size_bytes": 67,
                "content_preview": '{"error": "repository not found"}',
                "response_content_full": '{"errors": [{"code": "NAME_UNKNOWN", "message": "repository name not known to registry", "detail": {"name": "nonexistent/repo"}}]}',
                "headers": {"Content-Type": "application/json"},
                "error": "Repository not found"
            },
            {
                "timestamp": time.strftime("%H:%M:%S", time.localtime(base_time + 80)),
                "method": "GET",
                "url": "mock://gcr-io/v2/distroless/base/manifests/latest",
                "status_code": 200,
                "duration_ms": 156,
                "size_bytes": 1567,
                "content_preview": '{"schemaVersion": 2, "mediaType": "application/vnd.oci.image..."}',
                "response_content_full": '{"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json", "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "size": 2345, "digest": "sha256:config123"}, "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "size": 6789, "digest": "sha256:oci_layer1"}, {"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "size": 3456, "digest": "sha256:oci_layer2"}]}',
                "headers": {"Content-Type": "application/vnd.oci.image.manifest.v1+json"}
            }
        ]
        
        self.mock_api_calls = calls
    
    def get_mock_calls(self):
        """Get all mock API calls"""
        return self.mock_api_calls.copy()


# Global mock data instances
mock_registry = MockRegistryData()
mock_debug = MockDebugData()
