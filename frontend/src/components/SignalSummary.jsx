import { useState, useEffect } from 'react'

// Animates a numeric target from 0 → target over `duration` ms with cubic ease-out.
// Returns the current animated value. Non-numeric targets are returned as-is.
function useCountUp(target, duration = 1000) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    if (target == null) return
    const num = parseFloat(target)
    if (isNaN(num)) return
    let raf
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)   // cubic ease-out
      setVal(num * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
      else setVal(num)                          // snap to exact value
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, duration])
  return val
}

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
        <StatBlock label="LUFS"  rawValue={track.lufs}  format={v => v.toFixed(1)} unit="dB"  accent="sage"  />
        <StatBlock label="BPM"   rawValue={track.bpm}   format={v => Math.round(v).toString()} unit=""  accent="amber" />
        <StatBlock label="KEY"   value={track.key}      unit=""    accent="clay"  isText />
      </div>
    </div>
  )
}

// StatBlock with count-up for numeric values, plain reveal for text.
function StatBlock({ label, rawValue, value, format, unit, accent, isText = false }) {
  const colors = { sage: 'var(--sage)', amber: 'var(--amber)', clay: 'var(--clay)' }
  const color  = colors[accent]

  const animated = useCountUp(isText ? null : rawValue)
  const displayVal = isText
    ? (value ?? '—')
    : rawValue != null
      ? format(animated)
      : '—'

  const isLong = typeof displayVal === 'string' && /[a-zA-Z]/.test(displayVal)

  return (
    <div className="stat-block">
      <p className="eyebrow" style={{ marginBottom: 10, color, opacity: 0.85 }}>{label}</p>
      <div className="display-num" style={{
        fontSize: isLong ? 22 : 34,
        color: 'var(--ink)',
        display: 'flex',
        alignItems: 'baseline',
        gap: 4,
        minHeight: 34,
      }}>
        {displayVal}
        {unit && (
          <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--ink-4)', letterSpacing: 0 }}>{unit}</span>
        )}
      </div>
    </div>
  )
}
