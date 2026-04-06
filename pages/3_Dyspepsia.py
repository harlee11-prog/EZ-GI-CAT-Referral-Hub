import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from dyspepsia_engine import (
    run_dyspepsia_pathway, Action, DataRequest, Stop, Override,
)

st.set_page_config(page_title="Dyspepsia", layout="wide")


# ── MARKDOWN HELPER ──────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def build_dyspepsia_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Dyspepsia Pathway – Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age')} / {str(patient_data.get('sex', '')).capitalize()}")
    lines.append(f"- **Symptom duration:** {patient_data.get('symptom_duration_months')} months")
    lines.append(f"- **Predominant symptom:** "
                 f"{'Epigastric pain' if patient_data.get('predominant_epigastric_pain') else ''}"
                 f"{'/ Discomfort' if patient_data.get('predominant_epigastric_discomfort') else ''}"
                 f"{'/ Bloating' if patient_data.get('predominant_upper_abdominal_bloating') else ''}")
    lines.append(f"- **GERD symptoms (heartburn/regurgitation):** "
                 f"{'Yes' if (patient_data.get('predominant_heartburn') or patient_data.get('predominant_regurgitation')) else 'No'}")
    lines.append(f"- **Alarm features present:** "
                 f"{'Yes' if any([patient_data.get(k) for k in ['family_history_upper_gi_cancer_first_degree','symptom_onset_after_age_60','unintended_weight_loss','black_stool_or_blood_in_vomit','dysphagia','persistent_vomiting','iron_deficiency_anemia_present']]) else 'None documented'}")
    lines.append(f"- **H. pylori test done:** {patient_data.get('h_pylori_test_done')}")
    lines.append(f"- **H. pylori positive:** {patient_data.get('h_pylori_result_positive')}")
    lines.append(f"- **PPI once daily trial done:** {patient_data.get('ppi_once_daily_trial_done')}")
    lines.append(f"- **PPI twice daily trial done:** {patient_data.get('ppi_bid_trial_done')}")
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
                    skip = {"bullets", "notes", "supported_by"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(v)}")
            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                for a in o.actions:
                    lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                missing = ", ".join(o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing fields: {missing}")
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


# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
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

st.title("Dyspepsia Pathway")
st.markdown("---")

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "dys_overrides" not in st.session_state:
    st.session_state.dys_overrides = []
if "dys_has_run" not in st.session_state:
    st.session_state.dys_has_run = False
if "dys_notes" not in st.session_state:
    st.session_state.dys_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ────────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")

    age = st.number_input("Age", 1, 120, 45)
    sex = st.selectbox("Sex", ["male", "female"])

    # ── 1. SUSPECTED DYSPEPSIA ───────────────────────────────────────────────
    st.markdown("**1. Suspected Dyspepsia – Predominant Symptoms (> 1 month)**")
    symptom_duration_months = st.number_input(
        "Symptom duration (months)", min_value=0, max_value=240, value=2,
        help="Must be > 1 month to enter pathway"
    )
    predominant_epigastric_pain = st.checkbox("Predominant epigastric pain")
    predominant_epigastric_discomfort = st.checkbox("Predominant epigastric discomfort")
    predominant_upper_abdominal_bloating = st.checkbox("Predominant upper abdominal bloating / distension")

    st.markdown("*Rome IV support (optional)*")
    postprandial_fullness = st.checkbox("Postprandial fullness")
    early_satiety = st.checkbox("Early satiety")
    epigastric_pain_rome = st.checkbox("Epigastric pain (Rome IV criterion)", key="ep_rome")
    epigastric_burning = st.checkbox("Epigastric burning")
    symptom_onset_months_ago = st.number_input(
        "Symptom onset (months ago)", min_value=0, max_value=360, value=0,
        help="For Rome IV: onset ≥ 6 months ago"
    )

    # ── 2. GERD SCREEN ───────────────────────────────────────────────────────
    st.markdown("**2. Is it GERD?** *(heartburn ± regurgitation)*")
    predominant_heartburn = st.checkbox("Predominant heartburn")
    predominant_regurgitation = st.checkbox("Predominant regurgitation")

    # ── 3. ALARM FEATURES ────────────────────────────────────────────────────
    st.markdown("**3. Alarm Features**")
    actively_bleeding_now = st.checkbox("⚠️ Actively bleeding NOW (urgent)")
    al_fh_upper_gi_cancer = st.checkbox("Family hx (1st-degree) esophageal / gastric cancer")
    al_onset_after_60 = st.checkbox("Symptom onset after age 60 with new persistent symptoms (> 3 months)")
    al_weight_loss = st.checkbox("Unintended weight loss > 5% over 6–12 months")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_vomiting = st.checkbox("Persistent vomiting (not cannabis-related)")
    al_black_stool = st.checkbox("Black stool or blood in vomit")
    al_ida = st.checkbox("Iron deficiency anemia")

    # ── 4. MEDICATION & LIFESTYLE REVIEW ─────────────────────────────────────
    st.markdown("**4. Medication & Lifestyle Review**")
    medication_review_done = st.checkbox("Medication review completed")
    lifestyle_review_done = st.checkbox("Lifestyle review completed (alcohol, caffeine, smoking, stress)")
    diet_trigger_review_done = st.checkbox("Diet trigger review completed")
    symptoms_improved_after_review_sel = st.selectbox(
        "Symptoms after med/lifestyle review",
        ["Unknown / not yet assessed", "Improved – no further action", "Not improved – continue pathway"],
    )
    improved_map = {
        "Unknown / not yet assessed": None,
        "Improved – no further action": True,
        "Not improved – continue pathway": False,
    }

    # ── 5. BASELINE INVESTIGATIONS ───────────────────────────────────────────
    st.markdown("**5. Baseline Investigations**")
    cbc_done = st.selectbox("CBC", ["Not done", "Done – normal", "Done – abnormal"])
    cbc_map = {"Not done": False, "Done – normal": True, "Done – abnormal": True}
    cbc_abnormal = cbc_done == "Done – abnormal"

    ferritin_done_sel = st.selectbox("Ferritin (optional)", ["Not ordered", "Ordered / done", "Not done"])
    ferritin_map = {"Not ordered": None, "Ordered / done": True, "Not done": False}

    ttg_iga_done_sel = st.selectbox("TTG IgA (celiac screen)", ["Not ordered", "Done – negative", "Done – positive"])
    ttg_iga_map = {"Not ordered": None, "Done – negative": True, "Done – positive": True}
    ttg_iga_positive = ttg_iga_done_sel == "Done – positive"

    suspect_hepato = st.checkbox("Suspect hepatobiliary / pancreatic disease")
    hepato_tests_done = False
    hepato_abnormal = False
    if suspect_hepato:
        hepato_tests_done = st.checkbox("Hepatobiliary/pancreatic workup done (U/S, ALT, ALP, bilirubin, lipase)")
        if hepato_tests_done:
            hepato_abnormal = st.checkbox("Hepatobiliary/pancreatic workup abnormal")

    other_diagnosis_found = st.checkbox("Other diagnosis identified on investigations")

    # ── 6. H. PYLORI TEST AND TREAT ──────────────────────────────────────────
    st.markdown("**6. H. Pylori Test and Treat** *(HpSAT or UBT)*")
    hp_test_done_sel = st.selectbox("H. pylori test status", ["Not yet done", "Done"])
    hp_test_done = hp_test_done_sel == "Done"

    hp_result_positive = None
    if hp_test_done:
        hp_result_sel = st.selectbox("H. pylori result", ["Positive", "Negative"])
        hp_result_positive = hp_result_sel == "Positive"

    # ── 7. PHARMACOLOGICAL THERAPY ───────────────────────────────────────────
    st.markdown("**7. Pharmacological Therapy**")
    ppi_od_sel = st.selectbox(
        "PPI once-daily trial (4–8 weeks)",
        ["Not yet started", "Trial done – adequate response", "Trial done – inadequate response"],
    )
    ppi_od_done = ppi_od_sel != "Not yet started"
    ppi_od_adequate = True if ppi_od_sel == "Trial done – adequate response" else (
        False if ppi_od_sel == "Trial done – inadequate response" else None
    )

    ppi_bid_done = None
    ppi_bid_adequate = None
    if ppi_od_sel == "Trial done – inadequate response":
        ppi_bid_sel = st.selectbox(
            "PPI twice-daily trial (4–8 weeks)",
            ["Not yet started", "Trial done – adequate response", "Trial done – inadequate response"],
        )
        ppi_bid_done = ppi_bid_sel != "Not yet started"
        ppi_bid_adequate = True if ppi_bid_sel == "Trial done – adequate response" else (
            False if ppi_bid_sel == "Trial done – inadequate response" else None
        )

    symptoms_resolved_after_ppi = None
    symptoms_return_after_deprescribing = None
    if ppi_od_adequate or ppi_bid_adequate:
        resolved_sel = st.selectbox(
            "Symptoms resolved after PPI?",
            ["Unknown", "Yes – resolved", "No – not resolved"],
        )
        resolved_map = {"Unknown": None, "Yes – resolved": True, "No – not resolved": False}
        symptoms_resolved_after_ppi = resolved_map[resolved_sel]
        if symptoms_resolved_after_ppi is True:
            return_sel = st.selectbox(
                "Symptoms returned after deprescribing?",
                ["Unknown / not tried", "Yes – returned", "No – still resolved"],
            )
            return_map = {"Unknown / not tried": None, "Yes – returned": True, "No – still resolved": False}
            symptoms_return_after_deprescribing = return_map[return_sel]

    # ── 8. DOMPERIDONE ELIGIBILITY ───────────────────────────────────────────
    show_domperidone = ppi_bid_adequate is False
    ecg_qtc_ms = None
    family_hx_scd = None
    personal_cardiac_hx = None
    qt_meds = None
    if show_domperidone:
        st.markdown("**Domperidone Safety Check** *(required when PPI BID inadequate)*")
        ecg_qtc_ms = st.number_input("ECG QTc (ms)", min_value=0, max_value=700, value=430,
                                     help="Male threshold 470 ms, Female threshold 450 ms")
        family_hx_scd = st.checkbox("Family history of sudden cardiac death")
        personal_cardiac_hx = st.checkbox("Personal history of cardiac disease (e.g. heart failure)")
        qt_meds = st.checkbox("Currently on QT-prolonging medications")

    # ── MANAGEMENT RESPONSE ──────────────────────────────────────────────────
    st.markdown("**Overall Management Response**")
    mgmt_response_sel = st.selectbox(
        "Response to overall dyspepsia management",
        ["Not yet assessed", "Satisfactory – continue in medical home", "Unsatisfactory – further action needed"],
    )
    mgmt_map = {
        "Not yet assessed": None,
        "Satisfactory – continue in medical home": False,
        "Unsatisfactory – further action needed": True,
    }
    advice_service_considered = False
    if mgmt_response_sel == "Unsatisfactory – further action needed":
        advice_service_considered = st.checkbox("Advice service already consulted before referring")

    # ── ACTION BUTTONS ────────────────────────────────────────────────────────
    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.dys_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.dys_overrides = []
        if "dys_saved_output" in st.session_state:
            del st.session_state["dys_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ───────────────────────────────────────────────────────────────
with right:
    if st.session_state.dys_has_run:

        # Build patient_data dict keyed to engine field names
        patient_data = {
            "age": age,
            "sex": sex,
            # Node 1 – Suspected Dyspepsia
            "predominant_epigastric_pain": predominant_epigastric_pain or None,
            "predominant_epigastric_discomfort": predominant_epigastric_discomfort or None,
            "predominant_upper_abdominal_bloating": predominant_upper_abdominal_bloating or None,
            "symptom_duration_months": symptom_duration_months,
            "postprandial_fullness": postprandial_fullness or None,
            "early_satiety": early_satiety or None,
            "epigastric_pain": epigastric_pain_rome or None,
            "epigastric_burning": epigastric_burning or None,
            "symptom_onset_months_ago": symptom_onset_months_ago if symptom_onset_months_ago > 0 else None,
            # Node 2 – GERD Screen
            "predominant_heartburn": predominant_heartburn or None,
            "predominant_regurgitation": predominant_regurgitation or None,
            # Node 3 – Alarm Features
            "actively_bleeding_now": actively_bleeding_now or None,
            "family_history_upper_gi_cancer_first_degree": al_fh_upper_gi_cancer or None,
            "symptom_onset_after_age_60": al_onset_after_60 or None,
            "unintended_weight_loss": al_weight_loss or None,
            "dysphagia": al_dysphagia or None,
            "persistent_vomiting": al_vomiting or None,
            "black_stool_or_blood_in_vomit": al_black_stool or None,
            "iron_deficiency_anemia_present": al_ida or None,
            # Node 4 – Medication/Lifestyle Review
            "medication_review_done": medication_review_done or None,
            "lifestyle_review_done": lifestyle_review_done or None,
            "diet_trigger_review_done": diet_trigger_review_done or None,
            "symptoms_improved_after_med_lifestyle_review": improved_map[symptoms_improved_after_review_sel],
            # Node 5 – Baseline Investigations
            "cbc_done": cbc_map[cbc_done],
            "cbc_abnormal": cbc_abnormal or None,
            "ferritin_done": ferritin_map[ferritin_done_sel],
            "ttg_iga_done": ttg_iga_map[ttg_iga_done_sel],
            "ttg_iga_positive": ttg_iga_positive or None,
            "suspect_hepatobiliary_pancreatic_process": suspect_hepato or None,
            "hepatobiliary_pancreatic_tests_done": hepato_tests_done or None,
            "hepatobiliary_pancreatic_workup_abnormal": hepato_abnormal or None,
            "other_diagnosis_found": other_diagnosis_found or None,
            # Node 6 – H. pylori
            "h_pylori_test_done": hp_test_done,
            "h_pylori_result_positive": hp_result_positive,
            # Node 7 – Pharmacologic Therapy
            "ppi_once_daily_trial_done": ppi_od_done if ppi_od_done else None,
            "ppi_once_daily_response_adequate": ppi_od_adequate,
            "ppi_bid_trial_done": ppi_bid_done,
            "ppi_bid_response_adequate": ppi_bid_adequate,
            # Maintenance / Deprescribing
            "symptoms_resolved_after_ppi": symptoms_resolved_after_ppi,
            "symptoms_return_after_deprescribing": symptoms_return_after_deprescribing,
            # Node 8 – Domperidone
            "ecg_qtc_ms": ecg_qtc_ms,
            "family_history_sudden_cardiac_death": family_hx_scd,
            "personal_cardiac_history": personal_cardiac_hx,
            "qt_prolonging_medications_present": qt_meds,
            # Management Response
            "unsatisfactory_response_to_management": mgmt_map[mgmt_response_sel],
            "advice_service_considered": advice_service_considered or None,
        }

        outputs, logs, applied_overrides = run_dyspepsia_pathway(
            patient_data, overrides=st.session_state.dys_overrides
        )

        # ── Pathway state flags for SVG ───────────────────────────────────────
        has_alarm = any(
            isinstance(o, Stop) and "alarm" in o.reason.lower() for o in outputs
        )
        routed_gerd = any(
            isinstance(o, Stop) and "gerd" in o.reason.lower() for o in outputs
        )
        entry_met = any(
            isinstance(o, Action) and o.code == "DYSPEPSIA_ENTRY_MET" for o in outputs
        )
        not_entry = any(
            isinstance(o, Stop) and "entry criteria not met" in o.reason.lower() for o in outputs
        )
        improved_lifestyle = any(
            isinstance(o, Stop) and "improved after medication" in o.reason.lower() for o in outputs
        )
        other_diagnosis = any(
            isinstance(o, Stop) and "another diagnosis" in o.reason.lower() for o in outputs
        )
        routed_hp = any(
            isinstance(o, Stop) and "h. pylori positive" in o.reason.lower() for o in outputs
        )
        ppi_od_success = any(
            isinstance(o, Action) and o.code == "PPI_ONCE_DAILY_SUCCESS" for o in outputs
        )
        ppi_bid_success = any(
            isinstance(o, Action) and o.code == "PPI_BID_SUCCESS" for o in outputs
        )
        started_ppi = any(
            isinstance(o, Action) and o.code == "START_PPI_ONCE_DAILY" for o in outputs
        )
        tca_considered = any(
            isinstance(o, Action) and o.code == "CONSIDER_TCA" for o in outputs
        )
        domperidone_eligible = any(
            isinstance(o, Action) and o.code == "DOMPERIDONE_ELIGIBLE" for o in outputs
        )
        titrate_down = any(
            isinstance(o, Action) and o.code == "TITRATE_DOWN_PPI" for o in outputs
        )
        pathway_complete = any(
            isinstance(o, Stop) and "pathway complete" in o.reason.lower() for o in outputs
        )
        refer_endoscopy = any(
            isinstance(o, Stop) and "refer" in o.reason.lower() and "consultation" in o.reason.lower()
            for o in outputs
        )

        # ── SVG FLOWCHART ─────────────────────────────────────────────────────
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
        W, H = 700, 1180
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
                svgt(x + w / 2, y + h / 2 - 8, line1, tc, 11, True)
                svgt(x + w / 2, y + h / 2 + 7, line2, tc, 11, True)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 11, True)
            if sub:
                svgt(x + w / 2, y + h - 8, sub, tc + "99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w / 2, h / 2
            pts = f"{cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh} {cx - hw},{cy}"
            svg.append(
                f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(cx, cy - 7, line1, tc, 10, True)
                svgt(cx, cy + 8, line2, tc, 10, True)
            else:
                svgt(cx, cy + 4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x + w / 2, y + h / 2 - 7, line1, tc, 10, True)
                svgt(x + w / 2, y + h / 2 + 7, line2, tc, 9)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x + 6, (y1 + y2) / 2 - 3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y1 - 5, label, stroke, 10, True)

        # Layout constants
        CX = 350; NW, NH = 175, 50; DW, DH = 190, 58; EW, EH = 138, 44
        LEXT = 20; REXT = W - 20 - EW

        Y = {
            "start":    16,
            "d_entry":  88,   # 1. Suspected Dyspepsia?
            "d_gerd":   185,  # 2. Is it GERD?
            "d_alarm":  284,  # 3. Alarm Features?
            "med_rev":  383,  # 4. Med / Lifestyle Review
            "d_improv": 453,  # Improved after review?
            "baseline": 538,  # 5. Baseline Investigations
            "d_hpyl":   618,  # 6. H. pylori Test & Treat
            "pharma":   720,  # 7. Pharmacologic Therapy
            "d_ppi_od": 790,  # PPI OD response?
            "d_ppi_bid":875,  # Optimize PPI BID
            "tca_dom":  960,  # TCA / Domperidone
            "maintain": 1048, # Maintenance / Deprescribing
            "complete": 1110, # Pathway Complete / Refer
        }

        # Node 0 – Start
        rect_node(CX - NW / 2, Y["start"], NW, NH, nc(True), "Patient Presents", sub="Epigastric symptoms")

        # Node 1 – Suspected Dyspepsia
        vline(CX, Y["start"] + NH, Y["d_entry"], True)
        diamond_node(CX, Y["d_entry"] + DH / 2, DW, DH, dc(True), "1. Suspected", "Dyspepsia?")
        exit_node(LEXT, Y["d_entry"] + (DH - EH) / 2, EW, EH, nc(not_entry, exit_=True), "Entry Criteria", "Not Met")
        elbow_line(CX - DW / 2, Y["d_entry"] + DH / 2, LEXT + EW, Y["d_entry"] + (DH - EH) / 2 + EH / 2,
                   not_entry, exit_=True, label="No")

        v_entry = entry_met
        vline(CX, Y["d_entry"] + DH, Y["d_gerd"], v_entry, label="Yes")

        # Node 2 – GERD Screen
        diamond_node(CX, Y["d_gerd"] + DH / 2, DW, DH, dc(v_entry), "2. Is it", "GERD?")
        exit_node(REXT, Y["d_gerd"] + (DH - EH) / 2, EW, EH, nc(routed_gerd, exit_=True), "→ GERD", "Pathway")
        elbow_line(CX + DW / 2, Y["d_gerd"] + DH / 2, REXT, Y["d_gerd"] + (DH - EH) / 2 + EH / 2,
                   routed_gerd, exit_=True, label="Yes")

        v_not_gerd = v_entry and not routed_gerd
        vline(CX, Y["d_gerd"] + DH, Y["d_alarm"], v_not_gerd, label="No")

        # Node 3 – Alarm Features
        diamond_node(CX, Y["d_alarm"] + DH / 2, DW, DH, dc(v_not_gerd), "3. Alarm", "Features?")
        exit_node(REXT, Y["d_alarm"] + (DH - EH) / 2, EW, EH, nc(has_alarm, urgent=True), "⚠ Urgent Refer", "Endoscopy")
        elbow_line(CX + DW / 2, Y["d_alarm"] + DH / 2, REXT, Y["d_alarm"] + (DH - EH) / 2 + EH / 2,
                   has_alarm, urgent=True, label="Yes")

        v_no_alarm = v_not_gerd and not has_alarm
        vline(CX, Y["d_alarm"] + DH, Y["med_rev"], v_no_alarm, label="No")

        # Node 4 – Med/Lifestyle Review
        rect_node(CX - NW / 2, Y["med_rev"], NW, NH, nc(v_no_alarm), "4. Medication &", "Lifestyle Review")
        vline(CX, Y["med_rev"] + NH, Y["d_improv"], v_no_alarm)
        diamond_node(CX, Y["d_improv"] + DH / 2, DW, DH, dc(v_no_alarm), "Symptoms", "Improved?")
        exit_node(REXT, Y["d_improv"] + (DH - EH) / 2, EW, EH, nc(improved_lifestyle, exit_=True), "No Further", "Action Req'd")
        elbow_line(CX + DW / 2, Y["d_improv"] + DH / 2, REXT, Y["d_improv"] + (DH - EH) / 2 + EH / 2,
                   improved_lifestyle, exit_=True, label="Yes")

        v_not_improved = v_no_alarm and not improved_lifestyle
        vline(CX, Y["d_improv"] + DH, Y["baseline"], v_not_improved, label="No")

        # Node 5 – Baseline Investigations
        rect_node(CX - NW / 2, Y["baseline"], NW, NH, nc(v_not_improved), "5. Baseline", "Investigations")
        exit_node(LEXT, Y["baseline"] + (NH - EH) / 2, EW, EH, nc(other_diagnosis, exit_=True), "Other Dx", "Identified")
        elbow_line(CX - NW / 2, Y["baseline"] + NH / 2, LEXT + EW, Y["baseline"] + (NH - EH) / 2 + EH / 2,
                   other_diagnosis, exit_=True, label="Abnormal")

        v_baseline_ok = v_not_improved and not other_diagnosis
        vline(CX, Y["baseline"] + NH, Y["d_hpyl"], v_baseline_ok)

        # Node 6 – H. pylori Test & Treat
        diamond_node(CX, Y["d_hpyl"] + DH / 2, DW, DH, dc(v_baseline_ok), "6. H. pylori", "Test & Treat")
        exit_node(REXT, Y["d_hpyl"] + (DH - EH) / 2, EW, EH, nc(routed_hp, exit_=True), "→ H. pylori", "Pathway")
        elbow_line(CX + DW / 2, Y["d_hpyl"] + DH / 2, REXT, Y["d_hpyl"] + (DH - EH) / 2 + EH / 2,
                   routed_hp, exit_=True, label="+ve")

        v_hp_neg = v_baseline_ok and not routed_hp
        vline(CX, Y["d_hpyl"] + DH, Y["pharma"], v_hp_neg, label="-ve")

        # Node 7 – Pharmacologic Therapy
        rect_node(CX - NW / 2, Y["pharma"], NW, NH, nc(v_hp_neg), "7. Pharmacologic", "Therapy")
        vline(CX, Y["pharma"] + NH, Y["d_ppi_od"], v_hp_neg)
        diamond_node(CX, Y["d_ppi_od"] + DH / 2, DW, DH, dc(v_hp_neg), "PPI OD Trial", "Adequate?")

        v_ppi_od_ok = v_hp_neg and ppi_od_success
        exit_node(LEXT, Y["d_ppi_od"] + (DH - EH) / 2, EW, EH, nc(v_ppi_od_ok, exit_=True), "Titrate Down", "/ Maintain PPI")
        elbow_line(CX - DW / 2, Y["d_ppi_od"] + DH / 2, LEXT + EW, Y["d_ppi_od"] + (DH - EH) / 2 + EH / 2,
                   v_ppi_od_ok, exit_=True, label="Yes")

        v_ppi_od_fail = v_hp_neg and not ppi_od_success
        vline(CX, Y["d_ppi_od"] + DH, Y["d_ppi_bid"], v_ppi_od_fail, label="No")

        # PPI BID
        diamond_node(CX, Y["d_ppi_bid"] + DH / 2, DW, DH, dc(v_ppi_od_fail), "Optimize PPI BID", "Adequate?")
        v_ppi_bid_ok = v_ppi_od_fail and ppi_bid_success
        exit_node(LEXT, Y["d_ppi_bid"] + (DH - EH) / 2, EW, EH, nc(v_ppi_bid_ok, exit_=True), "Titrate Down", "/ Maintain PPI")
        elbow_line(CX - DW / 2, Y["d_ppi_bid"] + DH / 2, LEXT + EW, Y["d_ppi_bid"] + (DH - EH) / 2 + EH / 2,
                   v_ppi_bid_ok, exit_=True, label="Yes")

        v_ppi_bid_fail = v_ppi_od_fail and not ppi_bid_success
        vline(CX, Y["d_ppi_bid"] + DH, Y["tca_dom"], v_ppi_bid_fail, label="No")

        # Node 8 – TCA / Domperidone
        rect_node(CX - NW / 2, Y["tca_dom"], NW, NH, nc(tca_considered or v_ppi_bid_fail),
                  "TCA Trial", sub="Optional / while awaiting consult")
        domperidone_vis = domperidone_eligible or (v_ppi_bid_fail and ecg_qtc_ms is not None)
        rect_node(REXT - 10, Y["tca_dom"] + 4, EW, EH - 8, nc(domperidone_vis),
                  "Domperidone", "Eligibility")
        elbow_line(CX + NW / 2, Y["tca_dom"] + NH / 2, REXT - 10, Y["tca_dom"] + EH / 2,
                   domperidone_vis, label="If eligible")

        vline(CX, Y["tca_dom"] + NH, Y["maintain"], tca_considered or v_ppi_bid_fail)

        # Node 9 – Maintenance / Deprescribing
        rect_node(CX - NW / 2, Y["maintain"], NW, NH, nc(titrate_down), "PPI Maintenance /", "Deprescribing")

        vline(CX, Y["maintain"] + NH, Y["complete"], pathway_complete or refer_endoscopy)

        # Terminal nodes
        exit_node(CX - NW / 2 - 6, Y["complete"], NW, EH,
                  nc(pathway_complete, exit_=True), "Pathway Complete", "Medical Home")
        exit_node(CX + NW / 2 - EW + NW / 2 + 10, Y["complete"], EW, EH,
                  nc(refer_endoscopy, urgent=True), "8. Refer", "Consultation/Scope")

        # Legend
        ly = H - 20; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx + 16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 118
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=1210, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient Context Card ──────────────────────────────────────────────
        alarm_fields_display = [
            ("family_history_upper_gi_cancer_first_degree", "Family hx upper GI cancer"),
            ("symptom_onset_after_age_60", "Onset after age 60"),
            ("unintended_weight_loss", "Unintended weight loss >5%"),
            ("black_stool_or_blood_in_vomit", "Black stool / blood in vomit"),
            ("dysphagia", "Progressive dysphagia"),
            ("persistent_vomiting", "Persistent vomiting"),
            ("iron_deficiency_anemia_present", "Iron deficiency anemia"),
        ]
        active_alarms = [label for key, label in alarm_fields_display if patient_data.get(key)]
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"

        ppi_status = (
            "PPI OD adequate" if ppi_od_success else
            ("PPI BID adequate" if ppi_bid_success else
             ("PPI OD trial started" if started_ppi else "Not yet started"))
        )
        hp_test_str = (
            "Positive → H. pylori Pathway" if hp_result_positive else
            ("Negative" if (hp_test_done and hp_result_positive is False) else "Not yet done")
        )

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Symptom Duration:</b> {symptom_duration_months} months</span><br>'
            f'<span><b>H. pylori:</b> {hp_test_str}</span><br>'
            f'<span><b>PPI Status:</b> {ppi_status}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span><br>'
            f'<span><b>GERD Features:</b> {"Yes – routed to GERD pathway" if routed_gerd else "No"}</span>'
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
                skip = {"bullets", "notes", "supported_by"}
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
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">'
                "🔒 Override available – reason required</p>"
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

        # ── Clinician Notes ───────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.dys_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.dys_notes,
            height=180,
        )

        # ── Save / Download ───────────────────────────────────────────────────
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
                        "node": o.target_node,
                        "field": o.field,
                        "new_value": o.new_value,
                        "reason": o.reason,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in st.session_state.dys_overrides
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

        # ── Clinician Overrides Panel ─────────────────────────────────────────
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

        # ── Decision Audit Log ────────────────────────────────────────────────
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
