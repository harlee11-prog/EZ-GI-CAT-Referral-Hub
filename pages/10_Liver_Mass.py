import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Ensure liver_mass_engine is accessible in your path
from liver_mass_engine import (
    run_liver_mass_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Liver Mass", page_icon="🫀", layout="wide")

# ── MARKDOWN / PDF HELPERS ──────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_liver_mass_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Liver Mass Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / {str(patient_data.get('sex', '')).capitalize()}")
    lines.append(f"- **Lesion Detected:** {_safe_text(patient_data.get('liver_lesion_detected'))}")
    lines.append(f"- **Lesion Type:** {_safe_text(patient_data.get('lesion_type')) or 'Not specified'}")
    lines.append(f"- **Modality:** {_safe_text(patient_data.get('imaging_modality')) or 'N/A'}")
    lines.append(f"- **High Risk Factors:** Cirrhosis ({patient_data.get('history_cirrhosis')}), Hep B ({patient_data.get('chronic_hepatitis_b')}), Hep C ({patient_data.get('chronic_hepatitis_c')}), Prior Malignancy ({patient_data.get('prior_malignancy_any_location')})")
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
                    for k, v in o.details.items():
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

st.title("🫀 Liver Mass (Solid Lesion) Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "lm_overrides" not in st.session_state:
    st.session_state.lm_overrides = []
if "lm_has_run" not in st.session_state:
    st.session_state.lm_has_run = False
if "lm_notes" not in st.session_state:
    st.session_state.lm_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 50)
    sex = st.selectbox("Sex", ["male", "female"])
    
    st.markdown("**Initial Detection**")
    liver_lesion_detected = st.checkbox("Liver lesion detected on imaging", value=True)
    
    lesion_type_map = {
        "Unknown / Not Classified": None,
        "Simple Cyst": "simple_cyst",
        "Complex Cyst": "complex_cyst",
        "Hemangioma": "hemangioma",
        "Focal Nodular Hyperplasia (FNH)": "fnh",
        "Adenoma": "adenoma",
        "Indeterminate / Suspicious Solid": "indeterminate_suspicious",
        "Solid (Unspecified)": "solid_unspecified",
        "Metastatic Disease": "metastatic_disease"
    }
    lesion_type_sel = st.selectbox("Lesion Type", list(lesion_type_map.keys()))
    
    modality = st.selectbox("Imaging Modality", ["Ultrasound", "CT", "MRI", "Other"])
    symptomatic_status = st.selectbox("Detection Context", ["Incidental", "Symptomatic"])
    lesion_size = st.number_input("Lesion Size (cm)", 0.0, 50.0, 0.0, step=0.5)
    
    rad_confident = st.checkbox("Radiology characterization confident", value=True)
    rad_followup = st.checkbox("Radiology recommends follow-up")

    st.markdown("**Red Flags**")
    epigastric_pain = st.checkbox("Episodic epigastric or RUQ pain")
    hypotension = st.checkbox("Accompanied by hypotension")
    
    st.markdown("**High Risk Factors**")
    hx_cirrhosis = st.checkbox("History of Cirrhosis")
    hx_hep_b = st.checkbox("Chronic Hepatitis B")
    hx_hep_c = st.checkbox("Chronic Hepatitis C")
    hx_malignancy = st.checkbox("Prior Malignancy (Any location)")
    clinician_concern = st.checkbox("Clinician concern for malignancy")

    st.markdown("**Clinical Symptoms & Specifics**")
    weight_loss = st.checkbox("Unintentional weight loss (>5%)")
    persistent_pain = st.checkbox("Persistent abdominal pain")
    early_satiety = st.checkbox("Early satiety")
    pregnant = st.checkbox("Currently Pregnant (relevant for Adenoma)")
    ocp_use = st.checkbox("Oral Contraceptive Use")
    
    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.lm_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.lm_overrides = []
        if "lm_saved_output" in st.session_state:
            del st.session_state["lm_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.lm_has_run:
        patient_data = {
            "age": age,
            "sex": sex,
            "liver_lesion_detected": liver_lesion_detected,
            "lesion_type": lesion_type_map[lesion_type_sel],
            "imaging_modality": modality,
            "incidental_vs_symptomatic": symptomatic_status,
            "lesion_characterization_confident": rad_confident,
            "radiology_recommends_followup": rad_followup,
            "episodic_epigastric_or_ruq_pain": epigastric_pain,
            "hypotension": hypotension,
            "lesion_size_cm": lesion_size if lesion_size > 0 else None,
            "cyst_size_cm": lesion_size if lesion_size > 0 else None,
            "history_cirrhosis": hx_cirrhosis,
            "chronic_hepatitis_b": hx_hep_b,
            "chronic_hepatitis_c": hx_hep_c,
            "prior_malignancy_any_location": hx_malignancy,
            "clinician_concern_malignancy": clinician_concern,
            "unintentional_weight_loss": weight_loss,
            "persistent_abdominal_pain": persistent_pain,
            "early_satiety": early_satiety,
            "pregnant": pregnant,
            "oral_contraceptive_use": ocp_use,
            "possibly_symptomatic": (epigastric_pain or persistent_pain),
        }

        outputs, logs, applied_overrides = run_liver_mass_pathway(
            patient_data, overrides=st.session_state.lm_overrides
        )

        # Flag Extraction for SVG Flowchart
        has_lesion = patient_data.get("liver_lesion_detected") is True
        l_type = patient_data.get("lesion_type")
        is_cyst = l_type in ["simple_cyst", "complex_cyst"]
        is_solid = l_type in ["hemangioma", "fnh", "adenoma", "indeterminate_suspicious", "solid_unspecified", "metastatic_disease"]
        
        # Checking logic applied in engine
        hem_flag = patient_data.get("episodic_epigastric_or_ruq_pain") and patient_data.get("hypotension") and is_solid
        # Check overrides for hem_flag
        for o in st.session_state.lm_overrides:
            if o.target_node == "Red_Flag_Hemorrhage" and o.field == "hemorrhage_red_flag":
                hem_flag = o.new_value

        risk_flag = hx_cirrhosis or hx_hep_b or hx_hep_c or hx_malignancy or clinician_concern
        for o in st.session_state.lm_overrides:
            if o.target_node == "Solid_Lesion_Risk_Assessment" and o.field == "high_risk_malignancy":
                risk_flag = o.new_value

        # SVG Colors and Utilities
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if exit_: return C_EXIT
            return C_MAIN

        def dc(vis): return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent: return "mr"
            if exit_: return "mo"
            return "mg"

        svg = []
        W, H = 700, 750
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')
        svg.append("<defs>"
                   '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
                   '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
                   '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
                   '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
                   "</defs>")

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>')

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
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
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy-7, line1, tc, 10, True)
                svgt(cx, cy+8, line2, tc, 10, True)
            else:
                svgt(cx, cy+4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-7, line1, tc, 10, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 9)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label: svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label: svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        # SVG Flow Layout 
        CX = 350; NW, NH = 180, 50; DW, DH = 180, 58; EW, EH = 150, 46
        LEXT = 40; REXT = W - 40 - EW
        Y = {"present": 20, "d_hem": 110, "d_type": 210, "risk_ass": 310, "mgt": 420}

        # 1. Start Node
        rect_node(CX-NW/2, Y["present"], NW, NH, nc(has_lesion), "Initial Classification", sub="Determine Cyst vs Solid")
        
        # 2. Hemorrhage Red Flag
        vline(CX, Y["present"]+NH, Y["d_hem"], has_lesion and l_type is not None)
        v_hem_visited = has_lesion and l_type is not None
        diamond_node(CX, Y["d_hem"]+DH/2, DW, DH, dc(v_hem_visited), "Red Flag:", "Hemorrhage?")
        
        # Exit to Emergency
        exit_node(REXT, Y["d_hem"]+(DH-EH)/2, EW, EH, nc(hem_flag, urgent=True), "Emergent Care", "RAAPID / ED")
        elbow_line(CX+DW/2, Y["d_hem"]+DH/2, REXT, Y["d_hem"]+(DH-EH)/2+EH/2, hem_flag, urgent=True, label="Yes")

        # 3. Cyst vs Solid
        v_cyst_solid = v_hem_visited and not hem_flag
        vline(CX, Y["d_hem"]+DH, Y["d_type"], v_cyst_solid, label="No")
        diamond_node(CX, Y["d_type"]+DH/2, DW, DH, dc(v_cyst_solid), "Lesion Category", "Cyst vs Solid?")

        # Branch Left: Cyst
        v_cyst = v_cyst_solid and is_cyst
        exit_node(LEXT, Y["d_type"]+(DH-EH)/2, EW, EH, nc(v_cyst, exit_=True), "Cyst Pathway", "Simple/Complex Mgt")
        elbow_line(CX-DW/2, Y["d_type"]+DH/2, LEXT+EW, Y["d_type"]+(DH-EH)/2+EH/2, v_cyst, exit_=True, label="Cyst")

        # Branch Down: Solid Risk Assessment
        v_solid = v_cyst_solid and is_solid
        vline(CX, Y["d_type"]+DH, Y["risk_ass"], v_solid, label="Solid")
        diamond_node(CX, Y["risk_ass"]+DH/2, DW, DH, dc(v_solid), "Risk Assessment", "High or Low Risk?")

        # Branch Left: Low Risk
        v_low = v_solid and not risk_flag
        exit_node(LEXT, Y["risk_ass"]+(DH-EH)/2, EW, EH, nc(v_low, exit_=True), "Low Risk Mgt", "Hemangioma/FNH/Adenoma")
        elbow_line(CX-DW/2, Y["risk_ass"]+DH/2, LEXT+EW, Y["risk_ass"]+(DH-EH)/2+EH/2, v_low, exit_=True, label="Low Risk")

        # Branch Right: High Risk
        v_high = v_solid and risk_flag
        exit_node(REXT, Y["risk_ass"]+(DH-EH)/2, EW, EH, nc(v_high, exit_=True), "High Risk Mgt", "Cirrhosis/Hep/Malignancy")
        elbow_line(CX+DW/2, Y["risk_ass"]+DH/2, REXT, Y["risk_ass"]+(DH-EH)/2+EH/2, v_high, exit_=True, label="High Risk")

        # Legend
        ly = H - 22; lx = 18
        for col, lbl in [(C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>", height=780, scrolling=True
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Context Card
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Lesion Type:</b> {lesion_type_sel} &nbsp;|&nbsp; <b>Modality:</b> {modality}</span><br>'
            f'<span><b>Size:</b> {lesion_size} cm</span><br>'
            f'<span><b>High Risk Profile:</b> {"Yes" if risk_flag else "No"}</span>'
            "</div>", unsafe_allow_html=True
        )

        override_candidates = []

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls

            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n", "<br>")

            # Detail extraction
            items = ""
            if isinstance(a.details, dict):
                for k, v in a.details.items():
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k)).replace('_', ' ').title()}:</b> {html.escape(str(v))}</li>"
            detail_html = f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

            override_html = ('<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">🔒 Override available — reason required</p>' if a.override_options else "")

            st.markdown(f'<div class="action-card {cls}"><h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>{detail_html}{override_html}</div>', unsafe_allow_html=True)
            if a.override_options: override_candidates.append(a)

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        for output in outputs:
            if isinstance(output, Action): render_action(output)
            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in output.missing_fields)
                msg_html = html.escape(output.message).replace("\n", "<br>")
                st.markdown(f'<div class="action-card warning"><h4><span class="badge warning">DATA NEEDED</span> ⏳ {msg_html}</h4><ul><li>Missing fields: {missing_str}</li></ul></div>', unsafe_allow_html=True)
                for sa in output.suggested_actions: render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n", "<br>")
                cls_stop = "stop" if output.urgency == "urgent" else "warning"
                st.markdown(f'<div class="action-card {cls_stop}"><h4><span class="badge {cls_stop}">STOP</span> 🛑 {reason_html}</h4></div>', unsafe_allow_html=True)
                for a in output.actions: render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.session_state.lm_notes = st.text_area("Notes to attach to the saved output:", value=st.session_state.lm_notes, height=180)

        if st.button("💾 Save this output", key="lm_save_output"):
            st.success("Output saved for this session.")

        md_text = build_liver_mass_markdown(patient_data, outputs, st.session_state.lm_overrides, st.session_state.lm_notes)
        st.download_button(label="⬇️ Download Markdown summary", data=md_text.encode("utf-8"), file_name="liver_mass_summary.md", mime="text/markdown")

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                for a in override_candidates:
                    opt = a.override_options
                    raw_node, raw_field = opt["node"], opt["field"]
                    node_name, field_name = raw_node.replace("_", " ").title(), raw_field.replace("_", " ").title()
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node_name}** → `{field_name}`"):
                        existing = next((o for o in st.session_state.lm_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(f"Set `{field_name}` to:", options=allowed, index=allowed.index(current_val) if current_val in allowed else 0, key=f"ov_val_{raw_node}_{raw_field}", horizontal=True)
                        reason = st.text_input("Reason (required):", value=existing.reason if existing else "", key=f"ov_reason_{raw_node}_{raw_field}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip(): st.error("A reason is required.")
                                else:
                                    st.session_state.lm_overrides = [o for o in st.session_state.lm_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.lm_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Override applied. Click **▶ Run Pathway**.")
                        with col2:
                            if existing and st.button("🗑 Remove", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.lm_overrides = [o for o in st.session_state.lm_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.lm_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.lm_overrides:
                        st.markdown(f'<div class="override-card">🛠 <b>{html.escape(o.target_node.replace("_", " ").title())}</b> → <code>{html.escape(o.field.replace("_", " ").title())}</code> set to <b>{html.escape(str(o.new_value))}</b><br><span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span></div>', unsafe_allow_html=True)

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                st.markdown(f"**[{datetime.fromisoformat(log.timestamp).strftime('%H:%M:%S')}] {log.node}** → _{log.decision}_")
                if log.used_inputs: st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
