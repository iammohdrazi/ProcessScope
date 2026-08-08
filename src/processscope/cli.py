"""
ProcessScope — CLI entry point.

Provides the `processscope` command with subcommands:
  - start     Start the ProcessScope agent and dashboard
  - attach    Attach to a running process
  - detach    Detach from a hooked process (or all)
  - status    Show agent and hooked process status
  - version   Print version and build information
  - config    Show or generate configuration
  - list      List running system processes
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from processscope.version import get_build_info
from processscope.logging.error_codes import (
    PS100, PS101, PS110, PS111,
    PS200, PS201, PS300, PS305
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


def _state_style(state: str) -> str:
    """Return a rich markup color for a process state."""
    return {
        "attached": "bright_green",
        "process_exited": "red",
        "detaching": "yellow",
        "detached": "dim",
        "attaching": "cyan",
        "error": "red bold",
    }.get(state, "white")


def _state_icon(state: str) -> str:
    """Return an icon for a process state."""
    return {
        "attached": "●",
        "process_exited": "✕",
        "detaching": "◌",
        "detached": "○",
        "attaching": "◎",
        "error": "!",
    }.get(state, "?")


# ── Main CLI Group ────────────────────────────────────────────────────

@click.group(invoke_without_command=True, context_settings=dict(help_option_names=['-h', '--help']))
@click.option("--config", "-c", "config_path", type=click.Path(), default=None,
              help=(
                  "Path to configuration file. "
                  "Defaults to /etc/processscope/processscope.yaml. "
                  "Useful for running multiple isolated ProcessScope instances."
              ))
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
@click.option("--host", "-H", default=None, help="Dashboard host (default: 0.0.0.0).")
@click.option("--port", "-p", default=None, type=int, help="Dashboard port (default: 9876).")
@click.option("--dev", is_flag=True, default=False, help="Run in development mode with verbose console logging.")
@click.option("--no-dashboard", is_flag=True, default=False, help="Disable web dashboard.")
@click.option("--debug-log", is_flag=True, default=False,
              help="Write verbose DEBUG logs to /tmp/processscope/debug.log.")
@click.pass_context
def start(ctx: click.Context, host: str | None, port: int | None,
          dev: bool, no_dashboard: bool, debug_log: bool) -> None:
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
    if debug_log:
        config.logging.debug_log_enabled = True

    # Initialize dual logging
    setup_logging(config.logging, dev_mode=config.dev_mode)
    logger = get_logger("main")

    build_info = get_build_info()
    display_host = _get_display_host(config.server.host)

    # Build the startup panel
    build_type_color = "cyan" if build_info.build_number == "local" else "bright_green"
    build_type_label = f"[{build_type_color}]{build_info.build_number}[/{build_type_color}]"

    startup_lines = [
        f"[bold white]ProcessScope[/bold white] [dim]v{build_info.version}[/dim]  {build_type_label}",
        "",
        f"  [dim]Dashboard :[/dim]  [bright_cyan]http://{display_host}:{config.server.port}[/bright_cyan]",
        f"  [dim]API Docs  :[/dim]  [cyan]http://{display_host}:{config.server.port}/api/docs[/cyan]",
        f"  [dim]Mode      :[/dim]  {'[yellow]Development[/yellow]' if config.dev_mode else '[green]Production[/green]'}",
        f"  [dim]Log File  :[/dim]  {config.logging.file_path}/processscope.log",
    ]
    if config.logging.debug_log_enabled:
        startup_lines.append(
            f"  [dim]Debug Log :[/dim]  [yellow]{config.logging.debug_log_path}/debug.log[/yellow]"
        )

    console.print(Panel(
        "\n".join(startup_lines),
        title="[bold blue]Starting[/bold blue]",
        border_style="blue",
        padding=(0, 1),
    ))

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
        console.print(f"\n[yellow]Received {sig_name}, shutting down...[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    # Start the application
    try:
        from processscope.api.server import run_server
        run_server(config, serve_dashboard=not no_dashboard)
    except Exception as e:
        logger.error(PS300, error=str(e), exc_info=True)
        console.print(f"[bold red]✗ Fatal error:[/bold red] {e}", file=sys.stderr)
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
        console.print("[bold red]✗[/bold red] Specify either [cyan]--pid[/cyan] or [cyan]--name[/cyan]")
        sys.exit(1)

    _check_linux()
    _check_privileges()

    import httpx
    from processscope.config import load_config
    config = load_config(ctx.obj.get("config_path"))

    api_url = f"http://{config.server.host}:{config.server.port}/api/v1/processes/attach"
    payload = {
        "pid": pid,
        "name": name,
        "include_children": children,
        "read_only": read_only,
    }

    with console.status("[cyan]Attaching to process...[/cyan]", spinner="dots"):
        try:
            resp = httpx.post(api_url, json=payload, timeout=10.0)
        except httpx.ConnectError:
            console.print(
                "[bold red]✗[/bold red] ProcessScope agent is not running.\n"
                "  Start it with: [cyan]processscope start[/cyan]"
            )
            sys.exit(1)

    if resp.status_code == 200:
        data = resp.json()
        display_host = _get_display_host(config.server.host)

        # Handle single or multi-process attach
        if "processes" in data:
            procs = data["processes"]
            console.print(f"[bold green]✓[/bold green] Attached to [bold]{len(procs)}[/bold] process(es):")
            for p in procs:
                console.print(f"    [bright_green]●[/bright_green] [bold]{p.get('name', '?')}[/bold] "
                               f"[dim](PID {p.get('pid')})[/dim]")
        else:
            proc_name = data.get("name") or name or str(pid)
            proc_pid = data.get("pid") or pid
            console.print(
                f"[bold green]✓[/bold green] Attached to [bold]{proc_name}[/bold] "
                f"[dim](PID {proc_pid})[/dim]"
            )
        console.print(
            f"  [dim]Dashboard:[/dim] [bright_cyan]http://{display_host}:{config.server.port}[/bright_cyan]"
        )
    elif resp.status_code == 404:
        console.print(f"[bold red]✗[/bold red] [PS200] Process not found: {resp.json().get('detail', '')}")
        sys.exit(1)
    elif resp.status_code == 403:
        console.print(f"[bold red]✗[/bold red] [PS201] Access denied: {resp.json().get('detail', '')}")
        sys.exit(1)
    elif resp.status_code == 409:
        console.print(f"[bold yellow]⚠[/bold yellow] Already attached: {resp.json().get('detail', '')}")
        sys.exit(1)
    else:
        console.print(f"[bold red]✗[/bold red] [PS305] Failed to attach: {resp.text}")
        sys.exit(1)


# ── Detach Command ────────────────────────────────────────────────────

@main.command()
@click.option("--pid", "-p", type=int, default=None, help="Process ID to detach from.")
@click.option("--all", "-a", "detach_all", is_flag=True, default=False,
              help="Detach from all hooked processes.")
@click.pass_context
def detach(ctx: click.Context, pid: int | None, detach_all: bool) -> None:
    """Detach from a hooked process (or all processes with --all)."""
    if not pid and not detach_all:
        console.print(
            "[bold red]✗[/bold red] Specify either "
            "[cyan]--pid PID[/cyan] or [cyan]--all[/cyan]"
        )
        sys.exit(1)

    import httpx
    from processscope.config import load_config
    config = load_config(ctx.obj.get("config_path"))

    try:
        if detach_all:
            # Detach all processes
            api_url = f"http://{config.server.host}:{config.server.port}/api/v1/processes"
            with console.status("[cyan]Detaching all processes...[/cyan]", spinner="dots"):
                resp = httpx.delete(api_url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                count = data.get("detached_count", 0)
                console.print(f"[bold green]✓[/bold green] Detached from [bold]{count}[/bold] process(es)")
            else:
                console.print(f"[bold red]✗[/bold red] [PS305] Failed to detach all: {resp.text}")
                sys.exit(1)
        else:
            # Detach specific PID
            api_url = f"http://{config.server.host}:{config.server.port}/api/v1/processes/{pid}"
            with console.status(f"[cyan]Detaching PID {pid}...[/cyan]", spinner="dots"):
                resp = httpx.delete(api_url, timeout=10.0)
            if resp.status_code == 200:
                console.print(f"[bold green]✓[/bold green] Detached from process [bold]{pid}[/bold]")
            elif resp.status_code == 404:
                console.print(f"[bold yellow]⚠[/bold yellow] PID {pid} is not hooked")
                sys.exit(1)
            else:
                console.print(f"[bold red]✗[/bold red] [PS305] Failed to detach: {resp.text}")
                sys.exit(1)

    except httpx.ConnectError:
        console.print(
            "[bold red]✗[/bold red] ProcessScope agent is not running.\n"
            "  Start it with: [cyan]processscope start[/cyan]"
        )
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
    except httpx.ConnectError:
        console.print(
            "[bold red]✗[/bold red] ProcessScope agent is not running.\n"
            "  Start it with: [cyan]sudo processscope start[/cyan]"
        )
        sys.exit(1)

    display_host = _get_display_host(config.server.host)

    # ── Agent Status Panel ──────────────────────────────────────
    build_info = get_build_info()
    build_type = data.get("build_number", "?")
    version = data.get("version", "?")
    uptime = data.get("uptime", "?")
    hooked_count = data.get("hooked_count", 0)

    status_color = "green" if data.get("status") == "running" else "red"
    status_icon = "●" if data.get("status") == "running" else "✕"

    info_grid = Table.grid(padding=(0, 2))
    info_grid.add_column(style="dim", justify="right")
    info_grid.add_column()

    info_grid.add_row("Status", f"[{status_color}]{status_icon} {data.get('status', 'unknown')}[/{status_color}]")
    info_grid.add_row("Version", f"[white]{version}[/white]  [dim]{build_type}[/dim]")
    info_grid.add_row("Uptime", uptime)
    info_grid.add_row("Hooked Processes", f"[bold white]{hooked_count}[/bold white]")
    info_grid.add_row("Dashboard", f"[bright_cyan]http://{display_host}:{config.server.port}[/bright_cyan]")
    info_grid.add_row("API Docs", f"[cyan]http://{display_host}:{config.server.port}/api/docs[/cyan]")

    console.print(Panel(
        info_grid,
        title="[bold blue]ProcessScope Status[/bold blue]",
        border_style="blue",
        padding=(0, 1),
    ))

    # ── Hooked Processes Table ──────────────────────────────────
    processes = data.get("hooked_processes", [])
    if processes:
        table = Table(
            title="Hooked Processes",
            box=box.ROUNDED,
            border_style="dim",
            header_style="bold cyan",
            show_lines=False,
            padding=(0, 1),
        )
        table.add_column("PID", style="bold white", justify="right", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("State", no_wrap=True)
        table.add_column("Mode", style="dim")
        table.add_column("CPU %", justify="right")
        table.add_column("Memory", justify="right")

        for proc in processes:
            state = proc.get("state", "?")
            state_color = _state_style(state)
            icon = _state_icon(state)
            state_text = Text(f"{icon} {state}", style=state_color)

            cpu = proc.get("cpu_percent", 0)
            cpu_str = f"{cpu:.1f}%"
            cpu_color = "red" if cpu > 80 else "yellow" if cpu > 40 else "green"

            table.add_row(
                str(proc.get("pid", "?")),
                proc.get("name", "?")[:24],
                state_text,
                proc.get("mode", "?"),
                f"[{cpu_color}]{cpu_str}[/{cpu_color}]",
                proc.get("memory_human", "0 B"),
            )

        console.print(table)
    elif hooked_count == 0:
        console.print(
            "[dim]No processes currently hooked. "
            "Use [white]processscope attach --name <name>[/white] to start monitoring.[/dim]"
        )


# ── List Command ──────────────────────────────────────────────────────

@main.command("list")
@click.option("--tree", is_flag=True, default=False, help="Show output as a hierarchical tree.")
@click.option("--limit", "-l", type=int, default=50,
              help="Maximum number of processes to display (default: 50, use 0 for all).")
@click.pass_context
def list_cmd(ctx: click.Context, tree: bool, limit: int) -> None:
    """List running system processes."""
    import httpx
    from processscope.config import load_config
    config = load_config(ctx.obj.get("config_path"))

    api_url = f"http://{config.server.host}:{config.server.port}/api/v1/system/tree"

    try:
        resp = httpx.get(api_url, timeout=5.0)
        data = resp.json()
        process_tree = data.get("tree", [])
    except httpx.ConnectError:
        console.print("[bold red]✗[/bold red] ProcessScope agent is not running.")
        sys.exit(1)

    if not process_tree:
        console.print("[dim]No processes found.[/dim]")
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        border_style="dim",
        header_style="bold cyan",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("PID", justify="right", no_wrap=True, style="bold white")
    table.add_column("PPID", justify="right", style="dim")
    table.add_column("User", style="cyan")
    table.add_column("State", style="dim")
    table.add_column("Name")

    count = [0]

    def add_flat(nodes: list[dict]) -> None:
        for node in nodes:
            if limit > 0 and count[0] >= limit:
                return
            state = node.get("status", "?")[:10]
            table.add_row(
                str(node.get("pid", "?")),
                str(node.get("ppid", "?")),
                (node.get("username") or "?")[:12],
                state,
                node.get("name", "?"),
            )
            count[0] += 1
            if node.get("children"):
                add_flat(node["children"])

    def add_tree(nodes: list[dict], level: int = 0) -> None:
        for node in nodes:
            if limit > 0 and count[0] >= limit:
                return
            indent = "  " * level + ("└─ " if level > 0 else "")
            name = f"{indent}{node.get('name', '?')}"
            state = node.get("status", "?")[:10]
            table.add_row(
                str(node.get("pid", "?")),
                str(node.get("ppid", "?")),
                (node.get("username") or "?")[:12],
                state,
                name,
            )
            count[0] += 1
            if node.get("children"):
                add_tree(node["children"], level + 1)

    if tree:
        add_tree(process_tree)
    else:
        add_flat(process_tree)

    console.print(table)

    if limit > 0 and count[0] >= limit:
        console.print(f"[dim]... output truncated to {limit} processes (use [white]--limit 0[/white] to show all)[/dim]")


# ── Version Command ───────────────────────────────────────────────────

@main.command()
def version() -> None:
    """Print version and build information."""
    build_info = get_build_info()
    build_type = build_info.build_number
    is_release = build_type != "local" and not build_type.startswith("dev")
    type_color = "bright_green" if is_release else "cyan"
    type_label = "release" if is_release else "local"

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", justify="right")
    grid.add_column()

    grid.add_row("Version", f"[bold white]{build_info.version}[/bold white]")
    grid.add_row("Build", f"[{type_color}]{build_info.build_number}[/{type_color}]  [dim]({type_label})[/dim]")
    grid.add_row("Git Commit", f"[dim]{build_info.git_commit}[/dim]")
    grid.add_row("Git Branch", f"[dim]{build_info.git_branch}[/dim]")
    grid.add_row("Build Date", f"[dim]{build_info.build_date}[/dim]")
    grid.add_row("Python", build_info.python_version)
    grid.add_row("Platform", build_info.platform_info)
    grid.add_row("Min Kernel", build_info.min_kernel)

    console.print(Panel(
        grid,
        title="[bold blue]ProcessScope[/bold blue]",
        border_style="blue",
        padding=(0, 1),
    ))


# ── Config Command ────────────────────────────────────────────────────

@main.command()
@click.option("--generate", "-g", is_flag=True, help="Generate default config file.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output path for generated config.")
@click.pass_context
def config(ctx: click.Context, generate: bool, output: str | None) -> None:
    """Show current or generate default configuration.

    The config file is a YAML file that controls all aspects of ProcessScope:
    server host/port, telemetry collectors, logging paths, and more.

    Use -c/--config with other commands to specify a custom config path instead
    of the default /etc/processscope/processscope.yaml. This is useful for running
    multiple isolated ProcessScope instances on the same machine.

    Example:
        processscope -c /etc/ps-staging/config.yaml start
    """
    from processscope.config import load_config, write_default_config

    if generate:
        out_path = Path(output) if output else Path("processscope.yaml")
        write_default_config(out_path)
        console.print(f"[bold green]✓[/bold green] Default config written to [cyan]{out_path}[/cyan]")
    else:
        cfg = load_config(ctx.obj.get("config_path"))
        import yaml
        console.print(yaml.dump(cfg.model_dump(), default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
