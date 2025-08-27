"""
Local Container Runtime Client (Podman/Docker)

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
import json
import time
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime


class LocalContainerClient:
    """Client for local container runtimes (podman/docker)"""
    
    def __init__(self, runtime: str = 'podman'):
        self.runtime = runtime
        self.cmd = runtime
        self.base_url = f"local://{runtime}"
    
    def _format_timestamp(self, timestamp: int) -> str:
        """Format Unix timestamp to human readable format"""
        if not timestamp or timestamp == 0:
            return "Unknown"
        
        try:
            # Convert to datetime
            dt = datetime.fromtimestamp(timestamp)
            now = datetime.now()
            
            # Calculate time difference
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days} days ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hours ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minutes ago"
            else:
                return "Just now"
        except (ValueError, OSError, OverflowError):
            return "Unknown"
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format"""
        if not size_bytes or size_bytes == 0:
            return "Unknown"
        
        try:
            # Convert bytes to human readable format
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    if unit == 'B':
                        return f"{int(size_bytes)} {unit}"
                    else:
                        return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} PB"
        except (ValueError, TypeError):
            return "Unknown"
    
    def _extract_description_from_labels(self, labels: dict) -> str:
        """Extract description from image labels"""
        if not labels:
            return None
            
        # Try common label keys for description
        description_labels = [
            'description', 'Description', 'DESCRIPTION',
            'summary', 'Summary', 'SUMMARY',
            'io.k8s.description', 'io.openshift.description',
            'org.label-schema.description', 'org.opencontainers.image.description'
        ]
        
        for label_key in description_labels:
            if label_key in labels and labels[label_key]:
                desc = labels[label_key].strip()
                if desc and desc != 'null' and desc != '""':
                    return desc
        
        # Try to get maintainer or vendor info as fallback
        maintainer_labels = [
            'maintainer', 'Maintainer', 'MAINTAINER',
            'vendor', 'Vendor', 'VENDOR',
            'org.label-schema.vendor', 'org.opencontainers.image.vendor'
        ]
        
        for label_key in maintainer_labels:
            if label_key in labels and labels[label_key]:
                maintainer = labels[label_key].strip()
                if maintainer and maintainer != 'null' and maintainer != '""':
                    return f"Maintained by {maintainer}"
        
        return None
    
    async def _run_command(self, args: List[str]) -> Dict[str, Any]:
        """Run container runtime command and return parsed output"""
        start_time = time.time()
        cmd = [self.cmd] + args
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout_bytes, stderr_bytes = await process.communicate()
            stdout = stdout_bytes.decode('utf-8') if stdout_bytes else ""
            stderr = stderr_bytes.decode('utf-8') if stderr_bytes else ""
            response_time = time.time() - start_time
            
            # Log the API call for debug console
            try:
                from registry_client import registry_manager
                status_code = process.returncode
                
                # Create API call entry in the same format as HTTP calls
                api_call = {
                    'method': 'LOCAL',
                    'url': f"{self.runtime} {' '.join(args)}",
                    'status_code': status_code,
                    'response_size': len(stdout) if stdout else len(stderr),
                    'duration_ms': int(response_time * 1000),
                    'response_content': stdout[:500] if stdout else stderr[:500],
                    'response_content_full': stdout if stdout else stderr,
                    'timestamp': time.strftime("%H:%M:%S.") + f"{int((time.time() % 1) * 1000):03d}",
                    'base_url': f'local://{self.runtime}',
                    'endpoint': args[0] if args else 'unknown',
                    'size_bytes': len(stdout) if stdout else len(stderr)
                }
                registry_manager.add_api_call(api_call)
            except ImportError:
                pass  # Ignore if registry_manager not available
            
            if process.returncode != 0:
                return {
                    'error': f"{self.runtime} command failed",
                    'stderr': stderr,
                    'status_code': process.returncode
                }
            
            # Try to parse JSON output
            if stdout.strip():
                try:
                    return {'data': json.loads(stdout), 'status_code': 200}
                except json.JSONDecodeError:
                    return {'data': stdout.strip(), 'status_code': 200}
            
            return {'data': [], 'status_code': 200}
            
        except Exception as e:
            return {
                'error': f"Failed to run {self.runtime} command: {str(e)}",
                'status_code': 500
            }
    
    async def check_health(self) -> Dict[str, Any]:
        """Check if the container runtime is available"""
        result = await self._run_command(['version', '--format', 'json'])
        
        if 'error' in result:
            return {
                'status': 'error',
                'error': result['error'],
                'response_time': 0
            }
        
        version_info = result.get('data', {})
        if isinstance(version_info, list) and len(version_info) > 0:
            version_info = version_info[0]
        
        return {
            'status': 'healthy',
            'version': version_info.get('Client', {}).get('Version', 'Unknown'),
            'api_version': 'Local Cache',
            'response_time': 0.1  # Local is always fast
        }
    
    async def get_repositories(self) -> Dict[str, Any]:
        """Get list of repositories from local images"""
        result = await self._run_command(['images', '--format', 'json'])
        
        if 'error' in result:
            return result
        
        images = result.get('data', [])
        if not isinstance(images, list):
            return {'error': 'Unexpected response format', 'status_code': 500}
        
        # Group images by repository
        repos = defaultdict(lambda: {
            'name': '',
            'tags': [],
            'tag_details': {},  # Store full tag info including digests
            'image_refs': {},   # Store inspectable image references (full IDs or repo:tag)
            'total_size': 0,
            'image_count': 0,
            'last_updated': None,
            'description': None  # Store description from labels
        })
        
        orphaned_images = []
        
        for image in images:
            repo_tags = image.get('RepoTags') or []
            repo_digests = image.get('RepoDigests') or []
            names = image.get('Names') or []  # Alternative source for tag names
            size = image.get('Size', 0)
            created = image.get('Created', 0)
            image_id = image.get('Id', '')[:12]  # Short ID
            labels = image.get('Labels', {}) or {}
            
            # Extract description from labels
            image_description = self._extract_description_from_labels(labels)
            
            # Combine RepoTags and Names for a complete picture, removing duplicates
            all_tags = list(repo_tags) if repo_tags else []
            if names:
                all_tags.extend(names)
            # Remove duplicates while preserving order
            all_tags = list(dict.fromkeys(all_tags))
            
            # Handle orphaned images
            if not all_tags and not repo_digests:
                # Truly orphaned image: <none> <none>
                orphaned_images.append({
                    'image_id': image_id,
                    'size': size,
                    'created': created,
                    'type': 'orphaned'
                })
                continue
            
            # Handle both tagged and digest-only images from all_tags (RepoTags + Names)
            if all_tags:
                tag_processed = False  # Track if we processed any normal tags
                
                for repo_tag in all_tags:
                    if '@sha256:' in repo_tag:
                        # This is a digest reference - handle like repo_digests
                        if '@' in repo_tag:
                            repo_name = repo_tag.split('@')[0]
                            full_digest_part = repo_tag.split('@')[1]  # Just the sha256:... part
                            # For tag name, use just the hash part without sha256: prefix
                            if full_digest_part.startswith('sha256:'):
                                digest_short = full_digest_part[7:19]  # Skip 'sha256:' and take first 12 chars of hash
                            else:
                                digest_short = full_digest_part[:12]  # Fallback
                            
                            repos[repo_name]['name'] = repo_name
                            if digest_short not in repos[repo_name]['tags']:
                                repos[repo_name]['tags'].append(digest_short)
                            repos[repo_name]['tag_details'][digest_short] = {
                                'full_digest': full_digest_part,  # Store just sha256:... without repo prefix
                                'type': 'digest'
                            }
                            # Store the full digest reference for inspection
                            repos[repo_name]['image_refs'][digest_short] = repo_tag
                            repos[repo_name]['total_size'] += size
                            repos[repo_name]['image_count'] += 1
                            
                            if repos[repo_name]['last_updated'] is None or created > repos[repo_name]['last_updated']:
                                repos[repo_name]['last_updated'] = created
                    else:
                        # This is a normal tag reference
                        tag_processed = True
                        
                        if ':' in repo_tag:
                            repo_name, tag = repo_tag.rsplit(':', 1)
                        else:
                            repo_name, tag = repo_tag, 'latest'
                        
                        repos[repo_name]['name'] = repo_name
                        # Only add tag if not already present
                        if tag not in repos[repo_name]['tags']:
                            repos[repo_name]['tags'].append(tag)
                        repos[repo_name]['tag_details'][tag] = {
                            'full_digest': f"sha256:{image.get('Id', '')}",
                            'type': 'tag'
                        }
                        # Store the repo:tag for inspection (this is what podman knows about)
                        repos[repo_name]['image_refs'][tag] = repo_tag
                        repos[repo_name]['total_size'] += size
                        repos[repo_name]['image_count'] += 1
                        
                        # Store description from the most recent image
                        if image_description and (repos[repo_name]['description'] is None or created > repos[repo_name]['last_updated']):
                            repos[repo_name]['description'] = image_description
                        
                        if repos[repo_name]['last_updated'] is None or created > repos[repo_name]['last_updated']:
                            repos[repo_name]['last_updated'] = created
            
            # Handle additional digest-only images from repo_digests (if not already processed via Names)
            elif not all_tags and repo_digests:
                for digest in repo_digests:
                    if '@' in digest:
                        repo_name = digest.split('@')[0]
                        full_digest_part = digest.split('@')[1]  # Just the sha256:... part
                        # For tag name, use just the hash part without sha256: prefix
                        if full_digest_part.startswith('sha256:'):
                            digest_short = full_digest_part[7:19]  # Skip 'sha256:' and take first 12 chars of hash
                        else:
                            digest_short = full_digest_part[:12]  # Fallback
                        
                        repos[repo_name]['name'] = repo_name
                        repos[repo_name]['tags'].append(digest_short)
                        repos[repo_name]['tag_details'][digest_short] = {
                            'full_digest': full_digest_part,  # Store just sha256:... without repo prefix
                            'type': 'digest'
                        }
                        # Store the full digest reference for inspection
                        repos[repo_name]['image_refs'][digest_short] = digest
                        repos[repo_name]['total_size'] += size
                        repos[repo_name]['image_count'] += 1
                        
                        if repos[repo_name]['last_updated'] is None or created > repos[repo_name]['last_updated']:
                            repos[repo_name]['last_updated'] = created
        
        # Add orphaned images as a special repository
        if orphaned_images:
            repos['<orphaned>'] = {
                'name': '<orphaned>',
                'tags': ['<none>'],
                'total_size': sum(img['size'] for img in orphaned_images),
                'image_count': len(orphaned_images),
                'last_updated': max(img['created'] for img in orphaned_images),
                'orphaned_images': orphaned_images
            }
        
        # Convert to list format expected by the UI
        repo_list = []
        for repo_name, repo_data in repos.items():
            # Get recent tags (exclude 'latest', take up to 3)
            all_tags = repo_data['tags']
            recent_tags = [tag for tag in all_tags if tag != 'latest'][:3]
            recent_tags_display = ', '.join(recent_tags) if recent_tags else 'No recent tags'
            
            # Get the most recent image ID for latest hash and description
            latest_image_id = None
            description = repo_data.get('description', f"{repo_data['image_count']} images, {len(set(repo_data['tags']))} unique tags")
            
            tag_details = repo_data.get('tag_details', {})
            if tag_details:
                # Find the tag with the most recent creation time
                latest_tag = max(tag_details.keys(), 
                                key=lambda t: repo_data.get('creation_times', {}).get(t, 0), 
                                default=None)
                if latest_tag:
                    latest_image_id = tag_details[latest_tag].get('full_digest', 'Unknown')
            
            repo_list.append({
                'name': repo_name,
                'tag_count': len(set(repo_data['tags'])),  # Unique tags
                'recent_tags': recent_tags,
                'recent_tags_display': recent_tags_display,
                'tag_details': tag_details,  # Include full tag details
                'size': self._format_size(repo_data['total_size']),
                'last_updated': self._format_timestamp(repo_data['last_updated'] or 0),
                'description': description,
                'latest_hash': latest_image_id or 'Unknown'
            })
        
        # Sort by repository name (alphabetical)
        repo_list.sort(key=lambda x: x['name'].lower())
        
        return {
            'data': repo_list,
            'status_code': 200,
            'total_repositories': len(repo_list)
        }
    
    async def get_tags(self, repository: str) -> Dict[str, Any]:
        """Get tags for a specific repository"""
        result = await self._run_command(['images', '--format', 'json'])
        
        if 'error' in result:
            return result
        
        images = result.get('data', [])
        tags = []
        
        if repository == '<orphaned>':
            # Handle orphaned images specially
            for image in images:
                repo_tags = image.get('RepoTags') or []
                repo_digests = image.get('RepoDigests') or []
                image_id_short = image.get('Id', '')[:12]
                
                if not repo_tags and not repo_digests:
                    # Truly orphaned - use image ID as unique tag name
                    created_timestamp = image.get('Created', 0)
                    tags.append({
                        'name': f'<none>:{image_id_short}',
                        'tag': f'<none>:{image_id_short}',
                        'repository': repository,
                        'registry_url': f"local://{self.runtime}",
                        'image_id': image_id_short,
                        'size': self._format_size(image.get('Size', 0)),
                        'created': self._format_timestamp(created_timestamp),
                        'created_timestamp': created_timestamp,  # Keep raw timestamp for sorting
                        'digest': 'sha256:' + image.get('Id', ''),
                        'digest_short': 'sha256:' + image.get('Id', '')[:12],
                        'type': 'orphaned'
                    })
                elif not repo_tags and repo_digests:
                    # Untagged but has digest - use image ID as unique tag name
                    original_repo = repo_digests[0].split('@')[0] if repo_digests else 'unknown'
                    created_timestamp = image.get('Created', 0)
                    tags.append({
                        'name': f'<none>:{image_id_short}',
                        'tag': f'<none>:{image_id_short}',
                        'repository': repository,
                        'registry_url': f"local://{self.runtime}",
                        'image_id': image_id_short,
                        'size': self._format_size(image.get('Size', 0)),
                        'created': self._format_timestamp(created_timestamp),
                        'created_timestamp': created_timestamp,  # Keep raw timestamp for sorting
                        'digest': repo_digests[0] if repo_digests else 'sha256:' + image.get('Id', ''),
                        'type': 'untagged',
                        'original_repo': original_repo
                    })
        else:
            # Handle normal repository
            for image in images:
                repo_tags = image.get('RepoTags') or []
                repo_digests = image.get('RepoDigests') or []
                names = image.get('Names') or []
                image_id_short = image.get('Id', '')[:12]
                
                # Combine RepoTags and Names for a complete picture, removing duplicates
                all_tags = list(repo_tags) if repo_tags else []
                if names:
                    all_tags.extend(names)
                # Remove duplicates while preserving order
                all_tags = list(dict.fromkeys(all_tags))
                
                # Check tagged images from all_tags (RepoTags + Names)
                if all_tags:
                    for repo_tag in all_tags:
                        if '@sha256:' in repo_tag:
                            # This is a digest reference
                            if '@' in repo_tag:
                                repo_name = repo_tag.split('@')[0]
                                if repo_name == repository:
                                    full_digest_part = repo_tag.split('@')[1]
                                    if full_digest_part.startswith('sha256:'):
                                        digest_short = full_digest_part[7:19]  # Skip 'sha256:' and take first 12 chars
                                    else:
                                        digest_short = full_digest_part[:12]
                                    
                                    created_timestamp = image.get('Created', 0)
                                    tags.append({
                                        'name': digest_short,
                                        'tag': digest_short,
                                        'repository': repository,
                                        'registry_url': f"local://{self.runtime}",
                                        'image_id': image_id_short,
                                        'size': self._format_size(image.get('Size', 0)),
                                        'created': self._format_timestamp(created_timestamp),
                                        'created_timestamp': created_timestamp,
                                        'digest': repo_tag,  # Full digest reference
                                        'digest_short': f"sha256:{digest_short}",
                                        'manifest_media_type': 'application/vnd.docker.distribution.manifest.v2+json'
                                    })
                        else:
                            # This is a normal tag reference
                            if ':' in repo_tag:
                                repo_name, tag = repo_tag.rsplit(':', 1)
                            else:
                                repo_name, tag = repo_tag, 'latest'
                            
                            if repo_name == repository:
                                created_timestamp = image.get('Created', 0)
                                tags.append({
                                    'name': tag,
                                    'tag': tag,
                                    'repository': repository,
                                    'registry_url': f"local://{self.runtime}",
                                    'image_id': image_id_short,
                                    'size': self._format_size(image.get('Size', 0)),
                                    'created': self._format_timestamp(created_timestamp),
                                    'created_timestamp': created_timestamp,
                                    'digest': f"sha256:{image.get('Id', '')}",
                                    'digest_short': f"sha256:{image.get('Id', '')[:12]}",
                                    'manifest_media_type': 'application/vnd.docker.distribution.manifest.v2+json'
                                })
                
                # Check digest-only images from repo_digests (if not already processed via all_tags)
                elif not all_tags and repo_digests:
                    for digest in repo_digests:
                        if '@' in digest:
                            repo_name = digest.split('@')[0]
                            if repo_name == repository:
                                full_digest_part = digest.split('@')[1]
                                if full_digest_part.startswith('sha256:'):
                                    digest_short = full_digest_part[7:19]  # Skip 'sha256:' and take first 12 chars
                                else:
                                    digest_short = full_digest_part[:12]
                                
                                created_timestamp = image.get('Created', 0)
                                tags.append({
                                    'name': digest_short,
                                    'tag': digest_short,
                                    'repository': repository,
                                    'registry_url': f"local://{self.runtime}",
                                    'image_id': image_id_short,
                                    'size': self._format_size(image.get('Size', 0)),
                                    'created': self._format_timestamp(created_timestamp),
                                    'created_timestamp': created_timestamp,
                                    'digest': digest,
                                    'manifest_media_type': 'application/vnd.docker.distribution.manifest.v2+json'
                                })
        
        # Sort by creation time (newest first), then by tag name (alphanumeric)
        tags.sort(key=lambda x: (-x.get('created_timestamp', 0), x['name'].lower()))
        
        return {
            'data': {'tags': tags},
            'status_code': 200
        }
    
    async def get_manifest(self, repository: str, tag: str) -> Dict[str, Any]:
        """Get manifest information for a specific tag"""
        # For orphaned images, we need to find by image ID
        if repository == '<orphaned>' and tag == '<none>':
            return {
                'error': 'Manifest not available for orphaned images',
                'status_code': 404
            }
        
        # Find the image for this repo:tag combination
        result = await self._run_command(['images', '--format', 'json'])
        if 'error' in result:
            return result
        
        images = result.get('data', [])
        target_image_id = None
        
        for image in images:
            repo_tags = image.get('RepoTags') or []
            repo_digests = image.get('RepoDigests') or []
            names = image.get('Names') or []
            
            # Combine RepoTags and Names for comprehensive search
            all_tags = list(repo_tags) if repo_tags else []
            if names:
                all_tags.extend(names)
            # Remove duplicates while preserving order
            all_tags = list(dict.fromkeys(all_tags))
            
            # Check for normal tag match
            for repo_tag in all_tags:
                if '@sha256:' not in repo_tag:  # Normal tag
                    if repo_tag == f"{repository}:{tag}":
                        target_image_id = image.get('Id', '')
                        break
                else:  # Digest reference
                    if '@' in repo_tag:
                        repo_name = repo_tag.split('@')[0]
                        if repo_name == repository:
                            full_digest_part = repo_tag.split('@')[1]
                            if full_digest_part.startswith('sha256:'):
                                digest_short = full_digest_part[7:19]  # First 12 chars of hash
                            else:
                                digest_short = full_digest_part[:12]
                            
                            if digest_short == tag:  # tag is actually the short digest
                                target_image_id = image.get('Id', '')
                                break
            
            if target_image_id:
                break
            
            # Also check repo_digests for digest-only tags
            if not target_image_id:
                for digest in repo_digests:
                    if '@' in digest:
                        repo_name = digest.split('@')[0]
                        if repo_name == repository:
                            full_digest_part = digest.split('@')[1]
                            if full_digest_part.startswith('sha256:'):
                                digest_short = full_digest_part[7:19]
                            else:
                                digest_short = full_digest_part[:12]
                            
                            if digest_short == tag:
                                target_image_id = image.get('Id', '')
                                break
                
                if target_image_id:
                    break
        
        if not target_image_id:
            return {
                'error': f'Image not found for {repository}:{tag}',
                'status_code': 404
            }
        
        # Get detailed image information
        inspect_result = await self._run_command(['inspect', target_image_id])
        if 'error' in inspect_result:
            return inspect_result
        
        inspect_data = inspect_result.get('data', [])
        if not inspect_data:
            return {
                'error': 'No inspection data returned',
                'status_code': 404
            }
        
        image_data = inspect_data[0]
        
        # Extract layer information
        layers = []
        history = image_data.get('History', [])
        rootfs = image_data.get('RootFS', {})
        layer_digests = rootfs.get('Layers', [])
        
        # Try to estimate layer sizes from history if available
        history_sizes = []
        if history:
            for hist_entry in history:
                size = hist_entry.get('Size', 0)
                if size and size > 0:
                    history_sizes.append(size)
        
        for i, layer_digest in enumerate(layer_digests):
            # Use history size if available, otherwise estimate
            layer_size = 0
            if i < len(history_sizes):
                layer_size = history_sizes[i]
            elif history_sizes:
                # Use average of available sizes as estimate
                layer_size = sum(history_sizes) // len(history_sizes)
            
            layer_info = {
                'mediaType': 'application/vnd.docker.image.rootfs.diff.tar.gzip',
                'size': layer_size,
                'digest': layer_digest
            }
            layers.append(layer_info)
        
        # Create a mock manifest structure
        manifest = {
            'schemaVersion': 2,
            'mediaType': 'application/vnd.docker.distribution.manifest.v2+json',
            'config': {
                'mediaType': 'application/vnd.docker.container.image.v1+json',
                'size': len(json.dumps(image_data.get('Config', {}))),
                'digest': f"sha256:{target_image_id}"
            },
            'layers': layers
        }
        
        return {
            'data': {
                'manifest': manifest,
                'image_data': image_data
            },
            'status_code': 200
        }