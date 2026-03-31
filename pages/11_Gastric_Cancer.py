import os, sys
import html
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

# Import engine dependencies
from gastric_cancer_engine import (
    run_gastric_cancer_pathway, Action, DataRequest, Stop, Override
)

st.set_page_config(page_title="Gastric Cancer", page_icon="🎗️", layout="wide")

# ── MARKDOWN HELPERS ────────────────────────────────────────────────────────
def _safe_text(text) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\u00a0", " ").split())

def build_gc_markdown(patient_data, outputs, overrides, notes: str) -> str:
    lines = []
    lines.append("# Gastric Cancer Pathway - Clinical Summary")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Pathway Context:** {_safe_text(patient_data.get('patient_context')).replace('_', ' ').title()}")
    lines.append(f"- **Age:** {_safe_text(patient_data.get('age')) or 'Unknown'}")
    lines.append(f"- **Asymptomatic:** {_safe_text(patient_data.get('asymptomatic'))}")
    lines.append(f"- **Dyspepsia >1 month:** {_safe_text(patient_data.get('symptomatic_dyspepsia_over_1_month'))}")
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
                        if k in skip: continue
                        if isinstance(v, list):
                            for item in v:
                                lines.append(f"  - {_safe_text(item)}")
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

st.title("🎗️ Gastric Cancer Pathway")
st.markdown("---")

# ── SESSION STATE ────────────────────────────────────────────────────────────
if "gc_overrides" not in st.session_state:
    st.session_state.gc_overrides = []
if "gc_has_run" not in st.session_state:
    st.session_state.gc_has_run = False
if "gc_notes" not in st.session_state:
    st.session_state.gc_notes = ""

left, right = st.columns([1, 1.5])

