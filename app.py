import streamlit as st

st.set_page_config(page_title="GI Clinical Decision Hub", page_icon="🏥", layout="wide")

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
    </style>
""", unsafe_allow_html=True)

st.title("🏥 GI Clinical Decision Support Hub")
st.caption("Alberta Health Services · Primary Care Networks")
st.markdown("---")

# ── ROW 1 ──
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("### 🦠 H. Pylori")
        nav1, pdf1 = st.columns([2, 1])
        with nav1:
            st.page_link("pages/1_H_Pylori.py", label="Open →", use_container_width=True)
        with pdf1:
            st.link_button("📄 PDF", "www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-hpylori.pdf", use_container_width=True)

with col2:
    with st.container(border=True):
        st.markdown("### 💊 Chronic Constipation")
        nav2, pdf2 = st.columns([2, 1])
        with nav2:
            st.page_link("pages/2_Constipation.py", label="Open →", use_container_width=True)
        with pdf2:
            st.link_button("📄 PDF", "www.ahs.ca/assets/about/scn/ahs-scn-dh-pathway-chronic-constipation.pdf", use_container_width=True)

with col3:
    with st.container(border=True):
        st.markdown("### 🩸 Iron Deficiency Anemia")
        nav3, pdf3 = st.columns([2, 1])
        with nav3:
            st.page_link("pages/7_IDA.py", label="Open →", use_container_width=True)
        with pdf3:
            st.link_button("📄 PDF", "www.ahs.ca/assets/about/scn/ahs-scn-cancer-iron-deficiency-anemia-pathway.pdf", use_container_width=True)


