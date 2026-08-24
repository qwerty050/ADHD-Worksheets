import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useAppContext } from '../context/AppContext';

const API_BASE = 'http://localhost:8000/api';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { setSessionId, setKbName } = useAppContext();
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const initSession = async () => {
    const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
    const data = await res.json();
    setSessionId(data.session_id);
    return data.session_id;
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        const sid = await initSession();
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(`${API_BASE}/sessions/${sid}/kb/upload`, {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        setKbName(data.kb_name);
        navigate('/lecture');
      } catch (err) {
        console.error(err);
        alert('Failed to upload KB');
      }
    }
  };

  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleCreateClick = async () => {
    navigate('/create-kb');
  };

  return (
    <div className="brutalist-card" style={{ textAlign: 'center' }}>
      <h1>ADHD Worksheets</h1>
      <p style={{ fontSize: '1.2rem', marginBottom: '2rem' }}>
        Bring an existing course memory, or start a new one.
      </p>
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
        <input 
          type="file" 
          ref={fileInputRef} 
          style={{ display: 'none' }} 
          accept=".cmkb" 
          onChange={handleFileChange} 
        />
        <Button onClick={handleUploadClick}>Upload KB</Button>
        <Button variant="accent" onClick={handleCreateClick}>Create New</Button>
      </div>
    </div>
  );
};
