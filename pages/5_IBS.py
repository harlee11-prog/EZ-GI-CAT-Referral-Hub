import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st

from ibs_engine import (
    run_ibs_pathway,
    Action,
    DataRequest,
    Stop,
    Override,
)

st.set_page_config(page_title="IBS Pathway", layout="wide")


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())


def _pretty(s: str) -> str:
    return s.replace("_", " ").title()


def _yn_select(label: str, *, index: int = 0, key: str | None = None):
    choice = st.selectbox(label, ["Unknown / Not assessed", "Yes", "No"], index=index, key=key)
    if choice == "Yes":
        return True
    if choice == "No":
        return False
    return None


def _num_or_none(v, allow_zero: bool = False):
    if v is None:
        return None
    if allow_zero:
        return v
    return None if v == 0 else v


def determine_ibs_subtype(hard_pct, loose_pct) -> str:
    if hard_pct is None or loose_pct is None:
        return "Unknown"
    if hard_pct >= 25 and loose_pct < 25:
        return "IBS-C"
    if loose_pct >= 25 and hard_pct < 25:
        return "IBS-D"
    if hard_pct >= 25 and loose_pct >= 25:
        return "IBS-M"
    return "IBS-U"


def build_ibs_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# IBS Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    subtype = determine_ibs_subtype(
        patient_data.get("hard_stool_percent"),
        patient_data.get("loose_stool_percent"),
    )

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {patient_data.get('age', 'N/A')} / {str(patient_data.get('sex', 'N/A')).capitalize()}")
    lines.append(f"- **Abdominal pain days/week:** {patient_data.get('abdominal_pain_days_per_week', 'Not documented')}")
    lines.append(f"- **Symptom months present:** {patient_data.get('symptom_months_present', 'Not documented')}")
    lines.append(f"- **Rome IV supporting features present:** {sum(1 for x in [patient_data.get('pain_related_to_defecation'), patient_data.get('pain_with_change_in_stool_frequency'), patient_data.get('pain_with_change_in_stool_form')] if x is True)} / 3")
    lines.append(f"- **IBS subtype:** {subtype}")
    lines.append(f"- **High suspicion of IBD:** {patient_data.get('high_suspicion_ibd')}")
    lines.append(f"- **Fecal calprotectin (µg/g):** {patient_data.get('fecal_calprotectin_ug_g', 'Not documented')}")
    lines.append(f"- **Unsatisfactory response:** {patient_data.get('unsatisfactory_response_to_treatment')}")
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
                    skip = {"bullets", "notes", "supported_by", "options", "regimen_key"}
                    for k, v in o.details.items():
                        if k in skip:
                            continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_pretty(k)}: {_safe_text(item)}")
                        elif v not in (None, False, "", []):
                            lines.append(f"  - {_pretty(k)}: {_safe_text(v)}")

            elif isinstance(o, Stop):
                lines.append(f"- **[STOP]** {_safe_text(o.reason)}")
                for a in getattr(o, "actions", []) or []:
                    lines.append(f"  - Follow-up: {_safe_text(a.label)}")

            elif isinstance(o, DataRequest):
                lines.append(f"- **[DATA NEEDED]** {_safe_text(o.message)}")
                lines.append(f"  - Missing fields: {', '.join(o.missing_fields)}")
                for a in getattr(o, "suggested_actions", []) or []:
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


