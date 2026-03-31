import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from h_pylori_engine_v2 import (
    run_h_pylori_pathway, Action, DataRequest, Stop, Override,
    REGIMEN_DETAILS,
)

st.set_page_config(page_title="H. Pylori", page_icon="🦠", layout="wide")

# ── MARKDOWN / PDF HELPERS ──────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def build_h_pylori_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# H. Pylori Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age')} / {str(patient_data.get('sex')).capitalize()}")
    lines.append(f"- **H. pylori test result:** {_safe_text(patient_data.get('hp_test_result')) or 'Not tested'}")
    lines.append(f"- **Test type:** {_safe_text(patient_data.get('hp_test_type')) or 'N/A'}")
    lines.append(f"- **Treatment line:** {_safe_text(patient_data.get('treatment_line')) or 'N/A'}")
    lines.append(f"- **Penicillin allergy:** {_safe_text(patient_data.get('penicillin_allergy')) or 'No / not documented'}")
    lines.append(f"- **Pregnant:** {_safe_text(patient_data.get('pregnant')) or 'No / not documented'}")
    lines.append(f"- **Breastfeeding:** {_safe_text(patient_data.get('breastfeeding')) or 'No / not documented'}")
    lines.append(f"- **Symptoms persist:** {_safe_text(patient_data.get('symptoms_persist')) or 'Unknown'}")
    lines.append(f"- **Eradication test result:** {_safe_text(patient_data.get('eradication_test_result')) or 'Not done'}")
    lines.append("")

    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                label = _safe_text(o.label)
                lines.append(f"- **[{urgency}]** {label}")

                if isinstance(o.details, dict):
                    regimen_key = o.details.get("regimen_key")
                    if regimen_key and regimen_key in REGIMEN_DETAILS:
                        r = REGIMEN_DETAILS[regimen_key]
                        lines.append(f"  - Regimen: **{_safe_text(r.get('name'))}**")
                        lines.append(f"  - Duration: {_safe_text(r.get('duration'))}")
                        lines.append(f"  - Approx cost: {_safe_text(r.get('approx_cost'))}")

                        meds = r.get("medications", [])
                        if meds:
                            lines.append("  - Medications:")
                            for m in meds:
                                drug = _safe_text(m.get("drug"))
                                dose = _safe_text(m.get("dose"))
                                freq = _safe_text(m.get("frequency"))
                                lines.append(f"    - {drug}: {dose}, {freq}")

                        if r.get("notes"):
                            lines.append(f"  - Regimen note: {_safe_text(r.get('notes'))}")

                    for b in o.details.get("bullets", []):
                        lines.append(f"  - {_safe_text(b)}")
                    for n in o.details.get("notes", []):
                        lines.append(f"  - Note: {_safe_text(n)}")
                    for s in o.details.get("supported_by", []):
                        lines.append(f"  - Support: {_safe_text(s)}")

                    skip = {"bullets", "notes", "supported_by", "regimen_key"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(v)}")

            elif isinstance(o, Stop):
                reason = _safe_text(o.reason)
                lines.append(f"- **[STOP]** {reason}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")

            elif isinstance(o, DataRequest):
                msg = _safe_text(o.message)
                missing = ", ".join(field for field in o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {msg}")
                lines.append(f"  - Missing fields: {missing}")
                if getattr(o, "suggested_actions", None):
                    for a in o.suggested_actions:
                        lines.append(f"  - Suggested action: {_safe_text(a.label)}")

    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}.{_safe_text(ov.field)}** -> "
                f"`{_safe_text(ov.new_value)}` (Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")

    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    lines.append("")

    return "\n".join(lines)

    body_html = markdown2.markdown(
        md_text,
        extras=["tables", "fenced-code-blocks", "break-on-newline"]
    )

    full_html = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        @page {{
          size: A4;
          margin: 20mm 16mm 20mm 16mm;
        }}
        body {{
          font-family: Helvetica, Arial, sans-serif;
          font-size: 11pt;
          line-height: 1.45;
          color: #111111;
        }}
        h1 {{
          font-size: 20pt;
          margin: 0 0 12pt 0;
          padding: 0 0 6pt 0;
          border-bottom: 1px solid #cccccc;
        }}
        h2 {{
          font-size: 14pt;
          margin: 16pt 0 8pt 0;
        }}
        h3 {{
          font-size: 12pt;
          margin: 12pt 0 6pt 0;
        }}
        p {{
          margin: 0 0 8pt 0;
        }}
        ul {{
          margin: 0 0 8pt 18pt;
        }}
        li {{
          margin: 0 0 4pt 0;
        }}
        code {{
          font-family: Courier, monospace;
          background: #f3f4f6;
          padding: 1pt 3pt;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin: 8pt 0 10pt 0;
        }}
        th, td {{
          border: 1px solid #d1d5db;
          padding: 6pt;
          vertical-align: top;
          text-align: left;
        }}
        th {{
          background: #f3f4f6;
        }}
      </style>
    </head>
    <body>
      {body_html}
    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()
    result = pisa.CreatePDF(full_html, dest=pdf_buffer, encoding="utf-8")
    if result.err:
        raise ValueError("Markdown-to-PDF conversion failed.")
    return pdf_buffer.getvalue()


