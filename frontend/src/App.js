import "@/App.css";
import { Toaster } from "sonner";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import TransactionFlow from "@/components/TransactionFlow";
import PublicVerifyPage from "@/components/PublicVerifyPage";
import AdminApp from "@/admin/AdminApp";
import DevelopersPage from "@/developers/DevelopersPage";
import DocsPortal from "@/docs/DocsPortal";
import EnterpriseAccess from "@/pages/EnterpriseAccess";

function App() {
  return (
    <>
      <Toaster
        theme="light"
        position="top-right"
        toastOptions={{
          style: {
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            color: "#111827",
          },
        }}
      />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TransactionFlow />} />
          <Route path="/demo" element={<TransactionFlow />} />
          <Route path="/developers" element={<DevelopersPage />} />
          <Route path="/docs/*" element={<DocsPortal />} />
          <Route path="/evaluation" element={<EnterpriseAccess />} />
          <Route path="/verify" element={<PublicVerifyPage />} />
          <Route path="/admin/*" element={<AdminApp />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
