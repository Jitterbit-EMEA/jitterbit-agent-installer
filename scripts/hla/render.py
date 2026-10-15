#!/usr/bin/env python3
"""Build and validate the current native-vector HLA PDF."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
for name in ['document.py','validate.py']:
 subprocess.run([sys.executable,str(ROOT/'scripts/hla/rebuild'/name)],cwd=ROOT,check=True)
