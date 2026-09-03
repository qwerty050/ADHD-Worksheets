import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Toggle } from '../components/Toggle';
import { useAppContext } from '../context/AppContext';

import { API_BASE } from '../api';

export const GeneratePage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId } = useAppContext();
  
  const [objective, setObjective] = useState(false);
  const [newpage, setNewpage] = useState(true);
  const [updateMemory, setUpdateMemory] = useState(true);
  const [noReuse, setNoReuse] = useState(false);
  
  const [isGenerating, setIsGenerating] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    if (isDone) {
      navigate('/download');
    }
  }, [isDone, navigate]);

  const handleGenerate = async () => {
    if (!sessionId) return;
    setIsGenerating(true);
    setLogs([]);

    try {
      const queryParams = new URLSearchParams({
        objective: objective.toString(),
        newpage_per_question: newpage.toString(),
        update_memory: updateMemory.toString(),
        reuse: noReuse ? 'never' : 'prefer'
      });

      // Start SSE listening
      const evtSource = new EventSource(`${API_BASE}/sessions/${sessionId}/generate?${queryParams.toString()}`);
      evtSource.onmessage = (event) => {
        const msg = event.data;
        if (['Processing Section', 'Generation complete', 'deferred', 'ERROR'].some((f) => msg.includes(f))) {
          setLogs(prev => [...prev, msg.replace(/---/g, '').trim()]);
        }
        if (msg === 'None' || msg.includes('ERROR:')) {
          evtSource.close();
          if (!event.data.includes('ERROR:')) {
            setIsDone(true);
          } else {
            setIsGenerating(false);
            alert("Generation failed: " + event.data);
          }
        }
      };
      evtSource.onerror = (err) => {
        console.error("EventSource failed:", err);
        evtSource.close();
        setIsGenerating(false);
      };

    } catch (err) {
      console.error(err);
      alert("Failed to start generation");
      setIsGenerating(false);
    }
  };

  return (
    <div className="brutalist-card">
      <h2 style={{ textAlign: 'center' }}>Generate + Options</h2>
      
      <div style={{ margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', width: 'fit-content', textAlign: 'left' }}>
        <div>
          <Toggle label="Objective / MCQ mode" checked={objective} onChange={setObjective} />
          <p style={{ margin: '0.25rem 0 0 3.5rem', fontSize: '0.85rem', color: '#555' }}>Converts all generated questions into 4-option MCQs. (For those who hate writing out long answers).</p>
        </div>
        <div>
          <Toggle label="Never repeat PYQs" checked={noReuse} onChange={setNoReuse} />
          <p style={{ margin: '0.25rem 0 0 3.5rem', fontSize: '0.85rem', color: '#555' }}>Strictly excludes past-year questions the memory has already served in a previous worksheet. Off (default), used PYQs only come back once a topic's fresh pool runs dry.</p>
        </div>
        <div>
          <Toggle label="New page per question" checked={newpage} onChange={setNewpage} />
          <p style={{ margin: '0.25rem 0 0 3.5rem', fontSize: '0.85rem', color: '#555' }}>Forces the compiler to put every question on a shiny new page so you have plenty of room to scribble.</p>
        </div>
        <div>
          <Toggle label="Update memory after generation" checked={updateMemory} onChange={setUpdateMemory} />
          <p style={{ margin: '0.25rem 0 0 3.5rem', fontSize: '0.85rem', color: '#555' }}>Commits the parsed lecture back into the knowledge base so it organically remembers it next week. Turn off for dry runs.</p>
        </div>
      </div>

      {!isGenerating && !isDone && (
        <div style={{ textAlign: 'center' }}>
          <Button onClick={handleGenerate}>Generate</Button>
        </div>
      )}

      {isGenerating && (
        <div style={{ marginTop: '2rem', padding: '1rem', backgroundColor: '#171e19', color: '#fff', height: '300px', overflowY: 'auto', fontFamily: 'monospace', borderRadius: '8px' }}>
          {logs.map((log, i) => (
            <div key={i}>{log !== 'None' ? log : 'Done!'}</div>
          ))}
          <div style={{ marginTop: '1rem' }}>Generating... please wait.</div>
        </div>
      )}
    </div>
  );
};
