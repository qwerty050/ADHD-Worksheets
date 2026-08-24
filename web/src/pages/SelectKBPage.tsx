import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useAppContext } from '../context/AppContext';

const API_BASE = 'http://localhost:8000/api';

export const SelectKBPage: React.FC = () => {
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Knowledge Base</h2>
        <Button variant="secondary" onClick={() => navigate(-1)}>Back</Button>
      </div>
      <div style={{ fontSize: '1rem', marginBottom: '2rem', lineHeight: '1.5', textAlign: 'left', border: '2px solid black', padding: '1rem', backgroundColor: '#fafafa', boxShadow: '4px 4px 0px #000' }}>
        <strong>This is the heart of our app.</strong> A custom data store where all the Past Year Questions (PYQs) and reference books live. We use this context to ground your generated worksheets in reality so you aren't stuck flipping through three different PDFs. You literally cannot proceed without one.
      </div>
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
