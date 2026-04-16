export default function AnalyzeButton({ loading, onClick }) {
  return (
    <button className="analyze-btn" onClick={onClick} disabled={loading}>
      {loading ? (
        <>
          <Spinner />
          Analyzing…
        </>
      ) : (
        'Run Analysis'
      )}
    </button>
  )
}

function Spinner() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" style={{ flexShrink: 0 }}>
      <circle cx="7.5" cy="7.5" r="6" stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" />
      <circle
        cx="7.5" cy="7.5" r="6"
        stroke="white"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="9 28"
        style={{ animation: 'spin-slow 0.85s linear infinite', transformOrigin: '7.5px 7.5px' }}
      />
    </svg>
  )
}
