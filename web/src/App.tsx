import React from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { Settings } from 'lucide-react';

import { LandingPage } from './pages/LandingPage';
import { ConfigPage } from './pages/ConfigPage';
import { CreateKBPage } from './pages/CreateKBPage';
import { GuidePage } from './pages/GuidePage';
import { UploadLecturePage } from './pages/UploadLecturePage';
import { GeneratePage } from './pages/GeneratePage';
import { DownloadPage } from './pages/DownloadPage';

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="app-container">
      {location.pathname !== '/config' && (
        <div className="config-btn-container">
          <button 
            style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            onClick={() => navigate('/config')}
            title="Configuration"
          >
            <Settings size={32} />
          </button>
        </div>
      )}
      {children}
    </div>
  );
};

export const App = () => {
  return (
    <AppProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="/create-kb" element={<CreateKBPage />} />
            <Route path="/guide" element={<GuidePage />} />
            <Route path="/lecture" element={<UploadLecturePage />} />
            <Route path="/generate" element={<GeneratePage />} />
            <Route path="/download" element={<DownloadPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </AppProvider>
  );
};

export default App;
