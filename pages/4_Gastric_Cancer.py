import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from gastric_cancer_engine import (
    run_gastric_cancer_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="Gastric Cancer", page_icon="🎗️", layout="wide")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_gc_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Gastric Cancer Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    
    ctx_str = str(patient_data.get('patient_context', '')).replace('_', ' ').title()
    lines.append(f"- **Pathway Context:** {ctx_str}")
    lines.append(f"- **Age:** {patient_data.get('age', 'Not entered')}")
    lines.append(f"- **Asymptomatic:** {'Yes' if patient_data.get('asymptomatic') else 'No' if patient_data.get('asymptomatic') is False else 'Unknown'}")
    lines.append(f"- **Dyspepsia > 1 month:** {'Yes' if patient_data.get('symptomatic_dyspepsia_over_1_month') else 'No' if patient_data.get('symptomatic_dyspepsia_over_1_month') is False else 'Unknown'}")
    lines.append(f"- **Smoking Pack Years:** {patient_data.get('smoking_pack_years', 'Not entered')}")
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
                    for src in o.details.get("supported_by", []):
                        lines.append(f"  - Support: {_safe_text(src)}")
                    skip = {"supported_by"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_pretty(k)}: {_safe_text(v)}")
            elif isinstance(o, Stop):
                reason = _safe_text(o.reason)
                lines.append(f"- **[STOP]** {reason}")
                if getattr(o, "actions", None):
                    for a in o.actions:
                        lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                msg = _safe_text(o.message)
                missing = ", ".join(_pretty(f) for f in o.missing_fields)
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

st.title("Gastric Cancer Prevention, Screening & Diagnosis")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "gc_overrides" not in st.session_state:
    st.session_state.gc_overrides = []
if "gc_has_run" not in st.session_state:
    st.session_state.gc_has_run = False
if "gc_notes" not in st.session_state:
    st.session_state.gc_notes = ""


