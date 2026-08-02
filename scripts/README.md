# ProcessScope Release Workflow Scripts

This directory contains helper scripts for the GitHub Actions release workflow.

## Scripts

### bump_version.py
Automatically bumps the version in `pyproject.toml` based on the specified type.

**Usage:**
```bash
python scripts/bump_version.py --type <major|minor|patch>
```

**Examples:**
```bash
# Bump patch version (0.1.0 -> 0.1.1)
python scripts/bump_version.py --type patch

# Bump minor version (0.1.0 -> 0.2.0)
python scripts/bump_version.py --type minor

# Bump major version (0.1.0 -> 1.0.0)
python scripts/bump_version.py --type major
```

### get_version.py
Retrieves the current version from `pyproject.toml`.

**Usage:**
```bash
python scripts/get_version.py
```

**Output:**
```
0.1.0
```

### test_install.sh
Comprehensive installation test script that verifies:
- Binary installation
- Version reporting
- Systemd service configuration
- Service enablement and activation
- Directory structure
- Python virtual environment
- Basic CLI functionality

**Note**: The uninstall script in `dist/install.sh` has been updated to avoid `getcwd() failed` errors by changing to a safe directory (/tmp) before executing removal commands.

**Usage:**
```bash
# Run inside a container after installation
./scripts/test_install.sh
```

## GitHub Actions Workflow

The main workflow is defined in `.github/workflows/release.yml`.

### How to Use

1. Go to the **Actions** tab in your GitHub repository
2. Select **ProcessScope Release Build** workflow
3. Click **Run workflow**
4. Choose the version bump type:
   - **patch**: Bug fixes and minor improvements (0.1.0 -> 0.1.1)
   - **minor**: New features, backward compatible (0.1.0 -> 0.2.0)
   - **major**: Breaking changes (0.1.0 -> 1.0.0)
5. Choose whether to create a GitHub release (enabled by default)
6. Click **Run workflow**

### What Happens

1. **Version Bump**: The version in `pyproject.toml` is automatically incremented
2. **Build**: Packages are built using the Makefile build system
3. **Multi-Distro Testing**: The package is tested across 8 Linux distributions:
   - Ubuntu 22.04 & 24.04
   - Debian 11 & 12
   - RHEL 8 & 9
   - Fedora 39
   - SLES 15
4. **Installation Test**: Each distribution runs a full install/uninstall cycle
5. **Release Creation**: If all tests pass and release is enabled, a GitHub release is created

### Testing Matrix

Each distribution test includes:
- Package extraction
- Installation via `install.sh`
- Binary verification
- Service status checks
- Basic functionality tests
- Uninstallation via package manager
- Cleanup verification

### Version Management

- Version is stored in `pyproject.toml`
- Each workflow run increments the version
- Git commit is automatically created with the version bump
- Build number includes timestamp and git SHA
- Release tags follow semantic versioning (v1.2.3)

### Artifacts

Build artifacts are retained for 7 days:
- `processscope-{version}-linux-x86_64.tar.gz`

### Release Notes

Auto-generated release notes include:
- Version and build number
- Installation instructions
- List of tested distributions
- Test results summary

## Manual Testing

To test the workflow locally:

```bash
# Test version bump
python scripts/bump_version.py --type patch

# Check new version
python scripts/get_version.py

# Build package
make clean
make build
make package-tar

# Test installation (in a container)
docker run -it --privileged ubuntu:22.04
# Inside container:
# apt-get update && apt-get install -y python3 python3-venv python3-pip systemd
# copy package and run install.sh
# ./scripts/test_install.sh
```
