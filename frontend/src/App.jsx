import { useState, useEffect, useCallback, useRef } from "react";
import TrackSelector from "./components/TrackSelector";
import FileUpload from "./components/FileUpload";
import AnalyzeButton from "./components/AnalyzeButton";
import SignalSummary from "./components/SignalSummary";
import MusicianNotes from "./components/MusicianNotes";
import ConfidencePanel from "./components/ConfidencePanel";
import CriticTimeline from "./components/CriticTimeline";
import ProducerSettings from "./components/ProducerSettings";
import OutputDownloads from "./components/OutputDownloads";
import FrequencyMap from "./components/FrequencyMap";
import SignalScene from "./components/SignalScene";
import Icon from "./components/Icon";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

// ── Health-check with retry for Render cold-start ────────────────────────────
const HEALTH_POLL_MS = 2500; // retry interval
const HEALTH_TIMEOUT = 90_000; // give up after 90s
const MIN_CONNECTION_MS = 2200; // preserve the existing connection timing
const MAX_POLL_RETRIES = 4; // consecutive job-poll failures tolerated before giving up

function useBackendReady() {
  const [ready, setReady] = useState(false);
  const [waiting, setWaiting] = useState(false); // true after first failed ping

  useEffect(() => {
    let cancelled = false;
    const t0 = Date.now();

    async function ping() {
      try {
        const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (res.ok && !cancelled) {
          // Validate response is actually our API (not an SPA fallback serving HTML)
          const body = await res.json();
          if (body?.status !== "ok") return false;
          // Preserve existing readiness timing while the workspace stays visible.
          const remaining = MIN_CONNECTION_MS - (Date.now() - t0);
          if (remaining > 0) await new Promise((r) => setTimeout(r, remaining));
          if (!cancelled) setReady(true);
          return true;
        }
      } catch {
        /* network error or JSON parse error — backend not up yet */
      }
      return false;
    }

    (async () => {
      // First ping — fast path for warm server
      if (await ping()) {
        return;
      }
      if (cancelled) {
        return;
      }
      setWaiting(true);

      // Retry loop
      while (!cancelled && Date.now() - t0 < HEALTH_TIMEOUT) {
        await new Promise((r) => setTimeout(r, HEALTH_POLL_MS));
        if (cancelled) break;
        if (await ping()) {
            return;
        }
      }
      // Timeout — let the user in anyway (tracks fetch will show its own error)
      if (!cancelled) setReady(true);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return { ready, waiting };
}

// Theme lives on <html data-theme>. index.html resolves it before first paint,
// so this hook only has to read that value back and keep it in sync.
function useTheme() {
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || "light",
  );

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem("sr-theme", next);
      } catch {
        /* private mode */
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}

// Pull the server's own explanation out of an error response.
// FastAPI's 422 `detail` is an array of validation objects — take the first message.
async function readErrorDetail(res) {
  const body = await res.json().catch(() => ({}));
  const detail = body?.detail;
  if (Array.isArray(detail)) return detail[0]?.msg || `HTTP ${res.status}`;
  if (typeof detail === "string") return detail;
  return `HTTP ${res.status}`;
}

// fetch() rejects with a bare `TypeError: Failed to fetch` for every network-level
// failure — server asleep, connection reset, or a response the browser blocked for
// missing CORS headers. That message tells the user nothing, so replace it.
function describeError(e) {
  if (e instanceof TypeError) {
    return "Could not reach the analysis server — it may be asleep, restarting, or rejecting the request. Retry in a moment.";
  }
  return e?.message || "Something went wrong.";
}

// The generated PDF/JSON are served by the API, not this origin. The backend only emits
// absolute URLs when API_BASE_URL is configured; otherwise they arrive as "/outputs/…",
// which a browser resolves against the frontend host and 404s. Re-anchor those onto the API.
function resolveOutputs(outputs) {
  if (!outputs) return outputs;
  return Object.fromEntries(
    Object.entries(outputs).map(([key, url]) => [
      key,
      typeof url === "string" && url.startsWith("/")
        ? `${API_BASE}${url}`
        : url,
    ]),
  );
}

export default function App() {
  const [tracks, setTracks] = useState([]);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [selectedDemo, setSelectedDemo] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const { ready: backendReady, waiting: serverWaking } = useBackendReady();
  const { theme, toggle: toggleTheme } = useTheme();

  const resultsRef = useRef(null);

  // Keep completed results discoverable for keyboard and mobile users.
  useEffect(() => {
    if (result) resultsRef.current?.focus();
  }, [result]);

  // Fetch tracks once the existing backend readiness check finishes.
  useEffect(() => {
    if (!backendReady) return;
    // Fetch tracks now that backend is alive
    fetch(`${API_BASE}/tracks`)
      .then((r) => r.json())
      .then((data) => setTracks(data))
      .catch(() => setError("Failed to load tracks"));
  }, [backendReady]);

  // Shared polling loop: resolves with job result or rejects with an error message.
  // A poll that fails at the network level is retried a few times — the backend
  // sleeps/restarts on the free tier, and one blip shouldn't discard a running job.
  function pollJob(jobId) {
    return new Promise((resolve, reject) => {
      let consecutiveFailures = 0;
      const interval = setInterval(async () => {
        try {
          const poll = await fetch(`${API_BASE}/jobs/${jobId}`);
          if (!poll.ok) {
            // 503 = job store briefly unreachable; keep polling. Anything else is fatal.
            if (
              poll.status === 503 &&
              ++consecutiveFailures <= MAX_POLL_RETRIES
            )
              return;
            clearInterval(interval);
            reject(new Error(await readErrorDetail(poll)));
            return;
          }
          consecutiveFailures = 0;
          const job = await poll.json();
          if (job.status === "completed") {
            clearInterval(interval);
            resolve(job.result);
          } else if (job.status === "failed") {
            clearInterval(interval);
            reject(new Error(job.error || "Job failed"));
          }
          // pending / processing → keep polling
        } catch (e) {
          if (++consecutiveFailures <= MAX_POLL_RETRIES) return;
          clearInterval(interval);
          reject(new Error(describeError(e)));
        }
      }, 3000);
    });
  }

  // Wraps any fetch that returns {job_id}, polls to completion, and sets state.
  async function submit(makeRequest) {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await makeRequest();
      if (!res.ok) throw new Error(await readErrorDetail(res));
      const { job_id } = await res.json();
      const data = await pollJob(job_id);
      setResult(data);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }

  function handleAnalyze() {
    if (uploadedFile) {
      const fd = new FormData();
      fd.append("file", uploadedFile);
      submit(() => fetch(`${API_BASE}/analyze`, { method: "POST", body: fd }));
    } else if (selectedDemo) {
      submit(() =>
        fetch(`${API_BASE}/demo`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ track_id: selectedDemo }),
        }),
      );
    }
  }

  const selectedLabel = uploadedFile
    ? uploadedFile.name
    : tracks.find((t) => t.track_id === selectedDemo)?.label || "";

  return (
    <>
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <header className="site-header">
        <a
          className="brand"
          href="#workspace"
          aria-label="SoundReverse workspace"
        >
          <span className="brand-mark">
            <WaveIcon size={23} />
          </span>
          <span className="brand-name">
            SoundReverse<span className="brand-period">.</span>
          </span>
        </a>
        <nav className="header-nav" aria-label="Main navigation">
          <a className="nav-active" href="#workspace">
            Workspace
          </a>
          <a href="#how-it-works">
            How it works <span aria-hidden="true">↗</span>
          </a>
        </nav>
        <div className="header-tools">
          <span className="studio-label">THE LISTENING ROOM</span>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <main id="workspace" className="workspace" tabIndex={-1}>
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">A LITTLE SCIENCE. A LOT OF SOUND.</p>
            <h1>Your sound, understood.</h1>
          </div>
          <span className="session-badge">
            <span className="status-dot" /> Analysis studio
          </span>
        </div>
        <div className="app">
          <aside className="sidebar" aria-labelledby="source-heading">
            <div className="source-heading">
              <span className="step-number">01</span>
              <h2 id="source-heading">Start with a sound</h2>
            </div>
            <p className="source-description">
              Bring a track. Find what makes it work.
            </p>
            <div className="side-scroll">
              <FileUpload
                file={uploadedFile}
                disabled={loading}
                onFileChange={(f) => {
                  setUploadedFile(f);
                  if (f) setSelectedDemo("");
                }}
              />
              <div className="source-divider">
                <span>or explore a reference</span>
              </div>
              <div className="side-group">
                <div className="section-label">
                  <p className="label">Demo library</p>
                  <span className="mono">
                    {String(tracks.length).padStart(2, "0")} TRACKS
                  </span>
                </div>
                <TrackSelector
                  tracks={tracks}
                  selected={selectedDemo}
                  disabled={loading}
                  pending={!backendReady}
                  onChange={(id) => {
                    setSelectedDemo(id);
                    setUploadedFile(null);
                  }}
                />
              </div>
            </div>
            <div className="side-foot">
              {error && (
                <div className="error-notice" role="alert">
                  <Icon name="alert" />
                  <span>{error}</span>
                </div>
              )}
              <AnalyzeButton
                loading={loading}
                disabled={!backendReady || (!uploadedFile && !selectedDemo)}
                onClick={handleAnalyze}
              />
              <p className="selection-hint" aria-live="polite">
                {loading
                  ? "You can review your results here when ready."
                  : selectedLabel
                    ? `Ready: ${selectedLabel}`
                    : "Choose a track to begin your session"}
              </p>
              {!backendReady && (
                <p className="connection-status" role="status">
                  <span className="status-dot" />
                  {serverWaking
                    ? "Waking the analysis server…"
                    : "Connecting to the studio…"}
                </p>
              )}
            </div>
            <div className="source-note">
              <Icon name="headphones" />
              <p>
                Made for curious ears.
                <br />
                <span>Built for your next great mix.</span>
              </p>
            </div>
          </aside>
          <div
            className="main"
            ref={resultsRef}
            tabIndex={-1}
            aria-label="Analysis workspace"
          >
            <p className="sr-only" role="status">
              {loading
                ? "Analysis in progress. Keep this tab open."
                : result
                  ? "Analysis complete. Your session blueprint is ready."
                  : "Choose a track to begin."}
            </p>
            {loading ? (
              <LoadingState label={selectedLabel} />
            ) : result ? (
              <>
                <div className="result-heading">
                  <div>
                    <p className="eyebrow">YOUR SESSION BLUEPRINT</p>
                    <h2>{result.track.title}</h2>
                    {result.track.artist && <p>{result.track.artist}</p>}
                  </div>
                  <span className="chip chip-green">
                    <Icon name="check" size={14} />
                    Analysis complete
                  </span>
                </div>
                <ResultsView result={result} />
              </>
            ) : (
              <EmptyState
                theme={theme}
                onChoose={() =>
                  document.getElementById("audio-upload")?.click()
                }
              />
            )}
          </div>
        </div>
        <HowItWorks />
      </main>
      <footer className="footer">
        <span>
          SoundReverse<span className="brand-period">.</span>
        </span>
        <p>From listening to understanding.</p>
        <span className="mono">SIGNAL → INSIGHT → CREATE</span>
      </footer>
    </>
  );
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === "dark";
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      role="switch"
      aria-checked={isDark}
      aria-label="Dark mode"
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      <SunIcon className={isDark ? "" : "icon-active"} />
      <span className="toggle-track">
        <span className="toggle-knob" />
      </span>
      <MoonIcon className={isDark ? "icon-active" : ""} />
    </button>
  );
}

