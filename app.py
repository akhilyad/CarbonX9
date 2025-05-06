import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import folium_static
import uuid
import math
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import streamlit.components.v1 as components

# Initialize SQLite database
def init_db():
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS suppliers 
                        (id TEXT PRIMARY KEY, supplier_name TEXT, country TEXT, city TEXT, 
                         material TEXT, green_score INTEGER, annual_capacity_tons INTEGER, 
                         sustainable_practices TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS emissions 
                        (id TEXT PRIMARY KEY, source TEXT, destination TEXT, 
                         transport_mode TEXT, distance_km REAL, co2_kg REAL, 
                         weight_tons REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS packaging 
                        (id TEXT PRIMARY KEY, material_type TEXT, weight_kg REAL, 
                         co2_kg REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS offsets 
                        (id TEXT PRIMARY KEY, project_type TEXT, co2_offset_tons REAL, 
                         cost_usd REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            sample_suppliers = [
                (str(uuid.uuid4()), 'UK Steel Co', 'United Kingdom', 'London', 'Steel', 85, 50000, 'Renewable energy'),
                (str(uuid.uuid4()), 'London Tech Supplies', 'United Kingdom', 'London', 'Electronics', 70, 20000, 'Recycling'),
                (str(uuid.uuid4()), 'Nippon Steel', 'Japan', 'Tokyo', 'Steel', 80, 55000, 'Renewable energy'),
                (str(uuid.uuid4()), 'China Steel Group', 'China', 'Shanghai', 'Steel', 65, 80000, 'Energy-efficient manufacturing'),
                (str(uuid.uuid4()), 'American Steel Corp', 'United States', 'New York', 'Steel', 75, 60000, 'Renewable energy'),
            ]
            c.executemany('INSERT OR IGNORE INTO suppliers VALUES (?, ?, ?, ?, ?, ?, ?, ?)', sample_suppliers)
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

# DEFRA-based emission factors (kg CO₂ per km per ton)
EMISSION_FACTORS = {
    'Truck': 0.096, 'Train': 0.028, 'Ship': 0.016, 'Plane': 0.602,
    'Electric Truck': 0.020, 'Biofuel Truck': 0.050, 'Hydrogen Truck': 0.010
}

# Expanded country-city structure with coordinates (latitude, longitude)
LOCATIONS = {
    # Africa
    'Nigeria': {
        'Lagos': (6.5244, 3.3792), 'Abuja': (9.0579, 7.4951), 'Kano': (12.0001, 8.5167),
        'Ibadan': (7.3775, 3.9059), 'Port Harcourt': (4.8156, 7.0498), 'Benin City': (6.3350, 5.6037),
        'Kaduna': (10.5015, 7.4408), 'Enugu': (6.4584, 7.5464), 'Jos': (9.8965, 8.8583),
        'Owerri': (5.4836, 7.0353)
    },
    'South Africa': {
        'Johannesburg': (-26.2041, 28.0473), 'Cape Town': (-33.9249, 18.4241), 'Durban': (-29.8587, 31.0218),
        'Pretoria': (-25.7479, 28.2293), 'Port Elizabeth': (-33.9608, 25.6022), 'Bloemfontein': (-29.0852, 26.1596),
        'East London': (-33.0153, 27.9116), 'Nelspruit': (-25.4753, 30.9694), 'Kimberley': (-28.7323, 24.7623),
        'Polokwane': (-23.9045, 29.4689)
    },
    'Kenya': {
        'Nairobi': (-1.286389, 36.817223), 'Mombasa': (-4.0435, 39.6682), 'Kisumu': (-0.1022, 34.7617),
        'Nakuru': (-0.3031, 36.0800), 'Eldoret': (0.5204, 35.2698), 'Nyeri': (-0.4201, 36.9476),
        'Machakos': (-1.5201, 37.2634), 'Thika': (-1.0388, 37.0834), 'Meru': (0.0470, 37.6498),
        'Garissa': (-0.4536, 39.6460)
    },
    'Egypt': {
        'Cairo': (30.0444, 31.2357), 'Alexandria': (31.2001, 29.9187), 'Giza': (30.0131, 31.2089),
        'Luxor': (25.6872, 32.6396), 'Aswan': (24.0889, 32.8998), 'Hurghada': (27.2579, 33.8116),
        'Sharm El Sheikh': (27.9158, 34.3299), 'Mansoura': (31.0409, 31.3785), 'Tanta': (30.7833, 31.0000),
        'Port Said': (31.2653, 32.3019)
    },
    'Algeria': {
        'Algiers': (36.7372, 3.0870), 'Oran': (35.6977, -0.6308), 'Constantine': (36.3650, 6.6147),
        'Annaba': (36.9000, 7.7667), 'Blida': (36.4800, 2.8300), 'Sétif': (36.1911, 5.4137),
        'Tlemcen': (34.8783, -1.3150), 'Béjaïa': (36.7559, 5.0843), 'Batna': (35.5560, 6.1741),
        'Djelfa': (34.6728, 3.2630)
    },
    'Ghana': {
        'Accra': (5.6037, -0.1870), 'Kumasi': (6.6885, -1.6244), 'Tamale': (9.4008, -0.8393),
        'Takoradi': (4.9016, -1.7831), 'Cape Coast': (5.1315, -1.2798), 'Tema': (5.6698, -0.0166),
        'Koforidua': (6.0933, -0.2591), 'Wa': (10.0607, -2.5019), 'Ho': (6.6105, 0.4703),
        'Sunyani': (7.3349, -2.3123)
    },
    'Morocco': {
        'Casablanca': (33.5731, -7.5898), 'Rabat': (34.0209, -6.8416), 'Marrakech': (31.6295, -7.9811),
        'Fes': (34.0181, -5.0078), 'Tangier': (35.7673, -5.7999), 'Agadir': (30.4278, -9.5982),
        'Meknes': (33.8935, -5.5471), 'Oujda': (34.6867, -1.9114), 'Kenitra': (34.2610, -6.5802),
        'Tetouan': (35.5784, -5.3684)
    },
    'Ethiopia': {
        'Addis Ababa': (9.0084, 38.7648), 'Dire Dawa': (9.6008, 41.8501), 'Mekele': (13.4967, 39.4753),
        'Gondar': (12.6000, 37.4667), 'Adama': (8.5263, 39.2583), 'Hawassa': (7.0463, 38.4958),
        'Bahir Dar': (11.5850, 37.3826), 'Jimma': (7.6738, 36.8358), 'Dessie': (11.1270, 39.6363),
        'Jijiga': (9.3568, 42.7955)
    },
    'Tunisia': {
        'Tunis': (36.8065, 10.1815), 'Sfax': (34.7406, 10.7603), 'Sousse': (35.8256, 10.6412),
        'Kairouan': (35.6781, 10.0963), 'Bizerte': (37.2744, 9.8739), 'Gabès': (33.8815, 10.0982),
        'Gafsa': (34.4250, 8.7842), 'Monastir': (35.7833, 10.8333), 'Ben Arous': (36.7531, 10.2189),
        'Ariana': (36.8667, 10.1833)
    },
    'Uganda': {
        'Kampala': (0.3476, 32.5825), 'Gulu': (2.7746, 32.2990), 'Lira': (2.2581, 32.8874),
        'Mbale': (1.0784, 34.1750), 'Jinja': (0.4478, 33.2026), 'Mbarara': (-0.6047, 30.6545),
        'Masaka': (-0.3411, 31.7361), 'Entebbe': (0.0562, 32.4795), 'Fort Portal': (0.6617, 30.2748),
        'Arua': (3.0201, 30.9111)
    },
    # Asia
    'China': {
        'Shanghai': (31.2304, 121.4737), 'Beijing': (39.9042, 116.4074), 'Guangzhou': (23.1291, 113.2644),
        'Shenzhen': (22.5431, 114.0579), 'Chengdu': (30.5728, 104.0668), 'Wuhan': (30.5928, 114.3055),
        'Xi’an': (34.3416, 108.9398), 'Chongqing': (29.5637, 106.5516), 'Hangzhou': (30.2741, 120.1551),
        'Nanjing': (32.0603, 118.7969)
    },
    'India': {
        'Mumbai': (19.0760, 72.8777), 'Delhi': (28.7041, 77.1025), 'Bangalore': (12.9716, 77.5946),
        'Hyderabad': (17.3850, 78.4867), 'Chennai': (13.0827, 80.2707), 'Kolkata': (22.5726, 88.3639),
        'Ahmedabad': (23.0225, 72.5714), 'Pune': (18.5204, 73.8567), 'Jaipur': (26.9124, 75.7873),
        'Surat': (21.1702, 72.8311)
    },
    'Japan': {
        'Tokyo': (35.6762, 139.650 ), 'Osaka': (34.6937, 135.5023), 'Yokohama': (35.4437, 139.6380),
        'Nagoya': (35.1815, 136.9066), 'Sapporo': (43.0618, 141.3545), 'Kobe': (34.6901, 135.1956),
        'Kyoto': (35.0116, 135.7681), 'Fukuoka': (33.5904, 130.4017), 'Hiroshima': (34.3853, 132.4553),
        'Sendai': (38.2682, 140.8694)
    },
    'South Korea': {
        'Seoul': (37.5665, 126.9780), 'Busan': (35.1796, 129.0756), 'Incheon': (37.4563, 126.7052),
        'Daegu': (35.8714, 128.6018), 'Daejeon': (36.3504, 127.3845), 'Gwangju': (35.1595, 126.8526),
        'Suwon': (37.2636, 127.0286), 'Ulsan': (35.5384, 129.3115), 'Changwon': (35.2281, 128.6811),
        'Jeonju': (35.8242, 127.1479)
    },
    'Indonesia': {
        'Jakarta': (-6.2088, 106.8456), 'Surabaya': (-7.2575, 112.7521), 'Bandung': (-6.9175, 107.6191),
        'Medan': (3.5952, 98.6722), 'Semarang': (-6.9667, 110.4167), 'Palembang': (-2.9167, 104.7458),
        'Makassar': (-5.1477, 119.4327), 'Yogyakarta': (-7.7956, 110.3695), 'Denpasar': (-8.6705, 115.2126),
        'Malang': (-7.9667, 112.6167)
    },
    'Pakistan': {
        'Karachi': (24.8607, 67.0011), 'Lahore': (31.5204, 74.3587), 'Faisalabad': (31.4504, 73.1350),
        'Rawalpindi': (33.5651, 73.0169), 'Multan': (30.1575, 71.5249), 'Hyderabad': (25.3960, 68.3578),
        'Gujranwala': (32.1877, 74.1945), 'Peshawar': (34.0151, 71.5249), 'Quetta': (30.1830, 67.0014),
        'Islamabad': (33.6844, 73.0479)
    },
    'Bangladesh': {
        'Dhaka': (23.8103, 90.4125), 'Chittagong': (22.3569, 91.7832), 'Khulna': (22.8456, 89.5403),
        'Rajshahi': (24.3745, 88.6042), 'Sylhet': (24.8949, 91.8687), 'Barisal': (22.7010, 90.3535),
        'Rangpur': (25.7439, 89.2752), 'Comilla': (23.4682, 91.1850), 'Narayanganj': (23.6238, 90.4980),
        'Gazipur': (23.9999, 90.4203)
    },
    'Vietnam': {
        'Ho Chi Minh City': (10.8231, 106.6297), 'Hanoi': (21.0278, 105.8342), 'Da Nang': (16.0545, 108.2022),
        'Hai Phong': (20.8449, 106.6881), 'Can Tho': (10.0452, 105.7469), 'Nha Trang': (12.2388, 109.1967),
        'Hue': (16.4637, 107.5848), 'Vung Tau': (10.3460, 107.0842), 'Bien Hoa': (10.9574, 106.8427),
        'Thai Nguyen': (21.5672, 105.8252)
    },
    'Thailand': {
        'Bangkok': (13.7563, 100.5018), 'Chiang Mai': (18.7883, 98.9853), 'Pattaya': (12.9236, 100.8825),
        'Phuket': (7.8804, 98.3923), 'Hat Yai': (7.0084, 100.4747), 'Khon Kaen': (16.4322, 102.8230),
        'Udon Thani': (17.3647, 102.8158), 'Nakhon Ratchasima': (14.9738, 102.0839), 'Surat Thani': (9.1381, 99.3218),
        'Chiang Rai': (19.9086, 99.8325)
    },
    'Malaysia': {
        'Kuala Lumpur': (3.1390, 101.6869), 'George Town': (5.4141, 100.3354), 'Johor Bahru': (1.4927, 103.7414),
        'Ipoh': (4.5975, 101.0751), 'Kota Kinabalu': (5.9749, 116.0724), 'Malacca City': (2.1896, 102.2501),
        'Alor Setar': (6.1248, 100.3678), 'Kuantan': (3.8077, 103.3260), 'Shah Alam': (3.0738, 101.5185),
        'Seremban': (2.7297, 101.9378)
    },
    # Europe
    'United Kingdom': {
        'London': (51.5074, -0.1278), 'Manchester': (53.4808, -2.2426), 'Birmingham': (52.4862, -1.8904),
        'Glasgow': (55.8642, -4.2518), 'Liverpool': (53.4084, -2.9916), 'Bristol': (51.4545, -2.5879),
        'Sheffield': (53.3811, -1.4701), 'Leeds': (53.8008, -1.5491), 'Edinburgh': (55.9533, -3.1883),
        'Newcastle': (54.9783, -1.6174)
    },
    'France': {
        'Paris': (48.8566, 2.3522), 'Marseille': (43.2965, 5.3698), 'Lyon': (45.7640, 4.8357),
        'Toulouse': (43.6047, 1.4442), 'Nice': (43.7102, 7.2620), 'Nantes': (47.2184, -1.5536),
        'Strasbourg': (48.5734, 7.7521), 'Montpellier': (43.6108, 3.8767), 'Bordeaux': (44.8378, -0.5792),
        'Lille': (50.6292, 3.0573)
    },
    'Germany': {
        'Berlin': (52.5200, 13.4050), 'Hamburg': (53.5511, 9.9937), 'Munich': (48.1351, 11.5820),
        'Cologne': (50.9375, 6.9603), 'Frankfurt': (50.1109, 8.6821), 'Stuttgart': (48.7758, 9.1829),
        'Düsseldorf': (51.2277, 6.7735), 'Dortmund': (51.5136, 7.4653), 'Essen': (51.4556, 7.0116),
        'Leipzig': (51.3397, 12.3731)
    },
    'Italy': {
        'Rome': (41.9028, 12.4964), 'Milan': (45.4642, 9.1900), 'Naples': (40.8518, 14.2681),
        'Turin': (45.0703, 7.6869), 'Palermo': (38.1157, 13.3615), 'Genoa': (44.4056, 8.9463),
        'Bologna': (44.4949, 11.3426), 'Florence': (43.7696, 11.2558), 'Bari': (41.1171, 16.8719),
        'Catania': (37.5079, 15.0830)
    },
    'Spain': {
        'Madrid': (40.4168, -3.7038), 'Barcelona': (41.3851, 2.1734), 'Valencia': (39.4699, -0.3763),
        'Seville': (37.3891, -5.9845), 'Zaragoza': (41.6488, -0.8891), 'Málaga': (36.7213, -4.4213),
        'Murcia': (37.9922, -1.1307), 'Palma': (39.5696, 2.6502), 'Las Palmas': (28.1235, -15.4365),
        'Bilbao': (43.2630, -2.9350)
    },
    'Poland': {
        'Warsaw': (52.2297, 21.0122), 'Kraków': (50.0647, 19.9450), 'Łódź': (51.7592, 19.4550),
        'Wrocław': (51.1079, 17.0385), 'Poznań': (52.4064, 16.9252), 'Gdańsk': (54.3520, 18.6466),
        'Szczecin': (53.4285, 14.5528), 'Bydgoszcz': (53.1235, 18.0084), 'Lublin': (51.2465, 22.5684),
        'Katowice': (50.2649, 19.0238)
    },
    'Netherlands': {
        'Amsterdam': (52.3676, 4.9041), 'Rotterdam': (51.9244, 4.4777), 'The Hague': (52.0705, 4.3007),
        'Utrecht': (52.0907, 5.1214), 'Eindhoven': (51.4416, 5.4697), 'Tilburg': (51.5558, 5.0913),
        'Groningen': (53.2194, 6.5665), 'Almere': (52.3508, 5.2647), 'Breda': (51.5866, 4.7760),
        'Nijmegen': (51.8424, 5.8546)
    },
    'Sweden': {
        'Stockholm': (59.3293, 18.0686), 'Gothenburg': (57.7089, 11.9746), 'Malmö': (55.6050, 13.0007),
        'Uppsala': (59.8586, 17.6389), 'Linköping': (58.4108, 15.6214), 'Västerås': (59.6099, 16.5448),
        'Örebro': (59.2793, 15.2134), 'Norrköping': (58.5877, 16.1921), 'Helsingborg': (56.0465, 12.6940),
        'Jönköping': (57.7810, 14.1618)
    },
    'Belgium': {
        'Brussels': (50.8503, 4.3517), 'Antwerp': (51.2213, 4.4051), 'Ghent': (51.0543, 3.7174),
        'Charleroi': (50.4112, 4.4446), 'Liège': (50.6326, 5.5797), 'Bruges': (51.2091, 3.2247),
        'Namur': (50.4674, 4.8712), 'Leuven': (50.8790, 4.7009), 'Mons': (50.4542, 3.9519),
        'Aalst': (50.9360, 4.0390)
    },
    'Austria': {
        'Vienna': (48.2082, 16.3738), 'Graz': (47.0707, 15.4395), 'Linz': (48.3069, 14.2858),
        'Salzburg': (47.8095, 13.0550), 'Innsbruck': (47.2684, 11.4041), 'Klagenfurt': (46.6365, 14.3122),
        'Villach': (46.6101, 13.8558), 'Wels': (48.1667, 14.0333), 'Sankt Pölten': (48.2048, 15.6233),
        'Dornbirn': (47.4133, 9.7438)
    },
    # North America
    'United States': {
        'New York': (40.7128, -74.0060), 'Los Angeles': (34.0522, -118.2437), 'Chicago': (41.8781, -87.6298),
        'Houston': (29.7604, -95.3698), 'Phoenix': (33.4484, -112.0740), 'Philadelphia': (39.9526, -75.1652),
        'San Antonio': (29.4241, -98.4936), 'San Diego': (32.7157, -117.1611), 'Dallas': (32.7767, -96.7970),
        'San Jose': (37.3382, -121.8863)
    },
    'Canada': {
        'Toronto': (43.6532, -79.3832), 'Montreal': (45.5017, -73.5673), 'Vancouver': (49.2827, -123.1207),
        'Calgary': (51.0447, -114.0719), 'Edmonton': (53.5461, -113.4938), 'Ottawa': (45.4215, -75.6972),
        'Winnipeg': (49.8951, -97.1384), 'Quebec City': (46.8139, -71.2080), 'Hamilton': (43.2557, -79.8711),
        'Halifax': (44.6488, -63.5752)
    },
    'Mexico': {
        'Mexico City': (19.4326, -99.1332), 'Guadalajara': (20.6597, -103.3357), 'Monterrey': (25.6866, -100.3161),
        'Puebla': (19.0414, -98.2063), 'Tijuana': (32.5149, -117.0382), 'León': (21.1250, -101.6850),
        'Juárez': (31.7202, -106.4608), 'Zapopan': (20.7206, -103.3918), 'Mérida': (20.9674, -89.5926),
        'Querétaro': (20.5888, -100.3899)
    },
    'Cuba': {
        'Havana': (23.1136, -82.3666), 'Santiago de Cuba': (20.0218, -75.8290), 'Camagüey': (21.3859, -77.9137),
        'Holguín': (20.8872, -76.2631), 'Santa Clara': (22.4053, -79.9447), 'Guantánamo': (20.1444, -75.2092),
        'Cienfuegos': (22.1461, -80.4356), 'Matanzas': (23.0411, -81.5771), 'Pinar del Río': (22.4167, -83.6967),
        'Bayamo': (20.3742, -76.6436)
    },
    'Guatemala': {
        'Guatemala City': (14.6349, -90.5069), 'Mixco': (14.6308, -90.6071), 'Villa Nueva': (14.5251, -90.5854),
        'Quetzaltenango': (14.8362, -91.5211), 'San Miguel Petapa': (14.5199, -90.5608), 'Escuintla': (14.3009, -90.7858),
        'San Juan Sacatepéquez': (14.7189, -90.6427), 'Chimaltenango': (14.6611, -90.8248), 'Huehuetenango': (15.3147, -91.4768),
        'Cobán': (15.4710, -90.3708)
    },
    'Costa Rica': {
        'San José': (9.9281, -84.0907), 'Alajuela': (10.0160, -84.2116), 'Cartago': (9.8644, -83.9194),
        'Heredia': (10.0024, -84.1165), 'Puntarenas': (9.9702, -84.8339), 'Limón': (9.9913, -83.0360),
        'Liberia': (10.6350, -85.4377), 'San Isidro': (9.3741, -83.6971), 'Quesada': (10.3238, -84.4271),
        'Desamparados': (9.8984, -84.0640)
    },
    'Panama': {
        'Panama City': (8.9824, -79.5199), 'San Miguelito': (9.0503, -79.4707), 'Colón': (9.3593, -79.9001),
        'David': (8.4273, -82.4308), 'La Chorrera': (8.8827, -79.7834), 'Santiago': (8.0961, -80.9749),
        'Penonomé': (8.5189, -80.3559), 'Chitré': (7.9647, -80.4293), 'Las Tablas': (7.7758, -80.2748),
        'Bocas del Toro': (9.3403, -82.2420)
    },
    'Honduras': {
        'Tegucigalpa': (14.0723, -87.1921), 'San Pedro Sula': (15.5042, -88.0250), 'Choloma': (15.6144, -87.9530),
        'La Ceiba': (15.7635, -86.7965), 'El Progreso': (15.4000, -87.8000), 'Comayagua': (14.4514, -87.6375),
        'Puerto Cortés': (15.8256, -87.9286), 'Juticalpa': (14.6667, -86.2194), 'Siguatepeque': (14.5982, -87.8310),
        'Tocoa': (15.6833, -86.0000)
    },
    'El Salvador': {
        'San Salvador': (13.6929, -89.2182), 'Santa Ana': (13.9778, -89.5596), 'San Miguel': (13.4833, -88.1833),
        'Soyapango': (13.7347, -89.1397), 'Mejicanos': (13.7403, -89.2131), 'Apopa': (13.8000, -89.1792),
        'Delgado': (13.7217, -89.1687), 'Ahuachapán': (13.9214, -89.8450), 'Sonsonate': (13.7189, -89.7243),
        'Usulután': (13.3500, -88.4500)
    },
    'Nicaragua': {
        'Managua': (12.1140, -86.2362), 'León': (12.4379, -86.8780), 'Masaya': (11.9744, -86.0941),
        'Chinandega': (12.6294, -87.1311), 'Matagalpa': (12.9256, -85.9175), 'Estelí': (13.0919, -86.3538),
        'Granada': (11.9299, -85.9562), 'Jinotega': (13.0910, -86.0023), 'Bluefields': (12.0137, -83.7635),
        'Juigalpa': (12.1063, -85.3645)
    },
    # South America
    'Brazil': {
        'São Paulo': (-23.5505, -46.6333), 'Rio de Janeiro': (-22.9068, -43.1729), 'Brasília': (-15.8267, -47.9218),
        'Salvador': (-12.9714, -38.5014), 'Fortaleza': (-3.7172, -38.5434), 'Belo Horizonte': (-19.9167, -43.9345),
        'Manaus': (-3.1190, -60.0217), 'Curitiba': (-25.4284, -49.2731), 'Recife': (-8.0476, -34.8770),
        'Porto Alegre': (-30.0346, -51.2177)
    },
    'Argentina': {
        'Buenos Aires': (-34.6037, -58.3816), 'Córdoba': (-31.4201, -64.1888), 'Rosario': (-32.9468, -60.6393),
        'Mendoza': (-32.8895, -68.8458), 'La Plata': (-34.9205, -57.9534), 'Tucumán': (-26.8083, -65.2176),
        'Mar del Plata': (-38.0055, -57.5426), 'Salta': (-24.7821, -65.4232), 'Santa Fe': (-31.6107, -60.6973),
        'San Juan': (-31.5351, -68.5386)
    },
    'Chile': {
        'Santiago': (-33.4489, -70.6693), 'Valparaíso': (-33.0472, -71.6127), 'Concepción': (-36.8201, -73.0443),
        'La Serena': (-29.9045, -71.2489), 'Antofagasta': (-23.6524, -70.3954), 'Temuco': (-38.7359, -72.5904),
        'Rancagua': (-34.1708, -70.7444), 'Talca': (-35.4264, -71.6656), 'Arica': (-18.4783, -70.3126),
        'Puerto Montt': (-41.4689, -72.9411)
    },
    'Colombia': {
        'Bogotá': (4.7110, -74.0721), 'Medellín': (6.2442, -75.5812), 'Cali': (3.4516, -76.5320),
        'Barranquilla': (11.0041, -74.8069), 'Cartagena': (10.3910, -75.4794), 'Bucaramanga': (7.1193, -73.1227),
        'Pereira': (4.8143, -75.6946), 'Cúcuta': (7.8939, -72.5078), 'Ibagué': (4.4447, -75.2424),
        'Manizales': (5.0689, -75.5174)
    },
    'Peru': {
        'Lima': (-12.0464, -77.0428), 'Arequipa': (-16.4090, -71.5375), 'Trujillo': (-8.1160, -79.0290),
        'Chiclayo': (-6.7714, -79.8409), 'Piura': (-5.1949, -80.6327), 'Iquitos': (-3.7491, -73.2538),
        'Cusco': (-13.5319, -71.9675), 'Huancayo': (-12.0651, -75.2049), 'Tacna': (-18.0147, -70.2482),
        'Juliaca': (-15.4908, -70.1337)
    },
    'Venezuela': {
        'Caracas': (10.4806, -66.9036), 'Maracaibo': (10.6545, -71.7148), 'Valencia': (10.1577, -67.9972),
        'Barquisimeto': (10.0678, -69.3474), 'Maracay': (10.2354, -67.5911), 'Ciudad Guayana': (8.3490, -62.6410),
        'Barcelona': (10.1364, -64.6862), 'Maturín': (9.7500, -63.1832), 'Cumaná': (10.4564, -64.1675),
        'Puerto La Cruz': (10.2130, -64.6328)
    },
    'Ecuador': {
        'Quito': (-0.1807, -78.4678), 'Guayaquil': (-2.2058, -79.9079), 'Cuenca': (-2.9005, -79.0045),
        'Santo Domingo': (-0.2537, -79.1703), 'Machala': (-3.2586, -79.9554), 'Manta': (-0.9676, -80.7089),
        'Portoviejo': (-1.0546, -80.4525), 'Loja': (-3.9931, -79.2042), 'Ambato': (-1.2417, -78.6198),
        'Esmeraldas': (0.9682, -79.6520)
    },
    'Bolivia': {
        'La Paz': (-16.4897, -68.1193), 'Santa Cruz': (-17.8146, -63.1561), 'Cochabamba': (-17.4139, -66.1651),
        'Sucre': (-19.0333, -65.2627), 'Oruro': (-17.9641, -67.1060), 'Tarija': (-21.5287, -64.7311),
        'Potosí': (-19.5836, -65.7531), 'Beni': (-14.8333, -64.9000), 'Pando': (-11.0277, -68.7692),
        'Trinidad': (-14.8335, -64.9005)
    },
    'Paraguay': {
        'Asunción': (-25.2637, -57.5759), 'Ciudad del Este': (-25.5097, -54.6111), 'Encarnación': (-27.3306, -55.8601),
        'Luque': (-25.2678, -57.4872), 'San Lorenzo': (-25.3437, -57.5088), 'Capiatá': (-25.3552, -57.4453),
        'Lambaré': (-25.3468, -57.6065), 'Fernando de la Mora': (-25.3250, -57.5409), 'Limpio': (-25.1661, -57.4856),
        'Ñemby': (-25.3935, -57.5353)
    },
    'Uruguay': {
        'Montevideo': (-34.9011, -56.1645), 'Salto': (-31.3833, -57.9667), 'Paysandú': (-32.3171, -58.0807),
        'Las Piedras': (-34.7302, -56.2192), 'Rivera': (-30.9053, -55.5508), 'Maldonado': (-34.9000, -54.9500),
        'Tacuarembó': (-31.7169, -55.9811), 'Mercedes': (-33.2524, -58.0305), 'Artigas': (-30.4000, -56.4667),
        'Minas': (-34.3759, -55.2377)
    },
    # Oceania
    'Australia': {
        'Sydney': (-33.8688, 151.2093), 'Melbourne': (-37.8136, 144.9631), 'Brisbane': (-27.4698, 153.0251),
        'Perth': (-31.9505, 115.8605), 'Adelaide': (-34.9285, 138.6007), 'Gold Coast': (-28.0167, 153.4000),
        'Canberra': (-35.2809, 149.1300), 'Newcastle': (-32.9272, 151.7765), 'Wollongong': (-34.4240, 150.8935),
        'Hobart': (-42.8821, 147.3272)
    },
    'New Zealand': {
        'Auckland': (-36.8485, 174.7633), 'Wellington': (-41.2865, 174.7762), 'Christchurch': (-43.5321, 172.6362),
        'Hamilton': (-37.7870, 175.2793), 'Tauranga': (-37.6861, 176.1667), 'Dunedin': (-45.8788, 170.5028),
        'Palmerston North': (-40.3563, 175.6112), 'Napier': (-39.4928, 176.9120), 'Rotorua': (-38.1378, 176.2552),
        'Invercargill': (-46.4132, 168.3538)
    },
    'Papua New Guinea': {
        'Port Moresby': (-9.4431, 147.1803), 'Lae': (-6.7220, 146.9847), 'Madang': (-5.2215, 145.7852),
        'Mount Hagen': (-5.8581, 144.2306), 'Popondetta': (-8.7654, 148.2325), 'Goroka': (-6.0852, 145.3867),
        'Kavieng': (-2.5744, 150.7967), 'Alotau': (-10.3151, 150.4574), 'Kimbe': (-5.5502, 150.1377),
        'Rabaul': (-4.1997, 152.1649)
    },
    'Fiji': {
        'Suva': (-18.1248, 178.4501), 'Nadi': (-17.7765, 177.4356), 'Lautoka': (-17.6167, 177.4500),
        'Labasa': (-16.4333, 179.3833), 'Sigatoka': (-18.1416, 177.5090), 'Rakiraki': (-17.3833, 178.0833),
        'Savusavu': (-16.7804, 179.3320), 'Levuka': (-17.6833, 178.8333), 'Ba': (-17.5333, 177.6833),
        'Tavua': (-17.4500, 177.8667)
    },
    'Solomon Islands': {
        'Honiara': (-9.4456, 159.9729), 'Gizo': (-8.1030, 156.8419), 'Auki': (-8.7676, 160.7034),
        'Kirakira': (-10.4544, 161.9205), 'Tulagi': (-9.1031, 160.1503), 'Munda': (-8.3270, 157.2633),
        'Lata': (-10.7250, 165.8367), 'Buala': (-8.1450, 159.5921), 'Taro': (-6.7111, 156.3972),
        'Noro': (-8.2417, 157.1983)
    },
    'Vanuatu': {
        'Port Vila': (-17.7333, 168.3273), 'Luganville': (-15.5333, 167.1667), 'Norsup': (-16.0667, 167.3833),
        'Isangel': (-19.5333, 169.2667), 'Sola': (-13.8761, 167.5517), 'Longana': (-15.3167, 167.9667),
        'Lenakel': (-19.5167, 169.2667), 'Lakatoro': (-16.0999, 167.4164), 'Saratamata': (-15.2903, 167.9631),
        'Lamap': (-16.4167, 167.4167)
    },
    'Samoa': {
        'Apia': (-13.8333, -171.7667), 'Asau': (-13.5196, -172.6378), 'Mulifanua': (-13.8318, -172.0360),
        'Falealupo': (-13.4167, -172.6667), 'Salelologa': (-13.7467, -172.1912), 'Safotu': (-13.4513, -172.4018),
        'Lalomalava': (-13.7013, -172.2685), 'Satupaitea': (-13.7667, -172.3167), 'Vailoa': (-13.7558, -172.3047),
        'Faleasiu': (-13.8112, -172.3219)
    },
    'Tonga': {
        'Nuku’alofa': (-21.1393, -175.2049), 'Neiafu': (-18.6500, -173.9833), 'Haveluloto': (-21.1500, -175.2167),
        'Vaini': (-21.2000, -175.1667), 'Pangai': (-19.8000, -174.3500), 'Ohonua': (-21.3333, -174.9500),
        'Hihifo': (-15.9500, -173.7833), 'Kolonga': (-21.1333, -175.0667), 'Houma': (-21.1667, -175.2833),
        'Niuatoputapu': (-15.9667, -173.7667)
    },
    'Micronesia': {
        'Palikir': (6.9248, 158.1610), 'Kolonia': (6.9640, 158.2060), 'Tofol': (5.3145, 163.0078),
        'Weno': (7.4450, 151.8490), 'Fefan': (7.3640, 151.8530), 'Udot': (7.3890, 151.8190), 'Nema': (6.9930, 152.5870),
        'Madolenihmw': (6.8530, 158.2980), 'Sokehs': (6.9610, 158.1270), 'Kitti': (6.8430, 158.2180)
    },
    'Kiribati': {
        'Tarawa': (1.3293, 172.9750), 'Betio': (1.3579, 172.9210), 'Bikenibeu': (1.3673, 173.1240),
        'Teaoraereke': (1.3319, 173.0116), 'Ambo': (1.3517, 173.0425), 'Banraeaba': (1.3438, 173.0348),
        'Bairiki': (1.3273, 172.9752), 'Eita': (1.3615, 173.0833), 'Bonriki': (1.3808, 173.1389),
        'Rawannawi': (1.4066, 173.0905)
    }
}

# Carbon pricing data
CARBON_PRICE_EUR_PER_TON = 65.89
EXCHANGE_RATES = {'EUR': 1.0, 'USD': 1.06, 'AUD': 1.62, 'SAR': 3.98}

# Packaging emission factors (kg CO₂ per kg)
PACKAGING_EMISSIONS = {'Plastic': 6.0, 'Cardboard': 0.9, 'Biodegradable': 0.3, 'Reusable': 0.1}

# Offset project costs (USD per ton of CO₂)
OFFSET_COSTS = {'Reforestation': 15.0, 'Renewable Energy': 20.0, 'Methane Capture': 18.0}

# Packaging material costs (USD per kg)
PACKAGING_COSTS = {'Plastic': 1.5, 'Cardboard': 0.8, 'Biodegradable': 2.0, 'Reusable': 3.0}

def get_coordinates(country, city):
    return LOCATIONS.get(country, {}).get(city, (0, 0))

def calculate_distance(country1, city1, country2, city2):
    lat1, lon1 = get_coordinates(country1, city1)
    lat2, lon2 = get_coordinates(country2, city2)
    if lat1 == 0 and lon1 == 0 or lat2 == 0 and lon2 == 0:
        raise ValueError(f"Coordinates not found for {city1}, {country1} or {city2}, {country2}")
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

def calculate_co2(country1, city1, country2, city2, transport_mode, distance_km, weight_tons):
    emission_factor = EMISSION_FACTORS.get(transport_mode)
    if emission_factor is None:
        raise ValueError(f"Invalid transport mode: {transport_mode}")
    co2_kg = distance_km * weight_tons * emission_factor
    return round(co2_kg, 2)

def optimize_route(country1, city1, country2, city2, distance_km, weight_tons, prioritize_green=False):
    intercontinental = country1 != country2
    distance_short = distance_km < 1000
    distance_medium = 1000 <= distance_km < 5000
    distance_long = distance_km >= 5000
    current_co2 = distance_km * weight_tons * EMISSION_FACTORS['Truck']
    combinations = []
    if intercontinental:
        if distance_long:
            combinations.extend([
                ('Ship', 0.9, 'Train', 0.1),
                ('Ship', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Ship', 0.8, 'Truck', 0.2),
                ('Plane', 0.5, 'Ship', 0.5)
            ])
        elif distance_medium:
            combinations.extend([
                ('Ship', 0.7, 'Train', 0.3),
                ('Plane', 0.4, 'Hydrogen Truck', 0.6) if prioritize_green else ('Plane', 0.4, 'Truck', 0.6),
                ('Ship', 0.6, 'Plane', 0.4)
            ])
        else:
            combinations.extend([
                ('Train', 0.8, 'Electric Truck', 0.2) if prioritize_green else ('Train', 0.8, 'Truck', 0.2),
                ('Ship', 0.5, 'Truck', 0.5),
                ('Plane', 0.3, 'Truck', 0.7)
            ])
    else:
        if distance_short:
            combinations.extend([
                ('Train', 0.9, 'Electric Truck', 0.1) if prioritize_green else ('Train', 0.9, 'Truck', 0.1),
                ('Electric Truck', 1.0, None, 0.0) if prioritize_green else ('Truck', 1.0, None, 0.0),
                ('Train', 1.0, None, 0.0)
            ])
        else:
            combinations.extend([
                ('Train', 0.7, 'Biofuel Truck', 0.3) if prioritize_green else ('Train', 0.7, 'Truck', 0.3),
                ('Truck', 0.6, 'Train', 0.4),
                ('Plane', 0.3, 'Truck', 0.7)
            ])
    best_option = None
    min_co2 = float('inf')
    best_breakdown = None
    best_distances = None
    for mode1, ratio1, mode2, ratio2 in combinations:
        dist1 = distance_km * ratio1
        dist2 = distance_km * ratio2 if mode2 else 0
        co2_1 = dist1 * weight_tons * EMISSION_FACTORS[mode1]
        co2_2 = dist2 * weight_tons * EMISSION_FACTORS[mode2] if mode2 else 0
        total_co2 = co2_1 + co2_2
        if total_co2 < min_co2:
            min_co2 = total_co2
            best_option = (mode1, ratio1, mode2, ratio2)
            best_breakdown = (co2_1, co2_2)
            best_distances = (dist1, dist2)
    return best_option, round(min_co2, 2), best_breakdown, best_distances, round(current_co2, 2)

def save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons):
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            emission_id = str(uuid.uuid4())
            c.execute('INSERT INTO emissions (id, source, destination, transport_mode, distance_km, co2_kg, weight_tons, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
                      (emission_id, source, destination, transport_mode, distance_km, co2_kg, weight_tons))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def save_packaging(material_type, weight_kg, co2_kg):
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            packaging_id = str(uuid.uuid4())
            c.execute('INSERT INTO packaging (id, material_type, weight_kg, co2_kg, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                      (packaging_id, material_type, weight_kg, co2_kg))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def save_offset(project_type, co2_offset_tons, cost_usd):
    try:
        with sqlite3.connect('emissions.db') as conn:
            c = conn.cursor()
            offset_id = str(uuid.uuid4())
            c.execute('INSERT INTO offsets (id, project_type, co2_offset_tons, cost_usd, timestamp) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                      (offset_id, project_type, co2_offset_tons, cost_usd))
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_emissions():
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM emissions', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_packaging():
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM packaging', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_offsets():
    try:
        with sqlite3.connect('emissions.db') as conn:
            df = pd.read_sql_query('SELECT * FROM offsets', conn)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def get_suppliers(country=None, city=None, material=None, min_green_score=0):
    try:
        with sqlite3.connect('emissions.db') as conn:
            query = 'SELECT * FROM suppliers WHERE green_score >= ?'
            params = [min_green_score]
            conditions = []
            if country and country != "All":
                conditions.append('country = ?')
                params.append(country)
            if city and city != "All":
                conditions.append('city = ?')
                params.append(city)
            if material:
                conditions.append('LOWER(material) LIKE ?')
                params.append(f'%{material.lower()}%')
            if conditions:
                query += ' AND ' + ' AND '.join(conditions)
            df = pd.read_sql_query(query, conn, params=params)
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        raise

def calculate_warehouse_savings(warehouse_size_m2, led_percentage, solar_percentage):
    traditional_energy_kwh = warehouse_size_m2 * 100
    led_savings_kwh = traditional_energy_kwh * led_percentage * 0.5
    solar_savings_kwh = traditional_energy_kwh * solar_percentage * 0.3
    total_savings_kwh = led_savings_kwh + solar_savings_kwh
    co2_savings_kg = total_savings_kwh * 0.5
    return round(co2_savings_kg, 2), round(total_savings_kwh, 2)

def calculate_load_optimization(weight_tons, vehicle_capacity_tons, avg_trip_distance_km=100):
    trips_without_optimization = math.ceil(weight_tons / (vehicle_capacity_tons * 0.90))
    optimized_trips = math.ceil(weight_tons / (vehicle_capacity_tons * 0.98))
    trips_saved = max(trips_without_optimization - optimized_trips, 0)
    co2_savings_kg = trips_saved * avg_trip_distance_km * EMISSION_FACTORS['Truck']
    return trips_saved, round(co2_savings_kg, 2)

def main():
    st.set_page_config(page_title="Carbon 360", layout="wide", initial_sidebar_state="expanded")

    # Inject Tailwind CSS
    components.html("""
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .nav-item { 
            transition: all 0.3s ease; 
            padding: 0.5rem 1rem; 
            border-radius: 0.5rem; 
            margin: 0.25rem 0;
        }
        .nav-item:hover { background-color: #e6fffa; }
        .card { 
            background: white; 
            border-radius: 1rem; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); 
            padding: 1.5rem; 
            margin-bottom: 1.5rem;
        }
        .btn-primary {
            background: linear-gradient(to right, #10b981, #059669);
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            transition: all 0.3s ease;
        }
        .btn-primary:hover {
            background: linear-gradient(to right, #059669, #047857);
            transform: translateY(-1px);
        }
        .header { 
            background: linear-gradient(to right, #10b981, #059669); 
            color: white; 
            padding: 1rem 2rem; 
            border-radius: 0.5rem; 
            margin-bottom: 2rem;
        }
        .sidebar { 
            background: #f7fafc; 
            border-right: 1px solid #e2e8f0; 
            padding: 1rem;
        }
        .metric-card {
            background: #f7fafc;
            border-radius: 0.5rem;
            padding: 1rem;
            text-align: center;
        }
    </style>
    """, height=0)

    init_db()

    # Initialize session state
    if 'page' not in st.session_state:
        st.session_state.page = "Calculate Emissions"
    if 'source_country' not in st.session_state or st.session_state.source_country not in LOCATIONS:
        st.session_state.source_country = next(iter(LOCATIONS))
    if 'source_city' not in st.session_state or st.session_state.source_city not in LOCATIONS[st.session_state.source_country]:
        st.session_state.source_city = next(iter(LOCATIONS[st.session_state.source_country]))
    if 'dest_country' not in st.session_state or st.session_state.dest_country not in LOCATIONS:
        st.session_state.dest_country = next(iter(LOCATIONS))
    if 'dest_city' not in st.session_state or st.session_state.dest_city not in LOCATIONS[st.session_state.dest_country]:
        st.session_state.dest_city = next(iter(LOCATIONS[st.session_state.dest_country]))
    if 'weight_tons' not in st.session_state:
        st.session_state.weight_tons = 1.0
    if 'warehouse_inputs' not in st.session_state:
        st.session_state.warehouse_inputs = {'warehouse_size_m2': 1000, 'led_percentage': 0.5, 'solar_percentage': 0.3}
    if 'packaging_inputs' not in st.session_state:
        st.session_state.packaging_inputs = {'material_type': 'Plastic', 'weight_kg': 1.0}
    if 'offset_inputs' not in st.session_state:
        st.session_state.offset_inputs = {'project_type': 'Reforestation', 'co2_offset_tons': 1.0}
    if 'load_inputs' not in st.session_state:
        st.session_state.load_inputs = {'weight_tons': 10.0, 'vehicle_capacity_tons': 20.0, 'avg_trip_distance_km': 100.0}
    if 'energy_inputs' not in st.session_state:
        st.session_state.energy_inputs = {'facility_size_m2': 1000, 'smart_system_usage': 0.5}

    # Header
    st.markdown("""
    <div class="header flex items-center justify-between">
        <div class="flex items-center space-x-4">
            <img src="https://via.placeholder.com/40" class="rounded-full" alt="Logo">
            <h1 class="text-2xl font-bold">Carbon 360</h1>
        </div>
        <div class="text-sm">Sustainable Logistics Solutions</div>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar">', unsafe_allow_html=True)
        st.markdown('<h2 class="text-xl font-semibold mb-4 text-gray-800">Navigation</h2>', unsafe_allow_html=True)
        pages = [
            ("Calculate Emissions", "📊"),
            ("Route Visualizer", "🗺️"),
            ("Supplier Lookup", "🔍"),
            ("Reports", "📈"),
            ("Optimized Route Planning", "🚚"),
            ("Green Warehousing", "🏭"),
            ("Sustainable Packaging", "📦"),
            ("Carbon Offsetting", "🌳"),
            ("Efficient Load Management", "⚖️"),
            ("Energy Conservation", "💡")
        ]
        for page_name, icon in pages:
            if st.button(f"{icon} {page_name}", key=page_name, help=page_name):
                st.session_state.page = page_name
        st.markdown('</div>', unsafe_allow_html=True)

    # Main content
    st.markdown('<div class="container mx-auto px-4 py-6">', unsafe_allow_html=True)

    if st.session_state.page == "Calculate Emissions":
        st.markdown('<h2 class="text-3xl font-bold mb-6 text-gray-800">Calculate CO₂ Emissions</h2>', unsafe_allow_html=True)
        st.markdown('<div class="card">', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1], gap="large")
        
        with col1:
            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Source</h3>', unsafe_allow_html=True)
            source_country = st.selectbox(
                "Source Country", 
                sorted(LOCATIONS.keys()), 
                index=sorted(LOCATIONS.keys()).index(st.session_state.source_country) if st.session_state.source_country in LOCATIONS else 0,
                key="calc_source_country"
            )
            source_city = st.selectbox(
                "Source City", 
                sorted(LOCATIONS[source_country].keys()), 
                index=sorted(LOCATIONS[source_country].keys()).index(st.session_state.source_city) if st.session_state.source_city in LOCATIONS[source_country] else 0,
                key="calc_source_city"
            )
            st.session_state.source_country = source_country
            st.session_state.source_city = source_city
            
            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700 mt-6">Destination</h3>', unsafe_allow_html=True)
            dest_country = st.selectbox(
                "Destination Country", 
                sorted(LOCATIONS.keys()), 
                index=sorted(LOCATIONS.keys()).index(st.session_state.dest_country) if st.session_state.dest_country in LOCATIONS else 0,
                key="calc_dest_country"
            )
            dest_city = st.selectbox(
                "Destination City", 
                sorted(LOCATIONS[dest_country].keys()), 
                index=sorted(LOCATIONS[dest_country].keys()).index(st.session_state.dest_city) if st.session_state.dest_city in LOCATIONS[dest_country] else 0,
                key="calc_dest_city"
            )
            st.session_state.dest_country = dest_country
            st.session_state.dest_city = dest_city
        
        with col2:
            st.markdown('<h3 class="text-xl font-semibold mb-4 text-gray-700">Shipment Details</h3>', unsafe_allow_html=True)
            transport_mode = st.selectbox("Transport Mode", list(EMISSION_FACTORS.keys()))
            weight_tons = st.number_input("Weight (tons)", min_value=0.1, max_value=100000.0, value=st.session_state.weight_tons, step=0.1)
            st.session_state.weight_tons = weight_tons
            try:
                distance_km = calculate_distance(source_country, source_city, dest_country, dest_city)
                st.markdown(f'<p class="text-gray-600">Estimated Distance: <span class="font-semibold">{distance_km} km</span></p>', unsafe_allow_html=True)
            except ValueError as e:
                st.error(str(e))
                distance_km = 0.0
        
        st.markdown('<div class="mt-6">', unsafe_allow_html=True)
        if st.button("Calculate", key Spirit=True, key="calc_button", type="primary"):
            if distance_km > 0:
                source = f"{source_city}, {source_country}"
                destination = f"{dest_city}, {dest_country}"
                try:
                    co2_kg = calculate_co2(source_country, source_city, dest_country, dest_city, transport_mode, distance_km, weight_tons)
                    st.markdown(f'<div class="bg-green-100 p-4 rounded-lg"><p class="text-lg font-semibold text-green-800">Estimated CO₂ Emissions: {co2_kg} kg</p></div>', unsafe_allow_html=True)
                    save_emission(source, destination, transport_mode, distance_km, co2_kg, weight_tons)
                    
                    st.markdown('<h3 class="text-xl font-semibold mt-6 mb-4 text-gray-700">Calculation Dashboard</h3>', unsafe_allow_html=True)
                    col3, col4 = st.columns(2)
                    with col3:
                        st.markdown(f'<div class="metric-card"><p class="text-sm text-gray-600">Total Distance</p><p class="text-lg font-semibold">{distance_km} km</p></div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="metric-card"><p class="text-sm text-gray-600">Total CO₂ Emissions</p><p class="text-lg font-semibold">{co2_kg} kg</p></div>', unsafe_allow_html=True)
                    with col4:
                        st.markdown(f'<div class="metric-card"><p class="text-sm text-gray-600">Emission Factor</p><p class="text-lg font-semibold">{EMISSION_FACTORS[transport_mode]} kg CO₂/km/ton</p></div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="metric-card"><p class="text-sm text-gray-600">Weight</p><p class="text-lg font-semibold">{weight_tons} tons</p></div>', unsafe_allow_html=True)
                    
                    with st.expander("How were these values calculated?"):
                        st.markdown('<h4 class="text-lg font-semibold mb-2">Distance Calculation</h4>', unsafe_allow_html=True)
                        st.markdown("The distance between two cities is calculated using the **Haversine Formula**.", unsafe_allow_html=True)
                        st.markdown(f"Coordinates: {source_city} ({get_coordinates(source_country, source_city)}), {dest_city} ({get_coordinates(dest_country, dest_city)})", unsafe_allow_html=True)
                        
                        st.markdown('<h4 class="text-lg font-semibold mt-4 mb-2">CO₂ Emission Calculation</h4>', unsafe_allow_html=True)
                        st.markdown("CO₂ = Distance (km) * Weight (tons) * Emission Factor", unsafe_allow_html=True)
                        st.markdown(f"Calculation: {distance_km} km * {weight_tons} tons * {EMISSION_FACTORS[transport_mode]} = {co2_kg} kg", unsafe_allow_html=True)
                except ValueError as e:
                    st.error(str(e))
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    elif st.session_state.page == " AscendantRoutePlanning:
        st.markdown