# ── GLOBAL CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
.ctx-card {
    background: #1e3a5f; border: 1px solid #2e5c8a;
    border-radius: 10px; padding: 14px 18px;
    margin-bottom: 14px; font-size: 14px; color: #e2e8f0;
}
.ctx-card b { color: #93c5fd; }
.section-label {
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    color: #94a3b8; margin-bottom: 6px; margin-top: 18px;
}
.action-card {
    border-radius: 10px; padding: 14px 18px;
    margin-bottom: 12px; font-size: 13.5px; line-height: 1.6;
}
.action-card.urgent  { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.routine { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop    { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card h4 { margin:0 0 6px 0; font-size:14px; }
.action-card ul { margin:6px 0 0 16px; padding:0; }
.action-card li { margin-bottom:3px; }
.med-table-wrap {
    margin-top:10px; background:#0a1628;
    border-radius:6px; padding:10px 14px; font-size:12.5px;
}
.med-table-header {
    margin-bottom:6px; color:#94a3b8;
    font-size:11px; letter-spacing:.8px; font-weight:700;
}
.med-note { margin:8px 0 0; font-size:12px; color:#fde68a; }
.badge {
    display:inline-block; font-size:11px; font-weight:bold;
    padding:2px 8px; border-radius:20px; margin-right:6px;
    text-transform:uppercase; letter-spacing:0.5px;
}
.badge.urgent  { background:#ef4444; color:#fff; }
.badge.routine { background:#22c55e; color:#fff; }
.badge.info    { background:#3b82f6; color:#fff; }
.badge.warning { background:#f59e0b; color:#000; }
.badge.stop    { background:#ef4444; color:#fff; }
.override-card {
    background:#1a1a2e; border:1px dashed #6366f1;
    border-radius:8px; padding:10px 14px; margin-top:8px;
    font-size:13px; color:#c7d2fe;
}
</style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "hp_overrides" not in st.session_state:
    st.session_state.hp_overrides = []

if "hp_has_run" not in st.session_state:
    st.session_state.hp_has_run = False

if "hp_notes" not in st.session_state:
    st.session_state.hp_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**Pregnancy / Nursing**")
    pregnant = st.checkbox("Pregnant")
    breastfeeding = st.checkbox("Breastfeeding / Nursing")

    st.markdown("**Testing Indication**")
    dyspepsia = st.checkbox("Dyspepsia symptoms")
    ulcer_hx = st.checkbox("History of ulcer or GI bleed")
    family_gastric = st.checkbox("Personal/family history of gastric cancer")
    immigrant_prev = st.checkbox("Immigrant from high-prevalence region")

    st.markdown("**H. Pylori Test**")
    hp_result_sel = st.selectbox("Result", ["Not tested", "Positive", "Negative"])
    hp_result_map = {"Not tested": None, "Positive": "positive", "Negative": "negative"}
    hp_test_type = st.selectbox("Test type", ["HpSAT", "UBT", "Other"])

    st.markdown("**Washout Status**")
    off_abx = st.checkbox("Off antibiotics ≥4 weeks", value=True)
    off_ppi = st.checkbox("Off PPIs ≥2 weeks", value=True)
    off_bismuth = st.checkbox("Off bismuth ≥2 weeks", value=True)

    st.markdown("**Alarm Features**")
    al_family_cancer = st.checkbox("Family hx esophageal/gastric cancer")
    al_ulcer_hx = st.checkbox("Personal history of peptic ulcer")
    al_age_symptoms = st.checkbox("Age >60 with new persistent symptoms")
    al_weight_loss = st.checkbox("Unintended weight loss >5%")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_vomiting = st.checkbox("Persistent vomiting")
    al_gi_bleed = st.checkbox("Black stool or blood in vomit")
    al_ida = st.checkbox("Iron deficiency anemia")
    al_concern = st.checkbox("Clinician concern — serious pathology")

    st.markdown("**Treatment History**")
    penicillin_allergy = st.checkbox("Penicillin allergy")
    tx_line_sel = st.selectbox(
        "Treatment line",
        [
            "1 – Naive (no prior treatment)",
            "2 – Second line (1 prior failure)",
            "3 – Third line (2 prior failures)",
            "4 – Fourth line (3 prior failures)",
        ],
    )
    tx_map = {
        "1 – Naive (no prior treatment)": 1,
        "2 – Second line (1 prior failure)": 2,
        "3 – Third line (2 prior failures)": 3,
        "4 – Fourth line (3 prior failures)": 4,
    }
    bubble_pack = st.checkbox("Bubble/blister pack NOT being used", value=False)
    nonadherence = st.checkbox("Non-adherence suspected")

    if hp_result_map[hp_result_sel] is not None:
        st.markdown("**Eradication Follow-up** *(post-treatment)*")
        erad_result_sel = st.selectbox(
            "Eradication test result",
            ["Not done", "Negative (eradicated)", "Positive (failed)"],
        )
        erad_map = {
            "Not done": None,
            "Negative (eradicated)": "negative",
            "Positive (failed)": "positive",
        }
        symptoms_persist = st.selectbox("Symptoms still persisting?", ["Unknown", "Yes", "No"])
        sp_map = {"Unknown": None, "Yes": True, "No": False}
    else:
        erad_map = {"Not done": None}
        erad_result_sel = "Not done"
        sp_map = {"Unknown": None}
        symptoms_persist = "Unknown"

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.hp_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hp_overrides = []
        if "hp_saved_output" in st.session_state:
            del st.session_state["hp_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.hp_has_run:
        patient_data = {
            "age": age,
            "sex": sex,
            "pregnant": pregnant or None,
            "breastfeeding": breastfeeding or None,
            "dyspepsia_symptoms": dyspepsia or None,
            "current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed": ulcer_hx or None,
            "personal_or_first_degree_relative_history_gastric_cancer": family_gastric or None,
            "first_generation_immigrant_high_prevalence_region": immigrant_prev or None,
            "hp_test_type": hp_test_type if hp_result_map[hp_result_sel] else None,
            "hp_test_result": hp_result_map[hp_result_sel],
            "off_antibiotics_4_weeks_before_test": off_abx,
            "off_ppi_2_weeks_before_test": off_ppi,
            "off_bismuth_2_weeks_before_test": off_bismuth,
            "penicillin_allergy": penicillin_allergy or None,
            "treatment_line": tx_map[tx_line_sel],
            "bubble_pack_used": not bubble_pack,
            "nonadherence_suspected": nonadherence or None,
            "family_history_esophageal_or_gastric_cancer_first_degree": al_family_cancer or None,
            "personal_history_peptic_ulcer_disease": al_ulcer_hx or None,
            "age_over_60_new_persistent_symptoms_over_3_months": al_age_symptoms or None,
            "unintended_weight_loss": al_weight_loss or None,
            "progressive_dysphagia": al_dysphagia or None,
            "persistent_vomiting_not_cannabis_related": al_vomiting or None,
            "black_stool_or_blood_in_vomit": al_gi_bleed or None,
            "iron_deficiency_anemia_present": al_ida or None,
            "clinician_concern_serious_pathology": al_concern or None,
            "eradication_test_result": erad_map.get(erad_result_sel),
            "symptoms_persist": sp_map.get(symptoms_persist),
            "off_antibiotics_4_weeks_before_retest": off_abx,
            "off_ppi_2_weeks_before_retest": off_ppi,
        }

        outputs, logs, applied_overrides = run_h_pylori_pathway(
            patient_data, overrides=st.session_state.hp_overrides
        )

        is_positive = patient_data.get("hp_test_result") == "positive"
        test_negative = patient_data.get("hp_test_result") == "negative"
        no_indication = (
            not any([dyspepsia, ulcer_hx, family_gastric, immigrant_prev])
            and patient_data.get("hp_test_result") is None
        )
        has_alarm = any(isinstance(o, Stop) and "alarm" in o.reason.lower() for o in outputs)
        is_pregnant = bool(pregnant or breastfeeding)
        went_to_tx = any(isinstance(o, Action) and "TREAT" in o.code for o in outputs)
        has_followup = any(isinstance(o, Action) and "RETEST" in o.code for o in outputs)
        is_pediatric = age < 18

        eradication_failed = any(
            isinstance(o, Action) and o.code == "PROCEED_TO_NEXT_TREATMENT_LINE"
            for o in outputs
        ) or any(
            isinstance(o, Stop) and "not been eradicated after three" in o.reason.lower()
            for o in outputs
        )

        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis:
                return C_UNVISIT
            if urgent:
                return C_URGENT
            if exit_:
                return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis:
                return "ma"
            if urgent:
                return "mr"
            if exit_:
                return "mo"
            return "mg"

        svg = []
        W, H = 700, 950
        svg.append(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="' + str(H) + '" '
            'viewBox="0 0 ' + str(W) + ' ' + str(H) + '" '
            'style="background:' + C_BG + ';border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append(
            "<defs>"
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>"
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
                f'fill="{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>'
            )

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x+w/2, y+h/2-8, line1, tc, 11, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 11, True)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 11, True)
            if sub:
                svgt(x+w/2, y+h-8, sub, tc+"99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w/2, h/2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(
                f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(cx, cy-7, line1, tc, 10, True)
                svgt(cx, cy+8, line2, tc, 10, True)
            else:
                svgt(cx, cy+4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x+w/2, y+h/2-7, line1, tc, 10, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 9)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 170, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {
            "present": 18, "d_test": 100, "order": 202,
            "d_alarm": 295, "d_result": 398,
            "d_preg": 498, "washout": 598, "treat": 688,
            "d_erad": 778, "complete": 878,
        }

        rect_node(CX-NW/2, Y["present"], NW, NH, nc(True), "Patient Presents")
        vline(CX, Y["present"]+NH, Y["d_test"], True)
        diamond_node(CX, Y["d_test"]+DH/2, DW, DH, dc(not is_pediatric), "1. Testing", "Indication?")
        exit_node(REXT, Y["d_test"]+(DH-EH)/2, EW, EH, nc(is_pediatric, urgent=True), "Refer Peds GI", "Age < 18")
        elbow_line(CX+DW/2, Y["d_test"]+DH/2, REXT, Y["d_test"]+(DH-EH)/2+EH/2, is_pediatric, urgent=True, label="Age<18")
        exit_node(LEXT, Y["d_test"]+(DH-EH)/2, EW, EH, nc(no_indication, exit_=True), "No Indication", "Reassess")
        elbow_line(CX-DW/2, Y["d_test"]+DH/2, LEXT+EW, Y["d_test"]+(DH-EH)/2+EH/2, no_indication, exit_=True, label="No")

        v2 = not no_indication and not is_pediatric
        vline(CX, Y["d_test"]+DH, Y["order"], v2, label="Yes")
        rect_node(CX-NW/2, Y["order"], NW, NH, nc(v2), "Order HpSAT / UBT", sub="Pre-test washout req.")

        alarm_step_visited = v2
        vline(CX, Y["order"]+NH, Y["d_alarm"], alarm_step_visited)
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(alarm_step_visited), "2. Alarm", "Features?")

        urgent_alarm = has_alarm and alarm_step_visited
        exit_node(REXT, Y["d_alarm"]+(DH-EH)/2, EW, EH, nc(urgent_alarm, urgent=True), "⚠ Urgent Refer", "GI / Endoscopy")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT, Y["d_alarm"]+(DH-EH)/2+EH/2, urgent_alarm, urgent=True, label="Yes")

        v_res = patient_data.get("hp_test_result") is not None
        v3 = alarm_step_visited and not has_alarm and v_res
        vline(CX, Y["d_alarm"]+DH, Y["d_result"], v3, label="No")
        diamond_node(CX, Y["d_result"]+DH/2, DW, DH, dc(v3), "3. H. pylori", "Test Result?")

        v_neg = v3 and test_negative
        exit_node(LEXT, Y["d_result"]+(DH-EH)/2, EW, EH, nc(v_neg, exit_=True), "Negative", "→ Dyspepsia Path")
        elbow_line(CX-DW/2, Y["d_result"]+DH/2, LEXT+EW, Y["d_result"]+(DH-EH)/2+EH/2, v_neg, exit_=True, label="-")

        v4 = v3 and is_positive and not has_alarm
        vline(CX, Y["d_result"]+DH, Y["d_preg"], v4, label="+")
        diamond_node(CX, Y["d_preg"]+DH/2, DW, DH, dc(v4), "Pregnancy /", "Nursing?")
        v_preg = is_pregnant and is_positive and not has_alarm
        exit_node(REXT, Y["d_preg"]+(DH-EH)/2, EW, EH, nc(v_preg, urgent=True), "Do Not Treat", "Reassess postpartum")
        elbow_line(CX+DW/2, Y["d_preg"]+DH/2, REXT, Y["d_preg"]+(DH-EH)/2+EH/2, v_preg, urgent=True, label="Yes")

        v5 = v4 and not is_pregnant
        vline(CX, Y["d_preg"]+DH, Y["washout"], v5, label="No")
        rect_node(CX-NW/2, Y["washout"], NW, NH, nc(v5), "Washout Verified", sub="Abx / PPI / Bismuth")

        vline(CX, Y["washout"]+NH, Y["treat"], went_to_tx)
        rect_node(CX-NW/2, Y["treat"], NW, NH, nc(went_to_tx), "4. Treatment", "Selection", sub="1st / 2nd / 3rd / 4th Line")

        vline(CX, Y["treat"]+NH, Y["d_erad"], has_followup)
        diamond_node(CX, Y["d_erad"]+DH/2, DW, DH, dc(has_followup), "5. Eradication", "Confirmed?")

        exit_node(
            REXT, Y["d_erad"]+(DH-EH)/2, EW, EH,
            nc(eradication_failed, urgent=eradication_failed, exit_=eradication_failed),
            "Failure", "→ Next Line / Refer"
        )
        elbow_line(
            CX+DW/2, Y["d_erad"]+DH/2, REXT, Y["d_erad"]+(DH-EH)/2+EH/2,
            eradication_failed, urgent=eradication_failed, exit_=eradication_failed, label="No"
        )

        v8 = has_followup and not eradication_failed
        vline(CX, Y["d_erad"]+DH, Y["complete"], v8, exit_=v8, label="Yes")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v8, exit_=v8), "Pathway Complete", sub="Re-infection <2%")

        ly = H - 22; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=980, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        hp_disp = {"positive": "✓ Positive", "negative": "✗ Negative", None: "Not yet tested"}
        test_str = hp_disp.get(patient_data.get("hp_test_result"), "—")
        tx_labels = {1: "Treatment Naive", 2: "Second Line", 3: "Third Line", 4: "Fourth Line"}
        alarm_fields = [
            ("family_history_esophageal_or_gastric_cancer_first_degree", "Family hx cancer"),
            ("personal_history_peptic_ulcer_disease", "Peptic ulcer hx"),
            ("age_over_60_new_persistent_symptoms_over_3_months", "Age>60 new symptoms"),
            ("unintended_weight_loss", "Weight loss >5%"),
            ("progressive_dysphagia", "Dysphagia"),
            ("persistent_vomiting_not_cannabis_related", "Persistent vomiting"),
            ("black_stool_or_blood_in_vomit", "GI bleed signs"),
            ("iron_deficiency_anemia_present", "IDA"),
            ("clinician_concern_serious_pathology", "Clinician concern"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"
        pen_str = "Yes — penicillin-allergic regimens apply" if penicillin_allergy else "No"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>H. Pylori Test:</b> {test_str} &nbsp;|&nbsp; <b>Test Type:</b> {hp_test_type}</span><br>'
            f'<span><b>Treatment Line:</b> {tx_labels.get(tx_map[tx_line_sel], "—")}</span><br>'
            f'<span><b>Penicillin Allergy:</b> {pen_str}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        def _med_table_html(key: str) -> str:
            r = REGIMEN_DETAILS.get(key)
            if not r:
                return ""
            rows = "".join(
                f'<tr>'
                f'<td style="color:#93c5fd;padding:3px 12px 3px 0;min-width:200px">{html.escape(str(m["drug"]))}</td>'
                f'<td style="padding:3px 12px 3px 0;color:#e2e8f0">{html.escape(str(m["dose"]))}</td>'
                f'<td style="padding:3px 0;color:#a5f3fc">{html.escape(str(m["frequency"]))}</td>'
                f'</tr>'
                for m in r["medications"]
            )
            notes_html = f'<p class="med-note">📝 {html.escape(str(r["notes"]))}</p>' if r.get("notes") else ""
            return (
                '<div class="med-table-wrap">'
                '<div class="med-table-header">'
                f'📋 {html.escape(str(r["name"]))} &nbsp;|&nbsp; ⏱ {html.escape(str(r["duration"]))}'
                f' &nbsp;|&nbsp; 💊 {html.escape(str(r["approx_cost"]))}'
                "</div>"
                f'<table style="border-collapse:collapse;width:100%">{rows}</table>'
                f"{notes_html}"
                "</div>"
            )

        def _detail_html(details) -> str:
            if not details:
                return ""
            items = ""
            if isinstance(details, dict):
                for bullet in details.get("bullets", []):
                    items += f"<li>{html.escape(str(bullet))}</li>"
                for note in details.get("notes", []):
                    items += f'<li style="color:#fde68a">⚠️ {html.escape(str(note))}</li>'
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                skip = {"bullets", "notes", "supported_by", "regimen_key"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {
                "urgent": "urgent", "warning": "warning",
                None: "routine", "": "routine",
            }
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls:
                cls = extra_cls

            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
            med_html = _med_table_html(a.details.get("regimen_key")) if isinstance(a.details, dict) else ""
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">'
                "🔒 Override available — reason required</p>"
                if a.override_options else ""
            )

            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{med_html}{detail_html}{override_html}"
                "</div>",
                unsafe_allow_html=True,
            )
            if a.override_options:
                override_candidates.append(a)

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        for output in outputs:
            if isinstance(output, Action):
                render_action(output)
            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in output.missing_fields)
                msg_html = html.escape(output.message).replace("\n", "<br>")
                st.markdown(
                    '<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span>'
                    f' ⏳ {msg_html}</h4>'
                    f'<ul><li>Missing fields: {missing_str}</li></ul>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
                st.markdown(
                    '<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span>'
                    f' 🛑 {reason_html}</h4>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.hp_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.hp_notes,
            height=180,
        )

        def _serialize_output(o):
            if isinstance(o, Action):
                return {
                    "type": "action",
                    "code": o.code,
                    "label": o.label,
                    "urgency": o.urgency,
                }
            if isinstance(o, Stop):
                return {
                    "type": "stop",
                    "reason": o.reason,
                    "urgency": getattr(o, "urgency", None),
                }
            if isinstance(o, DataRequest):
                return {
                    "type": "data_request",
                    "message": o.message,
                    "missing_fields": o.missing_fields,
                }
            return {"type": "other", "repr": repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [
                    {
                        "node": o.target_node,
                        "field": o.field,
                        "new_value": o.new_value,
                        "reason": o.reason,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in st.session_state.hp_overrides
                ],
                "clinician_notes": st.session_state.hp_notes,
            },
        }

        if st.button("💾 Save this output", key="hp_save_output"):
            st.session_state.hp_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "hp_saved_output" in st.session_state:
            md_text = build_h_pylori_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.hp_overrides,
                notes=st.session_state.hp_notes,
            )

            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="h_pylori_summary.md",
                mime="text/markdown",
                key="hp_download_md",
            )

        def _pretty(s: str) -> str:
            return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node = _pretty(raw_node)
                    field = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(
                            f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (o for o in st.session_state.hp_overrides
                             if o.target_node == raw_node and o.field == raw_field),
                            None,
                        )
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(
                            f"Set `{field}` to:",
                            options=allowed,
                            index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}",
                            horizontal=True,
                        )
                        reason = st.text_input(
                            "Reason (required):",
                            value=existing.reason if existing else "",
                            key=f"ov_reason_{raw_node}_{raw_field}",
                            placeholder="Document clinical rationale...",
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.hp_overrides = [
                                        o for o in st.session_state.hp_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.hp_overrides.append(
                                        Override(
                                            target_node=raw_node,
                                            field=raw_field,
                                            old_value=None,
                                            new_value=new_val,
                                            reason=reason.strip(),
                                        )
                                    )
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.hp_overrides = [
                                    o for o in st.session_state.hp_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.hp_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.hp_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code>'
                            f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">'
                            f'Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            "</div>",
                            unsafe_allow_html=True,
                        )

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption(
                        "  ".join(
                            f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None
                        )
                    )
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
