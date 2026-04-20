import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime

import streamlit as st

from dyspepsia_engine import (
    run_dyspepsia_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

from pathway_handoff import apply_handoff, queue_handoff, show_handoff_banner, HANDOFF_KEY

st.set_page_config(page_title="Dyspepsia", page_icon="🩺", layout="wide")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_dyspepsia_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Dyspepsia Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(
        f"- **Age / Sex:** {patient_data.get('age')} / "
        f"{str(patient_data.get('sex', '')).capitalize()}"
    )
    lines.append(f"- **Symptom duration:** {patient_data.get('symptom_duration_months')} months")
    
    symptoms = []
    if patient_data.get("predominant_epigastric_pain"): symptoms.append("Epigastric pain")
    if patient_data.get("predominant_epigastric_discomfort"): symptoms.append("Epigastric discomfort")
    if patient_data.get("predominant_upper_abdominal_bloating"): symptoms.append("Upper abdominal bloating")
    lines.append(f"- **Predominant symptoms:** {', '.join(symptoms) or 'None documented'}")
    
    alarm_keys = [
        ("family_history_upper_gi_cancer_first_degree", "Family hx upper GI cancer"),
        ("symptom_onset_after_age_60", "Onset after 60"),
        ("unintended_weight_loss", "Weight loss >5%"),
        ("black_stool_or_blood_in_vomit", "Black stool/blood in vomit"),
        ("dysphagia", "Progressive dysphagia"),
        ("persistent_vomiting", "Persistent vomiting"),
        ("iron_deficiency_anemia_present", "Iron deficiency anemia"),
    ]
    active_alarms = [lbl for k, lbl in alarm_keys if patient_data.get(k)]
    lines.append(f"- **Alarm features:** {', '.join(active_alarms) or 'None'}")
    lines.append(f"- **H. pylori test done:** {patient_data.get('h_pylori_test_done')}")
    lines.append(f"- **H. pylori positive:** {patient_data.get('h_pylori_result_positive')}")
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
            elif isinstance(o, Stop):
                reason = _safe_text(o.reason)
                lines.append(f"- **[STOP]** {reason}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                msg = _safe_text(o.message)
                missing = ", ".join(f for f in o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {msg}")
                lines.append(f"  - Missing fields: {missing}")
    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}."
                f"{_safe_text(ov.field)}** → "
                f"`{_safe_text(ov.new_value)}` "
                f"(Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(
        notes.strip() if notes and notes.strip() else "No clinician notes entered."
    )
    lines.append("")
    return "\n".join(lines)


# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
.ctx-card {
  background:#1e3a5f;border:1px solid #2e5c8a;
  border-radius:10px;padding:14px 18px;
  margin-bottom:14px;font-size:14px;color:#e2e8f0;
}
.ctx-card b { color:#93c5fd; }
.section-label {
  font-size:11px;font-weight:700;letter-spacing:1.2px;
  color:#94a3b8;margin-bottom:6px;margin-top:18px;
}
.action-card {
  border-radius:10px;padding:14px 18px;
  margin-bottom:12px;font-size:13.5px;line-height:1.6;
}
.action-card.urgent {background:#3b0a0a;border-left:5px solid #ef4444;color:#fecaca;}
.action-card.routine{background:#052e16;border-left:5px solid #22c55e;color:#bbf7d0;}
.action-card.info   {background:#0c1a2e;border-left:5px solid #3b82f6;color:#bfdbfe;}
.action-card.warning{background:#2d1a00;border-left:5px solid #f59e0b;color:#fde68a;}
.action-card.stop   {background:#2d0a0a;border-left:5px solid #ef4444;color:#fecaca;}
.badge{
  display:inline-block;font-size:11px;font-weight:bold;
  padding:2px 8px;border-radius:20px;margin-right:6px;
  text-transform:uppercase;letter-spacing:0.5px;
}
.badge.urgent{background:#ef4444;color:#fff;}
.badge.routine{background:#22c55e;color:#fff;}
.badge.info{background:#3b82f6;color:#fff;}
.badge.warning{background:#f59e0b;color:#000;}
.badge.stop{background:#ef4444;color:#fff;}
.override-card{
  background:#1a1a2e;border:1px dashed #6366f1;
  border-radius:8px;padding:10px 14px;margin-top:8px;
  font-size:13px;color:#c7d2fe;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Dyspepsia")
st.markdown("---")

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "dys_overrides" not in st.session_state:
    st.session_state.dys_overrides = []
if "dys_has_run" not in st.session_state:
    st.session_state.dys_has_run = False
if "dys_notes" not in st.session_state:
    st.session_state.dys_notes = ""


# ── HANDOFF INBOUND ──────────────────────────────────────────────────────────
_dys_handoff = apply_handoff("3_Dyspepsia")
if _dys_handoff:
    transferred = []
    if _dys_handoff.get("age") is not None:
        st.session_state["_do_age"] = int(_dys_handoff["age"])
        transferred.append("age")
    if _dys_handoff.get("sex"):
        st.session_state["_do_sex"] = _dys_handoff["sex"]
        transferred.append("sex")

    if _dys_handoff.get("predominant_heartburn"):
        st.session_state["_do_heartburn"] = True
        transferred.append("predominant_heartburn")
    if _dys_handoff.get("predominant_regurgitation"):
        st.session_state["_do_regurg"] = True
        transferred.append("predominant_regurgitation")

    if _dys_handoff.get("h_pylori_result_positive") is not None:
        st.session_state["_do_hpdone"] = "Done"
        st.session_state["_do_hpresult"] = (
            "Positive" if _dys_handoff["h_pylori_result_positive"] else "Negative"
        )
        transferred.extend(
            ["h_pylori_test_done", "h_pylori_result_positive"]
        )
    elif _dys_handoff.get("hp_test_result") in ("positive", "negative"):
        st.session_state["_do_hpdone"] = "Done"
        st.session_state["_do_hpresult"] = _dys_handoff["hp_test_result"].capitalize()
        transferred.append("hp_test_result")

    alarm_map = [
        ("actively_bleeding_now", "do_al_bleeding"),
        ("family_history_upper_gi_cancer_first_degree", "do_al_cancer"),
        ("symptom_onset_after_age_60", "do_al_age60"),
        ("unintended_weight_loss", "do_al_wl"),
        ("dysphagia", "do_al_dys"),
        ("persistent_vomiting", "do_al_vomit"),
        ("black_stool_or_blood_in_vomit", "do_al_bleed"),
        ("iron_deficiency_anemia_present", "do_al_ida"),
    ]
    for src, dst in alarm_map:
        if _dys_handoff.get(src):
            st.session_state[f"_{dst}"] = True
            transferred.append(src)

    show_handoff_banner("GERD / H. Pylori", transferred)

left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    col_age, col_sex = st.columns(2)
    with col_age:
        age = st.number_input("Age", 1, 120, value=st.session_state.pop("_do_age", 45))
    with col_sex:
        sex = st.selectbox("Sex", ["male", "female"], index=["male", "female"].index(st.session_state.pop("_do_sex", "male")))

    st.markdown("**1. Suspected Dyspepsia — Entry Criteria**")
    symptom_duration_months = st.number_input(
        "Symptom duration (months)",
        min_value=0, max_value=240, value=2,
        help="Pathway requires > 1 month",
    )
    predominant_epigastric_pain = st.checkbox("Predominant epigastric pain")
    predominant_epigastric_discomfort = st.checkbox("Predominant epigastric discomfort")
    predominant_upper_abdominal_bloating = st.checkbox("Predominant upper abdominal bloating / distension")

    with st.expander("Rome IV support criteria (optional)"):
        postprandial_fullness = st.checkbox("Postprandial fullness")
        early_satiety = st.checkbox("Early satiety")
        epigastric_pain_rome = st.checkbox("Epigastric pain (Rome IV)")
        epigastric_burning = st.checkbox("Epigastric burning")
        symptom_onset_months_ago = st.number_input("Symptom onset (months ago)", min_value=0, max_value=360, value=0)

    st.markdown("**2. Is it GERD?**")
    predominant_heartburn = st.checkbox("Predominant heartburn", value=st.session_state.pop("_do_heartburn", False))
    predominant_regurgitation = st.checkbox("Predominant regurgitation", value=st.session_state.pop("_do_regurg", False))

    st.markdown("**3. Alarm Features**")
    actively_bleeding_now = st.checkbox("Actively bleeding NOW (emergency)", value=st.session_state.pop("_do_al_bleeding", False))
    al_fh_cancer = st.checkbox("Family hx 1st-degree upper GI cancer", value=st.session_state.pop("_do_al_cancer", False))
    al_onset_after_60 = st.checkbox("Onset after age 60", value=st.session_state.pop("_do_al_age60", False))
    al_weight_loss = st.checkbox("Unintended weight loss >5% over 6–12 months", value=st.session_state.pop("_do_al_wl", False))
    al_dysphagia = st.checkbox("Progressive dysphagia", value=st.session_state.pop("_do_al_dys", False))
    al_vomiting = st.checkbox("Persistent vomiting", value=st.session_state.pop("_do_al_vomit", False))
    al_black_stool = st.checkbox("Black stool or blood in vomit", value=st.session_state.pop("_do_al_bleed", False))
    al_ida = st.checkbox("Iron deficiency anemia", value=st.session_state.pop("_do_al_ida", False))

    st.markdown("**4. Medication & Lifestyle Review**")
    medication_review_done = st.checkbox("Medication review done (NSAIDs, steroids, metformin, iron…)")
    lifestyle_review_done = st.checkbox("Lifestyle review done (alcohol, caffeine, smoking, stress)")
    diet_trigger_review_done = st.checkbox("Dietary trigger review done")
    improved_sel = st.selectbox(
        "Symptoms after medication / lifestyle review:",
        ["Not yet assessed", "Improved — no further action needed", "Not improved — continue pathway"],
    )
    improved_map = {"Not yet assessed": None, "Improved — no further action needed": True, "Not improved — continue pathway": False}

    st.markdown("**5. Baseline Investigations**")
    cbc_sel = st.selectbox("CBC (mandatory)", ["Not done", "Done normal", "Done abnormal"])
    cbc_done_val = cbc_sel in ("Done normal", "Done abnormal")
    cbc_abnormal = cbc_sel == "Done abnormal"

    ferritin_sel = st.selectbox("Ferritin (optional)", ["Not ordered", "Done", "Not done"])
    ferritin_map = {"Not ordered": None, "Done": True, "Not done": False}

    ttg_sel = st.selectbox("TTG IgA – celiac screen", ["Not ordered", "Done negative", "Done positive"])
    ttg_done_val = ttg_sel in ("Done negative", "Done positive")
    ttg_positive = ttg_sel == "Done positive"

    suspect_hepato = st.checkbox("Suspect hepatobiliary / pancreatic disease")
    hepato_done = False
    hepato_abnormal = False
    if suspect_hepato:
        hepato_done = st.checkbox("Hepatobiliary / pancreatic workup done (U/S, ALT, ALP, bilirubin, lipase)")
        if hepato_done:
            hepato_abnormal = st.checkbox("Hepatobiliary / pancreatic workup abnormal")
    other_dx_found = st.checkbox("Other diagnosis identified on baseline investigations")

    st.markdown("**6. Test and Treat — H. pylori**")
    hp_done_sel = st.selectbox(
        "H. pylori test", ["Not yet done", "Done"],
        index=["Not yet done", "Done"].index(st.session_state.pop("_do_hpdone", "Not yet done"))
    )
    hp_done = hp_done_sel == "Done"
    hp_positive = None
    if hp_done:
        hp_result_sel = st.selectbox(
            "H. pylori result", ["Negative", "Positive"],
            index=["Negative", "Positive"].index(st.session_state.pop("_do_hpresult", "Negative"))
        )
        hp_positive = hp_result_sel == "Positive"

    st.markdown("**7. Pharmacological Therapy**")
    ppi_od_sel = st.selectbox(
        "PPI once-daily trial (4–8 weeks)",
        ["Not yet started", "Trial done adequate response", "Trial done inadequate response"]
    )
    ppi_od_done = ppi_od_sel != "Not yet started"
    ppi_od_adequate = True if ppi_od_sel == "Trial done adequate response" else False if ppi_od_sel == "Trial done inadequate response" else None

    ppi_bid_done = None
    ppi_bid_adequate = None
    if ppi_od_sel == "Trial done inadequate response":
        ppi_bid_sel = st.selectbox(
            "Optimize PPI twice-daily (4–8 weeks)",
            ["Not yet started", "Trial done adequate response", "Trial done inadequate response"]
        )
        ppi_bid_done = ppi_bid_sel != "Not yet started"
        ppi_bid_adequate = True if ppi_bid_sel == "Trial done adequate response" else False if ppi_bid_sel == "Trial done inadequate response" else None

    symptoms_resolved_after_ppi = None
    symptoms_return_after_deprescribing = None
    if ppi_od_adequate is True or ppi_bid_adequate is True:
        resolved_sel = st.selectbox("Symptoms resolved after PPI?", ["Unknown", "Yes resolved", "No persisting"])
        symptoms_resolved_after_ppi = {"Unknown": None, "Yes resolved": True, "No persisting": False}[resolved_sel]
        if symptoms_resolved_after_ppi is True:
            return_sel = st.selectbox("Symptoms returned after deprescribing?", ["Unknown / not tried", "Yes returned", "No still resolved"])
            symptoms_return_after_deprescribing = {"Unknown / not tried": None, "Yes returned": True, "No still resolved": False}[return_sel]

    ecg_qtc_ms = None
    family_hx_scd = None
    personal_cardiac = None
    qt_meds = None
    if ppi_bid_adequate is False:
        st.markdown("**Domperidone Safety Check**")
        ecg_qtc_ms = st.number_input("ECG QTc (ms)", min_value=300, max_value=700, value=430)
        family_hx_scd = st.checkbox("Family history of sudden cardiac death")
        personal_cardiac = st.checkbox("Personal cardiac history (e.g. heart failure)")
        qt_meds = st.checkbox("Currently on QT-prolonging medications")

    st.markdown("**Overall Management Response**")
    mgmt_sel = st.selectbox(
        "Response to overall dyspepsia management:",
        ["Not yet assessed", "Satisfactory — continue in medical home", "Unsatisfactory — further action needed"]
    )
    mgmt_map = {"Not yet assessed": None, "Satisfactory — continue in medical home": False, "Unsatisfactory — further action needed": True}
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


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.dys_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age,
            "sex": sex,
            "predominant_epigastric_pain": predominant_epigastric_pain,
            "predominant_epigastric_discomfort": predominant_epigastric_discomfort,
            "predominant_upper_abdominal_bloating": predominant_upper_abdominal_bloating,
            "symptom_duration_months": symptom_duration_months,
            "postprandial_fullness": postprandial_fullness or None,
            "early_satiety": early_satiety or None,
            "epigastric_pain": epigastric_pain_rome or None,
            "epigastric_burning": epigastric_burning or None,
            "symptom_onset_months_ago": symptom_onset_months_ago if symptom_onset_months_ago > 0 else None,
            "predominant_heartburn": predominant_heartburn,
            "predominant_regurgitation": predominant_regurgitation,
            "actively_bleeding_now": actively_bleeding_now,
            "family_history_upper_gi_cancer_first_degree": al_fh_cancer,
            "symptom_onset_after_age_60": al_onset_after_60,
            "unintended_weight_loss": al_weight_loss,
            "dysphagia": al_dysphagia,
            "persistent_vomiting": al_vomiting,
            "black_stool_or_blood_in_vomit": al_black_stool,
            "iron_deficiency_anemia_present": al_ida,
            "medication_review_done": medication_review_done,
            "lifestyle_review_done": lifestyle_review_done,
            "diet_trigger_review_done": diet_trigger_review_done,
            "symptoms_improved_after_med_lifestyle_review": improved_map[improved_sel],
            "cbc_done": cbc_done_val,
            "cbc_abnormal": cbc_abnormal,
            "ferritin_done": ferritin_map[ferritin_sel],
            "ttg_iga_done": ttg_done_val,
            "ttg_iga_positive": ttg_positive,
            "suspect_hepatobiliary_pancreatic_process": suspect_hepato,
            "hepatobiliary_pancreatic_tests_done": hepato_done,
            "hepatobiliary_pancreatic_workup_abnormal": hepato_abnormal,
            "other_diagnosis_found": other_dx_found,
            "h_pylori_test_done": hp_done,
            "h_pylori_result_positive": hp_positive,
            "ppi_once_daily_trial_done": ppi_od_done if ppi_od_done else None,
            "ppi_once_daily_response_adequate": ppi_od_adequate,
            "ppi_bid_trial_done": ppi_bid_done,
            "ppi_bid_response_adequate": ppi_bid_adequate,
            "symptoms_resolved_after_ppi": symptoms_resolved_after_ppi,
            "symptoms_return_after_deprescribing": symptoms_return_after_deprescribing,
            "ecg_qtc_ms": ecg_qtc_ms,
            "family_history_sudden_cardiac_death": family_hx_scd,
            "personal_cardiac_history": personal_cardiac,
            "qt_prolonging_medications_present": qt_meds,
            "unsatisfactory_response_to_management": mgmt_map[mgmt_sel],
            "advice_service_considered": advice_considered or None,
        }

        outputs, logs, applied_overrides = run_dyspepsia_pathway(
            patient_data, overrides=st.session_state.dys_overrides
        )

        _action_codes   = {o.code for o in outputs if isinstance(o, Action)}
        _stop_act_codes = {a.code for o in outputs if isinstance(o, Stop) for a in o.actions}
        _all_codes = _action_codes | _stop_act_codes

        entry_met      = "DYSPEPSIA_ENTRY_MET" in _all_codes
        entry_not_met  = "NOT_DYSPEPSIA" in _all_codes
        routed_gerd    = "ROUTE_GERD_PATHWAY" in _all_codes
        has_alarm      = "URGENT_ENDOSCOPY_REFERRAL" in _all_codes
        bleed_stop     = "EMERGENT_BLEEDING_ASSESSMENT" in _all_codes
        improved_life  = "NO_FURTHER_ACTION_REQUIRED" in _all_codes
        other_dx       = "OTHER_DIAGNOSIS_IDENTIFIED" in _all_codes
        routed_hp      = "ROUTE_H_PYLORI_PATHWAY" in _all_codes
        started_ppi    = "START_PPI_ONCE_DAILY" in _all_codes
        ppi_od_ok      = "PPI_ONCE_DAILY_SUCCESS" in _all_codes
        optimize_bid   = "OPTIMIZE_PPI_BID" in _all_codes
        ppi_bid_ok     = "PPI_BID_SUCCESS" in _all_codes
        tca_flag       = "CONSIDER_TCA" in _all_codes
        dom_eligible   = "DOMPERIDONE_ELIGIBLE" in _all_codes
        dom_ineligible = "DOMPERIDONE_NOT_ELIGIBLE" in _all_codes
        titrate_down   = "TITRATE_DOWN_PPI" in _all_codes
        ppi_maint      = "PPI_MAINTENANCE" in _all_codes
        pathway_done   = "CONTINUE_MEDICAL_HOME_CARE" in _all_codes
        refer_endo     = "REFER_FAILED_MANAGEMENT" in _all_codes

        # ── Outbound Integrations ──────────────────────────────────────────
        if routed_hp:
            st.info("Engine routes to **H. Pylori** based on positive test / indication. You can continue treatment in the H. Pylori pathway.")
            if st.button("→ Continue in H. Pylori Pathway", key="dys_to_hp"):
                queue_handoff("1_H._Pylori", patient_data)
                st.switch_page("pages/1_H._Pylori.py")

        if routed_gerd:
            st.info("Engine routes to **GERD** based on predominant heartburn / regurgitation. You can continue management in the GERD pathway.")
            if st.button("→ Continue in GERD Pathway", key="dys_to_gerd"):
                queue_handoff("2_GERD", patient_data)
                st.switch_page("pages/2_GERD.py")

        v1  = True
        v2  = entry_met
        v3  = v2 and not routed_gerd
        v4  = v3 and not (has_alarm or bleed_stop)
        v5  = v4 and not improved_life
        v6  = v5 and not other_dx
        v7  = v6 and not routed_hp
        v8  = v7 and not ppi_od_ok and optimize_bid
        v9  = v8 and not ppi_bid_ok and tca_flag
        v10 = titrate_down or ppi_maint
        v11 = pathway_done or refer_endo

        # ── SVG PATHWAY VISUAL ─────────────────────────────────────────────
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent:  return C_URGENT
            if exit_:   return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def _mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent:  return "mr"
            if exit_:   return "mo"
            return "mg"

        def _stroke(vis, urgent=False, exit_=False):
            if not vis: return "#64748b"
            if urgent:  return C_URGENT
            if exit_:   return C_EXIT
            return C_MAIN

        svg = []
        W, H = 820, 1380
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')
        svg.append("<defs>" + "".join(f'<marker id="{mid}" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="{col}"/></marker>' for mid, col in [("ma","#64748b"),("mg",C_MAIN),("mr",C_URGENT),("mo",C_EXIT)]) + "</defs>")

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

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label="", label_side="right"):
            m = _mid(vis, urgent, exit_); s = _stroke(vis, urgent, exit_)
            dash_style = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{s}" stroke-width="2" {dash_style} marker-end="url(#{m})"/>')
            if label:
                lx = x + 6 if label_side == "right" else x - 6
                anchor = "start" if label_side == "right" else "end"
                svgt(lx, (y1+y2)/2-3, label, s, 10, True, anchor)

        def elbow(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = _mid(vis, urgent, exit_); s = _stroke(vis, urgent, exit_)
            dash_style = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{s}" stroke-width="2" {dash_style} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, s, 10, True)

        # SVG Elements Placement
        CX = 410; NW, NH = 200, 48; DW, DH = 210, 62; EW, EH = 155, 42
        LX = 12; RX = W - 12 - EW
        Y = {"d1":12, "d2":120, "d3":228, "n4":336, "d4":406, "n5":506, "d6":590, "n7":700, "d7":768, "n8":876, "d8":944, "n9":1052, "n10":1140, "term":1230}

        # Node 1
        diamond_node(CX, Y["d1"]+DH/2, DW, DH, dc(v1), "1. Suspected", "Dyspepsia?")
        exit_node(LX, Y["d1"]+(DH-EH)//2, EW, EH, nc(entry_not_met, exit_=True), "Criteria", "Not Met")
        elbow(CX-DW/2, Y["d1"]+DH/2, LX+EW, Y["d1"]+(DH-EH)//2+EH//2, entry_not_met, exit_=True, label="No")
        vline(CX, Y["d1"]+DH, Y["d2"], v2, label="Yes")

        # Node 2
        diamond_node(CX, Y["d2"]+DH/2, DW, DH, dc(v2), "2. Is it GERD?", "Heartburn / regurgitation?")
        exit_node(RX, Y["d2"]+(DH-EH)//2, EW, EH, nc(routed_gerd, exit_=True), "→ GERD", "Pathway")
        elbow(CX+DW/2, Y["d2"]+DH/2, RX, Y["d2"]+(DH-EH)//2+EH//2, routed_gerd, exit_=True, label="Yes")
        vline(CX, Y["d2"]+DH, Y["d3"], v3, label="No")

        # Node 3
        diamond_node(CX, Y["d3"]+DH/2, DW, DH, dc(v3), "3. Alarm Features?")
        exit_node(RX, Y["d3"]+(DH-EH)//2, EW, EH, nc(has_alarm or bleed_stop, urgent=True), "⚠ Urgent Refer", "Endoscopy / ED")
        elbow(CX+DW/2, Y["d3"]+DH/2, RX, Y["d3"]+(DH-EH)//2+EH//2, has_alarm or bleed_stop, urgent=True, label="Yes")
        vline(CX, Y["d3"]+DH, Y["n4"], v4, label="No")

        # Node 4
        rect_node(CX-NW//2, Y["n4"], NW, NH, nc(v4), "4. Medication &", "Lifestyle Review")
        vline(CX, Y["n4"]+NH, Y["d4"], v4)
        diamond_node(CX, Y["d4"]+DH/2, DW, DH, dc(v4), "Symptoms", "Improved?")
        exit_node(RX, Y["d4"]+(DH-EH)//2, EW, EH, nc(improved_life, exit_=True), "No Further", "Action Req'd")
        elbow(CX+DW/2, Y["d4"]+DH/2, RX, Y["d4"]+(DH-EH)//2+EH//2, improved_life, exit_=True, label="Yes")
        vline(CX, Y["d4"]+DH, Y["n5"], v5, label="No")

        # Node 5
        rect_node(CX-NW//2, Y["n5"], NW, NH, nc(v5), "5. Baseline", "Investigations")
        exit_node(LX, Y["n5"]+(NH-EH)//2, EW, EH, nc(other_dx, exit_=True), "Other Dx Found", "Treat / Refer")
        elbow(CX-NW//2, Y["n5"]+NH//2, LX+EW, Y["n5"]+(NH-EH)//2+EH//2, other_dx, exit_=True, label="Abnormal")
        vline(CX, Y["n5"]+NH, Y["d6"], v6)

        # Node 6
        diamond_node(CX, Y["d6"]+DH/2, DW, DH, dc(v6), "6. H. pylori", "Test & Treat")
        exit_node(RX, Y["d6"]+(DH-EH)//2, EW, EH, nc(routed_hp, exit_=True), "→ H. pylori", "Pathway")
        elbow(CX+DW/2, Y["d6"]+DH/2, RX, Y["d6"]+(DH-EH)//2+EH//2, routed_hp, exit_=True, label="+ve")
        vline(CX, Y["d6"]+DH, Y["n7"], v7, label="−ve")

        # Node 7
        rect_node(CX-NW//2, Y["n7"], NW, NH, nc(v7), "7. PPI Trial", "Once Daily  4–8 wks")
        vline(CX, Y["n7"]+NH, Y["d7"], v7)
        diamond_node(CX, Y["d7"]+DH/2, DW, DH, dc(v7), "PPI OD", "Adequate Response?")
        titrate_od_y = Y["d7"] + (DH - EH) // 2
        exit_node(LX, titrate_od_y, EW, EH, nc(ppi_od_ok, exit_=True), "Titrate Down /", "Maintain PPI")
        elbow(CX-DW//2, Y["d7"]+DH//2, LX+EW, titrate_od_y+EH//2, ppi_od_ok, exit_=True, label="Yes")
        
        s_od = C_EXIT if ppi_od_ok else "#64748b"
        m_od = "mo" if ppi_od_ok else "ma"
        dash_od = "" if ppi_od_ok else 'stroke-dasharray="5,3"'
        svg.append(f'<polyline points="{LX+EW//2},{titrate_od_y+EH} {LX+EW//2},{Y["n10"]+NH//2} {CX-NW//2},{Y["n10"]+NH//2}" fill="none" stroke="{s_od}" stroke-width="2" {dash_od} marker-end="url(#{m_od})"/>')
        vline(CX, Y["d7"]+DH, Y["n8"], v8, label="No — optimize")

        # Node 8
        rect_node(CX-NW//2, Y["n8"], NW, NH, nc(v8), "Optimize PPI", "Twice Daily  4–8 wks")
        vline(CX, Y["n8"]+NH, Y["d8"], v8)
        diamond_node(CX, Y["d8"]+DH/2, DW, DH, dc(v8), "PPI BID", "Adequate Response?")
        titrate_bid_y = Y["d8"] + (DH - EH) // 2
        exit_node(LX, titrate_bid_y, EW, EH, nc(ppi_bid_ok, exit_=True), "Titrate Down /", "Maintain PPI")
        elbow(CX-DW//2, Y["d8"]+DH//2, LX+EW, titrate_bid_y+EH//2, ppi_bid_ok, exit_=True, label="Yes")
        
        s_bid = C_EXIT if ppi_bid_ok else "#64748b"
        m_bid = "mo" if ppi_bid_ok else "ma"
        dash_bid = "" if ppi_bid_ok else 'stroke-dasharray="5,3"'
        svg.append(f'<polyline points="{LX+EW//2},{titrate_bid_y+EH} {LX+EW//2},{Y["n10"]+NH//2} {CX-NW//2},{Y["n10"]+NH//2}" fill="none" stroke="{s_bid}" stroke-width="2" {dash_bid} marker-end="url(#{m_bid})"/>')
        vline(CX, Y["d8"]+DH, Y["n9"], v9, label="No")

        # Node 9
        rect_node(CX-NW//2, Y["n9"], NW, NH, nc(v9), "TCA Trial", sub="Optional / while awaiting consult")
        dom_vis = v9 and (dom_eligible or dom_ineligible)
        dom_col = nc(dom_vis, exit_=dom_eligible) if dom_vis else C_UNVISIT
        exit_node(RX, Y["n9"]+(NH-EH)//2, EW, EH, dom_col, "Domperidone", "Eligible" if dom_eligible else ("Ineligible" if dom_ineligible else "?"))
        elbow(CX+NW//2, Y["n9"]+NH//2, RX, Y["n9"]+(NH-EH)//2+EH//2, dom_vis, exit_=dom_eligible, label="Check")
        vline(CX, Y["n9"]+NH, Y["n10"], v10)

        # Node 10
        rect_node(CX-NW//2, Y["n10"], NW, NH, nc(v10), "PPI Maintenance /", "Deprescribing")
        vline(CX, Y["n10"]+NH, Y["term"], v11)

        # Terminal
        term_EW = 175; gap = 20
        left_term_x = CX - gap//2 - term_EW; right_term_x = CX + gap//2
        exit_node(left_term_x, Y["term"], term_EW, EH, nc(pathway_done, exit_=True), "Pathway Complete", "Medical Home")
        exit_node(right_term_x, Y["term"], term_EW, EH, nc(refer_endo, urgent=True), "8. Refer", "Consult / Endoscopy")
        if v11:
            sl = C_EXIT if pathway_done else "#64748b"
            ml = "mo" if pathway_done else "ma"
            dash_l = "" if pathway_done else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{CX},{Y["term"]} {CX},{Y["term"]+18} {left_term_x+term_EW//2},{Y["term"]+18} {left_term_x+term_EW//2},{Y["term"]}" fill="none" stroke="{sl}" stroke-width="2" {dash_l} marker-end="url(#{ml})"/>')
            
            sr = C_URGENT if refer_endo else "#64748b"
            mr = "mr" if refer_endo else "ma"
            dash_r = "" if refer_endo else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{CX},{Y["term"]} {CX},{Y["term"]+18} {right_term_x+term_EW//2},{Y["term"]+18} {right_term_x+term_EW//2},{Y["term"]}" fill="none" stroke="{sr}" stroke-width="2" {dash_r} marker-end="url(#{mr})"/>')

        # Legend
        ly = H - 18; lx = 14
        for col, lbl in [(C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_URGENT, "Urgent"), (C_EXIT, "Exit / Off-ramp"), (C_UNVISIT, "Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 140
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        st.markdown(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto;height:{H + 30}px;overflow-y:auto;">'
            + "".join(svg) + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ───────────────────────────────────────────
        alarm_display = [
            ("family_history_upper_gi_cancer_first_degree", "Family hx upper GI cancer"),
            ("symptom_onset_after_age_60", "Onset after age 60"),
            ("unintended_weight_loss", "Weight loss > 5%"),
            ("black_stool_or_blood_in_vomit", "Black stool / blood in vomit"),
            ("dysphagia", "Progressive dysphagia"),
            ("persistent_vomiting", "Persistent vomiting"),
            ("iron_deficiency_anemia_present", "Iron deficiency anemia"),
        ]
        active_alarms_disp = [lbl for k, lbl in alarm_display if patient_data.get(k)]
        alarm_str = ", ".join(active_alarms_disp) if active_alarms_disp else "None"

        ppi_str = (
            "OD trial adequate" if ppi_od_ok else
            "BID trial adequate" if ppi_bid_ok else
            "BID inadequate → TCA/Domperidone" if tca_flag else
            "OD trial started (awaiting response)" if started_ppi else
            "Not yet started"
        )
        hp_str = (
            "Positive → H. pylori pathway" if routed_hp else
            "Negative" if (hp_done and hp_positive is False) else
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

        # ── Step grouping map ──────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — Suspected Dyspepsia", "icon": "🔍", "cls": "routine",
                "codes": {"DYSPEPSIA_ENTRY_MET", "NOT_DYSPEPSIA"},
            },
            "step2": {
                "label": "Step 2 — GERD Screen", "icon": "🔥", "cls": "routine",
                "codes": {"NOT_PREDOMINANT_GERD", "ROUTE_GERD_PATHWAY"},
            },
            "step3": {
                "label": "Step 3 — Alarm Features", "icon": "🚨", "cls": "urgent",
                "codes": {"NO_ALARM_FEATURES", "EMERGENT_BLEEDING_ASSESSMENT", "URGENT_ENDOSCOPY_REFERRAL"},
            },
            "step4": {
                "label": "Step 4 — Medication & Lifestyle Review", "icon": "💊", "cls": "routine",
                "codes": {"REVIEW_MEDICATIONS", "REVIEW_LIFESTYLE", "REVIEW_DIET_TRIGGERS", "MEDICATION_LIFESTYLE_REVIEWED", "NO_FURTHER_ACTION_REQUIRED"},
            },
            "step5": {
                "label": "Step 5 — Baseline Investigations", "icon": "🩸", "cls": "routine",
                "codes": {"CONSIDER_CBC", "CONSIDER_FERRITIN", "CONSIDER_TTG_IGA", "CONSIDER_HEPATOBILIARY_PANCREATIC_TESTS", "OTHER_DIAGNOSIS_IDENTIFIED"},
            },
            "step6": {
                "label": "Step 6 — H. pylori Test & Treat", "icon": "🦠", "cls": "routine",
                "codes": {"ORDER_H_PYLORI_TEST", "ROUTE_H_PYLORI_PATHWAY", "H_PYLORI_NEGATIVE_OR_TREATED"},
            },
            "step7": {
                "label": "Step 7 — Pharmacologic Therapy (PPI)", "icon": "💊", "cls": "routine",
                "codes": {"START_PPI_ONCE_DAILY", "PPI_ONCE_DAILY_SUCCESS", "OPTIMIZE_PPI_BID", "PPI_BID_SUCCESS"},
            },
            "step8": {
                "label": "Step 8 — TCA / Domperidone Trial", "icon": "⚖️", "cls": "info",
                "codes": {"CONSIDER_TCA", "DOMPERIDONE_ELIGIBLE", "DOMPERIDONE_NOT_ELIGIBLE"},
            },
            "step9": {
                "label": "Step 9 — Maintenance & Deprescribing", "icon": "📉", "cls": "info",
                "codes": {"TITRATE_DOWN_PPI", "PPI_MAINTENANCE"},
            },
            "step10": {
                "label": "Step 10 — Management Response", "icon": "✅", "cls": "routine",
                "codes": {"CONSIDER_ADVICE_SERVICE", "REFER_FAILED_MANAGEMENT", "CONTINUE_MEDICAL_HOME_CARE"},
            },
        }

        code_to_group = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        grouped: dict = {k: [] for k in STEP_GROUPS}
        stops_and_requests = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                gkey = code_to_group.get(output.code)
                if gkey:
                    grouped[gkey].append(output)

        for output in outputs:
            if isinstance(output, Stop):
                for a in output.actions:
                    if a.override_options:
                        override_candidates.append(a)

        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEP_GROUPS[gkey]
            cls = g["cls"]
            icon = g["icon"]
            label = g["label"]

            border_colors = {"routine": "#22c55e", "info": "#3b82f6", "urgent": "#ef4444", "warning": "#f59e0b"}
            bg_colors = {"routine": "#052e16", "info": "#0c1a2e", "urgent": "#3b0a0a", "warning": "#2d1a00"}
            border = border_colors.get(cls, "#22c55e")
            bg = bg_colors.get(cls, "#052e16")

            for a in actions:
                if a.override_options:
                    override_candidates.append(a)

            bullets = "".join(
                f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                + ('<span style="font-size:10px;color:#a5b4fc;margin-left:8px">⚙ override available</span>' if a.override_options else "")
                + "</li>"
                for a in actions
            )

            st.markdown(
                f'<div style="background:{bg};border-left:5px solid {border};border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                f'<p style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:#e2e8f0;letter-spacing:0.3px">'
                f'{icon} {html.escape(label)}</p>'
                f'<ul style="margin:0;padding-left:18px;color:#cbd5e1;font-size:13.5px;line-height:1.7">{bullets}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

        def render_stop_request(output) -> None:
            if isinstance(output, DataRequest):
                missing_str = ", ".join(_pretty(f) for f in output.missing_fields)
                msg_html = html.escape(output.message)
                st.markdown(
                    '<div style="background:#2d1a00;border-left:5px solid #f59e0b;border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    '<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#fde68a">⏳ Data Required to Proceed</p>'
                    f'<p style="margin:0 0 6px;font-size:13.5px;color:#fde68a">{msg_html}</p>'
                    f'<p style="margin:0;font-size:12px;color:#94a3b8">Missing: <code style="color:#fbbf24">{missing_str}</code></p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif isinstance(output, Stop):
                is_complete = "continue management" in output.reason.lower() or "no further action" in output.reason.lower()
                is_refer = "referral" in output.reason.lower() or "urgent" in output.reason.lower() or "emergent" in output.reason.lower()
                is_gerd = "gerd pathway" in output.reason.lower()
                is_not_dysp = "criteria not met" in output.reason.lower()

                if is_complete:
                    bg, border, icon = "#052e16", "#22c55e", "✅"
                    tcol = "#bbf7d0"
                elif is_refer:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🏥"
                    tcol = "#fecaca"
                elif is_gerd:
                    bg, border, icon = "#0c1a2e", "#3b82f6", "🔄"
                    tcol = "#bfdbfe"
                elif is_not_dysp:
                    bg, border, icon = "#2d1a00", "#f59e0b", "⚠️"
                    tcol = "#fde68a"
                else:
                    bg, border, icon = "#1e1e2e", "#6366f1", "ℹ️"
                    tcol = "#c7d2fe"

                title = output.reason
                action_bullets = "".join(
                    f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                    + ('<span style="font-size:10px;color:#a5b4fc;margin-left:8px">⚙ override available</span>' if a.override_options else "")
                    + "</li>"
                    for a in output.actions
                )
                action_block = (
                    f'<ul style="margin:10px 0 0;padding-left:18px;color:#cbd5e1;font-size:13.5px;line-height:1.7">{action_bullets}</ul>'
                    if action_bullets else ""
                )
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    f'<p style="margin:0 0 {"6px" if action_block else "0"};font-size:13px;font-weight:700;color:{tcol}">{icon} {html.escape(title)}</p>'
                    f'{action_block}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        # ── Clinician Notes ────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.dys_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.dys_notes,
            height=180,
        )

        # ── Save / Download ────────────────────────────────────────────────
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

        # ── Override Panel ─────────────────────────────────────────────────
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

        # ── Decision Audit Log ─────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption(
                        "  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None)
                    )
