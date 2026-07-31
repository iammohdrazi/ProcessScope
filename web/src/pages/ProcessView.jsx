import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Cpu, MemoryStick, Network, HardDrive, Activity, AlertTriangle } from 'lucide-react';

const API_BASE = '/api/v1';

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

  // Fetch initial status and hooked processes
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
        
        {/* Process Selector Dropdown */}
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

      <div className="card" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
        <AlertTriangle size={32} style={{ marginBottom: 16, opacity: 0.5, color: 'var(--accent-yellow)' }} />
        <p style={{ fontSize: '1.1rem', marginBottom: 8, color: 'var(--text-primary)' }}>Advanced Telemetry Under Construction</p>
        <p style={{ fontSize: '0.9rem' }}>Deep inspection for {tab} will be enabled in Phase 4 updates.</p>
        <p style={{ fontSize: '0.85rem', marginTop: 12 }}>Currently viewing summary data for PID <span className="mono" style={{ color: 'var(--accent-cyan)' }}>{selectedPid}</span> in Dashboard.</p>
      </div>
    </div>
  );
}
