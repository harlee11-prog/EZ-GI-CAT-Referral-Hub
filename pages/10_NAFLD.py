import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from nafld_engine import (
    run_nafld_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="NAFLD", page_icon="🫁", layout="wide")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_nafld_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# NAFLD Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(
        f"- **Age / Sex:** {patient_data.get('age')} / "
        f"{str(patient_data.get('sex', '')).capitalize()}"
    )
    fib4 = patient_data.get("fib4")
    lines.append(f"- **FIB-4 Score:** {fib4 if fib4 is not None else 'Not yet calculated'}")
    lines.append(f"- **ALT:** {patient_data.get('alt', 'Not entered')} U/L")
    lines.append(f"- **AST:** {patient_data.get('ast', 'Not entered')} U/L")
    lines.append(f"- **Platelets:** {patient_data.get('platelets', 'Not entered')} ×10⁹/L")
    lines.append(f"- **Avg drinks/day:** {patient_data.get('average_drinks_per_day', 'Not entered')}")
    lines.append(
        f"- **Incidental abnormal ALT:** {'Yes' if patient_data.get('incidental_abnormal_alt') else 'No'}"
    )
    lines.append(
        f"- **Incidental fatty liver on US:** {'Yes' if patient_data.get('incidental_ultrasound_fatty_liver') else 'No'}"
    )
    lines.append(
        f"- **Other causes excluded:** {'Yes' if patient_data.get('other_causes_excluded') else 'No' if patient_data.get('other_causes_excluded') is False else 'Unknown'}"
    )
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

st.title("Non-Alcoholic Fatty Liver Disease (NAFLD)")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "nafld_overrides" not in st.session_state:
    st.session_state.nafld_overrides = []
if "nafld_has_run" not in st.session_state:
    st.session_state.nafld_has_run = False
if "nafld_notes" not in st.session_state:
    st.session_state.nafld_notes = ""


