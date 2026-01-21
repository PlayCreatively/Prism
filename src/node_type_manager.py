"""
Node Type Manager for PRISM.

Handles loading, validation, and caching of custom node type definitions.
Each node type is defined by a folder in node_types/ containing:
  - definition.json: Custom field definitions
  - *.md: Prompt files (become action buttons)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import re
import yaml

from src.paths import get_app_dir

logger = logging.getLogger(__name__)

# Reserved keys that cannot be used as custom field keys
RESERVED_KEYS = frozenset(['id', 'parent_id', 'node_type', 'label', 'description', 'metadata'])

# Valid semantic field types
VALID_FIELD_TYPES = frozenset(['text', 'tag', 'user'])


class NodeTypeManager:
    """
    Manages node type definitions.
    
    Responsibilities:
    - Load type definitions from node_types/{type}/definition.json
    - Validate definitions against schema rules
    - Cache loaded types for performance
    - Discover prompt files for each type
    - Generate output schemas for AI prompts
    """
    
    def __init__(self, node_types_dir: Path = None):
        self.node_types_dir = node_types_dir or (get_app_dir() / "node_types")
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._prompts_cache: Dict[str, List[Dict[str, Any]]] = {}
        
    def _ensure_dir(self):
        """Ensure node_types directory exists."""
        self.node_types_dir.mkdir(parents=True, exist_ok=True)
        
    def list_types(self) -> List[str]:
        """Return list of available node type names."""
        self._ensure_dir()
        types = []
        for item in self.node_types_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                types.append(item.name)
        return sorted(types)
    
    def get_type_display_name(self, type_name: str) -> str:
        """Convert type identifier to display name (e.g., 'game_mechanic' -> 'Game Mechanic')."""
        return type_name.replace('_', ' ').title()
    
    def _validate_field(self, field: Dict[str, Any], index: int) -> List[str]:
        """Validate a single field definition. Returns list of error messages."""
        errors = []
        
        # Required: key
        if 'key' not in field:
            errors.append(f"Field {index}: missing required 'key' property")
            return errors  # Can't continue without key
        
        key = field['key']
        
        # Key format: lowercase, underscores, starts with letter
        if not re.match(r'^[a-z][a-z0-9_]*$', key):
            errors.append(f"Field '{key}': key must be lowercase, start with letter, use only a-z, 0-9, _")
        
        # Reserved keys
        if key in RESERVED_KEYS:
            errors.append(f"Field '{key}': key is reserved (cannot use: {', '.join(RESERVED_KEYS)})")
        
        # Required: type
        if 'type' not in field:
            errors.append(f"Field '{key}': missing required 'type' property")
        elif field['type'] not in VALID_FIELD_TYPES:
            errors.append(f"Field '{key}': invalid type '{field['type']}' (must be: {', '.join(VALID_FIELD_TYPES)})")
        
        # Type-specific validation
        field_type = field.get('type')
        
        if field_type == 'tag':
            if 'selection' in field:
                if not isinstance(field['selection'], list):
                    errors.append(f"Field '{key}': 'selection' must be an array")
                elif not all(isinstance(s, str) for s in field['selection']):
                    errors.append(f"Field '{key}': 'selection' must contain only strings")
        
        if field_type == 'text':
            if 'multiline' in field and not isinstance(field['multiline'], bool):
                errors.append(f"Field '{key}': 'multiline' must be a boolean")
        
        return errors
    
    def _validate_definition(self, definition: Dict[str, Any], type_name: str) -> List[str]:
        """Validate a type definition. Returns list of error messages."""
        errors = []
        
        if not isinstance(definition, dict):
            return [f"Type '{type_name}': definition must be a JSON object"]
        
        if 'fields' not in definition:
            errors.append(f"Type '{type_name}': missing required 'fields' array")
            return errors
        
        if not isinstance(definition['fields'], list):
            errors.append(f"Type '{type_name}': 'fields' must be an array")
            return errors
        
        # Validate each field
        seen_keys = set()
        for i, field in enumerate(definition['fields']):
            if not isinstance(field, dict):
                errors.append(f"Type '{type_name}': field {i} must be an object")
                continue
            
            field_errors = self._validate_field(field, i)
            errors.extend(field_errors)
            
            # Check for duplicate keys
            key = field.get('key')
            if key:
                if key in seen_keys:
                    errors.append(f"Type '{type_name}': duplicate field key '{key}'")
                seen_keys.add(key)
        
        return errors
    
    def load_type(self, type_name: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Load a node type definition.
        
        Returns dict with:
          - name: type identifier
          - display_name: human-readable name
          - fields: list of custom field definitions
          - validation_errors: list of any errors found
        
        Returns None if type doesn't exist.
        """
        if use_cache and type_name in self._cache:
            return self._cache[type_name]
        
        type_dir = self.node_types_dir / type_name
        if not type_dir.is_dir():
            return None
        
        definition_path = type_dir / "definition.json"
        
        # Default empty definition
        definition = {"fields": []}
        validation_errors = []
        
        if definition_path.exists():
            try:
                with open(definition_path, 'r', encoding='utf-8') as f:
                    definition = json.load(f)
            except json.JSONDecodeError as e:
                validation_errors.append(f"Invalid JSON in definition.json: {e}")
            except Exception as e:
                validation_errors.append(f"Failed to load definition.json: {e}")
        
        # Validate
        validation_errors.extend(self._validate_definition(definition, type_name))
        
        result = {
            'name': type_name,
            'display_name': self.get_type_display_name(type_name),
            'fields': definition.get('fields', []),
            'validation_errors': validation_errors
        }
        
        if use_cache:
            self._cache[type_name] = result
        
        return result
    
    def get_type_fields(self, type_name: str) -> List[Dict[str, Any]]:
        """Get custom fields for a node type. Returns empty list if type not found."""
        type_def = self.load_type(type_name)
        if type_def:
            return type_def.get('fields', [])
        return []
    
    def load_prompts(self, type_name: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Load all prompt definitions for a node type.
        
        Returns list of dicts with:
          - filename: the .md file name
          - name: button label (from YAML frontmatter)
          - description: tooltip (from YAML frontmatter)
          - material_logo: icon name (from YAML frontmatter)
          - produces_type: what node type this prompt creates
          - content: the prompt body (after frontmatter)
        """
        if use_cache and type_name in self._prompts_cache:
            return self._prompts_cache[type_name]
        
        type_dir = self.node_types_dir / type_name
        if not type_dir.is_dir():
            return []
        
        prompts = []
        
        for md_file in sorted(type_dir.glob("*.md")):
            try:
                prompt_data = self._parse_prompt_file(md_file, type_name)
                if prompt_data:
                    prompts.append(prompt_data)
            except Exception as e:
                logger.warning(f"Failed to parse prompt file {md_file}: {e}")
        
        if use_cache:
            self._prompts_cache[type_name] = prompts
        
        return prompts
    
    def _parse_prompt_file(self, path: Path, type_name: str) -> Optional[Dict[str, Any]]:
        """Parse a prompt markdown file with YAML frontmatter."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse YAML frontmatter (between --- markers)
        frontmatter = {}
        body = content
        
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError as e:
                    logger.warning(f"Invalid YAML in {path}: {e}")
                body = parts[2].strip()
        
        # Extract frontmatter properties
        name = frontmatter.get('name', path.stem.replace('_', ' ').title())
        
        return {
            'filename': path.name,
            'path': str(path),
            'name': name,
            'description': frontmatter.get('description', ''),
            'material_logo': frontmatter.get('material-logo', 'smart_toy'),
            'produces_type': frontmatter.get('produces_type', type_name),
            'content': body
        }
    
    def generate_output_schema(self, type_name: str) -> str:
        """
        Generate a JSON schema string for AI to follow when creating nodes of this type.
        
        Includes base fields (label, description) plus custom fields from the type definition.
        """
        type_def = self.load_type(type_name)
        fields = type_def.get('fields', []) if type_def else []
        
        # Build schema object
        candidate_schema = {
            "label": "string",
            "description": "string"
        }
        
        for field in fields:
            key = field.get('key')
            field_type = field.get('type')
            
            if not key or not field_type:
                continue
            
            if field_type == 'text':
                candidate_schema[key] = "string"
            
            elif field_type == 'tag':
                selection = field.get('selection')
                multiple = field.get('multiple', True)
                
                if selection:
                    # Enum type
                    options = ' | '.join(selection)
                    if multiple:
                        candidate_schema[key] = f"[{options}]"
                    else:
                        candidate_schema[key] = options
                else:
                    # Free-form tags
                    candidate_schema[key] = '["string", "..."]'
            
            elif field_type == 'user':
                multiple = field.get('multiple', False)
                if multiple:
                    candidate_schema[key] = '["user_id", "..."]'
                else:
                    candidate_schema[key] = "user_id"
        
        # Build full schema with candidates wrapper
        schema = {
            "candidates": [candidate_schema]
        }
        
        return json.dumps(schema, indent=2)
    
    def validate_node_data(self, node_data: Dict[str, Any], type_name: str) -> Dict[str, Any]:
        """
        Validate node data against its type definition.
        
        Returns dict with:
          - valid: bool
          - errors: list of error messages (block save)
          - warnings: list of warning messages (allow save)
        """
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        type_def = self.load_type(type_name)
        if not type_def:
            result['warnings'].append(f"Unknown node type: {type_name}")
            return result
        
        fields = type_def.get('fields', [])
        
        for field in fields:
            key = field.get('key')
            field_type = field.get('type')
            required = field.get('required', False)
            label = field.get('label', key)
            
            value = node_data.get(key)
            
            # Check required fields
            if required and (value is None or value == '' or value == []):
                result['errors'].append(f"Field '{label}' is required")
                result['valid'] = False
                continue
            
            # Skip validation if no value
            if value is None or value == '' or value == []:
                if not required:
                    result['warnings'].append(f"Field '{label}' is empty")
                continue
            
            # Type-specific validation
            if field_type == 'tag':
                selection = field.get('selection')
                if selection:
                    # Validate enum values
                    values = value if isinstance(value, list) else [value]
                    for v in values:
                        if v not in selection:
                            result['errors'].append(f"Invalid value '{v}' for field '{label}' (must be one of: {', '.join(selection)})")
                            result['valid'] = False
        
        return result
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        self._prompts_cache.clear()
    
    def clear_prompts_cache(self, type_name: Optional[str] = None):
        """Clear prompts cache for a specific type or all types."""
        if type_name:
            self._prompts_cache.pop(type_name, None)
        else:
            self._prompts_cache.clear()
    
    def save_prompt(
        self, 
        type_name: str, 
        name: str, 
        description: str, 
        icon: str, 
        produces_type: str, 
        body: str,
        existing_filename: Optional[str] = None
    ) -> str:
        """
        Save a prompt file (create or update).
        
        Args:
            type_name: The node type folder to save in
            name: Prompt display name (for YAML frontmatter)
            description: Prompt description (for YAML frontmatter)
            icon: Material icon name (for YAML frontmatter)
            produces_type: Node type this prompt creates
            body: The prompt markdown content (without frontmatter)
            existing_filename: If updating, the current filename
        
        Returns:
            The filename of the saved prompt
        """
        type_dir = self.node_types_dir / type_name
        type_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename from name if creating new, otherwise use existing
        if existing_filename:
            filename = existing_filename
        else:
            # Convert name to snake_case filename
            filename = re.sub(r'[^\w\s-]', '', name.lower())
            filename = re.sub(r'[-\s]+', '_', filename).strip('_')
            filename = f"{filename}.md"
            
            # Ensure unique filename
            base_name = filename[:-3]  # Remove .md
            counter = 1
            while (type_dir / filename).exists():
                filename = f"{base_name}_{counter}.md"
                counter += 1
        
        # Build YAML frontmatter
        frontmatter = f"""---
name: {name}
description: {description}
material-logo: {icon}
produces_type: {produces_type}
---

"""
        
        # Combine frontmatter and body
        content = frontmatter + body.strip() + "\n"
        
        # Write file
        filepath = type_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Clear cache for this type
        self.clear_prompts_cache(type_name)
        
        return filename
    
    def delete_prompt(self, type_name: str, filename: str) -> bool:
        """
        Delete a prompt file.
        
        Args:
            type_name: The node type folder
            filename: The prompt filename to delete
        
        Returns:
            True if deleted, False if not found
        """
        filepath = self.node_types_dir / type_name / filename
        
        if filepath.exists():
            filepath.unlink()
            self.clear_prompts_cache(type_name)
            return True
        
        return False
    
    def get_prompt(self, type_name: str, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific prompt by type and filename.
        
        Returns prompt data dict or None if not found.
        """
        filepath = self.node_types_dir / type_name / filename
        
        if not filepath.exists():
            return None
        
        return self._parse_prompt_file(filepath, type_name)
    
    def get_default_prompt_template(self) -> str:
        """Get the default template for new prompts."""
        return """# Prompt Title

You are an expert helping to explore and develop ideas.

## Context
- **Label**: {label}
- **Description**: {description}
- **Team Notes**: {metadata}
- **Team Votes**: {votes}

## Existing Children
- **Approved**: {approved_children}
- **Rejected**: {rejected_children}

## Task
Generate 2-3 suggestions that expand on this concept.

## Output Format
{output_schema}
"""


# Global instance for convenience
_manager: Optional[NodeTypeManager] = None

def get_node_type_manager() -> NodeTypeManager:
    """Get the global NodeTypeManager instance."""
    global _manager
    if _manager is None:
        _manager = NodeTypeManager()
    return _manager
