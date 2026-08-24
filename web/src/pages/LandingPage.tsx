import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="brutalist-card" style={{ textAlign: 'center' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>ADHD Worksheets</h1>
      <p style={{ fontSize: '1.2rem', marginBottom: '2rem' }}>
        Transforms your lecture slides into worksheets grounded in your textbooks and matching PYQs. Everything you need to learn in one place. Zero context switching.
      </p>
      
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        margin: '2rem auto',
        padding: '1.5rem',
        border: '2px solid black',
        backgroundColor: '#fafafa',
        textAlign: 'left',
        maxWidth: '400px'
      }}>
        <h3 style={{ margin: '0 0 1.5rem 0', textAlign: 'center', fontSize: '1.3rem' }}>How it works</h3>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontWeight: 'bold', fontSize: '1.1rem' }}>
          <div style={{ minWidth: '2.5rem', height: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--color-primary)', border: '2px solid black', borderRadius: '50%' }}>1</div>
          <span>Configure Models</span>
        </div>
        
        <div style={{ borderLeft: '2px solid black', margin: '0.2rem 0 0.2rem 1.15rem', height: '1.5rem' }}></div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontWeight: 'bold', fontSize: '1.1rem' }}>
          <div style={{ minWidth: '2.5rem', height: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--color-accent)', border: '2px solid black', borderRadius: '50%' }}>2</div>
          <span>Bring or create a Memory (KB)</span>
        </div>
        
        <div style={{ borderLeft: '2px solid black', margin: '0.2rem 0 0.2rem 1.15rem', height: '1.5rem' }}></div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontWeight: 'bold', fontSize: '1.1rem' }}>
          <div style={{ minWidth: '2.5rem', height: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--color-primary)', border: '2px solid black', borderRadius: '50%' }}>3</div>
          <span>Upload your Lecture Slides</span>
        </div>
        
        <div style={{ borderLeft: '2px solid black', margin: '0.2rem 0 0.2rem 1.15rem', height: '1.5rem' }}></div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontWeight: 'bold', fontSize: '1.1rem' }}>
          <div style={{ minWidth: '2.5rem', height: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--color-accent)', border: '2px solid black', borderRadius: '50%' }}>4</div>
          <span>Download Worksheet!</span>
        </div>
      </div>

      <div style={{ marginTop: '2.5rem' }}>
        <Button variant="accent" onClick={() => navigate('/select-kb')}>Get Started</Button>
      </div>
    </div>
  );
};
