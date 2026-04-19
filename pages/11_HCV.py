import os
import sys
import html
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from hcv_engine import run_hcv_pathway, Action, DataRequest, Stop, Override
except Exception:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from hcv_engine import run_hcv_pathway, Action, DataRequest, Stop, Override

st.set_page_config(page_title="HCV", page_icon="🧬", layout="wide")

# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title() if s else ""


def _bool_text(val):
    if val is True:
        return "Yes"
    if val is False:
        return "No"
    return "Unknown"


def _serialize_output(o):
    if isinstance(o, Action):
        return {
            "type": "action",
            "code": o.code,
            "label": o.label,
            "urgency": o.urgency,
            "details": o.details,
        }
    if isinstance(o, Stop):
        return {
            "type": "stop",
            "reason": o.reason,
            "urgency": getattr(o, "urgency", None),
            "actions": [a.label for a in getattr(o, "actions", [])],
        }
    if isinstance(o, DataRequest):
        return {
            "type": "data_request",
            "blocking_node": o.blocking_node,
            "message": o.message,
            "missing_fields": o.missing_fields,
        }
    return {"type": "other", "repr": repr(o)}


def build_hcv_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Hepatitis C Virus (HCV) Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(f"- **Age:** {patient_data.get('age', 'Not entered')}")
    lines.append(f"- **Months since exposure:** {patient_data.get('months_since_exposure', 'Not entered')}")
    lines.append(f"- **Prior HCV infection:** {_bool_text(patient_data.get('prior_hcv_infection'))}")
    lines.append(f"- **HCV antibody result:** {_safe_text(patient_data.get('hcv_antibody_result')) or 'Not entered'}")
    lines.append(f"- **HCV RNA result:** {_safe_text(patient_data.get('hcv_rna_result')) or 'Not entered'}")
    lines.append(f"- **Pregnant:** {_bool_text(patient_data.get('pregnant'))}")
    lines.append(f"- **Lactating:** {_bool_text(patient_data.get('lactating'))}")
    lines.append(f"- **At risk of pregnancy:** {_bool_text(patient_data.get('at_risk_of_pregnancy'))}")
    fib4 = patient_data.get("fib4")
    lines.append(f"- **FIB-4 Score:** {fib4 if fib4 is not None else 'Not yet calculated'}")
    lines.append("")
    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                lines.append(f"- **[ACTION]** {_safe_text(o.label)}")
            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                for a in getattr(o, "actions", []):
                    lines.append(f"  - {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing: {', '.join(o.missing_fields)}")
    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}.{_safe_text(ov.field)}** → `{_safe_text(ov.new_value)}` (Reason: {_safe_text(ov.reason)})"
            )
    else:
        lines.append("- No active overrides.")
    lines.append("")
    lines.append("## Clinician Notes")
    lines.append(notes.strip() if notes and notes.strip() else "No clinician notes entered.")
    lines.append("")
    return "\n".join(lines)