def classify_action(action: Action) -> str:
    txt = f"{getattr(action, 'code', '')} {action.label}".lower()

    if any(k in txt for k in ["rome", "criteria", "suspected ibs", "diagnostic criteria"]):
        return "step1"

    if any(k in txt for k in ["cbc", "ferritin", "celiac", "baseline", "medical history", "physical exam", "secondary cause", "medication review"]):
        return "step2"

    if any(k in txt for k in ["alarm", "family history", "visible blood", "nocturnal", "iron deficiency", "onset after age 50"]):
        return "step3"

    if any(k in txt for k in ["diet", "fibre", "fiber", "physical activity", "psychological", "peppermint", "antispas", "counselling", "hypnotherapy", "cbt", "reassurance"]):
        return "step4"

    if any(k in txt for k in ["ibs-d", "ibs-c", "ibs-m", "ibs-u", "subtype", "loperamide", "tca", "tricyclic", "probiotic", "fodmap", "rifaximin", "osmotic", "linaclotide", "prucalopride", "tenapanor", "plecanatide", "ssri"]):
        return "step5"

    if any(k in txt for k in ["calprotectin", "refer", "consult", "endoscopy", "advice service", "unsatisfactory", "specialist"]):
        return "step6"

    return "step4"


def serialize_output(o):
    if isinstance(o, Action):
        return {"type": "action", "code": getattr(o, "code", None), "label": o.label, "urgency": o.urgency}
    if isinstance(o, Stop):
        return {"type": "stop", "reason": o.reason, "urgency": getattr(o, "urgency", None)}
    if isinstance(o, DataRequest):
        return {"type": "data_request", "message": o.message, "missing_fields": o.missing_fields}
    return {"type": "other", "repr": repr(o)}


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

st.title("Irritable Bowel Syndrome (IBS)")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "ibs_overrides" not in st.session_state:
    st.session_state.ibs_overrides = []
if "ibs_has_run" not in st.session_state:
    st.session_state.ibs_has_run = False
