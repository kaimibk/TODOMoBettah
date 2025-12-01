import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="3D Prioritization Matrix")

st.html("<h1><sub><sup>TODO</sup></sub> Mo' Bettah &mdash; 3D Task Prioritizer</h1>")

preamble_col1, preamble_col2 = st.columns(2)

with preamble_col1:
    st.write("""
    Prioritize your tasks by scoring them on three dimensions:
    * **Urgency:** How soon does it need to be done? Higher number means _more_ urgent.
    * **Impact:** How much value does it provide? Higher number means _more_ impact.
    * **Effort:** How hard is it to do? Higher number means _more_ effort.
    """)

with preamble_col2:
    st.write("Ideally, you want to focus on tasks that are **high urgency**, **high impact**, and **low effort**.")
    st.latex(r"\text{Priority} = \frac{\text{Urgency} + \text{Impact} + (10 - \text{Effort})}{3}")
    st.write("""
    This scales the result to a 0-10 range where:
    * **10 (Max Priority)** = 10 Urgency + 10 Impact + 0 Effort
    * **0 (Min Priority)** = 0 Urgency + 0 Impact + 10 Effort
    """
    )

# --- Helper Function for Priority ---
def calculate_priority(df):
    """Calculates priority score based on Urgency, Impact, and Effort."""
    # Formula: (Urgency + Impact + (10 - Effort)) / 3
    # We use fillna(0) to ensure the math works even if fields are empty
    return (
        df["Urgency (0-10)"].fillna(0) + 
        df["Impact (0-10)"].fillna(0) + 
        (10 - df["Effort (0-10)"].fillna(0))
    ) / 3

# --- Data Initialization ---
if "tasks_df" not in st.session_state:
    data = {
        "Task": ["Fix critical bug", "Write documentation", "Team meeting", "Learn Rust", "Update dependencies"],
        "Urgency (0-10)": [9, 4, 7, 2, 5],
        "Impact (0-10)": [8, 6, 5, 8, 3],
        "Effort (0-10)": [5, 4, 2, 9, 3],
        "Status": [False, False, True, False, False]
    }
    df = pd.DataFrame(data)
    df["Priority"] = calculate_priority(df)
    st.session_state.tasks_df = df

# Ensure we have a persistent ID for tracking selections
if "id" not in st.session_state.tasks_df.columns:
    st.session_state.tasks_df["id"] = st.session_state.tasks_df.index

# Initialize selection state if not present
if "selected_indices" not in st.session_state:
    st.session_state.selected_indices = []
if "last_selection_source" not in st.session_state:
    st.session_state.last_selection_source = None

# --- Sidebar / Controls ---
with st.sidebar:
    st.header("Settings")
    show_completed = st.checkbox("Show Completed Tasks in Plot", value=True)
    show_dividers = st.checkbox("Show Quadrant Dividers", value=True)
    
    st.info("""
    **Controls:**
    - **Click points** on any chart to highlight them across all views.
    - Double-click a chart to reset selection.
    - Edit cells directly in the table.
    - **Click 'Save / Update Analysis'** to refresh charts.
    """)
    
    if st.button("Clear Selection"):
        st.session_state.selected_indices = []
        st.session_state.last_selection_source = None
        st.rerun()

# --- Section 1: Editable Dataframe ---
st.subheader("Task List")

st.write("Add, edit, or delete tasks below. **Click the button below to update the analysis.**")
st.warning("Warning: data changes do not persist. You will lose them if you refresh or close the app.", icon="⚠️")

column_config = {
    "Task": st.column_config.TextColumn("Task Name", required=True),
    "Urgency (0-10)": st.column_config.NumberColumn("Urgency", min_value=0, max_value=10, format="%d ⭐"),
    "Impact (0-10)": st.column_config.NumberColumn("Impact", min_value=0, max_value=10, format="%d 💥"),
    "Effort (0-10)": st.column_config.NumberColumn("Effort", min_value=0, max_value=10, format="%d 💪"),
    "Status": st.column_config.CheckboxColumn("Done?", default=False),
    "Priority": st.column_config.ProgressColumn(
        "Priority Score",
        help="High Impact + High Urgency + Low Effort",
        format="%.1f",
        min_value=0,
        max_value=10,
    ),
    "id": None # Hide ID column
}

