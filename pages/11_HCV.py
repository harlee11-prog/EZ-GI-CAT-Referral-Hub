import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import html
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from hcv_engine import (
    run_hcv_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="HCV", page_icon="🧬", layout="wide")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def _yn(value):
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unknown"


def build_hcv_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# HCV Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(f"- **Age:** {patient_data.get('age')}")
    fib4 = patient_data.get("fib4")
    lines.append(f"- **FIB-4 Score:** {fib4 if fib4 is not None else 'Not yet calculated'}")
    lines.append(f"- **Months since exposure:** {patient_data.get('months_since_exposure', 'Not entered')}")
    lines.append(f"- **Prior HCV infection:** {_yn(patient_data.get('prior_hcv_infection'))}")
    lines.append(f"- **HCV antibody result:** {patient_data.get('hcv_antibody_result', 'Not entered')}")
    lines.append(f"- **HCV RNA result:** {patient_data.get('hcv_rna_result', 'Not entered')}")
    lines.append(f"- **AST:** {patient_data.get('ast', 'Not entered')} U/L")
    lines.append(f"- **ALT:** {patient_data.get('alt', 'Not entered')} U/L")
    lines.append(f"- **Platelets:** {patient_data.get('platelets', 'Not entered')} ×10⁹/L")
    lines.append("")
    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                lines.append(f"- **[{urgency}]** {_safe_text(o.label)}")
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

