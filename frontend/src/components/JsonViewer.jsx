import { useMemo } from "react";

export const JsonViewer = ({ data }) => {
  const formattedJson = useMemo(() => {
    if (!data) return null;
    
    const jsonString = JSON.stringify(data, null, 2);
    
    // Syntax highlight JSON
    const highlighted = jsonString
      .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
      .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>')
      .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
      .replace(/: (true|false)/g, ': <span class="json-boolean">$1</span>')
      .replace(/: (null)/g, ': <span class="json-null">$1</span>');
    
    return highlighted;
  }, [data]);

  if (!data) return null;

  return (
    <div className="json-viewer overflow-auto" data-testid="json-viewer">
      <pre 
        className="text-xs leading-relaxed"
        dangerouslySetInnerHTML={{ __html: formattedJson }}
      />
    </div>
  );
};
