import "@/App.css";
import { Toaster } from "sonner";
import TwoPartyProofComparison from "@/components/TwoPartyProofComparison";

function App() {
  return (
    <>
      <Toaster
        theme="dark"
        position="top-right"
        toastOptions={{
          style: {
            background: "#09090b",
            border: "1px solid #27272a",
            color: "#fafafa",
          },
        }}
      />
      <TwoPartyProofComparison />
    </>
  );
}

export default App;
