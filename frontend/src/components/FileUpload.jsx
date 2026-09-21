import { useRef, useState } from "react";
import Icon from "./Icon";

// Keep validation aligned with the existing API contract.
const ACCEPT = ".wav,.mp3";
const VALID = /\.(wav|mp3)$/i;
const MAX_MB = 50;

export default function FileUpload({ file, disabled = false, onFileChange }) {
  const inputRef = useRef(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState(null);

  function take(f) {
    if (!f || disabled) return;
    if (!VALID.test(f.name)) {
      setError("Choose a WAV or MP3 file.");
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`Choose a file smaller than ${MAX_MB} MB.`);
      return;
    }
    setError(null);
    onFileChange(f);
  }

  return (
    <div className="upload-control">
      <input
        id="audio-upload"
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        disabled={disabled}
        aria-label="Upload a WAV or MP3 track"
        onChange={(e) => {
          take(e.target.files?.[0]);
          e.target.value = "";
        }}
        hidden
      />
      {file ? (
        <div className="selected-file">
          <span className="upload-symbol">
            <Icon name="music" size={24} />
          </span>
          <div>
            <strong title={file.name}>{file.name}</strong>
            <span className="mono">
              {(file.size / (1024 * 1024)).toFixed(1)} MB · Ready to analyse
            </span>
          </div>
          <button
            className="icon-button"
            disabled={disabled}
            onClick={() => {
              onFileChange(null);
              setError(null);
            }}
            aria-label={`Remove ${file.name}`}
          >
            <Icon name="close" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          className={`dropzone${drag ? " is-over" : ""}`}
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            take(e.dataTransfer.files?.[0]);
          }}
        >
          <span className="upload-symbol">
            <Icon name="upload" size={24} />
          </span>
          <strong>
            {drag ? "Let your track land here" : "Drop your track here"}
          </strong>
          <span>
            or <span className="upload-link">browse files</span>
          </span>
          <span className="upload-formats mono">WAV / MP3 · UP TO 50 MB</span>
        </button>
      )}
      {error && (
        <p className="upload-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
