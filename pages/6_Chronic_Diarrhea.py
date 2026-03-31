import os
import sys
import html
import io
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from chronic_diarrhea_engine import (
    run_chronic_diarrhea_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Chronic Diarrhea", page_icon="🚽", layout="wide")

# ── MARKDOWN HELPERS ────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_cd_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Chronic Diarrhea Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / {str(patient_data.get('sex', 'N/A')).capitalize()}")
    lines.append(f"- **Stools per day:** {_safe_text(patient_data.get('loose_watery_stools_per_day')) or 'Not documented'}")
    lines.append(f"- **Duration (weeks):** {_safe_text(patient_data.get('symptom_duration_weeks')) or 'Not documented'}")
    lines.append(f"- **Fecal Calprotectin:** {_safe_text(patient_data.get('fecal_calprotectin_ug_g'))} µg/g")
    lines.append(f"- **Celiac Screen Positive:** {_safe_text(patient_data.get('celiac_screen_positive'))}")
    lines.append(f"- **Unsatisfactory Response:** {_safe_text(patient_data.get('unsatisfactory_response_to_treatment'))}")
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
                    for b in o.details.get("bullets", []):
                        lines.append(f"  - {_safe_text(b)}")
                    for n in o.details.get("notes", []):
                        lines.append(f"  - Note: {_safe_text(n)}")
                    for s in o.details.get("supported_by", []):
                        lines.append(f"  - Support: {_safe_text(s)}")
                    skip = {"bullets", "notes", "supported_by", "options"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(v)}")
                if isinstance(o.details.get("options"), list):
                     for opt in o.details.get("options"):
                         lines.append(f"  - Option: {_safe_text(opt)}")

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

st.title("🚽 Chronic Diarrhea Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "cd_overrides" not in st.session_state:
    st.session_state.cd_overrides = []

if "cd_has_run" not in st.session_state:
    st.session_state.cd_has_run = False

if "cd_notes" not in st.session_state:
    st.session_state.cd_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**Entry Criteria**")
    stools_per_day = st.number_input("Loose/watery stools per day", min_value=0, value=None, placeholder="e.g. 4")
    duration_weeks = st.number_input("Symptom duration (weeks)", min_value=0, value=None, placeholder="e.g. 6")

    st.markdown("**Alarm Features**")
    fh_ibd = st.checkbox("Family history IBD (first-degree)")
    fh_crc = st.checkbox("Family history Colorectal Cancer (first-degree)")
    onset_50 = st.checkbox("Symptom onset after age 50")
    nocturnal = st.checkbox("Nocturnal symptoms")
    incontinence = st.checkbox("Significant incontinence")
    visible_blood = st.checkbox("Visible blood in stool")
    ida = st.checkbox("Iron deficiency anemia present")
    weight_loss_pct = st.number_input("Unintended weight loss % (6-12 months)", min_value=0.0, value=0.0, step=1.0)

    st.markdown("**Baseline Investigations**")
    cbc_done = st.checkbox("CBC done", value=True)
    electrolytes_done = st.checkbox("Electrolytes done", value=True)
    ferritin_done = st.checkbox("Ferritin done", value=True)
    crp_done = st.checkbox("CRP done", value=True)
    celiac_done = st.checkbox("Celiac screen done", value=True)
    celiac_pos = st.checkbox("Celiac screen POSITIVE")
    c_diff_done = st.checkbox("C. difficile done", value=True)
    ova_parasites_done = st.checkbox("Ova and parasites done", value=True)
    fit_planned = st.checkbox("FIT ordered or planned", value=False)
    
    st.markdown("**Alternative Diagnoses & Context**")
    high_suspicion_ibd = st.selectbox("High clinical suspicion of IBD?", ["Unknown", "Yes", "No"])
    fcp_done = st.checkbox("Fecal Calprotectin done")
    fcp_ug_g = st.number_input("Fecal Calprotectin (µg/g)", min_value=0, value=None, placeholder="e.g. 80")
    
    pain_bloating = st.checkbox("Predominant pain or bloating (suspect IBS)")
    suspect_ibsd = st.checkbox("Suspected IBS-D")
    suspect_mc = st.checkbox("Suspect Microscopic Colitis")
    suspect_bad = st.checkbox("Suspect Bile Acid Diarrhea (BAD)")
    sibo_risk = st.checkbox("SIBO risk factors present")
    known_pancreatic = st.checkbox("Known pancreatic disease")

    st.markdown("**Secondary Causes**")
    med_review = st.checkbox("Medication review done", value=True)
    underlying_cond = st.checkbox("Underlying conditions optimized", value=True)
    hx_chole = st.checkbox("History of cholecystectomy")
    hx_bariatric = st.checkbox("History of bariatric surgery")
    hx_covid = st.checkbox("History of COVID-19")
    diet_review = st.checkbox("Dietary trigger review done", value=True)

    st.markdown("**Management Response**")
    unsat_resp_sel = st.selectbox("Unsatisfactory response to treatment?", ["Unknown", "Yes", "No"])
    advice_service = st.checkbox("Advice service considered (if unsatisfactory)")
    
    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.cd_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.cd_overrides = []
        if "cd_saved_output" in st.session_state:
            del st.session_state["cd_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.cd_has_run:
        
        unsat_map = {"Unknown": None, "Yes": True, "No": False}
        ibd_susp_map = {"Unknown": None, "Yes": True, "No": False}

        patient_data = {
            "age": age,
            "sex": sex,
            "loose_watery_stools_per_day": stools_per_day,
            "symptom_duration_weeks": duration_weeks,
            "family_history_ibd_first_degree": fh_ibd or None,
            "family_history_crc_first_degree": fh_crc or None,
            "symptom_onset_after_age_50": onset_50 or None,
            "nocturnal_symptoms": nocturnal or None,
            "significant_incontinence": incontinence or None,
            "visible_blood_in_stool": visible_blood or None,
            "iron_deficiency_anemia_present": ida or None,
            "unintended_weight_loss_percent_6_to_12_months": weight_loss_pct,
            "cbc_done": cbc_done,
            "electrolytes_done": electrolytes_done,
            "ferritin_done": ferritin_done,
            "crp_done": crp_done,
            "celiac_screen_done": celiac_done,
            "c_diff_done": c_diff_done,
            "ova_parasites_done": ova_parasites_done,
            "fit_ordered_or_planned": fit_planned,
            "celiac_screen_positive": celiac_pos,
            "high_suspicion_ibd": ibd_susp_map[high_suspicion_ibd],
            "fecal_calprotectin_done": fcp_done,
            "fecal_calprotectin_ug_g": fcp_ug_g,
            "predominant_pain_or_bloating": pain_bloating,
            "suspected_ibsd": suspect_ibsd,
            "suspect_microscopic_colitis": suspect_mc,
            "suspect_bad": suspect_bad,
            "sibo_risk_factor_present": sibo_risk,
            "known_pancreatic_disease": known_pancreatic,
            "medication_review_done": med_review,
            "underlying_conditions_reviewed": underlying_cond,
            "history_of_cholecystectomy": hx_chole,
            "history_of_bariatric_surgery": hx_bariatric,
            "history_of_covid19": hx_covid,
            "dietary_trigger_review_done": diet_review,
            "unsatisfactory_response_to_treatment": unsat_map[unsat_resp_sel],
            "advice_service_considered": advice_service
        }

        outputs, logs, applied_overrides = run_chronic_diarrhea_pathway(
            patient_data, overrides=st.session_state.cd_overrides
        )

        # Tracing flowchart states
        entry_met = any(isinstance(o, Action) and o.code == "CHRONIC_DIARRHEA_ENTRY_MET" for o in outputs)
        entry_fail = any(isinstance(o, Action) and o.code == "NOT_CHRONIC_DIARRHEA" for o in outputs)
        alarm_met = any(isinstance(o, Action) and o.code == "URGENT_ENDOSCOPY_REFERRAL" for o in outputs)
        refer_celiac = any(isinstance(o, Action) and o.code == "REFER_POSITIVE_CELIAC" for o in outputs)
        sec_causes_reviewed = any(isinstance(o, Action) and o.code == "SECONDARY_CAUSES_REVIEWED" for o in outputs) or any(isinstance(o, Action) and "REVIEW_" in o.code for o in outputs)
        route_ibs = any(isinstance(o, Action) and o.code == "ROUTE_IBS_PATHWAY" for o in outputs)
        refer_fcp = any(isinstance(o, Action) and o.code == "REFER_ELEVATED_FECAL_CALPROTECTIN" for o in outputs)
        refer_failed = any(isinstance(o, Action) and o.code == "REFER_FAILED_MANAGEMENT" for o in outputs)
        pathway_complete = any(isinstance(o, Action) and o.code == "CONTINUE_MEDICAL_HOME_CARE" for o in outputs)

        v1 = True
        v2 = entry_met
        v3 = v2 and not alarm_met
        v4 = v3 and not refer_celiac
        v5 = v4
        v6 = v5
        v7 = v6
        v8 = v7 and not route_ibs and not refer_fcp

        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if exit_: return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent: return "mr"
            if exit_: return "mo"
            return "mg"

        svg = []
        W, H = 700, 1050
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

        CX = 350; NW, NH = 180, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {
            "entry": 18, "alarm": 120, "baseline": 220, "celiac_fcp": 310,
            "secondary": 420, "gen_mgmt": 510, "pharm": 600,
            "alt_dx": 700, "mgmt_resp": 810, "complete": 910
        }

        # Node 1: Entry
        diamond_node(CX, Y["entry"]+DH/2, DW, DH, dc(v1), "1. Suspected CD", "Criteria Met?")
        exit_node(LEXT, Y["entry"]+(DH-EH)/2, EW, EH, nc(entry_fail, exit_=True), "No / Criteria Not Met", "Exit Pathway")
        elbow_line(CX-DW/2, Y["entry"]+DH/2, LEXT+EW, Y["entry"]+(DH-EH)/2+EH/2, entry_fail, exit_=True, label="No")

        vline(CX, Y["entry"]+DH, Y["alarm"], v2, label="Yes")

        # Node 2: Alarm
        diamond_node(CX, Y["alarm"]+DH/2, DW, DH, dc(v2), "2. Alarm", "Features?")
        exit_node(REXT, Y["alarm"]+(DH-EH)/2, EW, EH, nc(alarm_met, urgent=True), "⚠ Urgent Refer", "GI / Endoscopy")
        elbow_line(CX+DW/2, Y["alarm"]+DH/2, REXT, Y["alarm"]+(DH-EH)/2+EH/2, alarm_met, urgent=True, label="Yes")

        vline(CX, Y["alarm"]+DH, Y["baseline"], v3, label="No")

        # Node 3: Baseline Investigations
        rect_node(CX-NW/2, Y["baseline"], NW, NH, nc(v3), "3. Baseline Investigations", sub="Blood & Stool")
        vline(CX, Y["baseline"]+NH, Y["celiac_fcp"], v3)
        diamond_node(CX, Y["celiac_fcp"]+DH/2, DW, DH, dc(v3), "Celiac+ or", "High FCP?")
        exit_node(REXT, Y["celiac_fcp"]+(DH-EH)/2, EW, EH, nc(refer_celiac, urgent=True), "Refer", "Consultation")
        elbow_line(CX+DW/2, Y["celiac_fcp"]+DH/2, REXT, Y["celiac_fcp"]+(DH-EH)/2+EH/2, refer_celiac, urgent=True, label="Yes")

        vline(CX, Y["celiac_fcp"]+DH, Y["secondary"], v4, label="No")

        # Node 4: Secondary Causes
        rect_node(CX-NW/2, Y["secondary"], NW, NH, nc(v4), "4. Optimize Secondary", "Causes")
        vline(CX, Y["secondary"]+NH, Y["gen_mgmt"], v5)

        # Node 5: General Mgmt
        rect_node(CX-NW/2, Y["gen_mgmt"], NW, NH, nc(v5), "5. General Management")
        vline(CX, Y["gen_mgmt"]+NH, Y["pharm"], v6)

        # Node 6: Pharmacological
        rect_node(CX-NW/2, Y["pharm"], NW, NH, nc(v6), "6. Pharmacological", "Options")
        vline(CX, Y["pharm"]+NH, Y["alt_dx"], v7)

        # Node 7: Alternative Diagnoses
        diamond_node(CX, Y["alt_dx"]+DH/2, DW, DH, dc(v7), "7. Alternative Dx", "Suspect IBS / High FCP?")
        
        route_or_refer_fcp = route_ibs or refer_fcp
        exit_node(LEXT, Y["alt_dx"]+(DH-EH)/2, EW, EH, nc(route_ibs, exit_=True), "IBS Suspected", "→ IBS Pathway")
        elbow_line(CX-DW/2, Y["alt_dx"]+DH/2, LEXT+EW, Y["alt_dx"]+(DH-EH)/2+EH/2, route_ibs, exit_=True, label="Yes(IBS)")

        exit_node(REXT, Y["alt_dx"]+(DH-EH)/2, EW, EH, nc(refer_fcp, urgent=True), "Refer", "Consultation")
        elbow_line(CX+DW/2, Y["alt_dx"]+DH/2, REXT, Y["alt_dx"]+(DH-EH)/2+EH/2, refer_fcp, urgent=True, label="Yes(FCP)")

        vline(CX, Y["alt_dx"]+DH, Y["mgmt_resp"], v8, label="No")

        # Node 8: Management Response
        diamond_node(CX, Y["mgmt_resp"]+DH/2, DW, DH, dc(v8), "8. Mgmt Response", "Unsatisfactory?")
        
        exit_node(REXT, Y["mgmt_resp"]+(DH-EH)/2, EW, EH, nc(refer_failed, urgent=refer_failed, exit_=refer_failed), "Refer", "Consider Advice Service")
        elbow_line(CX+DW/2, Y["mgmt_resp"]+DH/2, REXT, Y["mgmt_resp"]+(DH-EH)/2+EH/2, refer_failed, urgent=refer_failed, exit_=refer_failed, label="Yes")

        v9 = v8 and pathway_complete
        vline(CX, Y["mgmt_resp"]+DH, Y["complete"], v9, label="No")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v9, exit_=True), "Continue Medical Home Care")

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
            height=1080, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        alarm_fields = [
            ("family_history_ibd_first_degree", "FHx IBD"),
            ("family_history_crc_first_degree", "FHx CRC"),
            ("symptom_onset_after_age_50", "Onset >50"),
            ("nocturnal_symptoms", "Nocturnal sx"),
            ("significant_incontinence", "Incontinence"),
            ("visible_blood_in_stool", "Visible blood"),
            ("iron_deficiency_anemia_present", "IDA")
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        if weight_loss_pct > 5:
            active_alarms.append(f"Weight loss ({weight_loss_pct}%)")
            
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"
        fcp_str = f"{fcp_ug_g} µg/g" if fcp_ug_g is not None else "Not done/recorded"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Stools/day & Duration:</b> {stools_per_day} | {duration_weeks} wks</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span><br>'
            f'<span><b>Fecal Calprotectin:</b> {fcp_str}</span><br>'
            f'<span><b>Unsatisfactory Response:</b> {unsat_resp_sel}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        def _detail_html(details) -> str:
            if not details:
                return ""
            items = ""
            if isinstance(details, dict):
                for bullet in details.get("bullets", []):
                    items += f"<li>{html.escape(str(bullet))}</li>"
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                for opt in details.get("options", []):
                    items += f"<li>🔹 {html.escape(str(opt))}</li>"
                skip = {"bullets", "supported_by", "options"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k)).replace('_', ' ').title()}:</b> {html.escape(str(v))}</li>"
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
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">'
                "🔒 Override available — reason required</p>"
                if a.override_options else ""
            )

            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{detail_html}{override_html}"
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
        st.session_state.cd_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.cd_notes,
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
                    for o in st.session_state.cd_overrides
                ],
                "clinician_notes": st.session_state.cd_notes,
            },
        }

        if st.button("💾 Save this output", key="cd_save_output"):
            st.session_state.cd_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "cd_saved_output" in st.session_state:
            md_text = build_cd_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.cd_overrides,
                notes=st.session_state.cd_notes,
            )

            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="chronic_diarrhea_summary.md",
                mime="text/markdown",
                key="cd_download_md",
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
                            (o for o in st.session_state.cd_overrides
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
                                    st.session_state.cd_overrides = [
                                        o for o in st.session_state.cd_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.cd_overrides.append(
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
                                st.session_state.cd_overrides = [
                                    o for o in st.session_state.cd_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.cd_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.cd_overrides:
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
