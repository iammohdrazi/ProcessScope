import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Cpu, HardDrive, LayoutDashboard, Network, Search, Clock, Layers, Settings } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import ProcessView from './pages/ProcessView';
import Timeline from './pages/Timeline';

function Sidebar() {
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
          <NavLink to="/timeline" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Clock className="nav-icon" size={18} />
            Timeline
          </NavLink>
        </div>

        <div className="nav-section">
          <div className="nav-section-title">Telemetry</div>
          <NavLink to="/process/cpu" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Cpu className="nav-icon" size={18} />
            CPU
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
            File System
          </NavLink>
          <NavLink to="/process/activity" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Activity className="nav-icon" size={18} />
            Activity
          </NavLink>
        </div>

        <div className="nav-section" style={{ marginTop: 'auto' }}>
          <div className="nav-section-title">System</div>
          <NavLink to="/search" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Search className="nav-icon" size={18} />
            Search
          </NavLink>
          <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Settings className="nav-icon" size={18} />
            Settings
          </NavLink>
        </div>
      </nav>

      <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border-subtle)', fontSize: '0.7rem', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="status-dot online"></span>
          Agent Running
        </div>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content animate-fade-in">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/process/:tab" element={<ProcessView />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/search" element={<Dashboard />} />
            <Route path="/settings" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
