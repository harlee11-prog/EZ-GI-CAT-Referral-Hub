# pathway_handoff.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared cross-pathway handoff helper for EZ-GI-CAT Referral Hub
#
# Usage (in each page file, at the top after imports):
#   from pathway_handoff import apply_handoff, queue_handoff, show_handoff_banner, HANDOFF_KEY
#
# How it works:
#   • When an engine output triggers a route (e.g. ROUTE_HPYLORI_PATHWAY),
#     the SOURCE page calls queue_handoff(target_page, patient_data).
#   • On the NEXT render of the TARGET page, apply_handoff() detects the
#     queued payload, pre-fills session-state widget keys, and clears the
#     queue so it only fires once.
#
# Python 3.9 compatible — uses typing module instead of PEP 604 (X | Y)
#   and PEP 585 (list[str]) syntax so it works on all Streamlit Cloud versions.
# ─────────────────────────────────────────────────────────────────────────────

from typing import Dict, List, Optional, Any

import streamlit as st

HANDOFF_KEY = "_cross_pathway_handoff"

# ── Field mapping ─────────────────────────────────────────────────────────────
# Maps generic patient-data dict keys → per-page session-state widget keys
# Only fields that are SHARED between pathways need to appear here.

# Fields that every pathway page reads from the patient_data dict
_COMMON_FIELDS = [
    "age", "sex",
    "pregnant", "breastfeeding",
    # Alarm features (shared across all three)
    "familyhistoryuppergicancerfirstdegree",
    "familyhistoryesophagealorgastriccancerfirstdegree",
    "symptomonsetafterage60",
    "ageover60newpersistentsymptomsover3months",
    "unintendedweightloss",
    "blackstoolorbloodinvomit",
    "dysphagia", "progressivedysphagia",
    "persistentvomiting",
    "irondeficiencyanemiapresent",
    "activelybleedingnow",
    # H. pylori result (shared between Dyspepsia and H. Pylori pages)
    "hpyloritestdone", "hpyloriresultpositive",
    "hptestresult", "hptesttype",
    # PPI status (shared between GERD and Dyspepsia)
    "ppioncedailytrialdone", "ppioncedailyresponseadequate",
    "ppibidtrialdone", "ppibidresponseadequate",
    # Symptom overlap
    "predominantheartburn", "predominantregurgitation",
    "predominantepigastricpain", "predominantepigastricdiscomfort",
    "predominantupperabdominalbloating",
    "symptomdurationmonths",
]


def queue_handoff(target_page, patient_data):
    # type: (str, Dict[str, Any]) -> None
    """
    Call this from a source page when a cross-pathway route is triggered.

    target_page : one of "1_H._Pylori", "2_GERD", "3_Dyspepsia"
    patient_data: the full patient_data dict collected by the source page
    """
    st.session_state[HANDOFF_KEY] = {
        "target": target_page,
        "data": {k: v for k, v in patient_data.items() if v is not None},
    }


def apply_handoff(current_page):
    # type: (str) -> Optional[Dict[str, Any]]
    """
    Call this near the top of each page (before widgets are rendered).

    If a handoff payload is waiting for this page:
      • Returns the transferred patient_data dict
      • Clears the handoff queue so it only fires once
    Otherwise returns None.

    The caller should use the returned dict to pre-populate default values
    for st.number_input / st.selectbox / st.checkbox widgets via
    st.session_state assignments BEFORE those widgets are defined.
    """
    payload = st.session_state.get(HANDOFF_KEY)
    if payload and payload.get("target") == current_page:
        del st.session_state[HANDOFF_KEY]
        return payload["data"]
    return None


def show_handoff_banner(source_label, transferred_fields):
    # type: (str, List[str]) -> None
    """Render a dismissible info banner when a handoff has just been applied."""
    if not transferred_fields:
        return
    fields_str = ", ".join("`{}`".format(f) for f in transferred_fields[:6])
    if len(transferred_fields) > 6:
        fields_str += " … (+{} more)".format(len(transferred_fields) - 6)
    st.info(
        "↩️ **Patient data carried over from {} pathway.** "
        "Pre-filled fields: {}. Review and adjust as needed.".format(
            source_label, fields_str
        ),
        icon="🔗",
    )
