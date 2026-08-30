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
  const [qFiles, setQFiles] = useState<File[]>([]);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'chunking' | 'page_index'>('chunking');
  const [isProcessing, setIsProcessing] = useState(false);
  const [progressMessage, setProgressMessage] = useState('');
  const [isSuccess, setIsSuccess] = useState(false);

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
    setIsSuccess(false);
    try {
      setProgressMessage('Waking up the server hamsters...');
      const sid = await initSessionAndKb();

      if (qFiles.length > 0) {
        for (let i = 0; i < qFiles.length; i++) {
          let qCount = 'some';
          try {
            const text = await qFiles[i].text();
            const json = JSON.parse(text);
            if (Array.isArray(json)) qCount = json.length.toString();
            else if (json.questions && Array.isArray(json.questions)) qCount = json.questions.length.toString();
            else qCount = Object.keys(json).length.toString();
          } catch(e) {}

          const messages = [
            `Source ${i + 1}/${qFiles.length}: found ${qCount} questions from ${qFiles[i].name}`,
            `Source ${i + 1}/${qFiles.length}: reading`,
            `Source ${i + 1}/${qFiles.length}: judging your question quality`,
            `Source ${i + 1}/${qFiles.length}: adding to KB`
          ];
          
          let msgIdx = 0;
          setProgressMessage(messages[0]);
          const timer = setInterval(() => {
            msgIdx = (msgIdx + 1) % messages.length;
            setProgressMessage(messages[msgIdx]);
          }, 1500);

          const qForm = new FormData();
          qForm.append('files', qFiles[i]);
          await fetch(`${API_BASE}/sessions/${sid}/kb/ingest_questions`, {
            method: 'POST',
            body: qForm
          });
          clearInterval(timer);
        }
      }

      if (pdfFiles.length > 0) {
        for (let i = 0; i < pdfFiles.length; i++) {
          const messages = [
            `Source ${i + 1}/${pdfFiles.length}: analyzing ${pdfFiles[i].name}`,
            `Source ${i + 1}/${pdfFiles.length}: reading`,
            `Source ${i + 1}/${pdfFiles.length}: pretending to understand`,
            `Source ${i + 1}/${pdfFiles.length}: adding to KB`
          ];

          let msgIdx = 0;
          setProgressMessage(messages[0]);
          const timer = setInterval(() => {
            msgIdx = (msgIdx + 1) % messages.length;
            setProgressMessage(messages[msgIdx]);
          }, 1500);

          const pdfForm = new FormData();
          pdfForm.append('files', pdfFiles[i]);
          pdfForm.append('mode', mode);
          await fetch(`${API_BASE}/sessions/${sid}/kb/ingest_pdf`, {
            method: 'POST',
            body: pdfForm
          });
          clearInterval(timer);
        }
      }

      setProgressMessage('Clustering the chaos into a structured knowledge base');
      await fetch(`${API_BASE}/sessions/${sid}/kb/cluster`, {
        method: 'POST'
      });

      setIsSuccess(true);
    } catch (err) {
      console.error(err);
      alert('Failed to initialize KB. The hamsters might be on strike.');
    } finally {
      setIsProcessing(false);
      setProgressMessage('');
    }
  };

  if (isSuccess) {
    return (
      <div className="brutalist-card" style={{ textAlign: 'center' }}>
        <h2>Knowledge Base Forged!</h2>
        <div style={{ fontSize: '1rem', marginBottom: '2rem', lineHeight: '1.5', textAlign: 'center', border: '2px solid black', padding: '1rem', backgroundColor: '#fafafa', boxShadow: '4px 4px 0px #000' }}>
          Your digital brain has been successfully created. We sacrificed a few gigabytes of RAM to read through your stuff, so please don't let it go to waste. What would you like to do now?
        </div>
        <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem', justifyContent: 'center' }}>
          <Button variant="secondary" onClick={() => window.open(`${API_BASE}/sessions/${sessionId}/download/cmkb`, '_blank')}>
            Download this KB
          </Button>
          <Button variant="primary" onClick={() => navigate('/lecture')}>
            Use this KB to generate worksheet
          </Button>
        </div>
      </div>
    );
  }

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
      <Dropzone label="Questions JSON" files={qFiles} onFilesSelect={setQFiles} accept=".json" multiple={true} />

      <h3 style={{ marginTop: '2rem' }}>Upload Book / Reference Material</h3>
      <Dropzone label="Reference PDF" files={pdfFiles} onFilesSelect={setPdfFiles} accept=".pdf" multiple={true} />

      {pdfFiles.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="checkbox"
              checked={mode === 'page_index'}
              onChange={e => setMode(e.target.checked ? 'page_index' : 'chunking')}
              id="mode-toggle"
            />
            <label htmlFor="mode-toggle">Detailed indexing (PageIndex)</label>
          </div>
          <p style={{ fontSize: '0.8rem', color: '#555', marginTop: '0.25rem', marginLeft: '1.5rem', marginBottom: 0 }}>
            Note: This uses PageIndex for deeper extraction. It is slower and will consume significantly more AI tokens.
          </p>
        </div>
      )}

      {isProcessing && (
        <div style={{ marginTop: '2rem', padding: '1rem', border: '2px solid black', backgroundColor: '#ffffe0', boxShadow: '4px 4px 0px #000', fontWeight: 'bold' }}>
          {progressMessage}
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
