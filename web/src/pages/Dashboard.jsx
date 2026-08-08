import React, { useState, useEffect, useRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Users, Activity, CheckSquare, Square, Unlink } from 'lucide-react';

const COLORS = [
  '#3b82f6', '#10b981', '#8b5cf6', '#ef4444', '#f59e0b',
  '#06b6d4', '#ec4899', '#84cc16', '#6366f1', '#f43f5e'
];

const MAX_HISTORY = 60;

function MultiLineChart({ data, selectedPids, dataKeyFn, title, unit = '' }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">{title}</div>
        <span className="badge blue">LIVE</span>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <defs>
              {selectedPids.map((pid, idx) => (
                <linearGradient key={pid} id={`grad-${pid}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS[idx % COLORS.length]} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={COLORS[idx % COLORS.length]} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} tickMargin={10} minTickGap={30} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(val) => `${val}${unit}`} />
            <Tooltip
              contentStyle={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-accent)',
                borderRadius: '10px',
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
              }}
              formatter={(value, name) => [`${value}${unit}`, `PID ${name}`]}
            />
            {selectedPids.map((pid, idx) => (
              <Area
                key={pid}
                type="monotone"
                dataKey={(row) => dataKeyFn(row, pid)}
                name={pid.toString()}
                stroke={COLORS[idx % COLORS.length]}
                fill={`url(#grad-${pid})`}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function StateBadge({ state }) {
  const map = {
    attached: 'green',
    process_exited: 'red',
    error: 'red',
    detaching: 'yellow',
    detached: 'blue',
    attaching: 'blue',
  };
  return <span className={`badge ${map[state] || 'blue'}`}>{state}</span>;
}

export default function Dashboard() {
  const [hooked, setHooked] = useState([]);
  const [selectedPids, setSelectedPids] = useState(new Set());
  const [history, setHistory] = useState([]);
  const [detachingPid, setDetachingPid] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    const initHistory = [];
    const now = Date.now();
    for (let i = MAX_HISTORY; i > 0; i--) {
      initHistory.push({
        timestamp: now - i * 1000,
        time: new Date(now - i * 1000).toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
        data: {}
      });
    }
    setHistory(initHistory);
  }, []);

  useEffect(() => {
    async function fetchStatus() {
      try {
        const res = await fetch('/api/v1/status');
        if (res.ok) {
          const data = await res.json();
          setHooked(data.hooked_processes || []);
          if (data.hooked_processes && data.hooked_processes.length > 0) {
            setSelectedPids(prev => {
              if (prev.size === 0) return new Set([data.hooked_processes[0].pid]);
              return prev;
            });
          }
        }
      } catch { /* ignore */ }
    }
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/telemetry`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry_event' && msg.data) {
          const d = msg.data;
          setHistory(prev => {
            const last = prev[prev.length - 1];
            const now = Date.now();
            if (now - last.timestamp >= 1000) {
              const pt = { timestamp: now, time: new Date(now).toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }), data: { ...last.data } };
              pt.data[d.pid] = { ...(pt.data[d.pid] || {}) };
              if (d.category === 'cpu' && d.data?.process) pt.data[d.pid].cpu = d.data.process.cpu_percent;
              if (d.category === 'memory' && d.data?.process) pt.data[d.pid].memory = d.data.process.rss / 1048576;
              const next = [...prev, pt];
              if (next.length > MAX_HISTORY) next.shift();
              return next;
            } else {
              const next = [...prev];
              const cur = { ...next[next.length - 1], data: { ...next[next.length - 1].data } };
              cur.data[d.pid] = { ...(cur.data[d.pid] || {}) };
              if (d.category === 'cpu' && d.data?.process) cur.data[d.pid].cpu = d.data.process.cpu_percent;
              if (d.category === 'memory' && d.data?.process) cur.data[d.pid].memory = d.data.process.rss / 1048576;
              next[next.length - 1] = cur;
              return next;
            }
          });
        }
      } catch { /* ignore */ }
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: selectedPids.size > 0 ? 'subscribe' : 'unsubscribe',
        pids: Array.from(selectedPids)
      }));
    }
  }, [selectedPids]);

  const togglePid = (pid) => setSelectedPids(prev => {
    const n = new Set(prev);
    n.has(pid) ? n.delete(pid) : n.add(pid);
    return n;
  });

  const toggleAll = () => {
    if (selectedPids.size === hooked.length) setSelectedPids(new Set());
    else setSelectedPids(new Set(hooked.map(p => p.pid)));
  };

  const detachProcess = async (pid) => {
    setDetachingPid(pid);
    try {
      await fetch(`/api/v1/processes/${pid}`, { method: 'DELETE' });
      setSelectedPids(prev => { const n = new Set(prev); n.delete(pid); return n; });
    } catch { /* ignore */ } finally {
      setDetachingPid(null);
    }
  };

  const hookedCount = hooked.length;
  const selectedPidsArray = Array.from(selectedPids);

  if (hookedCount === 0) {
    return (
      <div className="animate-fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', maxWidth: '420px' }}>
          <div style={{ width: '80px', height: '80px', background: 'var(--bg-tertiary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', boxShadow: 'var(--shadow-lg)' }}>
            <Activity size={40} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '12px' }}>No Processes Hooked</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '32px', lineHeight: '1.6' }}>
            ProcessScope is running. Attach to a process to start monitoring.
          </p>
          <div style={{ background: 'var(--bg-card)', padding: '20px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', textAlign: 'left' }}>
            <p style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '12px' }}>Attach via CLI:</p>
            {['sudo processscope attach --name nginx', 'sudo processscope attach --pid 1234', 'sudo processscope attach -n myapp --children'].map(cmd => (
              <div key={cmd} style={{ background: 'var(--bg-secondary)', padding: '10px 12px', borderRadius: '4px', fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--text-accent)', marginBottom: '8px' }}>
                {cmd}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time process observability</p>
        </div>
        <span className="badge green">
          <span className="status-dot online" style={{ width: 6, height: 6 }}></span>
          {hookedCount} Process{hookedCount !== 1 ? 'es' : ''} Hooked
        </span>
      </div>

      {/* Process Selector Bar */}
      <div className="card" style={{ marginBottom: '24px', padding: '12px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', overflowX: 'auto', paddingBottom: '4px' }}>
          <div onClick={toggleAll} style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontWeight: 600, paddingRight: '16px', borderRight: '1px solid var(--border-default)', flexShrink: 0 }}>
            {selectedPids.size === hooked.length ? <CheckSquare size={16} /> : <Square size={16} />}
            All
          </div>
          {hooked.map((proc, idx) => {
            const isSelected = selectedPids.has(proc.pid);
            const isExited = proc.state === 'process_exited';
            const color = isExited ? '#ef4444' : COLORS[idx % COLORS.length];
            return (
              <div key={proc.pid} onClick={() => togglePid(proc.pid)} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', background: isSelected ? 'var(--bg-hover)' : 'transparent', padding: '4px 10px', borderRadius: '100px', border: `1px solid ${isSelected ? color : 'transparent'}`, opacity: isExited ? 0.6 : 1 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, opacity: isSelected ? 1 : 0.3 }}></div>
                <span className="mono" style={{ fontSize: '0.8rem' }}>{proc.pid}</span>
                <span style={{ fontSize: '0.85rem' }}>{proc.name}</span>
                {isExited && <span style={{ fontSize: '0.7rem', color: '#ef4444' }}>✕ exited</span>}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: '24px' }}>
        <MultiLineChart title="CPU Usage" data={history} selectedPids={selectedPidsArray} dataKeyFn={(row, pid) => row.data[pid]?.cpu || 0} unit="%" />
        <MultiLineChart title="Memory (RSS)" data={history} selectedPids={selectedPidsArray} dataKeyFn={(row, pid) => parseFloat((row.data[pid]?.memory || 0).toFixed(1))} unit=" MB" />
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><Users size={16} /> Process Details</div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>PID</th><th>Name</th><th>Command</th><th>Mode</th>
              <th>State</th><th>CPU %</th><th>Memory</th><th></th>
            </tr>
          </thead>
          <tbody>
            {hooked.map(p => (
              <tr key={p.pid} style={{ opacity: p.state === 'process_exited' ? 0.6 : 1 }}>
                <td className="mono">{p.pid}</td>
                <td>{p.name}</td>
                <td className="mono" style={{ maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.cmdline?.join(' ') || p.exe}</td>
                <td><span className="badge blue">{p.mode}</span></td>
                <td><StateBadge state={p.state} /></td>
                <td className="mono">{(p.cpu_percent || 0).toFixed(1)}%</td>
                <td className="mono">{p.memory_human || '0 B'}</td>
                <td>
                  <button onClick={() => detachProcess(p.pid)} disabled={detachingPid === p.pid} title="Detach" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, color: 'var(--accent-red)', cursor: 'pointer', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.78rem' }}>
                    <Unlink size={12} />
                    {detachingPid === p.pid ? '...' : 'Detach'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
