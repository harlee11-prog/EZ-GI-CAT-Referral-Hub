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


# ── MARKDOWN HELPER ───────────────────────────────────────────────────────────
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
    symptoms = []
    if patient_data.get("predominant_epigastric_pain"):        symptoms.append("Epigastric pain")
    if patient_data.get("predominant_epigastric_discomfort"):  symptoms.append("Epigastric discomfort")
    if patient_data.get("predominant_upper_abdominal_bloating"): symptoms.append("Upper abdominal bloating")
    lines.append(f"- **Predominant symptoms:** {', '.join(symptoms) or 'None documented'}")
    alarm_keys = [
        ("family_history_upper_gi_cancer_first_degree", "Family hx upper GI cancer"),
        ("symptom_onset_after_age_60",  "Onset after 60"),
        ("unintended_weight_loss",       "Weight loss >5%"),
        ("black_stool_or_blood_in_vomit","Black stool/blood in vomit"),
        ("dysphagia",                   "Progressive dysphagia"),
        ("persistent_vomiting",          "Persistent vomiting"),
        ("iron_deficiency_anemia_present","Iron deficiency anemia"),
    ]
    active_alarms = [lbl for k, lbl in alarm_keys if patient_data.get(k)]
    lines.append(f"- **Alarm features:** {', '.join(active_alarms) or 'None'}")
    lines.append(f"- **H. pylori test done:** {patient_data.get('h_pylori_test_done')}")
    lines.append(f"- **H. pylori positive:** {patient_data.get('h_pylori_result_positive')}")
    lines.append(f"- **PPI OD done/adequate:** {patient_data.get('ppi_once_daily_trial_done')} / {patient_data.get('ppi_once_daily_response_adequate')}")
    lines.append(f"- **PPI BID done/adequate:** {patient_data.get('ppi_bid_trial_done')} / {patient_data.get('ppi_bid_response_adequate')}")
    lines.append("")
    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                lines.append(f"- **[{urgency}]** {_safe_text(o.label)}")
                if isinstance(o.details, dict):
                    for b in o.details.get("bullets", []):   lines.append(f"  - {_safe_text(b)}")
                    for n in o.details.get("notes", []):     lines.append(f"  - Note: {_safe_text(n)}")
                    for s in o.details.get("supported_by", []): lines.append(f"  - Support: {_safe_text(s)}")
                    skip = {"bullets", "notes", "supported_by"}
                    for k, v in o.details.items():
                        if k in skip: continue
                        if isinstance(v, list):
                            for item in v: lines.append(f"  - {k.replace('_',' ').title()}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {k.replace('_',' ').title()}: {_safe_text(v)}")
            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                for a in o.actions: lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing fields: {', '.join(o.missing_fields)}")
                for a in o.suggested_actions: lines.append(f"  - Suggested: {_safe_text(a.label)}")
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

