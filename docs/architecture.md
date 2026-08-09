# Architecture

ProcessScope uses a modular architecture combining a telemetry engine, a fast API layer, and a React-based web dashboard.

## System Diagram

```mermaid
flowchart TD
    subgraph Web ["Web Dashboard (Port 9876)"]
        UI[React + Vite]
    end

    subgraph API ["API Layer"]
        FastAPI[FastAPI Server]
        REST[REST API]
        WS[WebSocket]
        Assets[Static Assets]
        FastAPI --> REST
        FastAPI --> WS
        FastAPI --> Assets
    end

    subgraph Engine ["Telemetry Engine"]
        Core[Correlation · Timeline · Sessions]
        Coll[CPU, Mem, Thread, Net, FS, SysCall, HW Collectors]
        Core --> Coll
    end

    subgraph Hooking ["Process Hooking Layer"]
        Attach[Attach · Metadata · ELF · Tree]
    end

    subgraph Kernel ["Linux Kernel"]
        Linux[/proc · psutil · ptrace · eBPF]
    end

    Web -->|HTTP/WS| API
    API --> Engine
    Engine --> Hooking
    Hooking --> Kernel
```

## Components

1. **Process Hooking Layer**: Interfaces directly with Linux primitives (ptrace, /proc, eBPF) to attach to processes dynamically.
2. **Telemetry Engine**: Gathers high-resolution metrics for CPU, Memory, Network, and File System, building a cohesive timeline.
3. **API Server**: Powered by FastAPI, it provides REST endpoints for management and WebSockets for live telemetry streaming.
4. **Web Dashboard**: A React application that provides a unified, interactive view into process behavior.
