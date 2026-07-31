import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Cpu, MemoryStick, Network, Zap, Users, AlertTriangle, Activity, CheckSquare, Square } from 'lucide-react';

// Pre-defined colors for up to 10 processes
const COLORS = [
  '#3b82f6', '#10b981', '#8b5cf6', '#ef4444', '#f59e0b',
  '#06b6d4', '#ec4899', '#84cc16', '#6366f1', '#f43f5e'
];

function MetricCard({ label, value, change, color, icon: Icon }) {
  return (
    <div className={`metric-card ${color}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div className="metric-label">{label}</div>
          <div className={`metric-value ${color}`}>{value}</div>
          {change && (
            <div className={`metric-change ${change.startsWith('+') ? 'up' : change.startsWith('-') ? 'down' : 'stable'}`}>
              {change}
            </div>
          )}
        </div>
        {Icon && <Icon size={20} style={{ color: `var(--accent-${color})`, opacity: 0.5 }} />}
      </div>
    </div>
  );
}

// 60 data points for 60 seconds history
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
              formatter={(value, name, props) => [`${value}${unit}`, `PID ${name}`]}
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
                isAnimationActive={false} // Turn off recharts animation for smooth streaming
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [hooked, setHooked] = useState([]);
  const [selectedPids, setSelectedPids] = useState(new Set());
  
  const [history, setHistory] = useState([]);
  const wsRef = useRef(null);

  // Initialize history array with empty data points
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

  // Fetch initial status and hooked processes
  useEffect(() => {
    async function fetchStatus() {
      try {
        const res = await fetch('/api/v1/status');
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          setHooked(data.hooked_processes || []);
          
          // Select the first process by default if none selected
          if (data.hooked_processes && data.hooked_processes.length > 0) {
            setSelectedPids(prev => {
              if (prev.size === 0) {
                return new Set([data.hooked_processes[0].pid]);
              }
              return prev;
            });
          }
        }
      } catch (err) {
        // Ignore
      }
    }
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket connection for real-time telemetry
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // Subscribe to selected PIDs when opened
      if (selectedPids.size > 0) {
        ws.send(JSON.stringify({
          action: 'subscribe',
          pids: Array.from(selectedPids)
        }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry_event' && msg.data) {
          const d = msg.data;
          
          setHistory(prev => {
            const last = prev[prev.length - 1];
            const now = Date.now();
            
            // If it's been more than 1s since last point, create a new point
            if (now - last.timestamp >= 1000) {
              const newPoint = {
                timestamp: now,
                time: new Date(now).toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' }),
                data: { ...last.data } // Carry forward previous values
              };
              
              // Update new point with new event data
              if (!newPoint.data[d.pid]) newPoint.data[d.pid] = {};
              
              if (d.category === 'cpu' && d.data.process) {
                newPoint.data[d.pid].cpu = d.data.process.cpu_percent;
              } else if (d.category === 'memory' && d.data.process) {
                newPoint.data[d.pid].memory = d.data.process.rss / (1024 * 1024); // MB
              }
              
              const next = [...prev, newPoint];
              if (next.length > MAX_HISTORY) next.shift();
              return next;
            } else {
              // Update current point
              const next = [...prev];
              const curPoint = { ...next[next.length - 1] };
              curPoint.data = { ...curPoint.data };
              if (!curPoint.data[d.pid]) curPoint.data[d.pid] = {};
              
              if (d.category === 'cpu' && d.data.process) {
                curPoint.data[d.pid].cpu = d.data.process.cpu_percent;
              } else if (d.category === 'memory' && d.data.process) {
                curPoint.data[d.pid].memory = d.data.process.rss / (1024 * 1024);
              }
              
              next[next.length - 1] = curPoint;
              return next;
            }
          });
        }
      } catch (err) {
        // Ignore JSON errors
      }
    };

    return () => {
      ws.close();
    };
  }, []); // Only run once to setup WS

  // Update WS subscription when selectedPids changes
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      if (selectedPids.size > 0) {
        wsRef.current.send(JSON.stringify({
          action: 'subscribe',
          pids: Array.from(selectedPids)
        }));
      } else {
        wsRef.current.send(JSON.stringify({ action: 'unsubscribe' }));
      }
    }
  }, [selectedPids]);

  const togglePid = (pid) => {
    setSelectedPids(prev => {
      const next = new Set(prev);
      if (next.has(pid)) {
        next.delete(pid);
      } else {
        next.add(pid);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedPids.size === hooked.length) {
      setSelectedPids(new Set());
    } else {
      setSelectedPids(new Set(hooked.map(p => p.pid)));
    }
  };

  const hookedCount = hooked.length;

  if (hookedCount === 0) {
    return (
      <div className="animate-fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', maxWidth: '400px' }}>
          <div style={{ width: '80px', height: '80px', background: 'var(--bg-tertiary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', boxShadow: 'var(--shadow-lg)' }}>
            <Activity size={40} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '12px' }}>No Processes Hooked</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '32px', lineHeight: '1.6' }}>
            ProcessScope is running, but you haven't attached to any processes yet.
          </p>
          
          <div style={{ background: 'var(--bg-card)', padding: '20px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', textAlign: 'left' }}>
            <p style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '12px' }}>Attach via CLI on the server:</p>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '4px', fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-accent)' }}>
              sudo processscope attach --name nginx
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '4px', fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-accent)', marginTop: '8px' }}>
              sudo processscope attach --pid 1234
            </div>
          </div>
        </div>
      </div>
    );
  }

  const selectedPidsArray = Array.from(selectedPids);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time process observability</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="badge green">
            <span className="status-dot online" style={{ width: 6, height: 6 }}></span>
            Connected
          </span>
        </div>
      </div>

      {/* Process Selector Bar */}
      <div className="card" style={{ marginBottom: '24px', padding: '12px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', overflowX: 'auto', paddingBottom: '4px' }}>
          <div 
            onClick={toggleAll}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontWeight: 600, paddingRight: '16px', borderRight: '1px solid var(--border-default)' }}
          >
            {selectedPids.size === hooked.length ? <CheckSquare size={16} className="text-accent" /> : <Square size={16} />}
            Select All
          </div>
          
          {hooked.map((proc, idx) => {
            const isSelected = selectedPids.has(proc.pid);
            const color = COLORS[idx % COLORS.length];
            return (
              <div 
                key={proc.pid} 
                onClick={() => togglePid(proc.pid)}
                style={{ 
                  display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
                  background: isSelected ? 'var(--bg-hover)' : 'transparent',
                  padding: '4px 10px', borderRadius: '100px', border: `1px solid ${isSelected ? color : 'transparent'}`
                }}
              >
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, opacity: isSelected ? 1 : 0.3 }}></div>
                <span className="mono" style={{ fontSize: '0.8rem' }}>{proc.pid}</span>
                <span style={{ fontSize: '0.85rem' }}>{proc.name}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid-2" style={{ marginBottom: '24px' }}>
        <MultiLineChart 
          title="CPU Usage" 
          data={history} 
          selectedPids={selectedPidsArray} 
          dataKeyFn={(row, pid) => row.data[pid]?.cpu || 0}
          unit="%"
        />
        <MultiLineChart 
          title="Memory (RSS)" 
          data={history} 
          selectedPids={selectedPidsArray} 
          dataKeyFn={(row, pid) => parseFloat((row.data[pid]?.memory || 0).toFixed(1))}
          unit=" MB"
        />
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><Users size={16} /> Selected Process Details</div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>PID</th>
              <th>Name</th>
              <th>Command</th>
              <th>Mode</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {hooked.filter(p => selectedPids.has(p.pid)).map(p => (
              <tr key={p.pid}>
                <td className="mono">{p.pid}</td>
                <td>{p.name}</td>
                <td className="mono" style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.cmdline?.join(' ') || p.exe}
                </td>
                <td><span className="badge blue">{p.mode}</span></td>
                <td><span className={`badge ${p.state === 'attached' ? 'green' : 'yellow'}`}>{p.state}</span></td>
              </tr>
            ))}
            {selectedPids.size === 0 && (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '20px' }}>No processes selected</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
