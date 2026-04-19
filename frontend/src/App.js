import "@/App.css";
import { Toaster } from "sonner";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import TransactionFlow from "@/components/TransactionFlow";
import PublicVerifyPage from "@/components/PublicVerifyPage";

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
          <Route path="/verify" element={<PublicVerifyPage />} />
        </Routes>
      </BrowserRouter>
    </>
  );
}

export default App;
