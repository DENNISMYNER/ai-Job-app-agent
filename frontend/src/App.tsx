import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import { Spinner } from "./components/ui/States";

const page = (loader: () => Promise<{ default: React.ComponentType }>) => lazy(loader);
const Dashboard = page(() => import("./pages/DashboardPage"));
const Profile = page(() => import("./pages/ProfilePage"));
const Discovery = page(() => import("./pages/JobDiscoveryPage"));
const Recommended = page(() => import("./pages/RecommendedJobsPage"));
const Documents = page(() => import("./pages/DocumentsPage"));
const CoverLetters = page(() => import("./pages/CoverLettersPage"));
const Assistant = page(() => import("./pages/ApplicationAssistantPage"));
const Tracker = page(() => import("./pages/TrackerPage"));
const Interviews = page(() => import("./pages/InterviewPrepPage"));
const Automation = page(() => import("./pages/AutomationSettingsPage"));
const AISettings = page(() => import("./pages/AISettingsPage"));
const System = page(() => import("./pages/SystemSettingsPage"));

export default function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="profile" element={<Profile />} />
          <Route path="discovery" element={<Discovery />} />
          <Route path="recommended" element={<Recommended />} />
          <Route path="documents" element={<Documents />} />
          <Route path="cover-letters" element={<CoverLetters />} />
          <Route path="assistant" element={<Assistant />} />
          <Route path="tracker" element={<Tracker />} />
          <Route path="interviews" element={<Interviews />} />
          <Route path="automation" element={<Automation />} />
          <Route path="ai" element={<AISettings />} />
          <Route path="system" element={<System />} />
          <Route path="*" element={<p className="p-8 text-slate-600">Page not found.</p>} />
        </Route>
      </Routes>
    </Suspense>
  );
}
