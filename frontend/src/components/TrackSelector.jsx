export default function TrackSelector({ tracks, selected, onChange }) {
  return (
    <div className="track-list">
      {tracks.map(t => (
        <button
          key={t.track_id}
          className={`track-item ${selected === t.track_id ? 'active' : ''}`}
          onClick={() => onChange(t.track_id)}
        >
          <span className="track-dot" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="track-name">{t.label}</div>
          </div>
          {t.stress_test && (
            <span className="stress-badge" title="Stress test — triggers 2 iterations">⚡</span>
          )}
        </button>
      ))}
    </div>
  )
}