function ResultsView({ result }) {
  const {
    track,
    pipeline,
    settings,
    musician,
    outputs,
    trace_url: traceUrl,
  } = result;

  return (
    <div className="grid stagger">
      <SignalSummary track={track} confidence={pipeline.confidence} />

      <FrequencyMap targets={musician?.tuning_targets} eq={settings?.eq} />

      <ProducerSettings settings={settings} />
      <ConfidencePanel pipeline={pipeline} />

      <MusicianNotes musician={musician} />
      <CriticTimeline rounds={pipeline.critic_rounds} />

      <OutputDownloads outputs={resolveOutputs(outputs)} traceUrl={traceUrl} />
    </div>
  );
}

function EmptyState({ theme, onChoose }) {
  return (
    <div className="welcome fade-in">
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="small-spark">✳</span> HEAR THE BIGGER PICTURE
          </p>
          <h2 id="hero-title">
            Every sound has
            <br />a <em>blueprint.</em>
          </h2>
          <p>
            Uncover the decisions behind a great mix. Turn a track into clear,
            actionable insights for your next session.
          </p>
          <button className="text-button" onClick={onChoose}>
            Explore your sound <Icon name="arrow" />
          </button>
        </div>
        <div className="hero-visual">
          <div className="visual-label">
            <span className="status-dot" /> SIGNAL ANATOMY{" "}
            <span className="mono">SR / 001</span>
          </div>
          <SignalScene theme={theme} />
          <div className="visual-axis mono">
            <span>LOW END</span>
            <span>MIDRANGE</span>
            <span>AIR</span>
          </div>
          <p className="visual-caption">
            An illustrated spectrum. Your track tells its own story.
          </p>
        </div>
        <div className="hero-foot">
          <span>
            <Icon name="wave" size={15} /> From waveform to workflow
          </span>
          <span className="mono">DECODE YOUR SOUND ↗</span>
        </div>
      </section>
      <div className="section-label output-label">
        <h3>Your next session starts here</h3>
        <span className="label">INSIDE YOUR BLUEPRINT</span>
      </div>
      <div className="feature-grid">
        {[
          [
            "wave",
            "The sonic signature",
            "Loudness, tempo, key, and the frequencies that shape your track.",
            "01 / UNDERSTAND",
          ],
          [
            "sliders",
            "A direction for your mix",
            "Considered EQ, compression, and gain settings, with the why behind each.",
            "02 / REFINE",
          ],
          [
            "download",
            "Ideas you can take away",
            "A readable PDF blueprint and structured presets for your next session.",
            "03 / CREATE",
          ],
        ].map(([icon, title, description, step]) => (
          <article className="feature-card" key={title}>
            <div className={`feature-icon icon-${icon}`}>
              <Icon name={icon} size={22} />
            </div>
            <h3>{title}</h3>
            <p>{description}</p>
            <span className="mono feature-step">{step}</span>
          </article>
        ))}
      </div>
      <div className="empty-note">
        <Icon name="spark" />
        <p>
          Good mixes start with better questions.
          <span> Pick a demo to see what you might discover.</span>
        </p>
      </div>
    </div>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="how-section">
      <div>
        <p className="eyebrow">LESS GUESSWORK. MORE MAKING.</p>
        <h2>From a track to a plan.</h2>
        <p>Your ears lead. The analysis gives you a place to start.</p>
      </div>
      <div className="faq-list">
        <details>
          <summary>
            <span className="mono">01</span> What happens to my track?
            <Icon name="plus" />
          </summary>
          <p>
            Upload a WAV or MP3 up to 50 MB, or choose a demo. SoundReverse
            analyses the audio and researches its context to assemble your
            session pack. It does not modify your original audio.
          </p>
        </details>
        <details>
          <summary>
            <span className="mono">02</span> What is in the session pack?
            <Icon name="plus" />
          </summary>
          <p>
            Signal measurements, recommended producer settings, musician notes,
            and a record of the critic’s review. Available downloads include a
            PDF blueprint, JSON preset, and run metadata.
          </p>
        </details>
        <details>
          <summary>
            <span className="mono">03</span> How should I use the
            recommendations?
            <Icon name="plus" />
          </summary>
          <p>
            Treat them as a starting point. Check the confidence score and
            validation notes, try the suggested settings in your own session,
            and let your ears make the final call.
          </p>
        </details>
      </div>
    </section>
  );
}

