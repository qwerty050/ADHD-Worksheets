import React, { useRef } from 'react';
import { X } from 'lucide-react';

interface DropzoneProps {
  label: string;
  onFileSelect: (file: File | null) => void;
  file: File | null;
  accept?: string;
}

export const Dropzone: React.FC<DropzoneProps> = ({ label, onFileSelect, file, accept }) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClick = () => {
    if (!file && inputRef.current) {
      inputRef.current.click();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFileSelect(e.target.files[0]);
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileSelect(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div 
      className={`brutalist-dropzone ${file ? 'has-file' : ''}`} 
      onClick={handleClick}
    >
      <input 
        type="file" 
        ref={inputRef} 
        onChange={handleFileChange} 
        style={{ display: 'none' }}
        accept={accept}
      />
      
      {!file ? (
        <div>
          <h4>{label}</h4>
          <p>Click to upload or drag & drop</p>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h4>{file.name}</h4>
          <button 
            onClick={handleClear}
            style={{ 
              background: 'none', 
              border: 'none', 
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <X size={24} />
          </button>
        </div>
      )}
    </div>
  );
};
