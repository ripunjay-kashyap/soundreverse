import Icon from "./Icon";

export default function TrackSelector({
  tracks,
  selected,
  disabled = false,
  pending = false,
  onChange,
}) {
  if (!tracks || tracks.length === 0)
    return (
      <div className="library-empty" role="status">
        <Icon name="music" />
        <p>
          {pending
            ? "Connecting to the demo library…"
            : "No demo tracks available. Upload a track to get started."}
        </p>
      </div>
    );
  return (
    <div className="track-list" role="group" aria-label="Choose a demo track">
      {tracks.map((t, i) => {
        const parts = t.label.split(/\s[—–-]\s/);
        return (
          <button
            key={t.track_id}
            type="button"
            className={`track-item${selected === t.track_id ? " is-active" : ""}`}
            disabled={disabled}
            onClick={() => onChange(t.track_id)}
            aria-pressed={selected === t.track_id}
          >
            <span className={`track-art track-art-${i % 4}`}>
              <Icon name="wave" size={20} />
            </span>
            <span className="track-copy">
              <strong>
                {parts.length > 1 ? parts.slice(1).join(" — ") : t.label}
              </strong>
              <span>{parts.length > 1 ? parts[0] : "Reference track"}</span>
            </span>
            <span className="track-check">
              {selected === t.track_id ? (
                <Icon name="check" size={15} />
              ) : (
                <span className="mono">{String(i + 1).padStart(2, "0")}</span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
