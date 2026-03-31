import streamlit as st

st.set_page_config(page_title="EZ GI CAT Clinical Decision Hub", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    .stAppDeployButton {display: none !important;}
    div[class*="viewerBadge"] {display: none !important;}
    
    /* Card Shading and Hover Effects */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e5e7eb !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        transform: translateY(-3px);
    }
    
    /* Dark mode support for the background color */
    @media (prefers-color-scheme: dark) {
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #1e1e1e;
            border: 1px solid #333333 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.7);
        }
    }
    </style>
""", unsafe_allow_html=True)

st.title("EZ GI CAT Clinical Decision Support Hub")
st.caption("Alberta Health Services · Primary Care Networks")
st.markdown("---")

# ── ROW 1 ──
r1c1, r1c2, r1c3 = st.columns(3)

with r1c1:
    with st.container(border=True):
        st.markdown("### H. Pylori")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/1_H_Pylori.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-hpylori.pdf", use_container_width=True)

with r1c2:
    with st.container(border=True):
        st.markdown("### Liver Mass")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/2_Liver_Mass.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/info/aph/if-aph-prov-liver-mass-primary-care-pathway.pdf", use_container_width=True)

with r1c3:
    with st.container(border=True):
        st.markdown("### GERD")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/3_GERD.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/info/aph/if-aph-scn-dh-pathway-gerd.pdf", use_container_width=True)

# ── ROW 2 ──
st.markdown("<br>", unsafe_allow_html=True)
r2c1, r2c2, r2c3 = st.columns(3)

with r2c1:
    with st.container(border=True):
        st.markdown("### NAFLD")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/4_NAFLD.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-nafld.pdf", use_container_width=True)

with r2c2:
    with st.container(border=True):
        st.markdown("### IBS")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/5_IBS.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-ibs.pdf", use_container_width=True)

with r2c3:
    with st.container(border=True):
        st.markdown("### HRRB")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/6_HRRB.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-high-risk-rectal-bleeding-pathway.pdf", use_container_width=True)

# ── ROW 3 ──
st.markdown("<br>", unsafe_allow_html=True)
r3c1, r3c2, r3c3 = st.columns(3)

with r3c1:
    with st.container(border=True):
        st.markdown("### Iron Deficiency Anemia")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/7_IDA.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-cancer-iron-deficiency-anemia-pathway.pdf", use_container_width=True)

with r3c2:
    with st.container(border=True):
        st.markdown("### HCV")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/8_HCV.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-hepatitisc.pdf", use_container_width=True)

with r3c3:
    with st.container(border=True):
        st.markdown("### Chronic Diarrhea")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/9_Chronic_Diarrhea.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "http://www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-diarrhea.pdf", use_container_width=True)

# ── ROW 4 ──
st.markdown("<br>", unsafe_allow_html=True)
r4c1, r4c2, r4c3 = st.columns(3)

with r4c1:
    with st.container(border=True):
        st.markdown("### Chronic Constipation")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/10_Constipation.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-constipation.pdf", use_container_width=True)

with r4c2:
    with st.container(border=True):
        st.markdown("### Dyspepsia")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/11_Dyspepsia.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/info/aph/if-aph-scn-dh-pathway-dyspepsia.pdf", use_container_width=True)

with r4c3:
    with st.container(border=True):
        st.markdown("### Gastric Cancer")
        nav, pdf = st.columns([2, 1])
        with nav:
            st.page_link("pages/12_Gastric_Cancer_draft.py", label="Open →", use_container_width=True)
        with pdf:
            st.link_button("PDF", "https://www.albertahealthservices.ca/assets/info/aph/if-aph-prov-gastric-cancer-prevention-screening-and-diagnosis-primary-care-pathway.pdf", use_container_width=True)
