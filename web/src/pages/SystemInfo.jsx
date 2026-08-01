import React, { useState, useEffect } from 'react';
import { Monitor, Cpu, HardDrive, Network, Clock, Info } from 'lucide-react';

const API_BASE = '/api/v1';

function InfoCard({ title, icon: Icon, children }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Icon size={18} style={{ opacity: 0.7 }} />
          {title}
        </div>
      </div>
      <div>{children}</div>
    </div>
  );
}

export default function SystemInfo() {
  const [sysInfo, setSysInfo] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchSysInfo() {
      try {
        const res = await fetch(`${API_BASE}/system/info`);
        if (res.ok) {
          const data = await res.json();
          setSysInfo(data);
        } else {
          setError('Failed to fetch system info');
        }
      } catch (err) {
        setError(err.message);
      }
    }
    
    fetchSysInfo();
    const interval = setInterval(fetchSysInfo, 10000); // Update every 10s
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return <div style={{ color: 'var(--accent-red)' }}>Error: {error}</div>;
  }

  if (!sysInfo) {
    return <div>Loading system info...</div>;
  }

  const { os, cpu, memory, disk, network, load_avg, uptime_seconds, boot_time, users, process_count } = sysInfo;

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatUptime = (seconds) => {
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">System Information</h1>
          <p className="page-subtitle">OS and hardware overview</p>
        </div>
      </div>

      <div className="grid-2">
        <InfoCard title="Operating System" icon={Info}>
          <table className="data-table">
            <tbody>
              <tr>
                <td style={{ width: '120px' }}>Hostname</td>
                <td className="mono">{os.hostname}</td>
              </tr>
              <tr>
                <td>OS</td>
                <td>{os.system} {os.release}</td>
              </tr>
              <tr>
                <td>Kernel</td>
                <td className="mono">{os.version}</td>
              </tr>
              <tr>
                <td>Architecture</td>
                <td className="mono">{os.machine}</td>
              </tr>
              <tr>
                <td>Boot Time</td>
                <td>{boot_time}</td>
              </tr>
              <tr>
                <td>Uptime</td>
                <td>{formatUptime(uptime_seconds)}</td>
              </tr>
              <tr>
                <td>Users Logged In</td>
                <td>{users ? users.length : 0}</td>
              </tr>
              <tr>
                <td>Total Processes</td>
                <td className="mono">{process_count}</td>
              </tr>
            </tbody>
          </table>
        </InfoCard>

        <InfoCard title="Processor" icon={Cpu}>
          <table className="data-table">
            <tbody>
              <tr>
                <td style={{ width: '120px' }}>Model</td>
                <td>{os.processor || 'Unknown'}</td>
              </tr>
              <tr>
                <td>Physical Cores</td>
                <td className="mono">{cpu.physical_cores}</td>
              </tr>
              <tr>
                <td>Logical Cores</td>
                <td className="mono">{cpu.total_cores}</td>
              </tr>
              <tr>
                <td>Max Frequency</td>
                <td className="mono">{cpu.max_frequency ? `${cpu.max_frequency.toFixed(0)} MHz` : 'N/A'}</td>
              </tr>
              <tr>
                <td>Load Average</td>
                <td className="mono">{load_avg.map(v => v.toFixed(2)).join('  ')}</td>
              </tr>
            </tbody>
          </table>
        </InfoCard>

        <InfoCard title="Memory & Storage" icon={HardDrive}>
          <table className="data-table">
            <tbody>
              <tr>
                <td style={{ width: '120px' }}>Total RAM</td>
                <td className="mono">{formatBytes(memory.total)}</td>
              </tr>
              <tr>
                <td>Available RAM</td>
                <td className="mono">{formatBytes(memory.available)} <span style={{ color: 'var(--text-tertiary)' }}>({(100 - memory.percent).toFixed(1)}%)</span></td>
              </tr>
              {memory.swap_total > 0 && (
                <>
                  <tr>
                    <td>Swap Total</td>
                    <td className="mono">{formatBytes(memory.swap_total)}</td>
                  </tr>
                  <tr>
                    <td>Swap Free</td>
                    <td className="mono">{formatBytes(memory.swap_free)} <span style={{ color: 'var(--text-tertiary)' }}>({(100 - memory.swap_percent).toFixed(1)}%)</span></td>
                  </tr>
                </>
              )}
              <tr>
                <td>Root Disk Total</td>
                <td className="mono">{formatBytes(disk.total)}</td>
              </tr>
              <tr>
                <td>Root Disk Free</td>
                <td className="mono">{formatBytes(disk.free)} <span style={{ color: 'var(--text-tertiary)' }}>({(100 - disk.percent).toFixed(1)}%)</span></td>
              </tr>
            </tbody>
          </table>
        </InfoCard>

        <InfoCard title="Network Interfaces" icon={Network}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Interface</th>
                <th>IP Address</th>
                <th>Speed (Mbps)</th>
              </tr>
            </thead>
            <tbody>
              {network.map(net => (
                <tr key={net.name}>
                  <td className="mono">{net.name}</td>
                  <td className="mono">{net.ip || '-'}</td>
                  <td className="mono">{net.speed > 0 ? net.speed : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </InfoCard>
      </div>
    </div>
  );
}
