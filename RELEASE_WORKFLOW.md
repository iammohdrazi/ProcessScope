# ProcessScope Release Workflow - Implementation Summary

## Overview

I've created a comprehensive GitHub Actions workflow for automated release builds with multi-distribution testing. The workflow ensures that your release builds are tested across multiple Linux distributions before being released.

## What Was Created

### 1. GitHub Actions Workflow (`.github/workflows/release.yml`)

A complete workflow that:

- **Manual Trigger**: Can be run manually with a click from the GitHub Actions tab
- **Version Management**: Automatically bumps version (patch/minor/major) with each run
- **Build Process**: Creates release packages using your existing Makefile system
- **Multi-Distribution Testing**: Tests installation across 8 Linux distributions:
  - Ubuntu 22.04 & 24.04
  - Debian 11 & 12
  - RHEL 8 & 9
  - Fedora 39
  - SLES 15
- **Installation Testing**: Runs comprehensive install/uninstall cycles on each distribution
- **Release Creation**: Automatically creates GitHub releases with artifacts if all tests pass

### 2. Helper Scripts (`scripts/`)

#### `bump_version.py`
- Automatically bumps versions in `pyproject.toml`, `dist/install.sh`, and `README.md`
- Supports semantic versioning (major, minor, patch)
- Usage: `python scripts/bump_version.py --type <major|minor|patch>`

#### `get_version.py`
- Retrieves current version from `pyproject.toml`
- Used by the workflow to track version changes

#### `test_install.sh`
- Comprehensive installation test script
- Verifies binary installation, version reporting, systemd integration, directory structure
- Runs inside each test container to validate installation

### 3. Documentation Updates

- **Updated `README.md`**: Added release workflow documentation
- **Created `scripts/README.md`**: Detailed documentation for the workflow and scripts
- **Created `RELEASE_WORKFLOW.md`**: This summary document

### 4. Build System Updates

- **Updated `Makefile`**: Added VERSION environment variable support
- **Updated `build.sh`**: Added VERSION environment variable support
- **Updated `dist/install.sh`**: Added VERSION environment variable support

## How to Use

### Creating a Release

1. Navigate to your repository on GitHub
2. Go to the **Actions** tab
3. Select **ProcessScope Release Build** workflow
4. Click **Run workflow**
5. Choose the version bump type:
   - **patch**: Bug fixes and minor improvements (0.1.0 → 0.1.1)
   - **minor**: New features, backward compatible (0.1.0 → 0.2.0)
   - **major**: Breaking changes (0.1.0 → 1.0.0)
6. Choose whether to create a GitHub release (enabled by default)
7. Click **Run workflow**

### Workflow Stages

1. **Version Bump**: Automatically increments version in all relevant files
2. **Build**: Creates release packages using `make build` and `make package-tar`
3. **Multi-Distribution Testing**: Tests installation across 8 Linux distributions
4. **Release Creation**: Creates GitHub release with artifacts if all tests pass

### Testing Strategy

For each Linux distribution, the workflow:

1. Spins up a Docker container with the target OS
2. Installs required dependencies (Python, systemd, etc.)
3. Copies the release package into the container
4. Extracts and runs the installation script
5. Verifies installation using `test_install.sh`
6. Tests basic functionality
7. Uninstalls using the appropriate package manager
8. Verifies cleanup

### Version Management

- Version is stored in `pyproject.toml` (source of truth)
- Each workflow run automatically increments the version
- Git commit is created with the version bump
- Build number includes timestamp and git SHA (format: `YYYYMMDD.HHMMSS.gitsha`)
- Release tags follow semantic versioning (v1.2.3)

### Artifacts

- **Build Artifacts**: Retained for 7 days
  - `processscope-{version}-linux-x86_64.tar.gz`
- **Release Artifacts**: Attached to GitHub release
  - Downloadable tar.gz package
  - Auto-generated release notes

### Release Notes

Auto-generated release notes include:
- Version and build number
- Installation instructions
- List of tested distributions
- Test results summary

## Key Features

