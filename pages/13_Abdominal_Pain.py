import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from chronic_abdominal_pain_engine import (
    run_chronic_abdominal_pain_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(
    page_title="Chronic Abdominal Pain / CAPS",
    page_icon="🔴",
    layout="wide",
)


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_cap_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Chronic Abdominal Pain / CAPS Pathway — Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(
        f"- **Age / Sex:** {patient_data.get('age')} / "
        f"{str(patient_data.get('sex', '')).capitalize()}"
    )
    pain_dur = patient_data.get("pain_duration_months_at_criteria_level")
    lines.append(f"- **Pain Duration (months at criteria level):** {pain_dur if pain_dur is not None else 'Not entered'}")
    onset = patient_data.get("symptom_onset_months_ago")
    lines.append(f"- **Symptom Onset (months ago):** {onset if onset is not None else 'Not entered'}")
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
                        lines.append(f"  - {_safe_text(a.label)}")
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

st.title("Chronic Abdominal Pain / CAPS")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "cap_overrides" not in st.session_state:
    st.session_state.cap_overrides = []
if "cap_has_run" not in st.session_state:
    st.session_state.cap_has_run = False
if "cap_notes" not in st.session_state:
    st.session_state.cap_notes = ""


left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    age = st.number_input("Age", 18, 120, value=42)
    sex = st.selectbox("Sex", ["female", "male"])

    # ── 1. CAPS Diagnostic Criteria ──────────────────────────────────────────
    st.markdown("**1. CAPS Diagnostic Criteria (Rome IV)**")
    continuous_pain = st.checkbox(
        "Continuous or near-continuous abdominal pain",
        help="Required criterion: constant or near-constant pain",
    )
    pain_duration = st.number_input(
        "Pain duration at criteria level (months)",
        min_value=0,
        max_value=120,
        value=4,
        help="Must be ≥3 months",
    )
    symptom_onset = st.number_input(
        "Symptom onset (months ago)",
        min_value=0,
        max_value=240,
        value=8,
        help="Must be ≥6 months ago",
    )
    no_physiologic_relation = st.checkbox(
        "No / only occasional relationship of pain with physiological events",
        help="Pain not clearly tied to eating, defecation, or menses",
    )
    limits_function = st.checkbox(
        "Pain limits some aspect of daily functioning",
        help="Work, intimacy, social/leisure, family life, etc.",
    )
    not_feigned = st.checkbox(
        "Pain is not feigned",
    )
    not_explained_other = st.checkbox(
        "Pain not explained by another structural condition or gut-brain interaction disorder",
    )

    # ── 2. Other GI Disorder Differentiation ─────────────────────────────────
    st.markdown("**2. Differentiation from Other GI Disorders**")
    st.caption(
        "Answer whether symptoms are BETTER explained by another GI disorder. "
        "If any are checked, the pathway will route to the appropriate pathway."
    )
    heartburn_regurgitation = st.checkbox(
        "Predominant heartburn or regurgitation (→ GERD pathway)"
    )
    defecation_related = st.checkbox(
        "Pain related to defecation / change in stool form or frequency (→ IBS pathway)"
    )
    epigastric_discomfort = st.checkbox(
        "Epigastric discomfort or upper abdominal pain/bloating (→ Dyspepsia pathway)"
    )

    # ── 3. Alarm Features ─────────────────────────────────────────────────────
    st.markdown("**3. Alarm Features**")
    st.caption(
        "Check any present. If alarm features are identified, "
        "the engine will recommend urgent referral for consultation/endoscopy."
    )
    fam_hx_ibd_crc = st.checkbox(
        "Family history (first-degree relative) of IBD or colorectal cancer"
    )
    weight_loss = st.checkbox(
        "Unintended weight loss >5% over 6–12 months"
    )
    iron_deficiency_anemia = st.checkbox(
        "Iron deficiency anemia"
    )
    onset_after_50 = st.checkbox(
        "Onset of symptoms after age 50"
    )
    persistent_vomiting = st.checkbox(
        "Persistent vomiting"
    )
    visible_blood_stool = st.checkbox(
        "Visible blood in stool"
    )

    # ── 4. Secondary Cause Review ─────────────────────────────────────────────
    st.markdown("**4. Secondary Cause / Alternate Diagnosis Review**")
    med_review_done = st.checkbox("Medication review completed", value=False)
    dietary_review_done = st.checkbox("Dietary trigger/allergen review completed", value=False)
    referred_pain_assessed = st.checkbox("Referred pain from other systems assessed", value=False)
    referred_pain_present = st.checkbox("Referred pain from another system identified")
    culprit_medication = st.checkbox("Culprit medication identified (causing GI side effects)")
    dietary_trigger = st.checkbox("Dietary trigger or allergen identified")
    abdominal_wall_pain = st.checkbox("Abdominal wall pain suspected")
    cannabinoid_pain = st.checkbox("Cannabinoid-related pain suspected")
    narcotic_bowel = st.checkbox("Narcotic bowel syndrome suspected")
    organic_condition = st.checkbox("Organic condition already identified")
    carnet_considered = st.checkbox(
        "Carnett's test considered (if abdominal wall pain suspected)"
    )

    # ── 5. Baseline Investigations ─────────────────────────────────────────────
    st.markdown("**5. Baseline Investigations — Core Tests**")
    cbc_done = st.checkbox("CBC completed", value=False)
    electrolytes_done = st.checkbox("Electrolytes (Na, K, Cl, Ca, Mg, P) completed", value=False)
    creatinine_done = st.checkbox("Creatinine completed", value=False)
    liver_tests_done = st.checkbox("Liver enzymes (ALT, ALP), albumin, bilirubin, lipase completed", value=False)
    lipase_done = st.checkbox("Lipase completed", value=False)
    ferritin_tsat_done = st.checkbox("Ferritin and transferrin saturation completed", value=False)

    st.markdown("**Baseline Results (check if abnormal)**")
    cbc_abnormal = st.checkbox("CBC abnormal")
    electrolytes_abnormal = st.checkbox("Electrolytes abnormal")
    creatinine_abnormal = st.checkbox("Creatinine abnormal")
    liver_tests_abnormal = st.checkbox("Liver tests (ALT/ALP/bilirubin/lipase) abnormal")
    lipase_abnormal = st.checkbox("Lipase abnormal")
    ferritin_tsat_abnormal = st.checkbox("Ferritin/transferrin saturation abnormal")

    st.markdown("**Contextual Tests (check if clinically indicated)**")
    col_a, col_b = st.columns(2)
    with col_a:
        suspect_inflam = st.checkbox("Suspect inflammatory/infectious condition (→ CRP)")
        crp_done = st.checkbox("CRP done")
        crp_abnormal = st.checkbox("CRP abnormal")
        travel_risk = st.checkbox("Travel/parasite risk (→ O&P)")
        stool_op_done = st.checkbox("Stool O&P done")
        ova_parasites_pos = st.checkbox("O&P positive")
        infectious_diarrhea = st.checkbox("Infectious diarrhea risk (→ C. diff)")
        c_diff_done = st.checkbox("C. difficile done")
        c_diff_pos = st.checkbox("C. difficile positive")
    with col_b:
        celiac_relevant = st.checkbox("Celiac screen indicated")
        celiac_done = st.checkbox("Celiac screen done")
        celiac_pos = st.checkbox("Celiac screen positive")
        tsh_relevant = st.checkbox("TSH indicated")
        tsh_done = st.checkbox("TSH done")
        tsh_abnormal = st.checkbox("TSH abnormal")
        h_pylori_relevant = st.checkbox("H. pylori test indicated")
        h_pylori_done = st.checkbox("H. pylori done")
        h_pylori_pos = st.checkbox("H. pylori positive")

    col_c, col_d = st.columns(2)
    with col_c:
        urinary_context = st.checkbox("Urinary/renal context (→ urinalysis)")
        ua_done = st.checkbox("Urinalysis done")
        ua_abnormal = st.checkbox("Urinalysis abnormal")
        pregnancy_possible = st.checkbox("Pregnancy possible (→ β-hCG)")
        preg_test_done = st.checkbox("Pregnancy test done")
        preg_pos = st.checkbox("Pregnancy test positive")
    with col_d:
        us_relevant = st.checkbox("Abdominopelvic ultrasound indicated")
        us_done = st.checkbox("Ultrasound done")
        us_abnormal = st.checkbox("Ultrasound abnormal")

    # ── 6. Management ──────────────────────────────────────────────────────────
    st.markdown("**6. Management**")
    patient_reassurance = st.checkbox("Patient reassurance provided")
    lifestyle_mod = st.checkbox("Lifestyle modification started (stress reduction, physical activity)")
    dietary_mod = st.checkbox("Dietary modification started (food journal, trigger avoidance)")
    psych_referral = st.checkbox("Psychological referral or therapy started")
    pharma_started = st.checkbox("Pharmacologic CAPS therapy started")

    severity_sel = st.selectbox(
        "CAPS symptom severity",
        ["Not yet assessed", "Mild / intermittent", "Moderate / Severe"],
        help="Pharmacotherapy is reserved for moderate-to-severe symptoms only",
    )
    severity_map = {
        "Not yet assessed": None,
        "Mild / intermittent": False,
        "Moderate / Severe": True,
    }

    opioid_use = st.checkbox(
        "Patient currently using opioids for chronic GI pain",
        help="⚠ Opioids must NOT be used for CAPS — increases risk of narcotic bowel syndrome",
    )
    sleep_mood_screen = st.checkbox("Sleep and mood disorder screen completed")
    trauma_screen = st.checkbox("Trauma-informed assessment considered")

    # ── 7. Reassessment / Response ─────────────────────────────────────────────
    st.markdown("**7. Response to Management**")
    response_sel = st.selectbox(
        "Response to management",
        [
            "Not yet assessed",
            "Satisfactory response — continue care",
            "Unsatisfactory response — consider escalation",
        ],
    )
    response_map = {
        "Not yet assessed": None,
        "Satisfactory response — continue care": False,
        "Unsatisfactory response — consider escalation": True,
    }

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.cap_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.cap_overrides = []
        if "cap_saved_output" in st.session_state:
            del st.session_state["cap_saved_output"]

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.cap_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        # ── Assemble patient_data dict ─────────────────────────────────────────
        patient_data = {
            "age": age,
            "sex": sex,
            # Node 1 — Diagnostic criteria
            "continuous_or_near_continuous_pain": continuous_pain or None,
            "pain_duration_months_at_criteria_level": float(pain_duration),
            "symptom_onset_months_ago": float(symptom_onset),
            "pain_only_occasional_relation_to_physiologic_events": no_physiologic_relation or None,
            "pain_limits_daily_function": limits_function or None,
            "pain_not_feigned": not_feigned or None,
            "not_explained_by_other_condition_initial_assessment": not_explained_other or None,
            # Node 2 — Other GI disorder
            "predominant_heartburn_or_regurgitation": heartburn_regurgitation,
            "pain_related_to_defecation_or_change_in_stool": defecation_related,
            "epigastric_discomfort_or_upper_abdominal_pain_bloating": epigastric_discomfort,
            # Node 3 — Alarm features
            "family_history_ibd_or_crc_first_degree": fam_hx_ibd_crc,
            "unintended_weight_loss_over_5_percent": weight_loss,
            "iron_deficiency_anemia": iron_deficiency_anemia,
            "symptom_onset_after_age_50": onset_after_50,
            "persistent_vomiting": persistent_vomiting,
            "visible_blood_in_stool": visible_blood_stool,
            # Node 4 — Secondary causes
            "medication_review_completed": med_review_done,
            "dietary_review_completed": dietary_review_done,
            "referred_pain_assessed": referred_pain_assessed,
            "referred_pain_other_system": referred_pain_present,
            "culprit_medication_present": culprit_medication,
            "dietary_trigger_or_allergen_present": dietary_trigger,
            "abdominal_wall_pain_suspected": abdominal_wall_pain,
            "cannabinoid_related_pain_suspected": cannabinoid_pain,
            "narcotic_bowel_suspected": narcotic_bowel,
            "organic_condition_already_identified": organic_condition,
            "significant_psychological_comorbidity_predominant": False,
            "carnet_test_considered": carnet_considered,
            # Node 5 — Core baseline investigations
            "cbc_done": cbc_done,
            "electrolytes_done": electrolytes_done,
            "creatinine_done": creatinine_done,
            "liver_tests_done": liver_tests_done,
            "lipase_done": lipase_done,
            "ferritin_or_tsat_done": ferritin_tsat_done,
            # Baseline results
            "cbc_abnormal": cbc_abnormal,
            "electrolytes_abnormal": electrolytes_abnormal,
            "creatinine_abnormal": creatinine_abnormal,
            "liver_tests_abnormal": liver_tests_abnormal,
            "lipase_abnormal": lipase_abnormal,
            "ferritin_or_tsat_abnormal": ferritin_tsat_abnormal,
            # Contextual flags and results
            "suspect_inflammatory_or_infectious_condition": suspect_inflam,
            "crp_done": crp_done,
            "crp_abnormal": crp_abnormal,
            "travel_or_parasite_risk": travel_risk,
            "stool_ova_parasites_done": stool_op_done,
            "ova_parasites_positive": ova_parasites_pos,
            "infectious_diarrhea_risk": infectious_diarrhea,
            "c_difficile_done": c_diff_done,
            "c_difficile_positive": c_diff_pos,
            "celiac_screen_relevant": celiac_relevant,
            "celiac_screen_done": celiac_done,
            "celiac_screen_positive": celiac_pos,
            "tsh_relevant": tsh_relevant,
            "tsh_done": tsh_done,
            "tsh_abnormal": tsh_abnormal,
            "h_pylori_relevant": h_pylori_relevant,
            "h_pylori_done": h_pylori_done,
            "h_pylori_positive": h_pylori_pos,
            "urinary_or_renal_context": urinary_context,
            "urinalysis_done": ua_done,
            "urinalysis_abnormal": ua_abnormal,
            "pregnancy_possible": pregnancy_possible,
            "pregnancy_test_done": preg_test_done,
            "pregnancy_test_positive": preg_pos,
            "ultrasound_relevant": us_relevant,
            "abdominopelvic_ultrasound_done": us_done,
            "abdominopelvic_ultrasound_abnormal": us_abnormal,
            # Node 6 — Management
            "moderate_or_severe_caps_symptoms": severity_map[severity_sel],
            "opioid_use_for_chronic_gi_pain": opioid_use,
            "patient_reassurance_done": patient_reassurance,
            "lifestyle_modification_started": lifestyle_mod,
            "dietary_modification_started": dietary_mod,
            "psychological_referral_or_therapy_started": psych_referral,
            "pharmacologic_caps_therapy_started": pharma_started,
            "sleep_or_mood_disorder_screen_completed": sleep_mood_screen,
            "trauma_history_screen_considered": trauma_screen,
            # Node 7 — Reassessment
            "unsatisfactory_response_to_management": response_map[response_sel],
        }

        outputs, logs, ctx = run_chronic_abdominal_pain_pathway(
            patient_data, overrides=st.session_state.cap_overrides
        )

        # ── Derive pathway state flags for SVG ─────────────────────────────────
        caps_met = ctx.get("meets_caps_diagnostic_criteria")
        better_explained = ctx.get("better_explained_by_other_gi_disorder")
        alarm_present = ctx.get("alarm_features_present")
        secondary_present = ctx.get("alternate_or_secondary_cause_present")
        abnormal_baseline = ctx.get("abnormal_baseline_investigations")
        unsatisfactory = response_map[response_sel]

        # Node visit flags
        n1_visited = True
        n1_passed = caps_met is True
        n2_visited = n1_passed
        n2_passed = n2_visited and better_explained is False
        n3_visited = n2_passed
        n3_alarm = alarm_present is True
        n3_passed = n3_visited and not n3_alarm
        n4_visited = n3_passed
        n4_secondary = secondary_present is True
        n4_passed = n4_visited and not n4_secondary
        n5_visited = n4_passed
        n5_abnormal = abnormal_baseline is True
        n5_passed = n5_visited and not n5_abnormal
        n6_visited = n5_passed
        # GERD / IBS / dyspepsia branch flags
        gerd_branch = n2_visited and heartburn_regurgitation
        ibs_branch = n2_visited and defecation_related
        dyspepsia_branch = n2_visited and epigastric_discomfort
        n7_visited = n6_visited
        unsatisfactory_escalate = n7_visited and unsatisfactory is True
        continue_primary = n7_visited and unsatisfactory is False

        # ── SVG PATHWAY VISUAL ─────────────────────────────────────────────────
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"; C_REFER = "#7c3aed"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False, refer=False):
            if not vis:
                return C_UNVISIT
            if urgent:
                return C_URGENT
            if refer:
                return C_REFER
            if exit_:
                return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, exit_=False, refer=False):
            if not vis:
                return "ma"
            if urgent:
                return "mr"
            if refer:
                return "mp"
            if exit_:
                return "mo"
            return "mg"

        svg = []
        W, H = 720, 880
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
            '<marker id="mp" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#7c3aed"/></marker>'
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
                svgt(x + w / 2, y + h / 2 + 7, line2, tc, 10)
            else:
                svgt(x + w / 2, y + h / 2 + 4, line1, tc, 11, True)
            if sub:
                svgt(x + w / 2, y + h - 7, sub, tc + "99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w / 2, h / 2
            pts = f"{cx},{cy - hh} {cx + hw},{cy} {cx},{cy + hh} {cx - hw},{cy}"
            svg.append(
                f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(cx, cy - 7, line1, tc, 10, True)
                svgt(cx, cy + 8, line2, tc, 10)
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

        def vline(x, y1, y2, vis, urgent=False, exit_=False, refer=False, label=""):
            m = mid(vis, urgent, exit_, refer)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706", "mp": "#7c3aed"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x + 6, (y1 + y2) / 2, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, refer=False, label=""):
            m = mid(vis, urgent, exit_, refer)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706", "mp": "#7c3aed"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y1 - 5, label, stroke, 10, True)

        # ── Layout constants ────────────────────────────────────────────────────
        CX = 360
        NW, NH = 210, 52
        DW, DH = 210, 64
        EW, EH = 148, 46
        LEXT = 14
        REXT = W - 14 - EW

        # All Y positions derived sequentially — no gaps
        GAP = 38   # vertical space between bottom of one node and top of next
        Y = {}
        Y["n1"]   = 16
        Y["d2"]   = Y["n1"] + NH + GAP          # diamond: Better Explained by GI?
        Y["n3"]   = Y["d2"] + DH + GAP          # rect: Alarm Features?
        Y["d3"]   = Y["n3"] + NH + GAP          # diamond: Alternate Diagnosis?
        Y["n4"]   = Y["d3"] + DH + GAP          # rect: Optimize Alt Diagnosis
        Y["n5"]   = Y["n4"] + NH + GAP          # rect: Baseline Investigations
        Y["n6"]   = Y["n5"] + NH + GAP          # rect: CAPS Management
        Y["n7"]   = Y["n6"] + NH + GAP          # rect: Reassessment
        Y["done"] = Y["n7"] + NH + GAP          # rect: Continue Care

        # ── 1. Diagnostic Criteria ──────────────────────────────────────────────
        rect_node(
            CX - NW / 2, Y["n1"], NW, NH,
            nc(True),
            "1. Diagnostic Criteria",
            sub="Rome IV CAPS criteria",
        )
        vline(CX, Y["n1"] + NH, Y["d2"], n1_passed, label="Criteria met")

        # Criteria not met exit (left)
        not_met_exit_y = Y["n1"] + (NH - EH) / 2
        exit_node(LEXT, not_met_exit_y, EW, EH, nc(caps_met is False, urgent=True),
                  "Criteria Not Met", "Stop / Alternate Eval")
        if caps_met is False:
            elbow_line(CX - NW / 2, Y["n1"] + NH / 2, LEXT + EW,
                       not_met_exit_y + EH / 2, True, urgent=True, label="Not met")

        # ── 2. Better Explained by Another GI Disorder? ────────────────────────
        diamond_node(CX, Y["d2"] + DH / 2, DW, DH, dc(n2_visited),
                     "2. Better Explained by", "Another GI Disorder?")

        # GERD/IBS/Dyspepsia exit branches (right)
        gi_any = gerd_branch or ibs_branch or dyspepsia_branch
        gi_label_parts = []
        if gerd_branch:
            gi_label_parts.append("GERD")
        if ibs_branch:
            gi_label_parts.append("IBS")
        if dyspepsia_branch:
            gi_label_parts.append("Dyspepsia")
        gi_label = " / ".join(gi_label_parts) if gi_label_parts else "Other GI"

        exit_node(REXT, Y["d2"] + (DH - EH) / 2, EW, EH,
                  nc(gi_any, exit_=True), f"→ {gi_label}", "Pathway")
        elbow_line(
            CX + DW / 2, Y["d2"] + DH / 2,
            REXT, Y["d2"] + (DH - EH) / 2 + EH / 2,
            gi_any, exit_=True, label="Yes"
        )

        # ── 3. Alarm Features? ─────────────────────────────────────────────────
        vline(CX, Y["d2"] + DH, Y["n3"], n2_passed, label="No")
        rect_node(
            CX - NW / 2, Y["n3"], NW, NH,
            nc(n3_visited),
            "3. Alarm Features?",
            sub="FH IBD/CRC, wt loss, anemia, age>50, vomit, blood",
        )

        # Refer for endoscopy (right) if alarm
        exit_node(REXT, Y["n3"] + (NH - EH) / 2, EW, EH,
                  nc(n3_alarm, urgent=True), "7. Refer", "Consult/Endoscopy")
        elbow_line(
            CX + NW / 2, Y["n3"] + NH / 2,
            REXT, Y["n3"] + (NH - EH) / 2 + EH / 2,
            n3_alarm, urgent=True, label="Yes"
        )

        # ── 4. Alternate Diagnoses / Secondary Causes ──────────────────────────
        vline(CX, Y["n3"] + NH, Y["d3"], n3_passed, label="No")
        diamond_node(CX, Y["d3"] + DH / 2, DW, DH, dc(n4_visited),
                     "Alternate Diagnosis /", "Secondary Cause?")

        # Treat / Refer (left) if secondary cause
        exit_node(LEXT, Y["d3"] + (DH - EH) / 2, EW, EH,
                  nc(n4_secondary, exit_=True), "Treat / Refer", "Alt Cause")
        elbow_line(
            CX - DW / 2, Y["d3"] + DH / 2,
            LEXT + EW, Y["d3"] + (DH - EH) / 2 + EH / 2,
            n4_secondary, exit_=True, label="Yes"
        )

        # ── 4 node label ────────────────────────────────────────────────────────
        vline(CX, Y["d3"] + DH, Y["n4"], n4_passed, label="No")
        rect_node(
            CX - NW / 2, Y["n4"], NW, NH,
            nc(n4_passed),
            "4. Optimize Alt Diagnosis /",
            "Secondary Causes",
            sub="Meds, diet, referred pain",
        )

        # ── 5. Baseline Investigations ─────────────────────────────────────────
        vline(CX, Y["n4"] + NH, Y["n5"], n4_passed)
        rect_node(
            CX - NW / 2, Y["n5"], NW, NH,
            nc(n5_visited),
            "5. Baseline Investigations",
            sub="CBC, electrolytes, LFT, lipase, ferritin",
        )

        # Treat/Refer if abnormal baseline (right)
        exit_node(REXT, Y["n5"] + (NH - EH) / 2, EW, EH,
                  nc(n5_abnormal, exit_=True), "Treat / Refer", "Organic Cause")
        elbow_line(
            CX + NW / 2, Y["n5"] + NH / 2,
            REXT, Y["n5"] + (NH - EH) / 2 + EH / 2,
            n5_abnormal, exit_=True, label="Abnormal"
        )

        # ── 6. Management (CAPS) ───────────────────────────────────────────────
        vline(CX, Y["n5"] + NH, Y["n6"], n5_passed, label="Normal → CAPS")
        rect_node(
            CX - NW / 2, Y["n6"], NW, NH,
            nc(n6_visited),
            "6. CAPS Management",
            sub="Reassurance, lifestyle, diet, psychology, pharma",
        )

        # ── 7. Reassessment ────────────────────────────────────────────────────
        vline(CX, Y["n6"] + NH, Y["n7"], n7_visited)
        rect_node(
            CX - NW / 2, Y["n7"], NW, NH,
            nc(n7_visited),
            "7. Reassessment",
            sub="Evaluate response to management",
        )

        # Unsatisfactory → advice service → referral (right)
        exit_node(REXT, Y["n7"] + (NH - EH) / 2, EW, EH,
                  nc(unsatisfactory_escalate, refer=True), "Advice Service", "→ Referral")
        elbow_line(
            CX + NW / 2, Y["n7"] + NH / 2,
            REXT, Y["n7"] + (NH - EH) / 2 + EH / 2,
            unsatisfactory_escalate, refer=True, label="Unsatisfactory"
        )

        # Continue in medical home
        vline(CX, Y["n7"] + NH, Y["done"], continue_primary, label="Satisfactory")
        exit_node(
            CX - NW / 2, Y["done"], NW, 46,
            nc(continue_primary, exit_=True), "Continue Care", "Patient Medical Home",
        )

        # ── Legend ──────────────────────────────────────────────────────────────
        ly = H - 22; lx = 14
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent/Alarm"), (C_EXIT, "Exit/Branch"),
            (C_REFER, "Escalation"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly - 11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx + 16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 108
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=920,
            scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ───────────────────────────────────────────────
        criteria_display = "Met ✓" if caps_met else ("Not met ✗" if caps_met is False else "Pending")
        alarm_display = "Yes — Refer" if alarm_present else ("No alarm features" if alarm_present is False else "Pending")
        severity_display = severity_sel

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>CAPS Diagnostic Criteria:</b> {criteria_display}</span><br>'
            f'<span><b>Pain Duration:</b> {pain_duration} months at criteria level</span><br>'
            f'<span><b>Symptom Onset:</b> {symptom_onset} months ago</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_display}</span><br>'
            f'<span><b>Symptom Severity:</b> {severity_display}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Step grouping ──────────────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — Diagnostic Criteria (Rome IV)",
                "icon": "📋",
                "cls": "routine",
                "codes": {"CAPS_CRITERIA_MET", "NOT_CAPS_ENTRY", "CAPTURE_CAPS_DIAGNOSTIC_CRITERIA"},
            },
            "step2": {
                "label": "Step 2 — GI Disorder Differentiation",
                "icon": "🔀",
                "cls": "info",
                "codes": {
                    "NO_BETTER_GI_EXPLANATION",
                    "ROUTE_GERD_PATHWAY",
                    "ROUTE_IBS_PATHWAY",
                    "ROUTE_DYSPEPSIA_PATHWAY",
                    "OTHER_GI_DISORDER_BETTER_EXPLAINS",
                    "CAPTURE_OVERLAP_GI_PATTERN",
                },
            },
            "step3": {
                "label": "Step 3 — Alarm Features",
                "icon": "🚨",
                "cls": "urgent",
                "codes": {
                    "REFER_CONSULT_ENDOSCOPY",
                    "NO_ALARM_FEATURES",
                    "CAPTURE_CAP_ALARM_FEATURES",
                },
            },
            "step4": {
                "label": "Step 4 — Alternate Diagnoses / Secondary Causes",
                "icon": "🔍",
                "cls": "info",
                "codes": {
                    "REVIEW_MEDICATIONS",
                    "REVIEW_DIETARY_TRIGGERS",
                    "ASSESS_REFERRED_PAIN",
                    "CONSIDER_CARNET_TEST",
                    "NO_SECONDARY_CAUSE_IDENTIFIED",
                    "NO_SECONDARY_CAUSE_REQUIRING_ROUTE_CHANGE",
                    "TREAT_OR_REFER_ALTERNATE_CAUSE",
                    "CAPTURE_SECONDARY_CAUSE_REVIEW",
                },
            },
            "step5": {
                "label": "Step 5 — Baseline Investigations",
                "icon": "🩸",
                "cls": "routine",
                "codes": {
                    "ORDER_CORE_BASELINE_INVESTIGATIONS",
                    "ORDER_CRP",
                    "ORDER_OVA_PARASITES",
                    "ORDER_C_DIFFICLE",
                    "ORDER_CELIAC_SCREEN",
                    "ORDER_TSH",
                    "ORDER_H_PYLORI_TEST",
                    "ORDER_URINALYSIS",
                    "ORDER_BHCG",
                    "ORDER_ABDOMINOPELVIC_US",
                    "BASELINE_INVESTIGATIONS_REASSURING",
                    "TREAT_OR_REFER_ABNORMAL_WORKUP",
                },
            },
            "step6": {
                "label": "Step 6 — CAPS Management",
                "icon": "💊",
                "cls": "info",
                "codes": {
                    "PROVIDE_PATIENT_REASSURANCE",
                    "LIFESTYLE_MODIFICATION",
                    "DIETARY_MODIFICATION",
                    "PSYCHOLOGICAL_THERAPY",
                    "CAPTURE_CAPS_SEVERITY",
                    "CONSIDER_CAPS_PHARMACOTHERAPY",
                    "AVOID_OPIOIDS_CAPS",
                    "SCREEN_SLEEP_MOOD",
                    "CONSIDER_TRAUMA_INFORMED_ASSESSMENT",
                },
            },
            "step7": {
                "label": "Step 7 — Reassessment / Escalation",
                "icon": "🔄",
                "cls": "routine",
                "codes": {
                    "CONSIDER_ADVICE_SERVICE",
                    "REFER_CONSULTATION_IF_PERSISTENT",
                    "CONTINUE_PRIMARY_CARE_MANAGEMENT",
                    "CAPTURE_MANAGEMENT_RESPONSE",
                },
            },
        }

        code_to_group = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        grouped: dict = {k: [] for k in STEP_GROUPS}
        stops_and_requests = []
        override_candidates = []

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

        # ── Render group card ──────────────────────────────────────────────────
        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEP_GROUPS[gkey]
            cls = g["cls"]
            icon = g["icon"]
            label = g["label"]

            border_colors = {
                "routine": "#22c55e", "info": "#3b82f6",
                "urgent": "#ef4444", "warning": "#f59e0b",
            }
            bg_colors = {
                "routine": "#052e16", "info": "#0c1a2e",
                "urgent": "#3b0a0a", "warning": "#2d1a00",
            }
            border = border_colors.get(cls, "#22c55e")
            bg = bg_colors.get(cls, "#052e16")

            for a in actions:
                if a.override_options:
                    override_candidates.append(a)

            bullets = "".join(
                f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                + (
                    '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                    '⚙ override available</span>'
                    if a.override_options else ""
                )
                + "</li>"
                for a in actions
            )

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

        # ── Render stop / data request cards ──────────────────────────────────
        def render_stop_request(output) -> None:
            if isinstance(output, DataRequest):
                missing_str = ", ".join(_pretty(f) for f in output.missing_fields)
                msg_html = html.escape(output.message)
                st.markdown(
                    '<div style="background:#2d1a00;border-left:5px solid #f59e0b;'
                    'border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    '<p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#fde68a">'
                    '⏳ Data Required to Proceed</p>'
                    f'<p style="margin:0 0 6px;font-size:13.5px;color:#fde68a">{msg_html}</p>'
                    f'<p style="margin:0;font-size:12px;color:#94a3b8">'
                    f'Missing: <code style="color:#fbbf24">{missing_str}</code></p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            elif isinstance(output, Stop):
                reason_lc = output.reason.lower()
                is_alarm = "alarm" in reason_lc
                is_other_gi = "another gi" in reason_lc or "better explained" in reason_lc
                is_secondary = "secondary" in reason_lc or "alternate diagnosis" in reason_lc
                is_abnormal = "organic cause" in reason_lc or "alternate/organic" in reason_lc or "another cause" in reason_lc
                is_unsatisfactory = "unsatisfactory" in reason_lc or "escalation" in reason_lc
                is_continue = "continue" in reason_lc and "medical home" in reason_lc
                is_criteria_fail = "criteria not met" in reason_lc or "diagnostic criteria not met" in reason_lc

                if is_alarm:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🚨"
                    title = "Alarm Features Identified — Urgent Referral Required"
                    tcol = "#fecaca"
                elif is_other_gi:
                    bg, border, icon = "#1e1e2e", "#6366f1", "🔀"
                    title = "Symptoms Better Explained by Another GI Disorder"
                    tcol = "#c7d2fe"
                elif is_secondary:
                    bg, border, icon = "#2d1a00", "#f59e0b", "⚠️"
                    title = "Alternate Diagnosis or Secondary Cause — Treat or Refer"
                    tcol = "#fde68a"
                elif is_abnormal:
                    bg, border, icon = "#2d1a00", "#f59e0b", "🔬"
                    title = "Abnormal Investigations — Possible Organic Cause Found"
                    tcol = "#fde68a"
                elif is_unsatisfactory:
                    bg, border, icon = "#1a0a2e", "#7c3aed", "📞"
                    title = "Unsatisfactory Response — Consider Advice Service / Referral"
                    tcol = "#ddd6fe"
                elif is_continue:
                    bg, border, icon = "#052e16", "#22c55e", "✅"
                    title = "Continue CAPS Management — Patient Medical Home"
                    tcol = "#bbf7d0"
                elif is_criteria_fail:
                    bg, border, icon = "#1e1e2e", "#6366f1", "ℹ️"
                    title = "CAPS Diagnostic Criteria Not Met"
                    tcol = "#c7d2fe"
                else:
                    bg, border, icon = "#1e1e2e", "#6366f1", "ℹ️"
                    title = output.reason
                    tcol = "#c7d2fe"

                action_bullets = "".join(
                    f'<li style="margin-bottom:5px">{html.escape(a.label)}'
                    + (
                        '<span style="font-size:10px;color:#a5b4fc;margin-left:8px">'
                        '⚙ override available</span>'
                        if a.override_options else ""
                    )
                    + "</li>"
                    for a in output.actions
                )
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

        # ── Render all outputs ─────────────────────────────────────────────────
        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        # ── Clinician Notes ────────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.cap_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.cap_notes,
            height=180,
        )

        # ── Save / Download ────────────────────────────────────────────────────
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
                    for o in st.session_state.cap_overrides
                ],
                "clinician_notes": st.session_state.cap_notes,
            },
        }

        if st.button("💾 Save this output", key="cap_save_output"):
            st.session_state.cap_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "cap_saved_output" in st.session_state:
            md_text = build_cap_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.cap_overrides,
                notes=st.session_state.cap_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown Summary",
                data=md_text.encode("utf-8"),
                file_name="cap_summary.md",
                mime="text/markdown",
                key="cap_download_md",
            )

        # ── Override Panel ─────────────────────────────────────────────────────
        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                seen_overrides = set()
                for a in override_candidates:
                    opt = a.override_options
                    if opt is None:
                        continue
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    override_key = f"{raw_node}_{raw_field}"
                    if override_key in seen_overrides:
                        continue
                    seen_overrides.add(override_key)

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
                            (o for o in st.session_state.cap_overrides
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
                                    st.session_state.cap_overrides = [
                                        o for o in st.session_state.cap_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.cap_overrides.append(
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
                                st.session_state.cap_overrides = [
                                    o for o in st.session_state.cap_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.cap_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.cap_overrides:
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

        # ── Decision Audit Log ─────────────────────────────────────────────────
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
