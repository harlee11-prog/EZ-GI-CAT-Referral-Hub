import os, sys
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Ensure the engine is importable from the same directory or parent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nafld_engine import (
    run_nafld_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="NAFLD Pathway", layout="wide")

# ── MARKDOWN / PDF HELPERS ──────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_nafld_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# NAFLD Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / {str(patient_data.get('sex', 'N/A')).capitalize()}")
    lines.append(f"- **Incidental Abnormal ALT:** {_safe_text(patient_data.get('incidental_abnormal_alt'))}")
    lines.append(f"- **Incidental Ultrasound Fatty Liver:** {_safe_text(patient_data.get('incidental_ultrasound_fatty_liver'))}")
    lines.append(f"- **Average Drinks / Day:** {_safe_text(patient_data.get('average_drinks_per_day'))}")
    lines.append(f"- **ALT > 2x ULN (6 mo):** {_safe_text(patient_data.get('alt_gt_2x_uln_for_6_months'))}")
    lines.append(f"- **Other Causes Excluded:** {_safe_text(patient_data.get('other_causes_excluded'))}")
    lines.append(f"- **Baseline Investigations Complete:** {_safe_text(patient_data.get('baseline_investigations_complete'))}")
    lines.append(f"- **AST / ALT / Platelets:** {patient_data.get('ast', 'N/A')} / {patient_data.get('alt', 'N/A')} / {patient_data.get('platelets', 'N/A')}")
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
                    skip = {"bullets", "notes", "supported_by"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if v not in (None, False, "", []):
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

st.title("NAFLD Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "nafld_overrides" not in st.session_state:
    st.session_state.nafld_overrides = []
if "nafld_has_run" not in st.session_state:
    st.session_state.nafld_has_run = False
if "nafld_notes" not in st.session_state:
    st.session_state.nafld_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 50)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Entry Criteria**")
    incidental_alt = st.checkbox("Incidental abnormal ALT")
    incidental_us = st.checkbox("Incidental ultrasound finding of fatty liver")
    drinks = st.number_input("Average alcoholic drinks per day", 0.0, 20.0, 0.0, step=0.5)
    metabolic_risk = st.checkbox("Metabolic risk factors present (Obesity, Type 2 Diabetes, Hyperlipidemia)")

    st.markdown("**2. Persistent ALT Check**")
    alt_persistent_sel = st.selectbox("ALT >2x ULN for 6 months?", ["Unknown", "Yes", "No"])
    bool_map = {"Unknown": None, "Yes": True, "No": False}
    alt_persistent = bool_map[alt_persistent_sel]

    st.markdown("**3. Rule Out Other Causes**")
    causes_excluded_sel = st.selectbox("Other causes excluded?", ["Unknown", "Yes", "No"])
    causes_excluded = bool_map[causes_excluded_sel]
    
    st.caption("Workup Documentation")
    c1, c2 = st.columns(2)
    with c1:
        hbsag = st.checkbox("HBsAg completed")
        hcv = st.checkbox("Anti-HCV completed")
        autoimmune = st.checkbox("Autoimmune markers completed")
    with c2:
        iron = st.checkbox("Iron studies completed")
        celiac = st.checkbox("Celiac screen completed")
        ceruloplasmin = st.checkbox("Ceruloplasmin completed")

    st.markdown("**4. Medication & Lifestyle**")
    hepatotoxic = st.checkbox("Hepatotoxic meds present")
    inactivity = st.checkbox("Physical inactivity documented")
    diet_risk = st.checkbox("High-risk diet documented")

    st.markdown("**5. Baseline Investigations**")
    baseline_sel = st.selectbox("Baseline investigations complete?", ["Unknown", "Yes", "No"])
    baseline_complete = bool_map[baseline_sel]
    cirrhosis_susp = st.checkbox("Cirrhosis suspected")
    
    c3, c4 = st.columns(2)
    with c3:
        alp_val = st.number_input("ALP", value=None, min_value=0.0)
        ggt_val = st.number_input("GGT", value=None, min_value=0.0)
    with c4:
        hba1c_val = st.number_input("HbA1C", value=None, min_value=0.0)
        lipid_done = st.checkbox("Lipid profile done")

    st.markdown("**6. FIB-4 Inputs**")
    ast_val = st.number_input("AST (U/L)", value=None, min_value=0.0)
    alt_val = st.number_input("ALT (U/L)", value=None, min_value=0.0)
    platelets_val = st.number_input("Platelets (10^9/L)", value=None, min_value=0.0)

    st.markdown("**7. Low Risk Management / Follow-up**")
    exercise_c = st.checkbox("Exercise counselled")
    diet_c = st.checkbox("Diet counselled")
    weight_goal = st.checkbox("Weight loss goal set")
    smoke_sel = st.selectbox("Smoking Status", ["Unknown", "Current", "Former", "Never"])
    smoke_status = smoke_sel if smoke_sel != "Unknown" else None
    alcohol_c = st.checkbox("Alcohol reduction counselled")
    hep_a_v = st.checkbox("Hep A Vaccinated")
    hep_b_v = st.checkbox("Hep B Vaccinated")
    fib4_interval = st.number_input("FIB-4 Recheck Interval (years)", value=None, min_value=0, max_value=10)
    follow_up_doc = st.checkbox("Follow-up plan documented")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.nafld_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.nafld_overrides = []
        if "nafld_saved_output" in st.session_state:
            del st.session_state["nafld_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.nafld_has_run:
        patient_data = {
            "age": age,
            "sex": sex,
            "incidental_abnormal_alt": incidental_alt,
            "incidental_ultrasound_fatty_liver": incidental_us,
            "average_drinks_per_day": drinks,
            "metabolic_risk_factors_present": metabolic_risk or None,
            "alt_gt_2x_uln_for_6_months": alt_persistent,
            "other_causes_excluded": causes_excluded,
            "hepatitis_b_surface_antigen_done": hbsag,
            "hepatitis_c_antibody_done": hcv,
            "autoimmune_markers_done": autoimmune,
            "iron_studies_done": iron,
            "celiac_screen_done": celiac,
            "ceruloplasmin_done": ceruloplasmin,
            "hepatotoxic_medications_present": hepatotoxic or None,
            "physical_inactivity": inactivity or None,
            "diet_high_risk": diet_risk or None,
            "baseline_investigations_complete": baseline_complete,
            "cirrhosis_suspected": cirrhosis_susp or None,
            "alp": alp_val,
            "ggt": ggt_val,
            "hba1c": hba1c_val,
            "lipid_profile_done": lipid_done or None,
            "ast": ast_val,
            "alt": alt_val,
            "platelets": platelets_val,
            "exercise_counselled": exercise_c or None,
            "diet_counselled": diet_c or None,
            "weight_loss_goal_set": weight_goal or None,
            "smoking_status": smoke_status,
            "alcohol_reduction_counselled": alcohol_c or None,
            "hep_a_vaccinated": hep_a_v or None,
            "hep_b_vaccinated": hep_b_v or None,
            "fib4_recheck_interval_years": int(fib4_interval) if fib4_interval is not None else None,
            "follow_up_plan_documented": follow_up_doc or None,
        }

        outputs, logs, applied_overrides = run_nafld_pathway(
            patient_data, overrides=st.session_state.nafld_overrides
        )

        entry_met = bool(incidental_alt or incidental_us)
        high_alcohol = any(isinstance(o, Stop) and "significant alcohol" in o.reason.lower() for o in outputs)
        alt_check_done = alt_persistent is not None
        alt_high = alt_persistent is True
        causes_checked = causes_excluded is not None
        causes_excl = causes_excluded is True
        base_checked = baseline_complete is not None
        base_comp = baseline_complete is True
        
        nafld_diagnosed = entry_met and causes_excl
        for o in st.session_state.nafld_overrides:
            if o.target_node == "NAFLD_Diagnosis" and o.field == "nafld_diagnosed":
                nafld_diagnosed = o.new_value

        fib4_checked = ast_val and alt_val and platelets_val and age
        fib4_val = None
        if fib4_checked and alt_val > 0 and platelets_val > 0:
            fib4_val = (age * ast_val) / (platelets_val * (alt_val ** 0.5))

        fib4_high = fib4_val is not None and fib4_val >= 1.30

        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if exit_: return C_EXIT
            return C_MAIN

        def dc(vis): return C_DIAMOND if vis else C_UNVISIT
        def mid(vis, urgent=False, exit_=False):
            if not vis: return "ma"
            if urgent: return "mr"
            if exit_: return "mo"
            return "mg"

        svg = []
        W, H = 700, 1050
        svg.append(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="' + str(H) + '" '
            'viewBox="0 0 ' + str(W) + ' ' + str(H) + '" '
            'style="background:' + C_BG + ';border-radius:12px;font-family:Arial,sans-serif">'
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
            "entry": 18, "alc": 110, "alt_pers": 210, "rule_out": 310, "med_life": 410,
            "baseline": 510, "diag": 610, "fib4": 710, "med_home": 810
        }

        # 1. Entry
        diamond_node(CX, Y["entry"]+DH/2, DW, DH, dc(True), "1. Suspected", "NAFLD?")
        exit_node(LEXT, Y["entry"]+(DH-EH)/2, EW, EH, nc(not entry_met, exit_=True), "Not Suspected", "Exit Pathway")
        elbow_line(CX-DW/2, Y["entry"]+DH/2, LEXT+EW, Y["entry"]+(DH-EH)/2+EH/2, not entry_met, exit_=True, label="No")

        v2 = entry_met
        vline(CX, Y["entry"]+DH, Y["alc"], v2, label="Yes")

        # 2. Alcohol
        diamond_node(CX, Y["alc"]+DH/2, DW, DH, dc(v2), "High Alcohol", "Consumption?")
        exit_node(REXT, Y["alc"]+(DH-EH)/2, EW, EH, nc(high_alcohol, exit_=True), "Counsel Reduction", "Retest ALT in 6-8w")
        elbow_line(CX+DW/2, Y["alc"]+DH/2, REXT, Y["alc"]+(DH-EH)/2+EH/2, high_alcohol, exit_=True, label="Yes")

        v3 = v2 and not high_alcohol
        vline(CX, Y["alc"]+DH, Y["alt_pers"], v3, label="No")

        # 3. Persistent ALT
        diamond_node(CX, Y["alt_pers"]+DH/2, DW, DH, dc(v3 and alt_check_done), "2. ALT >2x ULN", "for 6 months?")
        v_alt_high = v3 and alt_check_done and alt_high
        
        v4 = v3 and alt_check_done
        vline(CX, Y["alt_pers"]+DH, Y["rule_out"], v4)

        # 4. Rule Out Causes
        diamond_node(CX, Y["rule_out"]+DH/2, DW, DH, dc(v4 and causes_checked), "3. Other Causes", "Excluded?")
        v_not_excl = v4 and causes_checked and not causes_excl
        exit_node(REXT, Y["rule_out"]+(DH-EH)/2, EW, EH, nc(v_not_excl, exit_=True), "Treat/Refer for", "Non-NAFLD Cause")
        elbow_line(CX+DW/2, Y["rule_out"]+DH/2, REXT, Y["rule_out"]+(DH-EH)/2+EH/2, v_not_excl, exit_=True, label="No")

        v5 = v4 and causes_checked and causes_excl
        vline(CX, Y["rule_out"]+DH, Y["med_life"], v5, label="Yes")

        # 5. Med & Lifestyle
        rect_node(CX-NW/2, Y["med_life"], NW, NH, nc(v5), "4. Med & Lifestyle", "Review")
        vline(CX, Y["med_life"]+NH, Y["baseline"], v5)

        # 6. Baseline Investigations
        rect_node(CX-NW/2, Y["baseline"], NW, NH, nc(v5 and base_checked), "5. Baseline", "Investigations")
        v6 = v5 and base_checked and base_comp
        vline(CX, Y["baseline"]+NH, Y["diag"], v6)

        # 7. Diagnosis
        rect_node(CX-NW/2, Y["diag"], NW, NH, nc(v6 and nafld_diagnosed), "NAFLD Diagnosed")
        v7 = v6 and nafld_diagnosed
        vline(CX, Y["diag"]+NH, Y["fib4"], v7)

        # 8. FIB4
        diamond_node(CX, Y["fib4"]+DH/2, DW, DH, dc(v7 and fib4_checked), "6. FIB-4", ">= 1.30?")
        v_fib_high = v7 and fib4_checked and fib4_high
        exit_node(REXT, Y["fib4"]+(DH-EH)/2, EW, EH, nc(v_fib_high, urgent=True), "Refer to", "Liver Specialist")
        elbow_line(CX+DW/2, Y["fib4"]+DH/2, REXT, Y["fib4"]+(DH-EH)/2+EH/2, v_fib_high, urgent=True, label="Yes")

        v8 = v7 and fib4_checked and not fib4_high
        vline(CX, Y["fib4"]+DH, Y["med_home"], v8, label="No")

        # 9. Low Risk Home
        rect_node(CX-NW/2, Y["med_home"], NW, NH, nc(v8), "7. Low Risk", "Medical Home")

        ly = H - 22; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=1080, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Entry Met:</b> {"Yes" if entry_met else "No"}</span><br>'
            f'<span><b>ALT Persistent:</b> {alt_persistent_sel}</span><br>'
            f'<span><b>Other Causes Excl:</b> {causes_excluded_sel}</span><br>'
            f'<span><b>Baseline Complete:</b> {baseline_sel}</span>'
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
                skip = {"bullets", "notes", "supported_by"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
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
                "🔒 Override available — reason required</p>"
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

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.session_state.nafld_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.nafld_notes,
            height=180,
        )

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [{"type": type(o).__name__} for o in outputs],
                "clinician_notes": st.session_state.nafld_notes,
            },
        }

        if st.button("💾 Save this output", key="nafld_save_output"):
            st.session_state.nafld_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "nafld_saved_output" in st.session_state:
            md_text = build_nafld_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.nafld_overrides,
                notes=st.session_state.nafld_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="nafld_summary.md",
                mime="text/markdown",
                key="nafld_download_md",
            )

        def _pretty(s: str) -> str:
            return s.replace("_", " ").title()

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)

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
                        existing = next((o for o in st.session_state.nafld_overrides if o.target_node == raw_node and o.field == raw_field), None)
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
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required to apply an override.")
                                else:
                                    st.session_state.nafld_overrides = [o for o in st.session_state.nafld_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.nafld_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Override applied. Click **▶ Run Pathway** to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.nafld_overrides = [o for o in st.session_state.nafld_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.nafld_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.nafld_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code>'
                            f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
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
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
