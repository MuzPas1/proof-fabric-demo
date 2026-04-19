import "@/App.css";
import { Toaster } from "sonner";
import TransactionFlow from "@/components/TransactionFlow";

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
      <TransactionFlow />
    </>
  );
}

export default App;
