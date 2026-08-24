import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dropzone } from '../components/Dropzone';
import { useAppContext } from '../context/AppContext';

const API_BASE = 'http://localhost:8000/api';

export const UploadLecturePage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId, setLectureId } = useAppContext();
  const [localLectureId, setLocalLectureId] = useState('L01');
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleContinue = async () => {
    if (!sessionId) {
      alert("Session lost. Please start over.");
      navigate('/');
      return;
    }
    
    if (!pdfFile && !jsonText.trim()) {
      alert("Please provide either a PDF or pasted JSON.");
      return;
    }

    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append('lecture_id', localLectureId);
      if (jsonText.trim()) {
        formData.append('json_text', jsonText);
      } else if (pdfFile) {
        formData.append('pdf_file', pdfFile);
      }

      await fetch(`${API_BASE}/sessions/${sessionId}/extract`, {
        method: 'POST',
        body: formData
      });
      
      setLectureId(localLectureId);
      navigate('/generate');
    } catch (err) {
      console.error(err);
      alert('Extraction failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="brutalist-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Upload Lecture</h2>
        <Button variant="secondary" onClick={() => navigate(-1)}>Back</Button>
      </div>
      
      <label style={{ fontWeight: 'bold', display: 'block', marginBottom: '0.5rem' }}>Lecture ID</label>
      <input 
        type="text" 
        className="brutalist-input" 
        value={localLectureId} 
        onChange={e => setLocalLectureId(e.target.value)} 
      />

      <h3 style={{ marginTop: '1rem' }}>PDF Upload</h3>
      <Dropzone label="Lecture PDF" file={pdfFile} onFileSelect={setPdfFile} accept=".pdf" />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '2rem 0 1rem' }}>
        <div>
          <p style={{ fontWeight: 'bold', margin: 0 }}>
            PSST. you can use AI ChatBots for extraction.
          </p>
          <span style={{ cursor: 'pointer', textDecoration: 'underline', fontSize: '0.9rem' }} onClick={() => navigate('/guide')}>
            paste JSON here
          </span>
        </div>
        <Button variant="accent" onClick={() => navigate('/guide')}>AI Guide</Button>
      </div>

      <textarea 
        className="brutalist-input" 
        placeholder='{ "section_map": [ ... ] }' 
        value={jsonText} 
        onChange={e => setJsonText(e.target.value)}
      />

      <div style={{ marginTop: '2rem' }}>
        <Button onClick={handleContinue} disabled={isProcessing || (!pdfFile && !jsonText.trim())}>
          {isProcessing ? 'Extracting (This takes a while)...' : 'Continue'}
        </Button>
      </div>
    </div>
  );
};
