# CLI Reference

ProcessScope provides a powerful command-line interface to manage the observability server and attach to processes.

## Basic Commands

### `processscope start`
Starts the ProcessScope backend server and web dashboard.
```bash
sudo processscope start
```

### `processscope attach`
Dynamically hooks into a running process.
```bash
# Attach by PID
processscope attach --pid 1234

# Attach by name
processscope attach --name nginx
```

### `processscope status`
Displays the current status of the daemon and attached processes.
```bash
processscope status
```

### `processscope stop`
Stops the daemon and detaches from all processes.
```bash
sudo processscope stop
```

## Logging
Logs are automatically written to standard Linux logging systems and dedicated application logs:

```bash
# Main log
tail -f /var/log/processscope/processscope.log

# Telemetry log
tail -f /var/log/processscope/telemetry.log

# Audit log
tail -f /var/log/processscope/audit.log
```
