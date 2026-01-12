#!/usr/bin/env python3
import sys
import os

# Ensure we can find the api module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import main from api.index which now holds the logic.
# Note: api/index.py does not define 'main' (it's a FastAPI app), 
# so we need to add the CLI logic back to api/index.py or re-implement it in a separate file.
# Since I merged everything, 'main' was lost. I need to re-add 'main' to api/index.py for CLI use.
from api.index import main

if __name__ == "__main__":
    main()
