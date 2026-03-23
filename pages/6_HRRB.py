import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import streamlit.components.v1 as components

from hrrb_engine import run_hrrb_pathway, Override, Action, DataRequest, Stop

st.set_page_config(page_title="HRRB Pathway", page_icon="🩸", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .card-urgent { background-color: #7a1a1a !important; border-left: 5px solid #ff4b4b; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-semiurgent { background-color: #5c4a1a !important; border-left: 5px solid #ffbb33; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-routine { background-color: #1a5c30 !important; border-left: 5px solid #21c55d; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-info { background-color: #1a3a5c !important; border-left: 5px solid #4b9eff; border-radius: 8px; padding: 16px 20px; margin-bottom: 12px; }
    .card-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; color: white; }
    .card-detail { font-size: 13px; color: #cccccc; margin: 2px 0; }
    .badge-urgent { background-color: #ff4b4b; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-semiurgent { background-color: #ffbb33; color: #333; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-routine { background-color: #21c55d; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .badge-info { background-color: #4b9eff; color: white; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; margin-right: 8px; }
    .section-header { font-size: 13px; font-weight: 600; color: #888888; text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 10px 0; }
    </style>
""", unsafe_allow_html=True)

st.title("🩸 High Risk Rectal Bleeding (HRRB) Pathway")
st.caption("Based on Alberta Health Services HRRB Pathway for Colorectal Cancer Diagnosis")
st.markdown("---")

left, right = st.columns([1, 1.4])
bool_map = {"Unknown": None, "Yes": True, "No": False}

with left:
    st.subheader("Patient Information")

    st.markdown("**Demographics**")
    sex        = st.selectbox("Sex", ["male", "female"])
    age        = st.number_input("Age", 1, 120, 55)

    st.markdown("**Rectal Bleeding History**")
    st.caption("All fields required to determine HRRB criteria")
    rb_visible       = st.selectbox("Blood visibly present in/on stool or toilet?", ["Unknown", "Yes", "No"])
    rb_not_tissue    = st.selectbox("Not just on tissue paper?", ["Unknown", "Yes", "No"])
    rb_new_worsening = st.selectbox("New onset or worsening?", ["Unknown", "Yes", "No"])
    rb_persistent    = st.selectbox("Persistent (not just a single episode)?", ["Unknown", "Yes", "No"])
    rb_most_days     = st.selectbox("Present most days of the week?", ["Unknown", "Yes", "No"])
    rb_duration      = st.number_input("Duration of bleeding (weeks)", 0.0, 104.0, 3.0, 0.5)
    scope_2y         = st.selectbox("Complete colonoscopy within last 2 years?", ["Unknown", "Yes", "No"])

    st.markdown("**Lab Values**")
    hemoglobin  = st.number_input("Hemoglobin (g/L)", 0.0, 250.0, 125.0)
    ferritin    = st.number_input("Serum Ferritin (µg/L)", 0.0, 1000.0, 25.0)
    baseline_hb = st.number_input("Baseline Hemoglobin (g/L, 0 = unknown)", 0.0, 250.0, 0.0)
    prior_anemia = st.checkbox("Prior anemia documented")

    st.markdown("**Medical History**")
    personal_crc = st.selectbox("Personal history of CRC?", ["Unknown", "Yes", "No"])
    fh_crc       = st.selectbox("Family history of CRC (1st degree)?", ["Unknown", "Yes", "No"])
    personal_ibd = st.selectbox("Personal history of IBD?", ["Unknown", "Yes", "No"])
    fh_ibd       = st.selectbox("Family history of IBD (1st degree)?", ["Unknown", "Yes", "No"])
    endoscopy_result = st.selectbox("Most recent lower endoscopy result", ["Unknown", "Normal", "Abnormal", "Never done"])
    endo_result_map = {"Unknown": None, "Normal": "normal", "Abnormal": "abnormal", "Never done": "never_done"}

    st.markdown("**Physical Exam**")
    dre_done         = st.selectbox("Digital rectal exam (DRE) done?", ["Unknown", "Yes", "No"])
    dre_pain         = st.selectbox("DRE not possible due to pain?", ["Unknown", "Yes", "No"])
    abdominal_mass   = st.checkbox("Palpable abdominal mass")
    rectal_mass      = st.checkbox("Palpable rectal mass")
    lesion_imaging   = st.checkbox("Suspected colorectal lesion on imaging")
    metastases       = st.checkbox("Evidence of metastases on imaging")

    st.markdown("**Other Alarm Features**")
    abd_pain     = st.checkbox("New/persistent/worsening abdominal pain")
    weight_loss  = st.number_input("Unintended weight loss % over 6 months (0 = none)", 0.0, 100.0, 0.0)
    bowel_change = st.checkbox("Concerning change in bowel habit")
    fit_planned  = st.checkbox("FIT ordered or planned")

    st.markdown("**Investigation Freshness**")
    cbc_fresh        = st.selectbox("CBC within 8 weeks?", ["Unknown", "Yes", "No"])
    creatinine_fresh = st.selectbox("Creatinine within 8 weeks?", ["Unknown", "Yes", "No"])
    ferritin_fresh   = st.selectbox("Ferritin within 8 weeks?", ["Unknown", "Yes", "No"])

    # ── OVERRIDE ──
    st.markdown("---")
    st.subheader("⚠ Clinician Override")
    override_active = st.checkbox("Apply an override")
    overrides_list  = []
    if override_active:
        ov_node   = st.selectbox("Node to override", [
            "Confirm_HRRB", "Alarm_Features", "Assign_Urgency"])
        ov_field_map = {
            "Confirm_HRRB":    "hrrb_confirmed",
            "Alarm_Features":  "alarm_present",
            "Assign_Urgency":  "urgency",
        }
        ov_field  = ov_field_map[ov_node]
        if ov_node == "Assign_Urgency":
            ov_value = st.selectbox("New urgency value", ["urgent", "semi_urgent", "routine"])
        else:
            ov_value = st.selectbox("New value", ["True", "False"]) == "True"
        ov_reason   = st.text_area("Clinical reason (required)")
        ov_initials = st.text_input("Clinician initials")
        if ov_reason and ov_initials:
            overrides_list.append(Override(
                target_node=ov_node, field=ov_field,
                old_value=None, new_value=ov_value,
                reason=f"[{ov_initials}] {ov_reason}",
            ))
        elif override_active:
            st.warning("Fill in reason and initials to activate override.")

    run = st.button("▶ Run Pathway", type="primary", use_container_width=True)

with right:
    if run:
        patient_data = {
            "sex":                                      sex,
            "age":                                      age,
            "hemoglobin":                               hemoglobin,
            "ferritin":                                 ferritin,
            "baseline_hemoglobin":                      baseline_hb if baseline_hb > 0 else None,
            "prior_anemia_documented":                  prior_anemia or None,
            "rectal_bleeding_visible":                  bool_map[rb_visible],
            "rectal_bleeding_not_just_tissue":          bool_map[rb_not_tissue],
            "rectal_bleeding_new_or_worsening":         bool_map[rb_new_worsening],
            "rectal_bleeding_persistent":               bool_map[rb_persistent],
            "rectal_bleeding_most_days_per_week":       bool_map[rb_most_days],
            "rectal_bleeding_duration_weeks":           rb_duration if rb_duration > 0 else None,
            "complete_colonoscopy_within_2y":           bool_map[scope_2y],
            "personal_history_crc":                     bool_map[personal_crc],
            "family_history_crc_first_degree":          bool_map[fh_crc],
            "personal_history_ibd":                     bool_map[personal_ibd],
            "family_history_ibd_first_degree":          bool_map[fh_ibd],
            "most_recent_lower_endoscopy_result":       endo_result_map[endoscopy_result],
            "dre_done":                                 bool_map[dre_done],
            "dre_not_possible_due_to_pain":             bool_map[dre_pain],
            "palpable_abdominal_mass":                  abdominal_mass or None,
            "palpable_rectal_mass":                     rectal_mass or None,
            "suspected_colorectal_lesion_on_imaging":   lesion_imaging or None,
            "evidence_of_metastases_on_imaging":        metastases or None,
            "abdominal_pain_new_persistent_or_worsening": abd_pain or None,
            "weight_loss_percent_6_months":             weight_loss if weight_loss > 0 else None,
            "concerning_change_in_bowel_habit":         bowel_change or None,
            "fit_ordered_or_planned":                   fit_planned or None,
            "cbc_within_8_weeks":                       bool_map[cbc_fresh],
            "creatinine_within_8_weeks":                bool_map[creatinine_fresh],
            "ferritin_within_8_weeks":                  bool_map[ferritin_fresh],
        }

        outputs, logs, applied_overrides = run_hrrb_pathway(patient_data, overrides=overrides_list)

        # ── ANIMATED DIAGRAM ──
        all_nodes = [
            ("confirm",     "Confirm\nHRRB"),
            ("history",     "Medical\nHistory"),
            ("exam",        "Physical\nExam"),
            ("baseline",    "Baseline\nInvestigations"),
            ("alarm",       "Alarm\nFeatures"),
            ("urgency",     "Assign\nUrgency"),
            ("finalize",    "Finalize\nReferral"),
        ]
        edges = [
            ("confirm","history"), ("history","exam"), ("exam","baseline"),
            ("baseline","alarm"), ("alarm","urgency"), ("urgency","finalize"),
        ]
        node_map = {
            "Confirm_HRRB":            "confirm",
            "Medical_History":         "history",
            "Physical_Exam":           "exam",
            "Baseline_Investigations": "baseline",
            "Alarm_Features":          "alarm",
            "Assign_Urgency":          "urgency",
            "Finalize":                "finalize",
        }
        visited = {"confirm"}
        for log in logs:
            n = node_map.get(log.node)
            if n: visited.add(n)

        n_nodes = len(all_nodes)
        node_w, node_h, gap, pad = 105, 60, 30, 30
        total_w = pad + n_nodes * node_w + (n_nodes - 1) * gap + pad
        positions = {nid: (pad + i * (node_w + gap), 30) for i, (nid, _) in enumerate(all_nodes)}

        svg = [
            f'<svg width="100%" viewBox="0 0 {total_w} 160" xmlns="http://www.w3.org/2000/svg" style="background:#0e0e0e;border-radius:14px;">',
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round"/></marker></defs>',
        ]
        for a, b in edges:
            ax, ay = positions[a]; bx, by = positions[b]
            svg.append(f'<line data-from="{a}" data-to="{b}" x1="{ax+node_w}" y1="{ay+node_h//2}" x2="{bx}" y2="{by+node_h//2}" stroke="#333" stroke-width="2" marker-end="url(#arr)" style="transition:stroke 0.5s"/>')
        for nid, title in all_nodes:
            x, y = positions[nid]
            svg.append(f'<rect data-node="{nid}" x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="8" fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5" style="transition:fill 0.5s,stroke 0.5s"/>')
            for li, line in enumerate(title.split("\n")):
                svg.append(f'<text x="{x+node_w//2}" y="{y+22+li*16}" text-anchor="middle" font-size="11" font-weight="700" fill="#666" font-family="Arial" data-label="{nid}" style="transition:fill 0.5s">{line}</text>')
        svg.append(f'<rect x="{pad}" y="110" width="12" height="12" rx="2" fill="#1a5c30" stroke="#21c55d" stroke-width="1.5"/><text x="{pad+18}" y="121" font-size="10" fill="#888" font-family="Arial">Followed</text>')
        svg.append(f'<rect x="{pad+90}" y="110" width="12" height="12" rx="2" fill="#1e1e1e" stroke="#3a3a3a" stroke-width="1.5"/><text x="{pad+108}" y="121" font-size="10" fill="#888" font-family="Arial">Not reached</text>')
        svg.append("</svg>")

        node_order = [nid for nid, _ in all_nodes]
        animated_html = f"""
        {"".join(svg)}
        <script>
        const visited = {list(visited)};
        const nodeOrder = {node_order};
        function animate() {{
            let i = 0;
            function step() {{
                if (i >= nodeOrder.length) return;
                const nid = nodeOrder[i];
                if (visited.includes(nid)) {{
                    const rect = document.querySelector('rect[data-node="' + nid + '"]');
                    const labels = document.querySelectorAll('text[data-label="' + nid + '"]');
                    const edgeIn = document.querySelector('line[data-to="' + nid + '"]');
                    if (rect) {{ rect.style.fill='#1a5c30'; rect.style.stroke='#21c55d'; }}
                    labels.forEach(l => l.style.fill='#ffffff');
                    if (edgeIn) edgeIn.setAttribute('stroke','#21c55d');
                }}
                i++; setTimeout(step, 400);
            }}
            step();
        }}
        setTimeout(animate, 200);
        </script>
        """
        st.subheader("🗺 Pathway Followed")
        components.html(animated_html, height=180, scrolling=False)
        st.markdown("---")

        # ── STATUS BANNER ──
        for o in outputs:
            if isinstance(o, Stop):
                urgency = (o.urgency or "").lower()
                if urgency == "urgent":
                    st.error(f"🚨 URGENT: {o.reason}")
                elif urgency == "semi_urgent":
                    st.warning(f"⚠ SEMI-URGENT: {o.reason}")
                else:
                    st.success(f"✅ {o.reason}")
            elif isinstance(o, DataRequest):
                st.warning(f"⏸ Pathway paused — missing: {', '.join(o.missing_fields)}")
                st.info(o.message)

        st.subheader("Clinical Recommendations")
        st.markdown('<div class="section-header">Recommended Actions</div>', unsafe_allow_html=True)

        for o in outputs:
            if isinstance(o, Action):
                urgency_raw = (o.urgency or "").lower()
                badge_raw   = (o.display or {}).get("badge", "")
                if urgency_raw == "urgent":
                    card_class, badge = "card-urgent",     '<span class="badge-urgent">🔴 URGENT</span>'
                elif urgency_raw == "semi_urgent":
                    card_class, badge = "card-semiurgent", '<span class="badge-semiurgent">🟡 SEMI-URGENT</span>'
                elif badge_raw == "warning":
                    card_class, badge = "card-semiurgent", '<span class="badge-semiurgent">⚠ WARNING</span>'
                elif urgency_raw == "routine":
                    card_class, badge = "card-routine",    '<span class="badge-routine">🟢 ROUTINE</span>'
                else:
                    card_class, badge = "card-info",       '<span class="badge-info">🔵 INFO</span>'
                details = o.details if isinstance(o.details, dict) else {}
                supported = details.get("supported_by", [])
                details_html = "".join(f'<div class="card-detail">• {d}</div>' for d in supported)
                details_html += "".join(f'<div class="card-detail"><b>{k}:</b> {v}</div>' for k, v in details.items() if k != "supported_by" and v not in [None, False, {}])
                st.markdown(f'<div class="{card_class}"><div class="card-title">{badge} {o.label}</div>{details_html}</div>', unsafe_allow_html=True)

            elif isinstance(o, DataRequest):
                with st.container(border=True):
                    st.warning(f"**Missing data — blocked at: {o.blocking_node}**")
                    st.write(o.message)
                    st.write(f"**Required:** {', '.join(o.missing_fields)}")

            elif isinstance(o, Stop):
                for a in o.actions:
                    urgency_raw = (o.urgency or "").lower()
                    if urgency_raw == "urgent":
                        card_class, badge = "card-urgent",     '<span class="badge-urgent">🔴 URGENT</span>'
                    elif urgency_raw == "semi_urgent":
                        card_class, badge = "card-semiurgent", '<span class="badge-semiurgent">🟡 SEMI-URGENT</span>'
                    else:
                        card_class, badge = "card-routine",    '<span class="badge-routine">🟢 DONE</span>'
                    details = a.details if isinstance(a.details, dict) else {}
                    supported = details.get("supported_by", [])
                    details_html = "".join(f'<div class="card-detail">• {d}</div>' for d in supported)
                    st.markdown(f'<div class="{card_class}"><div class="card-title">{badge} {a.label}</div>{details_html}</div>', unsafe_allow_html=True)

        with st.expander("📋 Decision Audit Log"):
            for log in logs:
                st.markdown(f"**[{log.node}]** {log.decision}")
                if log.used_inputs:
                    st.json(log.used_inputs)

        if applied_overrides:
            with st.expander("🔏 Applied Overrides"):
                for ov in applied_overrides:
                    st.markdown(f"- **{ov.target_node} / {ov.field}**: `{ov.old_value}` → `{ov.new_value}`")
                    st.caption(f"Reason: {ov.reason}")
    else:
        st.info("Fill in patient details on the left and click ▶ Run Pathway")
