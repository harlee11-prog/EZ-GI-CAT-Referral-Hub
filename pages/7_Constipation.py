import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from chronic_constipation_engine import (
    run_constipation_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Chronic Constipation", layout="wide")

# ── MARKDOWN HELPERS ─────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_constipation_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Chronic Constipation Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'Unknown')} / {str(patient_data.get('sex', 'Unknown')).capitalize()}")
    lines.append(f"- **SBMs per week:** {_safe_text(patient_data.get('spontaneous_bowel_movements_per_week'))}")
    lines.append(f"- **Symptoms duration (months of last 6):** {_safe_text(patient_data.get('symptom_months_present_last_6'))}")
    lines.append(f"- **Predominant Pain/Bloating:** {_safe_text(patient_data.get('predominant_pain_or_bloating'))}")
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

    st.markdown("**Diagnostic Criteria**")
    months_present = st.number_input("Months symptoms present in last 6 months", 0, 6, 6)
    sbm_per_week = st.number_input("Spontaneous bowel movements per week", 0, 50, 2)
    
    st.markdown("Symptom Frequencies (% of defecations):")
    hard_stool = st.slider("Hard or lumpy stool (Bristol 1-2)", 0, 100, 30)
    straining = st.slider("Straining during defecation", 0, 100, 30)
    incomplete = st.slider("Sensation of incomplete evacuation", 0, 100, 30)
    blockage = st.slider("Sensation of anorectal blockage", 0, 100, 0)
    manual = st.slider("Manual maneuvers needed", 0, 100, 0)

    st.markdown("**Medical History & Associated Symptoms**")
    predominant_pain = st.selectbox("Are abdominal pain/bloating the predominant symptoms?", ["Unknown", "Yes", "No"])
    pain_map = {"Unknown": None, "Yes": True, "No": False}
    
    symptom_trend = st.selectbox("Symptom duration trend", ["Stable", "Progressive/Worsening", "Fluctuating"])
    abd_pain = st.checkbox("Abdominal pain present")
    bloating = st.checkbox("Bloating present")
    distention = st.checkbox("Distention present")
    past_laxative = st.text_input("Past laxative use (types/duration)")

    st.markdown("**Defecatory Dysfunction Indicators**")
    traumatic_injury = st.checkbox("Traumatic perineal injury history")
    outlet_blockage = st.checkbox("Sense of blockage at the outlet")
    wiggle = st.checkbox("Needs to wiggle/rotate on toilet")

    st.markdown("**Physical Examination**")
    abd_exam = st.checkbox("Abdominal exam done", value=True)
    dre_exam = st.checkbox("Digital anorectal exam done", value=True)
    suspicious_mass = st.checkbox("Suspicious anal canal mass or irregularity on exam")

    st.markdown("**Alarm Features**")
    fh_crc = st.checkbox("Family hx of colorectal cancer (1st degree)")
    weight_loss = st.number_input("Unintended weight loss % (6-12 months)", 0.0, 50.0, 0.0)
    sudden_change = st.checkbox("Sudden or progressive change in bowel habits")
    visible_blood = st.checkbox("Visible blood in stool")
    ida = st.checkbox("Iron deficiency anemia (IDA)")

    st.markdown("**Management & Investigations**")
    meds_reviewed = st.checkbox("Medications/OTCs reviewed", value=True)
    conditions_reviewed = st.checkbox("Underlying medical conditions reviewed", value=True)
    diet_reviewed = st.checkbox("Diet and fluid intake reviewed", value=True)
    bowel_reg_reviewed = st.checkbox("Bowel regimen reviewed", value=True)
    
    cbc_done = st.checkbox("CBC recent/available", value=True)
    glucose_done = st.checkbox("Glucose done", value=True)
    cr_done = st.checkbox("Creatinine done", value=True)
    ca_done = st.checkbox("Calcium/Albumin done", value=True)
    tsh_done = st.checkbox("TSH done", value=True)
    celiac_done = st.checkbox("Celiac disease screen done", value=True)
    celiac_pos = st.checkbox("Celiac screen is positive")
    abdo_xray_done = st.checkbox("Abdominal radiograph done (if elderly)", value=False)

    st.markdown("**Therapy Response**")
    months_trialed = st.number_input("Months of multi-pronged management trialed", 0, 60, 0)
    unsat_resp = st.selectbox("Unsatisfactory response after 3-6 months?", ["Unknown", "Yes", "No"])
    unsat_map = {"Unknown": None, "Yes": True, "No": False}
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
    if st.session_state.cc_has_run:
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
            "predominant_pain_or_bloating": pain_map[predominant_pain],
            "symptom_duration_trend": symptom_trend,
            "abdominal_pain_present": abd_pain,
            "bloating_present": bloating,
            "distention_present": distention,
            "past_laxative_use": past_laxative,
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
            "unsatisfactory_response_after_3_to_6_months": unsat_map[unsat_resp],
            "advice_service_considered": advice_considered,
        }

        outputs, logs, applied_overrides = run_constipation_pathway(
            patient_data, overrides=st.session_state.cc_overrides
        )

        crit_met = any(isinstance(o, Action) and o.code == "CONSTIPATION_CRITERIA_MET" for o in outputs)
        ibsc_route = any(isinstance(o, Stop) and o.actions and o.actions[0].code == "ROUTE_IBSC" for o in outputs)
        alarm_present = any(isinstance(o, Stop) and "Alarm feature(s) identified" in o.reason for o in outputs)
        refer_celiac = any(isinstance(o, Stop) and "celiac" in o.reason.lower() for o in outputs)
        refer_manage = any(isinstance(o, Stop) and "Unsatisfactory response after management" in o.reason for o in outputs)
        pathway_complete = any(isinstance(o, Stop) and o.actions and o.actions[0].code == "FINAL_RECOMMENDATION" for o in outputs)

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
        W, H = 700, 850
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
        LEXT = 40; REXT = W - 40 - EW
        Y = {
            "crit": 20, "ibsc": 120, "hx": 220, "alarm": 320, 
            "sec": 420, "manage": 520, "complete": 620
        }

        # 1. Criteria
        diamond_node(CX, Y["crit"]+DH/2, DW, DH, dc(True), "1. Diagnostic Criteria", "Met?")
        exit_node(LEXT, Y["crit"]+(DH-EH)/2, EW, EH, nc(not crit_met, exit_=True), "Criteria Not Met", "Reassess")
        elbow_line(CX-DW/2, Y["crit"]+DH/2, LEXT+EW, Y["crit"]+(DH-EH)/2+EH/2, not crit_met, exit_=True, label="No")

        # 2. IBS-C
        v2 = crit_met
        vline(CX, Y["crit"]+DH, Y["ibsc"], v2, label="Yes")
        diamond_node(CX, Y["ibsc"]+DH/2, DW, DH, dc(v2), "3. Is it IBS-C?", "Predominant Pain/Bloating?")
        
        exit_node(REXT, Y["ibsc"]+(DH-EH)/2, EW, EH, nc(ibsc_route, exit_=True), "Follow IBS Pathway", "")
        elbow_line(CX+DW/2, Y["ibsc"]+DH/2, REXT, Y["ibsc"]+(DH-EH)/2+EH/2, ibsc_route, exit_=True, label="Yes")

        # 3. History & Physical
        v3 = v2 and not ibsc_route
        vline(CX, Y["ibsc"]+DH, Y["hx"], v3, label="No")
        rect_node(CX-NW/2, Y["hx"], NW, NH, nc(v3), "2 & 4. Medical History", "& Physical Exam")

        # 4. Alarm Features
        v4 = v3
        vline(CX, Y["hx"]+NH, Y["alarm"], v4)
        diamond_node(CX, Y["alarm"]+DH/2, DW, DH, dc(v4), "5. Alarm Features", "Present?")
        
        exit_node(REXT, Y["alarm"]+(DH-EH)/2, EW, EH, nc(alarm_present, urgent=True), "9. Refer Urgent", "Consult / Endoscopy")
        elbow_line(CX+DW/2, Y["alarm"]+DH/2, REXT, Y["alarm"]+(DH-EH)/2+EH/2, alarm_present, urgent=True, label="Yes")

        # 5. Secondary Causes & Labs
        v5 = v4 and not alarm_present
        vline(CX, Y["alarm"]+DH, Y["sec"], v5, label="No")
        rect_node(CX-NW/2, Y["sec"], NW, NH, nc(v5), "6 & 7. Optimize Secondary", "& Baseline Labs")
        
        exit_node(LEXT, Y["sec"]+(NH-EH)/2, EW, EH, nc(refer_celiac, urgent=True), "Refer", "Positive Celiac Screen")
        elbow_line(CX-NW/2, Y["sec"]+NH/2, LEXT+EW, Y["sec"]+(NH-EH)/2+EH/2, refer_celiac, urgent=True, label="Pos")

        # 6. Management
        v6 = v5 and not refer_celiac
        vline(CX, Y["sec"]+NH, Y["manage"], v6)
        diamond_node(CX, Y["manage"]+DH/2, DW, DH, dc(v6), "8. Management", "Unsatisfactory Response?")

        exit_node(REXT, Y["manage"]+(DH-EH)/2, EW, EH, nc(refer_manage, urgent=True), "9. Refer", "Consider Advice Service")
        elbow_line(CX+DW/2, Y["manage"]+DH/2, REXT, Y["manage"]+(DH-EH)/2+EH/2, refer_manage, urgent=True, label="Yes")

        # 7. Complete
        v7 = v6 and not refer_manage and pathway_complete
        vline(CX, Y["manage"]+DH, Y["complete"], v7, label="No")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v7, exit_=v7), "Pathway Complete", "Maintain Patient Medical Home")

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
            height=880, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        pain_str = "Yes" if pain_map[predominant_pain] else "No"
        alarm_fields = [
            ("family_history_crc_first_degree", "Family hx CRC"),
            ("sudden_or_progressive_change_in_bowel_habits", "Sudden bowel change"),
            ("visible_blood_in_stool", "Visible blood"),
            ("suspicious_anal_canal_mass_or_irregularity", "Anal mass"),
            ("iron_deficiency_anemia_present", "IDA"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        if weight_loss > 5.0:
            active_alarms.append(f"Weight loss ({weight_loss}%)")
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Constipation Criteria Met:</b> {"Yes" if crit_met else "No/Unknown"} &nbsp;|&nbsp; <b>IBS-C Predominant:</b> {pain_str}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        def _detail_html(details) -> str:
            if not details: return ""
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
                    if k in skip: continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k)).replace('_', ' ').title()}:</b> {html.escape(str(v))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls

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
        st.session_state.cc_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.cc_notes,
            height=180,
        )

        def _serialize_output(o):
            if isinstance(o, Action):
                return {"type": "action", "code": o.code, "label": o.label, "urgency": o.urgency}
            if isinstance(o, Stop):
                return {"type": "stop", "reason": o.reason, "urgency": getattr(o, "urgency", None)}
            if isinstance(o, DataRequest):
                return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
            return {"type": "other", "repr": repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [
                    {
                        "node": o.target_node, "field": o.field, 
                        "new_value": o.new_value, "reason": o.reason, 
                        "created_at": o.created_at.isoformat()
                    }
                    for o in st.session_state.cc_overrides
                ],
                "clinician_notes": st.session_state.cc_notes,
            },
        }

        if st.button("💾 Save this output", key="cc_save_output"):
            st.session_state.cc_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "cc_saved_output" in st.session_state:
            md_text = build_constipation_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.cc_overrides,
                notes=st.session_state.cc_notes,
            )

            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="chronic_constipation_summary.md",
                mime="text/markdown",
                key="cc_download_md",
            )

        def _pretty(s: str) -> str:
            return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption("Override engine decisions where clinical judgement differs. A documented reason is required.")

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
                            (o for o in st.session_state.cc_overrides
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
                                    st.session_state.cc_overrides = [
                                        o for o in st.session_state.cc_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.cc_overrides.append(
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
                                st.session_state.cc_overrides = [
                                    o for o in st.session_state.cc_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.cc_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.cc_overrides:
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
