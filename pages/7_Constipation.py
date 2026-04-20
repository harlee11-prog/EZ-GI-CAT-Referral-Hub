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

st.set_page_config(page_title="Chronic Constipation", page_icon="🟤", layout="wide")

# ── MARKDOWN HELPERS ────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def _pretty(s: str) -> str:
    if not s:
        return ""
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
    lines.append(f"- **Symptom onset ≥6 months ago:** {_safe_text(patient_data.get('symptom_onset_6_months_or_more_ago'))}")
    lines.append(f"- **Predominant Pain/Bloating:** {_safe_text(patient_data.get('predominant_pain_or_bloating'))}")
    lines.append(f"- **Loose stools rarely without laxatives:** {_safe_text(patient_data.get('loose_stools_rarely_without_laxatives'))}")
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
                    skip = {"bullets", "notes", "supported_by", "regimen_key", "display"}
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
    text-transform: uppercase;
}
.action-card {
    border-radius: 10px; padding: 14px 18px;
    margin-bottom: 12px; font-size: 13.5px; line-height: 1.6;
}
.action-card.urgent      { background:#3b0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.action-card.semi_urgent { background:#3b2a0a; border-left:5px solid #f97316; color:#fed7aa; }
.action-card.routine     { background:#052e16; border-left:5px solid #22c55e; color:#bbf7d0; }
.action-card.info        { background:#0c1a2e; border-left:5px solid #3b82f6; color:#bfdbfe; }
.action-card.warning     { background:#2d1a00; border-left:5px solid #f59e0b; color:#fde68a; }
.action-card.stop        { background:#2d0a0a; border-left:5px solid #ef4444; color:#fecaca; }
.badge {
    display:inline-block; font-size:11px; font-weight:bold;
    padding:2px 8px; border-radius:20px; margin-right:6px;
    text-transform:uppercase; letter-spacing:0.5px;
}
.badge.urgent      { background:#ef4444; color:#fff; }
.badge.semi_urgent { background:#f97316; color:#fff; }
.badge.routine     { background:#22c55e; color:#fff; }
.badge.info        { background:#3b82f6; color:#fff; }
.badge.warning     { background:#f59e0b; color:#000; }
.badge.stop        { background:#ef4444; color:#fff; }
.override-card {
    background:#1a1a2e; border:1px dashed #6366f1;
    border-radius:8px; padding:10px 14px; margin-top:8px;
    font-size:13px; color:#c7d2fe;
}
.rome-criteria-box {
    background: #0f2027; border: 1px solid #1e4d6b; border-radius: 8px;
    padding: 10px 14px; margin: 8px 0 14px 0; font-size: 0.78rem; color: #94a3b8;
}
.rome-criteria-box .rome-met { color: #4ade80; font-weight: 700; }
.rome-criteria-box .rome-unmet { color: #f87171; }
.rome-criteria-box .rome-partial { color: #fbbf24; }
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
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])
    elderly_patient = age >= 65

    # ── ROME IV DIAGNOSTIC CRITERIA ──────────────────────────────────────────
    st.markdown("**Rome IV Diagnostic Criteria**")
    st.caption(
        "Functional constipation requires ≥2 of the 6 symptoms below, "
        "present for ≥3 of the last 6 months, with symptom onset ≥6 months ago."
    )

    symptom_onset_6m = st.checkbox(
        "Symptom onset ≥6 months ago",
        value=False,
        help="Rome IV requires that symptoms began at least 6 months before the current assessment, "
             "even if the 3-month active criteria window is met.",
    )

    months_present = st.number_input(
        "Months symptoms present in last 6 months",
        min_value=0, max_value=6, value=0,
        help="Rome IV requires symptoms present in at least 3 of the last 6 months.",
    )

    st.markdown("**Criterion 1 — Stool Frequency**")
    sbm_per_week = st.number_input(
        "Spontaneous bowel movements (SBMs) per week",
        min_value=0, max_value=50, value=3,
        help="Criterion met if <3 SBMs/week (i.e., 0, 1, or 2 SBMs/week).",
    )
    sbm_criterion = sbm_per_week < 3
    if sbm_per_week < 3:
        st.caption(f"✅ <3 SBMs/week — criterion met ({sbm_per_week}/week)")
    else:
        st.caption(f"❌ ≥3 SBMs/week — criterion not met ({sbm_per_week}/week)")

    st.markdown("**Criteria 2–6 — Symptom Frequency (% of defecations)**")
    st.caption("Each criterion is met when the symptom occurs in >25% of defecations.")

    hard_stool = st.number_input("Hard/lumpy stool (Bristol 1–2) %", min_value=0, max_value=100, value=0, step=5)
    straining = st.number_input("Straining %", min_value=0, max_value=100, value=0, step=5)
    incomplete = st.number_input("Sensation of incomplete evacuation %", min_value=0, max_value=100, value=0, step=5)
    blockage = st.number_input("Sensation of anorectal blockage %", min_value=0, max_value=100, value=0, step=5)
    manual = st.number_input("Manual maneuvers needed %", min_value=0, max_value=100, value=0, step=5)

    # Compute how many of the 6 criteria are met (live preview)
    criteria_flags = {
        "< 3 SBMs/week": sbm_per_week < 3,
        "Hard/lumpy stool >25%": hard_stool > 25,
        "Straining >25%": straining > 25,
        "Incomplete evacuation >25%": incomplete > 25,
        "Anorectal blockage >25%": blockage > 25,
        "Manual maneuvers >25%": manual > 25,
    }
    criteria_met_count = sum(criteria_flags.values())

    # Live Rome IV mini-scorecard
    scorecard_lines = []
    for label, met in criteria_flags.items():
        icon = "✅" if met else "❌"
        scorecard_lines.append(f"{icon} {label}")
    criteria_color = "rome-met" if criteria_met_count >= 2 else ("rome-partial" if criteria_met_count == 1 else "rome-unmet")
    timing_ok = symptom_onset_6m and (months_present >= 3)
    timing_color = "rome-met" if timing_ok else "rome-partial"
    scorecard_html = (
        '<div class="rome-criteria-box">'
        f'<span class="{criteria_color}"><b>Symptoms met: {criteria_met_count}/6</b></span> '
        f'(need ≥2)<br>'
        f'<span class="{timing_color}">Duration: {months_present}/6 months active '
        f'{"✅" if months_present >= 3 else "❌"} | '
        f'Onset ≥6 months ago: {"✅" if symptom_onset_6m else "❌"}</span><br>'
        + "<br>".join(scorecard_lines)
        + "</div>"
    )
    st.markdown(scorecard_html, unsafe_allow_html=True)

    # Additional Rome IV exclusion criteria
    st.markdown("**Rome IV Exclusion Checks**")

    loose_stools_rarely = st.selectbox(
        "Loose stools rarely present without laxatives?",
        ["Unknown", "Yes", "No"],
        help="Rome IV requires that loose stools are rarely present without laxative use.",
    )
    loose_map = {"Unknown": None, "Yes": True, "No": False}

    st.markdown("**IBS-C Screen**")
    st.caption("IBS-C (Rome IV): Recurrent abdominal pain ≥1 day/week in last 3 months...")
    predominant_pain_sel = st.selectbox(
        "Are abdominal pain/bloating the predominant symptoms?",
        ["Unknown", "Yes", "No"],
        help="If predominant pain/bloating → follow IBS-C pathway.",
    )
    pain_map = {"Unknown": None, "Yes": True, "No": False}

    ibsc_pain_defecation = None
    ibsc_change_frequency = None
    ibsc_change_form = None
    if predominant_pain_sel == "Unknown":
        st.caption("If pain status is uncertain, screen with the IBS-C Rome IV sub-criteria below:")
        ibsc_pain_defecation = st.checkbox("Pain related to defecation")
        ibsc_change_frequency = st.checkbox("Change in stool frequency associated with pain")
        ibsc_change_form = st.checkbox("Change in stool form (Bristol) associated with pain")
        ibsc_sub_count = sum([ibsc_pain_defecation, ibsc_change_frequency, ibsc_change_form])
        if ibsc_sub_count >= 2:
            st.warning(f"⚠️ {ibsc_sub_count}/3 IBS-C sub-criteria met — consider IBS-C pathway.")

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
    weight_loss   = st.number_input("Unintended weight loss % (6–12 months)", min_value=0.0, max_value=50.0, value=0.0, step=0.5)
    sudden_change = st.checkbox("Sudden or progressive change in bowel habits")
    visible_blood = st.checkbox("Visible blood in stool")
    ida           = st.checkbox("Iron deficiency anemia (IDA)")
    tenesmus      = st.checkbox("Tenesmus")
    rectal_pain   = st.checkbox("Rectal pain (without alternative etiology)")

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
        abdo_xray_done = st.checkbox("Abdominal radiograph done (if elderly)", value=False)

    st.markdown("**Therapy Response**")
    months_trialed = st.number_input("Months of multi-pronged management trialed", min_value=0, max_value=60, value=0)
    unsat_resp_sel = st.selectbox("Unsatisfactory response after 3–6 months?", ["Unknown", "Yes", "No"])
    unsat_map      = {"Unknown": None, "Yes": True, "No": False}
    advice_considered = st.checkbox("Advice service considered before referral")

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
    if not st.session_state.cc_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age,
            "sex": sex,
            "elderly_patient": elderly_patient,
            "symptom_onset_6_months_or_more_ago": symptom_onset_6m,
            "symptom_months_present_last_6": months_present,
            "spontaneous_bowel_movements_per_week": sbm_per_week,
            "hard_or_lumpy_stool_percent": hard_stool,
            "straining_percent": straining,
            "incomplete_evacuation_percent": incomplete,
            "anorectal_blockage_percent": blockage,
            "manual_maneuvers_percent": manual,
            "loose_stools_rarely_without_laxatives": loose_map[loose_stools_rarely],
            "predominant_pain_or_bloating": pain_map[predominant_pain_sel],
            "ibsc_pain_related_to_defecation": ibsc_pain_defecation,
            "ibsc_change_in_stool_frequency": ibsc_change_frequency,
            "ibsc_change_in_stool_form": ibsc_change_form,
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
            "tenesmus_present": tenesmus,
            "rectal_pain_without_alternative_etiology": rectal_pain,
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

        # ── Setup Flags for the SVG ─────────────────────────────────────────
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

        # ── SVG FLOWCHART ───────────────────────────────────────────────────
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
        W, H = 700, 940
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

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 180, 50; DW, DH = 180, 58; EW, EH = 130, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = { "start": 20, "d_crit": 100, "hx": 210, "d_ibs": 320, "alarm": 430, "base": 540, "mgmt": 650, "unsat": 760, "done": 850 }

        rect_node(CX-NW/2, Y["start"], NW, NH, nc(True), "1. Diagnostic Criteria")
        vline(CX, Y["start"]+NH, Y["d_crit"], True)
        
        diamond_node(CX, Y["d_crit"]+DH/2, DW, DH, dc(True), "Rome IV Criteria", "Met?")
        exit_node(REXT, Y["d_crit"]+(DH-EH)/2, EW, EH, nc(crit_not_met, exit_=True), "Low Risk", "Criteria Not Met")
        elbow_line(CX+DW/2, Y["d_crit"]+DH/2, REXT, Y["d_crit"]+(DH-EH)/2+EH/2, crit_not_met, exit_=True, label="No")

        vline(CX, Y["d_crit"]+DH, Y["hx"], crit_met, label="Yes")
        rect_node(CX-NW/2, Y["hx"], NW, NH, nc(crit_met), "2. Medical History & Exam")
        vline(CX, Y["hx"]+NH, Y["d_ibs"], crit_met)

        diamond_node(CX, Y["d_ibs"]+DH/2, DW, DH, dc(crit_met), "3. IBS-C Predominant?", "Pain/Bloating?")
        exit_node(LEXT, Y["d_ibs"]+(DH-EH)/2, EW, EH, nc(ibsc_route, exit_=True), "IBS Pathway", "Route to IBS-C")
        elbow_line(CX-DW/2, Y["d_ibs"]+DH/2, LEXT+EW, Y["d_ibs"]+(DH-EH)/2+EH/2, ibsc_route, exit_=True, label="Yes")

        vline(CX, Y["d_ibs"]+DH, Y["alarm"], history_vis, label="No")
        diamond_node(CX, Y["alarm"]+DH/2, DW, DH, dc(history_vis), "4. Alarm Features?", "CRC hx, blood, wt loss")
        exit_node(REXT, Y["alarm"]+(DH-EH)/2, EW, EH, nc(alarm_present, urgent=True), "URGENT", "Refer for Endoscopy")
        elbow_line(CX+DW/2, Y["alarm"]+DH/2, REXT, Y["alarm"]+(DH-EH)/2+EH/2, alarm_present, urgent=True, label="Yes")

        vline(CX, Y["alarm"]+DH, Y["base"], secondary_vis, label="No")
        rect_node(CX-NW/2, Y["base"], NW, NH, nc(secondary_vis), "5. Baseline Labs & Sec. Causes")
        vline(CX, Y["base"]+NH, Y["mgmt"], secondary_vis)

        rect_node(CX-NW/2, Y["mgmt"], NW, NH, nc(mgmt_vis), "6. Management", sub="Therapy Trial")
        vline(CX, Y["mgmt"]+NH, Y["unsat"], mgmt_vis)

        diamond_node(CX, Y["unsat"]+DH/2, DW, DH, dc(mgmt_vis), "Unsatisfactory?", "After 3+ months")
        exit_node(REXT, Y["unsat"]+(DH-EH)/2, EW, EH, nc(unsat_refer, urgent=True), "Consider Referral", "Advice + Refer")
        elbow_line(CX+DW/2, Y["unsat"]+DH/2, REXT, Y["unsat"]+(DH-EH)/2+EH/2, unsat_refer, urgent=True, label="Yes")

        vline(CX, Y["unsat"]+DH, Y["done"], pathway_done, label="No")
        rect_node(CX-NW/2, Y["done"], NW, NH, nc(pathway_done, exit_=True), "Patient Medical Home")

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
            height=960, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        pain_display = "Yes" if pain_map[predominant_pain_sel] is True else ("No" if pain_map[predominant_pain_sel] is False else "Unknown")
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>SBMs per week:</b> {sbm_per_week}</span><br>'
            f'<span><b>Rome IV Criteria Met:</b> {criteria_met_count}/6</span><br>'
            f'<span><b>Predominant Pain/Bloating:</b> {pain_display}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Group Actions ───────────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 & 2 — Diagnostic Criteria",
                "icon": "🔍",
                "cls": "routine",
                "codes": {"CONSTIPATION_CRITERIA_MET", "CONSTIPATION_CRITERIA_NOT_MET"}
            },
            "step2": {
                "label": "Step 3 — IBS Screen",
                "icon": "📋",
                "cls": "info",
                "codes": {"IBSC_SCREEN_NEGATIVE", "ROUTE_IBSC"}
            },
            "step3": {
                "label": "Step 4 & 5 — Exam & Alarm Features",
                "icon": "🚨",
                "cls": "urgent",
                "codes": {"RECORD_MEDICAL_HISTORY", "DRE_COMPLETED", "DRE_NOT_COMPLETED", "URGENT_REFER_ALARM", "NO_ALARM_FEATURES_MET"}
            },
            "step4": {
                "label": "Step 6 — Secondary Causes & Baseline",
                "icon": "🩸",
                "cls": "warning",
                "codes": {"OPTIMIZE_FLUID_FIBRE", "REVIEW_MEDICATIONS", "ORDER_BASELINE_INVESTIGATIONS", "CBC_RECORDED", "TSH_RECORDED", "CALCIUM_RECORDED"}
            },
            "step5": {
                "label": "Step 7 — Management & Response",
                "icon": "💊",
                "cls": "routine",
                "codes": {"REFER_PELVIC_FLOOR_PT", "NPT_EFFECTIVE", "PHARM_EFFECTIVE", "TRIAL_PHARM_THERAPY", "REFER_GI", "FINAL_RECOMMENDATION"}
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

            border_colors = {"routine": "#22c55e", "info": "#3b82f6", "urgent": "#ef4444", "warning": "#f59e0b"}
            bg_colors = {"routine": "#052e16", "info": "#0c1a2e", "urgent": "#3b0a0a", "warning": "#2d1a00"}
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
                    skip = {"bullets", "notes", "supported_by", "regimen_key", "display"}
                    for dk, dv in a.details.items():
                        if dk in skip: continue
                        if dv not in (None, False, "", []):
                            if isinstance(dv, list):
                                for i in dv: sub_items.append(html.escape(str(i)))
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
                is_emergent = getattr(output, "urgency", None) == "urgent" or "alarm" in output.reason.lower()
                is_complete = "medical home" in output.reason.lower() or "final recommendation" in output.reason.lower()
                
                if is_emergent:
                    bg, border, icon, tcol = "#3b0a0a", "#ef4444", "🚨", "#fecaca"
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
            md_text = build_constipation_markdown(patient_data, outputs, st.session_state.cc_overrides, st.session_state.cc_notes)
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