# ── LEFT PANEL ───────────────────────────────────────────────────────────────
with left:
    st.subheader("Patient Information")
    
    context_sel = st.radio(
        "Pathway Context",
        ["Primary Prevention", "Targeted Screening (Asymptomatic)", "Symptomatic Dyspepsia"]
    )
    ctx_map = {
        "Primary Prevention": "prevention",
        "Targeted Screening (Asymptomatic)": "asymptomatic_screening",
        "Symptomatic Dyspepsia": "symptomatic_dyspepsia"
    }
    
    st.markdown("**Demographics**")
    age = st.number_input("Age", 1, 120, 52)
    
    st.markdown("**Prevention & Screening Risk Factors**")
    from_endemic = st.checkbox("Immigrant from high-risk region (East Asia, E. Europe, Central/South America)")
    family_origin = st.checkbox("Family origins in endemic region")
    hh_hp_positive = st.checkbox("Household member H. pylori positive")
    
    fh_gastric = st.checkbox("1st-degree relative with gastric cancer")
    fh_age = st.number_input("Age of relative at diagnosis (if applicable)", 0, 120, 0)
    
    hereditary_synd = st.checkbox("Hereditary GI polyposis or cancer syndrome (e.g. FAP, Lynch)")
    chronic_hp = st.checkbox("Chronic H. pylori infection")
    
    pack_years = st.number_input("Smoking Pack Years", 0, 150, 0)
    high_risk_diet = st.checkbox("High salt, red/processed meat diet")
    low_ses = st.checkbox("Low socioeconomic status")
    
    st.markdown("**Symptomatic & Alarm Features**")
    dyspepsia_1mo = st.checkbox("Dyspepsia symptoms > 1 month")
    
    al_fh_cancer = st.checkbox("Family history (1st degree) esophageal or gastric cancer")
    al_onset_60 = st.checkbox("Age > 60 with new and persistent symptoms")
    al_wt_loss = st.checkbox("Unintended weight loss (≥5%)")
    al_bleed = st.checkbox("Black stool or blood in vomit")
    al_dysphagia = st.checkbox("Progressive dysphagia")
    al_vomit = st.checkbox("Persistent vomiting")
    al_ida = st.checkbox("Iron deficiency anemia")
    al_imaging = st.checkbox("Concerning imaging for gastric cancer")
    
    st.markdown("**Management Response**")
    unsat_mgmt = st.checkbox("Unsatisfactory response to symptomatic management")
    advice_considered = st.checkbox("Specialist advice service considered")

    run_clicked = st.button("▶ Run Pathway", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.gc_has_run = True

    if st.button("🔄 Clear Overrides", use_container_width=True):
        st.session_state.gc_overrides = []
        if "gc_saved_output" in st.session_state:
            del st.session_state["gc_saved_output"]
        st.rerun()

    override_panel = st.container()


# ── RIGHT PANEL ──────────────────────────────────────────────────────────────
with right:
    if st.session_state.gc_has_run:
        
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

        # ── EXTRACT LOG STATES FOR SVG ──
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

        # ── SVG GENERATOR ──
        C_MAIN = "#16a34a"; C_UNVISIT = "#475569"; C_DIAMOND = "#1d4ed8"
        C_URGENT = "#dc2626"; C_EXIT = "#d97706"; C_TEXT = "#ffffff"; C_DIM = "#94a3b8"; C_BG = "#0f172a"

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
        W, H = 800, 680
        svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{H}" viewBox="0 0 {W} {H}" style="background:{C_BG};border-radius:12px;font-family:Arial,sans-serif">')
        svg.append("<defs>"
            '<marker id="ma" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker>'
            '<marker id="mg" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#16a34a"/></marker>'
            '<marker id="mr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dc2626"/></marker>'
            '<marker id="mo" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#d97706"/></marker>'
            "</defs>")

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

        NW, NH = 160, 50; DW, DH = 170, 58; EW, EH = 130, 46
        XC, XL, XR = 400, 200, 600
        Y_CTX = 60; Y_L1 = 180; Y_L2 = 300; Y_L3 = 420; Y_L4 = 540

        # Spine Entry
        diamond_node(XC, Y_CTX, DW, DH, dc(True), "Patient Context")

        # Right Branch - Prevention
        elbow_line(XC+DW/2, Y_CTX, XR, Y_L1-NH/2, ctx_prev, label="Prevention")
        exit_node(XR-EW/2, Y_L1-NH/2, EW, EH, nc(ctx_prev, exit_=True), "Primary Prevention", "Counseling & Actions")

        # Left Branch - Asymptomatic
        elbow_line(XC-DW/2, Y_CTX, XL, Y_L1-DH/2, ctx_asym, label="Asymptomatic")
        diamond_node(XL, Y_L1, DW, DH, dc(asym_visited), "Targeted Screening", "Risk Assessment")
        
        elbow_line(XL, Y_L1+DH/2, 90, Y_L2-EH/2, screening_no, exit_=True, label="No")
        exit_node(90-EW/2, Y_L2-EH/2, EW, EH, nc(screening_no, exit_=True), "Not Indicated")
        
        elbow_line(XL, Y_L1+DH/2, 290, Y_L2-EH/2, screening_yes, urgent=True, label="Yes")
        exit_node(290-EW/2, Y_L2-EH/2, EW, EH, nc(screening_yes, urgent=True), "Screening Endoscopy")

        # Center Branch - Symptomatic
        vline(XC, Y_CTX+DH/2, Y_L1-NH/2, ctx_symp, label="Symptomatic")
        rect_node(XC-NW/2, Y_L1-NH/2, NW, NH, nc(symp_visited), "Dyspepsia Assessment")
        
        vline(XC, Y_L1+NH/2, Y_L2-DH/2, alarm_visited)
        diamond_node(XC, Y_L2, DW, DH, dc(alarm_visited), "Alarm Features", "Present?")
        
        elbow_line(XC+DW/2, Y_L2, 580, Y_L2, alarm_yes, urgent=True, label="Yes")
        exit_node(580, Y_L2-EH/2, EW, EH, nc(alarm_yes, urgent=True), "Urgent Referral", "GI/Endoscopy")

        vline(XC, Y_L2+DH/2, Y_L3-DH/2, mgmt_visited, label="No")
        diamond_node(XC, Y_L3, DW, DH, dc(mgmt_visited), "Management Response", "Unsatisfactory?")

        elbow_line(XC, Y_L3+DH/2, 290, Y_L4-EH/2, mgmt_refer, urgent=True, label="Yes")
        exit_node(290-EW/2, Y_L4-EH/2, EW, EH, nc(mgmt_refer, exit_=True), "Refer", "Failed Management")

        elbow_line(XC, Y_L3+DH/2, 510, Y_L4-EH/2, mgmt_continue, exit_=True, label="No")
        exit_node(510-EW/2, Y_L4-EH/2, EW, EH, nc(mgmt_continue, exit_=True), "Continue Mgmt", "Primary Care")

        # Legend
        ly = H - 22; lx = 18
        for col, lbl in [(C_MAIN, "Visited"), (C_DIAMOND, "Decision"), (C_URGENT, "Urgent"), (C_EXIT, "Exit/Off-ramp"), (C_UNVISIT, "Not reached")]:
            svg.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="2" fill="{col}"/>')
            svgt(lx+16, ly, lbl, "#94a3b8", 10, anchor="start")
            lx += 110
        svg.append("</svg>")

        st.subheader("🗺️ Pathway Followed")
        components.html(
            '<div style="background:' + C_BG + ';padding:10px;border-radius:14px;overflow-x:auto">' + "".join(svg) + "</div>",
            height=700, scrolling=True
        )

        st.markdown("---")
        st.subheader("Clinical Recommendations")

        # Patient Context Display
        st.markdown('<p class="section-label">PATIENT CONTEXT</p>', unsafe_allow_html=True)
        st.markdown(
            '<div class="ctx-card">'
            f'<span><b>Pathway Target:</b> {ctx_map[context_sel].replace("_", " ").title()}</span><br>'
            f'<span><b>Age:</b> {age}</span><br>'
            f'<span><b>Pack Years:</b> {pack_years}</span>'
            "</div>",
            unsafe_allow_html=True
        )

        override_candidates = []

        def _detail_html(details) -> str:
            if not details: return ""
            items = ""
            if isinstance(details, dict):
                for src in details.get("supported_by", []):
                    items += f"<li>📌 {html.escape(str(src))}</li>"
                skip = {"bullets", "notes", "supported_by"}
                for k, v in details.items():
                    if k in skip: continue
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
            label_html = html.escape(a.label).replace("\n", "<br>")
            detail_html = _detail_html(a.details)
            override_html = (
                '<p style="margin:6px 0 0;font-size:11px;color:#a5b4fc">🔒 Override available — reason required</p>'
                if a.override_options else ""
            )

            st.markdown(
                f'<div class="action-card {cls}">'
                f'<h4><span class="badge {cls}">{badge_label}</span> {label_html}</h4>'
                f"{detail_html}{override_html}</div>",
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
                    f'<h4><span class="badge warning">DATA NEEDED</span> ⏳ {msg_html}</h4>'
                    f'<ul><li>Missing fields: {missing_str}</li></ul></div>',
                    unsafe_allow_html=True
                )
                for sa in output.suggested_actions:
                    render_action(sa, extra_cls="info")
            elif isinstance(output, Stop):
                reason_html = html.escape(output.reason).replace("\n", "<br>")
                st.markdown(
                    '<div class="action-card stop">'
                    f'<h4><span class="badge stop">STOP</span> 🛑 {reason_html}</h4></div>',
                    unsafe_allow_html=True
                )
                for a in output.actions:
                    render_action(a)

        st.markdown('<p class="section-label">CLINICIAN NOTES</p>', unsafe_allow_html=True)
        st.session_state.gc_notes = st.text_area(
            "Notes to attach to the saved output:",
            value=st.session_state.gc_notes,
            height=120
        )

        if st.button("💾 Save this output", key="gc_save_output"):
            st.session_state.gc_saved_output = {"saved_at": datetime.now().isoformat()}
            st.success("Output saved for this session.")

        if "gc_saved_output" in st.session_state:
            md_text = build_gc_markdown(patient_data, outputs, st.session_state.gc_overrides, st.session_state.gc_notes)
            st.download_button(
                label="⬇️ Download Markdown summary",
                data=md_text.encode("utf-8"),
                file_name="gastric_cancer_summary.md",
                mime="text/markdown",
                key="gc_download_md"
            )

        with override_panel:
            if override_candidates:
                st.markdown("---")
                st.markdown('<p class="section-label">CLINICIAN OVERRIDES</p>', unsafe_allow_html=True)
                for a in override_candidates:
                    opt = a.override_options
                    raw_node, raw_field = opt["node"], opt["field"]
                    node, field = raw_node.replace("_", " ").title(), raw_field.replace("_", " ").title()
                    allowed = opt.get("allowed", [True, False])

                    with st.expander(f"⚙️ Override: **{node}** → `{field}`"):
                        preview = a.label[:120] + ("…" if len(a.label) > 120 else "")
                        st.markdown(f'<div class="override-card">Engine decision based on: <b>{html.escape(preview)}</b></div>', unsafe_allow_html=True)
                        
                        existing = next((o for o in st.session_state.gc_overrides if o.target_node == raw_node and o.field == raw_field), None)
                        current_val = existing.new_value if existing else None
                        
                        new_val = st.radio(
                            f"Set `{field}` to:",
                            options=allowed,
                            index=allowed.index(current_val) if current_val in allowed else 0,
                            key=f"ov_val_{raw_node}_{raw_field}",
                            horizontal=True
                        )
                        reason = st.text_input("Reason (required):", value=existing.reason if existing else "", key=f"ov_reason_{raw_node}_{raw_field}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Apply Override", key=f"ov_apply_{raw_node}_{raw_field}"):
                                if not reason.strip():
                                    st.error("A reason is required.")
                                else:
                                    st.session_state.gc_overrides = [o for o in st.session_state.gc_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                    st.session_state.gc_overrides.append(Override(raw_node, raw_field, None, new_val, reason.strip()))
                                    st.success("Override applied. Click Run Pathway to re-evaluate.")
                        with col2:
                            if existing and st.button("🗑 Remove Override", key=f"ov_remove_{raw_node}_{raw_field}"):
                                st.session_state.gc_overrides = [o for o in st.session_state.gc_overrides if not (o.target_node == raw_node and o.field == raw_field)]
                                st.success("Override removed.")

                if st.session_state.gc_overrides:
                    st.markdown('<p class="section-label">ACTIVE OVERRIDES</p>', unsafe_allow_html=True)
                    for o in st.session_state.gc_overrides:
                        st.markdown(
                            f'<div class="override-card">🛠 <b>{html.escape(o.target_node.replace("_", " ").title())}</b> → '
                            f'<code>{html.escape(o.field.replace("_", " ").title())}</code> set to <b>{html.escape(str(o.new_value))}</b><br>'
                            f'<span style="color:#a5b4fc">Reason: {html.escape(o.reason)}</span></div>',
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
