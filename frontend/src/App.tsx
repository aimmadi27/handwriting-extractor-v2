import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import HomePage from './pages/HomePage';
import AuthCallback from './pages/AuthCallback';
import AppPage from './pages/AppPage';
import HistoryPage from './pages/HistoryPage';
import DocumentPage from './pages/DocumentPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                    element={<HomePage />} />
        <Route path="/auth/callback"       element={<AuthCallback />} />
        <Route path="/app"                 element={<AppPage />} />
        <Route path="/history"             element={<HistoryPage />} />
        <Route path="/documents/:documentId" element={<DocumentPage />} />
        <Route path="*"                    element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
