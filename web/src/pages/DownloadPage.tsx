import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { ExcuseBanner } from '../components/ExcuseBanner';
import { useAppContext } from '../context/AppContext';

import { API_BASE, apiFetch } from '../api';

export const DownloadPage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId } = useAppContext();

  const downloadFile = async (type: 'worksheet' | 'cmkb') => {
    if (!sessionId) return;
    window.open(`${API_BASE}/sessions/${sessionId}/download/${type}`, '_blank');
  };

  const handleStartOver = async () => {
    if (sessionId) {
      try {
        await apiFetch(`/sessions/${sessionId}`, { method: 'DELETE' });
      } catch { /* session may already be gone */ }
    }
    navigate('/');
    window.location.reload();
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', flexDirection: 'column' }}>
      <div className="brutalist-card" style={{ textAlign: 'center' }}>
        <ExcuseBanner role="The team responsible for generating the PDF and storing your data" />
        
        <p style={{ marginBottom: '1rem' }}>
          Here is your generated worksheet and updated memory. Since we don't have a backend to store your memory or a formatter to build your PDF, please download them below and keep them safe!
        </p>

        <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
          <Button onClick={() => downloadFile('worksheet')}>Download Worksheet (.json)</Button>
          <Button variant="accent" onClick={() => downloadFile('cmkb')}>Download KB</Button>
        </div>

        <p style={{ marginTop: '2rem', fontSize: '0.9rem', fontWeight: 'bold', borderTop: '2px solid black', paddingTop: '1rem' }}>
          The worksheet is structured JSON: every section's theory, questions and answers, with no formatting applied yet. Turning it into a printable LaTeX/PDF worksheet is a separate formatting step that this app does not run yet.
        </p>
      </div>

      <div style={{ textAlign: 'center', marginTop: '2rem' }}>
        <Button variant="secondary" onClick={handleStartOver}>Start Over</Button>
      </div>
      
    </div>
  );
};
