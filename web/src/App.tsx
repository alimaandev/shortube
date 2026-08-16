import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Topics from "./pages/Topics";
import Videos from "./pages/Videos";
import Settings from "./pages/Settings";
import Analytics from "./pages/Analytics";

const App: React.FC = () => {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/topics" element={<Topics />} />
        <Route path="/videos" element={<Videos />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
};

export default App;