st.title("Hepatitis C Virus (HCV)")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
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

    age = st.number_input("Age", 0, 120, value=45)

    st.markdown("**Who should be tested? — Risk factors**")
    risk_idu = st.checkbox("Current or history of injection drug use")
    risk_incarceration = st.checkbox("History of incarceration")
    risk_endemic = st.checkbox("Born/resided/medical-dental care in HCV-endemic country")
    risk_no_precautions = st.checkbox("Received health care without universal precautions")
    risk_needlestick = st.checkbox("History of needle-stick injury")
    risk_transfusion = st.checkbox("Blood transfusion, blood products, or organ transplant before 1992")
    risk_alt = st.checkbox("Persistently elevated ALT")
    risk_child = st.checkbox("Child >18 months born to mother with HCV")
    risk_hemodialysis = st.checkbox("Hemodialysis patient")
    risk_request = st.checkbox("Patient requests HCV screening")
    risk_other = st.checkbox("Other HCV risk factors documented")

    st.markdown("**Testing & blood work**")
    months_since_exposure = st.number_input(
        "Months since exposure (if known)", min_value=0, max_value=120, value=3,
        help="Testing is ideally performed at least 3 months after exposure."
    )
    prior_hcv_sel = st.selectbox("Prior HCV infection?", ["Unknown / Not documented", "Yes", "No"])
    prior_hcv_map = {"Unknown / Not documented": None, "Yes": True, "No": False}

    ab_sel = st.selectbox("HCV antibody result", ["Not tested", "Positive", "Negative"])
    rna_sel = st.selectbox("HCV RNA result", ["Not tested", "Positive", "Negative"])
    result_map = {"Not tested": None, "Positive": "positive", "Negative": "negative"}

    with st.expander("Additional treatment workup / follow-up inputs"):
        hep_a_igg = st.checkbox("Anti-Hep A IgG antibody completed")
        hep_b_sag = st.checkbox("Hep B surface antigen completed")
        anti_hbc = st.checkbox("Anti-HBc antibody completed")
        anti_hbs = st.checkbox("Anti-HBs antibody completed")
        hiv_antibody = st.checkbox("HIV antibody completed")
        pregnant = st.checkbox("Pregnant")
        lactating = st.checkbox("Lactating")
        pregnancy_risk = st.checkbox("At risk of pregnancy")
        adherence_barriers = st.checkbox("Barriers to adherence identified / needs support")
        ongoing_risk = st.checkbox("Ongoing risk of infection / reinfection")
        hcv_rna_12wk_sel = st.selectbox("HCV RNA 12 weeks after treatment", ["Not tested", "Positive", "Negative"])
        ast_post = st.number_input("AST post-treatment (U/L)", min_value=0.0, value=0.0, step=1.0)
        alt_post = st.number_input("ALT post-treatment (U/L)", min_value=0.0, value=0.0, step=1.0)

    st.markdown("**Treatment setting / referral criteria**")
    prior_treatment = st.checkbox("Prior HCV treatment")
    hbv_coinfection = st.checkbox("HBV co-infection")
    hiv_coinfection = st.checkbox("HIV co-infection")
    egfr = st.number_input("eGFR", min_value=0.0, value=90.0, step=1.0)
    provider_not_comfortable = st.checkbox("Primary care provider not comfortable treating")
    insurance_requires_advice = st.checkbox("Insurance requires specialist advice/referral")
    decomp_cirrhosis = st.checkbox("Decompensated cirrhosis")

    st.markdown("**Lab Values for FIB-4**")
    col_l, col_r = st.columns(2)
    with col_l:
        ast_val = st.number_input("AST (U/L)", min_value=0.0, value=0.0, step=1.0)
        alt_val = st.number_input("ALT (U/L)", min_value=0.0, value=0.0, step=1.0)
    with col_r:
        platelets_val = st.number_input("Platelets (×10⁹/L)", min_value=0.0, value=0.0, step=1.0)
        creatinine_val = st.number_input("Creatinine", min_value=0.0, value=0.0, step=1.0)

    if st.button("▶ Run Pathway", type="primary", use_container_width=True):
        st.session_state.hcv_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hcv_overrides = []

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — VISUAL + OUTPUTS
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.hcv_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age if age > 0 else None,
            "current_or_history_injection_drug_use": risk_idu or None,
            "incarceration_history": risk_incarceration or None,
            "endemic_country_exposure": risk_endemic or None,
            "unsafe_healthcare_exposure": risk_no_precautions or None,
            "needle_stick_history": risk_needlestick or None,
            "transfusion_or_transplant_pre_1992": risk_transfusion or None,
            "persistently_elevated_alt": risk_alt or None,
            "child_born_to_hcv_mother_over_18_months": risk_child or None,
            "hemodialysis": risk_hemodialysis or None,
            "patient_requests_screening": risk_request or None,
            "other_hcv_risk_factors": risk_other or None,
            "months_since_exposure": months_since_exposure if months_since_exposure > 0 else None,
            "prior_hcv_infection": prior_hcv_map[prior_hcv_sel],
            "hcv_antibody_result": result_map[ab_sel],
            "hcv_rna_result": result_map[rna_sel],
            "anti_hep_a_igg_antibody": hep_a_igg or None,
            "hep_b_surface_antigen": hep_b_sag or None,
            "anti_hbc_antibody": anti_hbc or None,
            "anti_hbs_antibody": anti_hbs or None,
            "hiv_antibody": hiv_antibody or None,
            "pregnant": pregnant or None,
            "lactating": lactating or None,
            "at_risk_of_pregnancy": pregnancy_risk or None,
            "adherence_barriers": adherence_barriers or None,
            "prior_hcv_treatment": prior_treatment or None,
            "hbv_coinfection": hbv_coinfection or None,
            "hiv_coinfection": hiv_coinfection or None,
            "egfr": egfr if egfr > 0 else None,
            "provider_not_comfortable_treating": provider_not_comfortable or None,
            "insurance_requires_referral": insurance_requires_advice or None,
            "decompensated_cirrhosis": decomp_cirrhosis or None,
            "pediatric_hcv": True if age and age < 18 else None,
            "ast": ast_val if ast_val > 0 else None,
            "alt": alt_val if alt_val > 0 else None,
            "platelets": platelets_val if platelets_val > 0 else None,
            "creatinine": creatinine_val if creatinine_val > 0 else None,
            "hcv_rna_12_weeks_post_treatment": result_map[hcv_rna_12wk_sel],
            "ast_post_treatment": ast_post if ast_post > 0 else None,
            "alt_post_treatment": alt_post if alt_post > 0 else None,
            "at_risk_reinfection": ongoing_risk or None,
        }

        outputs, logs, applied_overrides = run_hcv_pathway(
            patient_data, overrides=st.session_state.hcv_overrides
        )

        # ── Compute derived flags for SVG ──────────────────────────────────
        fib4_computed = None
        test_indicated = any([
            risk_idu, risk_incarceration, risk_endemic, risk_no_precautions,
            risk_needlestick, risk_transfusion, risk_alt, risk_child,
            risk_hemodialysis, risk_request, risk_other
        ])
        ab_neg = result_map[ab_sel] == "negative"
        ab_pos_rna_neg = result_map[ab_sel] == "positive" and result_map[rna_sel] == "negative"
        ab_pos_rna_pos = result_map[ab_sel] == "positive" and result_map[rna_sel] == "positive"
        postponed = False
        urgent_referral = decomp_cirrhosis
        treat_in_home = False
        referred = False
        advice_needed = insurance_requires_advice
        therapy_offered = False
        confirm_cure = False
        long_term = ongoing_risk
        treatment_failure = False

        override_candidates = []
        for o in outputs:
            if isinstance(o, Action) and o.code == "FIB4_CALCULATED":
                fib4_computed = o.details.get("fib4")
                patient_data["fib4"] = fib4_computed
            if isinstance(o, Action) and o.code in ("POSTPONE_TREATMENT_PREGNANCY", "POSTPONE_TREATMENT_ADHERENCE"):
                postponed = True
            if isinstance(o, Action) and o.code in ("OFFER_PANGENOTYPIC_THERAPY",):
                therapy_offered = True
            if isinstance(o, Action) and o.code in ("CONTINUE_HCV_FOLLOWUP", "MAINTAIN_HARM_REDUCTION_AND_RETEST"):
                long_term = True
            if isinstance(o, Action) and o.code in ("SEEK_SPECIALIST_ADVICE", "REFER_INSURANCE_REQUIREMENT"):
                advice_needed = True
            if isinstance(o, Action) and o.code in ("ALWAYS_REFER_SPECIALIST", "REFER_PROVIDER_COMFORT", "REFER_HIGH_FIB4", "URGENT_HEPATOLOGY_REFERRAL"):
                referred = True
            if isinstance(o, Action) and o.override_options:
                override_candidates.append(o)
            if isinstance(o, Stop):
                rs = o.reason.lower()
                if "decompensated cirrhosis" in rs:
                    urgent_referral = True
                if "treatment postponed" in rs or "postpone" in rs:
                    postponed = True
                if "failed" in rs or "not cured" in rs or "positive hcv rna" in rs:
                    treatment_failure = True
                if "medical home" in rs:
                    treat_in_home = True
                if "specialist" in rs or "refer" in rs:
                    referred = True
                for a in o.actions:
                    if a.override_options:
                        override_candidates.append(a)
                    if a.code == "OFFER_PANGENOTYPIC_THERAPY":
                        therapy_offered = True
                    if a.code in ("SEEK_SPECIALIST_ADVICE", "REFER_INSURANCE_REQUIREMENT"):
                        advice_needed = True
                    if a.code in ("ALWAYS_REFER_SPECIALIST", "REFER_PROVIDER_COMFORT", "REFER_HIGH_FIB4", "URGENT_HEPATOLOGY_REFERRAL"):
                        referred = True
            if isinstance(o, DataRequest):
                if getattr(o, 'blocking_node', '') == 'Confirm_Cure':
                    confirm_cure = True

        if result_map[hcv_rna_12wk_sel] is not None:
            confirm_cure = True
        if result_map[hcv_rna_12wk_sel] == "negative":
            long_term = True
        if result_map[hcv_rna_12wk_sel] == "positive":
            treatment_failure = True

        fib4_high = fib4_computed is not None and fib4_computed > 3.25
        fib4_low = fib4_computed is not None and fib4_computed <= 3.25
        if fib4_high:
            referred = True
        if fib4_low and ab_pos_rna_pos and not urgent_referral and not postponed and not referred:
            treat_in_home = True

        visited1 = True
        visited2 = True
        visited3 = True
        visited4 = ab_pos_rna_pos or ab_pos_rna_neg
        visited5 = visited4 and not urgent_referral and not postponed
        visited6 = visited5
        visited7 = fib4_low and not referred
        visited8 = therapy_offered or (visited7 and not therapy_offered)
        visited9 = confirm_cure or therapy_offered
        visited10 = long_term
        visited11 = referred or urgent_referral or fib4_high or treatment_failure

        # ── SVG PATHWAY VISUAL ─────────────────────────────────────────────
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
        W, H = 700, 1120
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

        CX = 350; NW, NH = 200, 50; DW, DH = 200, 60; EW, EH = 140, 44
        LEXT = 20; REXT = W - 20 - EW

        Y = {
            "step1": 18,
            "step2": 95,
            "step3": 172,
            "d_branch": 280,
            "left_cleared": 365,
            "right_negative": 365,
            "step4": 450,
            "step5": 530,
            "step6": 610,
            "d_fib4": 710,
            "left_ref": 818,
            "right7": 818,
            "right8": 900,
            "step9": 988,
            "left_fail": 1060,
            "right10": 1060,
        }

        rect_node(CX-NW/2, Y["step1"], NW, NH, nc(visited1), "1. Who should be tested?", sub="Risk factors / screening")
        rect_node(CX-NW/2, Y["step2"], NW, NH, nc(visited2), "2. Harm reduction", sub="Connect supports")
        rect_node(CX-NW/2, Y["step3"], NW, NH, nc(visited3), "3. Testing & blood work", sub="At least 3 months after exposure")
        diamond_node(CX, Y["d_branch"], DW, DH, dc(visited3), "Antibody / RNA", "result branch")
        exit_node(LEXT, Y["left_cleared"], EW, EH, nc(ab_pos_rna_neg, exit_=ab_pos_rna_neg), "3b. Ab+ / RNA-", "Cleared")
        exit_node(REXT, Y["right_negative"], EW, EH, nc(ab_neg, exit_=ab_neg), "3a. Antibody negative", "Retest if ongoing risk")
        rect_node(CX-NW/2, Y["step4"], NW, NH, nc(visited4), "4. Treatment timing", sub="Pregnancy / adherence review")
        rect_node(CX-NW/2, Y["step5"], NW, NH, nc(visited5), "5. Medical home check", sub="Referral criteria / PCP comfort")
        rect_node(CX-NW/2, Y["step6"], NW, NH, nc(visited6), "6. Calculate FIB-4", sub="Age, AST, ALT, platelets")
        diamond_node(CX, Y["d_fib4"], DW, DH, dc(visited6), "FIB-4 score", "> 3.25 or ≤ 3.25")
        exit_node(LEXT, Y["left_ref"], EW, EH, nc(visited11, urgent=(urgent_referral or fib4_high), exit_=(visited11 and not (urgent_referral or fib4_high))), "11. Refer to specialist", "GI / ID / Hepatology")
        exit_node(REXT, Y["right7"], EW, EH, nc(visited7), "7. Seek advice", "If insurance requires")
        rect_node(REXT, Y["right8"], EW, EH, nc(visited8), "8. Offer therapy", sub="Epclusa or Maviret")
        rect_node(CX-NW/2, Y["step9"], NW, NH, nc(visited9), "9. Confirm cure", sub="RNA 12 weeks after therapy")
        exit_node(LEXT, Y["left_fail"], EW, EH, nc(treatment_failure, urgent=treatment_failure), "Treatment failure", "Positive RNA → refer")
        exit_node(REXT, Y["right10"], EW, EH, nc(visited10, exit_=visited10), "10. Long-term follow-up", "Annual retesting if at risk")

        vline(CX, Y["step1"]+NH, Y["step2"], visited2)
        vline(CX, Y["step2"]+NH, Y["step3"], visited3)
        vline(CX, Y["step3"]+NH, Y["d_branch"]-DH/2, visited3)
        elbow_line(CX-DW/2, Y["d_branch"], LEXT+EW/2, Y["left_cleared"]+EH/2, ab_pos_rna_neg, exit_=ab_pos_rna_neg, label="Positive / RNA-")
        elbow_line(CX+DW/2, Y["d_branch"], REXT+EW/2, Y["right_negative"]+EH/2, ab_neg, exit_=ab_neg, label="Negative")
        vline(CX, Y["d_branch"]+DH/2, Y["step4"], visited4, urgent=postponed)
        vline(CX, Y["step4"]+NH, Y["step5"], visited5, urgent=postponed)
        vline(CX, Y["step5"]+NH, Y["step6"], visited6)
        vline(CX, Y["step6"]+NH, Y["d_fib4"]-DH/2, visited6)
        elbow_line(CX-DW/2, Y["d_fib4"], LEXT+EW/2, Y["left_ref"]+EH/2, visited11, urgent=(urgent_referral or fib4_high), exit_=(visited11 and not (urgent_referral or fib4_high)), label="> 3.25")
        elbow_line(CX+DW/2, Y["d_fib4"], REXT+EW/2, Y["right7"]+EH/2, visited7, label="≤ 3.25")
        vline(REXT+EW/2, Y["right7"]+EH, Y["right8"], visited8)
        elbow_line(REXT+EW/2, Y["right8"]+EH, CX, Y["step9"]+NH/2, visited9)
        elbow_line(CX-NW/2, Y["step9"]+NH/2, LEXT+EW/2, Y["left_fail"]+EH/2, treatment_failure, urgent=treatment_failure, label="RNA positive")
        elbow_line(CX+NW/2, Y["step9"]+NH/2, REXT+EW/2, Y["right10"]+EH/2, visited10, exit_=visited10, label="RNA negative")

        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html("".join(svg), height=1150)
        st.markdown(
            f'''
            <div style="display:flex;gap:18px;justify-content:center;margin-top:8px;font-size:11px;color:#94a3b8">
                <span><span style="display:inline-block;width:10px;height:10px;background:#16a34a;border-radius:2px;margin-right:5px"></span>Visited</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#1d4ed8;border-radius:2px;margin-right:5px"></span>Decision</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#dc2626;border-radius:2px;margin-right:5px"></span>Urgent</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#d97706;border-radius:2px;margin-right:5px"></span>Exit/Branch</span>
                <span><span style="display:inline-block;width:10px;height:10px;background:#475569;border-radius:2px;margin-right:5px"></span>Not reached</span>
            </div>
            ''',
            unsafe_allow_html=True,
        )

        st.markdown("## Clinical Recommendations")

        fib4_str = f"{fib4_computed:.2f}" if fib4_computed is not None else "Not calculated"
        st.markdown(
            '<p class="section-label">PATIENT CONTEXT</p>'
            '<div class="ctx-card">'
            f'<b>Age:</b> {age}<br>'
            f'<b>Testing Risk Present:</b> {"Yes" if test_indicated else "No"}<br>'
            f'<b>Prior HCV:</b> {prior_hcv_sel}<br>'
            f'<b>HCV Ab:</b> {ab_sel}<br>'
            f'<b>HCV RNA:</b> {rna_sel}<br>'
            f'<b>FIB-4 Score:</b> {fib4_str}<br>'
            f'<b>Referral Flags:</b> {"Yes" if (referred or urgent_referral or fib4_high) else "No"}'
            '</div>',
            unsafe_allow_html=True,
        )

        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — Who Should Be Tested",
                "icon": "🧪",
                "cls": "routine",
                "codes": {"HCV_TESTING_INDICATED", "HCV_TESTING_RISK_WARNING"},
            },
            "step2": {
                "label": "Step 2 — Harm Reduction",
                "icon": "🛟",
                "cls": "routine",
                "codes": {"CONNECT_HARM_REDUCTION"},
            },
            "step3": {
                "label": "Step 3 — Testing & Blood Work",
                "icon": "🧬",
                "cls": "routine",
                "codes": {
                    "TESTING_WINDOW_WARNING", "HCV_ANTIBODY_NEGATIVE", "HCV_CLEARED",
                    "COMPLETE_ADDITIONAL_BLOODWORK", "HCV_VIREMIC", "COMPLETE_TREATMENT_BLOODWORK"
                },
            },
            "step4": {
                "label": "Step 4 — Is Treatment Appropriate at This Time?",
                "icon": "🧑‍⚕️",
                "cls": "warning",
                "codes": {"ASSESS_ADHERENCE_SUPPORTS", "POSTPONE_TREATMENT_PREGNANCY", "POSTPONE_TREATMENT_ADHERENCE"},
            },
            "step5": {
                "label": "Step 5 — Determine Treatment in the Patient Medical Home",
                "icon": "🏠",
                "cls": "info",
                "codes": {"ALWAYS_REFER_SPECIALIST", "REFER_PROVIDER_COMFORT"},
            },
            "step6": {
                "label": "Step 6 — Calculate FIB-4 Score",
                "icon": "📊",
                "cls": "info",
                "codes": {"FIB4_CALCULATED", "REFER_HIGH_FIB4"},
            },
            "step7": {
                "label": "Step 7 — Seek Advice from Specialist",
                "icon": "📨",
                "cls": "info",
                "codes": {"SEEK_SPECIALIST_ADVICE", "REFER_INSURANCE_REQUIREMENT"},
            },
            "step8": {
                "label": "Step 8 — Offer Pan-Genotypic HCV Therapy",
                "icon": "💊",
                "cls": "routine",
                "codes": {"OFFER_PANGENOTYPIC_THERAPY", "ASSESS_DRUG_INTERACTIONS", "FACILITATE_INSURANCE_COVERAGE"},
            },
            "step9": {
                "label": "Step 9 — Complete HCV RNA Test to Confirm Cure",
                "icon": "✅",
                "cls": "routine",
                "codes": {"RECHECK_AST_ALT", "INVESTIGATE_PERSISTENT_LIVER_ENZYME_ELEVATION"},
            },
            "step10": {
                "label": "Step 10 — Maintain Harm Reduction Supports & Retest",
                "icon": "🔁",
                "cls": "routine",
                "codes": {"MAINTAIN_HARM_REDUCTION_AND_RETEST", "CONTINUE_HCV_FOLLOWUP"},
            },
            "step11": {
                "label": "Step 11 — Refer to Specialist Care",
                "icon": "🏥",
                "cls": "urgent",
                "codes": {"URGENT_HEPATOLOGY_REFERRAL", "REFER_TREATMENT_FAILURE"},
            },
        }

        code_to_group = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        grouped = {k: [] for k in STEP_GROUPS}
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

        def _fib4_pill() -> str:
            if fib4_computed is None:
                return ""
            col = "#22c55e" if fib4_low else "#ef4444"
            label = f"FIB-4 = {fib4_computed:.2f} — {'Low Risk ≤ 3.25' if fib4_low else 'High Risk > 3.25'}"
            return (
                f'<span style="background:{col};color:#fff;font-size:11px;font-weight:700;'
                f'padding:3px 10px;border-radius:20px;margin-left:8px">{label}</span>'
            )

        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEP_GROUPS[gkey]
            cls = g["cls"]
            icon = g["icon"]
            label = g["label"]
            pill = _fib4_pill() if gkey == "step6" else ""

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
                f'{icon} {html.escape(label)}{pill}</p>'
                f'<ul style="margin:0;padding-left:18px;color:#cbd5e1;'
                f'font-size:13.5px;line-height:1.7">{bullets}</ul>'
                f'</div>',
                unsafe_allow_html=True,
            )

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
                rs = output.reason.lower()
                is_complete = "complete" in rs or "follow-up" in rs or "retest annually" in rs
                is_refer = "specialist" in rs or "fib-4" in rs or "treatment failure" in rs or "refer" in rs
                is_urgent = "decompensated" in rs or getattr(output, "urgency", None) == "urgent"
                is_postpone = "postpone" in rs
                is_cleared = "cleared" in rs

                if is_urgent:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🏥"
                    title = "Urgent Referral Required"
                    tcol = "#fecaca"
                elif is_refer:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🏥"
                    title = output.reason
                    tcol = "#fecaca"
                elif is_postpone:
                    bg, border, icon = "#2d1a00", "#f59e0b", "⏸️"
                    title = output.reason
                    tcol = "#fde68a"
                elif is_cleared:
                    bg, border, icon = "#052e16", "#22c55e", "✅"
                    title = output.reason
                    tcol = "#bbf7d0"
                elif is_complete:
                    bg, border, icon = "#052e16", "#22c55e", "✅"
                    title = output.reason
                    tcol = "#bbf7d0"
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

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        st.markdown('<p class="section-label">OVERLAP BETWEEN PATHWAYS / OVERRIDE LOGIC</p>', unsafe_allow_html=True)
        overlap_msgs = []
        if urgent_referral:
            overlap_msgs.append("Urgent specialist referral overrides downstream treatment initiation.")
        if fib4_high:
            overlap_msgs.append("High FIB-4 routes away from community treatment toward specialist care.")
        if postponed:
            overlap_msgs.append("Treatment timing concerns override immediate antiviral therapy.")
        if not overlap_msgs:
            overlap_msgs.append("No overlap override currently triggered.")
        st.markdown(
            '<div class="ctx-card">' + '<br>'.join(html.escape(m) for m in overlap_msgs) + '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.hcv_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.hcv_notes,
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
        }

        if st.button("💾 Save this output", key="hcv_save_output"):
            st.session_state.hcv_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

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

        if st.session_state.hcv_saved_output is not None:
            st.download_button(
                label="⬇️ Download saved JSON output",
                data=json.dumps(st.session_state.hcv_saved_output, indent=2).encode("utf-8"),
                file_name="hcv_saved_output.json",
                mime="application/json",
                key="hcv_download_json",
            )

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                dedup = {}
                for a in override_candidates:
                    opt = a.override_options
                    dedup[(opt["node"], opt["field"])] = a

                for _, a in dedup.items():
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
                            (o for o in st.session_state.hcv_overrides
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
                                    st.session_state.hcv_overrides = [
                                        o for o in st.session_state.hcv_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.hcv_overrides.append(
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
                                st.session_state.hcv_overrides = [
                                    o for o in st.session_state.hcv_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.hcv_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.hcv_overrides:
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
                        "  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None)
                    )
