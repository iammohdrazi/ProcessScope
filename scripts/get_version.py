#!/usr/bin/env python3
"""
Get current version from pyproject.toml.
"""

import sys
import re
from pathlib import Path


def main():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        sys.exit(1)
    
    with open(pyproject_path, 'r') as f:
        content = f.read()
    
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        print("Error: Could not find version in pyproject.toml")
        sys.exit(1)
    
    print(match.group(1))


if __name__ == "__main__":
    main()
