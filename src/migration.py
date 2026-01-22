"""
Migration tools for converting projects between Git and Supabase backends.

Provides utilities to:
- Export a Git project to Supabase
- Export a Supabase project to local Git files
- Migrate node types and prompts
"""

import json
import os
import shutil
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from datetime import datetime

from src.paths import DB_DIR


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    nodes_migrated: int
    users_migrated: int
    errors: list[str]
    warnings: list[str]


class MigrationProgress:
    """Callback interface for migration progress updates."""
    
    def __init__(self, callback: Optional[Callable[[str, int, int], None]] = None):
        self.callback = callback
        self.current = 0
        self.total = 0
    
    def set_total(self, total: int):
        self.total = total
        self.current = 0
    
    def update(self, message: str):
        self.current += 1
        if self.callback:
            self.callback(message, self.current, self.total)


class GitToSupabaseMigrator:
    """Migrate a local Git project to Supabase."""
    
    def __init__(self, project_name: str, supabase_url: str, supabase_key: str, 
                 user_id: str, progress: Optional[MigrationProgress] = None):
        self.project_name = project_name
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.user_id = user_id
        self.progress = progress or MigrationProgress()
        self.errors: list[str] = []
        self.warnings: list[str] = []
        
        # Initialize Supabase client
        try:
            from supabase import create_client
            self.supabase = create_client(supabase_url, supabase_key)
        except ImportError:
            raise ImportError("supabase-py is required for Supabase migration. Install with: pip install supabase")
    
    def migrate(self) -> MigrationResult:
        """Perform the full migration from Git to Supabase."""
        nodes_migrated = 0
        users_migrated = 0
        
        project_path = DB_DIR / self.project_name
        if not project_path.exists():
            return MigrationResult(
                success=False,
                nodes_migrated=0,
                users_migrated=0,
                errors=[f"Project not found: {self.project_name}"],
                warnings=[]
            )
        
        try:
            # Step 1: Create project in Supabase
            project_id = self._create_project()
            if not project_id:
                return MigrationResult(
                    success=False,
                    nodes_migrated=0,
                    users_migrated=0,
                    errors=self.errors,
                    warnings=self.warnings
                )
            
            # Step 2: Migrate node types
            self._migrate_node_types(project_id, project_path)
            
            # Step 3: Migrate prompts
            self._migrate_prompts(project_id, project_path)
            
            # Step 4: Migrate nodes
            nodes_migrated = self._migrate_nodes(project_id, project_path)
            
            # Step 5: Migrate user data
            users_migrated = self._migrate_users(project_id, project_path)
            
            # Step 6: Update project config to use Supabase
            self._update_project_config(project_path)
            
            return MigrationResult(
                success=len(self.errors) == 0,
                nodes_migrated=nodes_migrated,
                users_migrated=users_migrated,
                errors=self.errors,
                warnings=self.warnings
            )
            
        except Exception as e:
            self.errors.append(f"Migration failed: {str(e)}")
            return MigrationResult(
                success=False,
                nodes_migrated=nodes_migrated,
                users_migrated=users_migrated,
                errors=self.errors,
                warnings=self.warnings
            )
    
    def _create_project(self) -> Optional[str]:
        """Create the project in Supabase and return its ID."""
        try:
            # Generate a slug from project name
            slug = self.project_name.lower().replace(' ', '-').replace('_', '-')
            
            response = self.supabase.table('projects').insert({
                'name': self.project_name,
                'slug': slug,
                'owner_id': self.user_id,
                'is_public': False,  # Default to private
                'settings': {}
            }).execute()
            
            if response.data:
                self.progress.update(f"Created project: {self.project_name}")
                return response.data[0]['id']
            else:
                self.errors.append("Failed to create project in Supabase")
                return None
                
        except Exception as e:
            self.errors.append(f"Failed to create project: {str(e)}")
            return None
    
    def _migrate_node_types(self, project_id: str, project_path: Path):
        """Migrate node types to Supabase."""
        node_types_path = project_path / 'node_types'
        if not node_types_path.exists():
            return
        
        # Migrate each node type directory
        for type_dir in node_types_path.iterdir():
            if type_dir.is_dir():
                type_name = type_dir.name
                schema_file = type_dir / 'schema.json'
                
                schema = {}
                if schema_file.exists():
                    with open(schema_file, 'r', encoding='utf-8') as f:
                        schema = json.load(f)
                
                try:
                    self.supabase.table('node_types').insert({
                        'project_id': project_id,
                        'name': type_name,
                        'schema': schema,
                        'icon': schema.get('icon', 'category'),
                        'color': schema.get('color', '#666666')
                    }).execute()
                    
                    self.progress.update(f"Migrated node type: {type_name}")
                    
                except Exception as e:
                    self.warnings.append(f"Failed to migrate node type {type_name}: {str(e)}")
    
    def _migrate_prompts(self, project_id: str, project_path: Path):
        """Migrate prompts to Supabase."""
        prompts_path = project_path / 'prompts'
        if not prompts_path.exists():
            return
        
        for prompt_file in prompts_path.glob('*.md'):
            prompt_name = prompt_file.stem
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            try:
                self.supabase.table('prompts').insert({
                    'project_id': project_id,
                    'name': prompt_name,
                    'content': content
                }).execute()
                
                self.progress.update(f"Migrated prompt: {prompt_name}")
                
            except Exception as e:
                self.warnings.append(f"Failed to migrate prompt {prompt_name}: {str(e)}")
    
    def _migrate_nodes(self, project_id: str, project_path: Path) -> int:
        """Migrate all nodes to Supabase."""
        nodes_path = project_path / 'nodes'
        if not nodes_path.exists():
            return 0
        
        node_files = list(nodes_path.glob('*.json'))
        self.progress.set_total(len(node_files))
        
        migrated = 0
        for node_file in node_files:
            try:
                with open(node_file, 'r', encoding='utf-8') as f:
                    node_data = json.load(f)
                
                node_id = node_file.stem
                
                self.supabase.table('nodes').insert({
                    'id': node_id,
                    'project_id': project_id,
                    'title': node_data.get('title', 'Untitled'),
                    'content': node_data.get('content', ''),
                    'node_type': node_data.get('type', 'default'),
                    'position_x': node_data.get('x', 0),
                    'position_y': node_data.get('y', 0),
                    'custom_fields': node_data.get('custom_fields', {}),
                    'created_by': self.user_id
                }).execute()
                
                # Migrate connections
                for target_id in node_data.get('links', []):
                    try:
                        self.supabase.table('connections').insert({
                            'source_id': node_id,
                            'target_id': target_id,
                            'project_id': project_id
                        }).execute()
                    except Exception:
                        pass  # Connection might fail if target not yet migrated
                
                migrated += 1
                self.progress.update(f"Migrated node: {node_data.get('title', node_id)}")
                
            except Exception as e:
                self.warnings.append(f"Failed to migrate node {node_file.name}: {str(e)}")
        
        return migrated
    
    def _migrate_users(self, project_id: str, project_path: Path) -> int:
        """Migrate user data files to Supabase."""
        data_path = project_path / 'data'
        if not data_path.exists():
            return 0
        
        user_files = list(data_path.glob('*.json'))
        migrated = 0
        
        for user_file in user_files:
            try:
                username = user_file.stem
                with open(user_file, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                
                # Store user data as project-level user settings
                self.supabase.table('project_users').insert({
                    'project_id': project_id,
                    'display_name': username,
                    'settings': user_data
                }).execute()
                
                migrated += 1
                self.progress.update(f"Migrated user data: {username}")
                
            except Exception as e:
                self.warnings.append(f"Failed to migrate user {user_file.name}: {str(e)}")
        
        return migrated
    
    def _update_project_config(self, project_path: Path):
        """Update the project's config.json to use Supabase backend."""
        config_path = project_path / 'config.json'
        
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        config['backend'] = 'supabase'
        config['supabase_url'] = self.supabase_url
        config['supabase_key'] = self.supabase_key
        config['migrated_at'] = datetime.now().isoformat()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        self.progress.update("Updated project config")


class SupabaseToGitMigrator:
    """Export a Supabase project to local Git files."""
    
    def __init__(self, project_id: str, supabase_url: str, supabase_key: str,
                 target_name: Optional[str] = None, progress: Optional[MigrationProgress] = None):
        self.project_id = project_id
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.target_name = target_name
        self.progress = progress or MigrationProgress()
        self.errors: list[str] = []
        self.warnings: list[str] = []
        
        try:
            from supabase import create_client
            self.supabase = create_client(supabase_url, supabase_key)
        except ImportError:
            raise ImportError("supabase-py is required for Supabase migration")
    
    def migrate(self) -> MigrationResult:
        """Perform the full export from Supabase to local files."""
        nodes_migrated = 0
        users_migrated = 0
        
        try:
            # Step 1: Get project info
            project = self._get_project()
            if not project:
                return MigrationResult(
                    success=False,
                    nodes_migrated=0,
                    users_migrated=0,
                    errors=self.errors,
                    warnings=self.warnings
                )
            
            project_name = self.target_name or project['name']
            project_path = DB_DIR / project_name
            
            # Step 2: Create directory structure
            self._create_directories(project_path)
            
            # Step 3: Export node types
            self._export_node_types(project_path)
            
            # Step 4: Export prompts
            self._export_prompts(project_path)
            
            # Step 5: Export nodes
            nodes_migrated = self._export_nodes(project_path)
            
            # Step 6: Export user data
            users_migrated = self._export_users(project_path)
            
            # Step 7: Create Git config
            self._create_git_config(project_path)
            
            return MigrationResult(
                success=len(self.errors) == 0,
                nodes_migrated=nodes_migrated,
                users_migrated=users_migrated,
                errors=self.errors,
                warnings=self.warnings
            )
            
        except Exception as e:
            self.errors.append(f"Export failed: {str(e)}")
            return MigrationResult(
                success=False,
                nodes_migrated=nodes_migrated,
                users_migrated=users_migrated,
                errors=self.errors,
                warnings=self.warnings
            )
    
    def _get_project(self) -> Optional[dict]:
        """Fetch project info from Supabase."""
        try:
            response = self.supabase.table('projects').select('*').eq('id', self.project_id).execute()
            
            if response.data:
                return response.data[0]
            else:
                self.errors.append(f"Project not found: {self.project_id}")
                return None
                
        except Exception as e:
            self.errors.append(f"Failed to fetch project: {str(e)}")
            return None
    
    def _create_directories(self, project_path: Path):
        """Create the project directory structure."""
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / 'nodes').mkdir(exist_ok=True)
        (project_path / 'data').mkdir(exist_ok=True)
        (project_path / 'node_types').mkdir(exist_ok=True)
        (project_path / 'prompts').mkdir(exist_ok=True)
        
        self.progress.update("Created directory structure")
    
    def _export_node_types(self, project_path: Path):
        """Export node types to local files."""
        try:
            response = self.supabase.table('node_types').select('*').eq('project_id', self.project_id).execute()
            
            for node_type in response.data or []:
                type_name = node_type['name']
                type_dir = project_path / 'node_types' / type_name
                type_dir.mkdir(exist_ok=True)
                
                schema = node_type.get('schema', {})
                schema['icon'] = node_type.get('icon', 'category')
                schema['color'] = node_type.get('color', '#666666')
                
                with open(type_dir / 'schema.json', 'w', encoding='utf-8') as f:
                    json.dump(schema, f, indent=2)
                
                self.progress.update(f"Exported node type: {type_name}")
                
        except Exception as e:
            self.warnings.append(f"Failed to export node types: {str(e)}")
    
    def _export_prompts(self, project_path: Path):
        """Export prompts to local files."""
        try:
            response = self.supabase.table('prompts').select('*').eq('project_id', self.project_id).execute()
            
            prompts_dir = project_path / 'prompts'
            for prompt in response.data or []:
                prompt_file = prompts_dir / f"{prompt['name']}.md"
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(prompt.get('content', ''))
                
                self.progress.update(f"Exported prompt: {prompt['name']}")
                
        except Exception as e:
            self.warnings.append(f"Failed to export prompts: {str(e)}")
    
    def _export_nodes(self, project_path: Path) -> int:
        """Export all nodes to local JSON files."""
        try:
            response = self.supabase.table('nodes').select('*').eq('project_id', self.project_id).execute()
            
            nodes = response.data or []
            self.progress.set_total(len(nodes))
            
            # Fetch all connections for this project
            conn_response = self.supabase.table('connections').select('*').eq('project_id', self.project_id).execute()
            connections = conn_response.data or []
            
            # Build connection map
            connection_map: dict[str, list[str]] = {}
            for conn in connections:
                source = conn['source_id']
                target = conn['target_id']
                if source not in connection_map:
                    connection_map[source] = []
                connection_map[source].append(target)
            
            nodes_dir = project_path / 'nodes'
            exported = 0
            
            for node in nodes:
                node_id = node['id']
                node_data = {
                    'title': node.get('title', 'Untitled'),
                    'content': node.get('content', ''),
                    'type': node.get('node_type', 'default'),
                    'x': node.get('position_x', 0),
                    'y': node.get('position_y', 0),
                    'links': connection_map.get(node_id, []),
                    'custom_fields': node.get('custom_fields', {})
                }
                
                with open(nodes_dir / f"{node_id}.json", 'w', encoding='utf-8') as f:
                    json.dump(node_data, f, indent=2)
                
                exported += 1
                self.progress.update(f"Exported node: {node_data['title']}")
            
            return exported
            
        except Exception as e:
            self.errors.append(f"Failed to export nodes: {str(e)}")
            return 0
    
    def _export_users(self, project_path: Path) -> int:
        """Export user data to local files."""
        try:
            response = self.supabase.table('project_users').select('*').eq('project_id', self.project_id).execute()
            
            data_dir = project_path / 'data'
            exported = 0
            
            for user in response.data or []:
                display_name = user.get('display_name', 'unknown')
                settings = user.get('settings', {})
                
                with open(data_dir / f"{display_name}.json", 'w', encoding='utf-8') as f:
                    json.dump(settings, f, indent=2)
                
                exported += 1
                self.progress.update(f"Exported user data: {display_name}")
            
            return exported
            
        except Exception as e:
            self.warnings.append(f"Failed to export users: {str(e)}")
            return 0
    
    def _create_git_config(self, project_path: Path):
        """Create a config.json for Git backend."""
        config = {
            'backend': 'git',
            'exported_from_supabase': True,
            'exported_at': datetime.now().isoformat()
        }
        
        with open(project_path / 'config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        self.progress.update("Created project config")


def migrate_git_to_supabase(
    project_name: str,
    supabase_url: str,
    supabase_key: str,
    user_id: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> MigrationResult:
    """
    Convenience function to migrate a Git project to Supabase.
    
    Args:
        project_name: Name of the local project in db/
        supabase_url: Supabase project URL
        supabase_key: Supabase anon or service key
        user_id: UUID of the user performing the migration
        progress_callback: Optional callback(message, current, total)
    
    Returns:
        MigrationResult with success status and counts
    """
    progress = MigrationProgress(progress_callback)
    migrator = GitToSupabaseMigrator(project_name, supabase_url, supabase_key, user_id, progress)
    return migrator.migrate()


def migrate_supabase_to_git(
    project_id: str,
    supabase_url: str,
    supabase_key: str,
    target_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> MigrationResult:
    """
    Convenience function to export a Supabase project to local Git files.
    
    Args:
        project_id: UUID of the Supabase project
        supabase_url: Supabase project URL
        supabase_key: Supabase anon or service key
        target_name: Optional local project name (defaults to Supabase project name)
        progress_callback: Optional callback(message, current, total)
    
    Returns:
        MigrationResult with success status and counts
    """
    progress = MigrationProgress(progress_callback)
    migrator = SupabaseToGitMigrator(project_id, supabase_url, supabase_key, target_name, progress)
    return migrator.migrate()
