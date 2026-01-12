#!/usr/bin/env python3
import sys
import os

# Ensure we can find the api module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.editorial_tracker import main

if __name__ == "__main__":
    main()
