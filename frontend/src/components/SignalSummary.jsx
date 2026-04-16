export default function SignalSummary({ track }) {
  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 14 }}>Signal Signature</p>

      <div style={{ marginBottom: 18 }}>
        <h2 className="font-brand" style={{
          margin: 0,
          fontSize: 20,
          fontWeight: 500,
          fontStyle: 'italic',
          color: 'var(--ink)',
          letterSpacing: '-0.01em',
          lineHeight: 1.2,
        }}>
          {track.title}
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--ink-4)' }}>
          {track.artist}
        </p>
      </div>

      <div className="divider" style={{ marginBottom: 18 }} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <StatBlock label="LUFS"  value={track.lufs?.toFixed(1)} unit="dB"  accent="sage"  />
        <StatBlock label="BPM"   value={track.bpm?.toFixed(1)}  unit=""    accent="amber" />
        <StatBlock label="KEY"   value={track.key}              unit=""    accent="clay"  />
      </div>
    </div>
  )
}

function StatBlock({ label, value, unit, accent }) {
  const colors = { sage: 'var(--sage)', amber: 'var(--amber)', clay: 'var(--clay)' }
  const bgs    = { sage: 'var(--sage-pale)', amber: 'var(--amber-pale)', clay: 'var(--clay-pale)' }
  const color  = colors[accent]
  const bg     = bgs[accent]

  return (
    <div className="stat-block">
      <p className="eyebrow" style={{ marginBottom: 8, color }}>{label}</p>
      <div className="font-mono" style={{ fontSize: 20, color, lineHeight: 1 }}>
        {value ?? '—'}
        {unit && (
          <span style={{ fontSize: 11, color: 'var(--ink-4)', marginLeft: 4 }}>{unit}</span>
        )}
      </div>
    </div>
  )
}
