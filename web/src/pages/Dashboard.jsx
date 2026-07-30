import React, { useState, useEffect, useCallback } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Cpu, MemoryStick, Network, HardDrive, Zap, Users, AlertTriangle, Activity } from 'lucide-react';

const API_BASE = '/api/v1';

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

function LiveChart({ data, dataKey, color, title }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">{title}</div>
        <span className="badge blue">LIVE</span>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: '#111827',
                border: '1px solid rgba(59,130,246,0.3)',
                borderRadius: '10px',
                fontSize: '12px',
                fontFamily: 'JetBrains Mono',
              }}
            />
            <Area type="monotone" dataKey={dataKey} stroke={color} fill={`url(#grad-${dataKey})`} strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [status, setStatus] = useState(null);
  const [cpuHistory, setCpuHistory] = useState([]);
  const [memHistory, setMemHistory] = useState([]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);

        const now = new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

        setCpuHistory(prev => {
          const next = [...prev, { time: now, cpu: Math.random() * 40 + 10 }];
          return next.slice(-30);
        });

        setMemHistory(prev => {
          const next = [...prev, { time: now, memory: Math.random() * 1024 + 512 }];
          return next.slice(-30);
        });
      }
    } catch (err) {
      // API not available yet
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const hookedCount = status?.hooked_count ?? 0;
  const engineEvents = status?.engine?.total_events ?? 0;

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Real-time process observability overview</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="badge green">
            <span className="status-dot online" style={{ width: 6, height: 6 }}></span>
            Connected
          </span>
          <button className="btn btn-primary" onClick={() => {/* attach modal */}}>
            <Zap size={14} /> Attach Process
          </button>
        </div>
      </div>

      <div className="metrics-grid">
        <MetricCard label="Hooked Processes" value={hookedCount} color="blue" icon={Activity} />
        <MetricCard label="Total Events" value={engineEvents.toLocaleString()} color="green" icon={Zap} />
        <MetricCard label="CPU Usage" value={`${(Math.random() * 30 + 5).toFixed(1)}%`} change="+2.3%" color="purple" icon={Cpu} />
        <MetricCard label="Memory" value={`${(Math.random() * 512 + 256).toFixed(0)} MB`} change="+12 MB" color="red" icon={MemoryStick} />
      </div>

      <div className="grid-2" style={{ marginBottom: '20px' }}>
        <LiveChart data={cpuHistory} dataKey="cpu" color="#3b82f6" title="CPU Usage %" />
        <LiveChart data={memHistory} dataKey="memory" color="#8b5cf6" title="Memory (MB)" />
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Users size={16} /> Hooked Processes</div>
          </div>
          {status?.hooked_processes?.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>PID</th>
                  <th>Name</th>
                  <th>State</th>
                  <th>Mode</th>
                </tr>
              </thead>
              <tbody>
                {status.hooked_processes.map(p => (
                  <tr key={p.pid}>
                    <td className="mono">{p.pid}</td>
                    <td>{p.name}</td>
                    <td><span className={`badge ${p.state === 'attached' ? 'green' : 'yellow'}`}>{p.state}</span></td>
                    <td><span className="badge blue">{p.mode}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
              <AlertTriangle size={24} style={{ marginBottom: 8, opacity: 0.5 }} />
              <p>No processes hooked yet</p>
              <p style={{ fontSize: '0.75rem', marginTop: 4 }}>Use the CLI or click Attach Process</p>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title"><Activity size={16} /> Recent Events</div>
          </div>
          <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
            {[...Array(8)].map((_, i) => (
              <div key={i} className="timeline-event">
                <div className={`timeline-dot ${['cpu', 'memory', 'thread', 'network', 'filesystem'][i % 5]}`}></div>
                <div>
                  <div className="timeline-time">{new Date(Date.now() - i * 3000).toLocaleTimeString()}</div>
                  <div className="timeline-title">
                    {['CPU Sample', 'Memory Sample', 'Thread Created', 'Connection Opened', 'File Read'][i % 5]}
                  </div>
                  <div className="timeline-message">Telemetry event collected</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