left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    age = st.number_input("Age", 18, 120, value=55)
    sex = st.selectbox("Sex", ["male", "female"])
    avg_drinks = st.number_input(
        "Average alcohol intake (drinks/day)",
        min_value=0.0,
        max_value=20.0,
        value=0.0,
        step=0.5,
        help="Males >2/day or females >1/day = significant alcohol (pathway not validated)",
    )

    st.markdown("**Suspected NAFLD — Entry Criteria**")
    incidental_alt = st.checkbox("Incidental finding of abnormal ALT")
    incidental_us = st.checkbox("Incidental ultrasound finding of fatty liver")

    st.markdown("**Metabolic Risk Factors**")
    metabolic_risk = st.checkbox(
        "Metabolic risk factors present (obesity, T2DM, hypertension, hyperlipidemia)"
    )

    st.markdown("**ALT Persistence**")
    alt_persistent_sel = st.selectbox(
        "Is ALT >2× ULN for ≥6 months?",
        ["Unknown / Not assessed", "Yes", "No"],
    )
    alt_persistent_map = {"Unknown / Not assessed": None, "Yes": True, "No": False}

    st.markdown("**Rule Out Other Causes**")
    other_causes_sel = st.selectbox(
        "Have other causes of liver disease been excluded?",
        ["Unknown / Pending", "Yes — excluded", "No — alternative cause identified"],
    )
    other_causes_map = {
        "Unknown / Pending": None,
        "Yes — excluded": True,
        "No — alternative cause identified": False,
    }

    with st.expander("Stepwise workup status (optional — for guidance outputs)"):
        hbsag_done = st.checkbox("HBsAg testing done", value=True)
        anti_hcv_done = st.checkbox("Anti-HCV testing done", value=True)
        autoimmune_done = st.checkbox("ANA / anti-smooth muscle / Ig done", value=True)
        iron_done = st.checkbox("Fasting ferritin / iron/TIBC done", value=True)
        celiac_done = st.checkbox("Celiac disease screen done", value=True)
        ceruloplasmin_done = st.checkbox("Ceruloplasmin done (if age <30)", value=True)
        hepatotoxic_meds = st.checkbox("Hepatotoxic medications / herbals present")

    st.markdown("**Medication & Lifestyle Review**")
    physical_inactivity = st.checkbox("Physical inactivity documented")
    diet_high_risk = st.checkbox("High-risk diet documented")

    st.markdown("**Baseline Investigations**")
    baseline_sel = st.selectbox(
        "Baseline investigations complete?",
        ["Not done / Pending", "Yes — complete"],
    )
    baseline_map = {"Not done / Pending": False, "Yes — complete": True}
    cirrhosis_suspected = st.checkbox("Cirrhosis suspected (add INR / bilirubin / albumin)")

    st.markdown("**Lab Values for FIB-4**")
    col_l, col_r = st.columns(2)
    with col_l:
        alt_val = st.number_input("ALT (U/L)", min_value=0.0, value=0.0, step=1.0)
        ast_val = st.number_input("AST (U/L)", min_value=0.0, value=0.0, step=1.0)
    with col_r:
        platelets_val = st.number_input("Platelets (×10⁹/L)", min_value=0.0, value=0.0, step=1.0)
        alp_val = st.number_input("ALP (U/L)", min_value=0.0, value=0.0, step=1.0)
    ggt_val = st.number_input("GGT (U/L)", min_value=0.0, value=0.0, step=1.0)
    hba1c_val = st.number_input("HbA1C (%)", min_value=0.0, value=0.0, step=0.1)
    lipid_done = st.checkbox("Lipid profile completed")

    st.markdown("**Low-Risk Lifestyle Follow-up (optional)**")
    exercise_counselled = st.checkbox("Exercise counselling done")
    diet_counselled = st.checkbox("Diet counselling done")
    weight_loss_goal = st.checkbox("Weight loss goal set")
    alcohol_reduction = st.checkbox("Alcohol reduction counselling done")
    hep_a_vax = st.checkbox("Hepatitis A immunization documented")
    hep_b_vax = st.checkbox("Hepatitis B immunization documented")
    smoking_sel = st.selectbox(
        "Smoking status",
        ["Not documented", "Non-smoker", "Current smoker", "Former smoker"],
    )
    smoking_map = {
        "Not documented": None,
        "Non-smoker": "non-smoker",
        "Current smoker": "current",
        "Former smoker": "former",
    }
    followup_plan = st.checkbox("Follow-up plan documented")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.nafld_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.nafld_overrides = []
        if "nafld_saved_output" in st.session_state:
            del st.session_state["nafld_saved_output"]

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.nafld_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age,
            "sex": sex,
            "average_drinks_per_day": avg_drinks,
            "incidental_abnormal_alt": incidental_alt or None,
            "incidental_ultrasound_fatty_liver": incidental_us or None,
            "metabolic_risk_factors_present": metabolic_risk or None,
            "alt_gt_2x_uln_for_6_months": alt_persistent_map[alt_persistent_sel],
            "other_causes_excluded": other_causes_map[other_causes_sel],
            "hepatitis_b_surface_antigen_done": hbsag_done,
            "hepatitis_c_antibody_done": anti_hcv_done,
            "autoimmune_markers_done": autoimmune_done,
            "iron_studies_done": iron_done,
            "celiac_screen_done": celiac_done,
            "ceruloplasmin_done": ceruloplasmin_done,
            "hepatotoxic_medications_present": hepatotoxic_meds or None,
            "physical_inactivity": physical_inactivity or None,
            "diet_high_risk": diet_high_risk or None,
            "baseline_investigations_complete": baseline_map[baseline_sel],
            "cirrhosis_suspected": cirrhosis_suspected or None,
            "alt": alt_val if alt_val > 0 else None,
            "ast": ast_val if ast_val > 0 else None,
            "platelets": platelets_val if platelets_val > 0 else None,
            "alp": alp_val if alp_val > 0 else None,
            "ggt": ggt_val if ggt_val > 0 else None,
            "hba1c": hba1c_val if hba1c_val > 0 else None,
            "lipid_profile_done": lipid_done or None,
            "exercise_counselled": exercise_counselled or None,
            "diet_counselled": diet_counselled or None,
            "weight_loss_goal_set": weight_loss_goal or None,
            "alcohol_reduction_counselled": alcohol_reduction or None,
            "hep_a_vaccinated": hep_a_vax or None,
            "hep_b_vaccinated": hep_b_vax or None,
            "smoking_status": smoking_map[smoking_sel],
            "fib4_recheck_interval_years": None,
            "follow_up_plan_documented": followup_plan or None,
        }

        outputs, logs, applied_overrides = run_nafld_pathway(
            patient_data, overrides=st.session_state.nafld_overrides
        )

        # ── Compute derived flags for SVG ──────────────────────────────────
        fib4_computed = None
        low_risk = False
        high_risk = False
        nafld_diagnosed = False
        significant_alcohol = False
        other_causes_not_excluded = False

        for o in outputs:
            if isinstance(o, Action) and o.code == "FIB4_CALCULATED":
                fib4_computed = o.details.get("fib4")
                low_risk = fib4_computed is not None and fib4_computed < 1.30
                high_risk = fib4_computed is not None and fib4_computed >= 1.30
            if isinstance(o, Action) and o.code in ("NAFLD_DIAGNOSED",):
                nafld_diagnosed = True
            if isinstance(o, Stop) and "significant alcohol" in o.reason.lower():
                significant_alcohol = True
            if isinstance(o, Stop) and "alternative liver disease" in o.reason.lower():
                other_causes_not_excluded = True

        if any(isinstance(o, Action) and o.code == "NAFLD_DIAGNOSED" for o in outputs):
            nafld_diagnosed = True

        entry_met = bool(incidental_alt or incidental_us)
        alcohol_stop = significant_alcohol
        alt_gt2 = alt_persistent_map[alt_persistent_sel] is True
        rule_out_visited = entry_met and not alcohol_stop
        med_review_visited = rule_out_visited and other_causes_map[other_causes_sel] is True
        baseline_visited = med_review_visited
        fib4_visited = fib4_computed is not None
        refer_specialist = high_risk
        low_risk_home = low_risk

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
        W, H = 700, 1020
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

        # ── Layout constants ──────────────────────────────────────────────
        CX = 350; NW, NH = 200, 50; DW, DH = 200, 60; EW, EH = 140, 44
        LEXT = 20; REXT = W - 20 - EW

        Y = {
            "suspected":  18,
            "d_alt":     100,
            "rule_out":  195,
            "d_excluded": 290,
            "med_review": 385,
            "baseline":  475,
            "nafld_dx":  565,
            "d_fib4":    655,
            "low_risk":  760,
            "high_risk":  760,
        }

        # ── 1. Suspected NAFLD ─────────────────────────────────────────────
        rect_node(CX-NW/2, Y["suspected"], NW, NH, nc(True), "1. Suspected NAFLD",
                  sub="Abnormal ALT or fatty liver on US")
        vline(CX, Y["suspected"]+NH, Y["d_alt"], entry_met, label="Entry met")

        # ── Alcohol exit (left) ────────────────────────────────────────────
        exit_node(LEXT, Y["d_alt"]+(DH-EH)/2, EW, EH,
                  nc(alcohol_stop, urgent=True), "⚠ Significant", "Alcohol — Stop")
        elbow_line(CX-DW/2, Y["d_alt"]+DH/2, LEXT+EW,
                   Y["d_alt"]+(DH-EH)/2+EH/2, alcohol_stop, urgent=True, label="Yes")

        # ── ALT >2× ULN check ─────────────────────────────────────────────
        diamond_node(CX, Y["d_alt"]+DH/2, DW, DH, dc(entry_met),
                     "Significant Alcohol?", "")

        # ── 2. Rule out other causes ───────────────────────────────────────
        vline(CX, Y["d_alt"]+DH, Y["rule_out"], rule_out_visited, label="No")
        rect_node(CX-NW/2, Y["rule_out"], NW, NH, nc(rule_out_visited),
                  "2. Rule Out Other Causes",
                  sub="Hep B/C, autoimmune, iron, celiac")

        # ── ALT >2× ULN side note (right)
        alt_flag_visited = rule_out_visited and alt_persistent_map[alt_persistent_sel] is True
        exit_node(REXT, Y["rule_out"]+(NH-EH)/2, EW, EH,
                  nc(alt_flag_visited, exit_=True), "ALT >2× ULN", ">6 months workup")
        elbow_line(CX+NW/2, Y["rule_out"]+NH/2, REXT,
                   Y["rule_out"]+(NH-EH)/2+EH/2, alt_flag_visited, exit_=True, label="Yes")

        # ── Other causes excluded decision ─────────────────────────────────
        vline(CX, Y["rule_out"]+NH, Y["d_excluded"], rule_out_visited)
        diamond_node(CX, Y["d_excluded"]+DH/2, DW, DH, dc(rule_out_visited),
                     "Other Causes", "Excluded?")

        non_nafld_exit = rule_out_visited and other_causes_map[other_causes_sel] is False
        exit_node(LEXT, Y["d_excluded"]+(DH-EH)/2, EW, EH,
                  nc(non_nafld_exit, urgent=True), "Treat / Refer", "Non-NAFLD Cause")
        elbow_line(CX-DW/2, Y["d_excluded"]+DH/2, LEXT+EW,
                   Y["d_excluded"]+(DH-EH)/2+EH/2, non_nafld_exit, urgent=True, label="No")

        # ── 3. Medication & lifestyle review ──────────────────────────────
        vline(CX, Y["d_excluded"]+DH, Y["med_review"], med_review_visited, label="Yes")
        rect_node(CX-NW/2, Y["med_review"], NW, NH, nc(med_review_visited),
                  "3. Medication &", "Lifestyle Review")

        # ── 4. Baseline investigations ────────────────────────────────────
        vline(CX, Y["med_review"]+NH, Y["baseline"], baseline_visited)
        rect_node(CX-NW/2, Y["baseline"], NW, NH, nc(baseline_visited),
                  "4. Baseline Investigations",
                  sub="ALT, AST, ALP, GGT, CBC, HbA1C, lipids")

        # ── 5. NAFLD Diagnosed ─────────────────────────────────────────────
        vline(CX, Y["baseline"]+NH, Y["nafld_dx"], baseline_visited)
        rect_node(CX-NW/2, Y["nafld_dx"], NW, NH, nc(nafld_diagnosed or baseline_visited),
                  "5. NAFLD Diagnosed",
                  sub="Diagnosis of exclusion")

        # ── 6. FIB-4 Assessment ───────────────────────────────────────────
        vline(CX, Y["nafld_dx"]+NH, Y["d_fib4"], baseline_visited)
        diamond_node(CX, Y["d_fib4"]+DH/2, DW, DH, dc(baseline_visited),
                     "6. FIB-4 Score?", "")

        fib4_label = f"FIB-4 = {fib4_computed:.2f}" if fib4_computed is not None else "FIB-4 = ?"

        # ── Low risk branch (right) ────────────────────────────────────────
        low_y = Y["d_fib4"]+(DH-EH)/2
        exit_node(REXT, low_y, EW, EH+10,
                  nc(low_risk_home, exit_=True), "6a. Low Risk", "Medical Home")
        elbow_line(CX+DW/2, Y["d_fib4"]+DH/2, REXT, low_y+EH/2+5,
                   low_risk_home, exit_=True, label="< 1.30")

        # ── High risk branch (left) ───────────────────────────────────────
        hi_y = Y["d_fib4"]+(DH-EH)/2
        exit_node(LEXT, hi_y, EW, EH+10,
                  nc(refer_specialist, urgent=True), "6b. High Risk", "Refer Specialist")
        elbow_line(CX-DW/2, Y["d_fib4"]+DH/2, LEXT+EW, hi_y+EH/2+5,
                   refer_specialist, urgent=True, label="≥ 1.30")

        # ── FIB-4 recheck loop arrow down ─────────────────────────────────
        check_y = Y["d_fib4"]+DH+20
        if low_risk_home:
            rect_node(CX-NW/2, check_y, NW, 42, nc(low_risk_home, exit_=True),
                      "Recheck FIB-4 q2–3 yrs",
                      rx=6)
            # small arrow from box back upward (schematic loop)
            svg.append(
                f'<line x1="{CX}" y1="{check_y+42}" x2="{CX}" y2="{check_y+60}" '
                f'stroke="#d97706" stroke-width="1.5" stroke-dasharray="4,3"/>'
            )
            svgt(CX+8, check_y+55, "If FIB-4 ≥1.30 → refer", "#d97706", 9, anchor="start")

        # ── FIB-4 label badge ─────────────────────────────────────────────
        if fib4_computed is not None:
            badge_col = "#16a34a" if low_risk else "#dc2626"
            fib4_y = Y["d_fib4"] - 22
            fib4_ty = Y["d_fib4"] - 8
            svg.append(
                f'<rect x="{CX-60}" y="{fib4_y}" width="120" height="20" '
                f'rx="10" fill="{badge_col}" opacity="0.9"/>'
            )
            svgt(CX, fib4_ty, fib4_label, "#ffffff", 10, True)

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
            height=1060, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ───────────────────────────────────────────
        fib4_display = f"{fib4_computed:.2f}" if fib4_computed else "Not calculated"
        risk_str = ("🟢 Low risk (< 1.30)" if low_risk else
                    "🔴 High risk (≥ 1.30)" if high_risk else "—")
        drink_limit = ">2/day (male)" if sex == "male" else ">1/day (female)"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Avg Alcohol:</b> {avg_drinks} drinks/day &nbsp;|&nbsp; Threshold: {drink_limit}</span><br>'
            f'<span><b>FIB-4 Score:</b> {fib4_display} &nbsp;|&nbsp; <b>Risk:</b> {risk_str}</span><br>'
            f'<span><b>Incidental ALT:</b> {"Yes" if incidental_alt else "No"} &nbsp;|&nbsp; '
            f'<b>Fatty Liver on US:</b> {"Yes" if incidental_us else "No"}</span><br>'
            f'<span><b>Other Causes Excluded:</b> {other_causes_sel}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        # ── Step grouping map ──────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — Suspected NAFLD",
                "icon": "🔍",
                "cls": "routine",
                "codes": {
                    "SUSPECTED_NAFLD_ENTRY_MET",
                    "METABOLIC_RISK_FACTORS_SUPPORT_NAFLD",
                    "NOT_SUSPECTED_NAFLD",
                },
            },
            "step2a": {
                "label": "Step 2 — ALT Persistence Check",
                "icon": "📊",
                "cls": "routine",
                "codes": {
                    "DEEPER_RULE_OUT_REQUIRED",
                    "NO_DEEPER_RULE_OUT_TRIGGER",
                },
            },
            "step2b": {
                "label": "Step 2 — Rule Out Other Causes",
                "icon": "🧪",
                "cls": "routine",
                "codes": {
                    "CHECK_HBSAG", "CHECK_ANTI_HCV", "CHECK_AUTOIMMUNE_MARKERS",
                    "CHECK_IRON_STUDIES", "CHECK_CELIAC_SCREEN", "CHECK_CERULOPLASMIN",
                    "OTHER_CAUSES_EXCLUDED", "TREAT_OR_REFER_NON_NAFLD_CAUSE",
                },
            },
            "step3": {
                "label": "Step 3 — Medication & Lifestyle Review",
                "icon": "💊",
                "cls": "routine",
                "codes": {
                    "COMPLETE_MEDICATION_REVIEW", "REPEAT_LIVER_TESTS_3_TO_6_MONTHS",
                    "REVIEW_AND_ADDRESS_ALCOHOL_USE", "HEPATOTOXIC_MEDICATION_FLAG",
                    "PHYSICAL_INACTIVITY_FLAG", "HIGH_RISK_DIET_FLAG",
                },
            },
            "step4": {
                "label": "Step 4 — Baseline Investigations",
                "icon": "🩸",
                "cls": "routine",
                "codes": {
                    "COMPLETE_BASELINE_INVESTIGATIONS", "BASELINE_INVESTIGATIONS_COMPLETE",
                    "CHECK_INR_BILIRUBIN_ALBUMIN", "ALP_RECORDED", "GGT_RECORDED",
                    "HBA1C_RECORDED", "LIPID_PROFILE_RECORDED",
                },
            },
            "step5": {
                "label": "Step 5 — NAFLD Diagnosis",
                "icon": "✅",
                "cls": "routine",
                "codes": {"NAFLD_DIAGNOSED", "NAFLD_NOT_DIAGNOSED"},
            },
            "step6": {
                "label": "Step 6 — FIB-4 Risk Assessment",
                "icon": "📐",
                "cls": "routine",
                "codes": {
                    "FIB4_CALCULATED", "INVALID_FIB4_INPUTS",
                    "CAPTURE_FIB4_INPUTS",
                },
            },
            "step6b": {
                "label": "Step 6b — Specialist Referral Required",
                "icon": "🏥",
                "cls": "urgent",
                "codes": {"REFER_LIVER_DISEASE_SPECIALIST"},
            },
            "step6a": {
                "label": "Step 6a — Care in the Patient Medical Home",
                "icon": "🏠",
                "cls": "info",
                "codes": {
                    "PHYSICAL_ACTIVITY_COUNSELLING", "DIET_WEIGHT_LOSS_COUNSELLING",
                    "SCREEN_AND_OPTIMIZE_CARDIOMETABOLIC_RISK", "ENCOURAGE_SMOKING_CESSATION",
                    "LIMIT_ALCOHOL_INTAKE", "CONSIDER_HEP_A_B_IMMUNIZATION",
                    "RECALCULATE_FIB4_2_TO_3_YEARS", "EXERCISE_COUNSELLING_DOCUMENTED",
                    "DIET_COUNSELLING_DOCUMENTED", "WEIGHT_LOSS_GOAL_DOCUMENTED",
                    "SMOKING_STATUS_RECORDED", "ALCOHOL_COUNSELLING_DOCUMENTED",
                    "HEP_A_STATUS_RECORDED", "HEP_B_STATUS_RECORDED",
                    "FIB4_RECHECK_INTERVAL_DOCUMENTED", "FOLLOWUP_PLAN_DOCUMENTED",
                },
            },
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
                gkey = code_to_group.get(output.code)
                if gkey:
                    grouped[gkey].append(output)
                # actions inside Stop handled separately

        # Also collect Stop.actions for override candidates
        for output in outputs:
            if isinstance(output, Stop):
                for a in output.actions:
                    if a.override_options:
                        override_candidates.append(a)

        # ── FIB-4 pill helper ─────────────────────────────────────────────
        def _fib4_pill() -> str:
            if fib4_computed is None:
                return ""
            col = "#16a34a" if low_risk else "#dc2626"
            label = f"FIB-4 = {fib4_computed:.2f} — {'Low Risk &lt; 1.30' if low_risk else 'High Risk ≥ 1.30'}"
            return (
                f'<span style="background:{col};color:#fff;font-size:11px;font-weight:700;'
                f'padding:3px 10px;border-radius:20px;margin-left:8px">{label}</span>'
            )

        # ── Render a group card ────────────────────────────────────────────
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
                f'{icon} {html.escape(label)}{pill}</p>'
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
                # Determine if this is a positive stop (complete) or a blocker
                is_complete = "low-risk" in output.reason.lower() or "medical home" in output.reason.lower()
                is_refer = "specialist" in output.reason.lower() or "fibrosis" in output.reason.lower()
                is_alcohol = "alcohol" in output.reason.lower()
                is_not_nafld = "not established" in output.reason.lower() or "alternative" in output.reason.lower()

                if is_complete:
                    bg, border, icon = "#052e16", "#22c55e", "✅"
                    title = "Pathway Complete — Continue Care in Patient Medical Home"
                    tcol = "#bbf7d0"
                elif is_refer:
                    bg, border, icon = "#3b0a0a", "#ef4444", "🏥"
                    title = "Referral Required — FIB-4 Indeterminate/High Risk"
                    tcol = "#fecaca"
                elif is_alcohol:
                    bg, border, icon = "#3b0a0a", "#ef4444", "⚠️"
                    title = "Pathway Not Applicable — Significant Alcohol Use"
                    tcol = "#fecaca"
                elif is_not_nafld:
                    bg, border, icon = "#2d1a00", "#f59e0b", "🔄"
                    title = "NAFLD Not Established — Alternative Cause or Incomplete Workup"
                    tcol = "#fde68a"
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

        # ── Render everything ──────────────────────────────────────────────
        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        # Priority stops / data requests first (blocking)
        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        for o in blocking:
            render_stop_request(o)

        # Grouped action steps in order
        for gkey in STEP_GROUPS:
            render_group(gkey, grouped[gkey])

        # Non-blocking stops (end-of-pathway outcomes) last
        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]
        for o in terminal:
            render_stop_request(o)

        # ── Clinician Notes ────────────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.nafld_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.nafld_notes,
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
                    for o in st.session_state.nafld_overrides
                ],
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
                            (o for o in st.session_state.nafld_overrides
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
                                    st.session_state.nafld_overrides = [
                                        o for o in st.session_state.nafld_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.nafld_overrides.append(
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
                                st.session_state.nafld_overrides = [
                                    o for o in st.session_state.nafld_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.nafld_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.nafld_overrides:
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
