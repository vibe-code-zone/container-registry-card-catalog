"""
Configuration Manager - Phase 1: Basic Persistence

AI Attribution (AIA): EAI Hin R Claude Code v1.0
Full: AIA Entirely AI, Human-initiated, Reviewed, Claude Code v1.0
Expanded: This work was entirely AI-generated. AI was prompted for its contributions, 
or AI assistance was enabled. AI-generated content was reviewed and approved. 
The following model(s) or application(s) were used: Claude Code.
Interpretation: https://aiattribution.github.io/interpret-attribution
More: https://aiattribution.github.io/
Vibe-Coder: Andrew Potozniak <potozniak@redhat.com>
Session Date: 2025-08-27
"""

import json
import os
import platform
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Set up logging for config operations
logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages persistent configuration storage for registry settings and monitored repositories"""
    
    def __init__(self, app_name: str = "container-registry-card-catalog"):
        self.app_name = app_name
        self.config_dir = self._get_config_directory()
        self.config_file = self.config_dir / "config.json"
        self.backup_file = self.config_dir / "config.backup.json"
        
        # Ensure config directory exists
        self._ensure_config_directory()
    
    def _get_config_directory(self) -> Path:
        """Get platform-appropriate configuration directory"""
        system = platform.system().lower()
        
        if system == "linux":
            # Linux: ~/.config/app-name/
            config_base = Path.home() / ".config"
        elif system == "darwin":  # macOS
            # macOS: ~/Library/Application Support/app-name/
            config_base = Path.home() / "Library" / "Application Support"
        elif system == "windows":
            # Windows: %APPDATA%\app-name\
            config_base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            # Fallback: ~/.config/app-name/
            config_base = Path.home() / ".config"
        
        return config_base / self.app_name
    
    def _ensure_config_directory(self) -> None:
        """Create configuration directory if it doesn't exist"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions (user only)
            os.chmod(self.config_dir, 0o700)
            logger.info(f"Config directory ready: {self.config_dir}")
        except Exception as e:
            logger.error(f"Failed to create config directory {self.config_dir}: {e}")
            # Fallback to temp directory
            import tempfile
            self.config_dir = Path(tempfile.gettempdir()) / self.app_name
            self.config_dir.mkdir(exist_ok=True)
            logger.warning(f"Using fallback config directory: {self.config_dir}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure"""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "app_settings": {
                "debug_enabled": False,
                "mock_mode": False,
                "default_page_size": 50
            },
            "registries": []
        }
    
    def _backup_existing_config(self) -> None:
        """Create backup of existing config before saving new one"""
        if self.config_file.exists():
            try:
                # Copy existing config to backup
                with open(self.config_file, 'r') as src, open(self.backup_file, 'w') as dst:
                    dst.write(src.read())
                logger.debug(f"Config backed up to {self.backup_file}")
            except Exception as e:
                logger.warning(f"Failed to backup config: {e}")
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file, return defaults if not found"""
        try:
            if not self.config_file.exists():
                logger.info("No config file found, using defaults")
                return self._get_default_config()
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Validate basic structure
            if not isinstance(config, dict) or "registries" not in config:
                logger.warning("Config file format invalid, using defaults")
                return self._get_default_config()
            
            logger.info(f"Config loaded from {self.config_file}")
            logger.debug(f"Loaded {len(config.get('registries', []))} registry configurations")
            
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"Config file corrupted (JSON error): {e}")
            return self._get_default_config()
        except PermissionError:
            logger.error(f"Permission denied reading config file: {self.config_file}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            return self._get_default_config()
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            # Update timestamp
            config["last_updated"] = datetime.now().isoformat()
            
            # Backup existing config
            self._backup_existing_config()
            
            # Write new config
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=True)
            
            # Set restrictive permissions
            os.chmod(self.config_file, 0o600)
            
            registry_count = len(config.get('registries', []))
            logger.info(f"Config saved to {self.config_file} ({registry_count} registries)")
            
            return True
            
        except PermissionError:
            logger.error(f"Permission denied writing config file: {self.config_file}")
            return False
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def get_registry_config(self, registry_url: str) -> Optional[Dict[str, Any]]:
        """Get configuration for specific registry"""
        config = self.load_config()
        
        for registry in config.get("registries", []):
            if registry.get("url") == registry_url:
                return registry
        
        return None
    
    def save_registry_config(self, registry_url: str, registry_name: str, 
                           monitored_repos: List[str], settings: Dict[str, Any]) -> bool:
        """Save or update configuration for a specific registry"""
        config = self.load_config()
        
        # Find existing registry or create new one
        registry_config = None
        for i, registry in enumerate(config["registries"]):
            if registry["url"] == registry_url:
                registry_config = config["registries"][i]
                break
        
        if registry_config is None:
            # Create new registry config
            registry_config = {
                "id": self._generate_registry_id(registry_url),
                "name": registry_name,
                "url": registry_url,
                "enabled": True,
                "created": datetime.now().isoformat()
            }
            config["registries"].append(registry_config)
        
        # Update registry configuration
        registry_config.update({
            "name": registry_name,
            "monitored_repos": monitored_repos,
            "settings": settings,
            "last_updated": datetime.now().isoformat()
        })
        
        # Save updated config
        success = self.save_config(config)
        
        if success:
            logger.info(f"Registry config saved: {registry_name} ({len(monitored_repos)} monitored repos)")
        
        return success
    
    def _generate_registry_id(self, registry_url: str) -> str:
        """Generate a unique ID for a registry based on its URL"""
        import hashlib
        # Use URL to generate consistent ID
        url_hash = hashlib.md5(registry_url.encode()).hexdigest()[:8]
        
        # Clean URL for readable part
        clean_url = registry_url.replace("https://", "").replace("http://", "")
        clean_url = clean_url.replace("/", "-").replace(".", "-")
        
        return f"{clean_url}-{url_hash}"
    
    def get_monitored_repos(self, registry_url: str) -> List[str]:
        """Get monitored repositories for a specific registry"""
        registry_config = self.get_registry_config(registry_url)
        
        if registry_config:
            return registry_config.get("monitored_repos", [])
        
        return []
    
    def remove_registry_config(self, registry_url: str) -> bool:
        """Remove configuration for a registry"""
        config = self.load_config()
        
        # Find and remove registry
        original_count = len(config["registries"])
        config["registries"] = [r for r in config["registries"] if r.get("url") != registry_url]
        
        if len(config["registries"]) < original_count:
            success = self.save_config(config)
            if success:
                logger.info(f"Registry config removed: {registry_url}")
            return success
        
        logger.warning(f"Registry config not found for removal: {registry_url}")
        return False
    
    def list_configured_registries(self) -> List[Dict[str, Any]]:
        """Get list of all configured registries"""
        config = self.load_config()
        return config.get("registries", [])
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get information about the configuration system"""
        config = self.load_config()
        
        return {
            "config_dir": str(self.config_dir),
            "config_file": str(self.config_file),
            "config_exists": self.config_file.exists(),
            "backup_exists": self.backup_file.exists(),
            "version": config.get("version", "unknown"),
            "last_updated": config.get("last_updated", "never"),
            "registry_count": len(config.get("registries", [])),
            "total_monitored_repos": sum(len(r.get("monitored_repos", [])) 
                                       for r in config.get("registries", []))
        }


# Global config manager instance
config_manager = ConfigManager()