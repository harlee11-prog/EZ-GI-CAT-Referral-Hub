import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import io
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from hcv_engine import run_hcv_pathway, Action, DataRequest, Stop, Override

st.set_page_config(page_title="HCV Pathway", layout="wide")

# ── MARKDOWN HELPERS ────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_hcv_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Hepatitis C (HCV) Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age:** {_safe_text(patient_data.get('age')) or 'Not specified'}")
    lines.append(f"- **HCV Antibody:** {_safe_text(patient_data.get('hcv_antibody_result')) or 'Not tested'}")
    lines.append(f"- **HCV RNA:** {_safe_text(patient_data.get('hcv_rna_result')) or 'Not tested'}")
    lines.append(f"- **Pregnant/Lactating:** {'Yes' if patient_data.get('pregnant') or patient_data.get('lactating') else 'No'}")
    
    fib4 = "Not calculated"
    if patient_data.get('age') and patient_data.get('ast') and patient_data.get('alt') and patient_data.get('platelets'):
        try:
            f = (patient_data['age'] * patient_data['ast']) / (patient_data['platelets'] * (patient_data['alt'] ** 0.5))
            fib4 = f"{f:.3f}"
        except:
            pass
    lines.append(f"- **FIB-4 Score:** {fib4}")
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

st.title(" Hepatitis C Virus (HCV) Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "hcv_overrides" not in st.session_state:
    st.session_state.hcv_overrides = []
if "hcv_has_run" not in st.session_state:
    st.session_state.hcv_has_run = False
if "hcv_notes" not in st.session_state:
    st.session_state.hcv_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL (Inputs) ──────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 45)
    
    st.markdown("**Risk Factors**")
    inj_drug_use = st.checkbox("Current or history of injection drug use")
    incarceration = st.checkbox("History of incarceration")
    endemic = st.checkbox("Endemic country exposure")
    unsafe_health = st.checkbox("Unsafe healthcare exposure")
    born_to_hcv = st.checkbox("Child >18m born to HCV positive mother")
    transfusion = st.checkbox("Transfusion/transplant before 1992")
    needle_stick = st.checkbox("Needle stick injury history")
    elevated_alt = st.checkbox("Persistently elevated ALT")
    hemodialysis = st.checkbox("Hemodialysis patient")
    patient_req = st.checkbox("Patient requests screening")
    other_risk = st.checkbox("Other risk factors (high-risk sex, homelessness, etc.)")

    st.markdown("**Pregnancy & Adherence**")
    pregnant = st.checkbox("Pregnant")
    lactating = st.checkbox("Lactating")
    risk_preg = st.checkbox("At risk of pregnancy")
    adherence_low = st.checkbox("Adherence readiness is low")

    st.markdown("**Testing & Blood Work**")
    months_exposure = st.number_input("Months since exposure (if known)", 0, 120, 4)
    prior_inf = st.selectbox("Prior HCV Infection?", ["Unknown / Not Documented", "Yes", "No"])
    prior_map = {"Unknown / Not Documented": None, "Yes": True, "No": False}
    
    hcv_ab_sel = st.selectbox("HCV Antibody Result", ["Not tested", "Positive", "Negative"])
    hcv_rna_sel = st.selectbox("HCV RNA Result", ["Not tested", "Positive", "Negative"])
    res_map = {"Not tested": None, "Positive": "positive", "Negative": "negative"}

    st.markdown("**Co-morbidities & Referral Criteria**")
    decomp_cirrhosis = st.checkbox("Decompensated cirrhosis")
    prior_tx = st.checkbox("Prior HCV treatment")
    hbv = st.checkbox("HBV Co-infection")
    hiv = st.checkbox("HIV Co-infection")
    pediatric = age < 18
    egfr = st.number_input("eGFR", 0, 150, 90)
    provider_comfort = st.checkbox("Primary care provider NOT comfortable treating", value=False)
    insurance_ref = st.checkbox("Insurance requires referral", value=False)

    st.markdown("**Liver Assessment Labs (for FIB-4)**")
    col1, col2, col3 = st.columns(3)
    with col1: ast = st.number_input("AST (U/L)", 0, 1000, value=0)
    with col2: alt = st.number_input("ALT (U/L)", 0, 1000, value=0)
    with col3: platelets = st.number_input("Platelets (10^9/L)", 0, 1000, value=0)

    st.markdown("**Confirm Cure (12 weeks post-therapy)**")
    rna_post_sel = st.selectbox("HCV RNA (12 weeks post-treatment)", ["Not tested", "Positive", "Negative"])
    ast_post = st.number_input("AST post-treatment", 0, 1000, value=0)
    alt_post = st.number_input("ALT post-treatment", 0, 1000, value=0)
    risk_reinf = st.checkbox("Patient at ongoing risk of re-infection")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.hcv_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.hcv_overrides = []
        if "hcv_saved_output" in st.session_state:
            del st.session_state["hcv_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL (Outputs) ────────────────────────────────────────────────────
with right:
    if st.session_state.hcv_has_run:
        patient_data = {
            "age": age if age > 0 else None,
            "current_or_history_injection_drug_use": inj_drug_use,
            "incarceration_history": incarceration,
            "endemic_country_exposure": endemic,
            "unsafe_healthcare_exposure": unsafe_health,
            "child_born_to_hcv_mother_over_18_months": born_to_hcv,
            "transfusion_or_transplant_pre_1992": transfusion,
            "needle_stick_history": needle_stick,
            "persistently_elevated_alt": elevated_alt,
            "hemodialysis": hemodialysis,
            "patient_requests_screening": patient_req,
            "other_hcv_risk_factors": other_risk,
            "pregnant": pregnant,
            "lactating": lactating,
            "at_risk_of_pregnancy": risk_preg,
            "adherence_readiness_low": adherence_low,
            "months_since_exposure": months_exposure if months_exposure > 0 else None,
            "prior_hcv_infection": prior_map[prior_inf],
            "hcv_antibody_result": res_map[hcv_ab_sel],
            "hcv_rna_result": res_map[hcv_rna_sel],
            "decompensated_cirrhosis": decomp_cirrhosis,
            "prior_hcv_treatment": prior_tx,
            "hbv_coinfection": hbv,
            "hiv_coinfection": hiv,
            "egfr": egfr if egfr > 0 else None,
            "pediatric_hcv": pediatric,
            "provider_not_comfortable_treating": provider_comfort,
            "insurance_requires_referral": insurance_ref,
            "ast": ast if ast > 0 else None,
            "alt": alt if alt > 0 else None,
            "platelets": platelets if platelets > 0 else None,
            "hcv_rna_12_weeks_post_treatment": res_map[rna_post_sel],
            "ast_post_treatment": ast_post if ast_post > 0 else None,
            "alt_post_treatment": alt_post if alt_post > 0 else None,
            "ast_upper_limit_normal": 40,
            "alt_upper_limit_normal": 40,
            "at_risk_reinfection": risk_reinf
        }

        outputs, logs, applied_overrides = run_hcv_pathway(
            patient_data, overrides=st.session_state.hcv_overrides
        )

        # Boolean flags for flowchart
        has_dr = any(isinstance(o, DataRequest) for o in outputs)
        ab_neg = patient_data.get("hcv_antibody_result") == "negative"
        cleared = patient_data.get("hcv_antibody_result") == "positive" and patient_data.get("hcv_rna_result") == "negative"
        viremic = patient_data.get("hcv_antibody_result") == "positive" and patient_data.get("hcv_rna_result") == "positive"
        
        postponed = any(isinstance(o, Stop) and "postponed" in o.reason.lower() for o in outputs)
        decomp_stop = any(isinstance(o, Stop) and "decompensated" in o.reason.lower() for o in outputs)
        must_refer = any(isinstance(o, Action) and o.code in ["ALWAYS_REFER_SPECIALIST", "REFER_PROVIDER_COMFORT", "REFER_INSURANCE_REQUIREMENT"] for o in outputs)
        
        fib4_calc = "Calculate_FIB4" in [l.node for l in logs]
        fib4_dr = any(isinstance(o, DataRequest) and o.blocking_node == "Calculate_FIB4" for o in outputs)
        fib4_high = any(isinstance(o, Stop) and "FIB-4 > 3.25" in o.reason for o in outputs)
        
        therapy_offered = "Offer_Therapy" in [l.node for l in logs]
        cured = any(l.decision == "CURED" for l in logs)
        failed = any(isinstance(o, Stop) and "failed" in o.reason.lower() for o in outputs)

        # Color Constants
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
        W, H = 700, 950
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
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        CX = 350; NW, NH = 170, 50; DW, DH = 180, 58; EW, EH = 140, 46
        LEXT = 30; REXT = W - 30 - EW
        Y = {"entry": 18, "test": 100, "treat_now": 200, "pmh": 300, "fib4": 400, "therapy": 500, "cure": 600, "followup": 700}

        rect_node(CX-NW/2, Y["entry"], NW, NH, nc(True), "Assess Testing Need", "& Harm Reduction")
        vline(CX, Y["entry"]+NH, Y["test"], True)
        
        diamond_node(CX, Y["test"]+DH/2, DW, DH, dc(True), "Testing &", "Blood Work")
        v_test_exit = ab_neg or cleared
        exit_node(LEXT, Y["test"]+(DH-EH)/2, EW, EH, nc(v_test_exit, exit_=True), "Neg / Cleared", "→ Followup")
        elbow_line(CX-DW/2, Y["test"]+DH/2, LEXT+EW, Y["test"]+(DH-EH)/2+EH/2, v_test_exit, exit_=True, label="-")
        
        vline(CX, Y["test"]+DH, Y["treat_now"], viremic, label="Viremic")
        diamond_node(CX, Y["treat_now"]+DH/2, DW, DH, dc(viremic), "Treatment", "Appropriate Now?")
        
        exit_node(REXT, Y["treat_now"]+(DH-EH)/2, EW, EH, nc(postponed, exit_=True), "Postpone", "Monitor")
        elbow_line(CX+DW/2, Y["treat_now"]+DH/2, REXT, Y["treat_now"]+(DH-EH)/2+EH/2, postponed, exit_=True, label="No")

        v_pmh = viremic and not postponed
        vline(CX, Y["treat_now"]+DH, Y["pmh"], v_pmh, label="Yes")
        diamond_node(CX, Y["pmh"]+DH/2, DW, DH, dc(v_pmh), "Appropriate in", "Medical Home?")
        
        exit_node(REXT, Y["pmh"]+(DH-EH)/2, EW, EH, nc(decomp_stop or must_refer, urgent=decomp_stop), "Refer to", "Specialist")
        elbow_line(CX+DW/2, Y["pmh"]+DH/2, REXT, Y["pmh"]+(DH-EH)/2+EH/2, decomp_stop or must_refer, urgent=decomp_stop, label="No")

        v_fib4 = v_pmh and not decomp_stop and not must_refer
        vline(CX, Y["pmh"]+DH, Y["fib4"], v_fib4, label="Yes")
        diamond_node(CX, Y["fib4"]+DH/2, DW, DH, dc(v_fib4), "Calculate", "FIB-4")

        exit_node(REXT, Y["fib4"]+(DH-EH)/2, EW, EH, nc(fib4_high, urgent=True), "High FIB-4", "Refer")
        elbow_line(CX+DW/2, Y["fib4"]+DH/2, REXT, Y["fib4"]+(DH-EH)/2+EH/2, fib4_high, urgent=True, label="> 3.25")

        v_therapy = v_fib4 and not fib4_dr and not fib4_high
        vline(CX, Y["fib4"]+DH, Y["therapy"], v_therapy, label="≤ 3.25")
        rect_node(CX-NW/2, Y["therapy"], NW, NH, nc(v_therapy), "Seek Advice &", "Offer Therapy")

        vline(CX, Y["therapy"]+NH, Y["cure"], therapy_offered)
        diamond_node(CX, Y["cure"]+DH/2, DW, DH, dc(therapy_offered), "Confirm Cure", "12 Weeks Post")

        exit_node(REXT, Y["cure"]+(DH-EH)/2, EW, EH, nc(failed, urgent=True), "Treatment Failed", "Refer")
        elbow_line(CX+DW/2, Y["cure"]+DH/2, REXT, Y["cure"]+(DH-EH)/2+EH/2, failed, urgent=True, label="Positive")

        v_follow = ab_neg or cleared or cured
        vline(CX, Y["cure"]+DH, Y["followup"], cured, label="Negative")
        rect_node(CX-NW/2, Y["followup"], NW, NH, nc(v_follow, exit_=True), "Long Term Follow-up")

        ly = H - 22; lx = 18
        for col, lbl in [(C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">{"".join(svg)}</div>',
            height=980, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        fib4_disp = "Not calculated"
        if patient_data.get('age') and patient_data.get('ast') and patient_data.get('alt') and patient_data.get('platelets'):
            try:
                f = (patient_data['age'] * patient_data['ast']) / (patient_data['platelets'] * (patient_data['alt'] ** 0.5))
                fib4_disp = f"{f:.3f}"
            except: pass

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age:</b> {age if age > 0 else "Not specified"}</span><br>'
            f'<span><b>HCV Antibody:</b> {hcv_ab_sel} &nbsp;|&nbsp; <b>HCV RNA:</b> {hcv_rna_sel}</span><br>'
            f'<span><b>FIB-4 Score:</b> {fib4_disp}</span><br>'
            f'<span><b>Pregnant/Lactating:</b> {"Yes" if pregnant or lactating else "No"}</span>'
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
                        items += f"<li><b>{html.escape(str(k)).replace('_', ' ').title()}:</b> {html.escape(str(v))}</li>"
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine"}
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls

            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">🔒 Override available — reason required</p>'
                if a.override_options else ""
            )

            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{detail_html}{override_html}"
                "</div>",
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
                    f'<div class="action-card warning">'
                    f'<h4><span class="badge warning">DATA NEEDED</span> ⏳ {msg_html}</h4>'
                    f'<ul><li>Missing fields: {missing_str}</li></ul>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
                st.markdown(
                    f'<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span> 🛑 {reason_html}</h4>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.session_state.hcv_notes = st.text_area("Notes to attach to the saved output:", value=st.session_state.hcv_notes, height=180)

        if st.button("💾 Save this output", key="hcv_save_output"):
            st.success("Output saved for this session.")

        md_text = build_hcv_markdown(patient_data, outputs, st.session_state.hcv_overrides, st.session_state.hcv_notes)
        st.download_button(
            label="⬇️ Download Markdown summary",
            data=md_text.encode("utf-8"),
            file_name="hcv_summary.md",
            mime="text/markdown",
            key="hcv_download_md",
        )

        def _pretty(s: str) -> str: return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                
                for a in override_candidates:
                    opt = a.override_options
                    raw_node = opt["node"]
                    raw_field = opt["field"]
                    node_name = _pretty(raw_node)
                    field_name = _pretty(raw_field)
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node_name}** → `{field_name}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>', unsafe_allow_html=True)
                        existing = next((o for o in st.session_state.hcv_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        
                        new_val = st.radio(
                            f"Set `{field_name}` to:",
                            options=allowed,
                            index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}", horizontal=True
                        )
                        reason = st.text_input("Reason (required):", value=existing.reason if existing else "", key=f"ov_reason_{raw_node}_{raw_field}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.hcv_overrides = [o for o in st.session_state.hcv_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.hcv_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.hcv_overrides = [o for o in st.session_state.hcv_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.hcv_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.hcv_overrides:
                        st.markdown(
                            f'<div class="override-card">🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code> '
                            f'set to <b>{html.escape(str(o.new_value))}</b><br><span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span></div>',
                            unsafe_allow_html=True
                        )

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try: ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except: ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if log.used_inputs:
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
