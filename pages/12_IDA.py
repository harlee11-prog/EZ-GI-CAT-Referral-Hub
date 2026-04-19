import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from ida_engine import (
    run_ida_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="IDA Pathway", page_icon="🩸", layout="wide")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_ida_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Iron Deficiency Anemia (IDA) Pathway — Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## Patient Context")
    lines.append(
        f"- **Age / Sex:** {patient_data.get('age')} / "
        f"{str(patient_data.get('sex', '')).capitalize()}"
    )
    lines.append(f"- **Hemoglobin:** {patient_data.get('hemoglobin', 'N/A')} g/L")
    lines.append(f"- **Ferritin:** {patient_data.get('ferritin', 'N/A')} ug/L")
    lines.append(f"- **Inflammation present:** {patient_data.get('inflammation_present', 'N/A')}")
    lines.append(f"- **TTG Positive:** {patient_data.get('ttg_positive', 'N/A')}")
    lines.append(f"- **Alarm symptoms:** diarrhea={patient_data.get('significant_diarrhea')}, "
                 f"weight_loss={patient_data.get('weight_loss')}, "
                 f"bowel_change={patient_data.get('progressive_bowel_change')}, "
                 f"abd_pain={patient_data.get('significant_abdominal_pain')}")
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
.action-card.urgent   {background:#3b0a0a;border-left:5px solid #ef4444;color:#fecaca;}
.action-card.semi_urgent{background:#3f2a04;border-left:5px solid #f97316;color:#fed7aa;}
.action-card.routine  {background:#052e16;border-left:5px solid #22c55e;color:#bbf7d0;}
.action-card.info     {background:#0c1a2e;border-left:5px solid #3b82f6;color:#bfdbfe;}
.action-card.warning  {background:#2d1a00;border-left:5px solid #f59e0b;color:#fde68a;}
.action-card.stop     {background:#2d0a0a;border-left:5px solid #ef4444;color:#fecaca;}
.badge{
  display:inline-block;font-size:11px;font-weight:bold;
  padding:2px 8px;border-radius:20px;margin-right:6px;
  text-transform:uppercase;letter-spacing:0.5px;
}
.badge.urgent     {background:#ef4444;color:#fff;}
.badge.semi_urgent{background:#f97316;color:#fff;}
.badge.routine    {background:#22c55e;color:#fff;}
.badge.info       {background:#3b82f6;color:#fff;}
.badge.warning    {background:#f59e0b;color:#000;}
.badge.stop       {background:#ef4444;color:#fff;}
.override-card{
  background:#1a1a2e;border:1px dashed #6366f1;
  border-radius:8px;padding:10px 14px;margin-top:8px;
  font-size:13px;color:#c7d2fe;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Iron Deficiency Anemia (IDA) Pathway")
st.markdown("---")


# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "ida_overrides" not in st.session_state:
    st.session_state.ida_overrides = []
if "ida_has_run" not in st.session_state:
    st.session_state.ida_has_run = False
if "ida_notes" not in st.session_state:
    st.session_state.ida_notes = ""


left, right = st.columns([1, 1.5])


# ═════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — INPUTS
# ═════════════════════════════════════════════════════════════════════════════
with left:
    st.subheader("Patient Information")

    col_a, col_b = st.columns(2)
    with col_a:
        age = st.number_input("Age", 18, 120, value=60)
    with col_b:
        sex = st.selectbox("Sex", ["male", "female"])

    # ── 1. Signs of IDA ───────────────────────────────────────────────────
    st.markdown("**1. Signs of IDA — Required Labs**")
    col_hb, col_fer = st.columns(2)
    with col_hb:
        hb = st.number_input("Hemoglobin (g/L)", min_value=40.0, max_value=200.0,
                             value=118.0, step=1.0,
                             help="Anemia: Hb <130 (men) / <120 (women)")
    with col_fer:
        ferritin = st.number_input("Serum Ferritin (ug/L)", min_value=0.0, max_value=800.0,
                                   value=10.0, step=1.0,
                                   help="Normal ≥30 (men) / ≥20 (women). <100 if inflammation present.")

    col_tsat, col_base = st.columns(2)
    with col_tsat:
        tsat = st.number_input("Transferrin Saturation (%)", min_value=0.0, max_value=100.0,
                               value=0.0, step=0.5,
                               help="<16% supports IDA. Enter 0 if not tested.")
    with col_base:
        baseline_hb = st.number_input("Baseline Hb (g/L, if known)", min_value=0.0,
                                      max_value=200.0, value=0.0, step=1.0,
                                      help="Optional. Used to detect significant Hb drop from baseline.")

    inflammation = st.checkbox(
        "Active inflammation / infection / active IBD present",
        help="Raises ferritin cutoff: <100 ug/L supports iron deficiency when inflammation present"
    )
    ckd = st.checkbox(
        "Significant chronic kidney disease (CKD)",
        help="CKD caveat: ferritin >100 in CKD context may still support iron deficiency"
    )

    # ── 2a. Celiac Rule-out ───────────────────────────────────────────────
    st.markdown("**2a. Rule Out Celiac Disease (TTG)**")
    prior_biopsy = st.checkbox(
        "Prior normal duodenal biopsy documented",
        help="If prior normal duodenal endoscopic biopsy exists, TTG not required"
    )
    ttg_years = st.number_input(
        "Years since last TTG test", min_value=0.0, max_value=50.0, value=1.0, step=0.5,
        help="TTG done within 5 years is considered recent; ≥5 years requires repeat"
    )
    ttg_pos_sel = st.selectbox(
        "TTG result (most recent)",
        ["Negative", "Positive", "Not yet tested / Unknown"]
    )
    ttg_pos_map = {"Negative": False, "Positive": True, "Not yet tested / Unknown": None}

    if ttg_pos_map[ttg_pos_sel] is True:
        with st.expander("TTG Positive — Additional Context Required"):
            celiac_months = st.number_input(
                "Duration of known celiac (months)", min_value=0.0, max_value=240.0,
                value=0.0, step=1.0
            )
            gluten_free = st.selectbox(
                "Gluten-free diet compliant?",
                ["Unknown", "Yes", "No"]
            )
            gluten_map = {"Unknown": None, "Yes": True, "No": False}
            anemia_disproportionate = st.selectbox(
                "Anemia out of keeping with degree of heavy menstruation?",
                ["Unknown", "Yes", "No"]
            )
            anemia_disp_map = {"Unknown": None, "Yes": True, "No": False}
    else:
        celiac_months = None
        gluten_free = "Unknown"
        gluten_map = {"Unknown": None, "Yes": True, "No": False}
        anemia_disproportionate = "Unknown"
        anemia_disp_map = {"Unknown": None, "Yes": True, "No": False}

    # ── 2b. Gynecology Causes (females only) ─────────────────────────────
    if sex == "female":
        st.markdown("**2b. Address Gynecology Causes**")
        menstruating = st.selectbox(
            "Menstrual status",
            ["Unknown", "Currently menstruating", "Not menstruating", "Hysterectomy"]
        )
        menstruating_map = {
            "Unknown": None,
            "Currently menstruating": True,
            "Not menstruating": False,
            "Hysterectomy": False
        }
        hysterectomy_map = {
            "Unknown": None,
            "Currently menstruating": False,
            "Not menstruating": None,
            "Hysterectomy": True
        }
        anemia_out_menses_sel = st.selectbox(
            "Anemia out of keeping with degree/duration of menstruation?",
            ["Not assessed / N/A", "Yes", "No"]
        )
        anemia_out_menses_map = {"Not assessed / N/A": None, "Yes": True, "No": False}
    else:
        menstruating = "Unknown"
        menstruating_map = {"Unknown": None}
        hysterectomy_map = {"Unknown": None}
        anemia_out_menses_sel = "Not assessed / N/A"
        anemia_out_menses_map = {"Not assessed / N/A": None, "Yes": True, "No": False}

    # ── 3. High-Risk Rectal Bleeding ──────────────────────────────────────
    st.markdown("**3. High-Risk Rectal Bleeding Assessment**")
    st.caption("All three must be present to qualify as high-risk rectal bleeding")
    hrrb_visible = st.selectbox(
        "Blood visibly in/on stool OR toilet (not just on tissue)?",
        ["Unknown", "Yes", "No"]
    )
    hrrb_vis_map = {"Unknown": None, "Yes": True, "No": False}

    hrrb_new = st.selectbox(
        "Rectal bleeding new onset or worsening AND persistent?",
        ["Unknown", "Yes", "No"]
    )
    hrrb_new_map = {"Unknown": None, "Yes": True, "No": False}

    hrrb_days = st.selectbox(
        "Bleeding present most days for >2 weeks?",
        ["Unknown", "Yes", "No"]
    )
    hrrb_days_map = {"Unknown": None, "Yes": True, "No": False}

    colonoscopy_2y = st.selectbox(
        "Complete colonoscopy within last 2 years?",
        ["Unknown / Not done", "Yes", "No"]
    )
    col2y_map = {"Unknown / Not done": None, "Yes": True, "No": False}

    alarm_investigated_sel = st.selectbox(
        "Current alarm features already investigated by lower endoscopy within 2 years?",
        ["Unknown / Not assessed", "Yes — already investigated", "No — not yet investigated"]
    )
    alarm_inv_map = {
        "Unknown / Not assessed": None,
        "Yes — already investigated": True,
        "No — not yet investigated": False,
    }

    # ── Alarm Symptoms ────────────────────────────────────────────────────
    st.markdown("**7. Alarm Symptoms (Urgency Determinants)**")
    st.caption("Alarm features should be unexplained (not investigated by lower endoscopy within last 2 years)")
    sig_diarrhea = st.checkbox("Significant diarrhea (as can occur in IBD)")
    weight_loss_flag = st.checkbox(
        "Unintentional weight loss ≥5–10% body weight over 6 months"
    )
    bowel_change = st.checkbox("Significant and progressive change in bowel habit")
    abd_pain = st.checkbox("Significant abdominal pain")

    # ── 4. Medication Review ──────────────────────────────────────────────
    st.markdown("**4. Medication Review**")
    anticoag = st.selectbox("Anticoagulant use?", ["Unknown", "Yes", "No"])
    anticoag_map = {"Unknown": None, "Yes": True, "No": False}
    antiplatelet = st.selectbox("Antiplatelet agent use?", ["Unknown", "Yes", "No"])
    antiplatelet_map = {"Unknown": None, "Yes": True, "No": False}
    nsaid = st.selectbox("NSAID use?", ["Unknown", "Yes", "No"])
    nsaid_map = {"Unknown": None, "Yes": True, "No": False}

    # ── 5. Baseline Investigations ────────────────────────────────────────
    st.markdown("**5. Baseline Investigations (within 8 weeks of referral)**")
    st.caption("Required: CBC, Serum Ferritin, TTG | Additional: Serum Iron, TIBC, Transferrin sat, Creatinine, ALP, Bilirubin, ALT")
    cbc_8wk = st.checkbox("CBC done within 8 weeks", value=True)
    ferritin_8wk = st.checkbox("Ferritin done within 8 weeks", value=True)
    ttg_8wk = st.checkbox("TTG done within 8 weeks", value=True)

    fit_ordered = st.selectbox(
        "FIT (fecal immunochemical test) ordered or planned?",
        ["No", "Yes", "Unknown"],
        help="Note: FIT should NOT be done when IDA signs are present"
    )
    fit_map = {"No": False, "Yes": True, "Unknown": None}

    # ── 6. Physical Exam ──────────────────────────────────────────────────
    st.markdown("**6. Physical Exam**")
    rectal_exam = st.selectbox(
        "Rectal exam documented?",
        ["Not documented", "Done — documented", "Deferred"],
        help="Consider rectal exam especially with bowel habit change or lower abdominal pain"
    )
    rectal_exam_map = {
        "Not documented": None,
        "Done — documented": True,
        "Deferred": False,
    }

    # ── Triage Modifiers ─────────────────────────────────────────────────
    st.markdown("**Triage Modifiers (Optional — Influence Referral Priority)**")
    nocturnal = st.checkbox("Nocturnal symptoms")
    fh_crc = st.checkbox("First-degree family history of colorectal cancer (CRC)")
    fh_ibd = st.checkbox("First-degree family history of IBD")
    gi_bleed_evidence = st.checkbox("Evidence of GI bleeding")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.ida_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.ida_overrides = []
        if "ida_saved_output" in st.session_state:
            del st.session_state["ida_saved_output"]

    override_panel = st.container()


# ═════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL
# ═════════════════════════════════════════════════════════════════════════════
with right:
    if not st.session_state.ida_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        # Build patient_data dict matching engine variables
        patient_data = {
            "age": age,
            "sex": sex,
            "hemoglobin": hb,
            "ferritin": ferritin,
            "transferrin_saturation": tsat if tsat > 0 else None,
            "baseline_hemoglobin": baseline_hb if baseline_hb > 0 else None,
            "inflammation_present": inflammation or None,
            "chronic_kidney_disease": ckd or None,
            # Celiac
            "prior_duodenal_biopsy_normal": prior_biopsy or None,
            "ttg_years_since_test": ttg_years,
            "ttg_positive": ttg_pos_map[ttg_pos_sel],
            "celiac_duration_months": celiac_months,
            "gluten_free_compliant": gluten_map.get(gluten_free),
            "anemia_out_of_keeping_with_menses": (
                anemia_disp_map.get(anemia_disproportionate)
                if ttg_pos_map[ttg_pos_sel] is True else anemia_out_menses_map.get(anemia_out_menses_sel)
            ),
            # Gynecology
            "menstruating": menstruating_map.get(menstruating),
            "hysterectomy": hysterectomy_map.get(menstruating),
            # Rectal bleeding
            "rectal_bleeding_visible": hrrb_vis_map[hrrb_visible],
            "rectal_bleeding_new_or_worsening": hrrb_new_map[hrrb_new],
            "rectal_bleeding_most_days": hrrb_days_map[hrrb_days],
            "complete_colonoscopy_within_2y": col2y_map[colonoscopy_2y],
            "alarm_features_investigated_by_lower_endoscopy_within_2y": alarm_inv_map[alarm_investigated_sel],
            # Alarm symptoms
            "significant_diarrhea": sig_diarrhea or None,
            "weight_loss": weight_loss_flag or None,
            "progressive_bowel_change": bowel_change or None,
            "significant_abdominal_pain": abd_pain or None,
            # Medications
            "anticoagulants": anticoag_map[anticoag],
            "antiplatelets": antiplatelet_map[antiplatelet],
            "nsaid_use": nsaid_map[nsaid],
            # Baseline investigations
            "cbc_within_8_weeks": cbc_8wk or None,
            "ferritin_within_8_weeks": ferritin_8wk or None,
            "ttg_within_8_weeks": ttg_8wk or None,
            # FIT
            "fit_ordered_or_planned": fit_map[fit_ordered],
            # Physical exam
            "rectal_exam_done": rectal_exam_map[rectal_exam],
            # Triage modifiers
            "nocturnal_symptoms": nocturnal or None,
            "family_history_crc_first_degree": fh_crc or None,
            "family_history_ibd_first_degree": fh_ibd or None,
            "evidence_of_gi_bleeding": gi_bleed_evidence or None,
        }

        outputs, logs, applied_overrides = run_ida_pathway(
            patient_data, overrides=st.session_state.ida_overrides
        )

        # ── Derive SVG flags from outputs ──────────────────────────────────
        ida_confirmed = False
        urgency_val = None          # "urgent" | "semi_urgent" | "routine"
        celiac_done = False
        hrrb_exit = False           # High-risk rectal bleeding → exit to HRRB pathway
        baseline_visited = False
        final_refer = False
        alarm_any = bool(sig_diarrhea or weight_loss_flag or bowel_change or abd_pain)

        for o in outputs:
            if isinstance(o, Action):
                if o.code == "IDA_CONFIRMED":
                    ida_confirmed = True
                if o.code == "ASSIGN_URGENCY":
                    urgency_val = o.urgency
                if o.code in {"CELIAC_RULED_OUT", "CELIAC_EXEMPT",
                              "CELIAC_POSITIVE_PROCEED", "CELIAC_POSITIVE_MANAGE"}:
                    celiac_done = True
                if o.code in {"HRRB_PATHWAY", "HRRB_PATHWAY_REQUIRED"}:
                    hrrb_exit = True
                if o.code in {"BASELINE_CBC_WITHIN_8_WEEKS", "ORDER_CBC_URGENTLY",
                              "BASELINE_FERRITIN_WITHIN_8_WEEKS", "BASELINE_TTG_WITHIN_8_WEEKS"}:
                    baseline_visited = True
                if o.code == "REFER_ENDOSCOPY":
                    final_refer = True
            if isinstance(o, Stop):
                for a in o.actions:
                    if a.code == "REFER_ENDOSCOPY":
                        final_refer = True
                        urgency_val = urgency_val or o.urgency

        urgent_final = urgency_val == "urgent"
        semi_urgent_final = urgency_val == "semi_urgent"

        # Pathway step visited flags
        entry_met = True  # Hb + ferritin always provided
        rule_out_visited = ida_confirmed
        med_review_visited = rule_out_visited and not hrrb_exit
        baseline_visited_flag = med_review_visited
        alarm_visited = baseline_visited_flag
        urgent_refer = alarm_visited and urgent_final
        semi_urgent_refer = alarm_visited and semi_urgent_final

        # ── SVG PATHWAY VISUAL ─────────────────────────────────────────────
        C_MAIN    = "#16a34a"   # green — visited
        C_UNVISIT = "#475569"   # slate — not reached
        C_DIAMOND = "#1d4ed8"   # blue — decision node
        C_URGENT  = "#dc2626"   # red — urgent
        C_SEMI    = "#ea580c"   # orange — semi-urgent
        C_EXIT    = "#d97706"   # amber — exit/branch
        C_TEXT    = "#ffffff"
        C_DIM     = "#94a3b8"
        C_BG      = "#0f172a"

        def nc(vis, urgent=False, semi=False, exit_=False):
            if not vis:       return C_UNVISIT
            if urgent:        return C_URGENT
            if semi:          return C_SEMI
            if exit_:         return C_EXIT
            return C_MAIN

        def dc(vis):
            return C_DIAMOND if vis else C_UNVISIT

        def mid(vis, urgent=False, semi=False, exit_=False):
            if not vis:  return "ma"
            if urgent:   return "mr"
            if semi:     return "ms"
            if exit_:    return "mo"
            return "mg"

        svg = []
        W, H = 700, 1080
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
            '<marker id="ms" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#ea580c"/></marker>'
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
                svgt(x+w/2, y+h/2-7, line1, tc, 11, True)
                svgt(x+w/2, y+h/2+8, line2, tc, 11, True)
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
                svgt(cx, cy-6, line1, tc, 10, True)
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

        def vline(x, y1, y2, vis, urgent=False, semi=False, exit_=False, label=""):
            m = mid(vis, urgent, semi, exit_)
            stroke = {"mg": C_MAIN, "mr": C_URGENT, "ms": C_SEMI, "mo": C_EXIT}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x+6, (y1+y2)/2-3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, semi=False, exit_=False, label=""):
            m = mid(vis, urgent, semi, exit_)
            stroke = {"mg": C_MAIN, "mr": C_URGENT, "ms": C_SEMI, "mo": C_EXIT}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1+x2)/2, y1-5, label, stroke, 10, True)

        # ── Layout constants ──────────────────────────────────────────────
        CX = 350; NW, NH = 210, 48; DW, DH = 210, 62; EW, EH = 145, 44
        LEXT = 14; REXT = W - 14 - EW

        Y = {
            "signs_ida":   16,
            "celiac":      108,
            "d_hrrb":      195,
            "med_review":  295,
            "baseline":    385,
            "physical":    470,
            "d_alarm":     560,
            "urgent":      660,
            "semi_urgent": 660,
        }

        # ── 1. Signs of IDA (Entry) ───────────────────────────────────────
        rect_node(CX-NW/2, Y["signs_ida"], NW, NH, nc(True), "1. Signs of IDA",
                  sub=f"Hb {hb} g/L | Ferritin {ferritin} ug/L")
        # Not IDA exit (left)
        not_ida = not ida_confirmed
        exit_node(LEXT, Y["signs_ida"]+(NH-EH)/2, EW, EH,
                  nc(not_ida, urgent=True), "⚠ IDA Not", "Confirmed — Stop")
        elbow_line(CX-NW/2, Y["signs_ida"]+NH/2, LEXT+EW,
                   Y["signs_ida"]+(NH-EH)/2+EH/2, not_ida, urgent=True, label="")

        # ── 2a/2b. Celiac + Gyne ──────────────────────────────────────────
        vline(CX, Y["signs_ida"]+NH, Y["celiac"], ida_confirmed)
        rect_node(CX-NW/2, Y["celiac"], NW, NH, nc(rule_out_visited),
                  "2a. Rule Out Celiac (TTG)", "2b. Address Gyne Causes")

        # ── 3. High-Risk Rectal Bleeding? ─────────────────────────────────
        vline(CX, Y["celiac"]+NH, Y["d_hrrb"], rule_out_visited)
        diamond_node(CX, Y["d_hrrb"]+DH/2, DW, DH, dc(rule_out_visited),
                     "High-Risk Rectal", "Bleeding?")

        # HRRB exit (right)
        exit_node(REXT, Y["d_hrrb"]+(DH-EH)/2, EW, EH,
                  nc(hrrb_exit, exit_=True), "→ Follow HRRB", "Pathway")
        elbow_line(CX+DW/2, Y["d_hrrb"]+DH/2, REXT,
                   Y["d_hrrb"]+(DH-EH)/2+EH/2, hrrb_exit, exit_=True, label="Yes")

        # ── 4. Medication Review ──────────────────────────────────────────
        vline(CX, Y["d_hrrb"]+DH, Y["med_review"], med_review_visited, label="No")
        rect_node(CX-NW/2, Y["med_review"], NW, NH, nc(med_review_visited),
                  "4. Medication Review",
                  sub="Anti-platelets, anti-coagulants, NSAIDs")

        # ── 5. Baseline Investigations ────────────────────────────────────
        vline(CX, Y["med_review"]+NH, Y["baseline"], baseline_visited_flag)
        rect_node(CX-NW/2, Y["baseline"], NW, NH, nc(baseline_visited_flag),
                  "5. Baseline Investigations",
                  sub="CBC, Ferritin, TTG (within 8 wks)")

        # FIT warning side note (right of baseline)
        fit_warn = bool(fit_map.get(fit_ordered)) and baseline_visited_flag
        exit_node(REXT, Y["baseline"]+(NH-EH)/2, EW, EH,
                  nc(fit_warn, urgent=True), "⚠ FIT Should", "NOT Be Done")
        elbow_line(CX+NW/2, Y["baseline"]+NH/2, REXT,
                   Y["baseline"]+(NH-EH)/2+EH/2, fit_warn, urgent=True, label="FIT?")

        # ── 6. Physical Exam ──────────────────────────────────────────────
        vline(CX, Y["baseline"]+NH, Y["physical"], baseline_visited_flag)
        rect_node(CX-NW/2, Y["physical"], NW, NH, nc(baseline_visited_flag),
                  "6. Physical Exam",
                  sub="Consider rectal exam if indicated")

        # ── 7. Alarm Symptoms? ────────────────────────────────────────────
        vline(CX, Y["physical"]+NH, Y["d_alarm"], alarm_visited)
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(alarm_visited),
                     "7. Alarm Symptoms", "Unexplained?")

        # ── 8. Urgent → <2 weeks (left) ──────────────────────────────────
        hi_y = Y["d_alarm"]+(DH-EH)/2
        exit_node(LEXT, hi_y, EW, EH+10,
                  nc(urgent_refer, urgent=True), "8. Urgent Refer", "< 2 Weeks")
        elbow_line(CX-DW/2, Y["d_alarm"]+DH/2, LEXT+EW,
                   hi_y+EH/2+5, urgent_refer, urgent=True, label="Yes")

        # ── 9. Semi-urgent → <8 weeks (right) ────────────────────────────
        si_y = Y["d_alarm"]+(DH-EH)/2
        exit_node(REXT, si_y, EW, EH+10,
                  nc(semi_urgent_refer, semi=True), "9. Semi-Urgent", "< 8 Weeks")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT,
                   si_y+EH/2+5, semi_urgent_refer, semi=True, label="No")

        # ── Urgency badge ─────────────────────────────────────────────────
        if urgency_val:
            badge_col = C_URGENT if urgent_final else (C_SEMI if semi_urgent_final else C_MAIN)
            badge_text = ("URGENT — <2 wks" if urgent_final else
                          "SEMI-URGENT — <8 wks" if semi_urgent_final else "ROUTINE")
            badge_y = Y["d_alarm"] - 22
            svg.append(
                f'<rect x="{CX-70}" y="{badge_y}" width="140" height="20" '
                f'rx="10" fill="{badge_col}" opacity="0.9"/>'
            )
            svgt(CX, badge_y+14, badge_text, "#ffffff", 10, True)

        # ── Legend ─────────────────────────────────────────────────────────
        ly = H - 22; lx = 14
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_SEMI, "Semi-Urgent"),
            (C_EXIT, "Exit/Branch"), (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 108
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">'
            + "".join(svg) + "</div>",
            height=1120, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── Patient context card ───────────────────────────────────────────
        urgency_display = {
            "urgent": "🔴 Urgent — Refer <2 weeks",
            "semi_urgent": "🟠 Semi-Urgent — Refer <8 weeks",
            "routine": "🟢 Routine",
        }.get(urgency_val or "", "—")

        anemia_threshold = "130 g/L (male)" if sex == "male" else "120 g/L (female)"
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Hemoglobin:</b> {hb} g/L &nbsp;|&nbsp; Anemia threshold: {anemia_threshold}</span><br>'
            f'<span><b>Ferritin:</b> {ferritin} ug/L &nbsp;|&nbsp; '
            f'Inflammation: {"Yes" if inflammation else "No"}</span><br>'
            f'<span><b>Urgency:</b> {urgency_display}</span><br>'
            f'<span><b>TTG:</b> {ttg_pos_sel} &nbsp;|&nbsp; '
            f'Alarm Symptoms: {"Yes" if alarm_any else "No"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        # ── Step grouping map ──────────────────────────────────────────────
        STEP_GROUPS = {
            "step1": {
                "label": "Step 1 — Signs of IDA Confirmed",
                "icon": "🩸",
                "cls": "routine",
                "codes": {
                    "IDA_CONFIRMED",
                    "ALT_ANEMIA_WORKUP",
                    "ORDER_HB", "ORDER_FERRITIN", "CAPTURE_SEX",
                },
            },
            "step2_urgency": {
                "label": "Step 2 — Urgency Triage",
                "icon": "⚡",
                "cls": "routine",
                "codes": {"ASSIGN_URGENCY", "CAPTURE_ALARM_INVESTIGATION"},
            },
            "step2a": {
                "label": "Step 2a — Celiac Rule-Out",
                "icon": "🧪",
                "cls": "routine",
                "codes": {
                    "CELIAC_EXEMPT", "CELIAC_RULED_OUT",
                    "CELIAC_POSITIVE_PROCEED", "CELIAC_POSITIVE_MANAGE",
                    "ORDER_TTG", "CAPTURE_TTG_RECENCY", "CAPTURE_TTG_RESULT",
                    "CAPTURE_TTG_RESULT_REPEAT", "CAPTURE_CELIAC_CONTEXT",
                },
            },
            "step2b": {
                "label": "Step 2b — Gynecology Causes",
                "icon": "👩‍⚕️",
                "cls": "routine",
                "codes": {
                    "GYNE_NOT_APPLICABLE", "GYNE_NOTE_MENSTRUATING",
                    "GYNE_NOTE_NOT_MENSTRUATING", "GYNE_NOTE_HYSTERECTOMY",
                    "GYNE_NOTE_ANEMIA_OUT_OF_KEEPING",
                    "GYNE_CAPTURE_MENSTRUATION", "CAPTURE_HYSTERECTOMY",
                    "CAPTURE_ANEMIA_PROPORTIONALITY",
                },
            },
            "step3": {
                "label": "Step 3 — High-Risk Rectal Bleeding",
                "icon": "🩺",
                "cls": "routine",
                "codes": {
                    "HRRB_NOT_APPLICABLE", "HRRB_PATHWAY",
                    "HRRB_PATHWAY_REQUIRED", "HRRB_NOT_REQUIRED",
                    "CAPTURE_RECTAL_BLEEDING_VISIBLE",
                    "CAPTURE_RECTAL_BLEEDING_ONSET",
                    "CAPTURE_RECTAL_BLEEDING_PERSISTENCE",
                    "CAPTURE_RECTAL_BLEEDING_DURATION",
                },
            },
            "step4_fit": {
                "label": "Step 4 & FIT — Medication Review & Investigations",
                "icon": "💊",
                "cls": "routine",
                "codes": {"FIT_WARNING", "FIT_OK"},
            },
            "step5": {
                "label": "Step 5 — Baseline Investigation Freshness",
                "icon": "🔬",
                "cls": "routine",
                "codes": {
                    "BASELINE_CBC_WITHIN_8_WEEKS", "BASELINE_FERRITIN_WITHIN_8_WEEKS",
                    "BASELINE_TTG_WITHIN_8_WEEKS",
                    "ORDER_CBC_URGENTLY", "ORDER_FERRITIN_URGENTLY", "ORDER_TTG_URGENTLY",
                    "CBC_NOT_WITHIN_8_WEEKS", "FERRITIN_NOT_WITHIN_8_WEEKS", "TTG_NOT_WITHIN_8_WEEKS",
                },
            },
            "step7_modifiers": {
                "label": "Step 7 — Alarm Symptoms & Triage Modifiers",
                "icon": "⚠️",
                "cls": "routine",
                "codes": {
                    "MOD_FH_CRC", "MOD_FH_IBD", "MOD_NOCTURNAL", "MOD_GI_BLEED",
                    "CAPTURE_FH_CRC", "CAPTURE_FH_IBD", "CAPTURE_NOCTURNAL", "CAPTURE_GI_BLEED",
                },
            },
            "step8_finalize": {
                "label": "Step 8/9 — Referral Decision",
                "icon": "📋",
                "cls": "urgent" if urgent_final else ("warning" if semi_urgent_final else "info"),
                "codes": {
                    "REFER_ENDOSCOPY",
                    "CAPTURE_ANTICOAG", "CAPTURE_ANTIPLATELET", "CAPTURE_NSAID",
                    "CONSIDER_RECTAL_EXAM",
                },
            },
        }

        # Adjust cls for urgency display
        for k, v in STEP_GROUPS.items():
            if v["cls"] == "routine" and urgency_val == "urgent":
                pass  # keep individual step colors

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

        # ── Render a group card ────────────────────────────────────────────
        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEP_GROUPS[gkey]

            # Override cls for urgency/semi in final step
            cls = g["cls"]
            if gkey == "step2_urgency" and urgency_val == "urgent":
                cls = "urgent"
            elif gkey == "step2_urgency" and urgency_val == "semi_urgent":
                cls = "warning"
            elif gkey == "step8_finalize":
                cls = "urgent" if urgent_final else ("warning" if semi_urgent_final else "info")

            icon = g["icon"]
            label = g["label"]

            border_colors = {
                "routine": "#22c55e", "info": "#3b82f6",
                "urgent": "#ef4444", "warning": "#f97316",
            }
            bg_colors = {
                "routine": "#052e16", "info": "#0c1a2e",
                "urgent": "#3b0a0a", "warning": "#3f2a04",
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
                reason_l = output.reason.lower()
                is_urgent = "urgent" in reason_l and "not" not in reason_l
                is_semi   = "semi" in reason_l
                is_not_ida = "not confirmed" in reason_l or "alternative anemia" in reason_l
                is_hrrb   = "high-risk rectal" in reason_l or "hrrb" in reason_l
                is_complete = "complete" in reason_l and "endoscop" in reason_l
                is_overridden = "overridden" in reason_l

                if is_urgent or (urgency_val == "urgent" and is_complete):
                    bg, border, icon_s = "#3b0a0a", "#ef4444", "🚨"
                    title = "Urgent Referral — Gastroscopy + Colonoscopy <2 Weeks"
                    tcol = "#fecaca"
                elif is_semi or (urgency_val == "semi_urgent" and is_complete):
                    bg, border, icon_s = "#3f2a04", "#f97316", "📅"
                    title = "Semi-Urgent Referral — Gastroscopy + Colonoscopy <8 Weeks"
                    tcol = "#fed7aa"
                elif is_not_ida:
                    bg, border, icon_s = "#3b0a0a", "#ef4444", "⚠️"
                    title = "IDA Not Confirmed — Investigate Alternative Anemia Causes"
                    tcol = "#fecaca"
                elif is_hrrb:
                    bg, border, icon_s = "#2d1a00", "#f59e0b", "🩸"
                    title = "High-Risk Rectal Bleeding — Follow HRRB Pathway"
                    tcol = "#fde68a"
                elif is_overridden:
                    bg, border, icon_s = "#1e1e2e", "#6366f1", "🔒"
                    title = "Referral Overridden by Clinician"
                    tcol = "#c7d2fe"
                elif is_complete:
                    bg, border, icon_s = "#052e16", "#22c55e", "✅"
                    title = "IDA Pathway Complete — Proceed with Endoscopic Evaluation"
                    tcol = "#bbf7d0"
                else:
                    bg, border, icon_s = "#1e1e2e", "#6366f1", "ℹ️"
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
                    f'font-weight:700;color:{tcol}">{icon_s} {html.escape(title)}</p>'
                    f'{action_block}</div>',
                    unsafe_allow_html=True,
                )

        # ── Render everything ──────────────────────────────────────────────
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
        st.session_state.ida_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.ida_notes,
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
                    for o in st.session_state.ida_overrides
                ],
                "clinician_notes": st.session_state.ida_notes,
            },
        }

        if st.button("💾 Save this output", key="ida_save_output"):
            st.session_state.ida_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "ida_saved_output" in st.session_state:
            md_text = build_ida_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.ida_overrides,
                notes=st.session_state.ida_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="ida_summary.md",
                mime="text/markdown",
                key="ida_download_md",
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
                            (o for o in st.session_state.ida_overrides
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
                                    st.session_state.ida_overrides = [
                                        o for o in st.session_state.ida_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.ida_overrides.append(
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
                                st.session_state.ida_overrides = [
                                    o for o in st.session_state.ida_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.ida_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.ida_overrides:
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
