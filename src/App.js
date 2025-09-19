import React, { useState } from 'react';
import './App.css';

function App() {
  const [mode, setMode] = useState('email');
  const [highContrast, setHighContrast] = useState(false);

  const modes = ['email', 'coding', 'supabase', 'document_processing', 'schedule', 'budget', 'pdf_viewer', 'googleearth'];

  const renderMode = (currentMode) => {
    switch (currentMode) {
      case 'email':
        return <div>Email Mode: Gmail clone with composer.</div>;
      case 'coding':
        return <div>Coding Mode: IDE with hex bubbles.</div>;
      case 'supabase':
        return <div>Supabase Mode: Table viewer.</div>;
      case 'document_processing':
        return <div>Document Processing Mode: Drag/drop upload.</div>;
      case 'schedule':
        return <div>Schedule Mode: Gantt/Calendar views.</div>;
      case 'budget':
        return <div>Budget Mode: Spreadsheet with alerts.</div>;
      case 'pdf_viewer':
        return <div>PDF Viewer Mode: Pen markup.</div>;
      case 'googleearth':
        return <div>GoogleEarth Mode: KMZ viewer.</div>;
      default:
        return <div>Main Show-Me Window</div>;
    }
  };

  return (
    <div className={`App ${highContrast ? 'high-contrast' : ''}`}>
      <header>
        <h1>V-Me2</h1>
        <div className="voice-controls">
          <button>Conversation Mode</button>
          <button>Meeting Mode</button>
        </div>
        <div className="settings-dropdown">
          <select onChange={(e) => setMode(e.target.value)}>
            {modes.map(m => <option key={m} value={m}>{m.replace('_', ' ').toUpperCase()}</option>)}
          </select>
          <button onClick={() => setHighContrast(!highContrast)}>High Contrast</button>
        </div>
      </header>
      <main className="show-me-window">
        {renderMode(mode)}
      </main>
    </div>
  );
}

export default App;
