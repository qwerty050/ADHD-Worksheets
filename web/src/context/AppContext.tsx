import React, { createContext, useContext, useState } from 'react';

interface AppContextType {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  kbName: string | null;
  setKbName: (name: string | null) => void;
  lectureId: string | null;
  setLectureId: (id: string | null) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [kbName, setKbName] = useState<string | null>(null);
  const [lectureId, setLectureId] = useState<string | null>(null);

  return (
    <AppContext.Provider value={{ sessionId, setSessionId, kbName, setKbName, lectureId, setLectureId }}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
