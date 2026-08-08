import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import {
  Cpu, HardDrive, LayoutDashboard, Network, Clock,
  Layers, Monitor, Moon, Sun, ListTree, Settings, Bug,
  Unlink, ChevronRight, Zap
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import ProcessView from './pages/ProcessView';
import Timeline from './pages/Timeline';
import SystemInfo from './pages/SystemInfo';
import ProcessList from './pages/ProcessList';
import { ThemeProvider, useTheme } from './ThemeContext';

// ── Settings Panel ────────────────────────────────────────────────────

function SettingsPanel({ onClose }) {
  const [debugLog, setDebugLog] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detachLoading, setDetachLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/v1/debug-log/status')
      .then(r => r.json())
      .then(d => setDebugLog(d.enabled))
      .catch(() => setDebugLog(false));
  }, []);

  const toggleDebugLog = async () => {
    setLoading(true);
    setMessage('');
    try {
      const endpoint = debugLog ? '/api/v1/debug-log/disable' : '/api/v1/debug-log/enable';
      const res = await fetch(endpoint, { method: 'POST' });
      const data = await res.json();
      setDebugLog(!debugLog);
      setMessage(data.path ? `Logging to: ${data.path}` : data.message);
    } catch (e) {
      setMessage('Failed to toggle debug log');
    } finally {
      setLoading(false);
    }
  };

  const detachAll = async () => {
    if (!confirm('Detach from ALL hooked processes?')) return;
    setDetachLoading(true);
    setMessage('');
    try {
      const res = await fetch('/api/v1/processes', { method: 'DELETE' });
      const data = await res.json();
      setMessage(`Detached ${data.detached_count} process(es)`);
    } catch (e) {
      setMessage('Failed to detach processes');
    } finally {
      setDetachLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
      zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      backdropFilter: 'blur(4px)'
    }} onClick={onClose}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-lg)', padding: '28px', minWidth: '360px',
          maxWidth: '440px', boxShadow: 'var(--shadow-lg)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Settings size={18} style={{ color: 'var(--accent-blue)' }} />
            Settings
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
        </div>

        {/* Debug Logging */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Debug Logging
          </div>
          <div style={{
            background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)',
            padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center'
          }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Bug size={14} style={{ color: debugLog ? 'var(--accent-yellow)' : 'var(--text-tertiary)' }} />
                Verbose Debug Log
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                Write all DEBUG events to <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-accent)' }}>/tmp/processscope/debug.log</code>
              </div>
            </div>
            <button
              onClick={toggleDebugLog}
              disabled={loading || debugLog === null}
              style={{
                width: 44, height: 24, borderRadius: 100,
                background: debugLog ? 'var(--accent-blue)' : 'var(--bg-card)',
                border: '2px solid ' + (debugLog ? 'var(--accent-blue)' : 'var(--border-default)'),
                cursor: 'pointer', position: 'relative', transition: 'all 0.2s',
                flexShrink: 0
              }}
            >
              <div style={{
                width: 16, height: 16, borderRadius: '50%', background: 'white',
                position: 'absolute', top: 2, transition: 'left 0.2s',
                left: debugLog ? 22 : 2
              }} />
            </button>
          </div>
        </div>

        {/* Process Management */}
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Process Management
          </div>
          <button
            onClick={detachAll}
            disabled={detachLoading}
            style={{
              width: '100%', padding: '12px', borderRadius: 'var(--radius-md)',
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              color: 'var(--accent-red)', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              transition: 'all 0.15s'
            }}
          >
            <Unlink size={16} />
            {detachLoading ? 'Detaching...' : 'Detach All Processes'}
          </button>
        </div>

        {/* Message */}
        {message && (
          <div style={{
            background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
            padding: '10px 14px', fontSize: '0.82rem', color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)', wordBreak: 'break-all'
          }}>
            {message}
          </div>
        )}

        <div style={{ marginTop: 20, fontSize: '0.78rem', color: 'var(--text-tertiary)', textAlign: 'center' }}>
          CLI: <code style={{ fontFamily: 'var(--font-mono)' }}>processscope start --debug-log</code>
        </div>
      </div>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────

function Sidebar() {
  const { theme, toggleTheme } = useTheme();
  const [version, setVersion] = useState(null);
  const [agentOnline, setAgentOnline] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/v1/version');
        if (res.ok) {
          const d = await res.json();
          setVersion(d);
          setAgentOnline(true);
        }
      } catch {
        setAgentOnline(false);
      }
    };
    check();
    const iv = setInterval(check, 10000);
    return () => clearInterval(iv);
  }, []);

  return (
    <>
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} />}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-icon">🔬</div>
            <div>
              <h1>ProcessScope</h1>
              <span className="version-badge">
                v{version?.version || '...'}
                {version?.build_type === 'release' && (
                  <span style={{ marginLeft: 4, color: 'var(--accent-green)', fontSize: '0.65rem' }}>● release</span>
                )}
                {version?.build_type === 'local' && (
                  <span style={{ marginLeft: 4, color: 'var(--accent-yellow)', fontSize: '0.65rem' }}>● local</span>
                )}
              </span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section">
            <div className="nav-section-title">Overview</div>
            <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <LayoutDashboard className="nav-icon" size={18} />
              Dashboard
            </NavLink>
            <NavLink to="/processes" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <ListTree className="nav-icon" size={18} />
              Process List
            </NavLink>
            <NavLink to="/timeline" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Clock className="nav-icon" size={18} />
              Timeline
            </NavLink>
          </div>

          <div className="nav-section">
            <div className="nav-section-title">Telemetry</div>
            <NavLink to="/process/cpu" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Cpu className="nav-icon" size={18} />
              CPU &amp; Threads
            </NavLink>
            <NavLink to="/process/memory" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Layers className="nav-icon" size={18} />
              Memory
            </NavLink>
            <NavLink to="/process/network" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Network className="nav-icon" size={18} />
              Network
            </NavLink>
            <NavLink to="/process/filesystem" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <HardDrive className="nav-icon" size={18} />
              I/O &amp; Files
            </NavLink>
          </div>

          <div className="nav-section" style={{ marginTop: 'auto' }}>
            <div className="nav-section-title">System</div>
            <NavLink to="/system" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              <Monitor className="nav-icon" size={18} />
              System Info
            </NavLink>
          </div>
        </nav>

        <div style={{
          padding: '14px 16px', borderTop: '1px solid var(--border-subtle)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8
        }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className={`status-dot ${agentOnline ? 'online' : ''}`} style={{ background: agentOnline ? 'var(--accent-green)' : 'var(--accent-red)' }}></span>
            {agentOnline ? 'Agent Online' : 'Agent Offline'}
          </div>

          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => setShowSettings(true)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 4 }}
              title="Settings"
            >
              <Settings size={15} />
            </button>
            <button
              onClick={toggleTheme}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 4 }}
              title="Toggle Theme"
            >
              {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

// ── App Root ──────────────────────────────────────────────────────────

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <div className="app-layout">
          <Sidebar />
          <main className="main-content animate-fade-in">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/processes" element={<ProcessList />} />
              <Route path="/process/:tab" element={<ProcessView />} />
              <Route path="/timeline" element={<Timeline />} />
              <Route path="/system" element={<SystemInfo />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}
