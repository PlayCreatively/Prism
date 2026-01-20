import os
import json
import traceback
from typing import Dict, Any, List, Optional
from openai import OpenAI

from src.node_type_manager import get_node_type_manager


class AIAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.node_type_manager = get_node_type_manager()

    def _load_prompt_for_type(self, node_type: str, prompt_filename: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific prompt from a node type's folder.
        
        Returns dict with:
          - content: The prompt body with variables
          - produces_type: What node type the output should be
          - name: Button label
        """
        prompts = self.node_type_manager.load_prompts(node_type)
        for prompt in prompts:
            if prompt['filename'] == prompt_filename:
                return prompt
        return None
    
    def _inject_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """Inject variables into prompt template, handling missing keys gracefully."""
        result = template
        for key, value in variables.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                # Format value appropriately
                if isinstance(value, list):
                    formatted = ", ".join(str(v) for v in value) if value else "None"
                elif value is None or value == "":
                    formatted = "None"
                else:
                    formatted = str(value)
                result = result.replace(placeholder, formatted)
        return result

    def generate_candidates_for_prompt(
        self,
        node_type: str,
        prompt_filename: str,
        node_data: Dict[str, Any],
        approved_children: List[str] = None,
        rejected_children: List[str] = None,
        temperature: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Generate candidates using a specific prompt from a node type.
        
        Args:
            node_type: The node type (e.g., 'default', 'game_mechanic')
            prompt_filename: The prompt file to use (e.g., 'drill_down.md')
            node_data: Full node data including custom fields
            approved_children: List of approved child labels
            rejected_children: List of rejected child labels
            temperature: AI temperature parameter
            
        Returns:
            List of candidate dicts with label, description, and custom fields
        """
        # Load the prompt
        prompt_info = self._load_prompt_for_type(node_type, prompt_filename)
        if not prompt_info:
            raise ValueError(f"Prompt '{prompt_filename}' not found for type '{node_type}'")
        
        # Get the output type and generate schema
        produces_type = prompt_info.get('produces_type', node_type)
        output_schema = self.node_type_manager.generate_output_schema(produces_type)
        
        # Build variables dict from node data
        variables = {
            'label': node_data.get('label', ''),
            'description': node_data.get('description', ''),
            'metadata': node_data.get('metadata', ''),
            'approved_children': approved_children or [],
            'rejected_children': rejected_children or [],
            'output_schema': output_schema
        }
        
        # Add any custom fields from node_data
        for key, value in node_data.items():
            if key not in variables and key not in ('id', 'parent_id', 'node_type', 'interested_users', 'rejected_users'):
                variables[key] = value
        
        # Inject variables into prompt
        prompt_content = self._inject_variables(prompt_info['content'], variables)
        
        print(f"[AI] Using prompt '{prompt_info['name']}' for type '{node_type}' -> produces '{produces_type}'")
        
        return self._call_openai(prompt_content, temperature, produces_type)
    
    def _call_openai(self, prompt: str, temperature: float, produces_type: str) -> List[Dict[str, Any]]:
        """Make the actual OpenAI API call and parse results."""
        try:
            print(f"[AI] Sending request to OpenAI...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                temperature=temperature,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant emitting JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            if not response.choices:
                raise ValueError("OpenAI returned empty choices")
            
            content = response.choices[0].message.content
            print(f"[AI] Received response: {content[:200]}..." if len(content) > 200 else f"[AI] Received response: {content}")
            
            if not content:
                raise ValueError("OpenAI returned empty content")
            
            data = json.loads(content)
            
            # Find candidates: use any root key whose value is a list, or data itself if it's a list
            candidates = None
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                # Find the first key with a list value
                for key, value in data.items():
                    if isinstance(value, list):
                        candidates = value
                        break
            
            if not candidates:
                print(f"[AI] Warning: No candidates in response. Full response: {data}")
                return []
            
            # Handle legacy format (list of strings)
            if candidates and isinstance(candidates[0], str):
                candidates = [{"label": c, "description": ""} for c in candidates]
            
            # Normalize keys to lowercase and map Label->label, Description->description
            normalized = []
            for candidate in candidates:
                norm = {}
                for k, v in candidate.items():
                    lower_key = k.lower()
                    # Map common variations
                    if lower_key in ('label', 'name', 'title'):
                        norm['label'] = v if isinstance(v, str) else str(v)
                    elif lower_key == 'description':
                        # Description might be a string or a complex object
                        if isinstance(v, str):
                            norm['description'] = v
                        elif isinstance(v, dict):
                            # Flatten dict to formatted string
                            parts = []
                            for dk, dv in v.items():
                                if isinstance(dv, dict):
                                    # Nested dict (e.g., per-user info)
                                    sub_parts = [f"  - {sk}: {sv}" for sk, sv in dv.items()]
                                    parts.append(f"**{dk}**:\n" + "\n".join(sub_parts))
                                elif isinstance(dv, list):
                                    parts.append(f"**{dk}**: {', '.join(str(x) for x in dv)}")
                                else:
                                    parts.append(f"**{dk}**: {dv}")
                            norm['description'] = "\n\n".join(parts)
                        else:
                            norm['description'] = str(v)
                    else:
                        norm[lower_key] = v
                normalized.append(norm)
            candidates = normalized
            
            # Attach the produces_type to each candidate
            for candidate in candidates:
                candidate['_produces_type'] = produces_type
            
            print(f"[AI] Successfully parsed {len(candidates)} candidates")
            return candidates
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse AI response as JSON: {e}"
            print(f"[AI] {error_msg}")
            traceback.print_exc()
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"AI Generation Error: {type(e).__name__}: {e}"
            print(f"[AI] {error_msg}")
            traceback.print_exc()
            raise

    def generate_drill_candidates(self, label, metadata, approved_children, rejected_children=None, description="", temperature=1.0, node_type: str = "default"):
        """
        Legacy method for backward compatibility.
        Now routes to generate_candidates_for_prompt.
        """
        node_data = {
            'label': label,
            'description': description,
            'metadata': metadata
        }
        
        return self.generate_candidates_for_prompt(
            node_type=node_type,
            prompt_filename='drill_down.md',
            node_data=node_data,
            approved_children=approved_children,
            rejected_children=rejected_children,
            temperature=temperature
        )
