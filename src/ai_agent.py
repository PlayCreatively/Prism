import os
import json
import traceback
from openai import OpenAI

from src.paths import get_prompts_dir


class AIAgent:
    def __init__(self, prompts_dir=None):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.prompts_dir = prompts_dir or str(get_prompts_dir())

    def _load_prompt(self, filename):
        path = os.path.join(self.prompts_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def generate_drill_candidates(self, label, metadata, approved_children, rejected_children=None, description="", temperature=1.0):
        try:
            template = self._load_prompt('drill_down.md')
            prompt = template.format(
                label=label,
                description=description or "No description provided.",
                metadata=metadata or "No context provided.",
                approved_children=", ".join(approved_children) if approved_children else "None",
                rejected_children=", ".join(rejected_children) if rejected_children else "None"
            )

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
            
            # Check if we got a valid response
            if not response.choices:
                raise ValueError("OpenAI returned empty choices")
            
            content = response.choices[0].message.content
            print(f"[AI] Received response: {content[:200]}..." if len(content) > 200 else f"[AI] Received response: {content}")
            
            if not content:
                raise ValueError("OpenAI returned empty content")
            
            data = json.loads(content)
            
            # Handle both old format (list of strings) and new format (list of objects)
            candidates = data.get("candidates", [])
            
            if not candidates:
                print(f"[AI] Warning: No candidates in response. Full response: {data}")
                return []
            
            if candidates and isinstance(candidates[0], str):
                # Old format: convert to new format
                return [{"label": c, "description": ""} for c in candidates]
            
            print(f"[AI] Successfully parsed {len(candidates)} candidates")
            return candidates
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse AI response as JSON: {e}"
            print(f"[AI] {error_msg}")
            print(f"[AI] Raw content: {content if 'content' in dir() else 'N/A'}")
            traceback.print_exc()
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"AI Generation Error: {type(e).__name__}: {e}"
            print(f"[AI] {error_msg}")
            traceback.print_exc()
            raise