# Capture the edited dataframe from the UI
edited_df = st.data_editor(
    st.session_state.tasks_df,
    column_config=column_config,
    num_rows="dynamic",
    use_container_width=True,
    key="editor",
    hide_index=True,
    disabled=["Priority"]
)

# Button to trigger the update
if st.button("Save / Update Analysis", type="primary"):
    # 1. Update the session state with the new data from the editor
    st.session_state.tasks_df = edited_df.copy()
    
    # 2. Reset index to ensure clean sequential IDs (handles deletions cleanly)
    st.session_state.tasks_df.reset_index(drop=True, inplace=True)
    
    # 3. Ensure every row has a unique ID (crucial for new rows added via UI)
    st.session_state.tasks_df["id"] = st.session_state.tasks_df.index
    
    # 4. Recalculate Priority for the whole dataframe
    st.session_state.tasks_df["Priority"] = calculate_priority(st.session_state.tasks_df)
    
    # 5. Rerun the app to update charts with the new data
    st.rerun()

# --- Helper: Handle Selection ---
def update_selection(selection_state, source_name):
    """
    Updates session state based on chart selection.
    """
    if selection_state and selection_state.get("selection", {}).get("points", []):
        # Extract IDs from customdata
        indices = [p["customdata"][0] if isinstance(p.get("customdata"), list) else p.get("customdata") 
                   for p in selection_state["selection"]["points"]]
        return indices
    return None

# --- Plotting Preparation ---
# Note: The charts below use 'st.session_state.tasks_df'.
# This means they show the state as of the LAST "Save/Update" click, not the current un-saved edits.

st.divider()
st.subheader("3D Priority Space")

# Filter data
plot_df = st.session_state.tasks_df.copy()
if not show_completed:
    plot_df = plot_df[plot_df["Status"] == False]

