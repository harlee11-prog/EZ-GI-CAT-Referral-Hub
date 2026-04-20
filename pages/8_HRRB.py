import os, sys
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
import io

# Import the HRRB engine. Adjust the module name if the file is named differently.
from hrrb_engine import run_hrrb_pathway, Action, DataRequest, Stop, Override

st.set_page_config(page_title="High Risk Rectal Bleeding", layout="wide")

# ── MARKDOWN HELPERS ────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def _pretty(s: str) -> str:
    if not s:
        return ""
    return s.replace("_", " ").title()

def build_hrrb_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# High Risk Rectal Bleeding Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Sex:** {_safe_text(patient_data.get('sex')).capitalize() or 'Not specified'}")
    lines.append(f"- **Visible Blood:** {_safe_text(patient_data.get('rectal_bleeding_visible'))}")
    lines.append(f"- **Persistent (>2wks):** {_safe_text(patient_data.get('rectal_bleeding_duration_weeks'))} weeks")
    lines.append(f"- **Recent Colonoscopy (<2y):** {_safe_text(patient_data.get('complete_colonoscopy_within_2y'))}")
    lines.append(f"- **DRE Completed:** {_safe_text(patient_data.get('dre_done'))}")
    lines.append(f"- **Hemoglobin:** {_safe_text(patient_data.get('hemoglobin'))}")
    lines.append(f"- **Ferritin:** {_safe_text(patient_data.get('ferritin'))}")
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
                    for b in o.details.get("supported_by", []):
                        lines.append(f"  - Support: {_safe_text(b)}")
                    skip = {"bullets", "notes", "supported_by"}
                    for k, v in o.details.items():
                        if k in skip: continue
                        if isinstance(v, list) and v:
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_',' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_',' ').title()}: {_safe_text(v)}")
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
.action-card.semi_urgent { background:#3b2a0a; border-left:5px solid #f97316; color:#fed7aa; }
.action-card.routine { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info    { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop    { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.badge {
    display:inline-block; font-size:11px; font-weight:bold;
    padding:2px 8px; border-radius:20px; margin-right:6px;
    text-transform:uppercase; letter-spacing:0.5px;
}
.badge.urgent  { background:#ef4444; color:#fff; }
.badge.semi_urgent { background:#f97316; color:#fff; }
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

st.title("High Risk Rectal Bleeding Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "hrrb_overrides" not in st.session_state:
    st.session_state.hrrb_overrides = []

if "hrrb_has_run" not in st.session_state:
    st.session_state.hrrb_has_run = False

if "hrrb_notes" not in st.session_state:
    st.session_state.hrrb_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    
    st.markdown("**1. Demographics**")
    sex = st.selectbox("Sex", ["male", "female", "unknown"])
    
    st.markdown("**2. Symptoms of Rectal Bleeding**")
    visible = st.checkbox("Blood visibly present in/on stool or toilet")
    not_just_tissue = st.checkbox("Bleeding is NOT just on the tissue paper")
    new_worsening = st.checkbox("New onset or worsening")
    persistent = st.checkbox("Persistent (present most days of the week)")
    duration = st.number_input("Duration of symptoms (weeks)", min_value=0.0, step=1.0)
    colo_2y = st.radio("Complete colonoscopy within the last 2 years?", ["Yes", "No", "Unknown"], index=2)

    st.markdown("**3. Medical History**")
    hx_personal_crc = st.checkbox("Personal history of CRC")
    hx_family_crc = st.checkbox("First-degree family history of CRC")
    hx_personal_ibd = st.checkbox("Personal history of IBD")
    hx_family_ibd = st.checkbox("First-degree family history of IBD")
    endo_results = st.text_input("Results of most recent lower endoscopy (optional)")

    st.markdown("**4. Physical Exam (DRE)**")
    dre_done = st.checkbox("Digital Rectal Exam (DRE) completed")
    dre_pain = st.checkbox("DRE not possible due to pain")

    st.markdown("**5. Baseline Investigations (< 8 weeks)**")
    col1, col2 = st.columns(2)
    with col1:
        cbc_8w = st.checkbox("CBC within 8 weeks")
        ferritin_8w = st.checkbox("Ferritin within 8 weeks")
        iron_8w = st.checkbox("Serum Iron within 8 weeks")
    with col2:
        creat_8w = st.checkbox("Creatinine within 8 weeks")
        tibc_8w = st.checkbox("TIBC within 8 weeks")
    
    hb_val = st.number_input("Hemoglobin (g/L)", min_value=0.0, step=1.0, value=0.0)
    baseline_hb = st.number_input("Baseline Hemoglobin (g/L) if known", min_value=0.0, step=1.0, value=0.0)
    prior_anemia = st.checkbox("Prior anemia documented")
    ferritin_val = st.number_input("Ferritin (µg/L)", min_value=0.0, step=1.0, value=0.0)

    st.markdown("**6. Alarm Features**")
    mass_abd = st.checkbox("Palpable abdominal mass")
    mass_rectal = st.checkbox("Palpable rectal mass")
    lesion_imaging = st.checkbox("Suspected colorectal lesion on imaging")
    mets_imaging = st.checkbox("Evidence of metastases on imaging")
    abd_pain = st.checkbox("New, persistent, or worsening abdominal pain")
    wt_loss = st.number_input("Unintentional weight loss % (over 6 months)", min_value=0.0, step=0.1, value=0.0)
    bowel_change = st.checkbox("Concerning change in bowel habit")
    fit_ordered = st.checkbox("FIT ordered or planned")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.hrrb_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hrrb_overrides = []
        if "hrrb_saved_output" in st.session_state:
            del st.session_state["hrrb_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.hrrb_has_run:
        patient_data = {
            "sex": sex if sex != "unknown" else None,
            "rectal_bleeding_visible": visible if visible else None,
            "rectal_bleeding_not_just_tissue": not_just_tissue if not_just_tissue else None,
            "rectal_bleeding_new_or_worsening": new_worsening if new_worsening else None,
            "rectal_bleeding_persistent": persistent if persistent else None,
            "rectal_bleeding_most_days_per_week": persistent if persistent else None,
            "rectal_bleeding_duration_weeks": float(duration) if duration > 0 else None,
            "complete_colonoscopy_within_2y": True if colo_2y == "Yes" else (False if colo_2y == "No" else None),
            "personal_history_crc": hx_personal_crc or None,
            "family_history_crc_first_degree": hx_family_crc or None,
            "personal_history_ibd": hx_personal_ibd or None,
            "family_history_ibd_first_degree": hx_family_ibd or None,
            "most_recent_lower_endoscopy_result": endo_results if endo_results else None,
            "dre_done": dre_done or None,
            "dre_not_possible_due_to_pain": dre_pain or None,
            "cbc_within_8_weeks": cbc_8w or None,
            "creatinine_within_8_weeks": creat_8w or None,
            "serum_iron_within_8_weeks": iron_8w or None,
            "tibc_within_8_weeks": tibc_8w or None,
            "ferritin_within_8_weeks": ferritin_8w or None,
            "hemoglobin": float(hb_val) if hb_val > 0 else None,
            "baseline_hemoglobin": float(baseline_hb) if baseline_hb > 0 else None,
            "prior_anemia_documented": prior_anemia or None,
            "ferritin": float(ferritin_val) if ferritin_val > 0 else None,
            "abdominal_pain_new_persistent_or_worsening": abd_pain or None,
            "weight_loss_percent_6_months": float(wt_loss) if wt_loss > 0 else None,
            "concerning_change_in_bowel_habit": bowel_change or None,
            "palpable_abdominal_mass": mass_abd or None,
            "palpable_rectal_mass": mass_rectal or None,
            "suspected_colorectal_lesion_on_imaging": lesion_imaging or None,
            "evidence_of_metastases_on_imaging": mets_imaging or None,
            "fit_ordered_or_planned": fit_ordered or None,
        }

        outputs, logs, applied_overrides = run_hrrb_pathway(
            patient_data, overrides=st.session_state.hrrb_overrides
        )

        hrrb_criteria_met = any(isinstance(o, Action) and o.code == "HRRB_CONFIRMED" for o in outputs)
        hrrb_criteria_failed = any(isinstance(o, Stop) and "High-risk rectal bleeding criteria are not met" in o.reason for o in outputs)
        
        assigned_urgent = any(isinstance(o, Action) and o.urgency == "urgent" for o in outputs)
        assigned_semi = any(isinstance(o, Action) and o.urgency == "semi_urgent" for o in outputs)

        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_SEMI = "#f97316"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, semi=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if semi: return C_SEMI
            if exit_: return C_EXIT
            return C_MAIN

        def dc(vis): return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, semi=False, exit_=False):
            if not vis: return "ma"
            if urgent: return "mr"
            if semi: return "ms"
            if exit_: return "mo"
            return "mg"

        svg = []
        W, H = 700, 850
        svg.append(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="' + str(H) + '" '
            'viewBox="0 0 ' + str(W) + ' ' + str(H) + '" '
            'style="background:' + C_BG + ';border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append(
            "<defs>"
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="ms" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#f97316"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>"
        )

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

        def vline(x, y1, y2, vis, urgent=False, semi=False, exit_=False, label=""):
            m = mid(vis, urgent, semi, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "ms": "#f97316", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, semi=False, exit_=False, label=""):
            m = mid(vis, urgent, semi, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "ms": "#f97316", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 180, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 40; REXT = W - 40 - EW
        Y = { "start": 20, "hrrb": 100, "hx": 200, "exam": 300, "labs": 400, "alarm": 500, "refer": 620 }

        rect_node(CX-NW/2, Y["start"], NW, NH, nc(True), "1. Symptoms Review")
        vline(CX, Y["start"]+NH, Y["hrrb"], True)
        
        diamond_node(CX, Y["hrrb"]+DH/2, DW, DH, dc(True), "HRRB Criteria", "Met?")
        
        exit_node(LEXT, Y["hrrb"]+(DH-EH)/2, EW, EH, nc(hrrb_criteria_failed, exit_=True), "Low Risk Pathway", "Monitor & Re-evaluate")
        elbow_line(CX-DW/2, Y["hrrb"]+DH/2, LEXT+EW, Y["hrrb"]+(DH-EH)/2+EH/2, hrrb_criteria_failed, exit_=True, label="No")

        vline(CX, Y["hrrb"]+DH, Y["hx"], hrrb_criteria_met, label="Yes")
        rect_node(CX-NW/2, Y["hx"], NW, NH, nc(hrrb_criteria_met), "2. Medical History", sub="CRC/IBD/Endoscopy")

        vline(CX, Y["hx"]+NH, Y["exam"], hrrb_criteria_met)
        rect_node(CX-NW/2, Y["exam"], NW, NH, nc(hrrb_criteria_met), "3. Physical Exam", sub="Digital Rectal Exam (DRE)")

        vline(CX, Y["exam"]+NH, Y["labs"], hrrb_criteria_met)
        rect_node(CX-NW/2, Y["labs"], NW, NH, nc(hrrb_criteria_met), "4. Investigations", sub="CBC, Creatinine, Fe, Ferritin")

        vline(CX, Y["labs"]+NH, Y["alarm"], hrrb_criteria_met)
        diamond_node(CX, Y["alarm"]+DH/2, DW, DH, dc(hrrb_criteria_met), "5. Alarm Scenarios", "(A, B, C)")

        exit_node(LEXT, Y["alarm"]+(DH-EH)/2 + 80, EW, EH, nc(assigned_urgent, urgent=True), "URGENT Refer (<2w)", "Scenario A or B")
        elbow_line(CX-DW/2, Y["alarm"]+DH/2, LEXT+EW/2, Y["alarm"]+(DH-EH)/2 + 80, assigned_urgent, urgent=True, label="A/B")

        exit_node(REXT, Y["alarm"]+(DH-EH)/2 + 80, EW, EH, nc(assigned_semi, semi=True), "SEMI-URGENT Refer (<8w)", "Scenario C or Pain")
        elbow_line(CX+DW/2, Y["alarm"]+DH/2, REXT+EW/2, Y["alarm"]+(DH-EH)/2 + 80, assigned_semi, semi=True, label="C/Pain")

        ly = H - 30; lx = 20
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_SEMI, "Semi-Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 105
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=880, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Sex:</b> {sex.capitalize()}</span><br>'
            f'<span><b>Hb / Ferritin:</b> {hb_val if hb_val else "—"} / {ferritin_val if ferritin_val else "—"}</span><br>'
            f'<span><b>Recent Colonoscopy (<2y):</b> {colo_2y}</span><br>'
            f'<span><b>Duration:</b> {duration} weeks</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 & 2 — HRRB Confirmation",
                "icon": "🔍",
                "cls": "routine",
                "codes": {"HRRB_CONFIRMED", "HRRB_NOT_MET"}
            },
            "step3": {
                "label": "Step 3 — Medical History",
                "icon": "📋",
                "cls": "info",
                "codes": {"RECORD_MEDICAL_HISTORY", "COLONOSCOPY_RECORDS_REQUESTED"}
            },
            "step4": {
                "label": "Step 4 — Physical Exam (DRE)",
                "icon": "🧤",
                "cls": "routine",
                "codes": {"DRE_COMPLETED", "DRE_NOT_COMPLETED"}
            },
            "step5": {
                "label": "Step 5 — Baseline Investigations",
                "icon": "🩸",
                "cls": "routine",
                "codes": {"CBC_RECORDED", "IRON_STUDIES_RECORDED", "CREATININE_RECORDED", "ORDER_BASELINE_INVESTIGATIONS", "PRIOR_ANEMIA_DOCUMENTED", "ANEMIA_DOCUMENTED", "IRON_DEFICIENCY_DOCUMENTED", "FIT_ORDER_NOTED"}
            },
            "step6": {
                "label": "Step 6 — Alarm Features Assessment",
                "icon": "🚨",
                "cls": "warning",
                "codes": {"SCENARIO_A_MET", "SCENARIO_B_MET", "SCENARIO_C_MET", "NO_ALARM_SCENARIOS_MET"}
            },
            "step7": {
                "label": "Step 7 — Urgency & Referral",
                "icon": "🏥",
                "cls": "urgent",
                "codes": {"ASSIGN_URGENCY_HRRB", "REFER_COLONOSCOPY"}
            },
        }

        code_to_group = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        grouped: dict = {k: [] for k in STEP_GROUPS}
        grouped["other"] = []
        stops_and_requests = []
        override_candidates = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                gkey = code_to_group.get(output.code, "other")
                grouped[gkey].append(output)

        for output in outputs:
            if isinstance(output, Stop):
                for a in getattr(output, "actions", []):
                    if getattr(a, "override_options", None) and a not in override_candidates:
                        override_candidates.append(a)
            elif getattr(output, "override_options", None):
                 override_candidates.append(output)

        def render_group(gkey: str, actions: list, title_override=None, cls_override=None, icon_override=None) -> None:
            if not actions:
                return
            if gkey in STEP_GROUPS:
                g = STEP_GROUPS[gkey]
                cls = g["cls"]
                icon = g["icon"]
                label = g["label"]
            else:
                cls = cls_override or "routine"
                icon = icon_override or "⚙️"
                label = title_override or "Other Actions"

            border_colors = {"routine": "#22c55e", "info": "#3b82f6", "urgent": "#ef4444", "semi_urgent": "#f97316", "warning": "#f59e0b"}
            bg_colors = {"routine": "#052e16", "info": "#0c1a2e", "urgent": "#3b0a0a", "semi_urgent": "#3b2a0a", "warning": "#2d1a00"}
            border = border_colors.get(cls, "#22c55e")
            bg = bg_colors.get(cls, "#052e16")

            bullets = ""
            for a in actions:
                if getattr(a, "override_options", None) and a not in override_candidates:
                    override_candidates.append(a)
                bullets += f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                if isinstance(a.details, dict):
                    sub_items = []
                    if "supported_by" in a.details:
                        for s in a.details["supported_by"]:
                            sub_items.append(html.escape(str(s)))
                    for dk, dv in a.details.items():
                        if dk == "supported_by": continue
                        if dv not in (None, False, "", []):
                            if isinstance(dv, list):
                                for i in dv:
                                    sub_items.append(html.escape(str(i)))
                            else:
                                sub_items.append(f"{html.escape(str(dk)).replace('_',' ').title()}: {html.escape(str(dv))}")
                    if sub_items:
                        bullets += f'<br><span style="color:#94a3b8;font-size:12px;margin-left:14px">↳ {"; ".join(sub_items)}</span>'

                if getattr(a, "override_options", None):
                    bullets += '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">⚙ override available</span>'
                bullets += "</li>"

            st.markdown(
                f'<div style="background:{bg};border-left:5px solid {border};'
                f'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                f'<p style="margin:0 0 10px 0;font-size:13px;font-weight:700;'
                f'color:#e2e8f0;letter-spacing:0.3px">'
                f'{icon} {html.escape(label)}</p>'
                f'<ul style="margin:0;padding-left:18px;color:#cbd5e1;'
                f'font-size:13.5px;line-height:1.7">{bullets}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

        def render_stop_request(output) -> None:
            if isinstance(output, DataRequest):
                missing_str = ", ".join(_pretty(f) for f in output.missing_fields)
                msg_html = html.escape(output.message)
                
                action_bullets = "".join(
                    f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                    + (
                        '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                        '⚙ override available</span>'
                        if getattr(a, "override_options", None) else ""
                    )
                    + "</li>"
                    for a in getattr(output, "suggested_actions", [])
                )
                
                for a in getattr(output, "suggested_actions", []):
                    if getattr(a, "override_options", None) and a not in override_candidates:
                        override_candidates.append(a)

                action_block = (
                    f'<ul style="margin:10px 0 0;padding-left:18px;color:#cbd5e1;'
                    f'font-size:13.5px;line-height:1.7">{action_bullets}</ul>'
                    if action_bullets else ""
                )
                
                st.markdown(
                    '<div style="background:#2d1a00;border-left:5px solid #f59e0b;'
                    'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    '<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#fde68a">'
                    '⏳ Data Required to Proceed</p>'
                    f'<p style="margin:0 0 6px;font-size:13.5px;color:#fde68a">{msg_html}</p>'
                    f'<p style="margin:0;font-size:12px;color:#94a3b8">'
                    f'Missing: <code style="color:#fbbf24">{missing_str}</code></p>'
                    f'{action_block}'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif isinstance(output, Stop):
                is_emergent = getattr(output, "urgency", None) == "urgent"
                is_semi = getattr(output, "urgency", None) == "semi_urgent"
                is_complete = "complete" in output.reason.lower() or "medical home" in output.reason.lower()
                
                if is_emergent:
                    bg, border, icon, tcol = "#3b0a0a", "#ef4444", "🚨", "#fecaca"
                elif is_semi:
                    bg, border, icon, tcol = "#3b2a0a", "#f97316", "⚠️", "#fed7aa"
                elif is_complete:
                    bg, border, icon, tcol = "#052e16", "#22c55e", "✅", "#bbf7d0"
                else:
                    bg, border, icon, tcol = "#1e1e2e", "#6366f1", "ℹ️", "#c7d2fe"
                
                title = output.reason

                action_bullets = "".join(
                    f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                    + (
                        '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                        '⚙ override available</span>'
                        if getattr(a, "override_options", None) else ""
                    )
                    + "</li>"
                    for a in getattr(output, "actions", [])
                )
                
                for a in getattr(output, "actions", []):
                    if getattr(a, "override_options", None) and a not in override_candidates:
                        override_candidates.append(a)
                
                action_block = (
                    f'<ul style="margin:10px 0 0;padding-left:18px;color:#cbd5e1;'
                    f'font-size:13.5px;line-height:1.7">{action_bullets}</ul>'
                    if action_bullets else ""
                )
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};'
                    f'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    f'<p style="margin:0 0 {"6px" if action_block else "0"};font-size:13px;'
                    f'font-weight:700;color:{tcol}">{icon} {html.escape(title)}</p>'
                    f'{action_block}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        if grouped["other"]:
            render_group("other", grouped["other"], title_override="Additional Actions", cls_override="info", icon_override="⚙️")

        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.session_state.hrrb_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.hrrb_notes,
            height=180,
        )

        def _serialize_output(o):
            if isinstance(o, Action): return {"type": "action", "code": o.code, "label": o.label, "urgency": o.urgency}
            if isinstance(o, Stop): return {"type": "stop", "reason": o.reason, "urgency": getattr(o, "urgency", None)}
            if isinstance(o, DataRequest): return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
            return {"type": "other"}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [{"node": o.target_node, "field": o.field, "new_value": o.new_value, "reason": o.reason, "created_at": o.created_at.isoformat()} for o in st.session_state.hrrb_overrides],
                "clinician_notes": st.session_state.hrrb_notes,
            },
        }

        if st.button("💾 Save this output", key="hrrb_save_output"):
            st.session_state.hrrb_saved_output = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        if "hrrb_saved_output" in st.session_state:
            md_text = build_hrrb_markdown(patient_data, outputs, st.session_state.hrrb_overrides, st.session_state.hrrb_notes)
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="hrrb_summary.md",
                mime="text/markdown",
                key="hrrb_download_md",
            )

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                for a in override_candidates:
                    opt = a.override_options
                    raw_node, raw_field = opt["node"], opt["field"]
                    node, field = _pretty(raw_node), _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        st.markdown(f'<div class="override-card">Engine decision based on: <b>{html.escape(a.label[:120])}</b></div>', unsafe_allow_html=True)
                        existing = next((o for o in st.session_state.hrrb_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(f"Set `{field}` to:", options=allowed, index=allowed.index(current_val) if current_val in allowed else 0, key=f"ov_val_{raw_node}_{raw_field}", horizontal=True)
                        reason = st.text_input("Reason (required):", value=existing.reason if existing else "", key=f"ov_reason_{raw_node}_{raw_field}", placeholder="Document clinical rationale...")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.hrrb_overrides = [o for o in st.session_state.hrrb_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.hrrb_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.hrrb_overrides = [o for o in st.session_state.hrrb_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.hrrb_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.hrrb_overrides:
                        st.markdown(f'<div class="override-card">🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code> set to <b>{html.escape(str(o.new_value))}</b><br><span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br><span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span></div>', unsafe_allow_html=True)

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S") if log.timestamp else "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs: st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
