import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function App() {
  return (
    <main>
      <p className="eyebrow">EXPLAIN THIS CODEBASE · IN DEVELOPMENT</p>
      <h1>Find your way through unfamiliar Python code.</h1>
      <p>Explore how files connect, discover functions and classes, and understand the potential impact of a change.</p>
      <section aria-labelledby="progress-title">
        <h2 id="progress-title">Our first milestone</h2>
        <p>Read a small Python project and extract its structure. Project uploads and interactive graphs will follow.</p>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
