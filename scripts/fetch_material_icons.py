"""Fetch Material Icons codepoints and write a JSON list of icon names.

Usage:
  python scripts/fetch_material_icons.py

This will download the codepoints file from the official Google repo,
parse icon names (first token per non-empty line) and write
`src/components/material_icons.json` containing a JSON array of icon names.
"""
from pathlib import Path
import requests
import json

RAW_URLS = [
    "https://raw.githubusercontent.com/google/material-design-icons/master/font/MaterialIcons-Regular.codepoints",
    "https://raw.githubusercontent.com/google/material-design-icons/master/iconfont/MaterialIcons-Regular.codepoints",
]
OUT_PATH = Path(__file__).resolve().parent.parent / 'src' / 'components' / 'material_icons.json'


def main():
    r = None
    for url in RAW_URLS:
        try:
            print(f"Trying {url} ...")
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                break
        except Exception:
            r = None
    if not r or r.status_code != 200:
        raise RuntimeError(f"Failed to fetch codepoints from known locations: {RAW_URLS}")
    lines = r.text.splitlines()
    icons = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        parts = ln.split()
        if len(parts) >= 1:
            icon = parts[0].strip()
            icons.append(icon)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(icons, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(icons)} icons to {OUT_PATH}")


if __name__ == '__main__':
    main()
