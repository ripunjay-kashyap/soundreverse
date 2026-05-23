function gainColor(g) {
  if (g > 0) return 'var(--sage)'
  if (g < 0) return 'var(--clay)'
  return 'var(--ink-4)'
}

function GainBar({ gain }) {
  const MAX    = 6
  const pct    = (Math.min(Math.abs(gain), MAX) / MAX) * 100
  const isPos  = gain >= 0
  const color  = gainColor(gain)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, width: 64 }}>
      <div style={{ flex: 1, height: 3, background: 'var(--border-mid)', borderRadius: 2, display: 'flex', justifyContent: 'flex-end' }}>
        {!isPos && (
          <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transformOrigin: 'right', animation: 'bar-grow 0.5s ease both' }} />
        )}
      </div>
      <div style={{ width: 1, height: 8, background: 'var(--border-strong)', flexShrink: 0 }} />
      <div style={{ flex: 1, height: 3, background: 'var(--border-mid)', borderRadius: 2 }}>
        {isPos && gain !== 0 && (
          <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, animation: 'bar-grow 0.5s ease both' }} />
        )}
      </div>
    </div>
  )
}

export default function ProducerSettings({ settings }) {
  if (!settings) return null
  const { eq, compression, compression_skip_reason, master_gain_db, master_gain_reason } = settings

  return (
    <div className="card-section anim-fade">
      <p className="eyebrow" style={{ marginBottom: 18 }}>Producer Settings</p>

      {/* EQ Bands */}
      {eq?.length > 0 && (
        <section style={{ marginBottom: 22 }}>
          <p className="font-mono" style={{ margin: '0 0 10px', fontSize: 10, color: 'var(--ink-4)', letterSpacing: '0.1em' }}>
            EQ BANDS
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {eq.map((band, i) => (
              <div key={i} style={{
                display: 'grid',
                gridTemplateColumns: 'auto auto auto auto 1fr',
                gap: '0 14px',
                alignItems: 'center',
                padding: '11px 14px',
                background: 'var(--surface)',
                borderRadius: 'var(--r-inner)',
                border: '1px solid var(--border)',
                animationDelay: `${i * 0.06}s`,
              }}>
                <span className="badge badge-sage">{band.band}</span>

                <span className="font-mono" style={{ fontSize: 12.5, color: 'var(--ink-2)', whiteSpace: 'nowrap' }}>
                  {band.freq}<span style={{ fontSize: 9, color: 'var(--ink-4)', marginLeft: 2 }}>Hz</span>
                </span>

                <span className="font-mono" style={{ fontSize: 12.5, fontWeight: 600, color: gainColor(band.gain_db), whiteSpace: 'nowrap', minWidth: 40 }}>
                  {band.gain_db > 0 ? '+' : ''}{band.gain_db}
                  <span style={{ fontSize: 9, color: 'var(--ink-4)', marginLeft: 2 }}>dB</span>
                </span>

                <GainBar gain={band.gain_db} />

                <p className="font-mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--ink-3)', lineHeight: 1.55 }}>
                  {band.reason}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Compression + Master Gain */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 16,
        paddingTop: 18,
        borderTop: '1px solid var(--border)',
      }}>
        {/* Compression */}
        <div>
          <p className="font-mono" style={{ margin: '0 0 12px', fontSize: 10, color: 'var(--ink-4)', letterSpacing: '0.1em' }}>
            BUS COMPRESSION
          </p>
          {compression ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {[
                { label: 'Ratio',   value: compression.ratio,      unit: ''   },
                { label: 'Attack',  value: compression.attack_ms,  unit: 'ms' },
                { label: 'Release', value: compression.release_ms, unit: 'ms' },
              ].map(({ label, value, unit }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 11, color: 'var(--ink-4)', width: 50 }}>{label}</span>
                  <span className="font-mono" style={{ fontSize: 12.5, color: 'var(--ink-2)' }}>
                    {value}
                    {unit && <span style={{ fontSize: 9, color: 'var(--ink-4)', marginLeft: 2 }}>{unit}</span>}
                  </span>
                </div>
              ))}
              {compression.reason && (
                <p className="font-mono" style={{ margin: '4px 0 0', fontSize: 10.5, color: 'var(--ink-3)', lineHeight: 1.55 }}>
                  {compression.reason}
                </p>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              <span className="badge badge-muted" style={{ alignSelf: 'flex-start' }}>Skipped</span>
              <p className="font-mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--ink-3)', lineHeight: 1.55 }}>
                {compression_skip_reason || 'already heavily compressed'}
              </p>
            </div>
          )}
        </div>

        {/* Master Gain */}
        <div>
          <p className="font-mono" style={{ margin: '0 0 12px', fontSize: 10, color: 'var(--ink-4)', letterSpacing: '0.1em' }}>
            MASTER GAIN
          </p>
          <div style={{ marginBottom: 8 }}>
            <span className="display-num" style={{ fontSize: 38, color: gainColor(master_gain_db), lineHeight: 1 }}>
              {master_gain_db > 0 ? '+' : ''}{master_gain_db}
            </span>
            <span className="font-mono" style={{ fontSize: 12, color: 'var(--ink-4)', marginLeft: 6 }}>dB</span>
          </div>
          {master_gain_reason && (
            <p className="font-mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--ink-3)', lineHeight: 1.55 }}>
              {master_gain_reason}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