# ── GLOBAL CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .stApp { background: #050816; color: #f8fafc; }
    .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }
    h1, h2, h3 { color: #f8fafc !important; }
    .section-label {
        letter-spacing: .08em; text-transform: uppercase; font-size: 0.78rem;
        font-weight: 700; color: #a5b4fc; margin: 1.1rem 0 0.45rem 0;
    }
    .context-card {
        background: linear-gradient(180deg, #1e3a67 0%, #234a82 100%);
        border: 1px solid rgba(147,197,253,.22);
        border-radius: 14px; padding: 14px 16px; color: #dbeafe;
        line-height: 1.55; font-size: .93rem;
    }
    .legend-row {
        display:flex; gap:22px; justify-content:center; align-items:center;
        flex-wrap:wrap; font-size:12px; color:#94a3b8; margin-top: 8px;
    }
    .legend-dot { width:10px; height:10px; border-radius:2px; display:inline-block; margin-right:6px; }
    .card-action {
        background: rgba(16,185,129,.18); border: 1px solid rgba(34,197,94,.45);
        border-left: 4px solid #22c55e; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
    }
    .card-stop {
        background: rgba(217,119,6,.18); border: 1px solid rgba(251,191,36,.38);
        border-left: 4px solid #f59e0b; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
    }
    .card-request {
        background: rgba(146,64,14,.22); border: 1px solid rgba(251,191,36,.25);
        border-left: 4px solid #f59e0b; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
    }
    .card-urgent {
        background: rgba(127,29,29,.25); border: 1px solid rgba(248,113,113,.4);
        border-left: 4px solid #ef4444; border-radius: 12px; padding: 12px 14px; margin-bottom: 10px;
    }
    .mini-note { color:#94a3b8; font-size:.83rem; }
    .override-chip {
        display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: .74rem;
        background:#0b3b2e; color:#86efac; border:1px solid rgba(74,222,128,.28); margin-left:8px;
    }
    div[data-testid="stExpander"] {
        border: 1px solid rgba(148,163,184,.22); border-radius: 12px; background: rgba(15,23,42,.4);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Hepatitis C Virus (HCV)")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "hcv_overrides" not in st.session_state:
    st.session_state.hcv_overrides = []
if "hcv_has_run" not in st.session_state:
    st.session_state.hcv_has_run = False
if "hcv_notes" not in st.session_state:
    st.session_state.hcv_notes = ""
if "hcv_saved_output" not in st.session_state:
    st.session_state.hcv_saved_output = None

left, right = st.columns([1, 1.5])

# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, value=45)

    st.markdown("**Who should be tested? — Risk factors**")
    inj_drug_use = st.checkbox("Current or history of injection drug use")
    incarceration = st.checkbox("History of incarceration")
    endemic = st.checkbox("Born/resided/medical-dental care in HCV-endemic country")
    unsafe_health = st.checkbox("Received health care without universal precautions")
    needle_stick = st.checkbox("History of needle-stick injury")
    transfusion = st.checkbox("Blood transfusion, blood products, or organ transplant before 1992")
    elevated_alt = st.checkbox("Persistently elevated ALT")
    born_to_hcv = st.checkbox("Child >18 months born to mother with HCV")
    hemodialysis = st.checkbox("Hemodialysis patient")
    patient_req = st.checkbox("Patient requests HCV screening")
    other_risk = st.checkbox("Other HCV risk factors documented")

    st.markdown("**Testing & blood work**")
    months_exposure = st.number_input(
        "Months since exposure (if known)", min_value=0, max_value=120, value=3,
        help="Testing is ideally performed at least 3 months after exposure."
    )
    prior_inf_sel = st.selectbox("Prior HCV infection?", ["Unknown / Not documented", "Yes", "No"])
    prior_inf_map = {"Unknown / Not documented": None, "Yes": True, "No": False}
    hcv_ab_sel = st.selectbox("HCV antibody result", ["Not tested", "Positive", "Negative"])
    hcv_rna_sel = st.selectbox("HCV RNA result", ["Not tested", "Positive", "Negative"])
    result_map = {"Not tested": None, "Positive": "positive", "Negative": "negative"}

    st.markdown("**Treatment timing & adherence**")
    pregnant = st.checkbox("Pregnant")
    lactating = st.checkbox("Lactating")
    risk_preg = st.checkbox("At risk of pregnancy / unable to use contraception")
    adherence_low = st.checkbox("Adherence readiness currently low")

    st.markdown("**Primary care vs specialist routing**")
    decomp_cirrhosis = st.checkbox("Decompensated cirrhosis (urgent hepatology referral)")
    prior_tx = st.checkbox("Prior HCV treatment / treatment-experienced")
    hbv = st.checkbox("HBV co-infection")
    hiv = st.checkbox("HIV co-infection")
    egfr = st.number_input("eGFR", min_value=0.0, max_value=200.0, value=90.0, step=1.0)
    provider_comfort = st.checkbox("Primary care provider not comfortable initiating treatment")
    insurance_ref = st.checkbox("Insurance requires specialist referral/advice")

    st.markdown("**Liver assessment labs (for FIB-4)**")
    col1, col2, col3 = st.columns(3)
    with col1:
        ast = st.number_input("AST (U/L)", min_value=0.0, value=0.0, step=1.0)
    with col2:
        alt = st.number_input("ALT (U/L)", min_value=0.0, value=0.0, step=1.0)
    with col3:
        platelets = st.number_input("Platelets (×10⁹/L)", min_value=0.0, value=0.0, step=1.0)

    with st.expander("Post-treatment follow-up (Step 9/10)"):
        rna_post_sel = st.selectbox("HCV RNA 12 weeks post-treatment", ["Not tested", "Positive", "Negative"])
        ast_post = st.number_input("AST 12 weeks post-treatment", min_value=0.0, value=0.0, step=1.0)
        alt_post = st.number_input("ALT 12 weeks post-treatment", min_value=0.0, value=0.0, step=1.0)
        risk_reinf = st.checkbox("Patient remains at risk of reinfection")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.hcv_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hcv_overrides = []
        st.session_state.hcv_saved_output = None

    override_panel = st.container()

# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — OUTPUTS / VISUAL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.hcv_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age if age > 0 else None,
            "current_or_history_injection_drug_use": inj_drug_use or None,
            "incarceration_history": incarceration or None,
            "endemic_country_exposure": endemic or None,
            "unsafe_healthcare_exposure": unsafe_health or None,
            "child_born_to_hcv_mother_over_18_months": born_to_hcv or None,
            "transfusion_or_transplant_pre_1992": transfusion or None,
            "needle_stick_history": needle_stick or None,
            "persistently_elevated_alt": elevated_alt or None,
            "hemodialysis": hemodialysis or None,
            "patient_requests_screening": patient_req or None,
            "other_hcv_risk_factors": other_risk or None,
            "months_since_exposure": months_exposure if months_exposure > 0 else None,
            "prior_hcv_infection": prior_inf_map[prior_inf_sel],
            "hcv_antibody_result": result_map[hcv_ab_sel],
            "hcv_rna_result": result_map[hcv_rna_sel],
            "pregnant": pregnant or None,
            "lactating": lactating or None,
            "at_risk_of_pregnancy": risk_preg or None,
            "adherence_readiness_low": adherence_low or None,
            "decompensated_cirrhosis": decomp_cirrhosis or None,
            "prior_hcv_treatment": prior_tx or None,
            "hbv_coinfection": hbv or None,
            "hiv_coinfection": hiv or None,
            "egfr": egfr if egfr > 0 else None,
            "pediatric_hcv": age < 18,
            "provider_not_comfortable_treating": provider_comfort or None,
            "insurance_requires_referral": insurance_ref or None,
            "ast": ast if ast > 0 else None,
            "alt": alt if alt > 0 else None,
            "platelets": platelets if platelets > 0 else None,
            "hcv_rna_12_weeks_post_treatment": result_map[rna_post_sel],
            "ast_post_treatment": ast_post if ast_post > 0 else None,
            "alt_post_treatment": alt_post if alt_post > 0 else None,
            "ast_upper_limit_normal": 40,
            "alt_upper_limit_normal": 40,
            "at_risk_reinfection": risk_reinf if 'risk_reinf' in locals() else None,
        }

        outputs, logs, applied_overrides = run_hcv_pathway(
            patient_data, overrides=st.session_state.hcv_overrides
        )

        fib4 = None
        for o in outputs:
            if isinstance(o, Action) and o.code == "FIB4_CALCULATED":
                fib4 = o.details.get("fib4")
                patient_data["fib4"] = fib4

        output_codes = {o.code for o in outputs if isinstance(o, Action)}
        stop_reasons = [o.reason for o in outputs if isinstance(o, Stop)]
        data_requests = [o for o in outputs if isinstance(o, DataRequest)]
        override_candidates = []
        for o in outputs:
            if isinstance(o, Action) and getattr(o, "override_options", None):
                override_candidates.append(o)
            if isinstance(o, Stop):
                for a in getattr(o, "actions", []):
                    if isinstance(a, Action) and getattr(a, "override_options", None):
                        override_candidates.append(a)

        risk_present = any([
            inj_drug_use, incarceration, endemic, unsafe_health, born_to_hcv,
            transfusion, needle_stick, elevated_alt, hemodialysis, patient_req, other_risk
        ])
        testing_known = prior_inf_map[prior_inf_sel] is not None and result_map[hcv_ab_sel] is not None and result_map[hcv_rna_sel] is not None
        ab_neg = result_map[hcv_ab_sel] == "negative"
        cleared = result_map[hcv_ab_sel] == "positive" and result_map[hcv_rna_sel] == "negative"
        viremic = result_map[hcv_ab_sel] == "positive" and result_map[hcv_rna_sel] == "positive"
        treatment_postponed = any("postponed" in s.lower() for s in stop_reasons)
        decomp_stop = any("decompensated cirrhosis" in s.lower() for s in stop_reasons)
        must_refer = any(code in output_codes for code in ["ALWAYS_REFER_SPECIALIST", "REFER_PROVIDER_COMFORT", "REFER_INSURANCE_REQUIREMENT"])
        fib4_high = any("FIB-4 > 3.25" in s for s in stop_reasons) or (fib4 is not None and fib4 > 3.25)
        confirm_cure_blocked = any(isinstance(o, DataRequest) and o.blocking_node == "Confirm_Cure" for o in outputs)
        cured_path = any(getattr(l, 'decision', '') == 'CURED' for l in logs)
        not_cured = any("not cured" in s.lower() or "failed" in s.lower() for s in stop_reasons)
        followup_complete = any("HCV pathway complete" in s for s in stop_reasons)

        visited_1 = True
        visited_2 = True
        visited_3 = True
        visited_4 = testing_known and not ab_neg
        visited_5 = visited_4 and not treatment_postponed
        visited_6 = visited_5 and not decomp_stop
        visited_7 = visited_6 and fib4 is not None and fib4 <= 3.25
        visited_8 = visited_7
        visited_9 = visited_8
        visited_10 = cured_path or followup_complete
        visited_11 = must_refer or fib4_high or not_cured or decomp_stop

        C_MAIN = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#2563eb"
        C_URGENT = "#dc2626"
        C_EXIT = "#d97706"
        C_TEXT = "#ffffff"
        C_DIM = "#94a3b8"
        C_BG = "#07152c"

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

        svg = f'''
        <svg viewBox="0 0 860 980" width="100%" height="980" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L10,3 L0,6 z" fill="#64748b"/>
            </marker>
            <style>
              .node {{ rx: 12; ry: 12; stroke-width: 2; }}
              .t1 {{ font: 700 15px Inter, sans-serif; fill: {C_TEXT}; }}
              .t2 {{ font: 500 11px Inter, sans-serif; fill: #dbeafe; }}
              .lab {{ font: 700 12px Inter, sans-serif; fill: {C_DIM}; }}
              .path {{ stroke: #64748b; stroke-width: 3; fill: none; marker-end: url(#arrow); }}
              .branch {{ font: 700 11px Inter, sans-serif; fill: #cbd5e1; }}
            </style>
          </defs>

          <rect x="0" y="0" width="860" height="980" fill="{C_BG}" rx="16"/>

          <rect class="node" x="300" y="30" width="260" height="54" fill="{nc(visited_1)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="52" text-anchor="middle" class="t1">1. Who should be tested?</text>
          <text x="430" y="69" text-anchor="middle" class="t2">Risk factors / screening eligibility</text>

          <rect class="node" x="300" y="118" width="260" height="54" fill="{nc(visited_2)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="140" text-anchor="middle" class="t1">2. Harm reduction</text>
          <text x="430" y="157" text-anchor="middle" class="t2">Connect to support programs</text>

          <rect class="node" x="300" y="206" width="260" height="54" fill="{nc(visited_3)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="228" text-anchor="middle" class="t1">3. Testing & blood work</text>
          <text x="430" y="245" text-anchor="middle" class="t2">At least 3 months after exposure</text>

          <polygon points="430,314 560,360 430,406 300,360" fill="{dc(visited_3)}" stroke="rgba(255,255,255,.18)" stroke-width="2"/>
          <text x="430" y="356" text-anchor="middle" class="t1">Antibody / RNA</text>
          <text x="430" y="373" text-anchor="middle" class="t2">result branch</text>

          <rect class="node" x="615" y="332" width="185" height="56" fill="{nc(ab_neg, exit_=ab_neg)}" stroke="rgba(255,255,255,.15)"/>
          <text x="707" y="354" text-anchor="middle" class="t1">3a. Antibody negative</text>
          <text x="707" y="371" text-anchor="middle" class="t2">Retest annually if ongoing risk</text>

          <rect class="node" x="300" y="452" width="260" height="54" fill="{nc(visited_4)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="474" text-anchor="middle" class="t1">4. Treatment timing</text>
          <text x="430" y="491" text-anchor="middle" class="t2">Adherence / pregnancy review</text>

          <rect class="node" x="40" y="452" width="195" height="56" fill="{nc(cleared, exit_=cleared)}" stroke="rgba(255,255,255,.15)"/>
          <text x="138" y="474" text-anchor="middle" class="t1">3b. Ab+ / RNA-</text>
          <text x="138" y="491" text-anchor="middle" class="t2">Cleared; complete blood work</text>

          <rect class="node" x="625" y="452" width="195" height="56" fill="{nc(viremic)}" stroke="rgba(255,255,255,.15)"/>
          <text x="723" y="474" text-anchor="middle" class="t1">3c. Ab+ / RNA+</text>
          <text x="723" y="491" text-anchor="middle" class="t2">Active HCV; treatment workup</text>

          <rect class="node" x="300" y="540" width="260" height="54" fill="{nc(visited_5)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="562" text-anchor="middle" class="t1">5. Medical home check</text>
          <text x="430" y="579" text-anchor="middle" class="t2">Referral criteria / PCP comfort</text>

          <rect class="node" x="300" y="628" width="260" height="54" fill="{nc(visited_6)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="650" text-anchor="middle" class="t1">6. Calculate FIB-4</text>
          <text x="430" y="667" text-anchor="middle" class="t2">Age, AST, ALT, platelets</text>

          <polygon points="430,736 560,782 430,828 300,782" fill="{dc(visited_6)}" stroke="rgba(255,255,255,.18)" stroke-width="2"/>
          <text x="430" y="778" text-anchor="middle" class="t1">FIB-4 score</text>
          <text x="430" y="795" text-anchor="middle" class="t2">&gt; 3.25 or &lt;= 3.25</text>

          <rect class="node" x="40" y="754" width="200" height="56" fill="{nc(visited_11, urgent=(fib4_high or decomp_stop), exit_=visited_11 and not (fib4_high or decomp_stop))}" stroke="rgba(255,255,255,.15)"/>
          <text x="140" y="776" text-anchor="middle" class="t1">11. Refer to specialist</text>
          <text x="140" y="793" text-anchor="middle" class="t2">Hepatology / GI / ID / Internal Med</text>

          <rect class="node" x="615" y="754" width="185" height="56" fill="{nc(visited_7)}" stroke="rgba(255,255,255,.15)"/>
          <text x="707" y="776" text-anchor="middle" class="t1">7. Seek advice</text>
          <text x="707" y="793" text-anchor="middle" class="t2">If required by insurance</text>

          <rect class="node" x="615" y="844" width="185" height="56" fill="{nc(visited_8)}" stroke="rgba(255,255,255,.15)"/>
          <text x="707" y="866" text-anchor="middle" class="t1">8. Offer therapy</text>
          <text x="707" y="883" text-anchor="middle" class="t2">Epclusa or Maviret, 8–12 weeks</text>

          <rect class="node" x="300" y="884" width="260" height="54" fill="{nc(visited_9)}" stroke="rgba(255,255,255,.15)"/>
          <text x="430" y="906" text-anchor="middle" class="t1">9. Confirm cure</text>
          <text x="430" y="923" text-anchor="middle" class="t2">RNA 12 weeks post-treatment</text>

          <rect class="node" x="40" y="884" width="200" height="56" fill="{nc(not_cured, urgent=not_cured)}" stroke="rgba(255,255,255,.15)"/>
          <text x="140" y="906" text-anchor="middle" class="t1">Treatment failure</text>
          <text x="140" y="923" text-anchor="middle" class="t2">Positive RNA → refer specialist</text>

          <rect class="node" x="615" y="914" width="185" height="48" fill="{nc(visited_10, exit_=visited_10)}" stroke="rgba(255,255,255,.15)"/>
          <text x="707" y="936" text-anchor="middle" class="t1">10. Long-term follow-up</text>
          <text x="707" y="953" text-anchor="middle" class="t2">Harm reduction & annual retesting</text>

          <path class="path" d="M430 84 L430 118"/>
          <path class="path" d="M430 172 L430 206"/>
          <path class="path" d="M430 260 L430 314"/>
          <path class="path" d="M560 360 L615 360"/>
          <path class="path" d="M430 406 L430 452"/>
          <path class="path" d="M300 360 L138 452"/>
          <path class="path" d="M560 360 L723 452"/>
          <path class="path" d="M430 506 L430 540"/>
          <path class="path" d="M430 594 L430 628"/>
          <path class="path" d="M430 682 L430 736"/>
          <path class="path" d="M300 782 L240 782"/>
          <path class="path" d="M560 782 L615 782"/>
          <path class="path" d="M707 810 L707 844"/>
          <path class="path" d="M615 872 L560 900"/>
          <path class="path" d="M300 912 L240 912"/>
          <path class="path" d="M560 912 L615 934"/>

          <text x="590" y="349" class="branch">Negative</text>
          <text x="576" y="432" class="branch">Positive / RNA+</text>
          <text x="242" y="432" class="branch">Positive / RNA-</text>
          <text x="252" y="772" class="branch">&gt; 3.25</text>
          <text x="570" y="772" class="branch">&lt;= 3.25</text>
        </svg>
        '''

        st.subheader("🗺️ Pathway Followed")
        components.html(svg, height=1020)
        st.markdown(
            '''
            <div class="legend-row">
              <span><span class="legend-dot" style="background:#16a34a"></span>Visited</span>
              <span><span class="legend-dot" style="background:#2563eb"></span>Decision</span>
              <span><span class="legend-dot" style="background:#dc2626"></span>Urgent</span>
              <span><span class="legend-dot" style="background:#d97706"></span>Exit/Branch</span>
              <span><span class="legend-dot" style="background:#475569"></span>Not reached</span>
            </div>
            ''',
            unsafe_allow_html=True,
        )

        st.markdown("## Clinical Recommendations")
        context_lines = [
            f"Age: {age}",
            f"Testing Risk Present: {_bool_text(risk_present)}",
            f"Prior HCV: {_bool_text(prior_inf_map[prior_inf_sel])}",
            f"HCV Ab: {hcv_ab_sel}",
            f"HCV RNA: {hcv_rna_sel}",
            f"Treatment postponed: {_bool_text(treatment_postponed)}",
            f"FIB-4: {fib4 if fib4 is not None else 'Not calculated'}",
            f"Specialist referral flags: {_bool_text(must_refer or decomp_stop or fib4_high)}",
        ]
        st.markdown(
            f'<div class="section-label">Patient Context</div><div class="context-card">' + "<br>".join(context_lines) + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-label">Recommended Actions</div>', unsafe_allow_html=True)

        step_groups = {
            "1": [], "2": [], "3": [], "4": [], "5": [], "6": [], "7": [], "8": [], "9": [], "10": [], "11": [], "other": []
        }

        code_to_step = {
            "HCV_TESTING_INDICATED": "1",
            "HCV_TESTING_RISK_WARNING": "1",
            "CONNECT_HARM_REDUCTION": "2",
            "TESTING_WINDOW_WARNING": "3",
            "HCV_ANTIBODY_NEGATIVE": "3",
            "HCV_CLEARED": "3",
            "COMPLETE_ADDITIONAL_BLOODWORK": "3",
            "HCV_VIREMIC": "3",
            "COMPLETE_TREATMENT_BLOODWORK": "3",
            "ASSESS_ADHERENCE_SUPPORTS": "4",
            "POSTPONE_TREATMENT_PREGNANCY": "4",
            "POSTPONE_TREATMENT_ADHERENCE": "4",
            "URGENT_HEPATOLOGY_REFERRAL": "11",
            "ALWAYS_REFER_SPECIALIST": "11",
            "REFER_PROVIDER_COMFORT": "11",
            "REFER_INSURANCE_REQUIREMENT": "7",
            "FIB4_CALCULATED": "6",
            "REFER_HIGH_FIB4": "11",
            "SEEK_SPECIALIST_ADVICE": "7",
            "OFFER_PANGENOTYPIC_THERAPY": "8",
            "ASSESS_DRUG_INTERACTIONS": "8",
            "FACILITATE_INSURANCE_COVERAGE": "8",
            "RECHECK_AST_ALT": "9",
            "REFER_TREATMENT_FAILURE": "11",
            "INVESTIGATE_PERSISTENT_LIVER_ENZYME_ELEVATION": "9",
            "MAINTAIN_HARM_REDUCTION_AND_RETEST": "10",
            "CONTINUE_HCV_FOLLOWUP": "10",
        }

        def push_item(step, title, body, kind="action"):
            step_groups[step].append((title, body, kind))

        for o in outputs:
            if isinstance(o, Action):
                step = code_to_step.get(o.code, "other")
                push_item(step, o.label, None, "action")
            elif isinstance(o, DataRequest):
                step = "9" if o.blocking_node == "Confirm_Cure" else ("6" if o.blocking_node == "Calculate_FIB4" else "3")
                body = f"Missing: {', '.join(o.missing_fields)}"
                push_item(step, o.message, body, "request")
            elif isinstance(o, Stop):
                kind = "urgent" if getattr(o, "urgency", None) == "urgent" else "stop"
                push_item(code_to_step.get("REFER_TREATMENT_FAILURE" if 'failed' in o.reason.lower() else "", "other"), o.reason, None, kind)
                for a in getattr(o, "actions", []):
                    step = code_to_step.get(a.code, "other")
                    push_item(step, a.label, None, "urgent" if getattr(a, "urgency", None) == "urgent" else "action")

        step_titles = {
            "1": "Step 1 — Who Should Be Tested",
            "2": "Step 2 — Harm Reduction",
            "3": "Step 3 — Testing & Blood Work",
            "4": "Step 4 — Is Treatment Appropriate Now?",
            "5": "Step 5 — Determine Treatment in Medical Home",
            "6": "Step 6 — Calculate FIB-4",
            "7": "Step 7 — Seek Specialist Advice",
            "8": "Step 8 — Offer Pan-Genotypic Therapy",
            "9": "Step 9 — Confirm Cure",
            "10": "Step 10 — Long-Term Follow-Up",
            "11": "Step 11 — Specialist Referral",
            "other": "Additional Outputs",
        }

        for step_key in ["1","2","3","4","5","6","7","8","9","10","11","other"]:
            if not step_groups[step_key]:
                continue
            items_html = []
            for title, body, kind in step_groups[step_key]:
                cls = {
                    "action": "card-action",
                    "stop": "card-stop",
                    "request": "card-request",
                    "urgent": "card-urgent",
                }.get(kind, "card-action")
                inner = f"<div><strong>{html.escape(_safe_text(title))}</strong></div>"
                if body:
                    inner += f"<div class='mini-note'>{html.escape(_safe_text(body))}</div>"
                items_html.append(f"<div class='{cls}'>{inner}</div>")
            st.markdown(f"**{step_titles[step_key]}**", unsafe_allow_html=True)
            st.markdown("".join(items_html), unsafe_allow_html=True)

        st.markdown("<div class='section-label'>Overlap Between Pathways / Override Logic</div>", unsafe_allow_html=True)
        overlap_notes = []
        if risk_present and must_refer:
            overlap_notes.append("HCV pathway is active, but referral criteria override primary-care treatment flow.")
        if decomp_cirrhosis:
            overlap_notes.append("Urgent specialist referral overrides treatment initiation and medical-home management.")
        if treatment_postponed:
            overlap_notes.append("Treatment postponement overrides downstream therapy steps until readiness changes.")
        if fib4_high:
            overlap_notes.append("High FIB-4 overrides medical-home therapy path and routes to specialist assessment.")
        if not overlap_notes:
            overlap_notes.append("No overlap override currently triggered.")
        st.info("\n\n".join(overlap_notes))

        st.markdown('<div class="section-label">Clinician Notes</div>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.hcv_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.hcv_notes,
            height=180,
        )

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
                    for o in st.session_state.hcv_overrides
                ],
                "clinician_notes": st.session_state.hcv_notes,
            },
            "decision_audit_log": [
                {
                    "node": l.node,
                    "decision": l.decision,
                    "used_inputs": l.used_inputs,
                    "outputs": l.outputs,
                    "timestamp": l.timestamp,
                }
                for l in logs
            ],
        }

        col_save, col_download = st.columns([1,1])
        with col_save:
            if st.button("💾 Save this output", key="hcv_save_output"):
                st.session_state.hcv_saved_output = {
                    "saved_at": datetime.now().isoformat(),
                    "payload": full_output,
                }
                st.success("Output saved for this session.")
        with col_download:
            md_text = build_hcv_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.hcv_overrides,
                notes=st.session_state.hcv_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="hcv_summary.md",
                mime="text/markdown",
                key="hcv_download_md",
            )

        if st.session_state.hcv_saved_output:
            st.download_button(
                label="⬇️ Download saved JSON output",
                data=json.dumps(st.session_state.hcv_saved_output, indent=2).encode("utf-8"),
                file_name="hcv_saved_output.json",
                mime="application/json",
                key="hcv_download_json",
            )

        with st.expander("🧾 Decision Audit Log"):
            if not logs:
                st.write("No audit log available.")
            else:
                for i, l in enumerate(logs, 1):
                    st.markdown(f"**{i}. {_pretty(l.node)}** — `{l.decision}`")
                    st.caption(l.timestamp)
                    st.code(json.dumps({
                        "used_inputs": l.used_inputs,
                        "outputs": l.outputs,
                    }, indent=2), language="json")

