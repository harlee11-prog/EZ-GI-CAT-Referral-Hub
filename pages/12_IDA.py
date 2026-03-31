import os
import sys
import html
import io
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Import the IDA engine components
try:
    from ida_engine import run_ida_pathway, Action, DataRequest, Stop, Override
except ImportError:
    st.error("Engine module 'ida_engine.py' not found. Ensure it is in the same directory.")
    st.stop()

st.set_page_config(page_title="IDA Pathway", layout="wide")

# ── MARKDOWN / SUMMARY HELPERS ──────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_ida_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Iron Deficiency Anemia (IDA) Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Age / Sex:** {_safe_text(patient_data.get('age'))} / {_safe_text(patient_data.get('sex')).capitalize()}")
    lines.append(f"- **Hemoglobin:** {_safe_text(patient_data.get('hemoglobin'))} g/L (Baseline: {_safe_text(patient_data.get('baseline_hemoglobin')) or 'N/A'})")
    lines.append(f"- **Ferritin:** {_safe_text(patient_data.get('ferritin'))} ug/L")
    lines.append(f"- **Inflammation Present:** {_safe_text(patient_data.get('inflammation_present'))}")
    lines.append(f"- **Celiac TTG Positive:** {_safe_text(patient_data.get('ttg_positive'))}")
    lines.append(f"- **High-Risk Rectal Bleeding Features:** {_safe_text(patient_data.get('rectal_bleeding_visible'))}")
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
                    for k, v in o.details.items():
                        if k not in ["supported_by"] and v not in (None, False, "", []):
                            if isinstance(v, list):
                                for item in v:
                                    lines.append(f"  - {_safe_text(k).replace('_', ' ').title()}: {_safe_text(item)}")
                            else:
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
.action-card.semi_urgent { background:#3f2a04; border-left:5px solid #f97316; color:#fed7aa; }
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
.badge.semi_urgent { background:#f97316; color:#fff; }
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

st.title("Iron Deficiency Anemia (IDA) Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "ida_overrides" not in st.session_state:
    st.session_state.ida_overrides = []

if "ida_has_run" not in st.session_state:
    st.session_state.ida_has_run = False

if "ida_notes" not in st.session_state:
    st.session_state.ida_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL: PATIENT INPUTS ───────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    
    col_a, col_b = st.columns(2)
    with col_a:
        age = st.number_input("Age", 1, 120, 50)
    with col_b:
        sex = st.selectbox("Sex", ["male", "female"])

    st.markdown("**1. Signs of IDA & Baseline Labs**")
    hb = st.number_input("Hemoglobin (g/L)", 1.0, 250.0, 115.0)
    ferritin = st.number_input("Ferritin (ug/L)", 1.0, 2000.0, 15.0)
    
    col_c, col_d = st.columns(2)
    with col_c:
        baseline_hb = st.number_input("Baseline Hb (Optional)", 0.0, 250.0, 0.0)
    with col_d:
        tsat = st.number_input("TSAT % (Optional)", 0.0, 100.0, 0.0)

    inflammation = st.checkbox("Active inflammation / infection / IBD")
    ckd = st.checkbox("Significant Chronic Kidney Disease")
    
    st.markdown("**2a. Celiac Disease Evaluation**")
    prior_biopsy = st.checkbox("Prior normal duodenal biopsy documented")
    ttg_years = st.number_input("Years since last TTG test", 0.0, 50.0, 0.0, step=0.5)
    ttg_sel = st.selectbox("TTG Result", ["Unknown", "Negative", "Positive"])
    ttg_map = {"Unknown": None, "Negative": False, "Positive": True}
    
    celiac_duration = st.number_input("Celiac duration (months)", 0, 600, 0) if ttg_map[ttg_sel] else 0
    gfd_compliant = st.checkbox("Compliant with Gluten-Free Diet") if ttg_map[ttg_sel] else False
    
    if sex == "female":
        st.markdown("**2b. Gynecology Evaluation**")
        menstruating = st.checkbox("Currently menstruating", value=True)
        hysterectomy = st.checkbox("Prior hysterectomy")
        anemia_out = st.checkbox("Anemia out of keeping with menstrual loss")
    else:
        menstruating, hysterectomy, anemia_out = None, None, None

    st.markdown("**3. High Risk Rectal Bleeding Features**")
    rectal_vis = st.selectbox("Visible blood in/on stool/toilet?", ["Unknown", "Yes", "No"])
    rectal_vis_map = {"Unknown": None, "Yes": True, "No": False}
    if rectal_vis_map[rectal_vis]:
        rectal_new = st.checkbox("New onset or worsening")
        rectal_freq = st.checkbox("Present most days of the week")
        rectal_dur = st.number_input("Duration of bleeding (weeks)", 0, 520, 3)
    else:
        rectal_new, rectal_freq, rectal_dur = None, None, None

    st.markdown("**4. Investigation & Medical History**")
    scope_2y_sel = st.selectbox("Complete colonoscopy in last 2 years?", ["Unknown", "Yes", "No"])
    scope_2y_map = {"Unknown": None, "Yes": True, "No": False}
    
    alarm_inv_sel = st.selectbox("Alarm features investigated by lower endoscopy in last 2 years?", ["Unknown", "Yes", "No", "Not Applicable"])
    alarm_inv_map = {"Unknown": None, "Yes": True, "No": False, "Not Applicable": None}

    st.markdown("**5. Alarm Symptoms & Modifiers**")
    alarm_diarrhea = st.checkbox("Significant diarrhea (e.g., IBD context)")
    alarm_weight = st.checkbox("Unintentional weight loss (≥ 5-10% over 6 mo)")
    alarm_bowel = st.checkbox("Progressive change in bowel habit")
    alarm_pain = st.checkbox("Significant abdominal pain")
    
    mod_nocturnal = st.checkbox("Nocturnal symptoms")
    mod_fh_crc = st.checkbox("First-degree family history of CRC")
    mod_fh_ibd = st.checkbox("First-degree family history of IBD")
    mod_gi_bleed = st.checkbox("Evidence of GI bleeding (other than specific rectal features)")

    st.markdown("**6. Physical Exam & Medications**")
    rectal_exam = st.checkbox("Rectal exam completed")
    anticoag = st.checkbox("Taking anticoagulants")
    antiplate = st.checkbox("Taking antiplatelet agents")
    nsaid = st.checkbox("Taking NSAIDs chronically")
    fit_planned = st.checkbox("FIT ordered or planned")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.ida_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.ida_overrides = []
        if "ida_saved_output" in st.session_state:
            del st.session_state["ida_saved_output"]
        st.rerun()

    override_panel = st.container()

# ── RIGHT PANEL: RESULTS & FLOWCHART ─────────────────────────────────────────
with right:
    if st.session_state.ida_has_run:
        # Construct expected data dictionary
        patient_data = {
            "age": age,
            "sex": sex,
            "hemoglobin": hb,
            "baseline_hemoglobin": baseline_hb if baseline_hb > 0 else None,
            "ferritin": ferritin,
            "inflammation_present": inflammation,
            "transferrin_saturation": tsat if tsat > 0 else None,
            "chronic_kidney_disease": ckd,
            "prior_duodenal_biopsy_normal": prior_biopsy,
            "ttg_years_since_test": ttg_years,
            "ttg_positive": ttg_map[ttg_sel],
            "celiac_duration_months": celiac_duration,
            "gluten_free_compliant": gfd_compliant,
            "menstruating": menstruating,
            "hysterectomy": hysterectomy,
            "anemia_out_of_keeping_with_menses": anemia_out,
            "rectal_bleeding_visible": rectal_vis_map[rectal_vis],
            "rectal_bleeding_new_or_worsening": rectal_new,
            "rectal_bleeding_most_days": rectal_freq,
            "rectal_bleeding_duration_weeks": rectal_dur,
            "complete_colonoscopy_within_2y": scope_2y_map[scope_2y_sel],
            "alarm_features_investigated_by_lower_endoscopy_within_2y": alarm_inv_map[alarm_inv_sel],
            "significant_diarrhea": alarm_diarrhea,
            "weight_loss": alarm_weight,
            "progressive_bowel_change": alarm_bowel,
            "significant_abdominal_pain": alarm_pain,
            "nocturnal_symptoms": mod_nocturnal,
            "family_history_crc_first_degree": mod_fh_crc,
            "family_history_ibd_first_degree": mod_fh_ibd,
            "evidence_of_gi_bleeding": mod_gi_bleed,
            "rectal_exam_done": rectal_exam,
            "anticoagulants": anticoag,
            "antiplatelets": antiplate,
            "nsaid_use": nsaid,
            "fit_ordered_or_planned": fit_planned
        }

        outputs, logs, applied_overrides = run_ida_pathway(
            patient_data, overrides=st.session_state.ida_overrides
        )

        # Map logs for SVG display
        visited_nodes = {log.node for log in logs}
        
        # SVG Configuration
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_SEMI = "#f97316"; C_EXIT = "#d97706"
        C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

        def nc(vis, urgent=False, semi=False, exit_=False):
            if not vis: return C_UNVISIT
            if urgent: return C_URGENT
            if semi: return C_SEMI
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
        W, H = 700, 1050
        svg.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" '
            f'viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">'
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
            "start": 20, "confirm_ida": 110, "urgency": 220,
            "celiac": 340, "gyne": 460, "hrrb": 580,
            "finalize": 720, "end": 850
        }

        # Flow logic evaluation
        v_ida = "Confirm_IDA" in visited_nodes
        ida_pass = v_ida and patient_data.get("hemoglobin") and patient_data.get("ferritin") and patient_data.get("sex") and not any(isinstance(o, Stop) and "IDA not confirmed" in o.reason for o in outputs)
        
        v_urgency = "Urgency_Triage" in visited_nodes
        v_celiac = "Celiac_RuleOut" in visited_nodes
        v_gyne = "Gynecology_Check" in visited_nodes
        v_hrrb = "HighRiskRectalBleeding_Check" in visited_nodes
        v_fin = "Finalize" in visited_nodes
        
        # Determine exit criteria explicitly from logs and outputs
        ida_stop = v_ida and not ida_pass
        celiac_manage = v_celiac and any(isinstance(o, Action) and o.code == "CELIAC_POSITIVE_MANAGE" for o in outputs)
        gyne_trial = v_gyne and any(isinstance(o, Action) and o.code == "TRIAL_IRON" for o in outputs)
        hrrb_route = v_hrrb and any(isinstance(o, Stop) and o.reason.startswith("High-risk rectal bleeding present") for o in outputs)

        rect_node(CX-NW/2, Y["start"], NW, NH, nc(True), "Patient Presents", "Suspected IDA")
        vline(CX, Y["start"]+NH, Y["confirm_ida"], True)
        
        diamond_node(CX, Y["confirm_ida"]+DH/2, DW, DH, dc(v_ida), "1. Confirm IDA", "(Low Hb + Ferritin)")
        exit_node(LEXT, Y["confirm_ida"]+(DH-EH)/2, EW, EH, nc(ida_stop, exit_=True), "Investigate Non-IDA", "Alternative Anemia")
        elbow_line(CX-DW/2, Y["confirm_ida"]+DH/2, LEXT+EW, Y["confirm_ida"]+(DH-EH)/2+EH/2, ida_stop, exit_=True, label="No")

        vline(CX, Y["confirm_ida"]+DH, Y["urgency"], ida_pass, label="Yes")
        diamond_node(CX, Y["urgency"]+DH/2, DW, DH, dc(v_urgency), "2. Urgency Triage", "Alarm / Modifiers")

        vline(CX, Y["urgency"]+DH, Y["celiac"], v_celiac)
        diamond_node(CX, Y["celiac"]+DH/2, DW, DH, dc(v_celiac), "3. Rule Out", "Celiac Disease")
        exit_node(REXT, Y["celiac"]+(DH-EH)/2, EW, EH, nc(celiac_manage, exit_=True), "Manage Celiac", "Hold Referral")
        elbow_line(CX+DW/2, Y["celiac"]+DH/2, REXT, Y["celiac"]+(DH-EH)/2+EH/2, celiac_manage, exit_=True, label="TTG+ (Not Longstanding)")

        v_after_celiac = v_celiac and not celiac_manage and v_gyne
        vline(CX, Y["celiac"]+DH, Y["gyne"], v_after_celiac)
        diamond_node(CX, Y["gyne"]+DH/2, DW, DH, dc(v_gyne), "4. Gynecology", "Check (Females)")
        exit_node(LEXT, Y["gyne"]+(DH-EH)/2, EW, EH, nc(gyne_trial, exit_=True), "Trial Iron", "Menses Proportional")
        elbow_line(CX-DW/2, Y["gyne"]+DH/2, LEXT+EW, Y["gyne"]+(DH-EH)/2+EH/2, gyne_trial, exit_=True, label="Yes")

        v_after_gyne = v_gyne and not gyne_trial and v_hrrb
        vline(CX, Y["gyne"]+DH, Y["hrrb"], v_after_gyne)
        diamond_node(CX, Y["hrrb"]+DH/2, DW, DH, dc(v_hrrb), "5. High-Risk", "Rectal Bleeding?")
        exit_node(REXT, Y["hrrb"]+(DH-EH)/2, EW, EH, nc(hrrb_route, urgent=True), "Route HRRB", "Diagnostic Pathway")
        elbow_line(CX+DW/2, Y["hrrb"]+DH/2, REXT, Y["hrrb"]+(DH-EH)/2+EH/2, hrrb_route, urgent=True, label="Yes")

        v_after_hrrb = v_hrrb and not hrrb_route and v_fin
        vline(CX, Y["hrrb"]+DH, Y["finalize"], v_after_hrrb)
        rect_node(CX-NW/2, Y["finalize"], NW, NH, nc(v_fin), "Assess Triage", "Modifiers & Readiness")

        final_referral = any(isinstance(o, Action) and o.code == "REFER_ENDOSCOPY" for o in outputs)
        final_urgency = "routine"
        for o in outputs:
            if isinstance(o, Action) and o.code == "ASSIGN_URGENCY":
                final_urgency = o.urgency

        v_complete = v_fin and final_referral
        vline(CX, Y["finalize"]+NH, Y["end"], v_complete)
        rect_node(CX-NW/2, Y["end"], NW, NH, nc(v_complete, urgent=(final_urgency == "urgent"), semi=(final_urgency == "semi_urgent")), "Pathway Complete", f"Referral: {final_urgency.replace('_', ' ').title()}")

        ly = H - 22; lx = 18
        for col, lbl in [
            (C_MAIN, "Visited"), (C_DIAMOND, "Decision"),
            (C_URGENT, "Urgent"), (C_SEMI, "Semi-Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached")
        ]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 105
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            f'<div style="background:{C_BG};padding:10px;border-radius:14px;overflow-x:auto">{"".join(svg)}</div>',
            height=1080, scrolling=True
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Context Card
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="ctx-card">'
            f'<span><b>Age / Sex:</b> {age} / {sex.capitalize()}</span><br>'
            f'<span><b>Hb & Ferritin:</b> {hb} g/L &nbsp;|&nbsp; {ferritin} ug/L</span><br>'
            f'<span><b>Active Inflammation/CKD:</b> {"Yes" if inflammation or ckd else "No"}</span><br>'
            f'<span><b>Celiac TTG Positive:</b> {ttg_sel}</span><br>'
            f'<span><b>Visible Rectal Bleeding:</b> {rectal_vis}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        override_candidates = []

        def _detail_html(details) -> str:
            if not details: return ""
            items = ""
            if isinstance(details, dict):
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                for k, v in details.items():
                    if k not in ["supported_by"] and v not in (None, False, "", []):
                        if isinstance(v, list):
                            items += "".join(f"<li>{html.escape(str(i))}</li>" for i in v)
                        else:
                            items += f"<li><b>{html.escape(str(k)).replace('_', ' ').title()}:</b> {html.escape(str(v))}</li>"
            return f'<ul style="margin:6px 0 0 16px;padding:0">{items}</ul>' if items else ""

        def render_action(a: Action, extra_cls: str = "") -> None:
            urgency_to_cls = {
                "urgent": "urgent", "semi_urgent": "semi_urgent", "warning": "warning",
                "routine": "routine", None: "info", "": "info"
            }
            cls = urgency_to_cls.get(a.urgency or "", "info")
            if extra_cls: cls = extra_cls

            badge_label = (a.urgency or "info").upper().replace("_", " ")
            label_html = html.escape(a.label).replace("\n", "<br>")
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
                reason_html = html.escape(output.reason).replace("\n", "<br>")
                st.markdown(
                    f'<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span> 🛑 {reason_html}</h4>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                for a in output.actions:
                    render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.session_state.ida_notes = st.text_area("Notes to attach to the saved output:", value=st.session_state.ida_notes, height=180)

        if st.button("💾 Save this output", key="ida_save_output"):
            st.session_state.ida_saved_output = {
                "saved_at": datetime.now().isoformat(),
                "payload": {"patient_context": patient_data, "notes": st.session_state.ida_notes}
            }
            st.success("Output saved for this session.")

        if "ida_saved_output" in st.session_state:
            md_text = build_ida_markdown(patient_data, outputs, st.session_state.ida_overrides, st.session_state.ida_notes)
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="ida_pathway_summary.md",
                mime="text/markdown",
                key="ida_download_md",
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
                        st.markdown(f'<div class="override-card">Engine decision based on: <b>{html.escape(a.label)}</b></div>', unsafe_allow_html=True)
                        existing = next((o for o in st.session_state.ida_overrides if o.target_node == raw_node and o.field == raw_field), None)
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
                                    st.error("A reason is required.")
                                else:
                                    st.session_state.ida_overrides = [o for o in st.session_state.ida_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.ida_overrides.append(Override(target_node=raw_node, field=raw_field, old_value=None, new_value=new_val, reason=reason.strip()))
                                    st.success("Applied. Re-run pathway.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.ida_overrides = [o for o in st.session_state.ida_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Removed.")

                if st.session_state.ida_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.ida_overrides:
                        st.markdown(
                            f'<div class="override-card">'
                            f'🛠 <b>{html.escape(_pretty(o.target_node))}</b> → <code>{html.escape(_pretty(o.field))}</code> set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span></div>',
                            unsafe_allow_html=True,
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
