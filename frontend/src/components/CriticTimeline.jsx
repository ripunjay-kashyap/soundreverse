export default function CriticTimeline({ rounds }) {
  if (!rounds || rounds.length === 0) return null

  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 18 }}>Critic Timeline</p>

      <div style={{ position: 'relative', paddingLeft: 24 }}>
        <div className="timeline-stem" />

        <ol style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {rounds.map((round, i) => {
            const isRejected = round.rejected
            return (
              <li key={i} style={{ position: 'relative' }}>
                {/* Node */}
                <div style={{
                  position: 'absolute',
                  left: -24,
                  top: 4,
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  border: `1.5px solid ${isRejected ? 'var(--clay)' : 'var(--sage)'}`,
                  background: isRejected ? 'var(--clay-pale)' : 'var(--sage-pale)',
                }} />

                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                  <span className="font-mono" style={{ fontSize: 10, color: 'var(--ink-4)', letterSpacing: '0.1em' }}>
                    ITER {round.iteration}
                  </span>
                  <span className={`badge ${isRejected ? 'badge-clay' : 'badge-sage'}`}>
                    {isRejected ? 'REJECTED' : 'APPROVED'}
                  </span>
                  <span className="font-mono" style={{ fontSize: 11, color: 'var(--ink-4)' }}>
                    {Math.round(round.confidence * 100)}%
                  </span>
                </div>

                {round.reason && (
                  <p className="font-mono" style={{
                    margin: 0,
                    fontSize: 11,
                    color: 'var(--ink-3)',
                    lineHeight: 1.65,
                    paddingLeft: 10,
                    borderLeft: `2px solid ${isRejected ? 'var(--clay-border)' : 'var(--sage-border)'}`,
                  }}>
                    {round.reason}
                  </p>
                )}
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
