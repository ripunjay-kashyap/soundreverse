import { useState, useEffect } from 'react'
import TrackSelector from './components/TrackSelector'
import FileUpload from './components/FileUpload'
import AnalyzeButton from './components/AnalyzeButton'
import SignalSummary from './components/SignalSummary'
import MusicianNotes from './components/MusicianNotes'
import ConfidencePanel from './components/ConfidencePanel'
import CriticTimeline from './components/CriticTimeline'
import ProducerSettings from './components/ProducerSettings'
import OutputDownloads from './components/OutputDownloads'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export default function App() {
  const [tracks, setTracks]           = useState([])
  const [uploadedFile, setUploadedFile] = useState(null)
  const [selectedDemo, setSelectedDemo] = useState('')
  const [result, setResult]             = useState(null)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState(null)
  const [booting, setBooting]           = useState(true)
  const [splashExiting, setSplashExiting] = useState(false)

  // 3s branded splash on first load: hold 2.5s, fade 0.5s, then unmount.
  useEffect(() => {
    const fade    = setTimeout(() => setSplashExiting(true), 2500)
    const unmount = setTimeout(() => setBooting(false), 3000)
    return () => { clearTimeout(fade); clearTimeout(unmount) }
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/tracks`)
      .then(r => r.json())
      .then(data => setTracks(data))          // no auto-select: upload is the default action
      .catch(() => setError('Failed to load tracks'))
  }, [])

  // Shared polling loop: resolves with job result or rejects with an error message.
  function pollJob(jobId) {
    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const poll = await fetch(`${API_BASE}/jobs/${jobId}`)
          if (!poll.ok) { clearInterval(interval); reject(new Error(`Poll error ${poll.status}`)); return }
          const job = await poll.json()
          if (job.status === 'completed') { clearInterval(interval); resolve(job.result) }
          else if (job.status === 'failed') { clearInterval(interval); reject(new Error(job.error || 'Job failed')) }
          // pending / processing → keep polling
        } catch (e) { clearInterval(interval); reject(e) }
      }, 3000)
    })
  }

  // Wraps any fetch that returns {job_id}, polls to completion, and sets state.
  async function submit(makeRequest) {
    setLoading(true); setResult(null); setError(null)
    try {
      const res = await makeRequest()
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        // FastAPI 422 detail is an array of validation objects — extract the first message.
        const detail = err.detail
        const msg = Array.isArray(detail)
          ? (detail[0]?.msg || `HTTP ${res.status}`)
          : (typeof detail === 'string' ? detail : `HTTP ${res.status}`)
        throw new Error(msg)
      }
      const { job_id } = await res.json()
      const data = await pollJob(job_id)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleAnalyze() {
    if (uploadedFile) {
      const fd = new FormData()
      fd.append('file', uploadedFile)
      submit(() => fetch(`${API_BASE}/analyze`, { method: 'POST', body: fd }))
    } else if (selectedDemo) {
      submit(() => fetch(`${API_BASE}/demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_id: selectedDemo }),
      }))
    }
  }

  return (
    <>
    {booting && <Splash exiting={splashExiting} />}
    <div className="app-layout">

      {/* ── Left Sidebar ── */}
      <aside className="sidebar">

        {/* Brand */}
        <div style={{ padding: '32px 24px 24px' }}>
          <p className="eyebrow" style={{ marginBottom: 8 }}>Audio Intelligence</p>
          <h1 className="font-brand" style={{
            margin: 0,
            fontSize: 27,
            fontWeight: 700,
            color: '#ffffff',
            lineHeight: 1.1,
            letterSpacing: '-0.035em',
          }}>
            Sound<span style={{ color: 'rgba(255,255,255,0.55)' }}>Reverse</span>
          </h1>
          <p style={{
            margin: '8px 0 0',
            fontSize: 12,
            color: 'rgba(255,255,255,0.55)',
            lineHeight: 1.5,
          }}>
            LangGraph multi-agent mastering analysis
          </p>
        </div>

        <div className="divider" style={{ margin: '0 24px' }} />

        {/* Track list */}
        <div style={{ padding: '20px 16px', flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          <p className="eyebrow" style={{ marginBottom: 12, paddingLeft: 4 }}>Upload a Track</p>
          <div style={{ marginBottom: 20 }}>
            <FileUpload onFileChange={(f) => { setUploadedFile(f); if (f) setSelectedDemo('') }} />
          </div>

          <p className="eyebrow" style={{ marginBottom: 12, paddingLeft: 4 }}>Or try a demo</p>
          <TrackSelector tracks={tracks} selected={selectedDemo} onChange={(id) => { setSelectedDemo(id); setUploadedFile(null) }} />

          {/* Decorative spectrum — sits below the track list */}
          <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', paddingTop: 24, paddingBottom: 4 }}>
            <SidebarSpectrum />
          </div>
        </div>

        {/* Analyze + footer */}
        <div style={{ padding: '16px 20px 24px', borderTop: '1px solid rgba(255,255,255,0.15)' }}>
          {error && (
            <div style={{
              marginBottom: 12,
              padding: '10px 14px',
              background: 'var(--clay-pale)',
              border: '1px solid var(--clay-border)',
              borderRadius: 'var(--r-inner)',
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--clay)',
            }}>
              ⚠ {error}
            </div>
          )}
          <AnalyzeButton
            loading={loading}
            disabled={!uploadedFile && !selectedDemo}
            onClick={handleAnalyze}
          />
        </div>
      </aside>

      {/* ── Right Panel ── */}
      <main className="output-panel">
        {loading ? (
          <LoadingState label={uploadedFile ? uploadedFile.name : (tracks.find(t => t.track_id === selectedDemo)?.label || '')} />
        ) : result ? (
          <ResultsView result={result} />
        ) : (
          <EmptyState />
        )}
      </main>
    </div>
    </>
  )
}

