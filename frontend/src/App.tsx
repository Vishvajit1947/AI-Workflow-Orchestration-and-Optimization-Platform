import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import ObjectiveInput from './pages/ObjectiveInput';
import WorkflowList from './pages/WorkflowList';
import WorkflowDetail from './pages/WorkflowDetail';
import WorkflowEditor from './pages/WorkflowEditor';
import Dashboard from './pages/Dashboard';
import CacheDashboard from './pages/CacheDashboard';
import ModelComparison from './pages/ModelComparison';
import ExecutionsPage from './pages/ExecutionsPage';
import ProjectsPage from './pages/ProjectsPage';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* Protected routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Layout />}>
              <Route index element={<ObjectiveInput />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="workflows" element={<WorkflowList />} />
              <Route path="workflows/new" element={<WorkflowEditor />} />
              <Route path="workflows/:id" element={<WorkflowDetail />} />
              <Route path="workflows/:id/edit" element={<WorkflowEditor />} />
              <Route path="cache" element={<CacheDashboard />} />
              <Route path="models" element={<ModelComparison />} />
              <Route path="executions" element={<ExecutionsPage />} />
              <Route path="projects" element={<ProjectsPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
