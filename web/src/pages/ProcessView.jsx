import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Cpu, MemoryStick, Network, HardDrive, Activity, AlertTriangle } from 'lucide-react';

const API_BASE = '/api/v1';

function useTelemetry(pid, category) {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    if (!pid || !category) return;
    async function fetchTelemetry() {
      try {
        const res = await fetch(`${API_BASE}/processes/${pid}/telemetry?category=${category}&limit=1`);
        if (res.ok) {
          const json = await res.json();
          if (json.events && json.events.length > 0) {
            setData(json.events[0].data);
          }
        }
      } catch (e) {
        console.error("Telemetry fetch error:", e);
      }
    }
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 2000);
    return () => clearInterval(interval);
  }, [pid, category]);
  
  return data;
}

function CpuTelemetryView({ pid }) {
  const cpuData = useTelemetry(pid, 'cpu');
  const threadData = useTelemetry(pid, 'thread');

  if (!cpuData) return <div>Loading CPU data...</div>;

  return (
    <div style={{ textAlign: 'left' }}>
      <div className="grid-3" style={{ marginBottom: '20px' }}>
        <div className="card">
          <div className="card-title">CPU Percent</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{cpuData.process?.cpu_percent}%</div>
        </div>
        <div className="card">
          <div className="card-title">Total Threads</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{cpuData.process?.num_threads}</div>
        </div>
        <div className="card">
          <div className="card-title">Context Switches</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{cpuData.context_switches?.voluntary}</div>
        </div>
      </div>
      
      {threadData && threadData.threads && (
        <div className="card">
          <div className="card-title">Threads (Top 100)</div>
          <div style={{ overflowX: 'auto', marginTop: '10px' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>TID</th>
                  <th>Name</th>
                  <th>State</th>
                  <th>User Time</th>
                  <th>System Time</th>
                </tr>
              </thead>
              <tbody>
                {threadData.threads.map(t => (
                  <tr key={t.tid}>
                    <td className="mono">{t.tid}</td>
                    <td>{t.name || '-'}</td>
                    <td>{t.state || '-'}</td>
                    <td className="mono">{t.user_time}</td>
                    <td className="mono">{t.system_time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MemoryTelemetryView({ pid }) {
  const memData = useTelemetry(pid, 'memory');
  if (!memData) return <div>Loading Memory data...</div>;

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div style={{ textAlign: 'left' }}>
      <div className="grid-3" style={{ marginBottom: '20px' }}>
        <div className="card">
          <div className="card-title">RSS Memory</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{formatBytes(memData.usage?.rss)}</div>
        </div>
        <div className="card">
          <div className="card-title">VMS Memory</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{formatBytes(memData.usage?.vms)}</div>
        </div>
        <div className="card">
          <div className="card-title">Page Faults</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{memData.usage?.pfaults || 0}</div>
        </div>
      </div>
      
      {memData.maps && (
        <div className="card">
          <div className="card-title">Memory Maps (Top 100)</div>
          <div style={{ overflowX: 'auto', marginTop: '10px' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Size</th>
                  <th>RSS</th>
                  <th>Permissions</th>
                </tr>
              </thead>
              <tbody>
                {memData.maps.map((m, idx) => (
                  <tr key={idx}>
                    <td className="mono" style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.path}>{m.path || '[anonymous]'}</td>
                    <td className="mono">{formatBytes(m.size)}</td>
                    <td className="mono">{formatBytes(m.rss)}</td>
                    <td className="mono">{m.perms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function NetworkTelemetryView({ pid }) {
  const netData = useTelemetry(pid, 'network');
  if (!netData) return <div>Loading Network data...</div>;

  return (
    <div style={{ textAlign: 'left' }}>
      <div className="grid-3" style={{ marginBottom: '20px' }}>
        <div className="card">
          <div className="card-title">Active Connections</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{netData.connection_count}</div>
        </div>
        <div className="card">
          <div className="card-title">Send Rate</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{netData.io?.send_rate_human || '0 B/s'}</div>
        </div>
        <div className="card">
          <div className="card-title">Receive Rate</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{netData.io?.recv_rate_human || '0 B/s'}</div>
        </div>
      </div>
      
      {netData.connections && (
        <div className="card">
          <div className="card-title">Connections</div>
          <div style={{ overflowX: 'auto', marginTop: '10px' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Local Address</th>
                  <th>Remote Address</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {netData.connections.map((c, idx) => (
                  <tr key={idx}>
                    <td>{c.family} / {c.type}</td>
                    <td className="mono">{c.local_address}</td>
                    <td className="mono">{c.remote_address}</td>
                    <td>{c.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function FileSystemTelemetryView({ pid }) {
  const fsData = useTelemetry(pid, 'filesystem');
  if (!fsData) return <div>Loading I/O data...</div>;

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div style={{ textAlign: 'left' }}>
      <div className="grid-3" style={{ marginBottom: '20px' }}>
        <div className="card">
          <div className="card-title">Open Files</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{fsData.open_files_count}</div>
        </div>
        <div className="card">
          <div className="card-title">Read Bytes</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{formatBytes(fsData.io?.read_bytes)}</div>
        </div>
        <div className="card">
          <div className="card-title">Write Bytes</div>
          <div style={{ fontSize: '1.5rem', marginTop: 10 }}>{formatBytes(fsData.io?.write_bytes)}</div>
        </div>
      </div>
      
      {fsData.open_files && (
        <div className="card">
          <div className="card-title">Open Files (Top 100)</div>
          <div style={{ overflowX: 'auto', marginTop: '10px' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>FD</th>
                  <th>Path</th>
                </tr>
              </thead>
              <tbody>
                {fsData.open_files.map((f, idx) => (
                  <tr key={idx}>
                    <td className="mono">{f.fd}</td>
                    <td className="mono" style={{ maxWidth: '500px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.path}>{f.path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ProcessView() {
  const { tab } = useParams();
  const [status, setStatus] = useState(null);
  const [selectedPid, setSelectedPid] = useState(null);
  
  const titles = {
    cpu: 'CPU & Threads',
    memory: 'Memory',
    network: 'Network',
    filesystem: 'I/O & Files'
  };
  
  const icons = {
    cpu: Cpu,
    memory: MemoryStick,
    network: Network,
    filesystem: HardDrive
  };

  const title = titles[tab] || 'Telemetry';
  const Icon = icons[tab] || Activity;

  useEffect(() => {
    async function fetchStatus() {
      try {
        const res = await fetch(`${API_BASE}/status`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          
          if (data.hooked_processes && data.hooked_processes.length > 0 && !selectedPid) {
            setSelectedPid(data.hooked_processes[0].pid);
          }
        }
      } catch (err) {
        // Ignore
      }
    }
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [selectedPid]);

  const hookedCount = status?.hooked_processes?.length || 0;

  if (hookedCount === 0) {
    return (
      <div className="animate-fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center', maxWidth: '400px' }}>
          <div style={{ width: '80px', height: '80px', background: 'var(--bg-tertiary)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 24px', boxShadow: 'var(--shadow-lg)' }}>
            <Activity size={40} style={{ color: 'var(--accent-blue)' }} />
          </div>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '12px' }}>No Processes Hooked</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '32px', lineHeight: '1.6' }}>
            Attach a process to view detailed {tab} telemetry.
          </p>
        </div>
      </div>
    );
  }

  const renderTabContent = () => {
    if (!selectedPid) return null;
    switch(tab) {
      case 'cpu':
        return <CpuTelemetryView pid={selectedPid} />;
      case 'memory':
        return <MemoryTelemetryView pid={selectedPid} />;
      case 'network':
        return <NetworkTelemetryView pid={selectedPid} />;
      case 'filesystem':
        return <FileSystemTelemetryView pid={selectedPid} />;
      default:
        return (
          <div className="card" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <AlertTriangle size={32} style={{ marginBottom: 16, opacity: 0.5, color: 'var(--accent-yellow)' }} />
            <p style={{ fontSize: '1.1rem', marginBottom: 8, color: 'var(--text-primary)' }}>Unknown Tab</p>
          </div>
        );
    }
  }

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Icon size={24} style={{ color: 'var(--accent-blue)' }} />
            {title}
          </h1>
          <p className="page-subtitle">Detailed {tab} monitoring for hooked processes</p>
        </div>
        
        {status?.hooked_processes && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Target Process:</span>
            <select 
              className="input" 
              style={{ width: '250px' }}
              value={selectedPid || ''}
              onChange={(e) => setSelectedPid(Number(e.target.value))}
            >
              {status.hooked_processes.map(p => (
                <option key={p.pid} value={p.pid}>
                  PID {p.pid} — {p.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {renderTabContent()}
    </div>
  );
}
