import React, { useRef } from 'react';
import { X } from 'lucide-react';

interface DropzoneProps {
  label: string;
  onFilesSelect: (files: File[]) => void;
  files: File[];
  accept?: string;
  multiple?: boolean;
}

export const Dropzone: React.FC<DropzoneProps> = ({ label, onFilesSelect, files, accept, multiple = false }) => {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleClick = () => {
    if (inputRef.current) {
      inputRef.current.click();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      if (multiple) {
        onFilesSelect([...files, ...selectedFiles]);
      } else {
        onFilesSelect([selectedFiles[0]]);
      }
    }
  };

  const handleClear = (e: React.MouseEvent, indexToRemove?: number) => {
    e.stopPropagation();
    if (indexToRemove !== undefined) {
      const newFiles = [...files];
      newFiles.splice(indexToRemove, 1);
      onFilesSelect(newFiles);
    } else {
      onFilesSelect([]);
    }
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div 
      className={`brutalist-dropzone ${files.length > 0 ? 'has-file' : ''}`} 
      onClick={handleClick}
    >
      <input 
        type="file" 
        ref={inputRef} 
        onChange={handleFileChange} 
        style={{ display: 'none' }}
        accept={accept}
        multiple={multiple}
      />
      
      {files.length === 0 ? (
        <div>
          <h4>{label}</h4>
          <p>Click to upload or drag & drop</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: multiple ? '0.5rem' : '0' }}>
            <h4 style={{ margin: 0 }}>
              {multiple ? `${files.length} file${files.length > 1 ? 's' : ''} selected` : files[0].name}
            </h4>
            <button 
              onClick={(e) => handleClear(e)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              <X size={24} />
            </button>
          </div>
          {multiple && files.map((file, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.25rem 0.5rem', background: '#f0f0f0', border: '1px solid black' }}>
              <span style={{ fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</span>
              <button 
                onClick={(e) => handleClear(e, idx)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '2px' }}
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