# ═══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL
# ═══════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 45)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Suspected Dyspepsia** — Predominant symptoms (> 1 month)")
    symptom_duration_months = st.number_input(
        "Symptom duration (months)", min_value=0, max_value=240, value=2,
        help="Pathway requires > 1 month",
    )
    predominant_epigastric_pain          = st.checkbox("Predominant epigastric pain")
    predominant_epigastric_discomfort    = st.checkbox("Predominant epigastric discomfort")
    predominant_upper_abdominal_bloating = st.checkbox("Predominant upper abdominal bloating / distension")

    with st.expander("Rome IV support criteria (optional)"):
        postprandial_fullness    = st.checkbox("Postprandial fullness")
        early_satiety            = st.checkbox("Early satiety")
        epigastric_pain_rome     = st.checkbox("Epigastric pain (Rome IV)")
        epigastric_burning       = st.checkbox("Epigastric burning")
        symptom_onset_months_ago = st.number_input(
            "Symptom onset (months ago)", min_value=0, max_value=360, value=0,
            help="Rome IV: onset ≥ 6 months ago",
        )

    st.markdown("**2. Is it GERD?** — Predominant heartburn ± regurgitation")
    predominant_heartburn     = st.checkbox("Predominant heartburn")
    predominant_regurgitation = st.checkbox("Predominant regurgitation")

    st.markdown("**3. Alarm Features**")
    actively_bleeding_now = st.checkbox("⚠️ Actively bleeding NOW (emergency)")
    al_fh_cancer          = st.checkbox("Family hx (1st-degree) esophageal / gastric cancer")
    al_onset_after_60     = st.checkbox("Age > 60 — new & persistent symptoms (> 3 months)")
    al_weight_loss        = st.checkbox("Unintended weight loss > 5% over 6–12 months")
    al_dysphagia          = st.checkbox("Progressive dysphagia")
    al_vomiting           = st.checkbox("Persistent vomiting (not cannabis-related)")
    al_black_stool        = st.checkbox("Black stool or blood in vomit")
    al_ida                = st.checkbox("Iron deficiency anemia")

    st.markdown("**4. Medication & Lifestyle Review**")
    medication_review_done   = st.checkbox("Medication review done (NSAIDs, steroids, metformin, iron…)")
    lifestyle_review_done    = st.checkbox("Lifestyle review done (alcohol, caffeine, smoking, stress)")
    diet_trigger_review_done = st.checkbox("Dietary trigger review done")
    improved_sel = st.selectbox(
        "Symptoms after medication / lifestyle review:",
        ["Not yet assessed", "Improved — no further action needed", "Not improved — continue pathway"],
    )
    improved_map = {
        "Not yet assessed":                       None,
        "Improved — no further action needed":    True,
        "Not improved — continue pathway":        False,
    }

    st.markdown("**5. Baseline Investigations**")
    cbc_sel      = st.selectbox("CBC (mandatory)", ["Not done", "Done — normal", "Done — abnormal"])
    cbc_done_val = cbc_sel in ("Done — normal", "Done — abnormal")
    cbc_abnormal = cbc_sel == "Done — abnormal"

    ferritin_sel = st.selectbox("Ferritin (optional)", ["Not ordered", "Done", "Not done"])
    ferritin_map = {"Not ordered": None, "Done": True, "Not done": False}

    ttg_sel      = st.selectbox("TTG IgA — celiac screen", ["Not ordered", "Done — negative", "Done — positive"])
    ttg_done_val = ttg_sel in ("Done — negative", "Done — positive")
    ttg_positive = ttg_sel == "Done — positive"

    suspect_hepato    = st.checkbox("Suspect hepatobiliary / pancreatic disease")
    hepato_done       = False
    hepato_abnormal   = False
    if suspect_hepato:
        hepato_done     = st.checkbox("Hepatobiliary / pancreatic workup done (U/S, ALT, ALP, bilirubin, lipase)")
        if hepato_done:
            hepato_abnormal = st.checkbox("Hepatobiliary / pancreatic workup abnormal")

    other_dx_found = st.checkbox("Other diagnosis identified on baseline investigations")

    st.markdown("**6. Test and Treat — H. pylori** (HpSAT or UBT)")
    hp_done_sel  = st.selectbox("H. pylori test", ["Not yet done", "Done"])
    hp_done      = hp_done_sel == "Done"
    hp_positive  = None
    if hp_done:
        hp_result_sel = st.selectbox("H. pylori result", ["Negative", "Positive"])
        hp_positive   = hp_result_sel == "Positive"

    st.markdown("**7. Pharmacological Therapy**")
    ppi_od_sel = st.selectbox(
        "PPI once-daily trial (4–8 weeks)",
        ["Not yet started", "Trial done — adequate response", "Trial done — inadequate response"],
    )
    ppi_od_done     = ppi_od_sel != "Not yet started"
    ppi_od_adequate = (
        True  if ppi_od_sel == "Trial done — adequate response"  else
        False if ppi_od_sel == "Trial done — inadequate response" else None
    )

    ppi_bid_done     = None
    ppi_bid_adequate = None
    if ppi_od_sel == "Trial done — inadequate response":
        ppi_bid_sel  = st.selectbox(
            "Optimize PPI twice-daily (4–8 weeks)",
            ["Not yet started", "Trial done — adequate response", "Trial done — inadequate response"],
        )
        ppi_bid_done = True if ppi_bid_sel != "Not yet started" else None
        ppi_bid_adequate = (
            True  if ppi_bid_sel == "Trial done — adequate response"  else
            False if ppi_bid_sel == "Trial done — inadequate response" else None
        )

    symptoms_resolved_after_ppi         = None
    symptoms_return_after_deprescribing = None
    if ppi_od_adequate is True or ppi_bid_adequate is True:
        resolved_sel = st.selectbox(
            "Symptoms resolved after PPI?",
            ["Unknown", "Yes — resolved", "No — persisting"],
        )
        resolved_map = {"Unknown": None, "Yes — resolved": True, "No — persisting": False}
        symptoms_resolved_after_ppi = resolved_map[resolved_sel]
        if symptoms_resolved_after_ppi is True:
            return_sel = st.selectbox(
                "Symptoms returned after deprescribing?",
                ["Unknown / not tried", "Yes — returned", "No — still resolved"],
            )
            return_map = {"Unknown / not tried": None, "Yes — returned": True, "No — still resolved": False}
            symptoms_return_after_deprescribing = return_map[return_sel]

    ecg_qtc_ms       = None
    family_hx_scd    = None
    personal_cardiac = None
    qt_meds          = None
    if ppi_bid_adequate is False:
        st.markdown("**Domperidone Safety Check**")
        ecg_qtc_ms       = st.number_input("ECG QTc (ms)", min_value=300, max_value=700, value=430,
                                            help="Male limit 470 ms | Female limit 450 ms")
        family_hx_scd    = st.checkbox("Family history of sudden cardiac death")
        personal_cardiac = st.checkbox("Personal cardiac history (e.g. heart failure)")
        qt_meds          = st.checkbox("Currently on QT-prolonging medications")

    st.markdown("**Overall Management Response**")
    mgmt_sel = st.selectbox(
        "Response to overall dyspepsia management:",
        ["Not yet assessed", "Satisfactory — continue in medical home", "Unsatisfactory — further action needed"],
    )
    mgmt_map = {
        "Not yet assessed":                         None,
        "Satisfactory — continue in medical home":  False,
        "Unsatisfactory — further action needed":   True,
    }
    advice_considered = False
    if mgmt_sel == "Unsatisfactory — further action needed":
        advice_considered = st.checkbox("Advice service already consulted before referring")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.dys_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.dys_overrides = []
        if "dys_saved_output" in st.session_state:
            del st.session_state["dys_saved_output"]
        st.rerun()

    override_panel = st.container()

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═══════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.dys_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age":  age,
            "sex":  sex,
            "predominant_epigastric_pain":           predominant_epigastric_pain,
            "predominant_epigastric_discomfort":     predominant_epigastric_discomfort,
            "predominant_upper_abdominal_bloating":  predominant_upper_abdominal_bloating,
            "symptom_duration_months":               symptom_duration_months,
            "postprandial_fullness":                 postprandial_fullness or None,
            "early_satiety":                         early_satiety or None,
            "epigastric_pain":                       epigastric_pain_rome or None,
            "epigastric_burning":                    epigastric_burning or None,
            "symptom_onset_months_ago":              symptom_onset_months_ago if symptom_onset_months_ago > 0 else None,
            "predominant_heartburn":                 predominant_heartburn,
            "predominant_regurgitation":             predominant_regurgitation,
            "actively_bleeding_now":                 actively_bleeding_now,
            "family_history_upper_gi_cancer_first_degree": al_fh_cancer,
            "symptom_onset_after_age_60":            al_onset_after_60,
            "unintended_weight_loss":                al_weight_loss,
            "dysphagia":                             al_dysphagia,
            "persistent_vomiting":                   al_vomiting,
            "black_stool_or_blood_in_vomit":         al_black_stool,
            "iron_deficiency_anemia_present":        al_ida,
            "medication_review_done":                medication_review_done,
            "lifestyle_review_done":                 lifestyle_review_done,
            "diet_trigger_review_done":              diet_trigger_review_done,
            "symptoms_improved_after_med_lifestyle_review": improved_map[improved_sel],
            "cbc_done":                              cbc_done_val,
            "cbc_abnormal":                          cbc_abnormal,
            "ferritin_done":                         ferritin_map[ferritin_sel],
            "ttg_iga_done":                          ttg_done_val,
            "ttg_iga_positive":                      ttg_positive,
            "suspect_hepatobiliary_pancreatic_process": suspect_hepato,
            "hepatobiliary_pancreatic_tests_done":   hepato_done,
            "hepatobiliary_pancreatic_workup_abnormal": hepato_abnormal,
            "other_diagnosis_found":                 other_dx_found,
            "h_pylori_test_done":                    hp_done,
            "h_pylori_result_positive":              hp_positive,
            "ppi_once_daily_trial_done":             ppi_od_done if ppi_od_done else None,
            "ppi_once_daily_response_adequate":      ppi_od_adequate,
            "ppi_bid_trial_done":                    ppi_bid_done,
            "ppi_bid_response_adequate":             ppi_bid_adequate,
            "symptoms_resolved_after_ppi":           symptoms_resolved_after_ppi,
            "symptoms_return_after_deprescribing":   symptoms_return_after_deprescribing,
            "ecg_qtc_ms":                            ecg_qtc_ms,
            "family_history_sudden_cardiac_death":   family_hx_scd,
            "personal_cardiac_history":              personal_cardiac,
            "qt_prolonging_medications_present":     qt_meds,
            "unsatisfactory_response_to_management": mgmt_map[mgmt_sel],
            "advice_service_considered":             advice_considered or None,
        }

        outputs, logs, applied_overrides = run_dyspepsia_pathway(
            patient_data, overrides=st.session_state.dys_overrides
        )

        _action_codes   = {o.code for o in outputs if isinstance(o, Action)}
        _stop_act_codes = {a.code for o in outputs if isinstance(o, Stop) for a in o.actions}

        entry_met      = "DYSPEPSIA_ENTRY_MET"           in _action_codes
        entry_not_met  = "NOT_DYSPEPSIA"                 in _stop_act_codes
        routed_gerd    = "ROUTE_GERD_PATHWAY"            in _stop_act_codes
        has_alarm      = "URGENT_ENDOSCOPY_REFERRAL"     in _stop_act_codes
        bleed_stop     = "EMERGENT_BLEEDING_ASSESSMENT"  in _stop_act_codes
        improved_life  = "NO_FURTHER_ACTION_REQUIRED"    in _stop_act_codes
        other_dx       = "OTHER_DIAGNOSIS_IDENTIFIED"    in _stop_act_codes
        routed_hp      = "ROUTE_H_PYLORI_PATHWAY"        in _stop_act_codes
        started_ppi    = "START_PPI_ONCE_DAILY"          in _action_codes
        ppi_od_ok      = "PPI_ONCE_DAILY_SUCCESS"        in _action_codes
        optimize_bid   = "OPTIMIZE_PPI_BID"              in _action_codes
        ppi_bid_ok     = "PPI_BID_SUCCESS"               in _action_codes
        tca_flag       = "CONSIDER_TCA"                  in _action_codes
        dom_eligible   = "DOMPERIDONE_ELIGIBLE"          in _action_codes
        dom_ineligible = "DOMPERIDONE_NOT_ELIGIBLE"      in _action_codes
        titrate_down   = "TITRATE_DOWN_PPI"              in _action_codes
        ppi_maint      = "PPI_MAINTENANCE"               in _action_codes
        pathway_done   = "CONTINUE_MEDICAL_HOME_CARE"    in _stop_act_codes
        refer_endo     = "REFER_FAILED_MANAGEMENT"       in _stop_act_codes

        v0  = True
        v1  = v0
        v2  = entry_met
        v3  = v2 and not routed_gerd
        v4  = v3 and not (has_alarm or bleed_stop)
        v5  = v4 and not improved_life
        v6  = v5 and not other_dx
        v7  = v6 and not routed_hp
        v7d = v7
        v8  = v7d and not ppi_od_ok and optimize_bid
        v8d = v8
        v9  = v8d and not ppi_bid_ok and tca_flag
        v10 = titrate_down or ppi_maint
        v11 = pathway_done or refer_endo

        # ── COLORS ────────────────────────────────────────────────────────────
        C_MAIN    = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT  = "#dc2626"
        C_EXIT    = "#d97706"
        C_TEXT    = "#ffffff"
        C_DIM     = "#94a3b8"
        C_BG      = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis:   return C_UNVISIT
            if urgent:    return C_URGENT
            if exit_:     return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def _mid(vis, urgent=False, exit_=False):
            if not vis:   return "ma"
            if urgent:    return "mr"
            if exit_:     return "mo"
            return "mg"

        def _stroke(vis, urgent=False, exit_=False):
            if not vis:   return "#64748b"
            if urgent:    return C_URGENT
            if exit_:     return C_EXIT
            return C_MAIN

        svg = []
        # Canvas: wider to accommodate left/right exit boxes comfortably
        W, H = 820, 1380
        svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" '
            f'viewBox="0 0 {W} {H}" '
            f'style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append(
            "<defs>"
            + "".join(
                f'<marker id="{mid}" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
                f'<path d="M0,0 L0,6 L9,3 z" fill="{col}"/></marker>'
                for mid, col in [("ma","#64748b"),("mg",C_MAIN),("mr",C_URGENT),("mo",C_EXIT)]
            )
            + "</defs>"
        )

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
                f'fill="{fill}" font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>'
            )

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                        f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-8,  line1, tc, 11, True)
                svgt(x+w/2, y+h/2+7,  line2, tc, 11, True)
            else:
                svgt(x+w/2, y+h/2+4,  line1, tc, 11, True)
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
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                        f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x+w/2, y+h/2-7, line1, tc, 10, True)
                svgt(x+w/2, y+h/2+7, line2, tc, 9)
            else:
                svgt(x+w/2, y+h/2+4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label="", label_side="right"):
            m = _mid(vis, urgent, exit_); s = _stroke(vis, urgent, exit_)
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                        f'stroke="{s}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                lx = x + 6 if label_side == "right" else x - 6
                anchor = "start" if label_side == "right" else "end"
                svgt(lx, (y1+y2)/2-3, label, s, 10, True, anchor)

        def elbow(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            """Horizontal then vertical elbow (go right/left to x2, then up/down to y2)"""
            m = _mid(vis, urgent, exit_); s = _stroke(vis, urgent, exit_)
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                        f'fill="none" stroke="{s}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, s, 10, True)

        def elbow_down_right(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            """Vertical then horizontal elbow (go down to y2, then right/left to x2)"""
            m = _mid(vis, urgent, exit_); s = _stroke(vis, urgent, exit_)
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x1},{y2} {x2},{y2}" '
                        f'fill="none" stroke="{s}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x1+6, (y1+y2)/2, label, s, 10, True, "start")

        # ── LAYOUT CONSTANTS ──────────────────────────────────────────────────
        CX = 410          # horizontal centre of main spine
        NW, NH = 200, 48  # main rect node width/height
        DW, DH = 210, 62  # diamond width/height
        EW, EH = 155, 42  # exit/side box width/height

        # left exit boxes start x
        LX = 12
        # right exit boxes start x
        RX = W - 12 - EW

        # Y positions (top edge of each element)
        Y = {
            "d1":    12,    # 1. Suspected Dyspepsia? (diamond)
            "d2":   120,    # 2. Is it GERD? (diamond)
            "d3":   228,    # 3. Alarm Features? (diamond)
            "n4":   336,    # 4. Med/Lifestyle Review (rect)
            "d4":   406,    # Symptoms Improved? (diamond)
            "n5":   506,    # 5. Baseline Investigations (rect)
            "n6":   590,    # 6. H. pylori (rect — shown as diamond in PDF but used as rect action)
            "d6":   590,    # 6. H. pylori (diamond)
            "n7":   700,    # 7. PPI OD trial (rect)
            "d7":   768,    # PPI OD adequate? (diamond)
            "n8":   876,    # Optimize PPI BID (rect)
            "d8":   944,    # PPI BID adequate? (diamond)
            "n9":  1052,    # TCA / Domperidone optional (rect)
            "n10": 1140,    # PPI Maintenance / Deprescribing (rect)
            "term":1230,    # terminal row (Pathway Complete / Refer)
        }

        # ── NODE 1: Suspected Dyspepsia ───────────────────────────────────────
        diamond_node(CX, Y["d1"]+DH/2, DW, DH, dc(v1), "1. Suspected", "Dyspepsia?")
        # Left exit: criteria not met
        exit_node(LX, Y["d1"]+(DH-EH)//2, EW, EH, nc(entry_not_met, exit_=True), "Criteria", "Not Met")
        elbow(CX-DW/2, Y["d1"]+DH/2, LX+EW, Y["d1"]+(DH-EH)//2+EH//2, entry_not_met, exit_=True, label="No")

        vline(CX, Y["d1"]+DH, Y["d2"], v2, label="Yes")

        # ── NODE 2: Is it GERD? ───────────────────────────────────────────────
        diamond_node(CX, Y["d2"]+DH/2, DW, DH, dc(v2), "2. Is it GERD?", "Heartburn / regurgitation?")
        # Right exit: GERD pathway
        exit_node(RX, Y["d2"]+(DH-EH)//2, EW, EH, nc(routed_gerd, exit_=True), "→ GERD", "Pathway")
        elbow(CX+DW/2, Y["d2"]+DH/2, RX, Y["d2"]+(DH-EH)//2+EH//2, routed_gerd, exit_=True, label="Yes")

        vline(CX, Y["d2"]+DH, Y["d3"], v3, label="No")

        # ── NODE 3: Alarm Features? ───────────────────────────────────────────
        diamond_node(CX, Y["d3"]+DH/2, DW, DH, dc(v3), "3. Alarm Features?")
        # Right exit: urgent endoscopy
        exit_node(RX, Y["d3"]+(DH-EH)//2, EW, EH, nc(has_alarm or bleed_stop, urgent=True), "⚠ Urgent Refer", "Endoscopy / ED")
        elbow(CX+DW/2, Y["d3"]+DH/2, RX, Y["d3"]+(DH-EH)//2+EH//2, has_alarm or bleed_stop, urgent=True, label="Yes")

        vline(CX, Y["d3"]+DH, Y["n4"], v4, label="No")

        # ── NODE 4: Medication & Lifestyle Review ─────────────────────────────
        rect_node(CX-NW//2, Y["n4"], NW, NH, nc(v4), "4. Medication &", "Lifestyle Review")
        vline(CX, Y["n4"]+NH, Y["d4"], v4)
        diamond_node(CX, Y["d4"]+DH/2, DW, DH, dc(v4), "Symptoms", "Improved?")
        # Right exit: no further action
        exit_node(RX, Y["d4"]+(DH-EH)//2, EW, EH, nc(improved_life, exit_=True), "No Further", "Action Req'd")
        elbow(CX+DW/2, Y["d4"]+DH/2, RX, Y["d4"]+(DH-EH)//2+EH//2, improved_life, exit_=True, label="Yes")

        vline(CX, Y["d4"]+DH, Y["n5"], v5, label="No")

        # ── NODE 5: Baseline Investigations ──────────────────────────────────
        rect_node(CX-NW//2, Y["n5"], NW, NH, nc(v5), "5. Baseline", "Investigations")
        # Left exit: abnormal → other dx
        exit_node(LX, Y["n5"]+(NH-EH)//2, EW, EH, nc(other_dx, exit_=True), "Other Dx Found", "Treat / Refer")
        elbow(CX-NW//2, Y["n5"]+NH//2, LX+EW, Y["n5"]+(NH-EH)//2+EH//2, other_dx, exit_=True, label="Abnormal")

        vline(CX, Y["n5"]+NH, Y["d6"], v6)

        # ── NODE 6: H. pylori Test & Treat ────────────────────────────────────
        diamond_node(CX, Y["d6"]+DH/2, DW, DH, dc(v6), "6. H. pylori", "Test & Treat")
        # Right exit: positive → H. pylori pathway
        exit_node(RX, Y["d6"]+(DH-EH)//2, EW, EH, nc(routed_hp, exit_=True), "→ H. pylori", "Pathway")
        elbow(CX+DW/2, Y["d6"]+DH/2, RX, Y["d6"]+(DH-EH)//2+EH//2, routed_hp, exit_=True, label="+ve")

        vline(CX, Y["d6"]+DH, Y["n7"], v7, label="−ve")

        # ── NODE 7: PPI Once-Daily Trial ──────────────────────────────────────
        rect_node(CX-NW//2, Y["n7"], NW, NH, nc(v7), "7. PPI Trial", "Once Daily  4–8 wks")
        vline(CX, Y["n7"]+NH, Y["d7"], v7d)

        # PPI OD adequate? (diamond)
        diamond_node(CX, Y["d7"]+DH/2, DW, DH, dc(v7d), "PPI OD", "Adequate Response?")

        # LEFT exit: PPI OD adequate → "Titrate Down / Maintain PPI"
        # This box sits to the LEFT at the same Y as the diamond
        titrate_od_y = Y["d7"] + (DH - EH) // 2
        exit_node(LX, titrate_od_y, EW, EH, nc(ppi_od_ok, exit_=True), "Titrate Down /", "Maintain PPI")
        elbow(CX-DW//2, Y["d7"]+DH//2, LX+EW, titrate_od_y+EH//2, ppi_od_ok, exit_=True, label="Yes")

        # "Titrate Down" → connects DOWN and then RIGHT into Maintenance node (n10)
        # Uses vertical drop from bottom of exit box, then horizontal to left edge of n10
        if ppi_od_ok:
            s = C_EXIT; m = "mo"
        else:
            s = "#64748b"; m = "ma"
        maint_mid_y = Y["n10"] + NH // 2
        maint_left_x = CX - NW // 2
        titrate_od_bottom = titrate_od_y + EH
        titrate_od_cx = LX + EW // 2
        svg.append(
            f'<polyline points="'
            f'{titrate_od_cx},{titrate_od_bottom} '
            f'{titrate_od_cx},{maint_mid_y} '
            f'{maint_left_x},{maint_mid_y}" '
            f'fill="none" stroke="{s}" stroke-width="2" '
            f'{"" if ppi_od_ok else "stroke-dasharray=\"5,3\""} '
            f'marker-end="url(#{m})"/>'
        )

        vline(CX, Y["d7"]+DH, Y["n8"], v8, label="No — optimize")

        # ── NODE 8: Optimize PPI BID ──────────────────────────────────────────
        rect_node(CX-NW//2, Y["n8"], NW, NH, nc(v8), "Optimize PPI", "Twice Daily  4–8 wks")
        vline(CX, Y["n8"]+NH, Y["d8"], v8d)

        # PPI BID adequate? (diamond)
        diamond_node(CX, Y["d8"]+DH/2, DW, DH, dc(v8d), "PPI BID", "Adequate Response?")

        # LEFT exit: PPI BID adequate → "Titrate Down / Maintain PPI"
        titrate_bid_y = Y["d8"] + (DH - EH) // 2
        exit_node(LX, titrate_bid_y, EW, EH, nc(ppi_bid_ok, exit_=True), "Titrate Down /", "Maintain PPI")
        elbow(CX-DW//2, Y["d8"]+DH//2, LX+EW, titrate_bid_y+EH//2, ppi_bid_ok, exit_=True, label="Yes")

        # "Titrate Down (BID)" → connects to Maintenance node from left
        if ppi_bid_ok:
            s2 = C_EXIT; m2 = "mo"
        else:
            s2 = "#64748b"; m2 = "ma"
        titrate_bid_bottom = titrate_bid_y + EH
        titrate_bid_cx = LX + EW // 2
        svg.append(
            f'<polyline points="'
            f'{titrate_bid_cx},{titrate_bid_bottom} '
            f'{titrate_bid_cx},{maint_mid_y} '
            f'{maint_left_x},{maint_mid_y}" '
            f'fill="none" stroke="{s2}" stroke-width="2" '
            f'{"" if ppi_bid_ok else "stroke-dasharray=\"5,3\""} '
            f'marker-end="url(#{m2})"/>'
        )

        vline(CX, Y["d8"]+DH, Y["n9"], v9, label="No")

        # ── NODE 9: TCA / Domperidone optional ───────────────────────────────
        rect_node(CX-NW//2, Y["n9"], NW, NH, nc(v9), "TCA Trial", sub="Optional / while awaiting consult")
        # Right side: domperidone eligibility
        dom_vis = v9 and (dom_eligible or dom_ineligible)
        dom_col = nc(dom_vis, exit_=dom_eligible) if dom_vis else C_UNVISIT
        exit_node(RX, Y["n9"]+(NH-EH)//2, EW, EH, dom_col,
                  "Domperidone", "Eligible" if dom_eligible else ("Ineligible" if dom_ineligible else "?"))
        elbow(CX+NW//2, Y["n9"]+NH//2, RX, Y["n9"]+(NH-EH)//2+EH//2, dom_vis, exit_=dom_eligible, label="Check")

        vline(CX, Y["n9"]+NH, Y["n10"], v10)

        # ── NODE 10: PPI Maintenance / Deprescribing ──────────────────────────
        rect_node(CX-NW//2, Y["n10"], NW, NH, nc(v10), "PPI Maintenance /", "Deprescribing")

        # Maintenance → dashed split to two terminal nodes
        vline(CX, Y["n10"]+NH, Y["term"], v11)

        # ── TERMINAL ROW ──────────────────────────────────────────────────────
        term_EW = 175
        gap = 20
        # Left terminal: Pathway Complete / Medical Home
        left_term_x  = CX - gap//2 - term_EW
        right_term_x = CX + gap//2

        exit_node(left_term_x, Y["term"], term_EW, EH, nc(pathway_done, exit_=True),
                  "Pathway Complete", "Medical Home")
        exit_node(right_term_x, Y["term"], term_EW, EH, nc(refer_endo, urgent=True),
                  "8. Refer", "Consult / Endoscopy")

        # Connector from spine into each terminal box
        spine_bottom = Y["term"]
        if v11:
            # horizontal T-bar at spine_bottom connecting to both boxes
            s_t = C_MAIN if pathway_done or refer_endo else "#64748b"
            m_t = "mg" if pathway_done or refer_endo else "ma"
            # Left branch
            sl = C_EXIT if pathway_done else "#64748b"
            ml = "mo" if pathway_done else "ma"
            svg.append(
                f'<polyline points="{CX},{spine_bottom} {CX},{spine_bottom+18} '
                f'{left_term_x+term_EW//2},{spine_bottom+18} {left_term_x+term_EW//2},{Y["term"]}" '
                f'fill="none" stroke="{sl}" stroke-width="2" '
                f'{"" if pathway_done else "stroke-dasharray=\"5,3\""} marker-end="url(#{ml})"/>'
            )
            # Right branch
            sr = C_URGENT if refer_endo else "#64748b"
            mr = "mr" if refer_endo else "ma"
            svg.append(
                f'<polyline points="{CX},{spine_bottom} {CX},{spine_bottom+18} '
                f'{right_term_x+term_EW//2},{spine_bottom+18} {right_term_x+term_EW//2},{Y["term"]}" '
                f'fill="none" stroke="{sr}" stroke-width="2" '
                f'{"" if refer_endo else "stroke-dasharray=\"5,3\""} marker-end="url(#{mr})"/>'
            )

        # ── LEGEND ────────────────────────────────────────────────────────────
        ly = H - 18; lx = 14
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit / Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 140
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=H + 30, scrolling=True,
        )

        # ── CLINICAL RECOMMENDATIONS ──────────────────────────────────────────
        st.markdown("---")
        st.subheader("Clinical Recommendations")

        alarm_display = [
            ("family_history_upper_gi_cancer_first_degree", "Family hx upper GI cancer"),
            ("symptom_onset_after_age_60",   "Onset after age 60"),
            ("unintended_weight_loss",        "Weight loss > 5%"),
            ("black_stool_or_blood_in_vomit", "Black stool / blood in vomit"),
            ("dysphagia",                    "Progressive dysphagia"),
            ("persistent_vomiting",           "Persistent vomiting"),
            ("iron_deficiency_anemia_present","Iron deficiency anemia"),
        ]
        active_alarms_disp = [lbl for k, lbl in alarm_display if patient_data.get(k)]
        alarm_str = ", ".join(active_alarms_disp) if active_alarms_disp else "None"

        ppi_str = (
            "OD trial adequate"                      if ppi_od_ok       else
            "BID trial adequate"                     if ppi_bid_ok      else
            "BID inadequate → TCA/Domperidone"       if tca_flag        else
            "OD trial started (awaiting response)"   if started_ppi     else
            "Not yet started"
        )
        hp_str = (
            "Positive → H. pylori pathway" if routed_hp else
            "Negative"                      if (hp_done and hp_positive is False) else
            "Not yet done"
        )

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Symptom Duration:</b> {symptom_duration_months} months</span><br>'
            f'<span><b>H. pylori:</b> {hp_str}</span><br>'
            f'<span><b>PPI Status:</b> {ppi_str}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span><br>'
            f'<span><b>GERD Routed:</b> {"Yes — follow GERD pathway" if routed_gerd else "No"}</span>'
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
                    if k in skip: continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls
            badge_label = (a.urgency or "info").upper()
            label_html  = html.escape(a.label).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">'
                "🔒 Override available — reason required</p>"
                if a.override_options else ""
            )
            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{detail_html}{override_html}</div>",
                unsafe_allow_html=True,
            )
            if a.override_options:
                override_candidates.append(a)

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        # ── Grouping logic ────────────────────────────────────────────────────
        # 1) Status/support-only chips at the top
        STATUS_CODES = {
            "DYSPEPSIA_ENTRY_MET",
            "NOT_PREDOMINANT_GERD",     # engine code NOTPREDOMINANTGERD
            "NO_ALARM_FEATURES",        # engine code NOALARMFEATURES
            "HPYLORI_NEGATIVE_OR_TREATED",  # engine code HPYLORINEGATIVEORTREATED
            "MEDICATION_LIFESTYLE_REVIEWED",  # engine code MEDICATIONLIFESTYLEREVIEWED
        }

        # 2) Medication & lifestyle review suggestions
        MED_LIFE_CODES = {
            "REVIEW_MEDICATIONS",
            "REVIEW_LIFESTYLE",
            "REVIEW_DIET_TRIGGERS",
        }

        # 3) Baseline investigation suggestions
        BASELINE_CODES = {
            "CONSIDER_CBC",
            "CONSIDER_FERRITIN",
            "CONSIDER_TTG_IGA",
            "CONSIDER_HEPATOBILIARY_PANCREATIC_TESTS",
        }

        # Map engine codes to these group keys
        code_alias = {
            "DYSPEPSIAENTRYMET": "DYSPEPSIA_ENTRY_MET",
            "NOTPREDOMINANTGERD": "NOT_PREDOMINANT_GERD",
            "NOALARMFEATURES": "NO_ALARM_FEATURES",
            "HPYLORINEGATIVEORTREATED": "HPYLORI_NEGATIVE_OR_TREATED",
            "MEDICATIONLIFESTYLEREVIEWED": "MEDICATION_LIFESTYLE_REVIEWED",
            "REVIEWMEDICATIONS": "REVIEW_MEDICATIONS",
            "REVIEWLIFESTYLE": "REVIEW_LIFESTYLE",
            "REVIEWDIETTRIGGERS": "REVIEW_DIET_TRIGGERS",
            "CONSIDERCBC": "CONSIDER_CBC",
            "CONSIDERFERRITIN": "CONSIDER_FERRITIN",
            "CONSIDERTTGIGA": "CONSIDER_TTG_IGA",
            "CONSIDERHEPATOBILIARYPANCREATICTESTS": "CONSIDER_HEPATOBILIARY_PANCREATIC_TESTS",
        }

        status_actions = []
        med_life_actions = []
        baseline_actions = []
        rendered_codes = set()

        # Pre‑scan outputs to populate groups
        for o in outputs:
            if not isinstance(o, Action):
                continue
            key = code_alias.get(o.code)
            if key in STATUS_CODES:
                status_actions.append(o)
                rendered_codes.add(o.code)
            elif key in MED_LIFE_CODES:
                med_life_actions.append(o)
                rendered_codes.add(o.code)
            elif key in BASELINE_CODES:
                baseline_actions.append(o)
                rendered_codes.add(o.code)

        # ── Status chips (entry, “not GERD”, no alarms, H. pylori, etc.) ─────
        if status_actions:
            chips = ""
            for a in status_actions:
                chips += (
                    '<span style="display:inline-block;'
                    'background:#0c2a1e;border:1px solid #166534;'
                    'color:#86efac;border-radius:20px;padding:3px 10px;'
                    'font-size:11px;margin:2px 4px 2px 0;">'
                    f'✓ {html.escape(a.label)}</span>'
                )
            st.markdown(
                f'<div style="margin-bottom:10px;line-height:2">{chips}</div>',
                unsafe_allow_html=True,
            )

        # ── Grouped card: Medication & lifestyle review ───────────────────────
        if med_life_actions:
            bullets = "".join(
                f">{html.escape(a.label)}</li>" for a in med_life_actions
            )
            st.markdown(
                '<div class="action-card routine">'
                '<h4><span class="badge routine">INFO</span> '
                '4. Medication & Lifestyle Review</h4>'
                f'<ul style="margin:8px 0 0 16px;padding:0;line-height:1.7">{bullets}</ul>'
                "</div>",
                unsafe_allow_html=True,
            )

        # ── Grouped card: Baseline investigations ─────────────────────────────
        if baseline_actions:
            bullets = "".join(
                f">{html.escape(a.label)}</li>" for a in baseline_actions
            )
            st.markdown(
                '<div class="action-card info">'
                '<h4><span class="badge info">INFO</span> '
                '5. Baseline Investigations</h4>'
                f'<ul style="margin:8px 0 0 16px;padding:0;line-height:1.7">{bullets}</ul>'
                "</div>",
                unsafe_allow_html=True,
            )

        # ── Render remaining outputs as usual ─────────────────────────────────
        for output in outputs:
            if isinstance(output, Action):
                if output.code in rendered_codes:
                    continue  # already shown in a group
                render_action(output)

            elif isinstance(output, DataRequest):
                missing_str = ", ".join(f"`{f}`" for f in output.missing_fields)
                msg_html = html.escape(output.message).replace("\\n", "<br>")
                st.markdown(
                    '<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span>'
                    f' ⏳ {msg_html}</h4>'
                    f"<ul>>Missing fields: {missing_str}</li></ul>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")

            elif isinstance(output, Stop):
                reason_html = (
                    html.escape(output.reason)
                    .replace("\\n   ", "<br>&nbsp;&nbsp;&nbsp;")
                    .replace("\\n", "<br>")
                )
                st.markdown(
                    '<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span>'
                    f" 🛑 {reason_html}</h4>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        # ── CLINICIAN NOTES ───────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.dys_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.dys_notes,
            height=180,
        )

        # ── SAVE / DOWNLOAD ───────────────────────────────────────────────────
        def _serialize(o):
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
                "engine_outputs":   [_serialize(o) for o in outputs],
                "overrides":        [
                    {"node": o.target_node, "field": o.field,
                     "new_value": o.new_value, "reason": o.reason,
                     "created_at": o.created_at.isoformat()}
                    for o in st.session_state.dys_overrides
                ],
                "clinician_notes":  st.session_state.dys_notes,
            },
        }

        if st.button("💾 Save this output", key="dys_save"):
            st.session_state.dys_saved_output = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        if "dys_saved_output" in st.session_state:
            md_text = build_dyspepsia_markdown(patient_data, outputs,
                                               st.session_state.dys_overrides, st.session_state.dys_notes)
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="dyspepsia_summary.md",
                mime="text/markdown",
                key="dys_dl_md",
            )

        # ── CLINICIAN OVERRIDES PANEL ─────────────────────────────────────────
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
                    raw_node, raw_field = opt["node"], opt["field"]
                    allowed = opt.get("allowed", [True, False])
                    with st.expander(f"⚙️ Override: **{_pretty(raw_node)}** → `{_pretty(raw_field)}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(
                            f'<div class="override-card">Engine decision: <b>{html.escape(preview)}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (o for o in st.session_state.dys_overrides
                             if o.target_node == raw_node and o.field == raw_field), None,
                        )
                        current_val = existing.new_value if existing else None
                        new_val = st.radio(
                            f"Set `{_pretty(raw_field)}` to:",
                            options=allowed,
                            index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}", horizontal=True,
                        )
                        reason = st.text_input(
                            "Reason (required):", value=existing.reason if existing else "",
                            key=f"ov_reason_{raw_node}_{raw_field}",
                            placeholder="Document clinical rationale...",
                        )
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required.")
                                else:
                                    st.session_state.dys_overrides = [
                                        o for o in st.session_state.dys_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.dys_overrides.append(
                                        Override(target_node=raw_node, field=raw_field,
                                                 old_value=None, new_value=new_val, reason=reason.strip())
                                    )
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with c2:
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
                        f'🛠 <b>{html.escape(_pretty(o.target_node))}</b>'
                        f' → <code>{html.escape(_pretty(o.field))}</code>'
                        f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                        f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                        f'<span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                        "</div>",
                        unsafe_allow_html=True,
                    )

        # ── DECISION AUDIT LOG ────────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except: ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
