import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import streamlit.components.v1 as components
from h_pylori_engine_v2 import (
    run_h_pylori_pathway, Action, DataRequest, Stop, Override,
    REGIMEN_DETAILS,
)
from datetime import datetime

st.set_page_config(page_title="H. Pylori", page_icon="🦠", layout="wide")

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
.custom-text-card {
    background:#020617; border:1px solid #1f2937;
    border-radius:10px; padding:14px 18px; margin-top:16px;
}
</style>
""", unsafe_allow_html=True)

st.title("🦠 H. Pylori Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "hp_overrides" not in st.session_state:
    st.session_state.hp_overrides = []

if "hp_has_run" not in st.session_state:
    st.session_state.hp_has_run = False

# editable export text
if "hp_custom_text" not in st.session_state:
    st.session_state.hp_custom_text = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**Pregnancy / Nursing**")
    pregnant      = st.checkbox("Pregnant")
    breastfeeding = st.checkbox("Breastfeeding / Nursing")

    st.markdown("**Testing Indication**")
    dyspepsia      = st.checkbox("Dyspepsia symptoms")
    ulcer_hx       = st.checkbox("History of ulcer or GI bleed")
    family_gastric = st.checkbox("Personal/family history of gastric cancer")
    immigrant_prev = st.checkbox("Immigrant from high-prevalence region")

    st.markdown("**H. Pylori Test**")
    hp_result_sel = st.selectbox("Result", ["Not tested", "Positive", "Negative"])
    hp_result_map = {"Not tested": None, "Positive": "positive", "Negative": "negative"}
    hp_test_type  = st.selectbox("Test type", ["HpSAT", "UBT", "Other"])

    st.markdown("**Washout Status**")
    off_abx     = st.checkbox("Off antibiotics ≥4 weeks", value=True)
    off_ppi     = st.checkbox("Off PPIs ≥2 weeks",        value=True)
    off_bismuth = st.checkbox("Off bismuth ≥2 weeks",     value=True)

    st.markdown("**Alarm Features**")
    al_family_cancer = st.checkbox("Family hx esophageal/gastric cancer")
    al_ulcer_hx      = st.checkbox("Personal history of peptic ulcer")
    al_age_symptoms  = st.checkbox("Age >60 with new persistent symptoms")
    al_weight_loss   = st.checkbox("Unintended weight loss >5%")
    al_dysphagia     = st.checkbox("Progressive dysphagia")
    al_vomiting      = st.checkbox("Persistent vomiting")
    al_gi_bleed      = st.checkbox("Black stool or blood in vomit")
    al_ida           = st.checkbox("Iron deficiency anemia")
    al_concern       = st.checkbox("Clinician concern — serious pathology")

    st.markdown("**Treatment History**")
    penicillin_allergy = st.checkbox("Penicillin allergy")
    tx_line_sel = st.selectbox(
        "Treatment line",
        [
            "1 – Naive (no prior treatment)",
            "2 – Second line (1 prior failure)",
            "3 – Third line (2 prior failures)",
            "4 – Fourth line (3 prior failures)",
        ],
    )
    tx_map = {
        "1 – Naive (no prior treatment)":     1,
        "2 – Second line (1 prior failure)":  2,
        "3 – Third line (2 prior failures)":  3,
        "4 – Fourth line (3 prior failures)": 4,
    }
    bubble_pack  = st.checkbox("Bubble/blister pack NOT being used", value=False)
    nonadherence = st.checkbox("Non-adherence suspected")

    if hp_result_map[hp_result_sel] is not None:
        st.markdown("**Eradication Follow-up** *(post-treatment)*")
        erad_result_sel = st.selectbox(
            "Eradication test result",
            ["Not done", "Negative (eradicated)", "Positive (failed)"],
        )
        erad_map = {
            "Not done": None,
            "Negative (eradicated)": "negative",
            "Positive (failed)":     "positive",
        }
        symptoms_persist = st.selectbox("Symptoms still persisting?", ["Unknown", "Yes", "No"])
        sp_map = {"Unknown": None, "Yes": True, "No": False}
    else:
        erad_map         = {"Not done": None}
        erad_result_sel  = "Not done"
        sp_map           = {"Unknown": None}
        symptoms_persist = "Unknown"

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.hp_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hp_overrides = []
        st.rerun()

    # Placeholder where the override UI will be rendered (after outputs are known)
    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.hp_has_run:
        patient_data = {
            "age":          age,
            "sex":          sex,
            "pregnant":     pregnant or None,
            "breastfeeding": breastfeeding or None,
            "dyspepsia_symptoms": dyspepsia or None,
            "current_or_past_gastric_or_duodenal_ulcer_or_upper_gi_bleed": ulcer_hx or None,
            "personal_or_first_degree_relative_history_gastric_cancer":     family_gastric or None,
            "first_generation_immigrant_high_prevalence_region":            immigrant_prev or None,
            "hp_test_type":   hp_test_type if hp_result_map[hp_result_sel] else None,
            "hp_test_result": hp_result_map[hp_result_sel],
            "off_antibiotics_4_weeks_before_test": off_abx,
            "off_ppi_2_weeks_before_test":         off_ppi,
            "off_bismuth_2_weeks_before_test":     off_bismuth,
            "penicillin_allergy":     penicillin_allergy or None,
            "treatment_line":         tx_map[tx_line_sel],
            "bubble_pack_used":       not bubble_pack,
            "nonadherence_suspected": nonadherence or None,
            "family_history_esophageal_or_gastric_cancer_first_degree": al_family_cancer or None,
            "personal_history_peptic_ulcer_disease":                    al_ulcer_hx or None,
            "age_over_60_new_persistent_symptoms_over_3_months":        al_age_symptoms or None,
            "unintended_weight_loss":              al_weight_loss or None,
            "progressive_dysphagia":               al_dysphagia or None,
            "persistent_vomiting_not_cannabis_related": al_vomiting or None,
            "black_stool_or_blood_in_vomit":       al_gi_bleed or None,
            "iron_deficiency_anemia_present":      al_ida or None,
            "clinician_concern_serious_pathology": al_concern or None,
            "eradication_test_result": erad_map.get(erad_result_sel),
            "symptoms_persist":        sp_map.get(symptoms_persist),
            "off_antibiotics_4_weeks_before_retest": off_abx,
            "off_ppi_2_weeks_before_retest":         off_ppi,
        }

        outputs, logs, applied_overrides = run_h_pylori_pathway(
            patient_data, overrides=st.session_state.hp_overrides
        )

        # ── PATH STATE FLAGS ──────────────────────────────────────────────
        is_positive   = patient_data.get("hp_test_result") == "positive"
        test_negative = patient_data.get("hp_test_result") == "negative"
        no_indication = (
            not any([dyspepsia, ulcer_hx, family_gastric, immigrant_prev])
            and patient_data.get("hp_test_result") is None
        )
        has_alarm    = any(isinstance(o, Stop) and "alarm" in o.reason.lower() for o in outputs)
        is_pregnant  = bool(pregnant or breastfeeding)
        went_to_tx   = any(isinstance(o, Action) and "TREAT" in o.code for o in outputs)
        has_followup = any(isinstance(o, Action) and "RETEST" in o.code for o in outputs)
        is_pediatric = age < 18

        eradication_failed = any(
            isinstance(o, Action) and o.code == "PROCEED_TO_NEXT_TREATMENT_LINE"
            for o in outputs
        ) or any(
            isinstance(o, Stop) and "not been eradicated after three" in o.reason.lower()
            for o in outputs
        )

        # ── SVG FLOWCHART (unchanged from previous fixed version) ─────────
        # [flowchart code omitted here for brevity – keep exactly as in the previous
        # working version you liked, including Alarm as box 2 and correct Failure flag]
        # --------------------------------------------------------------

        # (Paste the same flowchart section from the last version here.)

        # ── PATIENT CONTEXT CARD & ACTION RENDERING ───────────────────────
        # [unchanged from previous version, until after render_action loop]

        # ... keep the same PATIENT CONTEXT and render_action / outputs loop ...
        # after finishing rendering all outputs, add the custom text block:

        # ── CUSTOM EDITABLE TEXT BLOCK ────────────────────────────────────
        st.markdown('<p class="section-label">EDITABLE SUMMARY</p>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="custom-text-card">', unsafe_allow_html=True)
            st.caption("Clinician-edited summary for exporting into other systems.")
            st.session_state.hp_custom_text = st.text_area(
                "",
                value=st.session_state.hp_custom_text,
                height=140,
                label_visibility="collapsed",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        # ── CLINICIAN OVERRIDE PANEL (rendered in left column placeholder) ─
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
                    opt     = a.override_options
                    raw_node  = opt["node"]
                    raw_field = opt["field"]
                    node  = _pretty(raw_node)
                    field = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(
                            f'<div class="override-card">Engine decision based on: <b>{preview}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (o for o in st.session_state.hp_overrides
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
                                    st.session_state.hp_overrides = [
                                        o for o in st.session_state.hp_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.hp_overrides.append(
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
                                st.session_state.hp_overrides = [
                                    o for o in st.session_state.hp_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.hp_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.hp_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{_pretty(o.target_node)}</b> → <code>{_pretty(o.field)}</code>'
                            f' set to <b>{o.new_value}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {o.reason}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">'
                            f'Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            "</div>",
                            unsafe_allow_html=True,
                        )

        # ── DECISION AUDIT LOG ────────────────────────────────────────────
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
