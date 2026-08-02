import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Cpu, HardDrive, LayoutDashboard, Network, Clock, Layers, Monitor, Moon, Sun, ListTree } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import ProcessView from './pages/ProcessView';
import Timeline from './pages/Timeline';
import SystemInfo from './pages/SystemInfo';
import ProcessList from './pages/ProcessList';
import { ThemeProvider, useTheme } from './ThemeContext';

function Sidebar() {
  const { theme, toggleTheme } = useTheme();
  
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">🔬</div>
          <div>
            <h1>ProcessScope</h1>
            <span className="version-badge">v0.1.0</span>
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
            CPU & Threads
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
            I/O & Files
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

      <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="status-dot online"></span>
          Agent Running
        </div>
        
        <button 
          onClick={toggleTheme} 
          style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          title="Toggle Theme"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </div>
    </aside>
  );
}

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
