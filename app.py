import streamlit as st

from src.ui import render_app

st.set_page_config(page_title="Readily Module", layout="wide")
render_app()