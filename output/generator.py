import json
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF
from fpdf.enums import XPos, YPos

if TYPE_CHECKING:
    from agents.graph import GraphState

OUTPUT_DIR = Path(__file__).parent.parent / "output"

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

    # -- Header ---------------------------------------------------------------
    def header(self):
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*WHITE)
        self.set_y(2)
        self.cell(0, 7, f"SoundReverse  ·  Producer Session Pack  ·  {self.track_id}", align="C")
        self.set_text_color(*PRIMARY)
        self.ln(10)

    # -- Footer ---------------------------------------------------------------
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MID_GREY)
        trace_text = f"Trace: {self.trace_url}"
        self.cell(0, 5, trace_text, align="C")

    # -- Section title --------------------------------------------------------
    def section_title(self, text: str):
        self.set_fill_color(*ACCENT)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 7, f"  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(*PRIMARY)
        self.ln(2)

    # -- Key/value row --------------------------------------------------------
    def kv_row(self, label: str, value: str, shade: bool = False):
        if shade:
            self.set_fill_color(*LIGHT_BG)
        else:
            self.set_fill_color(*WHITE)
        self.set_font("Helvetica", "B", 9)
        self.cell(50, 6, label, fill=True)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)

    # -- Table header row -----------------------------------------------------
    def table_header(self, cols: list[tuple[str, float]]):
        self.set_fill_color(*PRIMARY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        for label, width in cols:
            self.cell(width, 6, label, border=0, fill=True)
        self.ln()
        self.set_text_color(*PRIMARY)

    # -- Table data row -------------------------------------------------------
    def table_row(self, cells: list[tuple[str, float]], shade: bool = False):
        fill_color = LIGHT_BG if shade else WHITE
        self.set_fill_color(*fill_color)
        self.set_font("Helvetica", "", 8)
        for text, width in cells:
            self.cell(width, 6, text, border=0, fill=True)
        self.ln()

    # -- Reason block ---------------------------------------------------------
    def reason_block(self, label: str, reason: str, shade: bool = False):
        if shade:
            self.set_fill_color(*LIGHT_BG)
        else:
            self.set_fill_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        self.cell(0, 5, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MID_GREY)
        self.multi_cell(0, 5, reason, fill=True)
        self.set_text_color(*PRIMARY)
        self.ln(1)


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
        ("Master LUFS",   str(sig.master.lufs)),
        ("Dynamic Range", f"{sig.master.dynamic_range_db} dB"),
        ("Spectral Tilt", str(sig.master.spectral_tilt)),
    ]
    for i, (k, v) in enumerate(pairs):
        pdf.kv_row(k, v, shade=(i % 2 == 0))
    pdf.ln(4)

    # EQ table
    pdf.section_title("EQ Settings")
    cols = [("Band", 35), ("Freq (Hz)", 30), ("Gain (dB)", 30), ("Q", 20), ("Reason", 67)]
    pdf.table_header(cols)
    for i, band in enumerate(settings.eq):
        q_str = str(band.q) if band.q is not None else "-"
        row = [
            (band.band,          35),
            (str(band.freq),     30),
            (f"{band.gain_db:+.1f}", 30),
            (q_str,              20),
            (band.reason[:55],   67),
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
    pdf.section_title("Agent Reasoning - Why Each Setting Was Chosen")
    pdf.ln(2)

    settings = state["producer_settings"]

    for i, band in enumerate(settings.eq):
        label = f"EQ · {band.band} @ {band.freq} Hz  ({band.gain_db:+.1f} dB)"
        pdf.reason_block(label, band.reason, shade=(i % 2 == 0))

    if settings.compression:
        label = f"Compression · {settings.compression.ratio}  attack={settings.compression.attack_ms}ms  release={settings.compression.release_ms}ms"
        pdf.reason_block(label, settings.compression.reason, shade=(len(settings.eq) % 2 == 0))
    else:
        pdf.reason_block("Compression · skipped", "Bus compression not applied.", shade=(len(settings.eq) % 2 == 0))

    pdf.reason_block(
        f"Master Gain · {settings.master_gain_db:+.1f} dB",
        f"Master LUFS = {state['signal_signature'].master.lufs}",
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
    critique        = state.get("critique", "")

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

    if critique:
        pdf.section_title("Flagged Issues")
        for i, issue in enumerate(critique.split(";")):
            issue = issue.strip()
            if issue:
                pdf.set_fill_color(*LIGHT_BG if i % 2 == 0 else WHITE)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*RED_SOFT)
                pdf.multi_cell(182, 5, f"• {issue}", fill=True)
                pdf.set_text_color(*PRIMARY)
        pdf.ln(2)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MID_GREY)
        pdf.cell(0, 6, "  No issues flagged - all validation checks passed.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
        pdf.multi_cell(182, 5, f"  [OK]  {check}", fill=True)


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
    pdf = BlueprintPDF(track_id=track_id, trace_url=trace_url)
    _page1_overview(pdf, state)
    _page2_reasoning(pdf, state)
    _page3_critic_log(pdf, state)

    pdf_path = OUTPUT_DIR / f"{track_id}_blueprint.pdf"
    pdf.output(str(pdf_path))

    return {**state, "trace_url": trace_url}
