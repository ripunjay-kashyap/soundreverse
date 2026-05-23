const R    = 40
const CIRC = 2 * Math.PI * R  // ≈ 251

function arcColor(c) {
  if (c >= 0.75) return 'var(--sage)'
  if (c >= 0.5)  return 'var(--amber)'
  return 'var(--clay)'
}

export default function ConfidencePanel({ pipeline }) {
  const { confidence, iteration_count, max_iterations, validation_checks } = pipeline
  const pct    = Math.round(confidence * 100)
  const color  = arcColor(confidence)
  const filled = CIRC * confidence

  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 18 }}>Confidence Verdict</p>

      <div style={{ display: 'flex', gap: 28, alignItems: 'flex-start', flexWrap: 'wrap' }}>

        {/* Arc meter */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <svg width="100" height="100" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r={R} fill="none" stroke="var(--border-mid)" strokeWidth="4" />
            <circle
              cx="50" cy="50" r={R}
              fill="none"
              stroke={color}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={`${filled} ${CIRC}`}
              transform="rotate(-90 50 50)"
              style={{ transition: 'stroke-dasharray 1s cubic-bezier(0.16,1,0.3,1)' }}
            />
          </svg>
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
          }}>
            <span className="display-num" style={{ fontSize: 30, color, lineHeight: 1 }}>{pct}</span>
            <span className="font-mono" style={{ fontSize: 8, fontWeight: 600, color: 'var(--ink-4)', letterSpacing: '0.18em', marginTop: 4 }}>PCT</span>
          </div>
        </div>

        {/* Right: iterations + checks */}
        <div style={{ flex: 1, minWidth: 160, display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Iterations bar */}
          <div>
            <p className="eyebrow" style={{ marginBottom: 8 }}>Iterations</p>
            <div style={{ display: 'flex', gap: 5 }}>
              {Array.from({ length: max_iterations }).map((_, i) => (
                <div key={i} style={{
                  height: 4,
                  flex: 1,
                  borderRadius: 2,
                  background: i < iteration_count ? color : 'var(--border-mid)',
                  transition: 'background 0.4s',
                }} />
              ))}
            </div>
            <p className="font-mono" style={{ margin: '6px 0 0', fontSize: 10, color: 'var(--ink-4)' }}>
              {iteration_count} of {max_iterations} used
            </p>
          </div>

          {/* Validation checks */}
          {validation_checks?.length > 0 && (
            <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {validation_checks.map((chk, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <span style={{
                    flexShrink: 0,
                    marginTop: 1,
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    border: `1px solid ${chk.passed ? 'var(--sage-border)' : 'var(--clay-border)'}`,
                    background: chk.passed ? 'var(--sage-pale)' : 'var(--clay-pale)',
                    color: chk.passed ? 'var(--sage)' : 'var(--clay)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    fontWeight: 700,
                  }}>
                    {chk.passed ? '✓' : '✗'}
                  </span>
                  <div>
                    <span style={{ fontSize: 12.5, color: 'var(--ink-2)' }}>{chk.name}</span>
                    {chk.detail && (
                      <p className="font-mono" style={{ margin: '2px 0 0', fontSize: 10, color: 'var(--ink-4)', lineHeight: 1.5 }}>
                        {chk.detail}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
