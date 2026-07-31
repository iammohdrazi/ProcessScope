"""
ProcessScope — CLI entry point.

Provides the `processscope` command with subcommands:
  - start     Start the ProcessScope agent and dashboard
  - attach    Attach to a running process
  - detach    Detach from a hooked process
  - status    Show agent and hooked process status
  - version   Print version and build information
  - config    Show or generate configuration
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from processscope.version import get_build_info
from processscope.logging.error_codes import (
    PS100, PS101, PS110, PS111, PS150, PS151,
    PS200, PS201, PS300, PS303, PS305
)

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────

def _check_linux() -> None:
    """Warn if not running on Linux."""
    if sys.platform != "linux":
        console.print(
            "[yellow]⚠ ProcessScope is designed for Linux. "
            "Some features may not work on this platform.[/yellow]"
        )


def _check_privileges() -> None:
    """Check if running with sufficient privileges."""
    if os.geteuid() != 0:
        console.print(
            "[yellow]⚠ ProcessScope requires root privileges for process attachment. "
            "Run with sudo or as root.[/yellow]"
        )


# ── Main CLI Group ────────────────────────────────────────────────────

def _get_display_host(host: str) -> str:
    """Resolve 0.0.0.0 to the primary IP address for display."""
    if host == "0.0.0.0":
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"
    return host

@click.group(invoke_without_command=True, context_settings=dict(help_option_names=['-h', '--help']))
@click.option("--config", "-c", "config_path", type=click.Path(), default=None,
              help="Path to configuration file.")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Enable verbose (DEBUG) logging.")
@click.pass_context
def main(ctx: click.Context, config_path: str | None, verbose: bool) -> None:
    """ProcessScope — Linux Process Observability Platform.

    Attach, inspect, and analyze any running Linux process in real time.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── Start Command ─────────────────────────────────────────────────────

