import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components
from chronic_diarrhea_engine import (
    run_chronic_diarrhea_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="Chronic Diarrhea", layout="wide")

# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def build_cd_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Chronic Diarrhea Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / {str(patient_data.get('sex', 'N/A')).capitalize()}")
    lines.append(f"- **Loose/watery stools per day:** {_safe_text(patient_data.get('loose_watery_stools_per_day')) or 'Not documented'}")
    lines.append(f"- **Symptom duration (weeks):** {_safe_text(patient_data.get('symptom_duration_weeks')) or 'Not documented'}")
    lines.append(f"- **Fecal Calprotectin:** {_safe_text(patient_data.get('fecal_calprotectin_ug_g')) or 'Not documented'}")
    lines.append(f"- **Celiac screen positive:** {_safe_text(patient_data.get('celiac_screen_positive'))}")
    lines.append(f"- **Unsatisfactory response:** {_safe_text(patient_data.get('unsatisfactory_response_to_treatment'))}")
    lines.append("")

    lines.append("## Clinical Recommendations")
    if not outputs:
        lines.append("- No recommendations generated.")
    else:
        for o in outputs:
            if isinstance(o, Action):
                urgency = (o.urgency or "info").upper()
                lines.append(f"- **[{urgency}]** {_safe_text(o.label)}")
                if isinstance(o.details, dict):
                    for bullet in o.details.get("bullets", []):
                        lines.append(f"  - {_safe_text(bullet)}")
                    for note in o.details.get("notes", []):
                        lines.append(f"  - Note: {_safe_text(note)}")
                    for support in o.details.get("supported_by", []):
                        lines.append(f"  - Support: {_safe_text(support)}")
            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                for a in getattr(o, "actions", []) or []:
                    lines.append(f"  - Follow-up: {_safe_text(a.label)}")
            elif isinstance(o, DataRequest):
                missing = ", ".join(o.missing_fields)
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing fields: {missing}")
                for a in getattr(o, "suggested_actions", []) or []:
                    lines.append(f"  - Suggested action: {_safe_text(a.label)}")

    lines.append("")
    lines.append("## Active Overrides")
    if overrides:
        for ov in overrides:
            lines.append(
                f"- **{_safe_text(ov.target_node)}.{_safe_text(ov.field)}** -> `{_safe_text(ov.new_value)}` "
                f"(Reason: {_safe_text(ov.reason)})"
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
""",
    unsafe_allow_html=True,
)

st.title("Chronic Diarrhea")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "cd_overrides" not in st.session_state:
    st.session_state.cd_overrides = []
if "cd_has_run" not in st.session_state:
    st.session_state.cd_has_run = False
if "cd_notes" not in st.session_state:
    st.session_state.cd_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", min_value=1, max_value=120, value=52, step=1)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**Entry Criteria**")
    stools_per_day = st.number_input(
        "Loose/watery stools per day",
        min_value=0,
        value=3,
        step=1,
        help="Chronic diarrhea pathway entry is 3 or more loose/watery stools per day.",
    )
    duration_weeks = st.number_input(
        "Symptom duration (weeks)",
        min_value=0,
        value=4,
        step=1,
        help="Pathway entry requires onset at least 4 weeks ago.",
    )

    st.markdown("**Alarm Features**")
    fh_ibd = st.checkbox("Family history IBD (first-degree)")
    fh_crc = st.checkbox("Family history colorectal cancer (first-degree)")
    onset_50 = st.checkbox("Symptom onset after age 50")
    nocturnal = st.checkbox("Nocturnal symptoms")
    incontinence = st.checkbox("Significant incontinence")
    visible_blood = st.checkbox("Visible blood in stool")
    ida = st.checkbox("Iron deficiency anemia present")
    weight_loss_pct = st.number_input(
        "Unintended weight loss % (6-12 months)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

    st.markdown("**Baseline Investigations**")
    cbc_done = st.checkbox("CBC done", value=True)
    electrolytes_done = st.checkbox("Electrolytes done", value=True)
    ferritin_done = st.checkbox("Ferritin done", value=True)
    crp_done = st.checkbox("CRP done", value=True)
    celiac_done = st.checkbox("Celiac screen done", value=True)
    celiac_pos = st.checkbox("Celiac screen POSITIVE")
    c_diff_done = st.checkbox("C. difficile done", value=True)
    ova_parasites_done = st.checkbox("Ova and parasites done", value=True)

    st.markdown("**Inflammation / IBS Context**")
    high_suspicion_ibd = st.selectbox("High clinical suspicion of IBD?", ["Unknown", "Yes", "No"])
    fcp_done = st.checkbox("Fecal calprotectin done")
    fcp_ug_g = st.number_input(
        "Fecal calprotectin (µg/g)",
        min_value=0,
        value=0,
        step=10,
    )
    pain_bloating = st.checkbox("Predominant pain or bloating (suspect IBS pathway)")
    suspect_ibsd = st.checkbox("Suspected IBS-D")

    st.markdown("**Alternative Diagnoses / Secondary Causes**")
    suspect_mc = st.checkbox("Suspect Microscopic Colitis")
    suspect_bad = st.checkbox("Suspect Bile Acid Diarrhea (BAD)")
    sibo_risk = st.checkbox("SIBO risk factors present")
    known_pancreatic = st.checkbox("Known pancreatic disease")
    med_review = st.checkbox("Medication review done", value=True)
    underlying_cond = st.checkbox("Underlying conditions optimized", value=True)
    hx_chole = st.checkbox("History of cholecystectomy")
    hx_bariatric = st.checkbox("History of bariatric surgery")
    hx_covid = st.checkbox("History of COVID-19")
    diet_review = st.checkbox("Dietary trigger review done", value=True)

    st.markdown("**Management Response**")
    unsat_resp_sel = st.selectbox("Unsatisfactory response to treatment?", ["Unknown", "Yes", "No"])
    advice_service = st.checkbox("Advice service considered before referral")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.cd_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.cd_overrides = []
        if "cd_saved_output" in st.session_state:
            del st.session_state["cd_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if not st.session_state.cd_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        unsat_map = {"Unknown": None, "Yes": True, "No": False}
        ibd_susp_map = {"Unknown": None, "Yes": True, "No": False}

        patient_data = {
            "age": age,
            "sex": sex,
            "loose_watery_stools_per_day": stools_per_day,
            "symptom_duration_weeks": duration_weeks,
            "family_history_ibd_first_degree": fh_ibd or None,
            "family_history_crc_first_degree": fh_crc or None,
            "symptom_onset_after_age_50": onset_50 or None,
            "nocturnal_symptoms": nocturnal or None,
            "significant_incontinence": incontinence or None,
            "visible_blood_in_stool": visible_blood or None,
            "iron_deficiency_anemia_present": ida or None,
            "unintended_weight_loss_percent_6_to_12_months": weight_loss_pct,
            "cbc_done": cbc_done,
            "electrolytes_done": electrolytes_done,
            "ferritin_done": ferritin_done,
            "crp_done": crp_done,
            "celiac_screen_done": celiac_done,
            "celiac_screen_positive": celiac_pos,
            "c_diff_done": c_diff_done,
            "ova_parasites_done": ova_parasites_done,
            "high_suspicion_ibd": ibd_susp_map[high_suspicion_ibd],
            "fecal_calprotectin_done": fcp_done,
            "fecal_calprotectin_ug_g": (fcp_ug_g if fcp_done and fcp_ug_g > 0 else None),
            "predominant_pain_or_bloating": pain_bloating or None,
            "suspected_ibsd": suspect_ibsd or None,
            "suspect_microscopic_colitis": suspect_mc or None,
            "suspect_bad": suspect_bad or None,
            "sibo_risk_factor_present": sibo_risk or None,
            "known_pancreatic_disease": known_pancreatic or None,
            "medication_review_done": med_review or None,
            "underlying_conditions_reviewed": underlying_cond or None,
            "history_of_cholecystectomy": hx_chole or None,
            "history_of_bariatric_surgery": hx_bariatric or None,
            "history_of_covid19": hx_covid or None,
            "dietary_trigger_review_done": diet_review or None,
            "unsatisfactory_response_to_treatment": unsat_map[unsat_resp_sel],
            "advice_service_considered": advice_service or None,
        }

        outputs, logs, applied_overrides = run_chronic_diarrhea_pathway(
            patient_data, overrides=st.session_state.cd_overrides
        )

        # ── DERIVED PATHWAY STATE FOR SVG ────────────────────────────────────
        def has_action(code: str) -> bool:
            return any(isinstance(o, Action) and getattr(o, "code", None) == code for o in outputs)

        entry_met = has_action("CHRONIC_DIARRHEA_ENTRY_MET")
        entry_fail = has_action("NOT_CHRONIC_DIARRHEA")
        urgent_referral = has_action("URGENT_ENDOSCOPY_REFERRAL")
        positive_celiac = has_action("REFER_POSITIVE_CELIAC")
        elevated_fcp = has_action("REFER_ELEVATED_FECAL_CALPROTECTIN")
        secondary_reviewed = has_action("SECONDARY_CAUSES_REVIEWED") or any(
            isinstance(o, Action) and "REVIEW" in getattr(o, "code", "") for o in outputs
        )
        route_ibs = has_action("ROUTE_IBS_PATHWAY")
        failed_management_refer = has_action("REFER_FAILED_MANAGEMENT")
        medical_home = has_action("CONTINUE_MEDICAL_HOME_CARE")

        v1 = True
        v2 = entry_met
        v3 = v2 and not urgent_referral
        v4 = v3 and not positive_celiac and not elevated_fcp
        v5 = v4
        v6 = v5
        v7 = v6
        v8 = v7 and not route_ibs
        v9 = v8 and not failed_management_refer and medical_home

        C_MAIN = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"
        C_EXIT = "#d97706"
        C_TEXT = "#ffffff"
        C_DIM = "#94a3b8"
        C_BG = "#0f172a"

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
        W, H = 760, 1180
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
                svgt(x + w/2, y + h/2 - 8, line1, tc, 11, True)
                svgt(x + w/2, y + h/2 + 7, line2, tc, 11, True)
            else:
                svgt(x + w/2, y + h/2 + 4, line1, tc, 11, True)
            if sub:
                svgt(x + w/2, y + h - 8, sub, tc + "99", 9)

        def diamond_node(cx, cy, w, h, color, line1, line2=""):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            hw, hh = w / 2, h / 2
            pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
            svg.append(
                f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(cx, cy - 7, line1, tc, 10, True)
                svgt(cx, cy + 8, line2, tc, 10, True)
            else:
                svgt(cx, cy + 4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                f'fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>'
            )
            if line2:
                svgt(x + w/2, y + h/2 - 7, line1, tc, 10, True)
                svgt(x + w/2, y + h/2 + 7, line2, tc, 9)
            else:
                svgt(x + w/2, y + h/2 + 4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                f'stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt(x + 8, (y1 + y2) / 2 - 3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(
                f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" '
                f'fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>'
            )
            if label:
                svgt((x1 + x2) / 2, y1 - 5, label, stroke, 10, True)

        CX = 380
        NW, NH = 210, 50
        DW, DH = 210, 58
        EW, EH = 150, 46
        LEXT = 30
        REXT = W - 30 - EW
        Y = {
            "entry": 18,
            "alarm": 120,
            "baseline": 240,
            "secondary": 390,
            "general": 500,
            "pharm": 610,
            "alt": 730,
            "response": 870,
            "complete": 1010,
        }

        # 1. Suspected chronic diarrhea
        diamond_node(CX, Y["entry"] + DH / 2, DW, DH, dc(v1), "1. Suspected CD", "Criteria Met?")
        exit_node(LEXT, Y["entry"] + (DH - EH) / 2, EW, EH, nc(entry_fail, exit_=True), "Not Chronic", "Exit pathway")
        elbow_line(CX - DW / 2, Y["entry"] + DH / 2, LEXT + EW, Y["entry"] + (DH - EH) / 2 + EH / 2, entry_fail, exit_=True, label="No")
        vline(CX, Y["entry"] + DH, Y["alarm"], v2, label="Yes")

        # 2. Alarm features
        diamond_node(CX, Y["alarm"] + DH / 2, DW, DH, dc(v2), "2. Alarm", "Features?")
        exit_node(REXT, Y["alarm"] + (DH - EH) / 2, EW, EH, nc(urgent_referral, urgent=True), "8. Refer", "Consult / Endoscopy")
        elbow_line(CX + DW / 2, Y["alarm"] + DH / 2, REXT, Y["alarm"] + (DH - EH) / 2 + EH / 2, urgent_referral, urgent=True, label="Yes")
        vline(CX, Y["alarm"] + DH, Y["baseline"], v3, label="No")

        # 3. Baseline investigations
        rect_node(CX - NW / 2, Y["baseline"], NW, NH, nc(v3), "3. Baseline Investigations", sub="CBC, lytes, ferritin, CRP, celiac, stool tests")
        vline(CX, Y["baseline"] + NH, Y["baseline"] + NH + 32, v3)
        diamond_node(CX, Y["baseline"] + NH + 72, DW, DH, dc(v3), "Celiac+ or FCP", "> 120 µg/g?")
        combined_refer = positive_celiac or elevated_fcp
        exit_node(REXT, Y["baseline"] + 54, EW, EH, nc(combined_refer, urgent=True), "8. Refer", "Consult / Endoscopy")
        elbow_line(CX + DW / 2, Y["baseline"] + NH + 72, REXT, Y["baseline"] + 54 + EH / 2, combined_refer, urgent=True, label="Yes")
        vline(CX, Y["baseline"] + NH + 101, Y["secondary"], v4, label="No")

        # 4. Secondary causes
        rect_node(CX - NW / 2, Y["secondary"], NW, NH, nc(v4), "4. Optimize Secondary", "Causes")
        vline(CX, Y["secondary"] + NH, Y["general"], v5)

        # 5. General management
        rect_node(CX - NW / 2, Y["general"], NW, NH, nc(v5), "5. General Principles", "Diet / fibre / lifestyle")
        vline(CX, Y["general"] + NH, Y["pharm"], v6)

        # 6. Pharmacological options
        rect_node(CX - NW / 2, Y["pharm"], NW, NH, nc(v6), "6. Pharmacological", "Options")
        vline(CX, Y["pharm"] + NH, Y["alt"], v7)

        # 7. Alternative diagnoses
        diamond_node(CX, Y["alt"] + DH / 2, DW, DH, dc(v7), "7. Alternative Dx", "IBS suspected?")
        exit_node(LEXT, Y["alt"] + (DH - EH) / 2, EW, EH, nc(route_ibs, exit_=True), "Follow", "IBS Pathway")
        elbow_line(CX - DW / 2, Y["alt"] + DH / 2, LEXT + EW, Y["alt"] + (DH - EH) / 2 + EH / 2, route_ibs, exit_=True, label="Yes")
        vline(CX, Y["alt"] + DH, Y["response"], v8, label="No")

        # 8. Response to management / referral
        diamond_node(CX, Y["response"] + DH / 2, DW, DH, dc(v8), "8. Response", "Unsatisfactory?")
        exit_node(REXT, Y["response"] + (DH - EH) / 2, EW, EH, nc(failed_management_refer, urgent=True), "Refer", "Consider advice service")
        elbow_line(CX + DW / 2, Y["response"] + DH / 2, REXT, Y["response"] + (DH - EH) / 2 + EH / 2, failed_management_refer, urgent=True, label="Yes")
        vline(CX, Y["response"] + DH, Y["complete"], v9, label="No")
        rect_node(CX - NW / 2, Y["complete"], NW, NH, nc(v9, exit_=True), "Continue Care in", "Medical Home")

        ly = H - 22
        lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"),
            (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"),
            (C_EXIT, "Exit/Off-ramp"),
            (C_UNVISIT, "Not reached"),
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx + 16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 135
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">' + ''.join(svg) + '</div>',
            height=1200,
            scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        alarm_fields = [
            ("family_history_ibd_first_degree", "FHx IBD"),
            ("family_history_crc_first_degree", "FHx CRC"),
            ("symptom_onset_after_age_50", "Onset >50"),
            ("nocturnal_symptoms", "Nocturnal sx"),
            ("significant_incontinence", "Incontinence"),
            ("visible_blood_in_stool", "Visible blood"),
            ("iron_deficiency_anemia_present", "IDA"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        if weight_loss_pct > 5:
            active_alarms.append(f"Weight loss ({weight_loss_pct}%)")

        alarm_str = ", ".join(active_alarms) if active_alarms else "None"
        fcp_str = f"{patient_data.get('fecal_calprotectin_ug_g')} µg/g" if patient_data.get("fecal_calprotectin_ug_g") is not None else "Not done / not recorded"

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Stools/day & Duration:</b> {stools_per_day} | {duration_weeks} weeks</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span><br>'
            f'<span><b>Fecal Calprotectin:</b> {fcp_str}</span><br>'
            f'<span><b>Unsatisfactory Response:</b> {unsat_resp_sel}</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── GROUP OUTPUTS SIMILAR TO NAFLD ───────────────────────────────────
        STEPGROUPS = {
            "step1": {"label": "Step 1 — Suspected Chronic Diarrhea", "icon": "•", "cls": "routine", "codes": ["CHRONIC_DIARRHEA_ENTRY_MET", "NOT_CHRONIC_DIARRHEA"]},
            "step2": {"label": "Step 2 — Alarm Features", "icon": "⚠️", "cls": "urgent", "codes": ["URGENT_ENDOSCOPY_REFERRAL"]},
            "step3": {"label": "Step 3 — Baseline Investigations", "icon": "🧪", "cls": "routine", "codes": ["BASELINE_INVESTIGATIONS_COMPLETE", "REFER_POSITIVE_CELIAC", "REFER_ELEVATED_FECAL_CALPROTECTIN"]},
            "step4": {"label": "Step 4 — Secondary Causes Review", "icon": "🩺", "cls": "routine", "codes": ["SECONDARY_CAUSES_REVIEWED"]},
            "step5": {"label": "Step 5 — General Management", "icon": "📘", "cls": "routine", "codes": ["GENERAL_MANAGEMENT_RECOMMENDED"]},
            "step6": {"label": "Step 6 — Pharmacological Options", "icon": "💊", "cls": "routine", "codes": ["PHARMACOLOGICAL_OPTIONS_RECOMMENDED"]},
            "step7": {"label": "Step 7 — Alternative Diagnoses", "icon": "🔎", "cls": "warning", "codes": ["ROUTE_IBS_PATHWAY", "CONSIDER_ALTERNATIVE_DIAGNOSES"]},
            "step8": {"label": "Step 8 — Ongoing Response", "icon": "📌", "cls": "info", "codes": ["REFER_FAILED_MANAGEMENT", "CONTINUE_MEDICAL_HOME_CARE"]},
        }

        code_to_group = {}
        for gkey, gdata in STEPGROUPS.items():
            for c in gdata["codes"]:
                code_to_group[c] = gkey

        grouped = {k: [] for k in STEPGROUPS}
        stops_and_requests = []
        override_candidates = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                gkey = code_to_group.get(getattr(output, "code", ""))
                if gkey:
                    grouped[gkey].append(output)
                else:
                    grouped.setdefault("step8", []).append(output)
                if getattr(output, "override_options", None):
                    override_candidates.append(output)

        for output in outputs:
            if isinstance(output, Stop):
                for a in getattr(output, "actions", []) or []:
                    if getattr(a, "override_options", None):
                        override_candidates.append(a)

        def _detail_html(details) -> str:
            if not details:
                return ""
            items = ""
            if isinstance(details, dict):
                for bullet in details.get("bullets", []):
                    items += f"<li>{html.escape(str(bullet))}</li>"
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                for opt in details.get("options", []):
                    items += f"<li>🔹 {html.escape(str(opt))}</li>"
                skip = {"bullets", "supported_by", "options", "notes"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k)).replace('_', ' ').title()}:</b> {html.escape(str(v))}</li>"
                for n in details.get("notes", []):
                    items += f"<li>Note: {html.escape(str(n))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {"urgent": "urgent", "warning": "warning", None: "routine", "": "routine", "info": "info"}
            cls = extra_cls or urgency_to_cls.get(a.urgency or "", "routine")
            badge_label = (a.urgency or "info").upper()
            label_html = html.escape(a.label).replace("\n   ", "<br>&nbsp;&nbsp;&nbsp;").replace("\n", "<br>")
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">🔒 Override available — reason required</p>'
                if getattr(a, "override_options", None) else ""
            )
            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f'{detail_html}{override_html}'
                '</div>',
                unsafe_allow_html=True,
            )

        def render_group(gkey: str, actions: list) -> None:
            if not actions:
                return
            g = STEPGROUPS[gkey]
            cls = g["cls"]
            icon = g["icon"]
            label = g["label"]
            border_colors = {"routine": "#22c55e", "info": "#3b82f6", "urgent": "#ef4444", "warning": "#f59e0b"}
            bg_colors = {"routine": "#052e16", "info": "#0c1a2e", "urgent": "#3b0a0a", "warning": "#2d1a00"}
            border = border_colors.get(cls, "#22c55e")
            bg = bg_colors.get(cls, "#052e16")
            bullets = ""
            for a in actions:
                bullets += f'<li style="margin-bottom:5px">{html.escape(a.label)}</li>'
                if getattr(a, "override_options", None) and a not in override_candidates:
                    override_candidates.append(a)
            st.markdown(
                f'<div style="background:{bg};border-left:5px solid {border};border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                f'<p style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:#e2e8f0;letter-spacing:0.3px">{icon} {html.escape(label)}</p>'
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
                    f'<p style="margin:0;font-size:12px;color:#94a3b8">Missing: <code style="color:#fbbf24">{html.escape(missing_str)}</code></p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                for sa in getattr(output, "suggested_actions", []) or []:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason = output.reason.lower()
                if "consult" in reason or "endoscopy" in reason or "refer" in reason:
                    bg, border, title, tcol = "#3b0a0a", "#ef4444", output.reason, "#fecaca"
                elif "ibs" in reason:
                    bg, border, title, tcol = "#2d1a00", "#f59e0b", output.reason, "#fde68a"
                else:
                    bg, border, title, tcol = "#1e1e2e", "#6366f1", output.reason, "#c7d2fe"
                action_bullets = ""
                for a in getattr(output, "actions", []) or []:
                    if getattr(a, "override_options", None) and a not in override_candidates:
                        override_candidates.append(a)
                    action_bullets += f'<li style="margin-bottom:5px">{html.escape(a.label)}</li>'
                action_block = (
                    f'<ul style="margin:10px 0 0;padding-left:18px;color:#cbd5e1;font-size:13.5px;line-height:1.7">{action_bullets}</ul>'
                    if action_bullets else ""
                )
                st.markdown(
                    f'<div style="background:{bg};border-left:5px solid {border};border-radius:10px;padding:14px 18px;margin-bottom:14px">'
                    f'<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:{tcol}">🛑 {html.escape(title)}</p>'
                    f'{action_block}'
                    '</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)
        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]

        for o in blocking:
            render_stop_request(o)
        for gkey in ["step1", "step2", "step3", "step4", "step5", "step6", "step7", "step8"]:
            render_group(gkey, grouped.get(gkey, []))
        for o in terminal:
            render_stop_request(o)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.cd_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.cd_notes,
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
                    for o in st.session_state.cd_overrides
                ],
                "clinician_notes": st.session_state.cd_notes,
            },
        }

        if st.button("💾 Save this output", key="cd_save_output"):
            st.session_state.cd_saved_output = {"saved_at": datetime.now().isoformat(), "payload": full_output}
            st.success("Output saved for this session.")

        if "cd_saved_output" in st.session_state:
            md_text = build_cd_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.cd_overrides,
                notes=st.session_state.cd_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="chronic_diarrhea_summary.md",
                mime="text/markdown",
                key="cd_download_md",
            )

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
                            (o for o in st.session_state.cd_overrides if o.target_node == raw_node and o.field == raw_field),
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
                                    st.session_state.cd_overrides = [
                                        o for o in st.session_state.cd_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.cd_overrides.append(
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
                                st.session_state.cd_overrides = [
                                    o for o in st.session_state.cd_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.cd_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.cd_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code>'
                            f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            '</div>',
                            unsafe_allow_html=True,
                        )

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if getattr(log, "used_inputs", None):
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
