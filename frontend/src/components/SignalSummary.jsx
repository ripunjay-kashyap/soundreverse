export default function SignalSummary({ track }) {
  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 14 }}>Signal Signature</p>

      <div style={{ marginBottom: 20 }}>
        <h2 className="font-brand" style={{
          margin: 0,
          fontSize: 23,
          fontWeight: 600,
          color: 'var(--ink)',
          letterSpacing: '-0.02em',
          lineHeight: 1.2,
        }}>
          {track.title}
        </h2>
        <p style={{ margin: '5px 0 0', fontSize: 13.5, color: 'var(--ink-4)' }}>
          {track.artist}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        <StatBlock label="LUFS"  value={track.lufs?.toFixed(1)} unit="dB"  accent="sage"  />
        <StatBlock label="BPM"   value={track.bpm?.toFixed(0)}  unit=""    accent="amber" />
        <StatBlock label="KEY"   value={track.key}              unit=""    accent="clay"  />
      </div>
    </div>
  )
}

function StatBlock({ label, value, unit, accent }) {
  const colors = { sage: 'var(--sage)', amber: 'var(--amber)', clay: 'var(--clay)' }
  const color  = colors[accent]
  // Keys are alphanumeric and longer ("Eb Minor") — scale down vs. pure numerals.
  const isText = typeof value === 'string' && /[a-zA-Z]/.test(value)

  return (
    <div className="stat-block">
      <p className="eyebrow" style={{ marginBottom: 10, color, opacity: 0.85 }}>{label}</p>
      <div className="display-num" style={{
        fontSize: isText ? 22 : 34,
        color: 'var(--ink)',
        display: 'flex',
        alignItems: 'baseline',
        gap: 4,
        minHeight: 34,
      }}>
        {value ?? '—'}
        {unit && (
          <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--ink-4)', letterSpacing: 0 }}>{unit}</span>
        )}
      </div>
    </div>
  )
}
