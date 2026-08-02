#!/usr/bin/env python3
"""
Version bump script for ProcessScope.
Updates the version in pyproject.toml based on the specified bump type.
"""

import sys
import re
from pathlib import Path


def bump_version(version_str, bump_type):
    """
    Bump version string based on type (major, minor, patch).
    
    Args:
        version_str: Current version string (e.g., "0.1.0")
        bump_type: Type of bump ("major", "minor", or "patch")
    
    Returns:
        New version string
    """
    # Parse version string
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    
    major, minor, patch = map(int, match.groups())
    
    # Bump the appropriate component
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return f"{major}.{minor}.{patch}"


def main():
    if len(sys.argv) != 3:
        print("Usage: bump_version.py --type <major|minor|patch>")
        sys.exit(1)
    
    bump_type = sys.argv[2]
    if bump_type not in ["major", "minor", "patch"]:
        print("Error: bump_type must be major, minor, or patch")
        sys.exit(1)
    
    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        sys.exit(1)
    
    with open(pyproject_path, 'r') as f:
        content = f.read()
    
    # Extract current version
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        print("Error: Could not find version in pyproject.toml")
        sys.exit(1)
    
    current_version = match.group(1)
    new_version = bump_version(current_version, bump_type)
    
    # Update version in pyproject.toml
    updated_content = re.sub(
        r'^version\s*=\s*["\']([^"\']+)["\']',
        f'version = "{new_version}"',
        content,
        flags=re.MULTILINE
    )
    
    # Write back to pyproject.toml
    with open(pyproject_path, 'w') as f:
        f.write(updated_content)
    
    # Update version in install.sh
    install_sh_path = Path(__file__).parent.parent / "dist" / "install.sh"
    if install_sh_path.exists():
        with open(install_sh_path, 'r') as f:
            install_content = f.read()
        
        updated_install = re.sub(
            r'VERSION="[^"]*"',
            f'VERSION="{new_version}"',
            install_content
        )
        
        with open(install_sh_path, 'w') as f:
            f.write(updated_install)
    
    print(f"Updated install.sh version to {new_version}")
    
    # Update version in README.md
    readme_path = Path(__file__).parent.parent / "README.md"
    if readme_path.exists():
        with open(readme_path, 'r') as f:
            readme_content = f.read()
        
        updated_readme = re.sub(
            r'\[!\[Version\]\([^)]*\)\]\(\)',
            f'[![Version](https://img.shields.io/badge/version-{new_version}-blue.svg)]()',
            readme_content
        )
        
        with open(readme_path, 'w') as f:
            f.write(updated_readme)
        
        print(f"Updated README.md version to {new_version}")
    
    print(f"Bumped version from {current_version} to {new_version}")


if __name__ == "__main__":
    main()
