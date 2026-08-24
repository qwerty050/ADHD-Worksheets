import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'accent' | 'dark';
}

export const Button: React.FC<ButtonProps> = ({ variant = 'primary', className = '', children, ...props }) => {
  const baseClass = 'brutalist-btn';
  const variantClass = variant === 'primary' ? '' : ` ${variant}`;
  
  return (
    <button className={`${baseClass}${variantClass} ${className}`} {...props}>
      {children}
    </button>
  );
};
