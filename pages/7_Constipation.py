import os, sys
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
import io

from chronic_constipation_engine import (
    run_constipation_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Chronic Constipation", layout="wide")

# ── MARKDOWN HELPERS ────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def _pretty(s: str) -> str:
    if not s:
        return ""
    return s.replace("_", " ").title()

def build_cc_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Chronic Constipation Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Sex:** {_safe_text(patient_data.get('sex')).capitalize() or 'Not specified'}")
    lines.append(f"- **Age:** {_safe_text(patient_data.get('age'))}")
    lines.append(f"- **SBMs per week:** {_safe_text(patient_data.get('spontaneous_bowel_movements_per_week'))}")
    lines.append(f"- **Symptom Duration > 3 mo:** {_safe_text(patient_data.get('symptoms_duration_gt_3_months'))}")
    lines.append(f"- **Pain/Bloating Predominant:** {_safe_text(patient_data.get('predominant_pain_or_bloating'))}")
    lines.append(f"- **DRE Completed:** {_safe_text(patient_data.get('dre_done'))}")
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

st.title("Chronic Constipation Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "cc_overrides" not in st.session_state:
    st.session_state.cc_overrides = []

if "cc_has_run" not in st.session_state:
    st.session_state.cc_has_run = False

if "cc_notes" not in st.session_state:
    st.session_state.cc_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    
    st.markdown("**1. Demographics**")
    age = st.number_input("Age", min_value=1, max_value=120, value=50)
    sex = st.selectbox("Sex", ["male", "female", "unknown"])
    
    st.markdown("**2. Diagnostic Criteria (Rome IV)**")
    symptoms_duration_gt_3_months = st.checkbox("Symptoms active for ≥3 months, onset ≥6 months prior", value=True)
    sbms = st.number_input("Spontaneous bowel movements (SBMs) per week", min_value=0.0, step=0.5, value=2.0)
    hard_stool = st.checkbox("Hard or lumpy stool (Bristol 1-2) for >25% of defecations")
    straining = st.checkbox("Straining during >25% of defecations")
    incomplete_evac = st.checkbox("Sensation of incomplete evacuation for >25% of defecations")
    blockage = st.checkbox("Sensation of anorectal blockage for >25% of defecations")
    manual_maneuvers = st.checkbox("Manual maneuvers needed to facilitate >25% of defecations")

    st.markdown("**3. Medical History & IBS Screen**")
    predominant_pain_bloating = st.checkbox("Predominant symptoms of pain and/or bloating (Suggests IBS-C)")
    duration_trend = st.text_input("Duration and progression trend (Optional)")
    past_laxative_use = st.checkbox("Past use of laxatives or other agents documented")

    st.markdown("**4. Physical Examination**")
    abd_exam_done = st.checkbox("Abdominal examination completed")
    dre_done = st.checkbox("Digital anorectal examination (DRE) completed")
    dyssynergia_suspected = st.checkbox("Signs of defecatory dysfunction (e.g., failed balloon expulsion, tight sphincter)")

    st.markdown("**5. Alarm Features**")
    fam_hx_crc = st.checkbox("Family history (first-degree) of colorectal cancer")
    weight_loss = st.checkbox("Unintended weight loss (>5% over 6-12 months)")
    sudden_change_bowel = st.checkbox("Sudden or progressive change in bowel habits")
    visible_blood = st.checkbox("Visible blood in stool")
    mass_irregularity = st.checkbox("Suspicious mass or irregularity of anal canal / rectal mucosa")
    positive_fit = st.checkbox("Positive FIT (Fecal Immunochemical Test)")
    anemia_documented = st.checkbox("Iron deficiency anemia documented")

    st.markdown("**6. Baseline Investigations & Secondary Causes**")
    col1, col2 = st.columns(2)
    with col1:
        cbc_done = st.checkbox("CBC completed")
        tsh_done = st.checkbox("TSH completed")
        ca_done = st.checkbox("Calcium completed")
    with col2:
        fluid_fibre_optimized = st.checkbox("Fluid and fibre intake optimized")
        meds_reviewed = st.checkbox("Medications reviewed for constipating side effects")

    st.markdown("**7. Management & Treatment Response**")
    npt_effective = st.checkbox("Non-pharmacological therapy effective (Lifestyle, diet)")
    pharm_tried = st.checkbox("Pharmacological therapy tried (Osmotic/stimulant laxatives)")
    pharm_effective = st.checkbox("Pharmacological therapy effective")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.cc_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.cc_overrides = []
        if "cc_saved_output" in st.session_state:
            del st.session_state["cc_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.cc_has_run:
        patient_data = {
            "age": int(age) if age > 0 else None,
            "sex": sex if sex != "unknown" else None,
            "symptoms_duration_gt_3_months": symptoms_duration_gt_3_months or None,
            "spontaneous_bowel_movements_per_week": float(sbms) if sbms is not None else None,
            "hard_lumpy_stool_gt_25_percent": hard_stool or None,
            "straining_gt_25_percent": straining or None,
            "incomplete_evacuation_gt_25_percent": incomplete_evac or None,
            "anorectal_blockage_gt_25_percent": blockage or None,
            "manual_maneuvers_gt_25_percent": manual_maneuvers or None,
            "predominant_pain_or_bloating": predominant_pain_bloating or None,
            "duration_and_progression_documented": bool(duration_trend) or None,
            "past_laxative_use_documented": past_laxative_use or None,
            "abdominal_exam_done": abd_exam_done or None,
            "dre_done": dre_done or None,
            "dyssynergia_suspected": dyssynergia_suspected or None,
            "family_history_crc_first_degree": fam_hx_crc or None,
            "weight_loss_gt_5_percent": weight_loss or None,
            "sudden_change_in_bowel_habits": sudden_change_bowel or None,
            "visible_blood_in_stool": visible_blood or None,
            "suspicious_mass_or_irregularity": mass_irregularity or None,
            "positive_fit": positive_fit or None,
            "iron_deficiency_anemia_documented": anemia_documented or None,
            "fluid_and_fibre_optimized": fluid_fibre_optimized or None,
            "constipating_medications_reviewed": meds_reviewed or None,
            "cbc_completed": cbc_done or None,
            "tsh_completed": tsh_done or None,
            "calcium_completed": ca_done or None,
            "non_pharm_therapy_effective": npt_effective or None,
            "pharm_therapy_tried": pharm_tried or None,
            "pharm_therapy_effective": pharm_effective or None,
        }

        outputs, logs, applied_overrides = run_constipation_pathway(
            patient_data, overrides=st.session_state.cc_overrides
        )

        cc_criteria_failed = any(isinstance(o, Stop) and "criteria for Chronic Constipation are not met" in o.reason for o in outputs)
        is_ibsc = any(isinstance(o, Stop) and "IBS-C" in o.reason for o in outputs) or any(isinstance(o, Action) and o.code == "ROUTE_IBS_PATHWAY" for o in outputs)
        has_alarm = any(isinstance(o, Action) and o.code == "URGENT_REFER_ALARM" for o in outputs) or any(isinstance(o, Stop) and "Alarm features" in o.reason for o in outputs)
        dys_dysfunction = any(isinstance(o, Action) and o.code == "REFER_PELVIC_FLOOR_PT" for o in outputs)
        pathway_complete = any(isinstance(o, Action) and o.code == "FINAL_RECOMMENDATION" for o in outputs) or any(isinstance(o, Stop) and "Final recommendation" in o.reason for o in outputs)

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
        Y = { "start": 20, "d_crit": 100, "d_ibs": 210, "d_alarm": 320, "rect_base": 430, "d_dys": 540, "rect_mgmt": 650 }

        rect_node(CX-NW/2, Y["start"], NW, NH, nc(True), "1. Symptoms Review")
        vline(CX, Y["start"]+NH, Y["d_crit"], True)
        
        diamond_node(CX, Y["d_crit"]+DH/2, DW, DH, dc(True), "Rome IV Criteria", "Met?")
        
        exit_node(REXT, Y["d_crit"]+(DH-EH)/2, EW, EH, nc(cc_criteria_failed, exit_=True), "Low Risk", "Criteria Not Met")
        elbow_line(CX+DW/2, Y["d_crit"]+DH/2, REXT, Y["d_crit"]+(DH-EH)/2+EH/2, cc_criteria_failed, exit_=True, label="No")

        v_crit_met = not cc_criteria_failed
        vline(CX, Y["d_crit"]+DH, Y["d_ibs"], v_crit_met, label="Yes")
        
        diamond_node(CX, Y["d_ibs"]+DH/2, DW, DH, dc(v_crit_met), "Pain/Bloating", "Predominant?")
        
        exit_node(LEXT, Y["d_ibs"]+(DH-EH)/2, EW, EH, nc(is_ibsc, exit_=True), "IBS Pathway", "Route to IBS-C")
        elbow_line(CX-DW/2, Y["d_ibs"]+DH/2, LEXT+EW, Y["d_ibs"]+(DH-EH)/2+EH/2, is_ibsc, exit_=True, label="Yes")

        v_not_ibs = v_crit_met and not is_ibsc
        vline(CX, Y["d_ibs"]+DH, Y["d_alarm"], v_not_ibs, label="No")
        
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(v_not_ibs), "Alarm Features?", "Present?")
        
        exit_node(REXT, Y["d_alarm"]+(DH-EH)/2, EW, EH, nc(has_alarm, urgent=True), "URGENT", "Refer for Endoscopy")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT, Y["d_alarm"]+(DH-EH)/2+EH/2, has_alarm, urgent=True, label="Yes")

        v_no_alarm = v_not_ibs and not has_alarm
        vline(CX, Y["d_alarm"]+DH, Y["rect_base"], v_no_alarm, label="No")
        
        rect_node(CX-NW/2, Y["rect_base"], NW, NH, nc(v_no_alarm), "Base Labs & Sec. Causes", sub="Fluid/Fibre/Meds/CBC")

        vline(CX, Y["rect_base"]+NH, Y["d_dys"], v_no_alarm)

        diamond_node(CX, Y["d_dys"]+DH/2, DW, DH, dc(v_no_alarm), "Defecatory", "Dysfunction?")
        
        exit_node(LEXT, Y["d_dys"]+(DH-EH)/2, EW, EH, nc(dys_dysfunction, exit_=True), "Referral", "Pelvic Floor PT")
        elbow_line(CX-DW/2, Y["d_dys"]+DH/2, LEXT+EW, Y["d_dys"]+(DH-EH)/2+EH/2, dys_dysfunction, exit_=True, label="Yes")

        v_mgmt = v_no_alarm
        vline(CX, Y["d_dys"]+DH, Y["rect_mgmt"], v_mgmt, label="No")
        
        rect_node(CX-NW/2, Y["rect_mgmt"], NW, NH, nc(v_mgmt), "Management", sub="Pharm & Non-Pharm")

        ly = H - 30; lx = 20
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
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
            f'<span><b>Age:</b> {age}</span><br>'
            f'<span><b>SBMs per week:</b> {sbms}</span><br>'
            f'<span><b>Duration > 3 months:</b> {symptoms_duration_gt_3_months}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 & 3 — Diagnostic Criteria & IBS Screen",
                "icon": "🔍",
                "cls": "routine",
                "codes": {"CC_CRITERIA_MET", "CC_CRITERIA_NOT_MET", "ROUTE_IBS_PATHWAY", "IBSC_SCREEN_NEGATIVE"}
            },
            "step2": {
                "label": "Step 2 & 4 — History & Physical Exam",
                "icon": "📋",
                "cls": "info",
                "codes": {"RECORD_MEDICAL_HISTORY", "DRE_COMPLETED", "DRE_NOT_COMPLETED"}
            },
            "step3": {
                "label": "Step 5 — Alarm Features",
                "icon": "🚨",
                "cls": "urgent",
                "codes": {"URGENT_REFER_ALARM", "NO_ALARM_FEATURES_MET"}
            },
            "step4": {
                "label": "Step 6 & 7 — Secondary Causes & Investigations",
                "icon": "🩸",
                "cls": "warning",
                "codes": {"OPTIMIZE_FLUID_FIBRE", "REVIEW_MEDICATIONS", "ORDER_BASELINE_INVESTIGATIONS", "CBC_RECORDED", "TSH_RECORDED", "CALCIUM_RECORDED"}
            },
            "step5": {
                "label": "Step 8 — Defecatory Dysfunction",
                "icon": "🧍",
                "cls": "info",
                "codes": {"REFER_PELVIC_FLOOR_PT"}
            },
            "step6": {
                "label": "Step 9 — Pharmacological Management",
                "icon": "💊",
                "cls": "routine",
                "codes": {"NPT_EFFECTIVE", "PHARM_EFFECTIVE", "TRIAL_PHARM_THERAPY", "REFER_GI", "FINAL_RECOMMENDATION"}
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
                is_complete = "complete" in output.reason.lower() or "medical home" in output.reason.lower() or "final recommendation" in output.reason.lower()
                
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
        st.session_state.cc_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.cc_notes,
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
                "overrides": [{"node": o.target_node, "field": o.field, "new_value": o.new_value, "reason": o.reason, "created_at": o.created_at.isoformat()} for o in st.session_state.cc_overrides],
                "clinician_notes": st.session_state.cc_notes,
            },
        }

        if st.button("💾 Save this output", key="cc_save_output"):
            st.session_state.cc_saved_output = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        if "cc_saved_output" in st.session_state:
            md_text = build_cc_markdown(patient_data, outputs, st.session_state.cc_overrides, st.session_state.cc_notes)
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="chronic_constipation_summary.md",
                mime="text/markdown",
                key="cc_download_md",
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
                        existing = next((o for o in st.session_state.cc_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(f"Set `{field}` to:", options=allowed, index=allowed.index(current_val) if current_val in allowed else 0, key=f"ov_val_{raw_node}_{raw_field}", horizontal=True)
                        reason = st.text_input("Reason (required):", value=existing.reason if existing else "", key=f"ov_reason_{raw_node}_{raw_field}", placeholder="Document clinical rationale...")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.cc_overrides = [o for o in st.session_state.cc_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.cc_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.cc_overrides = [o for o in st.session_state.cc_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.cc_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.cc_overrides:
                        st.markdown(f'<div class="override-card">🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code> set to <b>{html.escape(str(o.new_value))}</b><br><span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br><span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span></div>', unsafe_allow_html=True)

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S") if log.timestamp else "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs: st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
