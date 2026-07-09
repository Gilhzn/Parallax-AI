import { BrowserRouter, Route, Routes } from 'react-router-dom';

import JobProgressPage from './pages/JobProgressPage';
import TourPage from './pages/TourPage';
import UploadPage from './pages/UploadPage';

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/jobs/:jobId" element={<JobProgressPage />} />
        <Route path="/tour/:tourId" element={<TourPage />} />
      </Routes>
    </BrowserRouter>
  );
}
