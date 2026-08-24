import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Toggle } from '../components/Toggle';
import { useAppContext } from '../context/AppContext';

const API_BASE = 'http://localhost:8000/api';

export const GeneratePage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId } = useAppContext();
  
  const [objective, setObjective] = useState(false);
  const [review, setReview] = useState(true);
  const [newpage, setNewpage] = useState(true);
  const [updateMemory, setUpdateMemory] = useState(true);
  
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
        review: review.toString(),
        newpage_per_question: newpage.toString(),
        update_memory: updateMemory.toString()
      });

      // Start SSE listening
      const evtSource = new EventSource(`${API_BASE}/sessions/${sessionId}/generate?${queryParams.toString()}`);
      evtSource.onmessage = (event) => {
        const msg = event.data;
        if (msg.includes('Processing Section') || msg.includes('Generation complete!')) {
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
      
      <div style={{ margin: '2rem auto', display: 'flex', flexDirection: 'column', width: 'fit-content' }}>
        <Toggle label="Objective / MCQ mode" checked={objective} onChange={setObjective} />
        <Toggle label="Review pass" checked={review} onChange={setReview} />
        <Toggle label="New page per question" checked={newpage} onChange={setNewpage} />
        <Toggle label="Update memory after generation" checked={updateMemory} onChange={setUpdateMemory} />
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
