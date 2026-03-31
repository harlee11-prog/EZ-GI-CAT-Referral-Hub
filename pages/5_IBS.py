import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Import from the IBS engine module
from ibs_engine import (
    run_ibs_pathway, Action, DataRequest, Stop, Override,
)

# Empty dict to satisfy the regimen UI logic if expanded later
REGIMEN_DETAILS = {}

st.set_page_config(page_title="IBS Pathway", page_icon="🦠", layout="wide")

# ── MARKDOWN / PDF HELPERS ──────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_ibs_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# IBS Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    skip_keys = {"cbc_done", "ferritin_done", "celiac_screen_done"}
    for k, v in patient_data.items():
        if k in skip_keys or v is None:
            continue
        label = k.replace("_", " ").capitalize()
        lines.append(f"- **{label}:** {_safe_text(v)}")
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

st.title("🦠 IBS Pathway")
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
    def yn_map(val):
        if val == "Yes": return True
        if val == "No": return False
        return None

    st.subheader("Patient Information")
    age = st.number_input("Age", 1, 120, 52)
    sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. IBS Diagnostic Criteria (Rome IV)**")
    pain_days = st.number_input("Abdominal pain days per week", min_value=0, max_value=7, value=None)
    months = st.number_input("Symptom months present", min_value=0, max_value=120, value=None)
    related = yn_map(st.selectbox("Pain related to defecation?", ["Select...", "Yes", "No"]))
    freq_change = yn_map(st.selectbox("Pain associated with change in stool frequency?", ["Select...", "Yes", "No"]))
    form_change = yn_map(st.selectbox("Pain associated with change in stool form?", ["Select...", "Yes", "No"]))

    st.markdown("**2. Baseline Investigations**")
    cbc = yn_map(st.selectbox("CBC done?", ["Select...", "Yes", "No"]))
    ferritin = yn_map(st.selectbox("Ferritin done?", ["Select...", "Yes", "No"]))
    celiac = yn_map(st.selectbox("Celiac screen done?", ["Select...", "Yes", "No"]))
    celiac_pos = st.checkbox("Celiac screen positive", disabled=not celiac)

    st.markdown("**3. Alarm Features**")
    fh_crc = st.checkbox("Family history (1st degree) of CRC")
    fh_ibd = st.checkbox("Family history (1st degree) of IBD")
    age_50 = st.checkbox("Symptom onset after age 50")
    blood = st.checkbox("Visible blood in stool")
    nocturnal = st.checkbox("Nocturnal symptoms")
    ida = st.checkbox("Iron deficiency anemia")
    weight_loss = st.number_input("Unintended weight loss % (6-12 months)", min_value=0.0, max_value=100.0, value=0.0)

    st.markdown("**4. Stool Form (Bristol)**")
    hard = st.number_input("% Hard stools (Types 1-2)", min_value=0, max_value=100, value=None)
    loose = st.number_input("% Loose stools (Types 6-7)", min_value=0, max_value=100, value=None)

    st.markdown("**6. & 7. Advanced Screening**")
    high_ibd = yn_map(st.selectbox("High clinical suspicion of IBD?", ["Select...", "Yes", "No"]))
    if high_ibd:
        calprotectin = st.number_input("Fecal calprotectin (ug/g)", min_value=0, value=None)
    else:
        calprotectin = None

    st.markdown("**8. Management Follow-up**")
    unsatisfactory = yn_map(st.selectbox("Unsatisfactory response to treatment?", ["Select...", "Yes", "No"]))

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
    if st.session_state.ibs_has_run:
        patient_data = {
            "abdominal_pain_days_per_week": pain_days,
            "symptom_months_present": months,
            "pain_related_to_defecation": related,
            "pain_with_change_in_stool_frequency": freq_change,
            "pain_with_change_in_stool_form": form_change,
            "cbc_done": cbc,
            "ferritin_done": ferritin,
            "celiac_screen_done": celiac,
            "celiac_screen_positive": celiac_pos,
            "family_history_crc_first_degree": fh_crc,
            "family_history_ibd_first_degree": fh_ibd,
            "symptom_onset_after_age_50": age_50,
            "visible_blood_in_stool": blood,
            "nocturnal_symptoms": nocturnal,
            "iron_deficiency_anemia_present": ida,
            "unintended_weight_loss_percent_6_to_12_months": weight_loss,
            "hard_stool_percent": hard,
            "loose_stool_percent": loose,
            "high_suspicion_ibd": high_ibd,
            "fecal_calprotectin_ug_g": calprotectin,
            "unsatisfactory_response_to_treatment": unsatisfactory,
        }

        outputs, logs, applied_overrides = run_ibs_pathway(
            patient_data, overrides=st.session_state.ibs_overrides
        )

        # Pre-compute layout logic based on engine node conditions
        feature_count = sum([1 for f in [related, freq_change, form_change] if f is True])
        ibs_criteria = (pain_days is not None and pain_days >= 1) and (months is not None and months >= 3) and (feature_count >= 2)
        missing_base = (cbc is None or ferritin is None or celiac is None)
        alarm_present = any([fh_crc, fh_ibd, age_50, blood, nocturnal, ida, weight_loss > 5.0])
        missing_subtype = hard is None or loose is None
        missing_ibd = high_ibd is None
        missing_cal = high_ibd and calprotectin is None
        high_cal = calprotectin is not None and calprotectin > 120
        missing_resp = unsatisfactory is None

        # SVGs Layout
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
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')
        svg.append("<defs>")
        svg.append('<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>')
        svg.append('<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>')
        svg.append('<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>')
        svg.append('<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>')
        svg.append("</defs>")

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
        Y = {
            "present": 18, "d_crit": 100, "d_base": 202,
            "d_alarm": 304, "d_sub": 406, "d_ibd": 508,
            "d_cal": 610, "d_resp": 712, "complete": 814,
        }

        rect_node(CX-NW/2, Y["present"], NW, NH, nc(True), "Suspected IBS")
        vline(CX, Y["present"]+NH, Y["d_crit"], True)
        
        # 1. Criteria
        diamond_node(CX, Y["d_crit"]+DH/2, DW, DH, dc(True), "1. Rome IV Criteria", "Met?")
        exit_node(LEXT, Y["d_crit"]+(DH-EH)/2, EW, EH, nc(not ibs_criteria, exit_=True), "Criteria Not Met", "Stop Pathway")
        elbow_line(CX-DW/2, Y["d_crit"]+DH/2, LEXT+EW, Y["d_crit"]+(DH-EH)/2+EH/2, not ibs_criteria, exit_=True, label="No")

        # 2. Baseline
        v_base = ibs_criteria
        vline(CX, Y["d_crit"]+DH, Y["d_base"], v_base, label="Yes")
        diamond_node(CX, Y["d_base"]+DH/2, DW, DH, dc(v_base), "2. Baseline", "Investigations?")
        exit_node(REXT, Y["d_base"]+(DH-EH)/2, EW, EH, nc(v_base and celiac_pos, urgent=True), "Celiac Positive", "Refer GI")
        elbow_line(CX+DW/2, Y["d_base"]+DH/2, REXT, Y["d_base"]+(DH-EH)/2+EH/2, v_base and celiac_pos, urgent=True, label="Pos")

        # 3. Alarm
        v_alarm = v_base and not celiac_pos and not missing_base
        vline(CX, Y["d_base"]+DH, Y["d_alarm"], v_alarm, label="Complete")
        diamond_node(CX, Y["d_alarm"]+DH/2, DW, DH, dc(v_alarm), "3. Alarm", "Features?")
        exit_node(REXT, Y["d_alarm"]+(DH-EH)/2, EW, EH, nc(v_alarm and alarm_present, urgent=True), "Urgent Refer", "Endoscopy")
        elbow_line(CX+DW/2, Y["d_alarm"]+DH/2, REXT, Y["d_alarm"]+(DH-EH)/2+EH/2, v_alarm and alarm_present, urgent=True, label="Yes")

        # 4. Subtype
        v_sub = v_alarm and not alarm_present
        vline(CX, Y["d_alarm"]+DH, Y["d_sub"], v_sub, label="No")
        rect_node(CX-NW/2, Y["d_sub"], NW, NH, nc(v_sub), "4. & 5. IBS Subtype", sub="Determine & Treat")

        # 6. IBD Check
        v_ibd = v_sub and not missing_subtype
        vline(CX, Y["d_sub"]+NH, Y["d_ibd"], v_ibd)
        diamond_node(CX, Y["d_ibd"]+DH/2, DW, DH, dc(v_ibd), "6. Suspicion", "of IBD?")

        # 7. Fecal Calprotectin
        v_cal = v_ibd and high_ibd
        vline(CX, Y["d_ibd"]+DH, Y["d_cal"], v_cal, label="Yes")
        diamond_node(CX, Y["d_cal"]+DH/2, DW, DH, dc(v_cal), "7. Fecal Calprotectin", "> 120 ug/g?")
        exit_node(REXT, Y["d_cal"]+(DH-EH)/2, EW, EH, nc(v_cal and high_cal, urgent=True), "Elevated FCP", "Refer GI")
        elbow_line(CX+DW/2, Y["d_cal"]+DH/2, REXT, Y["d_cal"]+(DH-EH)/2+EH/2, v_cal and high_cal, urgent=True, label="Yes")

        # Bypass rendering for "No" High IBD to Response
        v_resp_from_ibd = v_ibd and not missing_ibd and not high_ibd
        if v_resp_from_ibd:
            svg.append(f'<polyline points="{CX-DW/2},{Y["d_ibd"]+DH/2} {CX-DW/2-40},{Y["d_ibd"]+DH/2} {CX-DW/2-40},{Y["d_resp"]} {CX},{Y["d_resp"]}" fill="none" stroke="{C_MAIN}" stroke-width="2" marker-end="url(#mg)"/>')
            svgt(CX-DW/2-20, Y["d_ibd"]+DH/2-5, "No", C_MAIN, 10, True)
        elif not v_ibd:
            svg.append(f'<polyline points="{CX-DW/2},{Y["d_ibd"]+DH/2} {CX-DW/2-40},{Y["d_ibd"]+DH/2} {CX-DW/2-40},{Y["d_resp"]} {CX},{Y["d_resp"]}" fill="none" stroke="{C_UNVISIT}" stroke-width="2" stroke-dasharray="5,3" marker-end="url(#ma)"/>')
            svgt(CX-DW/2-20, Y["d_ibd"]+DH/2-5, "No", C_UNVISIT, 10, True)

        v_resp_from_cal = v_cal and not missing_cal and not high_cal
        if v_cal:
            vline(CX, Y["d_cal"]+DH, Y["d_resp"], v_resp_from_cal, label="No")
        else:
            vline(CX, Y["d_cal"]+DH, Y["d_resp"], False)

        # 8. Management Response
        v_resp = v_resp_from_ibd or v_resp_from_cal
        diamond_node(CX, Y["d_resp"]+DH/2, DW, DH, dc(v_resp), "8. Treatment", "Response?")
        exit_node(REXT, Y["d_resp"]+(DH-EH)/2, EW, EH, nc(v_resp and unsatisfactory, exit_=True), "Unsatisfactory", "Advice Service")
        elbow_line(CX+DW/2, Y["d_resp"]+DH/2, REXT, Y["d_resp"]+(DH-EH)/2+EH/2, v_resp and unsatisfactory, exit_=True, label="Unsatisfactory")

        # Complete
        v_comp = v_resp and not missing_resp and not unsatisfactory
        vline(CX, Y["d_resp"]+DH, Y["complete"], v_comp, exit_=v_comp, label="Satisfactory")
        rect_node(CX-NW/2, Y["complete"], NW, NH, nc(v_comp, exit_=v_comp), "Pathway Complete", sub="Medical Home Management")

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
            height=980, scrolling=True,
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        alarm_fields = [
            ("family_history_crc_first_degree", "Family hx CRC"),
            ("family_history_ibd_first_degree", "Family hx IBD"),
            ("symptom_onset_after_age_50", "Onset > 50yrs"),
            ("visible_blood_in_stool", "Visible blood"),
            ("nocturnal_symptoms", "Nocturnal symptoms"),
            ("iron_deficiency_anemia_present", "IDA"),
        ]
        active_alarms = [label for key, label in alarm_fields if patient_data.get(key)]
        if patient_data.get("unintended_weight_loss_percent_6_to_12_months", 0) > 5.0:
            active_alarms.append("Weight loss > 5%")
            
        alarm_str = ", ".join(active_alarms) if active_alarms else "None"
        crit_met = "Yes" if ibs_criteria else "No/Unknown"

        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Criteria Met:</b> {crit_met}</span><br>'
            f'<span><b>Alarm Features:</b> {alarm_str}</span>'
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
                skip = {"bullets", "notes", "supported_by", "regimen_key"}
                for k, v in details.items():
                    if k in skip: continue
                    if isinstance(v, list) and v:
                        items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                    elif v not in (None, False, "", []):
                        items += f"<li><b>{html.escape(str(k))}:</b> {html.escape(str(v))}</li>"
            elif isinstance(details, list):
                items = "".join(f"<li>{html.escape(str(d))}</li>" for d in details if str(d).strip())
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {
                "urgent": "urgent", "warning": "warning",
                None: "routine", "": "routine",
            }
            cls = urgency_to_cls.get(a.urgency or "", "routine")
            if extra_cls: cls = extra_cls

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
        st.session_state.ibs_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.ibs_notes,
            height=180,
        )

        full_output = {
            "patient_context": patient_data,
            "clinical_recommendations": {
                "engine_outputs": [{"type": type(o).__name__} for o in outputs],
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
                        st.markdown(
                            f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>',
                            unsafe_allow_html=True,
                        )
                        existing = next(
                            (o for o in st.session_state.ibs_overrides
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
                        "  ".join(
                            f"`{k}={v}`" for k, v in log.used_inputs.items() if v is not None
                        )
                    )
    else:
        st.info("Fill in patient details on the left, then click **▶ Run Pathway**.")
