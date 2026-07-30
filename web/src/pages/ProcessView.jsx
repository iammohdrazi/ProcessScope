import React from 'react';
import { useParams } from 'react-router-dom';

export default function ProcessView() {
  const { tab } = useParams();
  const title = tab ? tab.charAt(0).toUpperCase() + tab.slice(1) : 'Process';

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">{title} Telemetry</h1>
          <p className="page-subtitle">Detailed {tab} monitoring for hooked processes</p>
        </div>
      </div>
      <div className="card" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
        <p style={{ fontSize: '1.1rem', marginBottom: 8 }}>Attach a process to view {tab} telemetry</p>
        <p style={{ fontSize: '0.8rem' }}>Run: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>processscope attach --pid &lt;PID&gt;</code></p>
      </div>
    </div>
  );
}
