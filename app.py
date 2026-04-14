import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import folium
from streamlit_folium import folium_static
from streamlit_lottie import st_lottie
import requests

# --- 1. GLOBAL CONFIG & THEME ---
st.set_page_config(
    page_title="BrickView Pro | Real Estate Analytics",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Professional Styling - Fixed for Visibility & Dark Mode
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    /* Fix for Executive Dashboard Summary Metric Visibility */
    [data-testid="stMetricValue"] { color: #1c2e4a !important; font-weight: bold; }
    [data-testid="stMetricLabel"] { color: #555555 !important; }
    .stMetric { 
        background-color: #ffffff; 
        padding: 20px; 
        border-radius: 12px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
        border: 1px solid #dee2e6; 
    }
    /* Fix for Navigation Sidebar */
    [data-testid="stSidebar"] { background-color: #1c2e4a !important; }
    [data-testid="stSidebar"] * { color: white !important; }
    /* Fix for CRUD Tabs visibility */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; 
        background-color: #e9ecef; 
        border-radius: 5px; 
        color: #1c2e4a !important; 
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #007bff !important; 
        color: white !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE UTILITIES ---
DB_PATH = 'db/brickview_manual.db'

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def run_query(query, params=()):
    try:
        with get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        return pd.DataFrame()

def execute_sql(query, params=()):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"❌ Database Error: {e}")
        return False

@st.cache_data(ttl=3600)
def load_lottieurl(url):
    try:
        r = requests.get(url)
        return r.json() if r.status_code == 200 else None
    except:
        return None

# --- 3. NAVIGATION ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/609/609803.png", width=70)
    st.title("BrickView Pro")
    menu = st.radio("MAIN NAVIGATION", [
        "🏠 Welcome Home", 
        "🔍 Market Explorer", 
        "📊 Analytics Hub", 
        "🛠️ Data Management", 
        "📚 FAQ (SQL Queries)", 
        "👤 About Developer"
    ])
    st.markdown("---")
    st.info("System Status: Online ✅")

# --- PAGE 1: INTRODUCTION ---
if menu == "🏠 Welcome Home":
    st.title("Real Estate Intelligence Reimagined 🏙️")
    
    lottie_house = load_lottieurl("https://lottie.host/7906663d-4c74-4537-8f55-7d84f88102a9/fJ6fW8YdYk.json")
    if lottie_house:
        st_lottie(lottie_house, height=250, key="home_lottie")

    st.subheader("Executive Dashboard Summary")
    # To add an image here as requested:
    st.image("https://images.unsplash.com/photo-1554469384-e58fac16e23a?auto=format&fit=crop&w=1200&q=80", caption="Global Real Estate Trends")
    
    c1, c2, c3, c4 = st.columns(4)
    res_list = run_query("SELECT COUNT(*) FROM Listings")
    total_listings = res_list.iloc[0,0] if not res_list.empty else 0
    
    avg_price = run_query("SELECT AVG(Price) FROM Listings").iloc[0,0] or 0
    sold_count = run_query("SELECT COUNT(*) FROM Sales").iloc[0,0] or 0
    revenue = run_query("SELECT SUM(sale_price) FROM Sales").iloc[0,0] or 0

    c1.metric("Total Listings", f"{total_listings:,}")
    c2.metric("Avg Price", f"${avg_price:,.0f}")
    c3.metric("Properties Sold", f"{sold_count:,}")
    c4.metric("Total Revenue", f"${revenue:,.0f}")

# --- PAGE 2: EXPLORE & FILTERS ---
elif menu == "🔍 Market Explorer":
    st.title("🔍 Advanced Property Search")
    with st.container(border=True):
        f1, f2, f3 = st.columns(3)
        cities = run_query("SELECT DISTINCT City FROM Listings")['City'].tolist()
        sel_cities = f1.multiselect("Filter Cities", cities, default=cities[:3])
        p_types = run_query("SELECT DISTINCT Property_Type FROM Listings")['Property_Type'].tolist()
        sel_type = f2.selectbox("Property Type", ["All Categories"] + p_types)
        price_range = f3.slider("Price Range ($)", 0, 5000000, (0, 2000000))

    query = "SELECT * FROM Listings WHERE City IN ({}) AND Price BETWEEN ? AND ?".format(','.join(['?']*len(sel_cities)))
    params = tuple(sel_cities) + price_range
    if sel_type != "All Categories":
        query += " AND Property_Type = ?"
        params += (sel_type,)
    
    df_f = run_query(query, params)
    st.dataframe(df_f, use_container_width=True)

# --- PAGE 4: VISUALIZATIONS ---
# --- PAGE 4: VISUALIZATIONS ---
elif menu == "📊 Analytics Hub":
    st.title("📊 Strategic Market Analysis")
    
    # 1. GEOSPATIAL MAP (Hover enabled)
    st.subheader("📍 Property Geospatial Distribution")
    st.caption("🔵 Apartment | 🟢 House | 🔴 Condo | 🟠 Townhouse | 🟣 Villa")
    
    map_df = run_query("SELECT Latitude, Longitude, City, Property_Type, Price FROM Listings LIMIT 500")
    if not map_df.empty:
        # Calculate center point
        m = folium.Map(location=[map_df['Latitude'].mean(), map_df['Longitude'].mean()], zoom_start=4, tiles="CartoDB Positron")
        colors = {"Apartment": "blue", "House": "green", "Condo": "red", "Townhouse": "orange", "Villa": "purple"}
        
        for _, row in map_df.iterrows():
            # EXACT FORMAT REQUESTED: Hover information
            hover_text = f"""
            City: "{row['City']}"<br>
            Price: "{row['Price']}"<br>
            Latitude: "{row['Latitude']}"<br>
            Longitude: "{row['Longitude']}"
            """
            
            folium.CircleMarker(
                location=[row['Latitude'], row['Longitude']],
                radius=7,
                color=colors.get(row['Property_Type'], "gray"),
                fill=True,
                fill_opacity=0.8,
                tooltip=folium.Tooltip(hover_text) # Hover interaction
            ).add_to(m)
        folium_static(m, width=1200)

    st.markdown("---")
    
    # ROW 1: PRICING & INVENTORY
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("💰 1. Avg Price by City")
        df_city = run_query("SELECT City, AVG(Price) as Price FROM Listings GROUP BY 1 ORDER BY Price DESC")
        st.plotly_chart(px.bar(df_city, x='City', y='Price', color='Price', template="plotly_white"), use_container_width=True)
    
    with col2:
        st.subheader("🏡 2. Property Type Distribution")
        df_type = run_query("SELECT Property_Type, COUNT(*) as Count FROM Listings GROUP BY 1")
        st.plotly_chart(px.pie(df_type, names='Property_Type', values='Count', hole=0.5, 
                             color_discrete_sequence=px.colors.sequential.RdBu), use_container_width=True)

    # ROW 2: SALES & PERFORMANCE
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("📈 3. Monthly Sales Trends")
        df_sales = run_query("SELECT strftime('%Y-%m', date_sold) as Month, COUNT(*) as Sales FROM Sales GROUP BY 1 ORDER BY 1")
        st.plotly_chart(px.line(df_sales, x='Month', y='Sales', markers=True, line_shape="spline"), use_container_width=True)
        
    with col4:
        st.subheader("🏆 4. Top 10 Agents by Deals Closed")
        df_agents = run_query("""
            SELECT a.Name, COUNT(s.Sale_ID) as Deals 
            FROM Agents a 
            JOIN Listings l ON a.Agent_ID = l.Agent_ID 
            JOIN Sales s ON l.Listing_ID = s.listing_id 
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """)
        st.plotly_chart(px.bar(df_agents, x='Deals', y='Name', orientation='h', color='Deals'), use_container_width=True)

    # ROW 3: BUYER BEHAVIOR
    st.markdown("---")
    st.subheader("💳 5. Buyer Payment Mode Distribution")
    df_payment = run_query("SELECT payment_mode, COUNT(*) as Count FROM Buyers GROUP BY 1 ORDER BY 2 DESC")
    st.plotly_chart(px.bar(df_payment, x='payment_mode', y='Count', color='payment_mode', 
                         title="Primary Transaction Methods"), use_container_width=True)

# --- PAGE 5: CRUD ---
elif menu == "🛠️ Data Management":
    st.title("🛠️ Database Administrative Controls")
    table = st.selectbox("Select Target Table", ["Agents", "Listings", "Buyers", "Sales"])
    t_view, t_add, t_upd, t_del = st.tabs(["📖 View", "➕ Add", "🔄 Update", "❌ Delete"])

    with t_view:
        st.dataframe(run_query(f"SELECT * FROM {table} LIMIT 100"), use_container_width=True)
    
    with t_add:
        st.write(f"Add New {table} Record")
        if table == "Agents":
            with st.form("add_a"):
                a1, a2 = st.columns(2)
                id = a1.text_input("Agent ID")
                name = a2.text_input("Name")
                email = a1.text_input("Email")
                if st.form_submit_button("Submit"):
                    execute_sql("INSERT INTO Agents (Agent_ID, Name, Email) VALUES (?,?,?)", (id, name, email))
                    st.toast("Record Added!")

# --- PAGE 6: FAQ (SQL Queries) ---
elif menu == "📚 FAQ (SQL Queries)":
    st.title("📚 SQL FAQ Explorer")
    
    categories = {
        "Property & Pricing Analysis (1-10)": [
            ("1. Avg listing price by city", "SELECT City, ROUND(AVG(Price), 2) FROM Listings GROUP BY City"),
            ("2. Avg price per sqft by type", "SELECT Property_Type, ROUND(AVG(Price/Sqft), 2) FROM Listings GROUP BY Property_Type"),
            ("3. Furnishing impact on price", "SELECT pa.furnishing_status, AVG(l.Price) FROM Listings l JOIN Property_Attributes pa ON l.Listing_ID = pa.listing_id GROUP BY 1"),
            ("4. Metro proximity vs price", "SELECT CASE WHEN metro_distance_km < 2 THEN 'Near' ELSE 'Far' END as Metro, AVG(Price) FROM Listings l JOIN Property_Attributes pa ON l.Listing_ID = pa.listing_id GROUP BY 1"),
            ("5. Rented vs Non-rented prices", "SELECT is_rented, AVG(Price) FROM Listings l JOIN Property_Attributes pa ON l.Listing_ID = pa.listing_id GROUP BY 1"),
            ("6. Bed/Bath impact", "SELECT bedrooms, bathrooms, AVG(Price) FROM Listings l JOIN Property_Attributes pa ON l.Listing_ID = pa.listing_id GROUP BY 1, 2"),
            ("7. Parking & Power Backup", "SELECT parking_available, power_backup, AVG(Price) FROM Listings l JOIN Property_Attributes pa ON l.Listing_ID = pa.listing_id GROUP BY 1, 2"),
            ("8. Year built influence", "SELECT year_built, AVG(Price) FROM Listings l JOIN Property_Attributes pa ON l.Listing_ID = pa.listing_id GROUP BY 1"),
            ("9. Cities with highest median", "SELECT City, Price FROM Listings GROUP BY City ORDER BY Price DESC"),
            ("10. Price bucket distribution", "SELECT CASE WHEN Price < 500000 THEN 'Budget' ELSE 'Luxury' END, COUNT(*) FROM Listings GROUP BY 1")
        ],
        "Sales & Market Performance (11-18)": [
            ("11. Avg days on market by city", "SELECT l.City, AVG(s.days_on_market) FROM Listings l JOIN Sales s ON l.Listing_ID = s.listing_id GROUP BY 1"),
            ("12. Fastest selling property types", "SELECT l.Property_Type, AVG(s.days_on_market) as DOM FROM Listings l JOIN Sales s ON l.Listing_ID = s.listing_id GROUP BY 1 ORDER BY DOM ASC"),
            ("13. % Sold above list price", "SELECT (COUNT(CASE WHEN s.sale_price > l.Price THEN 1 END)*100.0/COUNT(*)) FROM Sales s JOIN Listings l ON s.listing_id = l.Listing_ID")
        ],
        "Agent Performance (19-25)": [
            ("19. Most sales closed", "SELECT a.Name, COUNT(s.Sale_ID) FROM Agents a JOIN Listings l ON a.Agent_ID = l.Agent_ID JOIN Sales s ON l.Listing_ID = s.listing_id GROUP BY 1 ORDER BY 2 DESC"),
            ("20. Top agents by revenue", "SELECT a.Name, SUM(s.sale_price) FROM Agents a JOIN Listings l ON a.Agent_ID = l.Agent_ID JOIN Sales s ON l.Listing_ID = s.listing_id GROUP BY 1 ORDER BY 2 DESC")
        ],
        "Buyer & Financing Behavior (26-30)": [
            ("26. Investor vs End User %", "SELECT buyer_type, COUNT(*)*100.0/(SELECT COUNT(*) FROM Buyers) FROM Buyers GROUP BY 1"),
            ("29. Most common payment mode", "SELECT payment_mode, COUNT(*) FROM Buyers GROUP BY 1 ORDER BY 2 DESC")
        ]
    }
    
    sel_cat = st.selectbox("1. Select Category", list(categories.keys()))
    q_pairs = categories[sel_cat]
    sel_q_label = st.selectbox("2. Select Question", [p[0] for p in q_pairs])
    
    # Get the SQL for the chosen label
    actual_sql = next(p[1] for p in q_pairs if p[0] == sel_q_label)
    
    st.code(actual_sql, language="sql")
    st.table(run_query(actual_sql))

# --- PAGE 7: ABOUT ---
elif menu == "👤 About Developer":
    st.title("👤 About Me")
    c1, c2 = st.columns([1, 2])
    c1.image("https://ui-avatars.com/api/?name=Aryaman+Bhatnagar&size=200&background=1c2e4a&color=fff")
    with c2:
        st.header("Aryaman Bhatnagar")
        st.subheader("Computer Science Engineer")
        st.write("📍 Greater Noida, Uttar Pradesh")
        st.write("📧 aryamanbhatnagar2273@gmail.com")
        st.write("📞 +91 9461048675")
        st.markdown("---")
        st.write("Engineering graduate specializing in AI and Data Analytics, passionate about building high-performance SQL-driven dashboards.")