if not plot_df.empty:
    
    # Helper to convert hex to rgba for transparency handling
    def hex_to_rgba(hex_code, alpha):
        hex_code = hex_code.lstrip('#')
        return f"rgba({int(hex_code[0:2], 16)}, {int(hex_code[2:4], 16)}, {int(hex_code[4:6], 16)}, {alpha})"

    # Define colors based on selection state (using RGBA for transparency)
    def get_style(row, base_hex, base_alpha=1.0):
        # If nothing is selected, return the base color/alpha
        if not st.session_state.selected_indices:
            return hex_to_rgba(base_hex, base_alpha)
        # If this specific row is selected, return base color/alpha (highlighted)
        if row.name in st.session_state.selected_indices:
            return hex_to_rgba(base_hex, base_alpha)
        # Otherwise (unselected), return dimmed grey
        return "rgba(200, 200, 200, 0.1)"

    # Split data
    active_df = plot_df[plot_df["Status"] == False].copy()
    completed_df = plot_df[plot_df["Status"] == True].copy()
    
    # --- 3D Chart Construction ---
    traces = []
    
    # Optional: Add Semi-Transparent Planes to divide quadrants (Octants)
    if show_dividers:
        # Plane at X=5 (Urgency midpoint)
        traces.append(go.Surface(
            x=[[5, 5], [5, 5]], y=[[0, 10], [0, 10]], z=[[0, 0], [10, 10]],
            showscale=False, opacity=0.1, colorscale=[[0, 'gray'], [1, 'gray']], hoverinfo='skip'
        ))
        # Plane at Y=5 (Impact midpoint)
        traces.append(go.Surface(
            x=[[0, 10], [0, 10]], y=[[5, 5], [5, 5]], z=[[0, 0], [10, 10]],
            showscale=False, opacity=0.1, colorscale=[[0, 'gray'], [1, 'gray']], hoverinfo='skip'
        ))
        # Plane at Z=5 (Effort midpoint)
        traces.append(go.Surface(
            x=[[0, 10], [0, 10]], y=[[0, 0], [10, 10]], z=[[5, 5], [5, 5]],
            showscale=False, opacity=0.1, colorscale=[[0, 'gray'], [1, 'gray']], hoverinfo='skip'
        ))

    # Active Traces
    if not active_df.empty:
        colors = [get_style(row, '#e74c3c', 1.0) for _, row in active_df.iterrows()]
        
        traces.append(go.Scatter3d(
            x=active_df['Urgency (0-10)'],
            y=active_df['Impact (0-10)'],
            z=active_df['Effort (0-10)'],
            mode='markers+text',
            text=active_df['Task'],
            textposition="top center",
            name='Pending',
            customdata=active_df.index,
            hoverinfo='text+x+y+z',
            marker=dict(size=8, color=colors, symbol='diamond', line=dict(width=2, color='DarkSlateGrey')),
            projection=dict(x=dict(show=True, opacity=0.3, scale=0.4), y=dict(show=True, opacity=0.3, scale=0.4), z=dict(show=True, opacity=0.3, scale=0.4))
        ))

    # Completed Traces
    if not completed_df.empty:
        colors = [get_style(row, '#2ecc71', 0.3) for _, row in completed_df.iterrows()]
        
        traces.append(go.Scatter3d(
            x=completed_df['Urgency (0-10)'],
            y=completed_df['Impact (0-10)'],
            z=completed_df['Effort (0-10)'],
            mode='markers+text',
            text=completed_df['Task'],
            textposition="top center",
            name='Completed',
            customdata=completed_df.index,
            hoverinfo='text+x+y+z',
            marker=dict(size=8, color=colors, symbol='circle', line=dict(width=2, color='DarkSlateGrey')),
            projection=dict(x=dict(show=True, opacity=0.3, scale=0.4), y=dict(show=True, opacity=0.3, scale=0.4), z=dict(show=True, opacity=0.3, scale=0.4))
        ))

    fig_3d = go.Figure(data=traces)
    
    # Apply the requested background colors to the scene
    fig_3d.update_layout(
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            xaxis=dict(
                title='Urgency', 
                range=[0, 10], 
                backgroundcolor="rgb(200, 200, 230)", 
                gridcolor="white", 
                showbackground=True, 
                zerolinecolor="white"
            ),
            yaxis=dict(
                title='Impact', 
                range=[0, 10], 
                backgroundcolor="rgb(230, 200, 230)", 
                gridcolor="white", 
                showbackground=True, 
                zerolinecolor="white"
            ),
            zaxis=dict(
                title='Effort', 
                # We flip the Z axis (10 to 0) so Low Effort (0) appears at the "Top".
                # This aligns visually with High Urgency/Impact.
                range=[10, 0], 
                backgroundcolor="rgb(230, 230, 200)", 
                gridcolor="white", 
                showbackground=True, 
                zerolinecolor="white"
            ),
            aspectmode='cube'
        ),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        height=600,
        uirevision='constant',
    )

    sel_3d = st.plotly_chart(fig_3d, use_container_width=False, on_select="rerun", key="chart_3d")

    # --- 2D Charts ---
    st.divider()
    st.subheader("2D Axis Comparisons")
    
    col_a, col_b, col_c = st.columns(3)
    
    layout_2d = dict(
        xaxis=dict(range=[-0.5, 10.5], constrain='domain', fixedrange=True, showgrid=False, zeroline=False),
        yaxis=dict(range=[-0.5, 10.5], scaleanchor="x", scaleratio=1, fixedrange=True, showgrid=False, zeroline=False),
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False,
        height=350,
        hovermode='closest',
        shapes=[
            dict(type="line", x0=5, y0=-0.5, x1=5, y1=10.5, line=dict(color="Gray", width=1, dash="dash")),
            dict(type="line", x0=-0.5, y0=5, x1=10.5, y1=5, line=dict(color="Gray", width=1, dash="dash")),
        ]
    )

    # Dictionary defining labels for (x, y) coordinates of quadrants
    # Format: "X vs Y": {(x_coord, y_coord): "Label"}
    # Coordinates are center points of quadrants: 2.5 (Low) and 7.5 (High)
    QUADRANT_LABELS = {
        "Urgency vs Impact": {
            (10, 10): "Do First",    # High Urg, High Imp
            (0.5, 10): "Schedule",    # Low Urg, High Imp
            (10, 0.5): "Delegate",    # High Urg, Low Imp
            (0.5, 0.5): "Delete"       # Low Urg, Low Imp
        },
        "Impact vs Effort": {
            (10, 0.5): "Quick Wins",      # High Imp, Low Eff (Visually Top Right)
            (10, 10): "Major Projects",  # High Imp, High Eff (Visually Bottom Right)
            (0.5, 0.5): "Fill-ins",        # Low Imp, Low Eff (Visually Top Left)
            (0.75, 10): "Time Wasters"     # Low Imp, High Eff (Visually Bottom Left)
        },
        "Urgency vs Effort": {
            (10, 0.5): "Quick Fixes",     # High Urg, Low Eff
            (10, 10): "Critical Slog",   # High Urg, High Eff
            (0.5, 0.5): "Maybe Later",     # Low Urg, Low Eff
            (0.5, 10): "Avoid"            # Low Urg, High Eff
        }
    }

    def create_2d_fig(x_col, y_col, title, x_title, y_title):
        traces_2d = []
        if not active_df.empty:
            colors = [get_style(row, '#e74c3c', 1.0) for _, row in active_df.iterrows()]
            traces_2d.append(go.Scatter(
                x=active_df[x_col], y=active_df[y_col], mode='markers+text',
                text=active_df['Task'], textposition="top center", name='Pending',
                customdata=active_df.index,
                marker=dict(size=10, color=colors, symbol='diamond', line=dict(width=1, color='DarkSlateGrey'))
            ))
        if not completed_df.empty:
            colors = [get_style(row, '#2ecc71', 0.5) for _, row in completed_df.iterrows()]
            traces_2d.append(go.Scatter(
                x=completed_df[x_col], y=completed_df[y_col], mode='markers',
                text=completed_df['Task'], name='Completed', customdata=completed_df.index,
                marker=dict(size=8, color=colors, symbol='circle')
            ))
            
        fig_2d = go.Figure(data=traces_2d)
        fig_2d.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title, **layout_2d)
        
        # Add Quadrant Annotations
        if title in QUADRANT_LABELS:
            for (qx, qy), label in QUADRANT_LABELS[title].items():
                fig_2d.add_annotation(
                    x=qx, y=qy,
                    text=label,
                    showarrow=False,
                    font=dict(size=12, color="gray"),
                    opacity=0.5
                )

        # Invert Axis if "Effort" is involved to put 0 (Low Effort) at Top/Right
        if "Effort" in x_title:
             fig_2d.update_xaxes(range=[10.5, -0.5])
        if "Effort" in y_title:
             fig_2d.update_yaxes(range=[10.5, -0.5])
             
        return fig_2d

    # Render 2D charts and capture selection
    with col_a:
        fig1 = create_2d_fig('Urgency (0-10)', 'Impact (0-10)', "Urgency vs Impact", "Urgency", "Impact")
        sel_1 = st.plotly_chart(fig1, use_container_width=True, on_select="rerun", key="chart_2d_1")

    with col_b:
        fig2 = create_2d_fig('Impact (0-10)', 'Effort (0-10)', "Impact vs Effort", "Impact", "Effort")
        sel_2 = st.plotly_chart(fig2, use_container_width=True, on_select="rerun", key="chart_2d_2")

    with col_c:
        fig3 = create_2d_fig('Urgency (0-10)', 'Effort (0-10)', "Urgency vs Effort", "Urgency", "Effort")
        sel_3 = st.plotly_chart(fig3, use_container_width=True, on_select="rerun", key="chart_2d_3")

    # --- Selection Logic Processor ---
    # Combine selections
    s3d = update_selection(sel_3d, "3d")
    s1 = update_selection(sel_1, "2d_1")
    s2 = update_selection(sel_2, "2d_2")
    s3 = update_selection(sel_3, "2d_3")
    
    candidates = [s for s in [s3d, s1, s2, s3] if s is not None]
    
    if candidates:
        flat_list = list(set([item for sublist in candidates for item in sublist])) if isinstance(candidates[0], list) else candidates[0]
        if set(flat_list) != set(st.session_state.selected_indices):
            st.session_state.selected_indices = flat_list
            st.rerun()
    
    # --- Eisenhower Matrix View (Urgency vs Impact) ---
    st.divider()
    st.subheader("Action Matrix (Eisenhower Method)")
    st.caption("Tasks are grouped by Urgency & Impact, then sorted by Effort (Easiest first).")

    # Define bins for Eisenhower (2x2)
    # Urgency (High/Low) vs Impact (High/Low)
    # Cutoff at 5
    def categorize_eisenhower(row):
        # Urgency: High (>5) vs Low (<=5)
        # Impact: High (>5) vs Low (<=5)
        
        urgent = row["Urgency (0-10)"] >= 5
        important = row["Impact (0-10)"] >= 5
        
        if urgent and important:
            return 0, 0 # Do First (Top Left)
        elif not urgent and important:
            return 0, 1 # Schedule (Top Right)
        elif urgent and not important:
            return 1, 0 # Delegate (Bottom Left)
        else:
            return 1, 1 # Don't Do (Bottom Right)

    # Labels for the 2x2 Grid
    eisenhower_labels = [
        ["🔥 Do First (Urgent & Important)", "📅 Schedule (Important, Less Urgent)"],
        ["🙋 Delegate (Urgent, Less Important)", "🗑️ Delete (Not Urgent, Not Important)"]
    ]
    
    # Initialize grid buckets
    # grid_tasks[row][col] -> list of row data
    grid_tasks = [[[], []], [[], []]]
    
    # Populate buckets using plot_df
    for _, row in plot_df.iterrows():
        r, c = categorize_eisenhower(row)
        grid_tasks[r][c].append(row)

    # Render the grid (2x2)
    e_cols = st.columns(2)
    
    for r_idx in range(2):
        for c_idx in range(2):
            with e_cols[c_idx]: # 0 is Left, 1 is Right
                with st.container(border=True):
                    st.markdown(f"### {eisenhower_labels[r_idx][c_idx]}")
                    
                    tasks_in_bucket = grid_tasks[r_idx][c_idx]
                    
                    if tasks_in_bucket:
                        # Sort by Effort (Low effort first = Quickest wins in that quadrant)
                        sorted_tasks = sorted(tasks_in_bucket, key=lambda x: x["Effort (0-10)"])
                        
                        for t in sorted_tasks:
                            effort_val = t["Effort (0-10)"]
                            # Visual cue for effort
                            eff_icon = "🟢" if effort_val < 4 else ("🟡" if effort_val < 8 else "🔴")
                            st.markdown(f"- **{t['Task']}**")
                            st.caption(f"Effort: {effort_val}/10 {eff_icon}")
                    else:
                        st.caption("No tasks")
        
        # Add visual separator between Important (Row 0) and Not Important (Row 1)
        if r_idx == 0:
            st.divider()

else:
    st.info("No tasks to display. Add some tasks in the table on the left!")

# --- Metrics Summary ---
st.divider()
c1, c2, c3 = st.columns(3)

# Use st.session_state.tasks_df instead of edited_df
total_tasks = len(st.session_state.tasks_df)
completed_tasks = len(st.session_state.tasks_df[st.session_state.tasks_df['Status'] == True])
pending_tasks = total_tasks - completed_tasks

c1.metric("Total Tasks", total_tasks)
c2.metric("Pending", pending_tasks)
c3.metric("Completed", completed_tasks)