const LOADING_STAGES = [
  "Researching the track",
  "Reading the signal signature",
  "Mapping producer settings",
  "Cross-checking with the critic",
  "Finalising your session pack",
];

// TODO(mcp-integration): these captions currently cycle on a timer (cosmetic only) —
// they convey what the pipeline does, not real live status. Once the backend reports a
// live `stage` in GET /jobs/{id} (see api.py placeholders), pass it in as a prop and
// render that instead of the timer-driven index below.
const METER_BARS = [40, 70, 100, 55, 85, 30, 65, 95, 45, 75];

function LoadingState({ label }) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const id = setInterval(
      () => setStage((s) => (s + 1) % LOADING_STAGES.length),
      2800,
    );
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="fade-in"
      style={{
        minHeight: 500,
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 340 }}>
        <div
          className="meter"
          style={{ justifyContent: "center", marginBottom: 22 }}
        >
          {METER_BARS.map((h, i) => (
            <span
              key={i}
              className="meter-bar"
              style={{
                height: `${h}%`,
                animationDelay: `${-(i * 0.13).toFixed(2)}s`,
              }}
            />
          ))}
        </div>
        <h2
          style={{
            margin: "0 0 6px",
            fontSize: 28,
            fontWeight: 600,
            color: "var(--text-1)",
          }}
        >
          Listening closely.
        </h2>
        {label && (
          <p
            style={{
              margin: "0 0 16px",
              fontSize: 13.5,
              color: "var(--text-3)",
            }}
          >
            {label}
          </p>
        )}
        <p className="loading-explainer">Behind your analysis</p>
        <p
          key={stage}
          className="label fade-in"
          style={{ color: "var(--blue)" }}
        >
          {LOADING_STAGES[stage]}
        </p>
        <p
          style={{
            margin: "16px 0 0",
            fontSize: 12,
            color: "var(--text-4)",
            lineHeight: 1.6,
          }}
        >
          Your session is processing. These are the steps in our workflow, not
          live progress. Keep this tab open until your results arrive.
        </p>
      </div>
    </div>
  );
}

function WaveIcon({ size = 18 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 22 22"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M1 11h3M18 11h3M5 7v8M8 4v14M11 8v6M14 5v12M17 7v8"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SunIcon({ className = "" }) {
  return (
    <svg
      className={className}
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="3.1" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M8 1v1.6M8 13.4V15M15 8h-1.6M2.6 8H1M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1M12.9 12.9l-1.1-1.1M4.2 4.2L3.1 3.1"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon({ className = "" }) {
  return (
    <svg
      className={className}
      width="15"
      height="15"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M13.5 9.8A5.8 5.8 0 016.2 2.5a5.9 5.9 0 107.3 7.3z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}
