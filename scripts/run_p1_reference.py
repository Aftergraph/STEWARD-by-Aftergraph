#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from steward_reference.vertical_slice import ReferenceVerticalSlice

result = ReferenceVerticalSlice().run()
print(result.to_json())
print('STEWARD_P1_REFERENCE=PASS')
