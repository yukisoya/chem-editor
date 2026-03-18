import React, { Component, useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';

// Error boundary to catch render-time crashes
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 20, color: '#dc2626', fontFamily: 'sans-serif' }}>
          <b>Ketcher render error:</b>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>
            {this.state.error.message}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

function KetcherApp() {
  const [EditorComp, setEditorComp] = useState(null);
  const [provider, setProvider] = useState(null);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [{ Editor }, { StandaloneStructServiceProvider }] = await Promise.all([
          import('ketcher-react'),
          import('ketcher-standalone'),
        ]);
        // Also load CSS dynamically
        await import('ketcher-react/dist/index.css');

        if (cancelled) return;
        const ssp = new StandaloneStructServiceProvider();
        setEditorComp(() => Editor);
        setProvider(ssp);
      } catch (e) {
        console.error('Ketcher load error:', e);
        if (!cancelled) setLoadError(e.message || String(e));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loadError) {
    return (
      <div style={{ padding: 20, color: '#dc2626', fontFamily: 'sans-serif' }}>
        <b>Failed to load Ketcher:</b>
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{loadError}</pre>
      </div>
    );
  }

  if (!EditorComp || !provider) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100%', fontFamily: 'sans-serif', color: '#64748b',
      }}>
        Loading Ketcher...
      </div>
    );
  }

  return (
    <EditorComp
      staticResourcesUrl="/static/ketcher/"
      structServiceProvider={provider}
      errorHandler={(msg) => console.warn('Ketcher warning:', msg)}
      onInit={(ketcher) => {
        window.ketcher = ketcher;
        window.parent.postMessage({ type: 'ketcher-ready' }, '*');
        console.log('Ketcher ready');
      }}
    />
  );
}

createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <KetcherApp />
  </ErrorBoundary>
);
