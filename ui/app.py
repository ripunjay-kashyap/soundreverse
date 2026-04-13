import sys
from pathlib import Path

# Make project root importable regardless of where the script is launched from
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from agents.graph import run

# ── Track registry ───────────────────────────────────────────────────────────
TRACKS: dict[str, str] = {
    "Billie Jean — Michael Jackson":  "billie_jean_mj",
    "One More Time — Daft Punk":      "one_more_time_daft_punk",
    "Clocks — Coldplay":              "clocks_coldplay",
    "HUMBLE. — Kendrick Lamar":       "humble_kendrick",
    "Blinding Lights — The Weeknd":   "blinding_lights_weeknd",
}

OUTPUT_DIR = Path(__file__).parent.parent / "output"


# ── Core handler ─────────────────────────────────────────────────────────────

def analyze(display_name: str):
    track_id = TRACKS[display_name]

    try:
        final_state = run(track_id)
    except Exception as exc:
        return (
            f"Error: {exc}",
            "—",
            None,
            None,
            gr.update(visible=False),
        )

    if final_state.get("error"):
        return (
            f"Error: {final_state['error']}",
            "—",
            None,
            None,
            gr.update(visible=False),
        )

    confidence     = f"{final_state['confidence']:.2f}"
    iterations     = f"{final_state['iteration_count']} / 3"
    pdf_path       = str(OUTPUT_DIR / f"{track_id}_blueprint.pdf")
    json_path      = str(OUTPUT_DIR / f"{track_id}_preset.json")
    trace_url      = final_state.get("trace_url")

    trace_update = (
        gr.update(value=f'<a href="{trace_url}" target="_blank">View LangSmith trace →</a>', visible=True)
        if trace_url
        else gr.update(visible=False)
    )

    return confidence, iterations, pdf_path, json_path, trace_update


# ── UI layout ────────────────────────────────────────────────────────────────

with gr.Blocks(title="SoundReverse", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# SoundReverse\n### Producer Session Pack Generator")

    with gr.Row():
        with gr.Column(scale=1):
            track_dropdown = gr.Dropdown(
                choices=list(TRACKS.keys()),
                value=list(TRACKS.keys())[0],
                label="Select Track",
            )
            gr.Markdown("*Pre-analyzed · HTDemucs 4-stem · Cached*")
            analyze_btn = gr.Button("Analyze", variant="primary")

        with gr.Column(scale=1):
            confidence_out  = gr.Textbox(label="Confidence Score", interactive=False)
            iterations_out  = gr.Textbox(label="Iterations",       interactive=False)
            pdf_out         = gr.File(label="Blueprint PDF",  interactive=False)
            json_out        = gr.File(label="JSON Preset",    interactive=False)
            trace_link      = gr.HTML(visible=False)

    analyze_btn.click(
        fn=analyze,
        inputs=[track_dropdown],
        outputs=[confidence_out, iterations_out, pdf_out, json_out, trace_link],
    )


if __name__ == "__main__":
    demo.launch()
