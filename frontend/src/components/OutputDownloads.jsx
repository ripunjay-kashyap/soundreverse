export default function OutputDownloads({ outputs, traceUrl }) {
  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 16 }}>Session Outputs</p>

      {/* Downloads */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: traceUrl ? 18 : 0 }}>
        <DownloadPill href={outputs?.pdf_url}      label="Blueprint"    ext="PDF"  accent="sage"  />
        <DownloadPill href={outputs?.json_url}     label="Preset"       ext="JSON" accent="amber" />
        <DownloadPill href={outputs?.metadata_url} label="Run Metadata" ext="JSON" accent="clay"  />
      </div>

      {/* LangSmith trace */}
      {traceUrl && (
        <div style={{
          paddingTop: 16,
          borderTop: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
        }}>
          <div style={{
            flexShrink: 0,
            width: 26,
            height: 26,
            borderRadius: '50%',
            background: 'var(--sage-pale)',
            border: '1px solid var(--sage-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--sage)',
          }}>
            <TraceIcon />
          </div>
          <div style={{ minWidth: 0 }}>
            <p className="eyebrow" style={{ marginBottom: 5 }}>LangSmith Trace</p>
            <a
              href={traceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono"
              style={{
                fontSize: 10.5,
                color: 'var(--sage)',
                textDecoration: 'none',
                wordBreak: 'break-all',
                lineHeight: 1.5,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                opacity: 0.85,
                transition: 'opacity 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '1'}
              onMouseLeave={e => e.currentTarget.style.opacity = '0.85'}
            >
              {traceUrl}
              <ExternalIcon />
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

function DownloadPill({ href, label, ext, accent }) {
  if (!href) return null
  const styles = {
    sage:  { color: 'var(--sage)',  bg: 'var(--sage-pale)',  border: 'var(--sage-border)'  },
    amber: { color: 'var(--amber)', bg: 'var(--amber-pale)', border: 'var(--amber-border)' },
    clay:  { color: 'var(--clay)',  bg: 'var(--clay-pale)',  border: 'var(--clay-border)'  },
  }
  const s = styles[accent]

  return (
    <a
      href={href}
      download
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 16px',
        background: s.bg,
        border: `1px solid ${s.border}`,
        borderRadius: 8,
        textDecoration: 'none',
        transition: 'box-shadow 0.2s',
      }}
      onMouseEnter={e => e.currentTarget.style.boxShadow = `0 2px 10px rgba(0,0,0,0.06)`}
      onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
    >
      <DownloadIcon color={s.color} />
      <span style={{ fontSize: 13, color: 'var(--ink-2)', fontFamily: 'DM Sans, sans-serif' }}>{label}</span>
      <span className="font-mono" style={{
        fontSize: 9,
        color: s.color,
        background: 'rgba(28,23,20,0.04)',
        padding: '2px 6px',
        borderRadius: 4,
        letterSpacing: '0.08em',
      }}>
        {ext}
      </span>
    </a>
  )
}

function DownloadIcon({ color }) {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
      <path d="M6.5 1v7.5M4 6l2.5 2.5L9 6" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M1.5 10.5h10" stroke={color} strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  )
}

function TraceIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
      <circle cx="5.5" cy="5.5" r="4.5" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M5.5 3.5v3M3.5 5.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  )
}

function ExternalIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0 }}>
      <path d="M4 2H2a1 1 0 00-1 1v5a1 1 0 001 1h5a1 1 0 001-1V6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
      <path d="M6.5 1h2.5v2.5M9 1L5.5 4.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
