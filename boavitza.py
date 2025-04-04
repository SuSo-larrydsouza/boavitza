import streamlit as st
import pandas as pd
import math


# Set the Streamlit page layout to wide
st.set_page_config(layout="wide")

# Read the CSV file
file = "/Users/larrydsouza/Documents/Boavitza/boavitza/new_hp.csv"
open_file = pd.read_csv(file)
open_file["gwp_total"] = pd.to_numeric(open_file["gwp_total"], errors='coerce')



# Filter rows where 'gwp_total' is not null
filtered_df = open_file[
    open_file["gwp_total"].notnull() & 
    open_file["gwp_total"].apply(lambda x: isinstance(x, (int, float)))
]

complete_df = filtered_df[filtered_df["gwp_manufacturing_ratio"].notnull()]

table_options = {
    "filtered_df": filtered_df,
    "complete_df": complete_df
}

selected_table = st.selectbox("Select a table type", options=table_options)
data_table = table_options[selected_table]


data_table["gwp_total"] = pd.to_numeric(data_table["gwp_total"], errors='coerce')

data_table["gwp_manufacturing_ratio"] = pd.to_numeric(data_table["gwp_manufacturing_ratio"], errors='coerce')


mean_value = data_table["gwp_total"].mean()
mean_pcf = math.ceil(mean_value) if pd.notnull(mean_value) else 0

st.metric("Mean Total PCF",mean_pcf)

col1, col2, col3 = st.columns([1,1,1])
if "count_datasets" is not st.session_state:
        st.session_state.count_datasets = 0


new_count = len(data_table["sources_hash"])
count_datasets = st.session_state.count_datasets
if count_datasets != new_count:
    count_datasets = new_count

    with col1:
        # Current max value
        max_manufacturing_ratio = round(data_table["gwp_manufacturing_ratio"].max(), 2)


        # Show metric
        st.metric(
            "Max manufacturing GWP ratio",
            max_manufacturing_ratio,
            delta_color="normal",
            help="None",
            label_visibility="visible",
            border=False
        )

    # ✅ Now update session state for next run
    st.session_state["max_gwp_manufacturing"] = max_manufacturing_ratio

    with col2:
        mean_manufacturing_ratio = round(data_table["gwp_manufacturing_ratio"].mean(),2)
        st.metric("Mean manufacturing GWP ratio", mean_manufacturing_ratio)

    with col3:
        min_manufacturing_ratio = round(data_table["gwp_manufacturing_ratio"].min(),2)
        st.metric("Min manufacturing GWP ratio", min_manufacturing_ratio)    


data_table["gwp_manufacturing"] = data_table["gwp_total"] * data_table["gwp_manufacturing_ratio"]

mean_manufacturing_pcf = round(data_table["gwp_manufacturing"].mean(),2)
st.metric("**Mean manufacturing PCF**", mean_manufacturing_pcf)

st.caption(f" a total of {count_datasets} datasets")
st.dataframe(data_table, height=650, row_height=30)




