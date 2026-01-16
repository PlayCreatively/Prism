import os
import json
from openai import OpenAI

class AIAgent:
    def __init__(self, prompts_dir="prompts"):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.prompts_dir = prompts_dir

    def _load_prompt(self, filename):
        path = os.path.join(self.prompts_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def generate_drill_candidates(self, label, metadata, approved_children, rejected_children=None, temperature=1.0):
        try:
            template = self._load_prompt('drill_down.md')
            prompt = template.format(
                label=label,
                metadata=metadata or "No context provided.",
                approved_children=", ".join(approved_children) if approved_children else "None",
                rejected_children=", ".join(rejected_children) if rejected_children else "None"
            )

            response = self.client.chat.completions.create(
                model="gpt-4o",
                temperature=temperature,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant emitting JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return data.get("candidates", [])
        except Exception as e:
            print(f"AI Generation Error: {e}")
            return []