with override_panel:
    if st.session_state.hcv_has_run:
        patient_data_preview = locals().get("patient_data")
        outputs_preview = locals().get("outputs", [])
        override_candidates = []
        for o in outputs_preview:
            if isinstance(o, Action) and getattr(o, "override_options", None):
                override_candidates.append(o)
            if isinstance(o, Stop):
                for a in getattr(o, "actions", []):
                    if isinstance(a, Action) and getattr(a, "override_options", None):
                        override_candidates.append(a)

        if override_candidates:
            st.markdown("---")
            st.markdown("### Clinician Overrides")
            st.caption("Override engine decisions where clinical judgement differs. A documented reason is required for each override.")
            for idx, a in enumerate(override_candidates):
                opt = a.override_options
                raw_node = opt["node"]
                raw_field = opt["field"]
                allowed = opt.get("allowed", [True, False])
                with st.expander(f"⚙️ Override: **{_pretty(raw_node)}** → `{_pretty(raw_field)}`"):
                    st.markdown(f"<div class='mini-note'>{html.escape(a.label)}</div>", unsafe_allow_html=True)
                    sel = st.selectbox(
                        "Override value",
                        options=allowed,
                        index=0,
                        format_func=lambda x: str(x),
                        key=f"override_value_{idx}",
                    )
                    reason = st.text_area("Reason for override", key=f"override_reason_{idx}", height=80)
                    if st.button("Apply override", key=f"apply_override_{idx}"):
                        if not reason.strip():
                            st.error("Reason is required.")
                        else:
                            old_value = None
                            if isinstance(patient_data_preview, dict):
                                old_value = patient_data_preview.get(raw_field)
                            st.session_state.hcv_overrides.append(
                                Override(
                                    target_node=raw_node,
                                    field=raw_field,
                                    old_value=old_value,
                                    new_value=sel,
                                    reason=reason.strip(),
                                )
                            )
                            st.success("Override added. Re-run the pathway to see its effect.")

        if st.session_state.hcv_overrides:
            st.markdown("### Active Overrides")
            for i, o in enumerate(st.session_state.hcv_overrides, 1):
                st.markdown(
                    f"- **{i}. {_pretty(o.target_node)} → {_pretty(o.field)}**"
                    f" <span class='override-chip'>{html.escape(str(o.new_value))}</span><br>"
                    f"  <span class='mini-note'>Reason: {html.escape(o.reason)}</span>",
                    unsafe_allow_html=True,
                )
