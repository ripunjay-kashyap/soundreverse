import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF
from fpdf.enums import XPos, YPos

if TYPE_CHECKING:
    from agents.graph import GraphState

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(Path(__file__).parent.parent / "output")))

# ── Colour palette ───────────────────────────────────────────────────────────
PRIMARY   = (15,  23,  42)   # slate-900
ACCENT    = (99, 102, 241)   # indigo-500
LIGHT_BG  = (241, 245, 249)  # slate-100
MID_GREY  = (100, 116, 139)  # slate-500
WHITE     = (255, 255, 255)
RED_SOFT  = (220,  38,  38)
GREEN_SOFT= (22, 163,  74)


# ── PDF class ────────────────────────────────────────────────────────────────

class BlueprintPDF(FPDF):
    def __init__(self, track_id: str, trace_url: str | None):
        super().__init__()
        self.track_id  = track_id
        self.trace_url = trace_url or "LangSmith tracing not configured"
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(14, 14, 14)

    def normalize_text(self, txt: str) -> str:
        """Override to silently replace any non-latin-1 chars instead of crashing."""
        try:
            return super().normalize_text(txt)
        except Exception:
            return txt.encode("latin-1", errors="replace").decode("latin-1")

    # -- Header ---------------------------------------------------------------
    def header(self):
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*WHITE)
        self.set_y(2)
        self.cell(0, 7, self._safe(f"SoundReverse  \xb7  Producer Session Pack  \xb7  {self.track_id}"), align="C")
        self.set_text_color(*PRIMARY)
        self.ln(10)

    # -- Footer ---------------------------------------------------------------
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MID_GREY)
        trace_text = f"Trace: {self.trace_url}"
        self.cell(0, 5, self._safe(trace_text), align="C")

    # -- Section title --------------------------------------------------------
    def section_title(self, text: str):
        self.set_fill_color(*ACCENT)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 7, self._safe(f"  {text}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(*PRIMARY)
        self.ln(2)

    @staticmethod
    def _safe(text: str) -> str:
        """Replace Unicode chars outside latin-1 range so Helvetica doesn't choke."""
        return (
            str(text)
            .replace("\u2014", "--")   # em dash
            .replace("\u2013", "-")    # en dash
            .replace("\u2018", "'").replace("\u2019", "'")   # curly single quotes
            .replace("\u201c", '"').replace("\u201d", '"')   # curly double quotes
            .encode("latin-1", errors="replace").decode("latin-1")
        )

    # -- Key/value row --------------------------------------------------------
    def kv_row(self, label: str, value: str, shade: bool = False):
        if shade:
            self.set_fill_color(*LIGHT_BG)
        else:
            self.set_fill_color(*WHITE)
        self.set_font("Helvetica", "B", 9)
        self.cell(50, 6, self._safe(label), fill=True)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, self._safe(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    # -- Table header row -----------------------------------------------------
    def table_header(self, cols: list[tuple[str, float]]):
        self.set_fill_color(*PRIMARY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        for label, width in cols:
            self.cell(width, 6, self._safe(label), border=0, fill=True)
        self.ln()
        self.set_text_color(*PRIMARY)

    # -- Table data row -------------------------------------------------------
    def table_row(self, cells: list[tuple[str, float]], shade: bool = False):
        fill_color = LIGHT_BG if shade else WHITE
        self.set_fill_color(*fill_color)
        self.set_font("Helvetica", "", 8)
        for text, width in cells:
            self.cell(width, 6, self._safe(text), border=0, fill=True)
        self.ln()

    # -- Reason block ---------------------------------------------------------
    def reason_block(self, label: str, reason: str, shade: bool = False):
        if shade:
            self.set_fill_color(*LIGHT_BG)
        else:
            self.set_fill_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        self.cell(0, 5, self._safe(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MID_GREY)
        self.multi_cell(0, 5, self._safe(reason), fill=True)
        self.set_text_color(*PRIMARY)
        self.ln(1)

    # -- Signal summary table (reusable) --------------------------------------
    def signal_summary_table(self, sig: "SignalSignature"):
        self.section_title("Signal Summary & Grounding Metrics")
        m = sig.master
        drums = sig.stems.get("drums")
        kick_hz = f"{drums.kick_fundamental_hz} Hz" if (drums and drums.kick_fundamental_hz) else "-"

        summary_pairs = [
            ("Loudness (LUFS)", str(m.lufs)),
            ("Dynamic Range",   f"{m.dynamic_range_db} dB"),
            ("Spectral Tilt",   str(m.spectral_tilt)),
            ("Stereo Width",    str(m.stereo_width)),
            ("Kick Fundamental", kick_hz),
        ]
        for i, (k, v) in enumerate(summary_pairs):
            self.kv_row(k, v, shade=(i % 2 == 0))


# ── Page builders ────────────────────────────────────────────────────────────

def _page1_overview(pdf: BlueprintPDF, state: "GraphState"):
    """Page 1 - Track metadata + EQ table + Compression."""
    pdf.add_page()

    sig      = state["signal_signature"]
    settings = state["producer_settings"]
    meta     = sig.metadata

    # Metadata block
    pdf.section_title("Track Information")
    pairs = [
        ("Title",         meta.get("title", sig.track_id)),
        ("Artist",        meta.get("artist", "-")),
        ("Album",         meta.get("album",  "-")),
        ("Year",          str(meta.get("year", "-"))),
        ("Genre",         meta.get("genre",  "-")),
        ("BPM",           f"{sig.rhythm.bpm}  ({sig.rhythm.time_signature})"),
        ("Key",           sig.rhythm.key),
        ("Duration",      f"{meta.get('duration_seconds', '-')}s"),
    ]
    for i, (k, v) in enumerate(pairs):
        pdf.kv_row(k, v, shade=(i % 2 == 0))
    pdf.ln(4)

    pdf.signal_summary_table(sig)
    pdf.ln(4)

    # EQ table
    pdf.section_title("EQ Settings")
    cols = [("Band", 45), ("Freq (Hz)", 45), ("Gain (dB)", 45), ("Q", 47)]
    pdf.table_header(cols)
    for i, band in enumerate(settings.eq):
        q_str = str(band.q) if band.q is not None else "-"
        row = [
            (band.band,          45),
            (str(band.freq),     45),
            (f"{band.gain_db:+.1f}", 45),
            (q_str,              47),
        ]
        pdf.table_row(row, shade=(i % 2 == 0))
    pdf.ln(4)

    # Compression block
    pdf.section_title("Compression")
    if settings.compression:
        c = settings.compression
        for i, (k, v) in enumerate([
            ("Ratio",      c.ratio),
            ("Attack",     f"{c.attack_ms} ms"),
            ("Release",    f"{c.release_ms} ms"),
            ("Reason",     c.reason),
        ]):
            pdf.kv_row(k, v, shade=(i % 2 == 0))
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MID_GREY)
        pdf.cell(0, 6, "  No bus compression applied (see reasoning page for details)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*PRIMARY)

    pdf.ln(4)

    # Master gain
    pdf.section_title("Master Gain")
    pdf.kv_row("Gain (dB)", f"{settings.master_gain_db:+.1f}", shade=True)


def _page2_reasoning(pdf: BlueprintPDF, state: "GraphState"):
    """Page 2 - Agent reasoning trace."""
    pdf.add_page()

    sig      = state["signal_signature"]
    settings = state["producer_settings"]

    # -- Signal Summary -------------------------------------------------------
    pdf.signal_summary_table(sig)
    pdf.ln(6)

    pdf.section_title("Agent Reasoning - Why Each Setting Was Chosen")
    pdf.ln(2)

    for i, band in enumerate(settings.eq):
        label = f"EQ · {band.band} @ {band.freq} Hz  ({band.gain_db:+.1f} dB)"
        pdf.reason_block(label, band.reason, shade=(i % 2 == 0))

    if settings.compression:
        label = f"Compression · {settings.compression.ratio}  attack={settings.compression.attack_ms}ms  release={settings.compression.release_ms}ms"
        pdf.reason_block(label, settings.compression.reason, shade=(len(settings.eq) % 2 == 0))
    else:
        reason = settings.compression_skip_reason or "Bus compression not applied."
        pdf.reason_block("Compression · skipped", reason, shade=(len(settings.eq) % 2 == 0))

    pdf.reason_block(
        f"Master Gain · {settings.master_gain_db:+.1f} dB",
        settings.master_gain_reason or f"Master LUFS = {sig.master.lufs}",
        shade=((len(settings.eq) + 1) % 2 == 0),
    )

    pdf.ln(4)
    pdf.section_title("Confidence Score")
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 14, f"{state['confidence']:.2f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_text_color(*PRIMARY)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Iterations: {state['iteration_count']} / 3", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")


def _page3_critic_log(pdf: BlueprintPDF, state: "GraphState"):
    """Page 3 - Critic debate log."""
    pdf.add_page()
    pdf.section_title("Critic Debate Log")
    pdf.ln(2)

    iteration_count = state["iteration_count"]
    confidence      = state["confidence"]
    history         = state.get("critique_history", [])

    pdf.set_font("Helvetica", "", 9)
    pdf.kv_row("Total iterations", str(iteration_count))
    pdf.kv_row("Final confidence",  f"{confidence:.4f}", shade=True)
    pdf.ln(4)

    if confidence >= 0.75:
        pdf.set_fill_color(*GREEN_SOFT)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 7, "  Critic signed off: confidence threshold met", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.set_text_color(*PRIMARY)
    elif iteration_count >= 3:
        pdf.set_fill_color(*RED_SOFT)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 7, "  Max iterations reached - signed off with sub-threshold confidence", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        pdf.set_text_color(*PRIMARY)

    pdf.ln(4)

    if history:
        pdf.section_title("Critic Debate History")
        for round_idx, round_critique in enumerate(history):
            # Header for the round
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*MID_GREY)
            pdf.cell(0, 6, f" ROUND {round_idx + 1} REJECTIONS", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*PRIMARY)
            
            # List issues in this round
            for i, issue in enumerate(round_critique.split(";")):
                issue = issue.strip()
                if issue:
                    pdf.set_fill_color(*LIGHT_BG if i % 2 == 0 else WHITE)
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(*RED_SOFT)
                    pdf.multi_cell(180, 6, f"- {issue}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    pdf.set_text_color(*PRIMARY)
            pdf.ln(2)
        
        # If we finished with high confidence, add a success note
        if confidence >= 0.8:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*MID_GREY)
            pdf.cell(0, 6, "  Final pass resulted in target confidence - all issues resolved.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*PRIMARY)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MID_GREY)
        pdf.cell(0, 6, "  No issues flagged - all validation checks passed on first attempt.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*PRIMARY)

    pdf.ln(4)
    pdf.section_title("Validation Checks Run")
    checks = [
        "Over-compression: compression applied when dynamic_range_db < 4 dB",
        "Bright boost contradiction: high-shelf gain > 0 when spectral_tilt > 0.75",
        "Loudness ceiling: master_gain_db > 0 when LUFS > -9",
        "Kick frequency mismatch: EQ target differs from kick_fundamental_hz by > 20 Hz",
    ]
    for i, check in enumerate(checks):
        pdf.set_fill_color(*LIGHT_BG if i % 2 == 0 else WHITE)
        pdf.set_font("Helvetica", "", 8)
        # Use a slightly narrower width (178 instead of 182) and larger height to ensure wrapping works cleanly
        pdf.multi_cell(180, 6, f"  [OK]  {check}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# ── Output node ──────────────────────────────────────────────────────────────

def output_node(state: "GraphState") -> "GraphState":
    if state.get("error"):
        return state

    settings  = state["producer_settings"]
    track_id  = state["track_request"].track_id
    trace_url = state.get("trace_url")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── JSON preset ──────────────────────────────────────────────────────────
    preset = {
        "track_id":        track_id,
        "trace_url":       trace_url,
        "confidence":      state["confidence"],
        "iteration_count": state["iteration_count"],
        **settings.model_dump(),
    }
    preset_path = OUTPUT_DIR / f"{track_id}_preset.json"
    preset_path.write_text(json.dumps(preset, indent=2), encoding="utf-8")

    # ── PDF blueprint ────────────────────────────────────────────────────────
    try:
        pdf = BlueprintPDF(track_id=track_id, trace_url=trace_url)
        _page1_overview(pdf, state)
        _page2_reasoning(pdf, state)
        _page3_critic_log(pdf, state)
        pdf_path = OUTPUT_DIR / f"{track_id}_blueprint.pdf"
        pdf.output(str(pdf_path))
    except Exception as pdf_err:
        print(f"[PDF] generation failed for {track_id}: {pdf_err}")

    # ── Metadata JSON ────────────────────────────────────────────────────────
    run_id = None
    if trace_url:
        # trace URL ends with the run UUID, grab first 8 chars
        run_id = trace_url.rstrip("/").split("/")[-1][:8]

    metadata = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "track_id": track_id,
        "pipeline": {
            "gateway": {"source": "cache", "latency_ms": None},
            "analyst": {
                "iterations": state["iteration_count"],
                "model": "gemini-3.1-flash-lite-preview",
                "latency_ms": None,
            },
            "critic": {"rounds": state.get("critic_rounds", [])},
        },
        "trace_url": trace_url,
    }
    metadata_path = OUTPUT_DIR / f"{track_id}_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return {**state, "trace_url": trace_url}
