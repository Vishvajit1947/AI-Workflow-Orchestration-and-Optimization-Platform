import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ObjectiveInput from './pages/ObjectiveInput';
import WorkflowList from './pages/WorkflowList';
import WorkflowDetail from './pages/WorkflowDetail';
import WorkflowEditor from './pages/WorkflowEditor';
import Dashboard from './pages/Dashboard';
import CacheDashboard from './pages/CacheDashboard';
import ModelComparison from './pages/ModelComparison';
import ExecutionsPage from './pages/ExecutionsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
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
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
