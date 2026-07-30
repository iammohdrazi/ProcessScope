import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

const API_BASE = '/api/v1';

export default function Timeline() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    async function fetchTimeline() {
      try {
        const res = await fetch(`${API_BASE}/timeline/summary`);
        if (res.ok) {
          const data = await res.json();
          setEvents(data.buckets || []);
        }
      } catch { /* API not ready */ }
    }
    fetchTimeline();
    const interval = setInterval(fetchTimeline, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Event Timeline</h1>
          <p className="page-subtitle">Synchronized historical view of all telemetry events</p>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><Clock size={16} /> Live Timeline</div>
          <span className="badge green">STREAMING</span>
        </div>

        {events.length > 0 ? (
          <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
            {events.map((bucket, i) => (
              <div key={i} className="timeline-event">
                <div className="timeline-dot cpu"></div>
                <div>
                  <div className="timeline-time">{new Date(bucket.timestamp * 1000).toLocaleTimeString()}</div>
                  <div className="timeline-title">{bucket.total} events</div>
                  <div className="timeline-message">
                    {Object.entries(bucket).filter(([k]) => k !== 'timestamp' && k !== 'total').map(([k, v]) => `${k}: ${v}`).join(' · ')}
                  </div>
                </div>
              </div>
            ))}
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
