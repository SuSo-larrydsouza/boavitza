import streamlit as st
import pandas as pd

# Set the Streamlit page layout to wide
st.set_page_config(layout="wide")

# Read the CSV file
file = "/Users/larrydsouza/Documents/Boavitza/boavitza/new_hp.csv"
open_file = pd.read_csv(file)
open_file["gwp_total"] = pd.to_numeric(open_file["gwp_total"], errors='coerce')
filtered_df = open_file[open_file["gwp_total"].notnull()]


# Filter rows where 'gwp_total' is not null
filtered_df = open_file[
    open_file["gwp_total"].notnull() & 
    open_file["gwp_total"].apply(lambda x: isinstance(x, (int, float)))
]



st.caption(f" a total of {len(filtered_df["sources_hash"])} datasets")

# Display the filtered DataFrame in the app
st.dataframe(filtered_df, height=1100, row_height=30)
