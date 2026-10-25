import React from 'react';
import { createRoot } from 'react-dom/client';
import './app.css';
import './extra.css';
import App from './App.jsx';
import { startEffects } from './fx/effects.js';
startEffects();
createRoot(document.getElementById('root')).render(<App />);
