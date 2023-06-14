import streamlit as st
import json
import time
import pandas as pd
import datetime as dt
from pymongo import MongoClient, DESCENDING
import requests
import plotly.express as px
import plotly.graph_objects as go


###########################################################################

st.set_page_config(
    layout="centered", page_icon="", page_title="My Stock Portfolio"
)

# hide streamlit branding and hamburger menu
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown(
    "<h2 style='text-align: center; color: white;'>Bullet Momentum Strategy - Portfolio</h2>",
    unsafe_allow_html=True,
)

st.write("----")

###########################################################################

# connect to the database and get open and closed positions
mongo = MongoClient(st.secrets["mongo_db"]["mongo_url"])
mydb = mongo["algox"]
coll = mydb["algox-bms-portfolio"]

df = pd.DataFrame(list(coll.find()))[["trade_date","stock_symbol","entry_price","entry_time","qty","running_pnl","status","exit_price","exit_time","pnl"]]

df_open = df[df["status"] == "OPEN"]
df_closed = df[df["status"] == "CLOSED"]

# initiate variables
initial_capital = 1000000
realized_pnl = round(df_closed["pnl"].sum(),2)

###########################################################################

# Flatten the 'running_pnl' dictionaries into a DataFrame
running_pnl_df = pd.json_normalize(df['running_pnl'])

# Set the index of the DataFrame to the dates
running_pnl_df.index = pd.to_datetime(running_pnl_df.index)

# Sum the values for each date
running_pnl_sum = running_pnl_df.sum(axis=1)

# Convert the Series to a DataFrame
running_pnl_sum_df = running_pnl_sum.to_frame(name='running_pnl_sum')

# Assuming df is your DataFrame

# Create a list of DataFrames, each containing the 'running_pnl' data for one stock
dfs = [pd.DataFrame.from_dict(row['running_pnl'], orient='index', columns=[row['stock_symbol']]) for index, row in df.iterrows()]

# Concatenate the DataFrames along the columns axis
running_pnl_df = pd.concat(dfs, axis=1)

# Convert the index to datetime
running_pnl_df.index = pd.to_datetime(running_pnl_df.index)

#find cumulative pnl
running_pnl_df['cum_pnl'] = running_pnl_df.sum(axis=1)
running_pnl_df['cum_pnl_pct'] = running_pnl_df['cum_pnl'].apply(lambda x: round(x*100/initial_capital,2))

# Calculate the running maximum of the net pnl
running_pnl_df['running_max'] = running_pnl_df['cum_pnl'].cummax()

# Calculate the drawdown
running_pnl_df['drawdown'] = running_pnl_df['cum_pnl'] - running_pnl_df['running_max']
running_pnl_df['drawdown_pct'] = running_pnl_df['drawdown'].apply(lambda x: round(x*100/initial_capital,2))

# Calculate drawdown days
running_pnl_df['peak'] = running_pnl_df['cum_pnl'].cummax()
running_pnl_df['drawdown_start'] = (running_pnl_df['cum_pnl'] < running_pnl_df['peak']).astype(int)
running_pnl_df['drawdown_days'] = running_pnl_df['drawdown_start'].cumsum()
running_pnl_df['drawdown_days'] = running_pnl_df.apply(lambda x: int(x['drawdown_days']) if x["drawdown"] < 0 else 0, axis = 1)

#calculate strategy stats
net_profit = running_pnl_df["cum_pnl"][-1]
unrealized_pnl = round(net_profit - realized_pnl,2)
num_days = (dt.datetime.today() - dt.datetime(2023,6,5)).days
max_dd = running_pnl_df['drawdown_pct'].min()
max_dd_days = running_pnl_df['drawdown_days'].max()

###########################################################################

# create streamlit columns

st.markdown(
    "<h4 style='text-align: center; color: white;'>📊 Strategy Performance</h4>",
    unsafe_allow_html=True,
)
st.write("")
st.write("")

col1, col2, col3 = st.columns(3)
col1.metric(label="Initial Capital", value=initial_capital)
col2.metric(label="Net Profit", value= net_profit)
col3.metric(label="Net Returns", value=str(round(net_profit*100/initial_capital,2)) + "%")

st.write("")

col4, col5, col6 = st.columns(3)
col4.metric(label="Realized PNL", value=realized_pnl)
col5.metric(label="Unrealized PNL", value= unrealized_pnl)
col6.metric(label="Realized Returns", value=str(round(realized_pnl*100/initial_capital,2)) + "%")

st.write("")

col7, col8, col9 = st.columns(3)
col7.metric(label="Max Drawdown", value=str(max_dd) + "%")
col8.metric(label="Max Drawdown Period", value= str(max_dd_days) + " days")
col9.metric(label="Running since last", value=str(num_days) + " days")

st.write("---")

###########################################################################

# Create a line plot of 'cum_pnl' with date as the x-axis
fig_cumpnl = go.Figure(data=go.Scatter(x=running_pnl_df.index, y=running_pnl_df['cum_pnl_pct'], mode='lines+markers'))

# Add title and labels
fig_cumpnl.update_layout(title=dict(text = 'Strategy Equity PNL Curve',font=dict(size=22), x=0.25, xref="paper"), xaxis_title='Date', yaxis_title='Cumulative Returns (%)')

# Show the plot
st.plotly_chart(fig_cumpnl)

# Create a line plot of 'cum_pnl' with date as the x-axis
fig_dd = go.Figure(data=go.Scatter(x=running_pnl_df.index, y=running_pnl_df['drawdown_pct'], mode='lines+markers'))

# Add title and labels
fig_dd.update_layout(title=dict(text = 'Strategy Drawdown Curve',font=dict(size=22), x=0.25, xref="paper"), xaxis_title='Date', yaxis_title='Drawdown (%)')

# Show the plot
st.plotly_chart(fig_dd)


###########################################################################

st.write("---")


st.markdown(
    "<h4 style='text-align: center; color: white;'>📖 Open Positions</h4>",
    unsafe_allow_html=True,
)
st.write("")
st.write(f"Total Unrealized PNL : ₹ {unrealized_pnl}")
st.write("")
df_open = df_open[["trade_date","stock_symbol","entry_price","qty","running_pnl"]]
df_open["buy_value"] = df_open["entry_price"]*df_open["qty"]
df_open["running_pnl"] = df_open["running_pnl"].apply(lambda x: list(x.values())[-1])
df_open["running_returns (%)"] = df_open.apply(lambda x: round((x["running_pnl"]*100)/(x["buy_value"]),2), axis = 1)
df_open = df_open.set_index("trade_date")
st.dataframe(df_open)

st.write("---")


st.markdown(
    "<h4 style='text-align: center; color: white;'>📕 Closed Positions</h4>",
    unsafe_allow_html=True,
)
st.write("")
st.write(f"Total Realized PNL : ₹ {realized_pnl}")
st.write("")
df_closed = df_closed[["trade_date","stock_symbol","entry_price","exit_price","exit_time","qty","pnl"]]
df_closed["buy_value"] = df_closed["entry_price"]*df_closed["qty"]
df_closed["sell_value"] = df_closed["exit_price"]*df_closed["qty"]
df_closed["returns (%)"] = round((df_closed["pnl"]*100)/df_closed["buy_value"],2)
df_closed = df_closed.set_index("trade_date")
st.dataframe(df_closed)

st.write("---")
