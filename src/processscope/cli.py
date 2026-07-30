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
from rich.panel import Panel
from rich.table import Table

from processscope.version import get_build_info

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

@click.group(invoke_without_command=True)
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

    # Print startup banner
    banner = Panel(
        f"[bold cyan]{build_info.display_name}[/bold cyan] v{build_info.version}\n"
        f"[dim]Build: {build_info.build_number}[/dim]\n\n"
        f"[green]Dashboard:[/green]  http://{config.server.host}:{config.server.port}\n"
        f"[green]API:[/green]        http://{config.server.host}:{config.server.port}/api/v1\n"
        f"[green]Mode:[/green]       {'Development' if config.dev_mode else 'Production'}\n"
        f"[green]Log File:[/green]   {config.logging.file_path}/processscope.log\n"
        f"[green]Syslog:[/green]     {'Enabled' if config.logging.syslog_enabled else 'Disabled'}",
        title="[bold]🔬 ProcessScope Starting[/bold]",
        border_style="cyan",
        width=64,
    )
    console.print(banner)

    # Log startup to both syslog and file
    logger.info(
        "ProcessScope starting",
        version=build_info.version,
        build=build_info.build_number,
        host=config.server.host,
        port=config.server.port,
        dev_mode=config.dev_mode,
    )

    # Register signal handlers
    def _shutdown_handler(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, shutting down gracefully...")
        console.print(f"\n[yellow]Received {sig_name}, shutting down...[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    # Start the application
    try:
        from processscope.api.server import run_server
        run_server(config, serve_dashboard=not no_dashboard)
    except Exception as e:
        logger.error("Fatal error during startup", error=str(e), exc_info=True)
        console.print(f"[red]✗ Fatal error: {e}[/red]")
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
        console.print("[red]✗ Specify either --pid or --name[/red]")
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
            console.print(f"[green]✓ Attached to process {data.get('pid', pid or name)}[/green]")
            console.print(f"  Dashboard: http://{config.server.host}:{config.server.port}")
        else:
            console.print(f"[red]✗ Failed to attach: {resp.text}[/red]")
            sys.exit(1)
    except httpx.ConnectError:
        console.print("[red]✗ ProcessScope agent is not running. Start it with: processscope start[/red]")
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
            console.print(f"[green]✓ Detached from process {pid}[/green]")
        else:
            console.print(f"[red]✗ Failed to detach: {resp.text}[/red]")
            sys.exit(1)
    except httpx.ConnectError:
        console.print("[red]✗ ProcessScope agent is not running.[/red]")
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

        table = Table(title="ProcessScope Status", border_style="cyan")
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("Status", f"[green]{data.get('status', 'unknown')}[/green]")
        table.add_row("Version", data.get("version", "?"))
        table.add_row("Build", data.get("build_number", "?"))
        table.add_row("Uptime", data.get("uptime", "?"))
        table.add_row("Hooked Processes", str(data.get("hooked_count", 0)))
        table.add_row("Dashboard", f"http://{config.server.host}:{config.server.port}")

        console.print(table)

        # Show hooked processes
        processes = data.get("hooked_processes", [])
        if processes:
            proc_table = Table(title="Hooked Processes", border_style="green")
            proc_table.add_column("PID", justify="right")
            proc_table.add_column("Name")
            proc_table.add_column("State")
            proc_table.add_column("CPU %", justify="right")
            proc_table.add_column("Memory", justify="right")

            for proc in processes:
                proc_table.add_row(
                    str(proc.get("pid")),
                    proc.get("name", "?"),
                    proc.get("state", "?"),
                    f"{proc.get('cpu_percent', 0):.1f}",
                    proc.get("memory_human", "?"),
                )
            console.print(proc_table)

    except httpx.ConnectError:
        console.print("[red]✗ ProcessScope agent is not running.[/red]")
        console.print("  Start it with: [cyan]sudo processscope start[/cyan]")
        sys.exit(1)


# ── Version Command ───────────────────────────────────────────────────

@main.command()
def version() -> None:
    """Print version and build information."""
    build_info = get_build_info()
    console.print(build_info.format_banner())


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
        console.print(f"[green]✓ Default config written to {out_path}[/green]")
    else:
        cfg = load_config(ctx.obj.get("config_path"))
        import yaml
        console.print(yaml.dump(cfg.model_dump(), default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
