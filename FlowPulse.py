"""FlowPulse - Entry point wrapper for Nuitka compilation."""

import os
import sys

# Ensure the package directory is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowpulse.app import main

if __name__ == "__main__":
    sys.exit(main())
