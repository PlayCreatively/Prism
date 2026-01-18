# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PRISM.

This builds the application as a one-folder distribution (not one-file)
which is required for NiceGUI's web assets to work correctly.

External folders (db/, prompts/) are NOT bundled - they should be copied
alongside the executable for user customization.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Get the project root
project_root = Path(SPECPATH)

# Collect NiceGUI resources upfront
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all('nicegui')

a = Analysis(
    ['app.py'],
    pathex=[str(project_root / 'src')],
    binaries=nicegui_binaries,
    datas=nicegui_datas,
    hiddenimports=[
        # NiceGUI and its dependencies
        'nicegui',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'fastapi',
        'httptools',
        'websockets',
        'watchfiles',
        # OpenAI
        'openai',
        'httpx',
        'httpcore',
        # Graph
        'networkx',
        # Other
        'dotenv',
        'multiprocessing',
        # Source modules
        'src',
        'src.data_manager',
        'src.drill_engine',
        'src.ai_agent',
        'src.drill_workflow',
        'src.review_workflow',
        'src.git_manager',
        'src.graph_viz',
        'src.utils',
        'src.ui_common',
        'src.edit',
        'src.chart_builder',
        'src.project_manager',
        'src.paths',
        'src.config',
        'src.graph',
        'src.prism',
        'src.prism_core',
        'src.core',
        'src.conversion',
        'src.mutation_manager',
        'src.ui_components',
    ] + nicegui_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PRISM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one, e.g., 'assets/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PRISM',
)
