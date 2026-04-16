import { useState, useEffect } from 'react'
import TrackSelector from './components/TrackSelector'
import AnalyzeButton from './components/AnalyzeButton'
import SignalSummary from './components/SignalSummary'
import ConfidencePanel from './components/ConfidencePanel'
import CriticTimeline from './components/CriticTimeline'
import ProducerSettings from './components/ProducerSettings'
import OutputDownloads from './components/OutputDownloads'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export default function App() {
  const [tracks, setTracks]               = useState([])
  const [selectedTrack, setSelectedTrack] = useState('')
  const [result, setResult]               = useState(null)
  const [loading, setLoading]             = useState(false)
  const [error, setError]                 = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/tracks`)
      .then(r => r.json())
      .then(data => {
        setTracks(data)
        if (data.length > 0) setSelectedTrack(data[0].track_id)
      })
      .catch(() => setError('Failed to load tracks'))
  }, [])

  async function handleAnalyze() {
    if (!selectedTrack) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_id: selectedTrack }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data.outputs && API_BASE) {
        data.outputs.pdf_url      = API_BASE + data.outputs.pdf_url
        data.outputs.json_url     = API_BASE + data.outputs.json_url
        data.outputs.metadata_url = API_BASE + data.outputs.metadata_url
      }
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-layout">

      {/* ── Left Sidebar ── */}
      <aside className="sidebar">

        {/* Brand */}
        <div style={{ padding: '32px 24px 24px' }}>
          <p className="eyebrow" style={{ marginBottom: 8 }}>Audio Intelligence</p>
          <h1 className="font-brand" style={{
            margin: 0,
            fontSize: 28,
            fontWeight: 500,
            fontStyle: 'italic',
            color: 'var(--ink)',
            lineHeight: 1.1,
            letterSpacing: '-0.01em',
          }}>
            Sound<span style={{ color: 'var(--sage)' }}>Reverse</span>
          </h1>
          <p style={{
            margin: '8px 0 0',
            fontSize: 12,
            color: 'var(--ink-4)',
            lineHeight: 1.5,
          }}>
            LangGraph multi-agent mastering analysis
          </p>
        </div>

        <div className="divider" style={{ margin: '0 24px' }} />

        {/* Track list */}
        <div style={{ padding: '20px 16px', flex: 1, overflowY: 'auto' }}>
          <p className="eyebrow" style={{ marginBottom: 12, paddingLeft: 4 }}>Select Track</p>
          <TrackSelector tracks={tracks} selected={selectedTrack} onChange={setSelectedTrack} />
        </div>

        {/* Analyze + footer */}
        <div style={{ padding: '16px 20px 24px', borderTop: '1px solid var(--border)' }}>
          {error && (
            <div style={{
              marginBottom: 12,
              padding: '9px 14px',
              background: 'var(--clay-pale)',
              border: '1px solid var(--clay-border)',
              borderRadius: 8,
              fontSize: 12,
              color: 'var(--clay)',
              fontFamily: 'Fragment Mono, monospace',
            }}>
              ⚠ {error}
            </div>
          )}
          <AnalyzeButton loading={loading} onClick={handleAnalyze} />
          <div style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', gap: '4px 12px' }}>
            {['LangGraph', 'Gemini', 'HTDemucs', 'LangSmith'].map(t => (
              <span key={t} className="eyebrow" style={{ opacity: 0.45 }}>{t}</span>
            ))}
          </div>
        </div>
      </aside>

      {/* ── Right Panel ── */}
      <main className="output-panel">
        {loading ? (
          <LoadingSkeleton />
        ) : result ? (
          <ResultsView result={result} />
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 48px',
      textAlign: 'center',
    }}>
      <div style={{
        width: 52,
        height: 52,
        borderRadius: '50%',
        border: '1.5px solid var(--border-mid)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 22,
        color: 'var(--ink-5)',
      }}>
        <WaveformIcon />
      </div>
      <h2 className="font-brand" style={{
        margin: '0 0 10px',
        fontSize: 22,
        fontWeight: 500,
        fontStyle: 'italic',
        color: 'var(--ink-3)',
        letterSpacing: '-0.01em',
      }}>
        No analysis yet
      </h2>
      <p style={{
        margin: 0,
        fontSize: 13,
        color: 'var(--ink-4)',
        lineHeight: 1.65,
        maxWidth: 260,
      }}>
        Select a track from the sidebar and run analysis to generate a Producer Session Pack.
      </p>
      <div style={{
        marginTop: 26,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 11,
        color: 'var(--ink-5)',
        fontFamily: 'Fragment Mono, monospace',
        letterSpacing: '0.06em',
      }}>
        <span>←</span>
        <span>choose from the sidebar</span>
      </div>
    </div>
  )
}

function ResultsView({ result }) {
  return (
    <div className="stagger" style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <SignalSummary    track={result.track}                   />
      <CriticTimeline   rounds={result.pipeline.critic_rounds} />
      <ConfidencePanel  pipeline={result.pipeline}             />
      <ProducerSettings settings={result.settings}            />
      <OutputDownloads  outputs={result.outputs} traceUrl={result.trace_url} />
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {[80, 140, 120, 200, 90].map((h, i) => (
        <div
          key={i}
          className="card"
          style={{
            height: h,
            animation: `skeleton-pulse 1.6s ease-in-out infinite`,
            animationDelay: `${i * 0.12}s`,
          }}
        />
      ))}
    </div>
  )
}

function WaveformIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <path d="M1 11h3M18 11h3M5 7v8M8 4v14M11 8v6M14 5v12M17 7v8"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