left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    context_sel = st.radio(
        "Pathway Context",
        ["Primary Prevention", "Targeted Screening (Asymptomatic)", "Symptomatic Dyspepsia"],
        help="Select the specific branch of the pathway to evaluate."
    )
    ctx_map = {
        "Primary Prevention": "prevention",
        "Targeted Screening (Asymptomatic)": "asymptomatic_screening",
        "Symptomatic Dyspepsia": "symptomatic_dyspepsia"
    }

    st.markdown("**Demographics**")
    age = st.number_input("Age", 18, 120, value=52)

    st.markdown("**Prevention & Screening Risk Factors**")
    from_endemic = st.checkbox("Immigrant (1st gen) from high-risk region", help="East Asia, Eastern Europe, Central/South America")
    family_origin = st.checkbox("Family origins in endemic region")
    hh_hp_positive = st.checkbox("Household member H. pylori positive")
    
    fh_gastric = st.checkbox("1st-degree relative with gastric cancer")
    fh_age = st.number_input("Age of relative at diagnosis (if applicable)", min_value=0, max_value=120, value=0, help="Leave 0 if unknown/not applicable.")
    
    hereditary_synd = st.checkbox("Hereditary GI polyposis or cancer syndrome", help="e.g. FAP, Lynch, Peutz-Jeghers")
    chronic_hp = st.checkbox("Chronic H. pylori infection (ongoing, untreated)")
    
    col_l, col_r = st.columns(2)
    with col_l:
        pack_years = st.number_input("Smoking Pack Years", min_value=0, value=0)
    with col_r:
        low_ses = st.checkbox("Low socioeconomic status")
    high_risk_diet = st.checkbox("High salt, red meat, processed meat/foods diet")

    st.markdown("**Symptomatic & Alarm Features**")
    dyspepsia_1mo = st.checkbox("Dyspepsia symptoms > 1 month", help="Epigastric pain, bloating, early satiety")
    
    st.markdown("*Alarm Features*")
    al_fh_cancer = st.checkbox("Family history (1st degree) esophageal or gastric cancer")
    al_onset_60 = st.checkbox("Age > 60 with new and persistent symptoms (>3 months)")
    al_wt_loss = st.checkbox("Unexplained weight loss (≥5% over 6-12 months)")
    al_bleed = st.checkbox("GI Bleeding (Black stool or blood in vomit)")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_vomit = st.checkbox("Persistent vomiting (not cannabis-related)")
    al_ida = st.checkbox("Iron deficiency anemia")
    al_imaging = st.checkbox("Concerning imaging findings for gastric cancer")

    st.markdown("**Management Response**")
    unsat_mgmt = st.checkbox("Unsatisfactory response to symptomatic management / pharma therapy")
    advice_considered = st.checkbox("Specialist advice service considered prior to referral")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.gc_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.gc_overrides = []
        if "gc_saved_output" in st.session_state:
            del st.session_state["gc_saved_output"]

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.gc_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "patient_context": ctx_map[context_sel],
            "age": age,
            "asymptomatic": ctx_map[context_sel] == "asymptomatic_screening",
            "from_endemic_region": from_endemic or None,
            "family_origin_endemic_region": family_origin or None,
            "household_member_h_pylori_positive": hh_hp_positive or None,
            "family_history_gastric_cancer_first_degree": fh_gastric or None,
            "family_member_gastric_cancer_age_at_diagnosis": fh_age if fh_age > 0 else None,
            "hereditary_gi_polyposis_or_cancer_syndrome": hereditary_synd or None,
            "chronic_h_pylori_infection": chronic_hp or None,
            "smoking_pack_years": pack_years if pack_years > 0 else None,
            "high_salt_or_red_processed_meat_diet": high_risk_diet or None,
            "low_socioeconomic_status": low_ses or None,
            "symptomatic_dyspepsia_over_1_month": dyspepsia_1mo or None,
            "family_history_gastric_or_esophageal_cancer_first_degree": al_fh_cancer or None,
            "symptom_onset_after_age_60": al_onset_60 or None,
            "unintended_weight_loss": al_wt_loss or None,
            "black_stool_or_blood_in_vomit": al_bleed or None,
            "dysphagia": al_dysphagia or None,
            "persistent_vomiting": al_vomit or None,
            "iron_deficiency_anemia_present": al_ida or None,
            "concerning_imaging_for_gastric_cancer": al_imaging or None,
            "unsatisfactory_response_to_management": unsat_mgmt or None,
            "advice_service_considered": advice_considered or None,
        }

        outputs, logs, applied_overrides = run_gastric_cancer_pathway(
            patient_data, overrides=st.session_state.gc_overrides
        )

        # ── Compute derived flags for SVG ──────────────────────────────────
        asym_visited = any(l.node == "Targeted_Screening_Risk_Assessment" for l in logs)
        symp_visited = any(l.node == "Symptomatic_Dyspepsia_Assessment" for l in logs)
        alarm_visited = any(l.node == "Alarm_Features_Symptomatic" for l in logs)
        mgmt_visited = any(l.node == "Management_Response_Symptomatic" for l in logs)
        
        screening_yes = any(l.decision == "SCREENING_INDICATED" for l in logs)
        screening_no = any(l.decision == "SCREENING_NOT_INDICATED" for l in logs)
        alarm_yes = any(l.decision == "SYMPTOMATIC_ALARM_PRESENT" for l in logs)
        mgmt_refer = any(l.decision in ["FAILED_MANAGEMENT_REFER", "FAILED_MANAGEMENT_ADVICE_FIRST"] for l in logs)
        mgmt_continue = any(l.decision == "PATHWAY_COMPLETE" for l in logs)

        ctx_prev = patient_data["patient_context"] == "prevention"
        ctx_asym = patient_data["patient_context"] == "asymptomatic_screening"
        ctx_symp = patient_data["patient_context"] == "symptomatic_dyspepsia"

        # ── SVG PATHWAY VISUAL ─────────────────────────────────────────────
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
        W, H = 820, 680
        svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" '
            f'viewBox="0 0 {W} {H}" '
            f'style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
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

        # ── 3-Lane PDF Layout ──────────────────────────────────────────────
        NW, NH = 160, 50; DW, DH = 170, 58; EW, EH = 140, 46
        XC = 410  # Center lane (Asymptomatic)
        XL = 160  # Left lane (Prevention)
        XR = 660  # Right lane (Symptomatic)
        
        Y_START = 50
        Y_L1 = 160
        Y_L2 = 280
        Y_L3 = 400
        Y_L4 = 520

        # Top Node Router
        rect_node(XC-NW/2, Y_START, NW, NH, nc(True), "Patient Context", sub="Select Pathway Branch")
        
        # Branch Lines
        elbow_line(XC-NW/2, Y_START+NH/2, XL, Y_L1-NH/2, ctx_prev, label="Prevention")
        vline(XC, Y_START+NH, Y_L1-DH/2, ctx_asym, label="Asymptomatic")
        elbow_line(XC+NW/2, Y_START+NH/2, XR, Y_L1-NH/2, ctx_symp, label="Symptomatic")

        # ── Lane 1 (Left): Primary Prevention ───────────────────────────────
        rect_node(XL-NW/2, Y_L1-NH/2, NW, NH, nc(ctx_prev), "Primary Prevention", "for ALL", sub="Modifiable Risk Factors")
        vline(XL, Y_L1+NH/2, Y_L2-EH/2, ctx_prev)
        exit_node(XL-EW/2, Y_L2-EH/2, EW, EH+20, nc(ctx_prev, exit_=True), "Screening NOT Indicated.", "Counsel on primary", rx=5)
        svgt(XL, Y_L2+EH/2+10, "prevention & reassess.", C_TEXT if ctx_prev else C_DIM, 9)

        # ── Lane 2 (Center): Asymptomatic Screening ─────────────────────────
        diamond_node(XC, Y_L1, DW, DH, dc(asym_visited), "Risk Assessment for", "Targeted Screening")
        
        # Yes -> Screening
        vline(XC, Y_L1+DH/2, Y_L2-EH/2, screening_yes, urgent=True, label="Yes")
        exit_node(XC-EW/2, Y_L2-EH/2, EW, EH, nc(screening_yes, urgent=True), "Consider Screening", "Endoscopy")
        
        # No -> Point to Prevention
        elbow_line(XC-DW/2, Y_L1, XL+EW/2+10, Y_L2-EH/2, screening_no, exit_=True, label="No")

        # ── Lane 3 (Right): Symptomatic Dyspepsia ───────────────────────────
        rect_node(XR-NW/2, Y_L1-NH/2, NW, NH, nc(symp_visited), "Dyspepsia Symptoms", "(> 1 month)")
        vline(XR, Y_L1+NH/2, Y_L2-DH/2, alarm_visited)
        
        diamond_node(XR, Y_L2, DW, DH, dc(alarm_visited), "Assess for", "Alarm Features")
        
        # Yes -> Urgent Referral
        elbow_line(XR+DW/2, Y_L2, W-EW-20+EW/2, Y_L3-EH/2, alarm_yes, urgent=True, label="Yes")
        exit_node(W-EW-20, Y_L3-EH/2, EW, EH, nc(alarm_yes, urgent=True), "Refer to Local GI /", "Endoscopy Provider")
        
        # No -> Continue Dyspepsia
        vline(XR, Y_L2+DH/2, Y_L3-DH/2, mgmt_visited, label="No")
        diamond_node(XR, Y_L3, DW, DH, dc(mgmt_visited), "Management Response", "Unsatisfactory?")
        
        # Yes -> Refer
        elbow_line(XR+DW/2, Y_L3, W-EW-20+EW/2, Y_L4-EH/2, mgmt_refer, urgent=True, label="Yes")
        exit_node(W-EW-20, Y_L4-EH/2, EW, EH, nc(mgmt_refer, exit_=True), "Refer for", "Failed Management")
        
        # No -> Continue Primary Care
        vline(XR, Y_L3+DH/2, Y_L4-EH/2, mgmt_continue, exit_=True, label="No")
        exit_node(XR-EW/2, Y_L4-EH/2, EW, EH+15, nc(mgmt_continue, exit_=True), "Continue to manage", "within primary care", rx=5)
        svgt(XR, Y_L4+EH/2+5, "as per dyspepsia pathway", C_TEXT if mgmt_continue else C_DIM, 9)

        # ── Legend ─────────────────────────────────────────────────────────
        ly = H - 22; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Branch"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=720, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ───────────────────────────────────────────
        ctx_display = str(patient_data["patient_context"]).replace("_", " ").title()
        
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Pathway Branch:</b> {ctx_display}</span><br>'
            f'<span><b>Age:</b> {age} &nbsp;|&nbsp; <b>Smoking Pack Years:</b> {pack_years}</span><br>'
            f'<span><b>Asymptomatic:</b> {"Yes" if patient_data["asymptomatic"] else "No"} &nbsp;|&nbsp; '
            f'<b>Dyspepsia > 1 month:</b> {"Yes" if dyspepsia_1mo else "No"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        # ── Step grouping map ──────────────────────────────────────────────
        STEP_GROUPS = {
            "prevention": {
                "label": "Primary Prevention & Counseling",
                "icon": "🛡️",
                "cls": "info",
                "codes": {
                    "CONSIDER_H_PYLORI_TESTING_PREVENTION", "COUNSEL_SMOKING_CESSATION",
                    "COUNSEL_ALCOHOL_MODERATION", "COUNSEL_DIETARY_RISK_REDUCTION"
                },
            },
            "dyspepsia": {
                "label": "Dyspepsia Management",
                "icon": "📋",
                "cls": "routine",
                "codes": {
                    "CHAIN_DYSPEPSIA_PATHWAY", "ROUTE_DYSPEPSIA_PATHWAY",
                    "NO_SYMPTOMATIC_ALARM_FEATURES", "DYSPEPSIA_CHAIN_FAILED", "DYSPEPSIA_INPUT_MISSING"
                },
            },
            "advisory": {
                "label": "Specialist Advisory",
                "icon": "📞",
                "cls": "warning",
                "codes": {
                    "CONSIDER_ADVICE_SERVICE"
                },
            }
        }

        # Build code → group lookup
        code_to_group = {}
        for gkey, gdata in STEP_GROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        # Classify all outputs
        grouped: dict = {k: [] for k in STEP_GROUPS}
        stops_and_requests = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                # Dynamically catch DYSP_ actions
                if output.code.startswith("DYSP_"):
                    grouped["dyspepsia"].append(output)
                else:
                    gkey = code_to_group.get(output.code)
                    if gkey:
                        grouped[gkey].append(output)
        
        # Also collect Stop.actions for override candidates
        for output in outputs:
            if isinstance(output, Stop):
                for a in output.actions:
                    if a.override_options:
                        override_candidates.append(a)

        # ── Render a group card ────────────────────────────────────────────
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

            # Collect override-bearing actions
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

        # ── Render blocking / stop cards ───────────────────────────────────
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
                # Determine classification
                is_complete = "completed" in output.reason.lower() or "not indicated" in output.reason.lower() or "continue" in output.reason.lower()
                is_refer = "refer" in output.reason.lower() or "indicated" in output.reason.lower()
                is_invalid = "invalid" in output.reason.lower() or "applies to" in output.reason.lower() or "requires" in output.reason.lower()

                if is_complete:
                    bg, border, icon = "#052e16", "#22c55e", "✅"
                    title = "Pathway Complete — Continue Care in Patient Medical Home"
                    tcol = "#bbf7d0"
                elif is_refer:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🏥"
                    title = "Referral Required / Screening Indicated"
                    tcol = "#fecaca"
                elif is_invalid:
                    bg, border, icon = "#2d1a00", "#f59e0b", "⚠️"
                    title = "Pathway Condition Not Met"
                    tcol = "#fde68a"
                else:
                    bg, border, icon = "#1e1e2e", "#6366f1", "ℹ️"
                    title = output.reason
                    tcol = "#c7d2fe"

                # If the title is generic, prefix the actual reason
                display_title = f"{title}: {output.reason}" if title != output.reason and not is_invalid else output.reason

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
                    f'font-weight:700;color:{tcol}">{icon} {html.escape(display_title)}</p>'
                    f'{action_block}</div>',
                    unsafe_allow_html=True,
                )

        # ── Render everything ──────────────────────────────────────────────
        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        # Priority stops / data requests first
        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        # Grouped action steps in order
        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        # Terminal outcomes
        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        # ── Clinician Notes ────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.gc_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.gc_notes,
            height=120,
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
                    for o in st.session_state.gc_overrides
                ],
                "clinician_notes": st.session_state.gc_notes,
            },
        }

        if st.button("💾 Save this output", key="gc_save_output"):
            st.session_state.gc_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "gc_saved_output" in st.session_state:
            md_text = build_gc_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.gc_overrides,
                notes=st.session_state.gc_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="gastric_cancer_summary.md",
                mime="text/markdown",
                key="gc_download_md",
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
                            (o for o in st.session_state.gc_overrides
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
                                    st.session_state.gc_overrides = [
                                        o for o in st.session_state.gc_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.gc_overrides.append(
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
                                st.session_state.gc_overrides = [
                                    o for o in st.session_state.gc_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.gc_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.gc_overrides:
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
                if log.used_inputs
