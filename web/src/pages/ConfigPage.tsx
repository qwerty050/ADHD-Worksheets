import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';

const API_BASE = 'http://localhost:8000/api';

const DEFAULT_CONFIG = {
  OLLAMA_BASE: 'http://localhost:11434',
  MODEL_EXTRACTION: 'gpt-oss:120b-cloud',
  MODEL_QUESTION_EXTRACT: 'gpt-oss:20b-cloud',
  MODEL_PEDAGOGY: 'gpt-oss:120b-cloud',
  MODEL_THEORY: 'gpt-oss:120b-cloud',
  MODEL_QUESTIONS: 'gpt-oss:120b-cloud',
  MODEL_QUESTION_FILTER: 'gpt-oss:20b-cloud',
  MODEL_REVIEW: 'gpt-oss:20b-cloud',
  MODEL_CONTEXT_SUMMARY: 'gpt-oss:20b-cloud',
  EMBED_MODEL: 'nomic-embed-text',
  TAG_MODEL: 'gemma3n:e4b',
  PAGEINDEX_MODEL: 'gemma3n:e4b',
};

export const ConfigPage: React.FC = () => {
  const navigate = useNavigate();
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/config`)
      .then(res => res.json())
      .then(data => {
        if (Object.keys(data).length > 0) {
          setConfig(prev => ({ ...prev, ...data }));
        }
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key: string, value: string) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    try {
      await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      navigate('/');
    } catch (err) {
      console.error(err);
      alert('Failed to save config');
    }
  };

  if (loading) return <div>Loading config...</div>;

  return (
    <div className="brutalist-card">
      <h2>Configuration (.env)</h2>
      
      {Object.entries(config).map(([key, value]) => (
        <div key={key}>
          <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>{key}</label>
          <input 
            type="text" 
            className="brutalist-input" 
            value={value} 
            onChange={e => handleChange(key, e.target.value)} 
          />
        </div>
      ))}

      <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
        <Button onClick={handleSave}>Save & Return</Button>
        <Button variant="secondary" onClick={() => navigate('/')}>Cancel</Button>
      </div>
    </div>
  );
};
