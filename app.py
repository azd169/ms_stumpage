# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Mississippi Timber Price Report",
    layout="wide"
)

# -----------------------------------------------------------------------------
# Load data
# -----------------------------------------------------------------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/azd169/timber_prices/main/ms_stumpage.csv"

@st.cache_data
def load_stumpage():
    try:
        headers = {}
        # Optional: if you add a token (for private repos) via Streamlit secrets
        token = st.secrets.get("GITHUB_TOKEN", None)
        if token:
            headers["Authorization"] = f"token {token}"

        resp = requests.get(GITHUB_RAW_URL, headers=headers, timeout=10)
        resp.raise_for_status()  # will raise HTTPError if not 200

        # Read CSV from the text content
        return pd.read_csv(io.StringIO(resp.text))
    except Exception as e:
        st.error(
            "❌ Could not download stumpage data from GitHub. "
            "Please check that the repository is public (or that a valid token is set) "
            "and that the file path/branch are correct."
        )
        st.exception(e)
        return pd.DataFrame()

stumpage = load_stumpage()

# Make sure Year is numeric just in case
stumpage["Year"] = pd.to_numeric(stumpage["Year"], errors="coerce")

# Order of types for plotting (to mimic your factor levels)
type_order = [
    "Pine Sawtimber",
    "Mixed Hardwood Sawtimber",
    "Pine Chip-n-Saw",
    "Pine Pulpwood",
    "Hardwood Pulpwood"
]
stumpage["Type"] = pd.Categorical(stumpage["Type"], categories=type_order, ordered=True)

