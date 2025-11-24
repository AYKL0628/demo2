import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import os

st.title('Hello, Students!')
st.write('This is your Python Programming course.')
current_directory = os.getcwd()
file_path = os.path.join(current_directory, "winequality-red.csv")
with st.sidebar:
    selected=option_menu(
        menu_title = "Menu",
        options = ["Home", "About", "Contact"],
        icons = ["house",
                 "gear",
                 "list-task"],
        menu_icon= "cast",
        default_index=0,
    )

if selected == "Home":
    st.title(f"Welcome to the {selected} page.")
    df = pd.read_csv(file_path, delimiter=';')
    st.dataframe(df)
if selected == "About":
    st.title(f"Welcome to the {selected} page.")

if selected == "Contact":
    st.title(f"Welcome to the {selected} page.")
