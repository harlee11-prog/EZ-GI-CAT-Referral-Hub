import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from chronic_constipation_engine import (
    run_constipation_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="Chronic Constipation", page_icon="\U0001f7e4", layout="wide")


def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_constipation_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Chronic Constipation Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'Unknown')} / {str(patient_data.get('sex', 'Unknown')).capitalize()}")
    lines.append(f"- **SBMs per week:** {_safe_text(patient_data.get('spontaneous_bowel_movements_per_week'))}")
    lines.append(f"- **Symptom months (last 6):** {_safe_text(patient_data.get('symptom_months_present_last_6'))}")
    lines.append(f"- **Predominant Pain/Bloating:** {_safe_text(patient_data.get('predominant_pain_or_bloating'))}")
    lines.append(f"- **Management months trialed:** {_safe_text(patient_data.get('management_months_trialed'))}")
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
                    skip = {"bullets", "notes", "supported_by", "regimen_key"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {k.replace('_', ' ').title()}: {_safe_text(v)}")
            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing fields: {', '.join(o.missing_fields)}")
    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(f"- **{ov.target_node}.{ov.field}** -> `{ov.new_value}` (Reason: {ov.reason})")
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    return "\n".join(lines)


st.markdown("""
<style>
.patient-context-box {
    background: linear-gradient(135deg, #1e3a5f 0%, #1a3050 100%);
    border: 1px solid #2d5a8e; border-radius: 10px;
    padding: 14px 18px; margin-bottom: 18px;
    font-size: 0.82rem; line-height: 1.7; color: #d0e4f7;
}
.patient-context-box strong { color: #7ec8e3; }
.section-header {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.13em;
    text-transform: uppercase; color: #64748b; margin: 20px 0 10px 0;
    padding-bottom: 4px; border-bottom: 1px solid #e2e8f0;
}
.step-card { border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; border-left: 4px solid; }
.step-card.green  { background: #052e16; border-color: #16a34a; }
.step-card.red    { background: #3b0a0a; border-color: #dc2626; }
.step-card.amber  { background: #3d1f00; border-color: #d97706; }
.step-card.blue   { background: #0a1f3b; border-color: #3b82f6; }
.step-card-title { font-size: 0.78rem; font-weight: 700; margin-bottom: 6px; }
.step-card.green  .step-card-title { color: #4ade80; }
.step-card.red    .step-card-title { color: #f87171; }
.step-card.amber  .step-card-title { color: #fbbf24; }
.step-card.blue   .step-card-title { color: #60a5fa; }
.step-card ul { margin: 0; padding-left: 18px; list-style-type: disc;
    font-size: 0.79rem; color: #cbd5e1; line-height: 1.6; }
.step-card ul li { margin-bottom: 2px; }
.override-tag {
    font-size: 0.68rem; background: #1e293b; border: 1px dashed #475569;
    border-radius: 6px; padding: 8px 12px; color: #94a3b8; margin-bottom: 8px; font-family: monospace;
}
.override-tag .ov-field { color: #f59e0b; }
.override-tag .ov-val   { color: #34d399; }
.override-tag .ov-time  { color: #64748b; font-size: 0.63rem; }
.pill-info { background:#1e3a5f; color:#7ec8e3; font-size:0.65rem; padding:2px 8px; border-radius:999px; }
.override-avail { font-size:0.64rem; color:#94a3b8; font-style:italic; margin-top:4px; display:block; }
</style>
""", unsafe_allow_html=True)

st.title("Chronic Constipation Pathway")
st.markdown("---")

if "cc_overrides" not in st.session_state:
    st.session_state.cc_overrides = []
if "cc_has_run" not in st.session_state:
    st.session_state.cc_has_run = False
if "cc_notes" not in st.session_state:
    st.session_state.cc_notes = ""

left, right = st.columns([1, 1.5])

with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])
    elderly_patient = age >= 65

    st.markdown("**Diagnostic Criteria**")
    months_present = st.number_input(
        "Months symptoms present in last 6 months", min_value=0, max_value=6, value=0,
        help="Criteria require symptoms present in at least 3 of the last 6 months",
    )
    sbm_per_week = st.number_input(
        "Spontaneous bowel movements per week", min_value=0, max_value=50, value=3,
        help="3 or fewer SBMs/week counts as a criterion",
    )

    st.markdown("**Symptom Frequencies** (% of defecations):")
    hard_stool = st.number_input("Hard/lumpy stool (Bristol 1-2) %", min_value=0, max_value=100, value=0, step=5)
    straining  = st.number_input("Straining %", min_value=0, max_value=100, value=0, step=5)
    incomplete = st.number_input("Incomplete evacuation %", min_value=0, max_value=100, value=0, step=5)
    blockage   = st.number_input("Anorectal blockage sensation %", min_value=0, max_value=100, value=0, step=5)
    manual     = st.number_input("Manual maneuvers needed %", min_value=0, max_value=100, value=0, step=5)

    st.markdown("**IBS-C Screen**")
    predominant_pain_sel = st.selectbox(
        "Are abdominal pain/bloating the predominant symptoms?", ["Unknown", "Yes", "No"],
        help="If Yes, patient should follow the IBS-C pathway instead",
    )
    pain_map = {"Unknown": None, "Yes": True, "No": False}

    st.markdown("**Medical History & Associated Symptoms**")
    symptom_trend = st.selectbox("Symptom duration trend", ["Stable", "Progressive/Worsening", "Fluctuating"])
    abd_pain   = st.checkbox("Abdominal pain present")
    bloating   = st.checkbox("Bloating present")
    distention = st.checkbox("Distention present")
    past_laxative = st.text_input("Past laxative use (types / duration)", placeholder="e.g. PEG 3350 x 3 months")

    st.markdown("**Defecatory Dysfunction Indicators**")
    traumatic_injury = st.checkbox("Traumatic perineal injury history")
    outlet_blockage  = st.checkbox("Sense of blockage at the outlet")
    wiggle           = st.checkbox("Needs to wiggle/rotate on toilet to pass stool")

    st.markdown("**Physical Examination**")
    abd_exam        = st.checkbox("Abdominal exam done", value=True)
    dre_exam        = st.checkbox("Digital anorectal exam done", value=True)
    suspicious_mass = st.checkbox("Suspicious anal canal mass or irregularity on exam")

    st.markdown("**Alarm Features**")
    fh_crc        = st.checkbox("Family hx of colorectal cancer (1st degree)")
    weight_loss   = st.number_input("Unintended weight loss % (6-12 months)", min_value=0.0, max_value=50.0, value=0.0, step=0.5, help="Greater than 5% triggers alarm feature")
    sudden_change = st.checkbox("Sudden or progressive change in bowel habits")
    visible_blood = st.checkbox("Visible blood in stool")
    ida           = st.checkbox("Iron deficiency anemia (IDA)")

    st.markdown("**Optimize Secondary Causes**")
    meds_reviewed       = st.checkbox("Medications/OTCs reviewed", value=True)
    conditions_reviewed = st.checkbox("Underlying medical conditions reviewed", value=True)
    diet_reviewed       = st.checkbox("Diet and fluid intake reviewed", value=True)
    bowel_reg_reviewed  = st.checkbox("Bowel regimen reviewed", value=True)

    with st.expander("Baseline Investigations (optional detail)"):
        cbc_done       = st.checkbox("CBC recent/available", value=True)
        glucose_done   = st.checkbox("Glucose done", value=True)
        cr_done        = st.checkbox("Creatinine done", value=True)
        ca_done        = st.checkbox("Calcium/Albumin done", value=True)
        tsh_done       = st.checkbox("TSH done", value=True)
        celiac_done    = st.checkbox("Celiac disease screen done", value=True)
        celiac_pos     = st.checkbox("Celiac screen is positive")
        abdo_xray_done = st.checkbox("Abdominal radiograph done (if elderly)", value=False, help="Useful in elderly for evaluating overflow constipation")

    st.markdown("**Therapy Response**")
    months_trialed = st.number_input("Months of multi-pronged management trialed", min_value=0, max_value=60, value=0, help="Suggest 3-6 months before considering referral")
    unsat_resp_sel = st.selectbox("Unsatisfactory response after 3-6 months?", ["Unknown", "Yes", "No"])
    unsat_map      = {"Unknown": None, "Yes": True, "No": False}
    advice_considered = st.checkbox("Advice service considered before referral", help="Alberta eReferral Advice Request or tele-advice line")

    run_clicked = st.button("\u25b6 Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.cc_has_run = True

    if st.button("\U0001f504 Clear Overrides", use_container_width=True):
        st.session_state.cc_overrides = []
        if "cc_saved_output" in st.session_state:
            del st.session_state["cc_saved_output"]
        st.rerun()

    override_panel = st.container()

with right:
    if not st.session_state.cc_has_run:
        st.info("Fill in patient details on the left, then click **Run Pathway**.")
    else:
        patient_data = {
            "age": age,
            "sex": sex,
            "elderly_patient": elderly_patient,
            "symptom_months_present_last_6": months_present,
            "spontaneous_bowel_movements_per_week": sbm_per_week,
            "hard_or_lumpy_stool_percent": hard_stool,
            "straining_percent": straining,
            "incomplete_evacuation_percent": incomplete,
            "anorectal_blockage_percent": blockage,
            "manual_maneuvers_percent": manual,
            "predominant_pain_or_bloating": pain_map[predominant_pain_sel],
            "symptom_duration_trend": symptom_trend,
            "abdominal_pain_present": abd_pain,
            "bloating_present": bloating,
            "distention_present": distention,
            "past_laxative_use": past_laxative or None,
            "traumatic_perineal_injury_history": traumatic_injury,
            "outlet_blockage_sensation": outlet_blockage,
            "needs_to_wiggle_or_rotate_on_toilet": wiggle,
            "abdominal_exam_done": abd_exam or None,
            "digital_anorectal_exam_done": dre_exam or None,
            "suspicious_anal_canal_mass_or_irregularity": suspicious_mass,
            "family_history_crc_first_degree": fh_crc,
            "weight_loss_percent_6_to_12_months": weight_loss,
            "sudden_or_progressive_change_in_bowel_habits": sudden_change,
            "visible_blood_in_stool": visible_blood,
            "iron_deficiency_anemia_present": ida,
            "medication_history_reviewed": meds_reviewed,
            "secondary_causes_medical_conditions_reviewed": conditions_reviewed,
            "diet_fluid_reviewed": diet_reviewed,
            "bowel_regimen_reviewed": bowel_reg_reviewed,
            "cbc_recent_available": cbc_done,
            "glucose_done": glucose_done,
            "creatinine_done": cr_done,
            "calcium_albumin_done": ca_done,
            "tsh_done": tsh_done,
            "celiac_screen_done": celiac_done,
            "celiac_screen_positive": celiac_pos,
            "abdominal_radiograph_done": abdo_xray_done,
            "management_months_trialed": months_trialed,
            "unsatisfactory_response_after_3_to_6_months": unsat_map[unsat_resp_sel],
            "advice_service_considered": advice_considered,
        }

        outputs, logs, applied_overrides = run_constipation_pathway(
            patient_data,
            overrides=st.session_state.cc_overrides,
        )

        crit_met      = any(isinstance(o, Action) and o.code == "CONSTIPATION_CRITERIA_MET" for o in outputs)
        crit_not_met  = any(isinstance(o, Stop) and "not met" in o.reason.lower() for o in outputs)
        ibsc_route    = any(
            isinstance(o, Stop) and getattr(o, "actions", None) and
            any(getattr(a, "code", "") == "ROUTE_IBSC" for a in o.actions)
            for o in outputs
        )
        alarm_present = any(isinstance(o, Stop) and "alarm feature" in o.reason.lower() for o in outputs)
        celiac_refer  = any(isinstance(o, Stop) and "celiac" in o.reason.lower() for o in outputs)
        unsat_refer   = any(isinstance(o, Stop) and "unsatisfactory response" in o.reason.lower() for o in outputs)
        pathway_done  = any(
            isinstance(o, Stop) and getattr(o, "actions", None) and
            any(getattr(a, "code", "") == "FINAL_RECOMMENDATION" for a in o.actions)
            for o in outputs
        )
        history_vis   = crit_met and not ibsc_route
        exam_vis      = history_vis
        secondary_vis = exam_vis and not alarm_present
        baseline_vis  = secondary_vis
        mgmt_vis      = baseline_vis and not celiac_refer

        C_MAIN    = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT  = "#dc2626"
        C_EXIT    = "#d97706"
        C_TEXT    = "#ffffff"
        C_BG      = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis:  return C_UNVISIT
            if urgent:   return C_URGENT
            if exit_:    return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False):
            if not vis:  return "ma"
            if urgent:   return "mr"
            if exit_:    return "mo"
            return "mg"

        def rect_node(svg, x, y, w, h, color, label, sublabel="", rx=8):
            svg.append(
                '<rect x="' + str(x) + '" y="' + str(y) + '" width="' + str(w) +
                '" height="' + str(h) + '" rx="' + str(rx) + '" fill="' + color + '" opacity="0.92"/>'
            )
            ty = y + h // 2 - (6 if sublabel else 0)
            cx = x + w // 2
            svg.append(
                '<text x="' + str(cx) + '" y="' + str(ty) +
                '" text-anchor="middle" dominant-baseline="middle" fill="' + C_TEXT +
                '" font-family="system-ui,sans-serif" font-size="11" font-weight="600">' +
                html.escape(label) + '</text>'
            )
            if sublabel:
                svg.append(
                    '<text x="' + str(cx) + '" y="' + str(y + h // 2 + 10) +
                    '" text-anchor="middle" dominant-baseline="middle" fill="#cbd5e1"'
                    ' font-family="system-ui,sans-serif" font-size="9">' +
                    html.escape(sublabel) + '</text>'
                )

        def diamond_node(svg, cx, cy, hw, hh, color, label, sublabel=""):
            pts = str(cx) + "," + str(cy - hh) + " " + str(cx + hw) + "," + str(cy) + " " + str(cx) + "," + str(cy + hh) + " " + str(cx - hw) + "," + str(cy)
            svg.append('<polygon points="' + pts + '" fill="' + color + '" opacity="0.92"/>')
            ty = cy - (7 if sublabel else 0)
            svg.append(
                '<text x="' + str(cx) + '" y="' + str(ty) +
                '" text-anchor="middle" dominant-baseline="middle" fill="' + C_TEXT +
                '" font-family="system-ui,sans-serif" font-size="11" font-weight="600">' +
                html.escape(label) + '</text>'
            )
            if sublabel:
                svg.append(
                    '<text x="' + str(cx) + '" y="' + str(cy + 9) +
                    '" text-anchor="middle" dominant-baseline="middle" fill="#cbd5e1"'
                    ' font-family="system-ui,sans-serif" font-size="9">' +
                    html.escape(sublabel) + '</text>'
                )

        def arrow(svg, x1, y1, x2, y2, color, m_id):
            svg.append(
                '<line x1="' + str(x1) + '" y1="' + str(y1) + '" x2="' + str(x2) + '" y2="' + str(y2) +
                '" stroke="' + color + '" stroke-width="2" marker-end="url(#' + m_id + ')"/>')

        def lbl(svg, x, y, text, color="#94a3b8"):
            svg.append(
                '<text x="' + str(x) + '" y="' + str(y) +
                '" text-anchor="middle" font-family="system-ui,sans-serif" font-size="10" fill="' +
                color + '">' + html.escape(text) + '</text>'
            )

        W, H = 700, 1020
        CX = 350
        svg = []

        defs = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + str(W) + ' ' + str(H) +
            '" style="background:' + C_BG + ';border-radius:12px;width:100%;max-width:' + str(W) + 'px">'
            '<defs>'
            '<marker id="mg" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L8,3 z" fill="' + C_MAIN + '"/></marker>'
            '<marker id="mr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L8,3 z" fill="' + C_URGENT + '"/></marker>'
            '<marker id="mo" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L8,3 z" fill="' + C_EXIT + '"/></marker>'
            '<marker id="ma" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L8,3 z" fill="' + C_UNVISIT + '"/></marker>'
            '</defs>'
        )
        svg.append(defs)

        rect_node(svg, 215, 18, 270, 46, nc(True), "1. Diagnostic Criteria", "2+ symptoms, 3+ of last 6 months")
        arrow(svg, CX, 64, CX, 103, nc(True), mid(True))
        diamond_node(svg, CX, 130, 106, 30, dc(True), "Criteria Met?")
        arrow(svg, 244, 130, 130, 130, nc(crit_not_met, exit_=crit_not_met), mid(crit_not_met, exit_=crit_not_met))
        rect_node(svg, 28, 112, 104, 36, nc(crit_not_met, exit_=crit_not_met), "Not Met", "Reassess diagnosis")
        lbl(svg, 190, 124, "No")
        arrow(svg, CX, 160, CX, 197, nc(crit_met), mid(crit_met))
        lbl(svg, CX + 16, 182, "Yes", "#4ade80" if crit_met else "#94a3b8")
        rect_node(svg, 215, 197, 270, 46, nc(history_vis), "2. Medical History", "Duration, triggers, prior therapy")
        arrow(svg, CX, 243, CX, 282, nc(history_vis), mid(history_vis))
        diamond_node(svg, CX, 312, 118, 32, dc(history_vis), "3. IBS-C?", "Predominant pain/bloating?")
        arrow(svg, 468, 312, 578, 312, nc(ibsc_route, exit_=ibsc_route), mid(ibsc_route, exit_=ibsc_route))
        rect_node(svg, 578, 294, 110, 36, nc(ibsc_route, exit_=ibsc_route), "Follow IBS-C", "Pathway")
        lbl(svg, 526, 305, "Yes", "#fbbf24" if ibsc_route else "#94a3b8")
        arrow(svg, CX, 344, CX, 382, nc(history_vis and not ibsc_route), mid(history_vis and not ibsc_route))
        lbl(svg, CX + 16, 367, "No", "#4ade80" if (history_vis and not ibsc_route) else "#94a3b8")
        rect_node(svg, 215, 382, 270, 46, nc(exam_vis), "4. Physical Examination", "Abdominal + digital anorectal")
        arrow(svg, CX, 428, CX, 466, nc(exam_vis), mid(exam_vis))
        diamond_node(svg, CX, 496, 118, 32, dc(exam_vis), "5. Alarm Features?", "CRC hx, blood, wt loss, IDA")
        arrow(svg, 468, 496, 578, 496, nc(alarm_present, urgent=alarm_present), mid(alarm_present, urgent=alarm_present))
        rect_node(svg, 578, 478, 110, 36, nc(alarm_present, urgent=alarm_present), "9. Refer /", "Consult + Endoscopy")
        lbl(svg, 526, 489, "Yes", "#f87171" if alarm_present else "#94a3b8")
        arrow(svg, CX, 528, CX, 566, nc(secondary_vis), mid(secondary_vis))
        lbl(svg, CX + 16, 551, "No", "#4ade80" if secondary_vis else "#94a3b8")
        rect_node(svg, 215, 566, 270, 46, nc(secondary_vis), "6. Optimize Secondary Causes", "Meds, conditions, diet, activity")
        arrow(svg, CX, 612, CX, 650, nc(secondary_vis), mid(secondary_vis))
        rect_node(svg, 215, 650, 270, 46, nc(baseline_vis), "7. Baseline Investigations", "CBC, glucose, Cr, TSH, celiac")
        arrow(svg, 485, 673, 578, 673, nc(celiac_refer, urgent=celiac_refer), mid(celiac_refer, urgent=celiac_refer))
        rect_node(svg, 578, 655, 110, 36, nc(celiac_refer, urgent=celiac_refer), "+Celiac Screen", "Refer Specialist")
        arrow(svg, CX, 696, CX, 734, nc(mgmt_vis), mid(mgmt_vis))
        rect_node(svg, 215, 734, 270, 46, nc(mgmt_vis), "8. Management (3-6 months)", "Fibre, fluids, laxatives, PA")
        arrow(svg, CX, 780, CX, 818, nc(mgmt_vis), mid(mgmt_vis))
        diamond_node(svg, CX, 848, 120, 32, dc(mgmt_vis), "Unsatisfactory?", "After 3+ months therapy")
        arrow(svg, 470, 848, 578, 848, nc(unsat_refer, urgent=unsat_refer), mid(unsat_refer, urgent=unsat_refer))
        rect_node(svg, 578, 830, 110, 36, nc(unsat_refer, urgent=unsat_refer), "Consider Referral", "Advice + Refer")
        lbl(svg, 528, 841, "Yes", "#f87171" if unsat_refer else "#94a3b8")
        arrow(svg, CX, 880, CX, 916, nc(pathway_done), mid(pathway_done))
        lbl(svg, CX + 16, 902, "No", "#4ade80" if pathway_done else "#94a3b8")
        rect_node(svg, 215, 916, 270, 46, nc(pathway_done, exit_=pathway_done), "Patient Medical Home", "Pathway complete - continue care")
        svg.append("</svg>")

        st.subheader("\U0001f5fa\ufe0f Pathway Followed")
        components.html("".join(svg), height=1040, scrolling=False)

        st.markdown('<div class="section-header">Patient Context</div>', unsafe_allow_html=True)
        pain_display  = "Yes" if pain_map[predominant_pain_sel] is True else ("No" if pain_map[predominant_pain_sel] is False else "Unknown")
        alarm_display = "Present" if alarm_present else ("None identified" if secondary_vis else "-")
        st.markdown(
            '<div class="patient-context-box">' +
            '<strong>Age / Sex:</strong> ' + str(age) + ' / ' + sex.capitalize() +
            ' &nbsp;|&nbsp; <strong>SBMs/week:</strong> ' + str(sbm_per_week) +
            ' &nbsp;|&nbsp; <strong>Symptom months (last 6):</strong> ' + str(months_present) + '<br>' +
            '<strong>Predominant Pain/Bloating:</strong> ' + pain_display +
            ' &nbsp;|&nbsp; <strong>Alarm Features:</strong> ' + alarm_display + '<br>' +
            '<strong>Mgmt Months Trialed:</strong> ' + str(months_trialed) +
            ' &nbsp;|&nbsp; <strong>Unsatisfactory Response:</strong> ' + unsat_resp_sel +
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-header">Recommended Actions</div>', unsafe_allow_html=True)
        override_candidates = []

        for o in outputs:
            if isinstance(o, Action):
                if getattr(o, "override_options", None):
                    override_candidates.append(o)
                color = "green"
                icon  = "\u2705"
                if getattr(o, "urgency", None) == "urgent":
                    color = "red"
                    icon  = "\U0001f534"
                bullets = []
                if isinstance(o.details, dict):
                    bullets += [str(b) for b in o.details.get("bullets", [])]
                    bullets += [str(s) for s in o.details.get("supported_by", [])]
                    skip = {"bullets", "notes", "supported_by", "regimen_key", "display"}
                    for k, v in o.details.items():
                        if k in skip or v in (None, False, "", []):
                            continue
                        if isinstance(v, list):
                            for item in v:
                                if item:
                                    bullets.append(k.replace("_", " ").title() + ": " + _safe_text(item))
                        elif isinstance(v, bool) and v:
                            bullets.append(k.replace("_", " ").title())
                        elif not isinstance(v, bool):
                            bullets.append(k.replace("_", " ").title() + ": " + _safe_text(v))
                bullet_html = "".join("<li>" + html.escape(str(b)) + "</li>" for b in bullets[:6]) if bullets else ""
                override_pill = '<span class="override-avail">\U0001f512 Override available - reason required</span>' if o.override_options else ""
                st.markdown(
                    '<div class="step-card ' + color + '">' +
                    '<div class="step-card-title">' + icon + " " + html.escape(_safe_text(o.label)) + '</div>' +
                    ("<ul>" + bullet_html + "</ul>" if bullet_html else "") +
                    override_pill +
                    '</div>',
                    unsafe_allow_html=True,
                )

            elif isinstance(o, DataRequest):
                st.markdown(
                    '<div class="step-card amber">' +
                    '<div class="step-card-title">\u23f3 Data Required to Proceed</div>' +
                    "<ul><li>" + html.escape(_safe_text(o.message)) + "</li>" +
                    "<li>Missing: " + html.escape(", ".join(o.missing_fields)) + "</li></ul>" +
                    '</div>',
                    unsafe_allow_html=True,
                )

            elif isinstance(o, Stop):
                is_alarm   = "alarm" in o.reason.lower() or "refer" in o.reason.lower()
                is_ibsc    = "ibs-c" in o.reason.lower() or "predominant pain" in o.reason.lower()
                is_celiac  = "celiac" in o.reason.lower()
                is_medical = "medical home" in o.reason.lower() or "complete" in o.reason.lower()
                is_crit    = "not met" in o.reason.lower()
                color_s = ("red"   if is_alarm or is_celiac else
                           "amber" if is_ibsc or is_crit    else
                           "green" if is_medical             else "amber")
                icon_s  = ("\U0001f6a8" if is_alarm else "\U0001f535" if is_ibsc else "\u2705" if is_medical else "\u26a0\ufe0f")
                action_items = ""
                if getattr(o, "actions", None):
                    for a in o.actions:
                        if getattr(a, "override_options", None):
                            override_candidates.append(a)
                        action_items += "<li>" + html.escape(_safe_text(a.label)) + "</li>"
                        if getattr(a, "override_options", None):
                            action_items += '<li><span class="override-avail">\U0001f512 Override available</span></li>'
                st.markdown(
                    '<div class="step-card ' + color_s + '">' +
                    '<div class="step-card-title">' + icon_s + " " + html.escape(_safe_text(o.reason)) + '</div>' +
                    ("<ul>" + action_items + "</ul>" if action_items else "") +
                    '</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div class="section-header">Clinician Notes</div>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.cc_notes = st.text_area(
            "Notes to attach to the saved output:", value=st.session_state.cc_notes, height=180,
        )

        def _serialize_output(o):
            if isinstance(o, Action):
                return {"type": "action", "code": o.code, "label": o.label, "urgency": o.urgency}
            if isinstance(o, Stop):
                return {"type": "stop", "reason": o.reason}
            if isinstance(o, DataRequest):
                return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
            return {"type": "other", "repr": repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [
                    {"node": o.target_node, "field": o.field, "new_value": o.new_value,
                     "reason": o.reason, "created_at": o.created_at.isoformat()}
                    for o in st.session_state.cc_overrides
                ],
                "clinician_notes": st.session_state.cc_notes,
            },
        }

        if st.button("\U0001f4be Save this output", key="cc_save_output"):
            st.session_state.cc_saved_output = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        if "cc_saved_output" in st.session_state:
            md_text = build_constipation_markdown(
                patient_data=patient_data, outputs=outputs,
                overrides=st.session_state.cc_overrides, notes=st.session_state.cc_notes,
            )
            st.download_button(
                label="\u2b07\ufe0f Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="chronic_constipation_summary.md",
                mime="text/markdown",
                key="cc_download_md",
            )

        with st.expander("\U0001f4cb Decision Audit Log"):
            if logs:
                for entry in logs:
                    st.markdown(f"**Node:** `{entry.node}` | **Decision:** `{entry.decision}`")
                    if entry.used_inputs:
                        for k, v in entry.used_inputs.items():
                            st.markdown(f"  - `{k}`: `{v}`")
                    st.markdown("---")
            else:
                st.info("No decision log entries yet.")

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<div class="section-header">Clinician Overrides</div>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )
                for a in override_candidates:
                    opt       = a.override_options
                    raw_node  = opt["node"]
                    raw_field = opt["field"]
                    node      = _pretty(raw_node)
                    field     = _pretty(raw_field)
                    allowed   = opt.get("allowed", [True, False])
                    with st.expander("\u2699\ufe0f Override: **" + node + "** -> `" + field + "`"):
                        preview = a.label[:120] + ("..." if len(a.label) > 120 else "")
                        st.markdown(
                            '<span class="pill-info">Current engine value</span>' +
                            " &nbsp; `" + html.escape(_safe_text(a.code)) + "` - " + html.escape(preview),
                            unsafe_allow_html=True,
                        )
                        new_val = st.selectbox(
                            "Override value for " + field + ":",
                            options=allowed,
                            key="cc_ovr_val_" + raw_node + "_" + raw_field,
                        )
                        reason = st.text_input(
                            "Documented reason (required):",
                            key="cc_ovr_reason_" + raw_node + "_" + raw_field,
                            placeholder="e.g. Clinical exam contradicts engine flag",
                        )
                        if st.button("Apply override for " + field, key="cc_ovr_apply_" + raw_node + "_" + raw_field):
                            if not reason.strip():
                                st.error("A reason is required to apply an override.")
                            else:
                                st.session_state.cc_overrides = [
                                    o for o in st.session_state.cc_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                old_val = getattr(a, "details", {}).get(raw_field, None)
                                st.session_state.cc_overrides.append(
                                    Override(
                                        target_node=raw_node,
                                        field=raw_field,
                                        old_value=old_val,
                                        new_value=new_val,
                                        reason=reason.strip(),
                                    )
                                )
                                st.rerun()

                st.markdown('<div class="section-header">Active Overrides</div>', unsafe_allow_html=True)
                if st.session_state.cc_overrides:
                    for o in st.session_state.cc_overrides:
                        st.markdown(
                            '<div class="override-tag">\U0001f527 <span class="ov-field">' +
                            html.escape(_pretty(o.target_node)) + '</span> -> <code class="ov-field">' +
                            html.escape(_pretty(o.field)) + '</code> set to <span class="ov-val">' +
                            html.escape(str(o.new_value)) + '</span><br>Reason: ' +
                            html.escape(o.reason) + '<br><span class="ov-time">Applied: ' +
                            o.created_at.strftime("%H:%M:%S") + '</span></div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("No active overrides.")