if "ibs_notes" not in st.session_state:
    st.session_state.ibs_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    age = st.number_input("Age", min_value=1, max_value=120, value=35, step=1)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**IBS Diagnostic Criteria (Rome IV)**")
    pain_days = st.number_input(
        "Abdominal pain days per week",
        min_value=0,
        max_value=7,
        value=1,
        step=1,
        help="Rome IV requires recurrent abdominal pain at least 1 day/week on average in the last 3 months.",
    )
    symptom_months = st.number_input(
        "Symptom months present",
        min_value=0,
        max_value=120,
        value=3,
        step=1,
        help="Rome IV requires symptoms present for at least 3 months.",
    )
    pain_related_to_defecation = _yn_select("Pain related to defecation?")
    pain_freq_change = _yn_select("Pain associated with change in stool frequency?")
    pain_form_change = _yn_select("Pain associated with change in stool form?")

    st.markdown("**Baseline Investigations**")
    medical_history_done = st.checkbox("Detailed history / physical exam completed", value=True)
    medication_review_done = st.checkbox("Medication / secondary cause review completed", value=True)
    cbc_done = _yn_select("CBC completed?")
    ferritin_done = _yn_select("Ferritin completed?")
    celiac_screen_done = _yn_select("Celiac screen completed?")
    celiac_screen_positive = st.checkbox("Celiac screen POSITIVE", disabled=(celiac_screen_done is not True))

    st.markdown("**Alarm Features**")
    family_history_crc = st.checkbox("Family history (1st degree) of CRC")
    family_history_ibd = st.checkbox("Family history (1st degree) of IBD")
    symptom_onset_after_50 = st.checkbox("Symptom onset after age 50")
    visible_blood = st.checkbox("Visible blood in stool")
    nocturnal_symptoms = st.checkbox("Nocturnal symptoms")
    iron_deficiency_anemia = st.checkbox("Iron deficiency anemia")
    unintended_weight_loss = st.number_input(
        "Unintended weight loss % (6-12 months)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=1.0,
    )

    st.markdown("**Subtype Inputs (Bristol Pattern)**")
    hard_stool_percent = st.slider("% Hard stools (Types 1-2)", min_value=0, max_value=100, value=25, step=5)
    loose_stool_percent = st.slider("% Loose stools (Types 6-7)", min_value=0, max_value=100, value=0, step=5)

    st.markdown("**IBS-D / IBD Escalation**")
    high_suspicion_ibd = _yn_select("High clinical suspicion of IBD?")
    history_cholecystectomy = st.checkbox("History of cholecystectomy")
    fecal_calprotectin = None
    if high_suspicion_ibd is True:
        fecal_calprotectin = st.number_input(
            "Fecal calprotectin (µg/g)",
            min_value=0,
            value=0,
            step=10,
            help="Use when IBS-D and high clinical suspicion of IBD.",
        )

    st.markdown("**Management Follow-up**")
    unsatisfactory_response = _yn_select("Unsatisfactory response to treatment?")
    advice_service_considered = st.checkbox("Advice service considered before referral")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.ibs_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.ibs_overrides = []
        if "ibs_saved_output" in st.session_state:
            del st.session_state["ibs_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if not st.session_state.ibs_has_run:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
    else:
        patient_data = {
            "age": age,
            "sex": sex,
            "abdominal_pain_days_per_week": _num_or_none(pain_days, allow_zero=False),
            "symptom_months_present": _num_or_none(symptom_months, allow_zero=False),
            "pain_related_to_defecation": pain_related_to_defecation,
            "pain_with_change_in_stool_frequency": pain_freq_change,
            "pain_with_change_in_stool_form": pain_form_change,
            "medical_history_done": medical_history_done or None,
            "medication_review_done": medication_review_done or None,
            "cbc_done": cbc_done,
            "ferritin_done": ferritin_done,
            "celiac_screen_done": celiac_screen_done,
            "celiac_screen_positive": celiac_screen_positive if celiac_screen_done is True else None,
            "family_history_crc_first_degree": family_history_crc or None,
            "family_history_ibd_first_degree": family_history_ibd or None,
            "symptom_onset_after_age_50": symptom_onset_after_50 or None,
            "visible_blood_in_stool": visible_blood or None,
            "nocturnal_symptoms": nocturnal_symptoms or None,
            "iron_deficiency_anemia_present": iron_deficiency_anemia or None,
            "unintended_weight_loss_percent_6_to_12_months": unintended_weight_loss,
            "hard_stool_percent": hard_stool_percent,
            "loose_stool_percent": loose_stool_percent,
            "high_suspicion_ibd": high_suspicion_ibd,
            "fecal_calprotectin_ug_g": _num_or_none(fecal_calprotectin, allow_zero=False),
            "history_of_cholecystectomy": history_cholecystectomy or None,
            "unsatisfactory_response_to_treatment": unsatisfactory_response,
            "advice_service_considered": advice_service_considered or None,
        }

        outputs, logs, applied_overrides = run_ibs_pathway(
            patient_data,
            overrides=st.session_state.ibs_overrides,
        )

        # ── DERIVED STATE FOR VISUAL / CONTEXT ───────────────────────────────
        rome_feature_count = sum(
            1 for x in [
                pain_related_to_defecation,
                pain_freq_change,
                pain_form_change,
            ] if x is True
        )
        rome_met = (
            patient_data["abdominal_pain_days_per_week"] is not None
            and patient_data["abdominal_pain_days_per_week"] >= 1
            and patient_data["symptom_months_present"] is not None
            and patient_data["symptom_months_present"] >= 3
            and rome_feature_count >= 2
        )

        baseline_complete = (
            cbc_done is True
            and ferritin_done is True
            and celiac_screen_done is True
        )
        celiac_positive = celiac_screen_done is True and celiac_screen_positive is True

        alarm_present = any([
            family_history_crc,
            family_history_ibd,
            symptom_onset_after_50,
            visible_blood,
            nocturnal_symptoms,
            iron_deficiency_anemia,
            unintended_weight_loss > 5.0,
        ])

        subtype = determine_ibs_subtype(hard_stool_percent, loose_stool_percent)
        presumed_ibs = rome_met and baseline_complete and not celiac_positive and not alarm_present

        is_ibsd = subtype == "IBS-D"
        is_ibsmu = subtype in ["IBS-M", "IBS-U"]
        is_ibsc = subtype == "IBS-C"

        fcp_val = patient_data.get("fecal_calprotectin_ug_g")
        fcp_high = (high_suspicion_ibd is True and fcp_val is not None and fcp_val >= 120)
        fcp_no = (high_suspicion_ibd is True and fcp_val is not None and fcp_val < 120)

        response_ready = False
        if presumed_ibs:
            if not is_ibsd:
                response_ready = True
            elif high_suspicion_ibd is False:
                response_ready = True
            elif high_suspicion_ibd is True and fcp_val is not None and not fcp_high:
                response_ready = True

        complete_in_home = response_ready and unsatisfactory_response is False
        advice_exit = response_ready and unsatisfactory_response is True

        # ── SVG COLORS ────────────────────────────────────────────────────────
        C_MAIN = "#16a34a"
        C_UNVISIT = "#475569"
        C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"
        C_EXIT = "#d97706"
        C_TEXT = "#ffffff"
        C_DIM = "#94a3b8"
        C_BG = "#0f172a"

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
        W, H = 1280, 1450
        svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" '
            f'viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
        )
        svg.append("<defs>")
        svg.append('<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>')
        svg.append('<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>')
        svg.append('<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>')
        svg.append('<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>')
        svg.append("</defs>")

        def svgt(x, y, text, fill, size=11, bold=False, anchor="middle"):
            w = "bold" if bold else "normal"
            svg.append(
                f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" '
                f'font-size="{size}" font-weight="{w}">{html.escape(str(text))}</text>'
            )

        def rect_node(x, y, w, h, color, line1, line2="", sub="", rx=8):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
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
            svg.append(f'<polygon points="{pts}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(cx, cy - 7, line1, tc, 10, True)
                svgt(cx, cy + 8, line2, tc, 10, True)
            else:
                svgt(cx, cy + 4, line1, tc, 10, True)

        def exit_node(x, y, w, h, color, line1, line2="", rx=7):
            tc = C_TEXT if color != C_UNVISIT else C_DIM
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" stroke="#ffffff18" stroke-width="1.5"/>')
            if line2:
                svgt(x + w/2, y + h/2 - 7, line1, tc, 10, True)
                svgt(x + w/2, y + h/2 + 7, line2, tc, 9)
            else:
                svgt(x + w/2, y + h/2 + 4, line1, tc, 10, True)

        def vline(x, y1, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt(x + 8, (y1 + y2) / 2 - 3, label, stroke, 10, True, "start")

        def elbow_line(x1, y1, x2, y2, vis, urgent=False, exit_=False, label=""):
            m = mid(vis, urgent, exit_)
            stroke = {"mg": "#16a34a", "mr": "#dc2626", "mo": "#d97706"}.get(m, "#64748b")
            dash = "" if vis else 'stroke-dasharray="5,3"'
            svg.append(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{stroke}" stroke-width="2" {dash} marker-end="url(#{m})"/>')
            if label:
                svgt((x1 + x2) / 2, y1 - 6, label, stroke, 10, True)

        # ── PATHWAY LAYOUT CONFIGURATION ──────────────────────────────────────
        CX = 640
        COL_L = 340
        COL_R = 940
        NW, NH = 260, 64
        DW, DH = 220, 64
        EW, EH = 160, 50
        LEXT = 30
        REXT = 1090

        Y = {
            "suspected": 20,
            "rome": 130,
            "baseline": 260,
            "alarm": 390,
            "general": 520,
            "subtype": 650,
            "sub_boxes": 780,
            "ibd_susp": 910,
            "fcp": 1040,
            "response": 1200,
            "complete": 1340,
        }

        # 1. Suspected IBS
        rect_node(CX - NW/2, Y["suspected"], NW, NH, nc(True), "1. Suspected IBS", sub="Recurrent abdominal pain + Rome IV features")
        vline(CX, Y["suspected"] + NH, Y["rome"], True)

        # Rome IV decision
        diamond_node(CX, Y["rome"] + DH/2, DW, DH, dc(True), "Rome IV Criteria", "Met?")
        exit_node(LEXT, Y["rome"] + (DH - EH)/2, EW, EH, nc(not rome_met, exit_=True), "Criteria Not Met", "Stop / reassess")
        elbow_line(CX - DW/2, Y["rome"] + DH/2, LEXT + EW, Y["rome"] + (DH - EH)/2 + EH/2, not rome_met, exit_=True, label="No")
        vline(CX, Y["rome"] + DH, Y["baseline"], rome_met, label="Yes")

        # Baseline
        rect_node(CX - NW/2, Y["baseline"], NW, NH, nc(rome_met), "2. Baseline Investigations", sub="Hx/PE, CBC, ferritin, celiac")
        exit_node(REXT, Y["baseline"] + (NH - EH)/2, EW, EH, nc(rome_met and celiac_positive, urgent=True), "6. Refer", "Positive celiac")
        elbow_line(CX + NW/2, Y["baseline"] + NH/2, REXT, Y["baseline"] + (NH - EH)/2 + EH/2, rome_met and celiac_positive, urgent=True, label="Positive")
        vline(CX, Y["baseline"] + NH, Y["alarm"], rome_met and baseline_complete and not celiac_positive, label="Complete")

        # Alarm
        diamond_node(CX, Y["alarm"] + DH/2, DW, DH, dc(rome_met and baseline_complete and not celiac_positive), "3. Alarm Features", "Present?")
        exit_node(REXT, Y["alarm"] + (DH - EH)/2, EW, EH, nc(rome_met and baseline_complete and not celiac_positive and alarm_present, urgent=True), "6. Refer", "Consult / endoscopy")
        elbow_line(CX + DW/2, Y["alarm"] + DH/2, REXT, Y["alarm"] + (DH - EH)/2 + EH/2, rome_met and baseline_complete and not celiac_positive and alarm_present, urgent=True, label="Yes")
        vline(CX, Y["alarm"] + DH, Y["general"], presumed_ibs, label="No")

        # Core treatment
        rect_node(CX - NW/2, Y["general"], NW, NH, nc(presumed_ibs), "4. Potential Approaches", "All IBS Subtypes", sub="Diet, activity, psychological tx, antispasmodics")
        vline(CX, Y["general"] + NH, Y["subtype"], presumed_ibs)

        # Subtype decision
        diamond_node(CX, Y["subtype"] + DH/2, DW, DH, dc(presumed_ibs), "5. IBS Subtype", "?")

        # ── SUBTYPE BRANCHING ────────────────────────────────────────────────
        subtype_active = presumed_ibs
        ibsd_vis = subtype_active and is_ibsd
        ibsmu_vis = subtype_active and is_ibsmu
        ibsc_vis = subtype_active and is_ibsc

        # Left Branch (IBS-D)
        elbow_line(CX - DW/2, Y["subtype"] + DH/2, COL_L, Y["sub_boxes"], ibsd_vis, label="IBS-D")
        rect_node(COL_L - NW/2, Y["sub_boxes"], NW, NH, nc(ibsd_vis), "IBS-D", "Loperamide / TCA / FODMAP", sub="Rifaximin / Probiotic")

        # Middle Branch (IBS-M/U)
        vline(CX, Y["subtype"] + DH, Y["sub_boxes"], ibsmu_vis, label="IBS-M/U")
        rect_node(CX - NW/2, Y["sub_boxes"], NW, NH, nc(ibsmu_vis), "IBS-M / IBS-U", "Lifestyle / Probiotic / FODMAP", sub="TCA")
        vline(CX, Y["sub_boxes"] + NH, Y["response"], ibsmu_vis) 

        # Right Branch (IBS-C)
        elbow_line(CX + DW/2, Y["subtype"] + DH/2, COL_R, Y["sub_boxes"], ibsc_vis, label="IBS-C")
        rect_node(COL_R - NW/2, Y["sub_boxes"], NW, NH, nc(ibsc_vis), "IBS-C", "Fibre / Laxatives / Linaclotide", sub="Prucalopride / Tenapanor / SSRIs")

        dash_c = "" if ibsc_vis else 'stroke-dasharray="5,3"'
        stroke_c = C_MAIN if ibsc_vis else "#64748b"
        mid_c = mid(ibsc_vis)
        svg.append(f'<polyline points="{COL_R},{Y["sub_boxes"] + NH} {COL_R},{Y["response"] - 25} {CX},{Y["response"] - 25} {CX},{Y["response"]}" fill="none" stroke="{stroke_c}" stroke-width="2" {dash_c} marker-end="url(#{mid_c})"/>')

        # IBD Suspicion (Left Column)
        vline(COL_L, Y["sub_boxes"] + NH, Y["ibd_susp"], ibsd_vis)
        diamond_node(COL_L, Y["ibd_susp"] + DH/2, DW, DH, dc(ibsd_vis), "High IBD", "Suspicion?")

        # IBD Suspicion = Yes -> FCP
        vline(COL_L, Y["ibd_susp"] + DH, Y["fcp"], ibsd_vis and high_suspicion_ibd is True, label="Yes")

        # IBD Suspicion = No -> Bypass FCP, route to Response
        ibsd_no_ibd = (ibsd_vis and high_suspicion_ibd is False)
        dash_ibsd = "" if ibsd_no_ibd else 'stroke-dasharray="5,3"'
        stroke_ibsd = C_MAIN if ibsd_no_ibd else "#64748b"
        mid_ibsd = mid(ibsd_no_ibd)

        px1, py1 = COL_L + DW/2, Y["ibd_susp"] + DH/2
        px2, py2 = px1 + 30, py1
        px3, py3 = px2, Y["response"] - 40
        px4, py4 = CX, py3
        svg.append(f'<polyline points="{px1},{py1} {px2},{py2} {px3},{py3} {px4},{py4} {CX},{Y["response"]}" fill="none" stroke="{stroke_ibsd}" stroke-width="2" {dash_ibsd} marker-end="url(#{mid_ibsd})"/>')
        svgt(px1 + 15, py1 - 5, "No", stroke_ibsd, 10, True)

        # FCP Diamond
        diamond_node(COL_L, Y["fcp"] + DH/2, DW, DH, dc(ibsd_vis and high_suspicion_ibd is True), "Fecal Calprotectin", "≥ 120 µg/g?")

        # FCP = Yes -> Refer (Exit Left)
        fcp_high_vis = (ibsd_vis and high_suspicion_ibd is True and fcp_high)
        exit_node(LEXT, Y["fcp"] + (DH-EH)/2, EW, EH, nc(fcp_high_vis, urgent=True), "6. Refer", "Elevated FCP")
        elbow_line(COL_L - DW/2, Y["fcp"] + DH/2, LEXT + EW, Y["fcp"] + DH/2, fcp_high_vis, urgent=True, label="Yes")

        # FCP = No -> Merge to Response
        fcp_no_vis = (ibsd_vis and high_suspicion_ibd is True and fcp_no)
        dash_fcp = "" if fcp_no_vis else 'stroke-dasharray="5,3"'
        stroke_fcp = C_MAIN if fcp_no_vis else "#64748b"
        mid_fcp = mid(fcp_no_vis)
        svg.append(f'<polyline points="{COL_L},{Y["fcp"] + DH} {COL_L},{Y["response"] - 25} {CX},{Y["response"] - 25} {CX},{Y["response"]}" fill="none" stroke="{stroke_fcp}" stroke-width="2" {dash_fcp} marker-end="url(#{mid_fcp})"/>')
        svgt(COL_L + 12, Y["fcp"] + DH + 15, "No", stroke_fcp, 10, True, "start")

        # ── MERGED OUTCOME ───────────────────────────────────────────────────
        # Response Decision
        diamond_node(CX, Y["response"] + DH/2, DW, DH, dc(response_ready), "Response to", "Treatment?")
        exit_node(REXT, Y["response"] + (DH - EH)/2, EW, EH, nc(advice_exit, exit_=True), "Advice / Refer", "Unsatisfactory response")
        elbow_line(CX + DW/2, Y["response"] + DH/2, REXT, Y["response"] + (DH - EH)/2 + EH/2, advice_exit, exit_=True, label="Unsatisfactory")

        # Complete
        vline(CX, Y["response"] + DH, Y["complete"], complete_in_home, label="Satisfactory")
        rect_node(CX - NW/2, Y["complete"], NW, NH, nc(complete_in_home, exit_=True), "Continue Care in", "Medical Home")

        # ── LEGEND ────────────────────────────────────────────────────────────
        ly = H - 24
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
            lx += 145
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        st.markdown(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto;height:1450px;overflow-y:auto;">'
            + "".join(svg) + "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # ── CONTEXT CARD ──────────────────────────────────────────────────────
        active_alarms = []
        if family_history_crc:
            active_alarms.append("Family hx CRC")
        if family_history_ibd:
            active_alarms.append("Family hx IBD")
        if symptom_onset_after_50:
            active_alarms.append("Onset >50")
        if visible_blood:
            active_alarms.append("Visible blood")
        if nocturnal_symptoms:
            active_alarms.append("Nocturnal symptoms")
        if iron_deficiency_anemia:
            active_alarms.append("IDA")
        if unintended_weight_loss > 5:
            active_alarms.append(f"Weight loss {unintended_weight_loss}%")

        alarm_str = ", ".join(active_alarms) if active_alarms else "None"
        fcp_str = (
            f"{patient_data['fecal_calprotectin_ug_g']} µg/g"
            if patient_data.get("fecal_calprotectin_ug_g") is not None else "Not done / not recorded"
        )

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Rome IV Features:</b> {rome_feature_count}/3 | <b>Criteria Met:</b> {"Yes" if rome_met else "No/Unknown"}</span><br>'
            f'<span><b>Subtype:</b> {subtype} | <b>High IBD Suspicion:</b> {"Yes" if high_suspicion_ibd is True else "No" if high_suspicion_ibd is False else "Unknown"}</span><br>'
            f'<span><b>Fecal Calprotectin:</b> {fcp_str}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── GROUP ACTIONS LIKE NAFLD PAGE ─────────────────────────────────────
        STEPGROUPS = {
            "step1": {"label": "Step 1 — Rome IV Diagnostic Criteria", "icon": "🧠", "cls": "routine"},
            "step2": {"label": "Step 2 — Baseline Investigations", "icon": "🧪", "cls": "routine"},
            "step3": {"label": "Step 3 — Alarm Features", "icon": "🚨", "cls": "urgent"},
            "step4": {"label": "Step 4 — Core IBS Management", "icon": "📘", "cls": "routine"},
            "step5": {"label": "Step 5 — Subtype-Specific Treatment", "icon": "🧭", "cls": "info"},
            "step6": {"label": "Step 6 — Escalation / Referral", "icon": "📌", "cls": "warning"},
        }

        grouped = {k: [] for k in STEPGROUPS}
        stops_and_requests = []
        override_candidates = []

        for output in outputs:
            if isinstance(output, (Stop, DataRequest)):
                stops_and_requests.append(output)
            elif isinstance(output, Action):
                g = classify_action(output)
                grouped[g].append(output)
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
                for note in details.get("notes", []):
                    items += f'<li style="color:#fde68a">⚠️ {html.escape(str(note))}</li>'
                skip = {"bullets", "supported_by", "options", "notes", "regimen_key"}
                for k, v in details.items():
                    if k in skip:
                        continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(_pretty(k))}:</b> {html.escape(str(v))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {
                "urgent": "urgent",
                "warning": "warning",
                None: "routine",
                "": "routine",
                "info": "info",
            }
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
                f"{detail_html}{override_html}"
                "</div>",
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
                if any(k in reason for k in ["consult", "endoscopy", "refer", "calprotectin", "celiac"]):
                    bg, border, tcol = "#3b0a0a", "#ef4444", "#fecaca"
                elif any(k in reason for k in ["advice", "unsatisfactory", "criteria not met", "not met"]):
                    bg, border, tcol = "#2d1a00", "#f59e0b", "#fde68a"
                else:
                    bg, border, tcol = "#1e1e2e", "#6366f1", "#c7d2fe"

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
                    f'<p style="margin:0 0 6px;font-size:13px;font-weight:700;color:{tcol}">🛑 {html.escape(output.reason)}</p>'
                    f'{action_block}'
                    '</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<p class="section-label">RECOMMENDED ACTIONS</p>', unsafe_allow_html=True)

        blocking = [o for o in stops_and_requests if isinstance(o, DataRequest)]
        terminal = [o for o in stops_and_requests if isinstance(o, Stop)]

        for o in blocking:
            render_stop_request(o)

        for gkey in ["step1", "step2", "step3", "step4", "step5", "step6"]:
            render_group(gkey, grouped.get(gkey, []))

        for o in terminal:
            render_stop_request(o)

        # ── NOTES / SAVE / DOWNLOAD ───────────────────────────────────────────
        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.caption("Optional free-text notes to be attached to the clinical recommendations.")
        st.session_state.ibs_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.ibs_notes,
            height=180,
        )

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [serialize_output(o) for o in outputs],
                "overrides": [
                    {
                        "node": o.target_node,
                        "field": o.field,
                        "new_value": o.new_value,
                        "reason": o.reason,
                        "created_at": o.created_at.isoformat(),
                    }
                    for o in st.session_state.ibs_overrides
                ],
                "clinician_notes": st.session_state.ibs_notes,
            },
        }

        if st.button("💾 Save this output", key="ibs_save_output"):
            st.session_state.ibs_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": full_output,
            }
            st.success("Output saved for this session.")

        if "ibs_saved_output" in st.session_state:
            md_text = build_ibs_markdown(
                patient_data=patient_data,
                outputs=outputs,
                overrides=st.session_state.ibs_overrides,
                notes=st.session_state.ibs_notes,
            )
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="ibs_summary.md",
                mime="text/markdown",
                key="ibs_download_md",
            )

        # ── OVERRIDES ─────────────────────────────────────────────────────────
        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                st.caption(
                    "Override engine decisions where clinical judgement differs. "
                    "A documented reason is required for each override."
                )

                unique_override_candidates = []
                seen = set()
                for a in override_candidates:
                    opt = getattr(a, "override_options", None)
                    if not opt:
                        continue
                    key = (opt.get("node"), opt.get("field"))
                    if key in seen:
                        continue
                    seen.add(key)
                    unique_override_candidates.append(a)

                for a in unique_override_candidates:
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
                            (o for o in st.session_state.ibs_overrides if o.target_node == raw_node and o.field == raw_field),
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
                                    st.session_state.ibs_overrides = [
                                        o for o in st.session_state.ibs_overrides
                                        if not (o.target_node == raw_node and o.field == raw_field)
                                    ]
                                    st.session_state.ibs_overrides.append(
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
                                st.session_state.ibs_overrides = [
                                    o for o in st.session_state.ibs_overrides
                                    if not (o.target_node == raw_node and o.field == raw_field)
                                ]
                                st.success("Override removed.")

                if st.session_state.ibs_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.ibs_overrides:
                        st.markdown(
                            '<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code>'
                            f' set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span><br>'
                            f'<span style="color:#64748b;font-size:11px">Applied: {o.created_at.strftime("%H:%M:%S")}</span>'
                            '</div>',
                            unsafe_allow_html=True,
                        )

        # ── AUDIT LOG ─────────────────────────────────────────────────────────
        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                try:
                    ts = datetime.fromisoformat(log.timestamp).strftime("%H:%M:%S")
                except Exception:
                    ts = "—"
                st.markdown(f"**[{ts}] {log.node}** → _{log.decision}_")
                if getattr(log, "used_inputs", None):
                    st.caption("  ".join(f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None))
