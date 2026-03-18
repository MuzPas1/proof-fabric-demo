import './globals.css'

export const metadata = {
  title: 'Proof Fabric Protocol — RBI Sandbox Demo',
  description: 'Financial Evidence Artifact (FEA) Generation & Verification System',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <head>
        <script dangerouslySetInnerHTML={{__html:'window.addEventListener("error",function(e){if(e.error instanceof DOMException&&e.error.name==="DataCloneError"&&e.message&&e.message.includes("PerformanceServerTiming")){e.stopImmediatePropagation();e.preventDefault()}},true);'}} />
      </head>
      <body className="bg-slate-950 min-h-screen">
        {children}
      </body>
    </html>
  )
}
