import React, { useState, useEffect, useMemo } from 'react';
import { Search, ChevronRight, ChevronDown, Activity, Users, Hash, Shield } from 'lucide-react';

const API_BASE = '/api/v1';

// Recursive component for rendering process tree rows
const ProcessTreeNode = ({ node, level, expanded, toggleExpand, searchQuery }) => {
  const isExpanded = expanded.has(node.pid);

  return (
    <>
      <tr className="process-row">
        <td style={{ paddingLeft: `${level * 20 + 10}px`, display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border-subtle)' }}>
          {node.children && node.children.length > 0 ? (
            <button 
              onClick={() => toggleExpand(node.pid)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', padding: '2px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
          ) : (
            <span style={{ width: '16px', display: 'inline-block' }}></span> // Spacer
          )}
          <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 500, fontSize: '0.9rem' }}>
            {node.name || 'Unknown'}
          </span>
        </td>
        <td className="mono" style={{ borderBottom: '1px solid var(--border-subtle)' }}>{node.pid}</td>
        <td className="mono" style={{ color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)' }}>{node.ppid}</td>
        <td className="mono" style={{ borderBottom: '1px solid var(--border-subtle)' }}>{node.username || '-'}</td>
        <td style={{ borderBottom: '1px solid var(--border-subtle)' }}>
          <span className={`badge ${node.status === 'running' ? 'green' : node.status === 'sleeping' ? 'blue' : 'gray'}`}>
            {node.status || 'unknown'}
          </span>
        </td>
      </tr>
      {isExpanded && node.children && node.children.map(child => (
        <ProcessTreeNode 
          key={child.pid} 
          node={child} 
          level={level + 1} 
          expanded={expanded} 
          toggleExpand={toggleExpand} 
        />
      ))}
    </>
  );
};

export default function ProcessList() {
  const [treeData, setTreeData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  
  // Set of PIDs that are currently expanded
  const [expanded, setExpanded] = useState(new Set());

  const toggleExpand = (pid) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(pid)) {
        next.delete(pid);
      } else {
        next.add(pid);
      }
      return next;
    });
  };

  const fetchProcessTree = async () => {
    try {
      const res = await fetch(`${API_BASE}/system/tree`);
      if (res.ok) {
        const data = await res.json();
        setTreeData(data.tree || []);
        setError(null);
      } else {
        setError('Failed to fetch process tree');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProcessTree();
    const interval = setInterval(fetchProcessTree, 5000);
    return () => clearInterval(interval);
  }, []);

  // Filter tree data based on search
  const filterTree = (nodes, query) => {
    if (!query) return nodes;
    
    const q = query.toLowerCase();
    const filtered = [];
    
    for (const node of nodes) {
      // Check if node itself matches
      const matches = 
        (node.name && node.name.toLowerCase().includes(q)) || 
        (node.pid.toString().includes(q)) ||
        (node.username && node.username.toLowerCase().includes(q));
      
      // Check if any children match
      const filteredChildren = filterTree(node.children || [], query);
      
      if (matches || filteredChildren.length > 0) {
        filtered.push({ ...node, children: filteredChildren });
      }
    }
    
    return filtered;
  };

  const filteredData = useMemo(() => filterTree(treeData, search), [treeData, search]);

  // Auto-expand all nodes when searching, but preserve manual state when not searching
  const effectiveExpanded = useMemo(() => {
    if (search) {
      const allExpanded = new Set();
      const addAll = (nodes) => {
        nodes.forEach(n => {
          if (n.children && n.children.length > 0) {
            allExpanded.add(n.pid);
            addAll(n.children);
          }
        });
      };
      addAll(filteredData);
      return allExpanded;
    }
    return expanded;
  }, [search, filteredData, expanded]);

  return (
    <div className="animate-fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header" style={{ flexShrink: 0 }}>
        <div>
          <h1 className="page-title">Process List</h1>
          <p className="page-subtitle">Real-time system process tree</p>
        </div>
        
        <div style={{ position: 'relative' }}>
          <Search size={18} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
          <input 
            type="text" 
            placeholder="Search processes..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              padding: '8px 12px 8px 36px',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              width: '250px',
              fontFamily: 'inherit',
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => e.target.style.borderColor = 'var(--accent-blue)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--border-subtle)'}
          />
        </div>
      </div>

      {error ? (
        <div style={{ color: 'var(--accent-red)', padding: '20px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
          <strong>Error:</strong> {error}
        </div>
      ) : loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
          <Activity size={24} className="spin" style={{ color: 'var(--accent-blue)', marginRight: '8px' }} />
          Loading processes...
        </div>
      ) : (
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-primary)', zIndex: 10 }}>
                <tr>
                  <th style={{ textAlign: 'left', paddingLeft: '32px', borderBottom: '1px solid var(--border-subtle)' }}>Process Name</th>
                  <th style={{ width: '100px', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Hash size={14} /> PID</div></th>
                  <th style={{ width: '100px', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Hash size={14} /> PPID</div></th>
                  <th style={{ width: '150px', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Users size={14} /> User</div></th>
                  <th style={{ width: '120px', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Shield size={14} /> Status</div></th>
                </tr>
              </thead>
              <tbody>
                {filteredData.length > 0 ? (
                  filteredData.map(node => (
                    <ProcessTreeNode 
                      key={node.pid} 
                      node={node} 
                      level={0} 
                      expanded={effectiveExpanded} 
                      toggleExpand={search ? () => {} : toggleExpand} // Disable manual toggle during search
                    />
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
                      No processes found matching "{search}"
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
