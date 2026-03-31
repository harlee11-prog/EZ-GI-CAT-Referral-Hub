import os, sys
import html
import io
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from dyspepsia_engine import (
    run_dyspepsia_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Dyspepsia Pathway", page_icon="⚕️", layout="wide")

# ── MARKDOWN / PDF HELPERS ──────────────────────────────────────────────────
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
    lines.append(f"- **Age / Sex:** {_safe_text(patient_data.get('age'))} / {_safe_text(patient_data.get('sex')).capitalize()}")
    lines.append(f"- **Symptom duration (months):** {_safe_text(patient_data.get('symptom_duration_months'))}")
    lines.append(f"- **Predominant Pain/Discomfort:** {_safe_text(patient_data.get('predominant_epigastric_pain') or patient_data.get('predominant_epigastric_discomfort'))}")
    lines.append(f"- **Predominant Bloating:** {_safe_text(patient_data.get('predominant_upper_abdominal_bloating'))}")
    lines.append(f"- **Predominant GERD symptoms:** {_safe_text(patient_data.get('predominant_heartburn') or patient_data.get('predominant_regurgitation'))}")
    lines.append(f"- **H. Pylori Test Done:** {_safe_text(patient_data.get('h_pylori_test_done'))}")
    lines.append(f"- **H. Pylori Positive:** {_safe_text(patient_data.get('h_pylori_result_positive'))}")
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

st.title("⚕️ Dyspepsia Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "dysp_overrides" not in st.session_state:
    st.session_state.dysp_overrides = []

if "dysp_has_run" not in st.session_state:
    st.session_state.dysp_has_run = False

if "dysp_notes" not in st.session_state:
    st.session_state.dysp_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 50)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Pathway Entry Criteria (Symptoms)**")
    symptom_duration_months = st.number_input("Symptom duration (months)", 0, 600, 2)
    symptom_onset_months_ago = st.number_input("Symptom onset (months ago)", 0, 600, 2)
    
    col_sym1, col_sym2 = st.columns(2)
    with col_sym1:
        epigastric_pain = st.checkbox("Predominant epigastric pain")
        epigastric_discomfort = st.checkbox("Predominant epigastric discomfort")
        bloating = st.checkbox("Predominant upper abdominal bloating")
    with col_sym2:
        heartburn = st.checkbox("Predominant heartburn (GERD screen)")
        regurgitation = st.checkbox("Predominant regurgitation (GERD screen)")

    st.markdown("**Rome IV Supportive Symptoms**")
    rome_fullness = st.checkbox("Postprandial fullness")
    rome_satiety = st.checkbox("Early satiety")
    rome_burning = st.checkbox("Epigastric burning")

    st.markdown("**3. Alarm Features**")
    active_bleeding = st.checkbox("Actively bleeding now (EMERGENT)")
    fh_gi_cancer = st.checkbox("Family history (1st-degree) upper GI cancer")
    onset_after_60 = st.checkbox("New/persistent symptom onset after age 60")
    weight_loss = st.checkbox("Unintended weight loss > 5%")
    dysphagia = st.checkbox("Progressive dysphagia")
    vomiting = st.checkbox("Persistent vomiting")
    gi_bleed_signs = st.checkbox("Black stool or blood in vomit")
    ida = st.checkbox("Iron deficiency anemia present")

    st.markdown("**4. Medication & Lifestyle Review**")
    med_review = st.selectbox("Medication review done?", ["Unknown", "Yes", "No"])
    lifestyle_review = st.selectbox("Lifestyle review done?", ["Unknown", "Yes", "No"])
    diet_review = st.selectbox("Diet trigger review done?", ["Unknown", "Yes", "No"])
    symptoms_improved_lifestyle = st.selectbox("Symptoms improved after review?", ["Unknown", "Yes", "No"])

    st.markdown("**5. Baseline Investigations**")
    cbc_done = st.selectbox("CBC Done?", ["Unknown", "Yes", "No"])
    cbc_abnormal = st.checkbox("CBC Abnormal")
    hp_test_done = st.selectbox("H. Pylori Test Done?", ["Unknown", "Yes", "No"])
    hp_result_positive = st.selectbox("H. Pylori Result Positive?", ["Unknown", "Yes", "No"])
    ferritin_done = st.checkbox("Ferritin done")
    ttg_done = st.checkbox("TTG IgA (Celiac) done")
    ttg_positive = st.checkbox("TTG IgA Positive")
    hep_suspect = st.checkbox("Suspect hepatobiliary/pancreatic process")
    hep_done = st.checkbox("Hepatobiliary/pancreatic tests done")
    hep_abnormal = st.checkbox("Hepatobiliary/pancreatic tests abnormal")
    other_dx = st.checkbox("Other diagnosis identified at baseline")

    st.markdown("**7. Pharmacologic Therapy & Domperidone**")
    ppi_qd_trial = st.selectbox("PPI Once Daily Trial Done?", ["Unknown", "Yes", "No"])
    ppi_qd_resp = st.selectbox("Response to PPI Once Daily Adequate?", ["Unknown", "Yes", "No"])
    ppi_bid_trial = st.selectbox("PPI BID Trial Done?", ["Unknown", "Yes", "No"])
    ppi_bid_resp = st.selectbox("Response to PPI BID Adequate?", ["Unknown", "Yes", "No"])
    
    st.markdown("*Domperidone Eligibility Info*")
    ecg_qtc = st.number_input("ECG QTc (ms)", 300, 600, 420)
    fh_sudden_death = st.checkbox("Family history of sudden cardiac death")
    pers_cardiac = st.checkbox("Personal cardiac history (e.g., HF)")
    qt_meds = st.checkbox("Concurrent QT-prolonging medications")

    st.markdown("**9. Maintenance & Deprescribing**")
    symp_resolved = st.selectbox("Symptoms resolved after PPI?", ["Unknown", "Yes", "No"])
    symp_return = st.selectbox("Symptoms return after deprescribing?", ["Unknown", "Yes", "No"])

    st.markdown("**10. Management Response**")
    unsatisfactory_mgmt = st.selectbox("Unsatisfactory response to management?", ["Unknown", "Yes", "No"])
    advice_considered = st.selectbox("Advice service considered?", ["Unknown", "Yes", "No"])

    def _map_sel(val):
        if val == "Yes": return True
        if val == "No": return False
        return None

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.dysp_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.dysp_overrides = []
        if "dysp_saved_output" in st.session_state:
            del st.session_state["dysp_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.dysp_has_run:
        patient_data = {
            "age": age,
            "sex": sex,
            "predominant_epigastric_pain": epigastric_pain,
            "predominant_epigastric_discomfort": epigastric_discomfort,
            "predominant_upper_abdominal_bloating": bloating,
            "predominant_heartburn": heartburn,
            "predominant_regurgitation": regurgitation,
            "symptom_duration_months": symptom_duration_months,
            "symptom_onset_months_ago": symptom_onset_months_ago,
            "postprandial_fullness": rome_fullness,
            "early_satiety": rome_satiety,
            "epigastric_burning": rome_burning,
            "actively_bleeding_now": active_bleeding,
            "family_history_upper_gi_cancer_first_degree": fh_gi_cancer,
            "symptom_onset_after_age_60": onset_after_60,
            "unintended_weight_loss": weight_loss,
            "black_stool_or_blood_in_vomit": gi_bleed_signs,
            "dysphagia": dysphagia,
            "persistent_vomiting": vomiting,
            "iron_deficiency_anemia_present": ida,
            "medication_review_done": _map_sel(med_review),
            "lifestyle_review_done": _map_sel(lifestyle_review),
            "diet_trigger_review_done": _map_sel(diet_review),
            "symptoms_improved_after_med_lifestyle_review": _map_sel(symptoms_improved_lifestyle),
            "cbc_done": _map_sel(cbc_done),
            "cbc_abnormal": cbc_abnormal,
            "h_pylori_test_done": _map_sel(hp_test_done),
            "h_pylori_result_positive": _map_sel(hp_result_positive),
            "ferritin_done": ferritin_done,
            "ttg_iga_done": ttg_done,
            "ttg_iga_positive": ttg_positive,
            "suspect_hepatobiliary_pancreatic_process": hep_suspect,
            "hepatobiliary_pancreatic_tests_done": hep_done,
            "hepatobiliary_pancreatic_workup_abnormal": hep_abnormal,
            "other_diagnosis_found": other_dx,
            "ppi_once_daily_trial_done": _map_sel(ppi_qd_trial),
            "ppi_once_daily_response_adequate": _map_sel(ppi_qd_resp),
            "ppi_bid_trial_done": _map_sel(ppi_bid_trial),
            "ppi_bid_response_adequate": _map_sel(ppi_bid_resp),
            "ecg_qtc_ms": ecg_qtc,
            "family_history_sudden_cardiac_death": fh_sudden_death,
            "personal_cardiac_history": pers_cardiac,
            "qt_prolonging_medications_present": qt_meds,
            "symptoms_resolved_after_ppi": _map_sel(symp_resolved),
            "symptoms_return_after_deprescribing": _map_sel(symp_return),
            "unsatisfactory_response_to_management": _map_sel(unsatisfactory_mgmt),
            "advice_service_considered": _map_sel(advice_considered),
        }

        outputs, logs, applied_overrides = run_dyspepsia_pathway(
            patient_data, overrides=st.session_state.dysp_overrides
        )

        # SVG Routing Logic
        def check_code(code_str):
            return any((getattr(o, "code", "") == code_str) for o in outputs)
        
        is_not_dysp = check_code("NOT_DYSPEPSIA")
        is_gerd = check_code("ROUTE_GERD_PATHWAY")
        is_emergent_bleed = check_code("EMERGENT_BLEEDING_ASSESSMENT")
        is_urgent_endo = check_code("URGENT_ENDOSCOPY_REFERRAL")
        is_alarm = is_emergent_bleed or is_urgent_endo
        is_improved_med = check_code("NO_FURTHER_ACTION_REQUIRED")
        is_other_dx = check_code("OTHER_DIAGNOSIS_IDENTIFIED")
        is_hp_route = check_code("ROUTE_H_PYLORI_PATHWAY")
        is_failed_mgmt = check_code("REFER_FAILED_MANAGEMENT")
        is_path_complete = check_code("CONTINUE_MEDICAL_HOME_CARE")

        v_entry = True
        v_gerd = v_entry and not is_not_dysp
        v_alarm = v_gerd and not is_gerd
        v_medlife = v_alarm and not is_alarm
        v_base = v_medlife and not is_improved_med
        v_hp = v_base and not is_other_dx
        v_pharm = v_hp and not is_hp_route
        v_mgmt = v_pharm # Abstracting domperidone/maintenance into pharm flow
        v_complete = v_mgmt and is_path_complete

        # SVG Draw
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
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" '
            f'style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
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
            if label: svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label: svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 170, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {
            "present": 18, "dysp": 100, "gerd": 202, "alarm": 304,
            "medlife": 406, "base": 508, "hp": 610, "pharm": 712,
            "mgmt": 814, "complete": 916
        }

        rect_node(CX-NW/2, Y["present"], NW, NH, nc(True), "Patient Presents")
        vline(CX, Y["present"]+NH, Y["dysp"], True)
        
        diamond_node(CX, Y["dysp"]+DH/2, DW, DH, dc(v_entry), "1. Suspected", "Dyspepsia?")
        exit_node(LEXT, Y["dysp"]+(DH-EH)/2, EW, EH, nc(is_not_dysp, exit_=True), "Criteria Not Met", "Reassess")
        elbow_line(CX-DW/2, Y["dysp"]+DH/2, LEXT+EW, Y["dysp"]+(DH-EH)/2+EH/2, is_not_dysp, exit_=True, label="No")

        vline(CX, Y["dysp"]+DH, Y["gerd"], v_gerd, label="Yes")
        diamond_node(CX, Y["gerd"]+DH/2, DW, DH, dc(v_gerd), "2. Is it GERD?")
        exit_node(REXT, Y["gerd"]+(DH-EH)/2, EW, EH, nc(is_gerd, exit_=True), "Route to GERD", "Follow GERD Path")
        elbow_line(CX+DW/2, Y["gerd"]+DH/2, REXT, Y["gerd"]+(DH-EH)/2+EH/2, is_gerd, exit_=True, label="Yes")

        vline(CX, Y["gerd"]+DH, Y["alarm"], v_alarm, label="No")
        diamond_node(CX, Y["alarm"]+DH/2, DW, DH, dc(v_alarm), "3. Alarm Features?")
        exit_node(REXT, Y["alarm"]+(DH-EH)/2, EW, EH, nc(is_alarm, urgent=True), "Urgent Endoscopy", "Consultation")
        elbow_line(CX+DW/2, Y["alarm"]+DH/2, REXT, Y["alarm"]+(DH-EH)/2+EH/2, is_alarm, urgent=True, label="Yes")

        vline(CX, Y["alarm"]+DH, Y["medlife"], v_medlife, label="No")
        diamond_node(CX, Y["medlife"]+DH/2, DW, DH, dc(v_medlife), "4. Med/Lifestyle", "Review Improved?")
        exit_node(LEXT, Y["medlife"]+(DH-EH)/2, EW, EH, nc(is_improved_med, exit_=True), "Symptoms Improve", "No further action")
        elbow_line(CX-DW/2, Y["medlife"]+DH/2, LEXT+EW, Y["medlife"]+(DH-EH)/2+EH/2, is_improved_med, exit_=True, label="Yes")

        vline(CX, Y["medlife"]+DH, Y["base"], v_base, label="No")
        diamond_node(CX, Y["base"]+DH/2, DW, DH, dc(v_base), "5. Baseline Inv.", "Abnormal?")
        exit_node(LEXT, Y["base"]+(DH-EH)/2, EW, EH, nc(is_other_dx, exit_=True), "Other Diagnosis", "Treat/Refer")
        elbow_line(CX-DW/2, Y["base"]+DH/2, LEXT+EW, Y["base"]+(DH-EH)/2+EH/2, is_other_dx, exit_=True, label="Yes")

        vline(CX, Y["base"]+DH, Y["hp"], v_hp, label="No")
        diamond_node(CX, Y["hp"]+DH/2, DW, DH, dc(v_hp), "6. H. Pylori Test", "Positive?")
        exit_node(REXT, Y["hp"]+(DH-EH)/2, EW, EH, nc(is_hp_route, exit_=True), "Route to H. Pylori", "Follow HP Path")
        elbow_line(CX+DW/2, Y["hp"]+DH/2, REXT, Y["hp"]+(DH-EH)/2+EH/2, is_hp_route, exit_=True, label="Yes")

        vline(CX, Y["hp"]+DH, Y["pharm"], v_pharm, label="No")
        rect_node(CX-NW/2, Y["pharm"], NW, NH, nc(v_pharm), "7. Pharmacologic", "Therapy (PPI/TCA)")

        vline(CX, Y["pharm"]+NH, Y["mgmt"], v_mgmt)
        diamond_node(CX, Y["mgmt"]+DH/2, DW, DH, dc(v_mgmt), "10. Management", "Unsatisfactory?")
        exit_node(LEXT, Y["mgmt"]+(DH-EH)/2, EW, EH, nc(is_failed_mgmt, urgent=True), "Refer for Consult", "Failed Mgmt")
        elbow_line(CX-DW/2, Y["mgmt"]+DH/2, LEXT+EW, Y["mgmt"]+(DH-EH)/2+EH/2, is_failed_mgmt, urgent=True, label="Yes")

        vline(CX, Y["mgmt"]+DH, Y["complete"], v_complete, label="No")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v_complete), "Pathway Complete", "Medical Home Care")

        ly = H - 22; lx = 18
        for col, lbl in [(C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">{"".join(svg)}</div>',
            height=1080, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Symptom Duration:</b> {symptom_duration_months} mo</span><br>'
            f'<span><b>H. Pylori Status:</b> {"Positive" if hp_result_positive == "Yes" else "Negative" if hp_result_positive == "No" else "Unknown"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        def _detail_html(details) -> str:
            if not details: return ""
            items = ""
            if isinstance(details, dict):
                for k, v in details.items():
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls

            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n", "<br>")
            detail_html = _detail_html(a.details)
            override_html = '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">🔒 Override available — reason required</p>' if a.override_options else ""

            st.markdown(
                f'<div class="action-card {cls}"><h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>{detail_html}{override_html}</div>',
                unsafe_allow_html=True,
            )
            if a.override_options: override_candidates.append(a)

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        for output in outputs:
            if isinstance(output, Action):
                render_action(output)
            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in output.missing_fields)
                msg_html = html.escape(output.message).replace("\n", "<br>")
                st.markdown(
                    f'<div class="action-card warning"><h4><span class="badge warning">DATA NEEDED</span> ⏳ {msg_html}</h4><ul><li>Missing fields: {missing_str}</li></ul></div>',
                    unsafe_allow_html=True,
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n", "<br>")
                st.markdown(
                    f'<div class="action-card stop"><h4><span class="badge stop">STOP</span> 🛑 {reason_html}</h4></div>',
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.dysp_notes = st.text_area("Notes to attach to the saved output:", value=st.session_state.dysp_notes, height=180)

        def _serialize_output(o):
            if isinstance(o, Action): return {"type": "action", "code": o.code, "label": o.label, "urgency": o.urgency}
            if isinstance(o, Stop): return {"type": "stop", "reason": o.reason, "urgency": getattr(o, "urgency", None)}
            if isinstance(o, DataRequest): return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
            return {"type": "other", "repr": repr(o)}

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [_serialize_output(o) for o in outputs],
                "overrides": [{"node": o.target_node, "field": o.field, "new_value": o.new_value, "reason": o.reason, "created_at": o.created_at.isoformat()} for o in st.session_state.dysp_overrides],
                "clinician_notes": st.session_state.dysp_notes,
            },
        }

        if st.button("💾 Save this output", key="dysp_save_output"):
            st.session_state.dysp_saved_output = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        if "dysp_saved_output" in st.session_state:
            md_text = build_dyspepsia_markdown(patient_data, outputs, st.session_state.dysp_overrides, st.session_state.dysp_notes)
            st.download_button(label="⬇️ Download Markdown summary", data=md_text.encode("utf-8"), file_name="dyspepsia_summary.md", mime="text/markdown", key="dysp_download_md")

        def _pretty(s: str) -> str:
            return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption("Override engine decisions where clinical judgement differs. A documented reason is required for each override.")

                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node = _pretty(raw_node)
                    field = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>', unsafe_allow_html=True)
                        existing = next((o for o in st.session_state.dysp_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(
                            f"Set `{field}` to:", options=allowed, index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}", horizontal=True
                        )
                        reason = st.text_input("Reason (required):", value=existing.reason if existing else "", key=f"ov_reason_{raw_node}_{raw_field}", placeholder="Document clinical rationale...")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.dysp_overrides = [o for o in st.session_state.dysp_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.dysp_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.dysp_overrides = [o for o in st.session_state.dysp_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.dysp_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.dysp_overrides:
                        st.markdown(
                            f'<div class="override-card">🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code> set to <b>{html.escape(str(o.new_value))}</b><br><span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br><span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span></div>',
                            unsafe_allow_html=True
                        )

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try: ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception: ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