function Splash({ exiting }) {
  return (
    <div className={`splash${exiting ? ' exiting' : ''}`}>
      <div className="splash-mark" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22 }}>
        <p className="eyebrow" style={{ margin: 0, color: 'var(--ink-4)' }}>Audio Intelligence</p>
        <h1 className="font-brand" style={{
          margin: 0,
          fontSize: 44,
          fontWeight: 700,
          color: 'var(--ink)',
          letterSpacing: '-0.04em',
          lineHeight: 1,
        }}>
          Sound<span style={{ color: 'var(--ink-4)' }}>Reverse</span>
        </h1>
        <BootSpinner />
      </div>
    </div>
  )
}

function BootSpinner() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none" style={{ marginTop: 4 }}>
      <circle cx="15" cy="15" r="12" stroke="var(--sage-border)" strokeWidth="2.5" />
      <circle
        cx="15" cy="15" r="12"
        stroke="var(--sage)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="20 56"
        style={{ animation: 'spin-slow 0.85s linear infinite', transformOrigin: '15px 15px' }}
      />
    </svg>
  )
}

function EmptyState() {
  return (
    <div style={{
      position: 'relative',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 48px',
      textAlign: 'center',
      overflow: 'hidden',
    }}>
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="pulse-breathe" style={{
          width: 56,
          height: 56,
          borderRadius: '50%',
          background: 'var(--ink)',
          border: 'none',
          boxShadow: 'var(--shadow-sm)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 22,
          color: '#ffffff',
        }}>
          <WaveformIcon />
        </div>
        <h2 className="font-brand" style={{
          margin: '0 0 10px',
          fontSize: 23,
          fontWeight: 600,
          color: 'var(--ink-2)',
          letterSpacing: '-0.02em',
        }}>
          No analysis yet
        </h2>
        <p style={{
          margin: 0,
          fontSize: 13.5,
          color: 'var(--ink-4)',
          lineHeight: 1.65,
          maxWidth: 280,
        }}>
          Select a track from the sidebar and run analysis to generate a Producer Session Pack.
        </p>
        <div className="pill" style={{
          marginTop: 26,
          background: 'var(--ink)',
          border: 'none',
          boxShadow: 'var(--shadow-xs)',
          color: '#ffffff',
          letterSpacing: '0.04em',
        }}>
          <span>←</span>
          <span>choose from the sidebar</span>
        </div>
      </div>
    </div>
  )
}

