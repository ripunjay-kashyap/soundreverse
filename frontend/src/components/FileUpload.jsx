import { useRef, useState } from 'react'

// Frontend-only for now: captures a file into local state so the section is
// fully interactive (drag-drop, validation, selected chip). Nothing is sent —
// there is no backend upload endpoint yet (audio analysis lives in the MCP).
// TODO(mcp-integration): when an upload endpoint exists, lift the File via
// `onFileChange` and POST it instead of the song-query string.

const ACCEPT = '.wav,.mp3,.flac,.aiff,.aif,.m4a,.ogg'
const VALID  = /\.(wav|mp3|flac|aiff?|m4a|ogg)$/i
const MAX_MB = 50

function formatSize(bytes) {
  if (bytes < 1024)        return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileUpload({ onFileChange }) {
  const inputRef            = useRef(null)
  const [file, setFile]     = useState(null)
  const [drag, setDrag]     = useState(false)
  const [error, setError]   = useState(null)

  function take(f) {
    if (!f) return
    if (!VALID.test(f.name)) {
      setError('Unsupported file — use WAV, MP3, FLAC, AIFF, M4A, or OGG')
      return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File too large — max ${MAX_MB} MB`)
      return
    }
    setError(null)
    setFile(f)
    onFileChange?.(f)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDrag(false)
    take(e.dataTransfer.files?.[0])
  }

  function clear(e) {
    e.stopPropagation()
    setFile(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
    onFileChange?.(null)
  }

  if (file) {
    return (
      <div className="upload-file">
        <span className="upload-file-icon"><NoteIcon /></span>
        <div className="upload-file-meta">
          <div className="upload-file-name" title={file.name}>{file.name}</div>
          <div className="upload-file-size">{formatSize(file.size)} · ready</div>
        </div>
        <button className="upload-remove" onClick={clear} aria-label="Remove file" title="Remove">
          <CloseIcon />
        </button>
      </div>
    )
  }

  return (
    <>
      <button
        type="button"
        className={`upload-zone${drag ? ' dragover' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
      >
        <span className="upload-zone-icon"><UploadIcon /></span>
        <span className="upload-zone-title">{drag ? 'Drop to load' : 'Drop an audio track'}</span>
        <span className="upload-zone-hint">or click to browse · WAV, MP3, FLAC</span>
        <input ref={inputRef} type="file" accept={ACCEPT} onChange={(e) => take(e.target.files?.[0])} hidden />
      </button>
      {error && <p className="upload-error">⚠ {error}</p>}
    </>
  )
}

function UploadIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 17 17" fill="none">
      <path d="M8.5 11V2.5M8.5 2.5 5 6M8.5 2.5 12 6M2.5 11v2.5a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V11"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function NoteIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
      <path d="M5.5 11.5V4l6-1.5v7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="3.75" cy="11.5" r="1.75" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="9.75" cy="9.5" r="1.75" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
      <path d="M3.5 3.5l6 6M9.5 3.5l-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}
