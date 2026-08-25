import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import StudentPage from './pages/StudentPage';
import AdminPage from './pages/AdminPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StudentPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;