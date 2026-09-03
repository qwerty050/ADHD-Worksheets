import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dropzone } from '../components/Dropzone';
import { apiFetch, apiPostForm } from '../api';
import { useAppContext } from '../context/AppContext';

interface KbStats {
  name: string | null;
  questions: number;
  exams: number;
  topic_clusters: number;
  sections: number;
  lectures: number;
  document_chunks: number;
  total_questions: number;
  used_questions: number;
  embed_model: string | null;
}

/**
 * Manage an existing KB: inspect it, add more questions/PDFs, re-cluster.
 * Reached after uploading a .cmkb or after creating one.
 */
export const KBManagePage: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId, kbName } = useAppContext();
  const [stats, setStats] = useState<KbStats | null>(null);
  const [qFiles, setQFiles] = useState<File[]>([]);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'chunking' | 'page_index'>('chunking');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshStats = useCallback(async () => {
    if (!sessionId) return;
    try {
      setStats(await apiFetch(`/sessions/${sessionId}/kb`));
    } catch (err: any) {
      setError(err.message);
    }
  }, [sessionId]);

  useEffect(() => { refreshStats(); }, [refreshStats]);

  if (!sessionId) {
    return (
      <div className="brutalist-card" style={{ textAlign: 'center' }}>
        <h2>No Session</h2>
        <p style={{ margin: '1rem 0 2rem' }}>Upload or create a knowledge base first.</p>
        <Button onClick={() => navigate('/select-kb')}>Go to KB selection</Button>
      </div>
    );
  }

  const ingest = async (kind: 'questions' | 'pdf') => {
    setError(null);
    const files = kind === 'questions' ? qFiles : pdfFiles;
    if (files.length === 0) return;
    setBusy(kind === 'questions' ? 'Ingesting questions (tagging topics)...' : 'Ingesting PDFs (chunking + embedding)...');
    try {
      for (const file of files) {
        const form = new FormData();
        form.append('files', file);
        if (kind === 'pdf') form.append('mode', mode);
        await apiPostForm(`/sessions/${sessionId}/kb/ingest_${kind}`, form);
      }
      if (kind === 'questions') setQFiles([]);
      else setPdfFiles([]);
      await refreshStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const recluster = async () => {
    setError(null);
    setBusy('Re-clustering topics (embedding + aliasing)...');
    try {
      await apiFetch(`/sessions/${sessionId}/kb/cluster`, { method: 'POST' });
      await refreshStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="brutalist-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Knowledge Base: {stats?.name ?? kbName ?? '...'}</h2>
        <Button variant="secondary" onClick={() => navigate('/select-kb')}>Back</Button>
      </div>

      {stats && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '2rem' }}>
          {[
            ['Questions', stats.questions],
            ['Exams', stats.exams],
            ['Topic clusters', stats.topic_clusters],
            ['PYQs already used', `${stats.used_questions}/${stats.total_questions}`],
            ['Book chunks', stats.document_chunks],
            ['Sections learned', stats.sections],
            ['Lectures seen', stats.lectures],
          ].map(([label, value]) => (
            <div key={String(label)} style={{ border: '2px solid black', padding: '0.75rem 1rem', backgroundColor: '#fafafa', boxShadow: '3px 3px 0px #000', minWidth: '120px' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{String(value)}</div>
              <div style={{ fontSize: '0.8rem', color: '#555' }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      <h3>Add more questions (JSON)</h3>
      <Dropzone label="Questions JSON" files={qFiles} onFilesSelect={setQFiles} accept=".json" multiple={true} />
      <div style={{ marginTop: '1rem' }}>
        <Button onClick={() => ingest('questions')} disabled={busy !== null || qFiles.length === 0}>
          Add questions
        </Button>
      </div>

      <h3 style={{ marginTop: '2rem' }}>Add book / reference material (PDF)</h3>
      <Dropzone label="Reference PDF" files={pdfFiles} onFilesSelect={setPdfFiles} accept=".pdf" multiple={true} />
      {pdfFiles.length > 0 && (
        <div style={{ margin: '0.5rem 0' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input type="checkbox" checked={mode === 'page_index'} onChange={e => setMode(e.target.checked ? 'page_index' : 'chunking')} />
            Detailed indexing (PageIndex) — slower, more tokens
          </label>
        </div>
      )}
      <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
        <Button onClick={() => ingest('pdf')} disabled={busy !== null || pdfFiles.length === 0}>
          Add PDFs
        </Button>
        <Button variant="secondary" onClick={recluster} disabled={busy !== null}>
          Re-cluster topics
        </Button>
      </div>

      {busy && (
        <div style={{ marginTop: '2rem', padding: '1rem', border: '2px solid black', backgroundColor: '#ffffe0', boxShadow: '4px 4px 0px #000', fontWeight: 'bold' }}>
          {busy}
        </div>
      )}
      {error && (
        <div style={{ marginTop: '1rem', padding: '1rem', border: '2px solid black', backgroundColor: '#ffe0e0', boxShadow: '4px 4px 0px #000' }}>
          {error}
        </div>
      )}

      <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'center' }}>
        <Button variant="primary" onClick={() => navigate('/lecture')} disabled={busy !== null}>
          Continue to lecture
        </Button>
      </div>
    </div>
  );
};
