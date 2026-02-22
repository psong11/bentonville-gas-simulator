import re
from pathlib import Path

app_path = Path(__file__).parent / 'app.py'

with open(app_path, 'r') as f:
    content = f.read()

# 1. Update CSS - find the closing pattern and add new styles
old_pattern = '''    .stButton>button {
        width: 100%;
    }
    
    /* Sidebar button text - smaller to fit on one line */
    [data-testid="stSidebar"] .stButton>button {
        font-size: 0.8rem;
        padding: 0.4rem 0.5rem;
        white-space: nowrap;
    }
</style>'''

new_pattern = '''    .stButton>button {
        width: 100%;
    }
    
    /* Sidebar button text - smaller to fit on one line */
    [data-testid="stSidebar"] .stButton>button {
        font-size: 0.72rem;
        padding: 0.35rem 0.25rem;
        white-space: nowrap;
    }
    
    /* Darker dividers in sidebar */
    [data-testid="stSidebar"] hr {
        border-color: #555 !important;
        border-width: 2px !important;
    }
    
    /* Map legend text - ensure black text visibility */
    .legend-item {
        color: #000000 !important;
        font-weight: 600;
        padding: 0.2rem 0.5rem;
        background: rgba(255,255,255,0.95);
        border-radius: 4px;
        display: inline-block;
        font-size: 0.9rem;
    }
</style>'''

content = content.replace(old_pattern, new_pattern)

# 2. Update buttons with original labels and help text
replacements = [
    ('st.button("Analyze Network", use_container_width=True, type="primary", key="analyze_main")',
     'st.button("Analyze Network", use_container_width=True, type="primary", key="analyze_main", help="Run intelligent leak detection algorithm to identify potential leaks in the network")'),
    
    ('st.button("Generate", use_container_width=True)',
     'st.button("Generate New", use_container_width=True, help="Create a new randomly generated gas distribution network")'),
    
    ('st.button("Load", use_container_width=True)',
     'st.button("Load Existing", use_container_width=True, help="Load the previously saved network configuration")'),
    
    ('st.button("Add Leak", use_container_width=True)',
     'st.button("Add Leak", use_container_width=True, help="Create a leak at the selected node with specified severity")'),
    
    ('st.button("Clear", use_container_width=True)',
     'st.button("Clear Leaks", use_container_width=True, help="Remove all active leaks and reset the network")'),
    
    ('st.button("Random Leak", use_container_width=True)',
     'st.button("Add Random Leak", use_container_width=True, help="Add a random leak at a random location with random severity")'),
]

for old, new in replacements:
    content = content.replace(old, new)

# 3. Update legend with styled spans - using actual emoji characters
old_legend = '''    # Legend
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown("🔵 **Optimal** (>70%)")
    with col2:
        st.markdown("🟢 **Normal** (50-70%)")
    with col3:
        st.markdown("🟡 **Low** (30-50%)")
    with col4:
        st.markdown("🟠 **Warning** (10-30%)")
    with col5:
        st.markdown("🔴 **Critical** (<10%)")'''

new_legend = '''    # Legend
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown('<span class="legend-item">🔵 <strong>Optimal</strong> (>70%)</span>', unsafe_allow_html=True)
    with col2:
        st.markdown('<span class="legend-item">🟢 <strong>Normal</strong> (50-70%)</span>', unsafe_allow_html=True)
    with col3:
        st.markdown('<span class="legend-item">🟡 <strong>Low</strong> (30-50%)</span>', unsafe_allow_html=True)
    with col4:
        st.markdown('<span class="legend-item">🟠 <strong>Warning</strong> (10-30%)</span>', unsafe_allow_html=True)
    with col5:
        st.markdown('<span class="legend-item">🔴 <strong>Critical</strong> (<10%)</span>', unsafe_allow_html=True)'''

content = content.replace(old_legend, new_legend)

with open(app_path, 'w') as f:
    f.write(content)

print("Updates applied successfully!")