@main.command()
@click.option("--host", "-h", default=None, help="Dashboard host (default: 0.0.0.0).")
@click.option("--port", "-p", default=None, type=int, help="Dashboard port (default: 9876).")
@click.option("--dev", is_flag=True, default=False, help="Run in development mode.")
@click.option("--no-dashboard", is_flag=True, default=False, help="Disable web dashboard.")
@click.pass_context
def start(ctx: click.Context, host: str | None, port: int | None,
          dev: bool, no_dashboard: bool) -> None:
    """Start the ProcessScope agent and web dashboard."""
    from processscope.config import load_config
    from processscope.logging import setup_logging, get_logger

    # Load configuration
    config = load_config(ctx.obj.get("config_path"))
    if dev:
        config.dev_mode = True
    if host:
        config.server.host = host
    if port:
        config.server.port = port
    if ctx.obj.get("verbose"):
        config.logging.level = "DEBUG"

    # Initialize dual logging
    setup_logging(config.logging, dev_mode=config.dev_mode)
    logger = get_logger("main")

    build_info = get_build_info()

    # Print simple plain-text startup banner
    print(f"ProcessScope v{build_info.version} (build: {build_info.build_number})")
    print(f"Dashboard:  http://{_get_display_host(config.server.host)}:{config.server.port}")
    print(f"API:        http://{_get_display_host(config.server.host)}:{config.server.port}/api/v1")
    print(f"Mode:       {'Development' if config.dev_mode else 'Production'}")
    print(f"Log File:   {config.logging.file_path}/processscope.log")
    print(f"Syslog:     {'Enabled' if config.logging.syslog_enabled else 'Disabled'}")
    print()

    # Log startup to both syslog and file
    logger.info(
        PS100,
        version=build_info.version,
        build=build_info.build_number,
        host=config.server.host,
        port=config.server.port,
        dev_mode=config.dev_mode,
    )

    # Register signal handlers
    def _shutdown_handler(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(PS101, signal=sig_name)
        print(f"\nReceived {sig_name}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    # Start the application
    try:
        from processscope.api.server import run_server
        run_server(config, serve_dashboard=not no_dashboard)
    except Exception as e:
        logger.error(PS300, error=str(e), exc_info=True)
        print(f"✗ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


# ── Attach Command ────────────────────────────────────────────────────

@main.command()
@click.option("--pid", "-p", type=int, default=None, help="Process ID to attach to.")
@click.option("--name", "-n", type=str, default=None, help="Process name to attach to.")
@click.option("--children", is_flag=True, default=False, help="Also attach to child processes.")
@click.option("--read-only", is_flag=True, default=False, help="Attach in read-only mode.")
@click.pass_context
def attach(ctx: click.Context, pid: int | None, name: str | None,
           children: bool, read_only: bool) -> None:
    """Attach to a running process for observation."""
    if not pid and not name:
        print("✗ Specify either --pid or --name", file=sys.stderr)
        sys.exit(1)

    _check_linux()
    _check_privileges()

    # In a running service, this sends a command to the agent via HTTP API.
    # For standalone usage, it triggers attachment directly.
    import httpx

    config_path = ctx.obj.get("config_path")

    from processscope.config import load_config
    config = load_config(config_path)

    api_url = f"http://{config.server.host}:{config.server.port}/api/v1/processes/attach"
    payload = {
        "pid": pid,
        "name": name,
        "include_children": children,
        "read_only": read_only,
    }

    try:
        resp = httpx.post(api_url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ Attached to process {data.get('pid', pid or name)}")
            print(f"  Dashboard: http://{_get_display_host(config.server.host)}:{config.server.port}")
        else:
            print(f"✗ Failed to attach: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except httpx.ConnectError:
        print("✗ ProcessScope agent is not running. Start it with: processscope start", file=sys.stderr)
        sys.exit(1)


# ── Detach Command ────────────────────────────────────────────────────

@main.command()
@click.option("--pid", "-p", type=int, required=True, help="Process ID to detach from.")
@click.pass_context
def detach(ctx: click.Context, pid: int) -> None:
    """Detach from a hooked process."""
    import httpx

    from processscope.config import load_config
    config = load_config(ctx.obj.get("config_path"))

    api_url = f"http://{config.server.host}:{config.server.port}/api/v1/processes/{pid}"

    try:
        resp = httpx.delete(api_url, timeout=10.0)
        if resp.status_code == 200:
            print(f"✓ Detached from process {pid}")
        else:
            print(f"✗ Failed to detach: {resp.text}", file=sys.stderr)
            sys.exit(1)
    except httpx.ConnectError:
        print("✗ ProcessScope agent is not running.", file=sys.stderr)
        sys.exit(1)


# ── Status Command ────────────────────────────────────────────────────

@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show ProcessScope agent and hooked process status."""
    import httpx

    from processscope.config import load_config
    config = load_config(ctx.obj.get("config_path"))

    api_url = f"http://{config.server.host}:{config.server.port}/api/v1/status"

    try:
        resp = httpx.get(api_url, timeout=5.0)
        data = resp.json()
        print("ProcessScope Status")
        print("━━━━━━━━━━━━━━━━━━━")
        print(f"Status:           {data.get('status', 'unknown')}")
        print(f"Version:          {data.get('version', '?')}")
        print(f"Build:            {data.get('build_number', '?')}")
        print(f"Uptime:           {data.get('uptime', '?')}")
        print(f"Hooked Processes: {data.get('hooked_count', 0)}")
        print(f"Dashboard:        http://{_get_display_host(config.server.host)}:{config.server.port}")

        processes = data.get("hooked_processes", [])
        if processes:
            print("\nHooked Processes")
            print("━━━━━━━━━━━━━━━━")
            print(f"{'PID':<8} {'Name':<20} {'State':<15} {'CPU %':<8} {'Memory':<10}")
            print("-" * 65)
            for proc in processes:
                print(f"{proc.get('pid'):<8} {proc.get('name', '?')[:19]:<20} {proc.get('state', '?'):<15} {proc.get('cpu_percent', 0):<8.1f} {proc.get('memory_human', '?'):<10}")

    except httpx.ConnectError:
        print("✗ ProcessScope agent is not running.", file=sys.stderr)
        print("  Start it with: sudo processscope start", file=sys.stderr)
        sys.exit(1)


# ── Version Command ───────────────────────────────────────────────────

@main.command()
def version() -> None:
    """Print version and build information."""
    build_info = get_build_info()
    print(build_info.format_banner())


# ── Config Command ────────────────────────────────────────────────────

@main.command()
@click.option("--generate", "-g", is_flag=True, help="Generate default config file.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output path for generated config.")
@click.pass_context
def config(ctx: click.Context, generate: bool, output: str | None) -> None:
    """Show current or generate default configuration."""
    from processscope.config import load_config, write_default_config

    if generate:
        out_path = Path(output) if output else Path("processscope.yaml")
        write_default_config(out_path)
        print(f"✓ Default config written to {out_path}")
    else:
        cfg = load_config(ctx.obj.get("config_path"))
        import yaml
        print(yaml.dump(cfg.model_dump(), default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
