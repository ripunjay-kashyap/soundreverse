export default function MusicianNotes({ musician }) {
  if (!musician) return null

  const {
    tuning_targets = [],
    tuning_tip,
    tonal_tags = [],
    tonal_character,
  } = musician

  const hasTonal = tonal_tags.length > 0 || tonal_character
  const hasTuning = tuning_targets.length > 0
  if (!hasTonal && !hasTuning) return null

  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 14 }}>For Musicians</p>

      {/* ── Tonal character ── */}
      {hasTonal && (
        <div style={{ marginBottom: hasTuning ? 20 : 0 }}>
          {tonal_tags.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              {tonal_tags.map(tag => (
                <span
                  key={tag}
                  className="font-mono"
                  style={{
                    fontSize: 11,
                    padding: '3px 10px',
                    borderRadius: 999,
                    background: 'var(--sage-pale)',
                    color: 'var(--sage)',
                    letterSpacing: '0.02em',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {tonal_character && (
            <p style={{ margin: 0, fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.65 }}>
              {tonal_character}
            </p>
          )}
        </div>
      )}

      {/* ── Sound & tuning targets ── */}
      {hasTuning && (
        <>
          {hasTonal && <div className="divider" style={{ marginBottom: 16 }} />}
          <p className="eyebrow" style={{ marginBottom: 12 }}>Sound &amp; Tuning Targets</p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {tuning_targets.map(t => (
              <div
                key={t.element}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--r-inner)',
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                }}
              >
                <span style={{ fontSize: 13, color: 'var(--ink-3)' }}>{t.element}</span>
                <span className="font-mono" style={{ fontSize: 13, color: 'var(--ink)' }}>
                  {t.hz} Hz
                  <span style={{ color: 'var(--amber)', marginLeft: 10 }}>&asymp; {t.note}</span>
                </span>
              </div>
            ))}
          </div>

          {tuning_tip && (
            <p
              style={{
                margin: '14px 0 0',
                fontSize: 12,
                color: 'var(--ink-4)',
                lineHeight: 1.6,
                fontStyle: 'italic',
              }}
            >
              {tuning_tip}
            </p>
          )}
        </>
      )}
    </div>
  )
}
