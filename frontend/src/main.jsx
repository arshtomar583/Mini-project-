import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function App() {
  const [mode, setMode] = useState('github');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [sourceRoot, setSourceRoot] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState(null);
  const [selected, setSelected] = useState('');
  const [search, setSearch] = useState('');
  const api = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

  async function analyze(event) {
    event.preventDefault();
    if (busy) return;
    setError('');
    if (mode === 'zip' && (!file || !file.name.toLowerCase().endsWith('.zip'))) {
      setError('Choose a ZIP file containing a Python project.');
      return;
    }
    if (mode === 'zip' && file.size > 5 * 1024 * 1024) {
      setError('Your ZIP exceeds 5 MiB. Remove environments and installed dependencies, then try again.');
      return;
    }
    setBusy(true);
    setReport(null);
    setSelected('');
    setSearch('');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 65000);
    try {
      let body;
      let headers;
      if (mode === 'github') {
        body = JSON.stringify({ repository_url: url.trim(), source_root: sourceRoot.trim() });
        headers = { 'Content-Type': 'application/json' };
      } else {
        body = new FormData();
        body.append('file', file);
        body.append('source_root', sourceRoot.trim());
      }
      const response = await fetch(`${api}/api/analyses/${mode}`, { method: 'POST', body, headers, signal: controller.signal });
      let result;
      try { result = await response.json(); }
      catch { throw new Error('The server returned an unreadable response. Please try again.'); }
      if (!response.ok) throw new Error(result.error?.message || 'The project could not be analyzed.');
      setReport(result);
      setSelected(result.files.some(item => item.path === 'src/engine.py') ? 'src/engine.py' : result.files[0]?.path || '');
    } catch (failure) {
      setError(failure.name === 'AbortError'
        ? 'The request timed out. Choose a smaller project or try again shortly.'
        : failure instanceof TypeError ? 'Could not reach the analysis server. Check that the backend is running and try again.' : failure.message);
    } finally {
      clearTimeout(timeout);
      setBusy(false);
    }
  }

  function downloadReport() {
    const objectUrl = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = 'codebase-analysis.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  const selectedFile = report?.files.find(item => item.path === selected);
  const node = report?.graph.nodes.find(item => item.id === selected);
  const impact = report?.impact[selected];

  function fileLinks(paths, emptyMessage) {
    return paths?.length ? <ul className="file-links">{paths.map(path => <li key={path}>
      <button className="text-button" onClick={() => setSelected(path)}>{path}</button>
    </li>)}</ul> : <p className="muted small">{emptyMessage}</p>;
  }

  return (
    <main>
      <header>
        <p className="eyebrow">EXPLAIN THIS CODEBASE</p>
        <h1>Find your way through Python code.</h1>
        <p className="intro">Start with a public GitHub repository or a ZIP. Explore the files, their connections, and what a change might affect.</p>
      </header>
      <section className="input-panel" aria-labelledby="input-title">
        <div className="section-heading"><h2 id="input-title">Choose a project</h2><span className="badge">Python only</span></div>
        <form onSubmit={analyze}>
          <fieldset disabled={busy}>
            <legend className="sr-only">Project input method</legend>
            <div className="input-methods">
              <label className={mode === 'github' ? 'method selected' : 'method'}>
                <input type="radio" name="method" value="github" checked={mode === 'github'} onChange={() => { setMode('github'); setError(''); }} />Public GitHub link
              </label>
              <label className={mode === 'zip' ? 'method selected' : 'method'}>
                <input type="radio" name="method" value="zip" checked={mode === 'zip'} onChange={() => { setMode('zip'); setError(''); }} />Upload ZIP
              </label>
            </div>
            {mode === 'github' ? <div className="field" key="github">
              <label htmlFor="repository">Repository URL</label>
              <input id="repository" type="url" required maxLength={300} value={url} onChange={event => setUrl(event.target.value)} placeholder="https://github.com/owner/repository" aria-describedby="repository-help" />
              <div className="field-help"><span id="repository-help">Analyzes a snapshot of the default branch. Public repositories only.</span>
                <button type="button" className="text-button" onClick={() => setUrl('https://github.com/nikhilbajantri/AltF4.git')}>Use AltF4 example</button>
              </div>
            </div> : <div className="field" key="zip">
              <label htmlFor="archive">Python project ZIP</label>
              <input id="archive" type="file" accept=".zip,application/zip" required onChange={event => setFile(event.target.files[0] || null)} aria-describedby="zip-help" />
              <p id="zip-help" className="small muted">Up to 5 MiB. Leave out virtual environments, installed dependencies, and nested archives.</p>
            </div>}
            <details className="advanced">
              <summary>Choose a source folder (optional)</summary>
              <label htmlFor="source-root">Folder inside the project</label>
              <input id="source-root" value={sourceRoot} maxLength={220} onChange={event => setSourceRoot(event.target.value)} placeholder="Leave blank for project root" />
              <p className="small muted">For example, enter src if imports begin inside that folder. For AltF4, leave this blank: src is itself a package.</p>
            </details>
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Analyzing project…' : 'Analyze project'}</button>
          </fieldset>
          {busy && <p role="status" className="status">Preparing the source and analyzing its Python files. This may take a moment.</p>}
          {error && <p role="alert" className="error">{error}</p>}
        </form>
        <p className="privacy">Code is read, never run. Source files are processed temporarily and removed after the request. No AI service is used.</p>
        <p className="small muted">Limits: 200 Python files, 25 MiB extracted, 1 MiB per Python file. Analysis work is limited to 15 seconds.</p>
      </section>
      {report && <section className="results" aria-labelledby="results-title">
        <div className="section-heading"><div><p className="eyebrow">ANALYSIS RESULTS</p><h2 id="results-title">Your project at a glance</h2></div>
          <button className="secondary" onClick={downloadReport}>Download report</button></div>
        <p className="small muted">{report.input.kind === 'github'
          ? <><a href={`${report.input.repository_url}/tree/${report.input.commit}`} target="_blank" rel="noreferrer">{report.input.repository_url.replace('https://github.com/', '')}</a> · {report.input.branch} · snapshot {report.input.commit.slice(0, 8)}</>
          : 'Uploaded ZIP'} · Source folder: {report.input.source_root}</p>
        <div className="metrics">{[
          ['Python files', report.summary.files_analyzed], ['Functions', report.summary.functions],
          ['Classes', report.summary.classes], ['Connections', report.summary.local_dependencies],
          ['Circular groups', report.summary.circular_dependency_groups], ['Source errors', report.summary.errors],
        ].map(([label, value]) => <div className="metric" key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>
        {report.analysis_status === 'partial' && <div className="warning" role="status"><strong>Some source could not be read.</strong> The results below cover successfully analyzed files only.
          <details><summary>View source errors</summary><ul>{report.errors.map((item, index) => <li key={index}>{item.path}{item.line ? `, line ${item.line}` : ''}: {item.message}</li>)}</ul></details>
        </div>}
        {report.summary.unresolved_imports > 0 && <p className="notice">{report.summary.unresolved_imports} imported names were not matched locally. These may include Python libraries, installed packages, or unsupported imports; they are not automatically errors.</p>}
        <div className="explorer">
          <aside className="file-panel" aria-label="Project files"><h3>Files</h3>
            <label className="sr-only" htmlFor="file-search">Search files</label>
            <input id="file-search" type="search" placeholder="Find a file…" value={search} onChange={event => setSearch(event.target.value)} />
            <ul className="file-list">{report.files.filter(item => item.path.toLowerCase().includes(search.toLowerCase())).map(item => <li key={item.path}>
              <button className={item.path === selected ? 'file selected' : 'file'} aria-pressed={item.path === selected} onClick={() => setSelected(item.path)}>{item.path}</button>
            </li>)}</ul>
            {!report.files.some(item => item.path.toLowerCase().includes(search.toLowerCase())) && <p className="small muted">No matching files.</p>}
          </aside>
          <article className="detail-panel" aria-label="Selected file details">
            {selectedFile ? <><p className="eyebrow">SELECTED FILE</p><h3 className="file-title">{selectedFile.path}</h3>
              <div className="detail-columns">
                <section><h4>Functions</h4>{selectedFile.functions.length ? <ul>{selectedFile.functions.map(item => <li key={`${item.qualified_name}-${item.line}`}><code>{item.qualified_name}()</code><span className="line">line {item.line}{item.is_async ? ' · async' : ''}</span></li>)}</ul> : <p className="small muted">No named functions found.</p>}</section>
                <section><h4>Classes</h4>{selectedFile.classes.length ? <ul>{selectedFile.classes.map(item => <li key={`${item.qualified_name}-${item.line}`}><code>{item.qualified_name}</code><span className="line">line {item.line}</span></li>)}</ul> : <p className="small muted">No classes found.</p>}</section>
                <section><h4>Imports from</h4>{fileLinks(node.dependencies, 'No local file dependencies found.')}</section>
                <section><h4>Imported by</h4>{fileLinks(node.imported_by, 'No local importers found.')}</section>
              </div>
              <section className="impact"><h4>Potential change impact <span className="badge">{impact.affected_count} other {impact.affected_count === 1 ? 'file' : 'files'}</span></h4>
                <p className="small muted">These files may need attention if you change this file. This does not mean they will break.</p>
                <div className="detail-columns"><div><h5>Direct dependents</h5>{fileLinks(impact.direct_dependents, 'None found.')}</div><div><h5>Indirect dependents</h5>{fileLinks(impact.indirect_dependents, 'None found.')}</div></div>
              </section>
            </> : <p>No successfully analyzed Python file is available to select.</p>}
          </article>
        </div>
        <section className="cycle-panel"><h3>Circular dependency groups</h3>{report.circular_dependency_groups.length
          ? <ul>{report.circular_dependency_groups.map((group, index) => <li key={index}>{group.join(' ↔ ')}</li>)}</ul>
          : <p className="muted small">No circular groups found in the resolved file graph.</p>}
          <p className="small muted">A group means its files can reach one another through import connections. It is not automatically a bug. Interactive graph visualization comes next.</p>
        </section>
      </section>}
      <footer>Static analysis shows possible import relationships. It does not prove execution order or resolve every Python import.</footer>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