### ✅ Automated Version Management
- No manual version editing required
- Consistent versioning across all files
- Semantic versioning support

### ✅ Comprehensive Testing
- Tests on 8 different Linux distributions
- Full install/uninstall cycles
- Service integration verification
- Basic functionality testing

### ✅ Safe Release Process
- Release only created if all tests pass
- Failed tests prevent release creation
- Detailed test logs for debugging

### ✅ Flexible Configuration
- Choose version bump type per release
- Option to skip release creation (for testing)
- Manual trigger only (no accidental releases)

### ✅ Complete Traceability
- Build numbers include git SHA
- Release notes include test results
- Full workflow logs available

## Customization Options

### Adding More Distributions

Edit the matrix in `.github/workflows/release.yml`:

```yaml
matrix:
  distro:
    - name: arch-linux
      image: archlinux:latest
      pkg_manager: pacman
      install_cmd: pacman -Sy --noconfirm python python-pip
```

### Adjusting Test Timeout

Modify the container startup timeout:

```yaml
- name: Set up Docker
  run: |
    docker run -d --name test-container --privileged -v /sys/fs/cgroup:/sys/fs/cgroup:ro ${{ matrix.distro.image }} /usr/sbin/init
    sleep 20  # Increase timeout if needed
```

### Changing Artifact Retention

Modify the retention period:

```yaml
- name: Upload build artifacts
  uses: actions/upload-artifact@v4
  with:
    name: release-packages
    path: dist/output/*.tar.gz
    retention-days: 30  # Change from 7 to 30 days
```

## Troubleshooting

### Workflow Fails at Version Bump
- Check that `pyproject.toml` has a valid version string
- Ensure scripts directory exists and is accessible

### Build Fails
- Verify all build dependencies are installed
- Check that Node.js 18+ is available
- Review Makefile build output

### Container Tests Fail
- Check Docker container logs in workflow output
- Verify systemd is available in the container image
- Review test_install.sh output for specific failures

### Release Not Created
- Ensure "create_release" checkbox is enabled
- Verify all tests passed successfully
- Check that GitHub token has necessary permissions

## Local Testing

To test the workflow components locally:

```bash
# Test version bump
python scripts/bump_version.py --type patch
python scripts/get_version.py

# Build package
VERSION=0.1.1 make clean
VERSION=0.1.1 make build
VERSION=0.1.1 make package-tar

# Test installation in container
docker run -it --privileged ubuntu:22.04
# Inside container:
apt-get update && apt-get install -y python3 python3-venv python3-pip systemd
# Copy package and run install.sh
./scripts/test_install.sh
```

## Next Steps

1. **Push to GitHub**: Commit and push all changes to your repository
2. **Enable Actions**: Ensure GitHub Actions is enabled for your repository
3. **Test Run**: Run the workflow once without release creation to test
4. **First Release**: Create your first automated release
5. **Monitor**: Review workflow runs and adjust as needed

## Files Modified/Created

### Created:
- `.github/workflows/release.yml` - Main workflow file
- `scripts/bump_version.py` - Version bumping script
- `scripts/get_version.py` - Version retrieval script
- `scripts/test_install.sh` - Installation test script
- `scripts/README.md` - Scripts documentation
- `RELEASE_WORKFLOW.md` - This summary

### Modified:
- `README.md` - Added release workflow section
- `Makefile` - Added VERSION environment variable support
- `build.sh` - Added VERSION environment variable support
- `dist/install.sh` - Added VERSION environment variable support

## Security Considerations

- Workflow uses GitHub's default `GITHUB_TOKEN` (no additional secrets needed)
- No credentials are exposed in logs
- Package manager operations run in isolated containers
- Service operations require appropriate permissions (handled by containers)

## Support

For issues or questions:
1. Check workflow logs in GitHub Actions
2. Review this documentation
3. Examine script output in failed runs
4. Test components locally as described above

---

**This workflow provides a complete, automated release pipeline with comprehensive testing across multiple Linux distributions, ensuring your releases are reliable and thoroughly tested.**
