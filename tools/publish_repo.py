#!/usr/bin/env python3
"""(old name) Build the repository branch and push it.

Kept so old notes keep working: `tools/release_repo.py` does the work now.
    python3 tools/publish_repo.py [args]   ==   python3 tools/release_repo.py [args]
"""
import os
import runpy
import sys

sys.dont_write_bytecode = True
sys.argv[0] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release_repo.py")
runpy.run_path(sys.argv[0], run_name="__main__")
