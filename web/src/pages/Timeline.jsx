import React, { useState, useEffect, useRef } from 'react';
import { Clock, Search, Filter } from 'lucide-react';

export default function Timeline() {
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const wsRef = useRef(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // Subscribe to all processes and all categories
      ws.send(JSON.stringify({ action: 'subscribe' }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'telemetry_event' && msg.data) {
          setEvents(prev => {
            const next = [msg.data, ...prev];
            return next.slice(0, 500); // Keep last 500 events
          });
        }
      } catch (err) {}
    };

    return () => {
      ws.close();
    };
  }, []);

  const getCategoryColor = (category) => {
    const map = {
      cpu: 'blue',
      memory: 'purple',
      thread: 'cyan',
      network: 'green',
      filesystem: 'yellow',
      syscall: 'orange',
      runtime: 'red'
    };
    return map[category] || 'blue';
  };

  const filteredEvents = events.filter(e => {
    if (categoryFilter !== 'all' && e.category !== categoryFilter) return false;
    if (filter) {
      const q = filter.toLowerCase();
      return e.pid.toString().includes(q) || 
             e.category.includes(q) || 
             JSON.stringify(e.data).toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Event Timeline</h1>
          <p className="page-subtitle">Real-time stream of all telemetry events</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="badge green">
            <span className="status-dot online" style={{ width: 6, height: 6 }}></span>
            STREAMING
          </span>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '20px', padding: '16px' }}>
        <div style={{ display: 'flex', gap: '16px' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: 12, top: 10, color: 'var(--text-tertiary)' }} />
            <input 
              type="text" 
              className="input" 
              placeholder="Search events, PIDs, or data..." 
              style={{ paddingLeft: 36 }}
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
          </div>
          <div style={{ position: 'relative', width: '200px' }}>
            <Filter size={16} style={{ position: 'absolute', left: 12, top: 10, color: 'var(--text-tertiary)' }} />
            <select 
              className="input" 
              style={{ paddingLeft: 36, appearance: 'none' }}
              value={categoryFilter}
              onChange={e => setCategoryFilter(e.target.value)}
            >
              <option value="all">All Categories</option>
              <option value="cpu">CPU & Threads</option>
              <option value="memory">Memory</option>
              <option value="network">Network</option>
              <option value="filesystem">File System</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        {events.length > 0 ? (
          <div style={{ maxHeight: '650px', overflowY: 'auto', paddingRight: '10px' }}>
            {filteredEvents.map((e, i) => (
              <div key={i} className="timeline-event">
                <div className={`timeline-dot ${getCategoryColor(e.category)}`}></div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <div className="timeline-title" style={{ textTransform: 'capitalize' }}>
                      {e.category} Event
                      <span className="mono" style={{ marginLeft: 8, fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>PID {e.pid}</span>
                    </div>
                    <div className="timeline-time">{new Date(e.timestamp * 1000).toLocaleTimeString([], { hour12: false, fractionalSecondDigits: 3 })}</div>
                  </div>
                  <div className="timeline-message mono" style={{ fontSize: '0.75rem', background: 'var(--bg-hover)', padding: '4px 8px', borderRadius: '4px', marginTop: '6px' }}>
                    {JSON.stringify(e.data)}
                  </div>
                </div>
              </div>
            ))}
            {filteredEvents.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
                No events match the current filters.
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-tertiary)' }}>
            <Clock size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
            <p>No events yet — attach a process to start collecting telemetry</p>
          </div>
        )}
      </div>
    </div>
  );
}