function ResultsView({ result }) {
  return (
    <div className="stagger" style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <SignalSummary    track={result.track}                   />
      <MusicianNotes    musician={result.musician}             />
      <CriticTimeline   rounds={result.pipeline.critic_rounds} />
      <ConfidencePanel  pipeline={result.pipeline}             />
      <ProducerSettings settings={result.settings}            />
      <OutputDownloads  outputs={result.outputs} traceUrl={result.trace_url} />
    </div>
  )
}

const LOADING_STAGES = [
  'Researching the track',
  'Reading the signal signature',
  'Mapping producer settings',
  'Cross-checking with the critic',
  'Finalizing your session pack',
]

// TODO(mcp-integration): these captions currently cycle on a timer (cosmetic only) —
// they convey what the pipeline does, not real live status. Once the backend reports a
// live `stage` in GET /jobs/{id} (see api.py placeholders), pass it in as a prop and
// render that instead of the timer-driven index below.
function LoadingState({ label }) {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setStage(s => (s + 1) % LOADING_STAGES.length), 2800)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="loading-state anim-fade">
      <WaveformViz />
      <h2 className="font-brand" style={{
        margin: '16px 0 0',
        fontSize: 24,
        fontWeight: 600,
        color: 'var(--ink-2)',
        letterSpacing: '-0.02em',
      }}>
        Analyzing…
      </h2>
      {label && (
        <p style={{ margin: '6px 0 0', fontSize: 14, color: 'var(--ink-3)', maxWidth: 320 }}>
          {label}
        </p>
      )}

      <p
        key={stage}
        className="eyebrow anim-fade"
        style={{ marginTop: 24, color: 'var(--ink-4)', opacity: 0.9 }}
      >
        {LOADING_STAGES[stage]}
      </p>

      <p style={{
        margin: '14px 0 0',
        fontSize: 12.5,
        color: 'var(--ink-4)',
        lineHeight: 1.6,
        maxWidth: 300,
      }}>
        This can take up to a minute — hang tight and keep this tab open.
      </p>
    </div>
  )
}

// 16-bar animated waveform visualizer — replaces spinner in loading state.
// Each bar gets a unique --max-h and a negative animationDelay so all bars
// start mid-cycle (already at different phases) instead of all bouncing together.
const WVZ_HEIGHTS = [4, 8, 14, 20, 12, 26, 32, 22, 36, 28, 30, 20, 24, 16, 10, 5]

function WaveformViz() {
  return (
    <div className="waveform-viz">
      {WVZ_HEIGHTS.map((h, i) => (
        <div
          key={i}
          className="wvz-bar"
          style={{
            '--max-h': `${h}px`,
            animationDelay: `${-(i * 0.072).toFixed(3)}s`,
          }}
        />
      ))}
    </div>
  )
}

// Decorative frequency-spectrum bars for the sidebar bottom — purely atmospheric.
const SPECTRUM_HEIGHTS = [2,4,7,11,8,15,10,19,13,17,21,15,19,13,17,11,15,9,13,7,11,6,9,5,7,4,6,3,5,3,4,2]

function SidebarSpectrum() {
  const max = Math.max(...SPECTRUM_HEIGHTS)
  return (
    <div className="sidebar-spectrum" style={{ width: '100%' }}>
      {SPECTRUM_HEIGHTS.map((h, i) => (
        <div
          key={i}
          className="sidebar-spectrum-bar"
          style={{ height: `${(h / max) * 100}%` }}
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

function ArrowIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
      <path d="M3 7.5h8M7.5 4l3.5 3.5-3.5 3.5"
        stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