# -----------------------------------------------------------------------------
# Optional: Inject CSS (rough equivalent of your Shiny CSS + dark mode hints)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
      --background-color: #ffffff;
      --text-color: #000000;
      --link-color: #0072B2;
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --background-color: #1e1e1e;
        --text-color: #ffffff;
        --link-color: #8ab4f8;
      }
    }

    body, .stApp {
      background-color: var(--background-color) !important;
      color: var(--text-color) !important;
    }

    a {
      color: var(--link-color) !important;
    }

    /* center the main title row */
    .title-row {
      display: flex;
      align-items: center;
      justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------------------------------------------------------
# Header with logo + title
# -----------------------------------------------------------------------------
title_col1, title_col2 = st.columns([1, 5])

with title_col1:
    # Make sure MS_logo.jpg is in the same directory as this script
    st.image("MS_logo.jpg", caption=None, width=120)

with title_col2:
    st.markdown(
        "<h1 style='font-size:52px; font-weight:bold; margin-bottom:0;'>"
        "Mississippi Timber Price Report"
        "</h1>",
        unsafe_allow_html=True
    )

st.write("")  # small spacer

# -----------------------------------------------------------------------------
# Left: controls; Right: description text
# -----------------------------------------------------------------------------
left_col, right_col = st.columns([1.3, 2.2])

min_year = int(stumpage["Year"].min())
max_year = int(stumpage["Year"].max())

all_types = [t for t in type_order if t in stumpage["Type"].unique()]
all_quarters = ["Q1", "Q2", "Q3", "Q4"]

with left_col:
    # Price selector
    price_selector = st.radio(
        "Select Price:",
        options=["Minimum", "Average", "Maximum"],
        index=1  # default "Average"
    )

    # Type selector (equivalent to checkboxGroupInput)
    selected_types = st.multiselect(
        "Select Type(s):",
        options=all_types,
        default=[]
    )

    # Quarter selector
    selected_quarters = st.multiselect(
        "Select Quarter(s):",
        options=all_quarters,
        default=[]
    )

    # Year slider
    year_range = st.slider(
        "Select Year Range:",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        step=1
    )

    # Clear all button → reset selections using session state
    if st.button("Clear All"):
        st.session_state["selected_types"] = []
        st.session_state["selected_quarters"] = []
        st.session_state["year_range"] = (min_year, max_year)

    # Re-bind after potential reset
    selected_types = st.session_state.get("selected_types", selected_types)
    selected_quarters = st.session_state.get("selected_quarters", selected_quarters)
    year_range = st.session_state.get("year_range", year_range)

with right_col:
    st.markdown(
        """
        The Mississippi Timber Price Report provides a picture of timber market activity
        showing statewide stumpage prices for common forest products. This report should
        only be used as a guide to help individuals monitor timber market trends. The
        average price should not be applied as fair market value for a specific timber
        sale because many variables influence actual prices each landowner will receive.
        Timber prices are available by contacting your local county Extension office or
        consulting
        [Mississippi State Forestry Extension](http://www.extension.msstate.edu/forestry/forest-economics/timber-prices).
        """
    )
    st.markdown(
        """
        Timber prices are generated using data from timber sales conducted and reported
        across Mississippi. Reporters include forest product companies, logging
        contractors, consulting foresters, landowners, and other natural resource
        professionals. Are you interested in reporting timber prices or do you want more
        information about the Mississippi Timber Price Report? Please contact
        [Sabhyata Lamichhane](mailto:sabhyata.lamichhane@msstate.edu) at 662-325-3550
        for more information.
        """
    )

st.write("---")

# -----------------------------------------------------------------------------
# Filter data (equivalent to filtered_data() reactive)
# -----------------------------------------------------------------------------
def get_filtered_data():
    # Require at least one type, year range, and quarter
    if not selected_types or not selected_quarters or year_range is None:
        return None

    yr_min, yr_max = year_range

    data = stumpage[
        (stumpage["Type"].isin(selected_types)) &
        (stumpage["Year"] >= yr_min) &
        (stumpage["Year"] <= yr_max) &
        (stumpage["Quarter"].isin(selected_quarters))
    ].copy()

    # Ensure Time is treated as an ordered categorical on the x-axis
    if "Time" in data.columns:
        unique_time = sorted(data["Time"].unique())
        data["Time"] = pd.Categorical(data["Time"], categories=unique_time, ordered=True)

    return data

data = get_filtered_data()

# -----------------------------------------------------------------------------
# Plot or message
# -----------------------------------------------------------------------------
if data is None or data.shape[0] == 0:
    st.markdown(
        "<h3 style='color:red; text-align:center; margin-top:80px;'>"
        "No types, years, or quarters selected, or no data available. "
        "Please select at least one type, one year range, and one quarter to display the plot."
        "</h3>",
        unsafe_allow_html=True
    )
else:
    # Determine which price column to use
    price_column_name = price_selector  # "Minimum" / "Average" / "Maximum"
    if price_column_name not in data.columns:
        st.error(f"Column '{price_column_name}' not found in data.")
    else:
        y_vals = data[price_column_name]

        # Color mapping to match your ggplot scale_color_manual
        color_map = {
            "Pine Sawtimber": "#D55E00",
            "Mixed Hardwood Sawtimber": "#009E73",
            "Pine Chip-n-Saw": "#E69F00",
            "Pine Pulpwood": "#0072B2",
            "Hardwood Pulpwood": "#CC79A7",
        }

        # Symbol mapping (Plotly marker symbols)
        symbol_map = {
            "Pine Sawtimber": "circle",
            "Mixed Hardwood Sawtimber": "square",
            "Pine Chip-n-Saw": "diamond",
            "Pine Pulpwood": "triangle-up",
            "Hardwood Pulpwood": "triangle-down",
        }

        fig = go.Figure()

        # Plot each type separately (lines + markers)
        for t in data["Type"].cat.categories:
            if t not in data["Type"].values:
                continue

            df_t = data[data["Type"] == t].sort_values("Time")

            fig.add_trace(
                go.Scatter(
                    x=df_t["Time"],
                    y=df_t[price_column_name],
                    mode="lines+markers",
                    name=t,
                    marker=dict(
                        size=9,
                        symbol=symbol_map.get(t, "circle"),
                    ),
                    line=dict(width=2),
                    hovertemplate=(
                        "Type: %{customdata[0]}<br>"
                        "Time: %{x}<br>"
                        "Price ($/ton): %{y:.2f}<extra></extra>"
                    ),
                    customdata=df_t[["Type"]],
                )
            )

        # X ticks: show every 4th value like your ggplot code
        if "Time" in data.columns:
            cats = list(data["Time"].cat.categories)
            if len(cats) > 0:
                tickvals = cats[::4]
            else:
                tickvals = []
        else:
            tickvals = None

        fig.update_layout(
            xaxis=dict(
                title="",
                showgrid=True,
                tickfont=dict(color="black"),
                gridcolor="lightgray",
                zerolinecolor="black",
                tickvals=tickvals,
                tickangle=45
            ),
            yaxis=dict(
                title="Price ($/ton)",
                showgrid=True,
                tickfont=dict(color="black"),
                gridcolor="lightgray",
                zerolinecolor="black",
                tickmode="linear",
                dtick=5  # step of 5 as in scale_y_continuous(seq(0, 100, by = 5))
            ),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5
            ),
            margin=dict(l=50, r=50, t=50, b=120),
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis_title_font=dict(color="black", size=16),
            yaxis_title_font=dict(color="black", size=16),
            font=dict(color="black")
        )

        st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# Download filtered data
# -----------------------------------------------------------------------------
if data is not None and data.shape[0] > 0:
    csv_bytes = data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Data as CSV",
        data=csv_bytes,
        file_name="data.csv",
        mime="text/csv"
    )

st.write("")
st.write("---")

# -----------------------------------------------------------------------------
# Footer
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align: center; margin-top: 40px; font-size: 20px;">
    For further assistance contact
    <a href="mailto:ads992@msstate.edu">Andrea De&nbsp;Stefano</a>.
    </div>
    """,
    unsafe_allow_html=True

)
