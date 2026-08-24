import React from 'react';

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export const Toggle: React.FC<ToggleProps> = ({ label, checked, onChange }) => {
  return (
    <div className="brutalist-toggle-container" onClick={() => onChange(!checked)}>
      <div className={`brutalist-toggle ${checked ? 'on' : ''}`}></div>
      <span>{label}</span>
    </div>
  );
};
