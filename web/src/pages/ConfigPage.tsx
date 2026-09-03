import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';

import { apiFetch } from '../api';

const DEFAULT_CONFIG = {
  LLM_PROVIDER: 'ollama',
  OLLAMA_BASE: 'http://localhost:11434',
  ANTHROPIC_API_KEY: '',
  OPENAI_API_KEY: '',
  GEMINI_API_KEY: '',
  ANTHROPIC_MAX_TOKENS: '16384',
  MODEL_EXTRACTION: 'gpt-oss:120b-cloud',
  MODEL_PEDAGOGY: 'gpt-oss:120b-cloud',
  MODEL_WRITER: 'gpt-oss:120b-cloud',
  MODEL_QUESTIONS: 'gpt-oss:120b-cloud',
  EMBED_MODEL: 'nomic-embed-text',
  TAG_MODEL: 'gemma3n:e4b',
  PAGEINDEX_MODEL: 'gemma3n:e4b',
};

export const ConfigPage: React.FC = () => {
  const navigate = useNavigate();
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/config')
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
      await apiFetch('/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      alert('Config saved. Restart the backend server for provider/model changes to take effect.');
      navigate('/');
    } catch (err) {
      console.error(err);
      alert('Failed to save config: ' + (err as Error).message);
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
