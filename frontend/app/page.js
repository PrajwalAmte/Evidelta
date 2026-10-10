'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';

const baseHeaders = {
  'Content-Type': 'application/json',
};

function statusClass(status) {
  const map = {
    acknowledged: 'status acknowledged',
    measured: 'status measured',
    corroborated: 'status corroborated',
    candidate: 'status candidate',
    insufficient_evidence: 'status weak',
  };

  return map[status] || 'status candidate';
}

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function Page() {
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState('all');
  const [changes, setChanges] = useState([]);
  const [summary, setSummary] = useState(null);
  const [evidence, setEvidence] = useState([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [theme, setTheme] = useState('light');
  const [form, setForm] = useState({
    source_type: 'github',
    source_url: '',
    observed_at: new Date().toISOString(),
    raw_content: '',
    author_id: '',
  });
  const [submitState, setSubmitState] = useState({
    submitting: false,
    message: '',
    success: false,
  });

  async function fetchProducts() {
    const response = await fetch(`${API_BASE}/ui/products`);
    if (!response.ok) {
      throw new Error('Unable to load products');
    }
    const data = await response.json();
    return data.products || [];
  }

  async function fetchChanges(product, limit = 10) {
    const response = await fetch(`${API_BASE}/changes/feed`, {
      method: 'POST',
      headers: baseHeaders,
      body: JSON.stringify({ product, limit }),
    });

    if (!response.ok) {
      throw new Error('Unable to load changes');
    }

    const data = await response.json();
    return data.changes || [];
  }

  async function fetchSummary(product) {
    const response = await fetch(`${API_BASE}/incident/query`, {
      method: 'POST',
      headers: baseHeaders,
      body: JSON.stringify({
        product,
        symptom: 'observed change',
        time_window: '30d',
      }),
    });

    if (!response.ok) {
      throw new Error('Unable to load incident summary');
    }

    return response.json();
  }

  async function fetchEvidence(ids) {
    const evidenceIds = Array.isArray(ids) ? ids : [];
    if (!evidenceIds.length) {
      setEvidence([]);
      return [];
    }

    const response = await fetch(`${API_BASE}/ui/evidence`, {
      method: 'POST',
      headers: baseHeaders,
      body: JSON.stringify({ evidence_ids: evidenceIds }),
    });

    if (!response.ok) {
      throw new Error('Unable to fetch evidence details');
    }

    const data = await response.json();
    return data.evidence || [];
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitState({ submitting: true, message: '', success: false });

    try {
      const response = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        headers: baseHeaders,
        body: JSON.stringify({
          source_type: form.source_type,
          source_url: form.source_url,
          observed_at: form.observed_at,
          raw_content: form.raw_content,
          author_id: form.author_id || null,
        }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload?.detail || 'Unable to save evidence');
      }

      setSubmitState({
        submitting: false,
        message: 'Evidence saved successfully. Refreshing the feed…',
        success: true,
      });

      setForm({
        source_type: 'github',
        source_url: '',
        observed_at: new Date().toISOString(),
        raw_content: '',
        author_id: '',
      });

      const nextProducts = await fetchProducts();
      setProducts(nextProducts);
      const nextChanges = await fetchChanges(selectedProduct, 10);
      setChanges(nextChanges);
      const nextSummary = await fetchSummary(selectedProduct);
      setSummary(nextSummary);
      const nextIds = nextChanges.flatMap((item) => item.evidence_ids || []);
      const nextEvidence = (await fetchEvidence(nextIds)) || [];
      setEvidence(nextEvidence);
      setSelectedEvidenceId(nextEvidence[0]?.id || '');
      setError('');
    } catch (err) {
      setSubmitState({
        submitting: false,
        message: err.message || 'Unable to save evidence.',
        success: false,
      });
    }
  }

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError('');

        const productList = await fetchProducts();
        setProducts(productList);

        const defaultProduct = 'all';
        const changeList = await fetchChanges(defaultProduct, 10);
        setChanges(changeList);

        const summaryData = await fetchSummary(defaultProduct);
        setSummary(summaryData);

        const allIds = changeList.flatMap((item) => item.evidence_ids || []);
        const detailList = (await fetchEvidence(allIds)) || [];
        setEvidence(detailList);

        if (detailList[0]?.id) {
          setSelectedEvidenceId(detailList[0].id);
        }
      } catch (err) {
        setError(err.message || 'The backend is not reachable yet. Start the FastAPI API on port 8000 and refresh.');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const selectedEvidence = useMemo(() => {
    const safeEvidence = Array.isArray(evidence) ? evidence : [];
    return safeEvidence.find((item) => item.id === selectedEvidenceId) || safeEvidence[0] || null;
  }, [evidence, selectedEvidenceId]);

  const overviewStats = useMemo(
    () => [
      { label: 'Products', value: products.length || 0 },
      { label: 'Signals', value: changes.length || 0 },
      { label: 'Evidence', value: evidence.length || 0 },
      { label: 'Status', value: summary?.status || 'unknown' },
    ],
    [changes.length, evidence.length, products.length, summary?.status],
  );

  async function handleProductChange(nextProduct) {
    setSelectedProduct(nextProduct);
    setLoading(true);

    try {
      const nextChanges = await fetchChanges(nextProduct, 10);
      setChanges(nextChanges);

      const nextSummary = await fetchSummary(nextProduct);
      setSummary(nextSummary);

      const ids = nextChanges.flatMap((item) => item.evidence_ids || []);
      const nextEvidence = (await fetchEvidence(ids)) || [];
      setEvidence(nextEvidence);
      setSelectedEvidenceId(nextEvidence[0]?.id || '');
      setError('');
    } catch (err) {
      setError(err.message || 'Could not refresh this product view.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={theme === 'dark' ? 'page-shell dark-theme' : 'page-shell'}>
      <div className="main-column">
        <header className="hero-card" id="overview">
          <div className="header-copy">
            <p className="eyebrow">Overview</p>
            <h1>Evidelta</h1>
            <h2>Product signal monitor</h2>
          </div>
          <div className="hero-actions">
            <button type="button" className="secondary-button" onClick={() => setTheme((current) => (current === 'light' ? 'dark' : 'light'))}>
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </button>
            <button type="button" className="primary-button" onClick={() => handleProductChange(selectedProduct)}>
              Refresh view
            </button>
          </div>
        </header>

        <section className="info-grid">
          <article className="info-card">
            <h3>What this is</h3>
            <p>
              Evidelta turns scattered product and platform signals into a small, evidence-backed feed of likely changes.
            </p>
          </article>
          <article className="info-card">
            <h3>How it works</h3>
            <p>
              It ingests raw evidence, classifies the signal, groups related reports, and grades the resulting change based on how strong the evidence is.
            </p>
          </article>
          <article className="info-card">
            <h3>How to use it</h3>
            <p>
              Pick a product, review the change feed, and inspect the underlying evidence to understand why a signal is rising or being acknowledged.
            </p>
          </article>
        </section>

        <section className="process-grid">
          <div className="process-step">
            <span>1</span>
            <div>
              <h3>Collect</h3>
              <p>Ingest GitHub, docs, status pages, and probe signals into one evidence store.</p>
            </div>
          </div>
          <div className="process-step">
            <span>2</span>
            <div>
              <h3>Classify</h3>
              <p>Resolve product, dimension, and confidence using the actual text of the signal.</p>
            </div>
          </div>
          <div className="process-step">
            <span>3</span>
            <div>
              <h3>Review</h3>
              <p>Assess the feed, summarize the incident, and drill into evidence before acting.</p>
            </div>
          </div>
        </section>

        <section className="input-panel panel">
          <div className="panel-header">
            <h2>Submit evidence</h2>
          </div>

          <form className="ingest-form" onSubmit={handleSubmit}>
            <div className="field-row">
              <label>
                Source type
                <select value={form.source_type} onChange={(event) => setForm({ ...form, source_type: event.target.value })}>
                  <option value="github">github</option>
                  <option value="status_page">status_page</option>
                  <option value="docs">docs</option>
                  <option value="probe">probe</option>
                  <option value="other">other</option>
                </select>
              </label>

              <label>
                Source URL
                <input
                  type="url"
                  required
                  value={form.source_url}
                  onChange={(event) => setForm({ ...form, source_url: event.target.value })}
                  placeholder="https://example.com/issue"
                />
              </label>
            </div>

            <div className="field-row">
              <label>
                Observed at
                <input
                  type="datetime-local"
                  value={form.observed_at ? form.observed_at.slice(0, 16) : ''}
                  onChange={(event) => setForm({ ...form, observed_at: new Date(event.target.value).toISOString() })}
                />
              </label>

              <label>
                Author ID (optional)
                <input
                  type="text"
                  value={form.author_id}
                  onChange={(event) => setForm({ ...form, author_id: event.target.value })}
                  placeholder="team-or-user-id"
                />
              </label>
            </div>

            <label>
              Evidence text
              <textarea
                required
                rows={8}
                value={form.raw_content}
                onChange={(event) => setForm({ ...form, raw_content: event.target.value })}
                placeholder="Paste the actual issue, changelog, status note, or product signal here..."
              />
            </label>

            <div className="submit-row">
              <button type="submit" className="primary-button" disabled={submitState.submitting}>
                {submitState.submitting ? 'Saving…' : 'Save evidence'}
              </button>
              {submitState.message ? (
                <span className={submitState.success ? 'form-success' : 'form-error'}>{submitState.message}</span>
              ) : null}
            </div>
          </form>
        </section>

        <section className="dashboard" id="feed">
          <div className="toolbar">
            <label>
              Product
              <select value={selectedProduct} onChange={(event) => handleProductChange(event.target.value)}>
                <option value="all">All products</option>
                {products.map((product) => (
                  <option key={product} value={product}>
                    {product}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {error ? <div className="error-box">{error}</div> : null}

          <div className="content-grid">
            <div className="panel">
              <div className="panel-header">
                <h2>Change feed</h2>
              </div>

              {loading ? (
                <div className="empty-state">Loading…</div>
              ) : changes.length === 0 ? (
                <div className="empty-state">No evidence-backed changes found for this filter.</div>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>Dimension</th>
                        <th>Window</th>
                        <th>Status</th>
                        <th>Evidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {changes.map((item, index) => {
                        const rowKey = item.id || `${item.product || 'unknown'}-${item.dimension || 'unknown'}-${index}`;

                        return (
                          <tr key={rowKey} onClick={() => setSelectedEvidenceId((item.evidence_ids || [])[0] || '')}>
                            <td>{item.product || 'unknown'}</td>
                            <td>{item.dimension || 'unknown'}</td>
                            <td>{item.time_window || 'unknown'}</td>
                            <td>
                              <span className={statusClass(item.status)}>{item.status || 'candidate'}</span>
                            </td>
                            <td>{item.evidence_count || 0}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2>Incident summary</h2>
              </div>
              {summary ? (
                <div className="summary-box">
                  <p>{summary.summary || 'No summary available yet.'}</p>
                  <div className="meta-row">
                    <span>{summary.status || 'unknown'}</span>
                    <span>{(summary.evidence_ids || []).length} evidence items</span>
                  </div>
                </div>
              ) : (
                <div className="empty-state">Summary pending.</div>
              )}
            </div>
          </div>

          <div className="detail-grid" id="evidence">
            <div className="panel evidence-list">
              <div className="panel-header">
                <h2>Evidence</h2>
              </div>
              {evidence.length === 0 ? (
                <div className="empty-state">No evidence rows loaded for the selected product.</div>
              ) : (
                <ul className="evidence-list-items">
                  {evidence.map((item) => (
                    <li key={item.id} className={item.id === selectedEvidence?.id ? 'selected' : ''} onClick={() => setSelectedEvidenceId(item.id)}>
                      <strong>{item.product || 'unknown'}</strong>
                      <span>{item.dimension || 'unknown'}</span>
                      <small>{item.source_type || 'unknown'} · {formatTime(item.observed_at)}</small>
                      <p>{(item.raw_text || '').replace(/\s+/g, ' ').trim().slice(0, 120) || 'No snippet available'}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="panel detail-panel">
              <div className="panel-header">
                <h2>Evidence detail</h2>
              </div>
              {selectedEvidence ? (
                <div className="detail-content">
                  <div className="detail-row">
                    <span className="label">Source</span>
                    <strong>{selectedEvidence.source_type || 'unknown'}</strong>
                  </div>
                  <div className="detail-row">
                    <span className="label">URL</span>
                    <a href={selectedEvidence.source_url} target="_blank" rel="noreferrer noopener">
                      {selectedEvidence.source_url}
                    </a>
                  </div>
                  <div className="detail-row">
                    <span className="label">Fetched</span>
                    <strong>{formatTime(selectedEvidence.fetched_at)}</strong>
                  </div>
                  <div className="detail-row">
                    <span className="label">Observed</span>
                    <strong>{formatTime(selectedEvidence.observed_at)}</strong>
                  </div>
                  <div className="detail-row">
                    <span className="label">Hash</span>
                    <strong>{selectedEvidence.content_hash || '—'}</strong>
                  </div>
                  <div className="detail-row">
                    <span className="label">Author hash</span>
                    <strong>{selectedEvidence.author_hash || '—'}</strong>
                  </div>
                  <div className="detail-row">
                    <span className="label">Product</span>
                    <strong>{selectedEvidence.product || 'unknown'}</strong>
                  </div>
                  <div className="detail-row">
                    <span className="label">Dimension</span>
                    <strong>{selectedEvidence.dimension || 'unknown'}</strong>
                  </div>
                  <div className="detail-block">
                    <span className="label">Evidence text</span>
                    <p>{selectedEvidence.raw_text || 'No raw text available for this record.'}</p>
                  </div>
                </div>
              ) : (
                <div className="empty-state">Select an evidence item to inspect its full context.</div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
