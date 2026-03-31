import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Import from the Dyspepsia engine
from dyspepsia_engine import (
    run_dyspepsia_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Dyspepsia Pathway", page_icon="🩺", layout="wide")

# ── MARKDOWN HELPER ──────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_dyspepsia_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Dyspepsia Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age')} / {str(patient_data.get('sex')).capitalize()}")
    lines.append(f"- **Symptom Duration:** {_safe_text(patient_data.get('symptom_duration_months'))} months")
    
    alarms = [k for k in [
        "actively_bleeding_now", "family_history_upper_gi_cancer_first_degree",
        "symptom_onset_after_age_60", "unintended_weight_loss", "black_stool_or_blood_in_vomit",
        "dysphagia", "persistent_vomiting", "iron_deficiency_anemia_present"
    ] if patient_data.get(k)]
    
    lines.append(f"- **Alarm Features Present:** {'Yes' if alarms else 'No'}")
    lines.append(f"- **H. pylori Test Done:** {_safe_text(patient_data.get('h_pylori_test_done'))}")
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

                    skip = {"bullets", "notes", "supported_by", "rome_iv_feature_count", "rome_iv_support_dyspepsia"}
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
.action-card.advisory { background:#301e04; border-left:5px solid #fbbf24; color:#fde68a; }
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

st.title("🩺 Dyspepsia Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "dys_overrides" not in st.session_state:
    st.session_state.dys_overrides = []

if "dys_has_run" not in st.session_state:
    st.session_state.dys_has_run = False

if "dys_notes" not in st.session_state:
    st.session_state.dys_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    colA, colB = st.columns(2)
    with colA:
        age = st.number_input("Age", 1, 120, 50)
    with colB:
        sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Suspected Dyspepsia Symptoms**")
    dur = st.number_input("Symptom duration (months)", 0, 240, 2)
    onset = st.number_input("Symptom onset (months ago)", 0, 240, 6)
    
    epi_pain = st.checkbox("Predominant epigastric pain")
    epi_disc = st.checkbox("Predominant epigastric discomfort")
    bloating = st.checkbox("Predominant upper abdominal bloating")
    
    st.markdown("*Rome IV Supportive Features (Optional)*")
    postprandial = st.checkbox("Postprandial fullness")
    early_satiety = st.checkbox("Early satiety")
    epi_burning = st.checkbox("Epigastric burning")

    st.markdown("**2. GERD Screen**")
    heartburn = st.checkbox("Predominant heartburn")
    regurg = st.checkbox("Predominant regurgitation")

    st.markdown("**3. Alarm Features**")
    active_bleed = st.checkbox("Actively bleeding now (EMERGENT)")
    fh_cancer = st.checkbox("Family history upper GI cancer (1st degree)")
    onset_60 = st.checkbox("Symptom onset after age 60")
    weight_loss = st.checkbox("Unintended weight loss >5%")
    black_stool = st.checkbox("Black stool or blood in vomit")
    dysphagia = st.checkbox("Progressive dysphagia")
    vomiting = st.checkbox("Persistent vomiting")
    ida = st.checkbox("Iron deficiency anemia present")

    st.markdown("**4. Medication & Lifestyle Review**")
    med_rev = st.checkbox("Medication review completed")
    life_rev = st.checkbox("Lifestyle review completed")
    diet_rev = st.checkbox("Diet trigger review completed")
    symp_imp_rev = st.selectbox("Symptoms improved after review?", ["Unknown", "Yes", "No"])
    symp_imp_map = {"Unknown": None, "Yes": True, "No": False}

    st.markdown("**5. Baseline Investigations**")
    cbc_stat = st.selectbox("CBC Done?", ["Unknown", "Yes", "No"])
    cbc_abn = st.checkbox("CBC Abnormal") if cbc_stat == "Yes" else False
    
    hp_stat = st.selectbox("H. pylori Test Done?", ["Unknown", "Yes", "No"])
    hp_res = st.selectbox("H. pylori Result", ["Unknown", "Positive", "Negative"]) if hp_stat == "Yes" else "Unknown"
    
    ferritin = st.checkbox("Ferritin done")
    ttg = st.checkbox("TTG IgA done")
    ttg_pos = st.checkbox("TTG IgA Positive") if ttg else False
    
    hep_susp = st.checkbox("Suspect hepatobiliary/pancreatic process")
    hep_done = st.checkbox("Hepatobiliary/pancreatic tests done") if hep_susp else False
    hep_abn = st.checkbox("Hepatobiliary workup abnormal") if hep_done else False
    
    other_diag = st.checkbox("Other diagnosis found during baseline")

    st.markdown("**7. Pharmacologic Therapy**")
    ppi_qd = st.selectbox("PPI once daily trial done?", ["Unknown", "Yes", "No"])
    ppi_qd_resp = st.selectbox("PPI once daily response adequate?", ["Unknown", "Yes", "No"]) if ppi_qd == "Yes" else "Unknown"
    
    ppi_bid = st.selectbox("PPI twice daily trial done?", ["Unknown", "Yes", "No"])
    ppi_bid_resp = st.selectbox("PPI twice daily response adequate?", ["Unknown", "Yes", "No"]) if ppi_bid == "Yes" else "Unknown"

    st.markdown("**8. Domperidone Eligibility (if PPI fails)**")
    qtc = st.number_input("ECG QTc (ms)", 300, 600, 420)
    fh_scd = st.checkbox("Family history sudden cardiac death")
    cardiac_hx = st.checkbox("Personal cardiac history")
    qt_meds = st.checkbox("QT-prolonging medications present")

    st.markdown("**9. Maintenance / Management**")
    ppi_res = st.selectbox("Symptoms resolved after PPI?", ["Unknown", "Yes", "No"])
    depresc = st.selectbox("Symptoms return after deprescribing?", ["Unknown", "Yes", "No"]) if ppi_res == "Yes" else "Unknown"
    
    unsat = st.selectbox("Unsatisfactory response to management?", ["Unknown", "Yes", "No"])
    advice = st.checkbox("Advice service considered") if unsat == "Yes" else False

    bool_map = {"Unknown": None, "Yes": True, "No": False}

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.dys_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.dys_overrides = []
        if "dys_saved_output" in st.session_state:
            del st.session_state["dys_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.dys_has_run:
        patient_data = {
            "age": age,
            "sex": sex,
            "symptom_duration_months": dur,
            "symptom_onset_months_ago": onset,
            "predominant_epigastric_pain": epi_pain,
            "predominant_epigastric_discomfort": epi_disc,
            "predominant_upper_abdominal_bloating": bloating,
            "postprandial_fullness": postprandial,
            "early_satiety": early_satiety,
            "epigastric_pain": epi_pain or epi_burning, 
            "epigastric_burning": epi_burning,
            "predominant_heartburn": heartburn,
            "predominant_regurgitation": regurg,
            "actively_bleeding_now": active_bleed,
            "family_history_upper_gi_cancer_first_degree": fh_cancer,
            "symptom_onset_after_age_60": onset_60,
            "unintended_weight_loss": weight_loss,
            "black_stool_or_blood_in_vomit": black_stool,
            "dysphagia": dysphagia,
            "persistent_vomiting": vomiting,
            "iron_deficiency_anemia_present": ida,
            "medication_review_done": med_rev,
            "lifestyle_review_done": life_rev,
            "diet_trigger_review_done": diet_rev,
            "symptoms_improved_after_med_lifestyle_review": bool_map[symp_imp_rev],
            "cbc_done": bool_map[cbc_stat],
            "cbc_abnormal": cbc_abn,
            "h_pylori_test_done": bool_map[hp_stat],
            "h_pylori_result_positive": bool_map[hp_res] if bool_map[hp_stat] else None,
            "ferritin_done": ferritin,
            "ttg_iga_done": ttg,
            "ttg_iga_positive": ttg_pos,
            "suspect_hepatobiliary_pancreatic_process": hep_susp,
            "hepatobiliary_pancreatic_tests_done": hep_done,
            "hepatobiliary_pancreatic_workup_abnormal": hep_abn,
            "other_diagnosis_found": other_diag,
            "ppi_once_daily_trial_done": bool_map[ppi_qd],
            "ppi_once_daily_response_adequate": bool_map[ppi_qd_resp],
            "ppi_bid_trial_done": bool_map[ppi_bid],
            "ppi_bid_response_adequate": bool_map[ppi_bid_resp],
            "ecg_qtc_ms": qtc,
            "family_history_sudden_cardiac_death": fh_scd,
            "personal_cardiac_history": cardiac_hx,
            "qt_prolonging_medications_present": qt_meds,
            "symptoms_resolved_after_ppi": bool_map[ppi_res],
            "symptoms_return_after_deprescribing": bool_map[depresc],
            "unsatisfactory_response_to_management": bool_map[unsat],
            "advice_service_considered": advice
        }

        outputs, logs, applied_overrides = run_dyspepsia_pathway(
            patient_data, overrides=st.session_state.dys_overrides
        )

        # Map logs to determine SVG traversal
        visited_nodes = {log.node: log.decision for log in logs}
        
        v_suspected = "Suspected_Dyspepsia" in visited_nodes
        v_gerd = "GERD_Screen" in visited_nodes
        v_alarm = "Alarm_Features" in visited_nodes
        v_med = "Medication_Lifestyle_Review" in visited_nodes
        v_base = "Baseline_Investigations" in visited_nodes
        v_hp = "H_Pylori_Test_And_Treat" in visited_nodes
        v_pharm = "Pharmacologic_Therapy" in visited_nodes
        v_resp = "Management_Response" in visited_nodes
        
        exit_not_dyspepsia = visited_nodes.get("Suspected_Dyspepsia") == "ENTRY_CRITERIA_NOT_MET"
        exit_gerd = visited_nodes.get("GERD_Screen") == "ROUTE_GERD"
        exit_alarm = visited_nodes.get("Alarm_Features") in ["ACTIVE_BLEEDING", "ALARM_FEATURES_PRESENT"]
        exit_med = visited_nodes.get("Medication_Lifestyle_Review") == "IMPROVED_AFTER_REVIEW"
        exit_base = visited_nodes.get("Baseline_Investigations") == "OTHER_DIAGNOSIS"
        exit_hp = visited_nodes.get("H_Pylori_Test_And_Treat") == "H_PYLORI_POSITIVE"
        exit_refer = visited_nodes.get("Management_Response") in ["FAILED_MANAGEMENT_REFER", "FAILED_MANAGEMENT_ADVICE_FIRST"]

        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"; C_SUCCESS = "#22c55e"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False, success=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if exit_: return C_EXIT
            if success: return C_SUCCESS
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

        CX = 350; NW, NH = 180, 50; DW, DH = 190, 58; EW, EH = 150, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {
            "n1": 20, "n2": 120, "n3": 220, "n4": 320, 
            "n5": 420, "n6": 520, "n7": 620, "n8": 740, "n9": 840
        }

        # 1. Suspected Dyspepsia
        diamond_node(CX, Y["n1"]+DH/2, DW, DH, dc(v_suspected), "1. Suspected Dyspepsia?", "> 1 month")
        exit_node(LEXT, Y["n1"]+(DH-EH)/2, EW, EH, nc(exit_not_dyspepsia, exit_=True), "Criteria Not Met")
        elbow_line(CX-DW/2, Y["n1"]+DH/2, LEXT+EW, Y["n1"]+(DH-EH)/2+EH/2, exit_not_dyspepsia, exit_=True, label="No")

        # 2. GERD Screen
        vline(CX, Y["n1"]+DH, Y["n2"], v_gerd, label="Yes")
        diamond_node(CX, Y["n2"]+DH/2, DW, DH, dc(v_gerd), "2. Is it GERD?", "Heartburn/Regurg.")
        exit_node(REXT, Y["n2"]+(DH-EH)/2, EW, EH, nc(exit_gerd, exit_=True), "Route to GERD Path")
        elbow_line(CX+DW/2, Y["n2"]+DH/2, REXT, Y["n2"]+(DH-EH)/2+EH/2, exit_gerd, exit_=True, label="Yes")

        # 3. Alarm Features
        vline(CX, Y["n2"]+DH, Y["n3"], v_alarm, label="No")
        diamond_node(CX, Y["n3"]+DH/2, DW, DH, dc(v_alarm), "3. Alarm Features?")
        exit_node(REXT, Y["n3"]+(DH-EH)/2, EW, EH, nc(exit_alarm, urgent=True), "8. Refer to GI / Endo")
        elbow_line(CX+DW/2, Y["n3"]+DH/2, REXT, Y["n3"]+(DH-EH)/2+EH/2, exit_alarm, urgent=True, label="Yes")

        # 4. Medication & Lifestyle
        vline(CX, Y["n3"]+DH, Y["n4"], v_med, label="No")
        diamond_node(CX, Y["n4"]+DH/2, DW, DH, dc(v_med), "4. Med/Lifestyle Review", "Symptoms improve?")
        exit_node(REXT, Y["n4"]+(DH-EH)/2, EW, EH, nc(exit_med, success=True), "No Further Action", "Symptoms Resolved")
        elbow_line(CX+DW/2, Y["n4"]+DH/2, REXT, Y["n4"]+(DH-EH)/2+EH/2, exit_med, label="Yes")
        
        # 5. Baseline Investigations
        vline(CX, Y["n4"]+DH, Y["n5"], v_base, label="No")
        diamond_node(CX, Y["n5"]+DH/2, DW, DH, dc(v_base), "5. Baseline Labs", "Abnormal?")
        exit_node(REXT, Y["n5"]+(DH-EH)/2, EW, EH, nc(exit_base, exit_=True), "Other Diagnosis")
        elbow_line(CX+DW/2, Y["n5"]+DH/2, REXT, Y["n5"]+(DH-EH)/2+EH/2, exit_base, exit_=True, label="Yes")

        # 6. H. Pylori Test
        vline(CX, Y["n5"]+DH, Y["n6"], v_hp, label="No")
        diamond_node(CX, Y["n6"]+DH/2, DW, DH, dc(v_hp), "6. H. pylori Test", "Positive?")
        exit_node(REXT, Y["n6"]+(DH-EH)/2, EW, EH, nc(exit_hp, exit_=True), "Follow H. pylori Path")
        elbow_line(CX+DW/2, Y["n6"]+DH/2, REXT, Y["n6"]+(DH-EH)/2+EH/2, exit_hp, exit_=True, label="Yes")

        # 7. Pharmacological Therapy
        vline(CX, Y["n6"]+DH, Y["n7"], v_pharm, label="No")
        rect_node(CX-NW/2, Y["n7"], NW, NH, nc(v_pharm), "7. Pharmacological Therapy", sub="PPI Trial -> Optimize -> TCA/Domp")

        # 8. Management Response
        vline(CX, Y["n7"]+NH, Y["n8"], v_resp)
        diamond_node(CX, Y["n8"]+DH/2, DW, DH, dc(v_resp), "Response to Therapy", "Unsatisfactory?")
        
        exit_node(REXT, Y["n8"]+(DH-EH)/2, EW, EH, nc(exit_refer, urgent=True), "8. Refer to GI / Endo", "Consider Advice Service")
        elbow_line(CX+DW/2, Y["n8"]+DH/2, REXT, Y["n8"]+(DH-EH)/2+EH/2, exit_refer, urgent=True, label="Yes")
        
        comp = v_resp and not exit_refer
        vline(CX, Y["n8"]+DH, Y["n9"], comp, label="No")
        rect_node(CX-NW/2, Y["n9"], NW, NH, nc(comp, success=True), "Continue PMH Care", sub="Pathway Complete")

        ly = H - 22; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_SUCCESS, "Resolved"),
            (C_URGENT, "Referral"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 105
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=1080, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Context Card
        alarm_str = "Yes" if any([active_bleed, fh_cancer, onset_60, weight_loss, black_stool, dysphagia, vomiting, ida]) else "No"
        hp_str = hp_res if hp_stat == "Yes" else "Not Tested"
        
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Symptom Duration:</b> {dur} months &nbsp;|&nbsp; <b>Alarm Features:</b> {alarm_str}</span><br>'
            f'<span><b>H. pylori Test:</b> {hp_str} &nbsp;|&nbsp; <b>Baseline CBC:</b> {cbc_stat}</span><br>'
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
                for note in details.get("notes", []):
                    items += f'<li style="color:#fde68a">⚠️ {html.escape(str(note))}</li>'
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                skip = {"bullets", "notes", "supported_by", "rome_iv_feature_count", "rome_iv_support_dyspepsia"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {
                "urgent": "urgent", "warning": "warning", "advisory": "advisory",
                None: "routine", "": "routine",
            }
            cls = urgency_to_cls.get(a.urgency or a.display.get("badge", ""), "routine")
            if extra_cls:
                cls = extra_cls

            badge_label = a.display.get("badge", a.urgency or "info").upper()
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
        st.session_state.dys_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.dys_notes,
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
                        "node": o.target_node, "field": o.field, "new_value": o.new_value,
                        "reason": o.reason, "created_at": o.created_at.isoformat(),
                    } for o in st.session_state.dys_overrides
                ],
                "clinician_notes": st.session_state.dys_notes,
            },
        }

        if st.button("💾 Save this output", key="dys_save_output"):
            st.session_state.dys_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "dys_saved_output" in st.session_state:
            md_text = build_dyspepsia_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.dys_overrides,
                notes=st.session_state.dys_notes,
            )

            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="dyspepsia_summary.md",
                mime="text/markdown",
                key="dys_download_md",
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
                            (o for o in st.session_state.dys_overrides
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
                                    st.session_state.dys_overrides = [
                                        o for o in st.session_state.dys_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.dys_overrides.append(
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
                                st.session_state.dys_overrides = [
                                    o for o in st.session_state.dys_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.dys_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.dys_overrides:
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
