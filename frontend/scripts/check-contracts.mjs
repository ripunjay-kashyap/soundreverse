// Frontend-only contract checks: no backend server, writes, or paid analysis calls.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const helpers = source.slice(
  source.indexOf("async function readErrorDetail"),
  source.indexOf("export default function App"),
);
const actions = source.slice(
  source.indexOf("  function pollJob("),
  source.indexOf("  const selectedLabel"),
);
let checks = 0;
const check = async (name, run) => {
  await run();
  checks++;
  console.log(`✓ ${name}`);
};
function harness(options = {}) {
  const calls = [],
    timers = new Map(),
    state = {},
    submits = [];
  let id = 0;
  const context = vm.createContext({
    API_BASE: "https://api.example.test",
    MAX_POLL_RETRIES: 4,
    FormData,
    TypeError,
    uploadedFile: null,
    selectedDemo: "",
    ...options,
    fetch: async (...args) => {
      calls.push(args);
      return options.fetch?.(...args);
    },
    setInterval: (callback) => {
      timers.set(++id, callback);
      return id;
    },
    clearInterval: (key) => timers.delete(key),
    setLoading: (value) => {
      state.loading = value;
    },
    setResult: (value) => {
      state.result = value;
    },
    setError: (value) => {
      state.error = value;
    },
  });
  vm.runInContext(helpers + actions, context);
  return {
    context,
    calls,
    timers,
    state,
    submits,
    tick: async () => {
      for (const cb of [...timers.values()]) await cb();
    },
  };
}
const response = (body, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => body,
});
await check(
  "Demo analysis preserves POST /demo and track_id JSON",
  async () => {
    const h = harness({
      selectedDemo: "demo-42",
      fetch: () => response({ job_id: "job-42" }),
    });
    h.context.submit = (fn) => h.submits.push(fn());
    h.context.handleAnalyze();
    await Promise.all(h.submits);
    assert.equal(h.calls[0][0], "https://api.example.test/demo");
    assert.equal(h.calls[0][1].method, "POST");
    assert.equal(h.calls[0][1].headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(h.calls[0][1].body), { track_id: "demo-42" });
  },
);
await check(
  "Upload preserves multipart POST /analyze and file field",
  async () => {
    const file = new File(["audio"], "mix.wav", { type: "audio/wav" });
    const h = harness({
      uploadedFile: file,
      selectedDemo: "ignored-demo",
      fetch: () => response({ job_id: "upload-job" }),
    });
    h.context.submit = (fn) => h.submits.push(fn());
    h.context.handleAnalyze();
    await Promise.all(h.submits);
    assert.equal(h.calls[0][0], "https://api.example.test/analyze");
    assert.equal(h.calls[0][1].method, "POST");
    assert.equal(h.calls[0][1].body.get("file").name, "mix.wav");
    assert.equal(h.calls[0][1].headers, undefined);
  },
);
await check(
  "Polling resolves a completed job and stops its timer",
  async () => {
    let count = 0;
    const h = harness({
      fetch: () =>
        response(
          ++count === 1
            ? { status: "processing" }
            : { status: "completed", result: { track: { title: "Example" } } },
        ),
    });
    const promise = h.context.pollJob("job-42");
    await h.tick();
    assert.equal(h.timers.size, 1);
    await h.tick();
    assert.equal((await promise).track.title, "Example");
    assert.equal(h.calls[0][0], "https://api.example.test/jobs/job-42");
    assert.equal(h.timers.size, 0);
  },
);
await check("Transient 503 polling errors retain a running job", async () => {
  let count = 0;
  const h = harness({
    fetch: () =>
      ++count < 3
        ? response({}, 503)
        : response({ status: "completed", result: { ok: true } }),
  });
  const promise = h.context.pollJob("recoverable");
  await h.tick();
  await h.tick();
  await h.tick();
  assert.equal((await promise).ok, true);
});
await check(
  "A failed job reports the server error and clears polling",
  async () => {
    const h = harness({
      fetch: () => response({ status: "failed", error: "Unsupported signal" }),
    });
    const promise = h.context.pollJob("failed");
    const rejection = assert.rejects(promise, /Unsupported signal/);
    await h.tick();
    await rejection;
    assert.equal(h.timers.size, 0);
  },
);
await check(
  "Repeated polling failures terminate after the existing retry budget",
  async () => {
    const h = harness({
      fetch: () => response({ detail: "Unavailable" }, 503),
    });
    const promise = h.context.pollJob("unavailable");
    const rejection = assert.rejects(promise, /Unavailable/);
    for (let i = 0; i < 5; i++) await h.tick();
    await rejection;
    assert.equal(h.timers.size, 0);
  },
);
await check(
  "Submission errors restore the UI and expose validation messages",
  async () => {
    const h = harness();
    await h.context.submit(() =>
      response({ detail: [{ msg: "Invalid file" }] }, 422),
    );
    assert.equal(h.state.loading, false);
    assert.equal(h.state.result, null);
    assert.equal(h.state.error, "Invalid file");
  },
);
await check(
  "Successful submissions populate results and restore controls",
  async () => {
    const h = harness();
    h.context.pollJob = async () => ({ track: { title: "Finished" } });
    await h.context.submit(() => response({ job_id: "done" }));
    assert.equal(h.state.loading, false);
    assert.equal(h.state.error, null);
    assert.equal(h.state.result.track.title, "Finished");
  },
);
await check(
  "Download paths remain API-relative; absolute URLs remain intact",
  async () => {
    const h = harness();
    const resolved = h.context.resolveOutputs({
      pdf_url: "/outputs/pack.pdf",
      json_url: "https://storage.example.test/pack.json",
    });
    assert.equal(resolved.pdf_url, "https://api.example.test/outputs/pack.pdf");
    assert.equal(resolved.json_url, "https://storage.example.test/pack.json");
    assert.equal(h.context.resolveOutputs(null), null);
  },
);
await check(
  "Upload validation accepts supported formats and rejects invalid or oversized files",
  async () => {
    const upload = readFileSync(
      new URL("../src/components/FileUpload.jsx", import.meta.url),
      "utf8",
    );
    const take = upload.slice(
      upload.indexOf("  function take("),
      upload.indexOf("\n  return ("),
    );
    let error = null,
      selected = null;
    const context = vm.createContext({
      VALID: /\.(wav|mp3)$/i,
      MAX_MB: 50,
      disabled: false,
      setError: (value) => {
        error = value;
      },
      onFileChange: (value) => {
        selected = value;
      },
    });
    vm.runInContext(take, context);
    context.take({ name: "track.FLAC", size: 100 });
    assert.match(error, /WAV or MP3/);
    assert.equal(selected, null);
    context.take({ name: "track.wav", size: 51 * 1024 * 1024 });
    assert.match(error, /50 MB/);
    assert.equal(selected, null);
    context.take({ name: "track.MP3", size: 1024 });
    assert.equal(error, null);
    assert.equal(selected.name, "track.MP3");
    context.disabled = true;
    context.take({ name: "other.wav", size: 1024 });
    assert.equal(selected.name, "track.MP3");
  },
);
console.log(`${checks} frontend contract checks passed.`);
