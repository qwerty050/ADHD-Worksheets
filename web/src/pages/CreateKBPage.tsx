import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dropzone } from '../components/Dropzone';
import { useAppContext } from '../context/AppContext';

const API_BASE = 'http://localhost:8000/api';

export const CreateKBPage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId, setSessionId, kbName, setKbName } = useAppContext();
  const [localKbName, setLocalKbName] = useState('');
  const [qFile, setQFile] = useState<File | null>(null);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [mode, setMode] = useState<'chunking' | 'page_index'>('chunking');
  const [isProcessing, setIsProcessing] = useState(false);

  const initSessionAndKb = async () => {
    let sid = sessionId;
    if (!sid) {
      const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
      const data = await res.json();
      sid = data.session_id;
      setSessionId(sid);
    }
    
    if (!kbName) {
      const formData = new FormData();
      formData.append('name', localKbName || 'New_KB');
      await fetch(`${API_BASE}/sessions/${sid}/kb/create`, {
        method: 'POST',
        body: formData
      });
      setKbName(localKbName || 'New_KB');
    }
    return sid;
  };

  const handleContinue = async () => {
    setIsProcessing(true);
    try {
      const sid = await initSessionAndKb();

      if (qFile) {
        const qForm = new FormData();
        qForm.append('file', qFile);
        await fetch(`${API_BASE}/sessions/${sid}/kb/ingest_questions`, {
          method: 'POST',
          body: qForm
        });
      }

      if (pdfFile) {
        const pdfForm = new FormData();
        pdfForm.append('file', pdfFile);
        pdfForm.append('mode', mode);
        await fetch(`${API_BASE}/sessions/${sid}/kb/ingest_pdf`, {
          method: 'POST',
          body: pdfForm
        });
      }

      navigate('/lecture');
    } catch (err) {
      console.error(err);
      alert('Failed to initialize KB');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="brutalist-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Create Knowledge Base</h2>
        <Button variant="secondary" onClick={() => navigate(-1)}>Back</Button>
      </div>
      
      <div style={{ fontSize: '1rem', marginBottom: '2rem', lineHeight: '1.5', textAlign: 'left', border: '2px solid black', padding: '1rem', backgroundColor: '#fafafa', boxShadow: '4px 4px 0px #000' }}>
        Oh no, you don't have a knowledge base already? Don't worry, we'll build a fresh one for you. Just dump your reference books and past questions below. (If your questions aren't in the correct JSON format, try clicking the AI guide instead of just staring blankly at the screen).
      </div>
      <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>KB Name</label>
      <input 
        type="text" 
        className="brutalist-input" 
        placeholder="e.g. CS101_Fall24" 
        value={localKbName} 
        onChange={e => setLocalKbName(e.target.value)} 
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '2rem 0 1rem' }}>
        <h3 style={{ margin: 0 }}>Upload question in JSON</h3>
        <Button variant="accent" onClick={() => navigate('/guide')}>AI Guide</Button>
      </div>
      <Dropzone label="Questions JSON" file={qFile} onFileSelect={setQFile} accept=".json" />

      <h3 style={{ marginTop: '2rem' }}>Upload Book / Reference Material</h3>
      <Dropzone label="Reference PDF" file={pdfFile} onFileSelect={setPdfFile} accept=".pdf" />
      
      {pdfFile && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
          <input 
            type="checkbox" 
            checked={mode === 'page_index'} 
            onChange={e => setMode(e.target.checked ? 'page_index' : 'chunking')} 
            id="mode-toggle"
          />
          <label htmlFor="mode-toggle">Detailed indexing (slower)</label>
        </div>
      )}

      <div style={{ marginTop: '2rem' }}>
        <Button onClick={handleContinue} disabled={isProcessing || !localKbName}>
          {isProcessing ? 'Processing...' : 'Continue'}
        </Button>
      </div>
    </div>
  );
};
