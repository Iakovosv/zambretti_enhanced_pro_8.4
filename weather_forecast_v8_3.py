import math
from datetime import datetime, timedelta




# ============================================================
# CONFIG - SENSORS (GW2000A Ecowitt)
# ============================================================
PRESSURE_SENSOR = "sensor.gw2000a_relative_pressure"
TEMP_SENSOR = "sensor.gw2000a_outdoor_temperature"
HUM_SENSOR = "sensor.gw2000a_humidity"
WIND_SPEED_SENSOR = "sensor.gw2000a_wind_speed"
WIND_DIR_SENSOR = "sensor.gw2000a_wind_direction"
SOLAR_SENSOR = "sensor.gw2000a_solar_radiation"  # W/m²


WIND_SPEED_IS_MS = False




# ============================================================
# PHYSICS CONSTANTS - Magnus-Tetens (Buck 1981)
# ============================================================
MAGNUS_A = 17.62    #°C
MAGNUS_B = 243.12    #°C




# ============================================================
# SCORING THRESHOLDS (FIXED: Separate falling/rising)
# ============================================================
# For NEGATIVE signals (pressure drop, negative curvature)
SCORE_THRESHOLDS_FALLING = {
    "pressure_trend_3h": [
        (-2.0, 35),
        (-1.0, 15),
    ],
    "pressure_curvature": [
        (-0.4, 20),
    ],
}


# For POSITIVE signals (humidity, wind, pressure)
SCORE_THRESHOLDS_RISING = {
    "humidity": [
        (90, 25),
        (80, 15),
    ],
    "wind_speed": [
        (35, 10),
    ],
    "pressure_abs": [
        (1000, 15),
        (1005, 8),
    ],
}




# ============================================================
# REGIME STABILITY CONFIG (v1.1 - Increased for damping)
# ============================================================
REGIME_STABILITY_WINDOW = 30  # minutes (was 15)
REGIME_COOLDOWN = 20          # minutes (was 10)


# NEW: Minimum state dwell time (anti-micro-flip)
MIN_STATE_DWELL_TIME = 25  # minutes


# NEW: Hysteresis for state transitions
STATE_UPPER_HYSTERESIS = 48
STATE_LOWER_HYSTERESIS = 38




# ============================================================
# SMOOTHING CONFIGURATION
# ============================================================
SMOOTHING_FACTOR = 0.25  # 25% current, 75% previous




# ============================================================
# SOLAR POSITION MODULE (v1.0 - NOAA SPA + Local Horizon)
# ============================================================

SOLAR_CONSTANT = 1361  # W/m²


def _calculate_julian_date(dt: datetime) -> float:
    """Υπολογισμός Julian Date"""
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour + dt.minute/60.0 + dt.second/3600.0
    
    if month <= 2:
        year -= 1
        month += 12
    
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    JD = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + hour/24.0 + B - 1524.5
    return JD


def get_solar_position_accurate(lat: float, lon: float, dt: datetime) -> dict:
    """
    v8.8: Διορθωμένος υπολογισμός θέσης ήλιου
    Με timezone support για Greece (UTC+3)
    """
    day_of_year = dt.timetuple().tm_yday
    
    # Solar declination (απλοποιημένη)
    decl = 23.45 * math.sin(math.radians(360/365 * (day_of_year - 81)))
    decl_rad = math.radians(decl)
    
    # Timezone offset (Greece = UTC+3 θερινή ώρα)
    tz_offset = 3.0
    
    # Solar noon = 12:00 + tz_offset - longitude/15
    solar_noon = 12.0 + tz_offset - lon/15
    
    # Hour angle
    hour_angle = (dt.hour + dt.minute/60 - solar_noon) * 15
    ha_rad = math.radians(hour_angle)
    
    lat_rad = math.radians(lat)
    
    # Solar Elevation
    sin_alt = (math.sin(lat_rad) * math.sin(decl_rad) + 
               math.cos(lat_rad) * math.cos(decl_rad) * math.cos(ha_rad))
    elevation = math.degrees(math.asin(max(-1, min(1, sin_alt))))
    
    # Solar Azimuth
    zenith_rad = math.radians(max(1, 90 - elevation))
    cos_az = (math.sin(decl_rad) - math.sin(lat_rad) * math.cos(zenith_rad)) / \
             (math.cos(lat_rad) * math.sin(zenith_rad))
    cos_az = max(-1, min(1, cos_az))
    azimuth = math.degrees(math.acos(cos_az))
    
    if hour_angle > 0:
        azimuth = 360 - azimuth
    
    return {
        "elevation": elevation,
        "azimuth": azimuth % 360,
        "declination": decl,
        "is_above_horizon": elevation > 0
    }


def _get_local_horizon_blocking(lat: float, lon: float, azimuth: float) -> float:
    """
    v8.9: Horizon blocking με εύκολη διαμόρφωση
    
    Για να προσθέσεις βουνά της περιοχής σου:
    1. Βρες τις συντεταγμένες της κορυφής (Google Maps > Βουνό)
    2. Βρες το ύψος (Google: "Βουνό ύψος")
    3. Πρόσθεσε στο USER_MOUNTAINS παρακάτω
    """
    # ============================================================
    # ΔΙΟΡΘΩΣΕ ΤΑ ΒΟΥΝΑ ΤΗΣ ΠΕΡΙΟΧΗΣ ΣΟΥ ΕΔΩ!
    # ============================================================
    # Μορφή: (lat, lon, height, spread_degrees)
    # spread = ±μοίρες που επηρεάζει το βουνό (π.χ. 20 = ±20°)
    
    USER_MOUNTAINS = [
        # Παράδειγμα - Ιλιούπολη (άφησε κενό για να χρησιμοποιηθεί η DB):
        # (37.938, 23.84, 1026, 35),  # Υμηττός
    ]
    
    # Βάση δεδομένων Ελληνικών βουνών (κορυφές)
    # Χρησιμοποιείται αυτόματα βάσει απόστασης από τον χρήστη
    MOUNTAINS_DB = [
        # ========== ΑΤΤΙΚΗ ==========
        (37.938, 23.84, 1026, 35),  # Υμηττός (Ιλιούπολη, 5km Α)
        (38.05, 23.73, 1410, 40),   # Πάρνηθα (15km Β)
        (38.18, 23.71, 1407, 25),   # Πεντέλη (17km ΒΑ)
        (38.0, 23.57, 487, 20),     # Αιγάλεω (18km Δ)
        (37.80, 23.86, 487, 15),    # Λαυρεωτική (20km ΝΑ)
        
        # ========== ΘΕΣΣΑΛΟΝΙΚΗ ==========
        (40.60, 22.95, 1201, 30),   # Χορτιάτης (5km Β)
        (40.65, 23.03, 1150, 25),   # Σέδες (10km ΒΑ)
        (40.52, 22.78, 330, 15),    # Στρατόνι (15km Δ)
        (40.73, 23.15, 1020, 20),   # Κερδύλιο (25km ΒΑ)
        
        # ========== ΠΑΤΡΑ ==========
        (38.22, 21.72, 1926, 35),   # Παναχαϊκό (10km ΒΑ)
        (38.28, 21.78, 719, 25),    # Άρτεμις (8km Β)
        (38.15, 21.55, 1426, 20),   # Μαλιακός (20km Δ)
        (38.25, 22.0, 1424, 15),    # Ερύμανθος (25km Ν)
        
        # ========== ΛΑΡΙΣΑ / ΘΕΣΣΑΛΙΑ ==========
        (40.0, 22.35, 2918, 50),    # Όλυμπος (30km Δ)
        (39.65, 21.77, 2543, 35),   # Γκαμήλα/Αθαμανικά (40km Δ)
        (39.55, 22.0, 2178, 25),    # Καλιακούδα (35km Δ)
        (39.5, 21.5, 1800, 20),     # Περιστέρι (45km Δ)
        
        # ========== ΙΩΑΝΝΙΝΑ ==========
        (40.17, 20.93, 2520, 40),   # Γράμμος (30km ΒΔ)
        (39.99, 20.75, 2117, 30),   # Σμόλιτσα (40km ΒΔ)
        (39.7, 21.18, 1827, 25),    # Βαρνάς (35km Δ)
        (40.15, 21.2, 1780, 20),    # Μιτσικέλι (15km Δ)
        
        # ========== ΒΟΛΟΣ ==========
        (39.44, 22.88, 1781, 30),   # Πήλιο (10km ΒΑ)
        (39.55, 22.75, 1550, 20),   # Μαυροβούνι (8km Β)
        (39.35, 23.0, 1348, 15),    # Αιγαίο (15km Α)
        (39.6, 22.45, 950, 15),     # Κίσσαβος (20km Δ)
        
        # ========== ΧΑΝΙΑ / ΚΡΗΤΗ ==========
        (35.27, 24.93, 2456, 35),   # Ψηλορείτης (25km ΝΑ)
        (35.40, 24.0, 2452, 30),    # Λευκά Όρη (30km Δ)
        (35.23, 24.35, 2217, 20),   # Μαδάρα Πσίρας (20km Α)
        (35.32, 24.28, 1476, 15),   # Κούρνοβος (15km ΒΑ)
        
        # ========== ΗΡΑΚΛΕΙΟ / ΚΡΗΤΗ ==========
        (35.18, 25.47, 880, 25),    # Ίδη (15km ΝΑ)
        (35.22, 25.27, 497, 15),    # Λασιθιώτικα όρη (20km Α)
        (35.12, 25.0, 782, 15),     # Δίκτη (30km Α)
        
        # ========== ΡΕΘΥΜΝΟ / ΚΡΗΤΗ ==========
        (35.32, 24.38, 524, 15),    # Ακρωτήρι (15km Δ)
        
        # ========== ΜΥΤΙΛΗΝΗ / ΛΕΣΒΟΣ ==========
        (39.08, 26.55, 968, 25),    # Όλυμπος Λέσβου (25km Β)
        (39.15, 26.35, 510, 15),    # Λεπέτυμνος (15km Δ)
        
        # ========== ΧΙΟΣ ==========
        (38.48, 26.14, 1297, 25),   # Προφήτης Ηλίας (15km Β)
        (38.52, 26.0, 850, 15),     # Αίνος (10km ΒΑ)
        
        # ========== ΣΑΜΟΣ ==========
        (37.77, 26.84, 1434, 25),   # Κέρκης/Υψηλό (20km Δ)
        (37.73, 26.95, 1150, 15),   # Λεκτούρι (15km ΒΔ)
        
        # ========== ΚΕΦΑΛΟΝΙΑ ==========
        (38.37, 20.58, 1628, 30),   # Αίνος (15km ΒΔ)
        
        # ========== ΖΑΚΥΝΘΟΣ ==========
        (38.67, 20.76, 756, 20),    # Βραχονήσια (10km ΒΑ)
        
        # ========== ΚΟΡΙΝΘΟΣ ==========
        (37.97, 22.65, 1136, 25),   # Αρτεμίσιο (20km Δ)
        (37.90, 22.42, 1031, 15),   # Ολονοστή (25km Δ)
        
        # ========== ΤΡΙΠΟΛΗ / ΑΡΚΑΔΙΑ ==========
        (37.93, 22.45, 1981, 30),   # Μαίναλο (20km Δ)
        (37.65, 22.36, 2371, 35),   # Ταΰγετος (30km ΝΔ)
        (37.78, 21.93, 1733, 20),   # Λύρκειο (25km Δ)
        
        # ========== ΚΑΛΑΜΑΤΑ / ΜΕΣΣΗΝΙΑ ==========
        (37.18, 22.01, 2401, 40),   # Ταΰγετος νότια (40km Δ)
        (37.05, 22.25, 1204, 20),   # Ιθώμη (15km ΒΔ)
        (37.23, 21.78, 650, 15),    # Αιγάλεω Μεσσηνίας (20km Δ)
        
        # ========== ΚΑΒΑΛΑ ==========
        (40.94, 24.07, 1827, 25),   # Σύμβολο (20km ΒΑ)
        (40.85, 24.35, 1113, 15),   # Παγγαίο (15km Α)
        
        # ========== ΞΑΝΘΗ / ΔΡΑΜΑ ==========
        (41.23, 24.15, 1827, 25),   # Φαλακρό (25km Β)
        (41.35, 24.0, 1533, 20),    # Μενοίκειο (20km ΒΑ)
        
        # ========== ΚΟΜΟΤΗΝΗ / ΡΟΔΟΠΗ ==========
        (41.27, 25.55, 826, 20),    # Ισβόρος (15km ΝΑ)
        
        # ========== ΑΛΕΞΑΝΔΡΟΥΠΟΛΗ / ΕΒΡΟΣ ==========
        (41.15, 26.15, 937, 25),    # Σουφλί/Μακρυβούνι (25km ΒΑ)
        (41.55, 26.28, 532, 15),    # Δειράδες (35km ΒΑ)
        
        # ========== ΚΑΡΔΙΤΣΑ ==========
        (39.47, 21.62, 1848, 25),   # Αγράμπελη (20km Δ)
        (39.35, 21.75, 1677, 20),   # Νευρόπολη (25km Δ)
        
        # ========== ΛΑΜΙΑ / ΦΘΙΩΤΙΔΑ ==========
        (38.88, 22.44, 1722, 25),   # Οίτη (25km ΒΔ)
        (38.95, 22.6, 826, 15),     # Ξηροβούνι (15km Β)
        (38.72, 22.78, 1346, 20),   # Καλλίδρομο (20km ΝΑ)
        
        # ========== ΛΕΒΑΔΕΙΑ / ΒΟΙΩΤΙΑ ==========
        (38.35, 22.85, 1439, 25),   # Ελικών (15km ΒΑ)
        (38.27, 23.12, 1083, 20),   # Πάρνωνας (20km ΝΑ)
        
        # ========== ΑΜΦΙΣΣΑ / ΦΩΚΙΔΑ ==========
        (38.57, 22.48, 1749, 30),   # Γκιώνας (25km ΒΔ)
        (38.67, 22.28, 1172, 20),   # Βαρδούσια (30km ΒΔ)
        
        # ========== ΝΑΥΠΛΙΟ / ΑΡΓΟΛΙΔΑ ==========
        (37.72, 22.68, 1359, 25),   # Αρτεμίσιο (20km ΒΔ)
        (37.65, 22.42, 650, 15),    # Λύρκειο (15km Δ)
        
        # ========== ΣΠΑΡΤΗ / ΛΑΚΩΝΙΑ ==========
        (37.15, 22.45, 2407, 35),   # Ταΰγετος (30km ΝΔ)
        (37.08, 22.22, 990, 15),    # Πάρνωνας (20km ΝΑ)
        (37.25, 22.62, 997, 15),    # Μενεάτειο (15km Δ)
        
        # ========== ΚΥΘΗΡΑ ==========
        (36.27, 22.99, 506, 15),    # Κυρά Παλαιόχωρα (10km Ν)
    ]
    
    # Χρήση user mountains αν έχουν οριστεί
    mountains = USER_MOUNTAINS if USER_MOUNTAINS else MOUNTAINS_DB
    
    max_blocking = 0.0
    
    for m_lat, m_lon, height, spread in mountains:
        # Υπολογισμός απόστασης (Haversine)
        R = 6371
        dlat = math.radians(m_lat - lat)
        dlon = math.radians(m_lon - lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(m_lat)) * math.sin(dlon/2)**2
        distance = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        if distance > 100 or distance < 1:
            continue
        
        # Υπολογισμός αζιμουθίου προς το βουνό
        dlon_r = math.radians(m_lon - lon)
        lat_r = math.radians(lat)
        m_lat_r = math.radians(m_lat)
        x = math.sin(dlon_r) * math.cos(m_lat_r)
        y = math.cos(lat_r) * math.sin(m_lat_r) - math.sin(lat_r) * math.cos(m_lat_r) * math.cos(dlon_r)
        mountain_az = (math.degrees(math.atan2(x, y)) + 360) % 360
        
        # Έλεγχος: ο ήλιος πρέπει να είναι προς την κατεύθυνση του βουνού
        az_diff = abs(azimuth - mountain_az)
        if az_diff > 180:
            az_diff = 360 - az_diff
        
        if az_diff > spread:
            continue
        
        # Υπολογισμός γωνίας αποκλεισμού
        base_angle = math.degrees(math.atan(height / (distance * 1000)))
        direction_factor = 1 - (az_diff / spread) * 0.5
        blocking = base_angle * direction_factor
        max_blocking = max(max_blocking, blocking)
    
    return max_blocking


def get_expected_clear_sky_solar(lat: float, lon: float, dt: datetime) -> float:
    """
    v8.5: Υπολογισμός αναμενόμενης ηλιακής ακτινοβολίας
    Με διόρθωση για τοπικό ορίζοντα (βουνά)
    """
    # NOVA: Ακριβής θέση ήλιου
    solar = get_solar_position_accurate(lat, lon, dt)
    
    if not solar["is_above_horizon"]:
        return 0
    
    # v8.5: Έλεγχος για αποκλεισμό από βουνά
    blocking_angle = _get_local_horizon_blocking(lat, lon, solar["azimuth"])
    effective_elevation = solar["elevation"] - blocking_angle
    
    if effective_elevation <= 0:
        return 0
    
    # Υπολογισμός ακτινοβολίας
    day_of_year = dt.timetuple().tm_yday
    lat_rad = math.radians(lat)
    solar_alt_rad = math.radians(effective_elevation)
    
    # Atmospheric transmittance
    transmittance = 0.75 + 0.2 * (effective_elevation / 90)
    seasonal_factor = 1 + 0.033 * math.cos(math.radians(360/365 * (day_of_year - 10)))
    
    expected = SOLAR_CONSTANT * seasonal_factor * transmittance * math.sin(solar_alt_rad)
    
    # v8.5: Επιπλέον μείωση αν ο ήλιος είναι κοντά στο βουνό
    if blocking_angle > 5:
        mountain_factor = 1 - (blocking_angle / 90)
        expected *= max(0.3, mountain_factor)
    
    return max(0, min(expected, 1050))




# ============================================================
# PERSISTENT STORAGE (Restart-proof)
# ============================================================
def _ensure_storage():
    defaults = {
        'pressure_history': [],
        'temp_history': [],
        'hum_history': [],
        'wind_history': [],
        'solar_history': [],
        'last_score': None,
        'last_rain': None,
        'last_dp_depression': None,
        'current_regime': 'unknown',
        'regime_start_time': None,
        'last_regime_transition': None,
        'sky_confidence_persistence': None,
        'sky_streak_clear': 0,
        'sky_streak_cloudy': 0,
        # NEW: Dwell time tracking
        'last_state_change_time': None,
        'last_primary_state': None,
    }
    for var, default in defaults.items():
        if var not in globals():
            globals()[var] = default




# ============================================================
# DEW POINT - Magnus-Tetens (Buck variant)
# ============================================================
def dewpoint(temperature_c: float, humidity_rh: float) -> float:
    if humidity_rh <= 0 or temperature_c < -40 or temperature_c > 50:
        return temperature_c
    
    rh_frac = humidity_rh / 100.0
    gamma = math.log(rh_frac) + (MAGNUS_A * temperature_c) / (MAGNUS_B + temperature_c)
    dp = (MAGNUS_B * gamma) / (MAGNUS_A - gamma)
    
    return dp




def dewpoint_depression(temperature_c: float, humidity_rh: float) -> float:
    dp = dewpoint(temperature_c, humidity_rh)
    return temperature_c - dp




# ============================================================
# PRESSURE TREND - 3-hour baseline
# ============================================================
def pressure_trend_3h(history: list, current_time: datetime, current_pressure: float) -> float:
    if len(history) < 3:
        return 0.0
    
    target_time = current_time - timedelta(hours=3)
    valid_points = [x for x in history if x[0] <= target_time]
    
    if not valid_points:
        return 0.0
    
    baseline = max(valid_points, key=lambda x: x[0])
    return current_pressure - baseline[1]




# ============================================================
# PRESSURE CURVATURE
# ============================================================
def pressure_curvature(history: list, current_time: datetime, current_pressure: float) -> float:
    if len(history) < 8:
        return 0.0
    
    t_1h = current_time - timedelta(hours=1)
    points_1h = [x for x in history if x[0] <= t_1h]
    
    t_3h = current_time - timedelta(hours=3)
    points_3h = [x for x in history if x[0] <= t_3h]
    
    trend_1h = 0.0
    trend_3h = 0.0
    
    if points_1h:
        baseline_1h = max(points_1h, key=lambda x: x[0])
        trend_1h = current_pressure - baseline_1h[1]
    
    if points_3h:
        baseline_3h = max(points_3h, key=lambda x: x[0])
        trend_3h = current_pressure - baseline_3h[1]
    
    return trend_1h - trend_3h




# ============================================================
# PRESSURE ACCELERATION MODULE (Shadow Signal - Phase 1)
# ============================================================
FRONTAL_SCALE = 3.0
NOISE_THRESHOLD = 0.25
DIRECTION_VIOLATION_THRESHOLD = 0.3




def _get_pressure_trend(history: list, now: datetime, 
                        current_pressure: float, hours_back: float) -> float | None:
    target_time = now - timedelta(hours=hours_back)
    valid_points = [x for x in history if x[0] <= target_time]
    
    if not valid_points:
        return None
    
    baseline = max(valid_points, key=lambda x: x[0])
    return current_pressure - baseline[1]




def _compute_coherence(n1: float, n3: float, n6: float) -> float:
    weights = [0.5, 0.3, 0.2]
    values = [n1, n3, n6]
    
    filtered = [(v, w) for v, w in zip(values, weights) if abs(v) > NOISE_THRESHOLD]
    
    if not filtered:
        return 0.5
    
    signed = sum(math.copysign(1, v) * w for v, w in filtered)
    total = sum(w for _, w in filtered)
    
    return abs(signed) / total




def _compute_direction_consistency(n1: float, n3: float, n6: float) -> float:
    S = [n6, n3, n1]
    violations = 0
    
    for i in range(len(S) - 1):
        if abs(S[i+1]) > 0.01:
            rel_change = abs(S[i] - S[i+1]) / abs(S[i+1])
        else:
            rel_change = 0
        
        if rel_change > DIRECTION_VIOLATION_THRESHOLD:
            if math.copysign(1, S[i]) != math.copysign(1, S[i+1]):
                violations += 1
    
    return max(0.0, 1.0 - (violations / 2))




def get_pressure_acceleration(history: list, now: datetime, 
                              current_pressure: float) -> dict:
    t1 = _get_pressure_trend(history, now, current_pressure, 1)
    t3 = _get_pressure_trend(history, now, current_pressure, 3)
    t6 = _get_pressure_trend(history, now, current_pressure, 6)
    
    if None in [t1, t3, t6]:
        return {
            "valid": False, "magnitude": 0.0, "coherence": 0.5, 
            "direction_consistency": 0.5, "trend_1h": None, "trend_3h": None, 
            "trend_6h": None, "trend_1h_normalized": None, "trend_3h_normalized": None, 
            "trend_6h_normalized": None, "raw_magnitude": 0.0
        }
    
    n1 = t1
    n3 = t3 / 3
    n6 = t6 / 6
    
    raw_magnitude = 0.5 * n1 + 0.3 * n3 + 0.2 * n6
    magnitude = max(-2.0, min(2.0, raw_magnitude / FRONTAL_SCALE))
    coherence = _compute_coherence(n1, n3, n6)
    direction_consistency = _compute_direction_consistency(n1, n3, n6)
    
    return {
        "valid": True,
        "magnitude": round(magnitude, 3),
        "coherence": round(coherence, 3),
        "direction_consistency": round(direction_consistency, 3),
        "trend_1h": round(t1, 3),
        "trend_3h": round(t3, 3),
        "trend_6h": round(t6, 3),
        "trend_1h_normalized": round(n1, 3),
        "trend_3h_normalized": round(n3, 3),
        "trend_6h_normalized": round(n6, 3),
        "raw_magnitude": round(raw_magnitude, 3)
    }




def interpret_acceleration(accel_data: dict) -> str:
    if not accel_data["valid"]:
        return "no_data"
    
    mag = accel_data["magnitude"]
    coh = accel_data["coherence"]
    dir_cons = accel_data["direction_consistency"]
    
    if abs(mag) < 0.3:
        strength = "neutral"
    elif abs(mag) < 0.7:
        strength = "weak"
    else:
        strength = "strong"
    
    if abs(mag) < 0.1:
        direction = "neutral"
    elif mag > 0:
        direction = "rising"
    else:
        direction = "falling"
    
    quality = coh * dir_cons
    if quality > 0.8:
        quality_str = "high_confidence"
    elif quality > 0.5:
        quality_str = "moderate"
    else:
        quality_str = "noisy"
    
    return f"{strength}_{direction}_{quality_str}"




# ============================================================
# SEA BREEZE AUTO-DETECTION
# ============================================================
def sea_bearing(lat: float, lon: float) -> int:
    if 37.7 <= lat <= 38.3 and 23.4 <= lon <= 24.2:
        return 200  # Attica / Saronic Gulf
    if 36.8 <= lat <= 37.4 and 25.1 <= lon <= 25.7:
        return 270  # Naxos / Cyclades
    return 180  # Default: South




def is_sea_breeze(wind_dir: float, bearing: int, threshold: int = 45) -> bool:
    diff = abs(wind_dir - bearing)
    if diff > 180:
        diff = 360 - diff
    return diff <= threshold




# ============================================================
# FIXED SCORING ENGINE (Anti-Bug Edition)
# ============================================================
def _score_falling(value: float, thresholds: list) -> float:
    """For negative signals (pressure drop, negative curvature)"""
    for threshold, points in thresholds:
        if value <= threshold:
            return points
    return 0.0




def _score_rising(value: float, thresholds: list) -> float:
    """For positive signals (humidity, wind, pressure)"""
    for threshold, points in thresholds:
        if value >= threshold:
            return points
    return 0.0




def score_enhanced(
    p_abs: float, 
    h: float, 
    w_speed: float, 
    p_trend_3h: float, 
    p_curvature: float,
    breeze: bool
) -> float:
    s = 0.0
    
    # FALLING signals (negative = bad weather)
    s += _score_falling(p_trend_3h, SCORE_THRESHOLDS_FALLING["pressure_trend_3h"])
    s += _score_falling(p_curvature, SCORE_THRESHOLDS_FALLING["pressure_curvature"])
    
    # RISING signals (high values = bad weather)
    s += _score_rising(h, SCORE_THRESHOLDS_RISING["humidity"])
    s += _score_rising(w_speed, SCORE_THRESHOLDS_RISING["wind_speed"])
    s += _score_rising(p_abs, SCORE_THRESHOLDS_RISING["pressure_abs"])
    
    if breeze:
        s -= 25
    
    return max(0, min(100, s))




# ============================================================
# RAIN PROBABILITY (v8.2 - Calibrated for Greece)
# ============================================================
def rain_probability(s: float, h: float, dp_depression: float, 
                     p_curvature: float, regime: str) -> float:
    base = min(100.0, s * 1.1)
    
    # v8.2: Softened DP depression multipliers (was 1.5x)
    if dp_depression > 10:
        base *= 0.4
    elif dp_depression > 6:
        base *= 0.7
    elif dp_depression < 4:
        base *= 1.15   # v8.2: was nothing (no bonus)
    elif dp_depression < 6:
        base *= 1.05   # v8.2: was 1.5x - too aggressive for Greek summer
    
    # v8.2: Harder curvature trigger (was -0.4 → +15)
    if p_curvature < -0.7:
        base += 10     # v8.2: was -0.4 → +15
    elif p_curvature < -0.4:
        base += 5      # v8.2: new intermediate band
    
    if regime == "converging":
        base *= 1.3
    elif regime == "improving":
        base *= 0.6
    elif regime == "convective":
        base += 10
    
    return max(0, min(100, base))




# ============================================================
# REGIME DETECTION - With Hysteresis
# ============================================================
def detect_regime_base(p_trend: float, p_curvature: float, 
                      h: float, solar: float, hour: int) -> str:
    if p_curvature < -0.4 or (p_trend < -1.5 and p_curvature < -0.2):
        return "converging"
    if p_trend > 1.0 and p_curvature > 0.1:
        return "improving"
    if hour is not None and 9 <= hour <= 19:
        if h > 80 and solar > 500:
            return "convective"
    if h > 75 and p_trend > -0.5:
        return "humid_stable"
    return "normal"




def detect_regime_hysteresis(
    p_trend: float, 
    p_curvature: float, 
    h: float, 
    solar: float,
    hour: int,
    current_regime: str,
    regime_start_time: datetime | None,
    last_transition: datetime | None,
    now: datetime,
    stability_window_min: int = 30,
    cooldown_min: int = 20
) -> tuple[str, datetime, datetime]:
    proposed = detect_regime_base(p_trend, p_curvature, h, solar, hour)
    
    if regime_start_time is None:
        return proposed, now, now
    
    if proposed == current_regime:
        return current_regime, regime_start_time, last_transition
    
    elapsed = (now - regime_start_time).total_seconds() / 60
    time_since_transition = 0
    if last_transition:
        time_since_transition = (now - last_transition).total_seconds() / 60
    
    if time_since_transition < cooldown_min:
        return current_regime, regime_start_time, last_transition
    
    if elapsed < stability_window_min:
        return current_regime, regime_start_time, last_transition
    
    return proposed, now, now




# ============================================================
# SKY FUSION LAYER (v8.4 - FIXED: Season-aware dawn detection)
# ============================================================

# FIX v8.4: Dynamic dawn threshold based on solar altitude
MORNING_HOURS_START = 5   # 5:00 AM
MORNING_HOURS_END = 9     # 9:00 AM
DAWN_SOLAR_RATIO = 0.40    # 40% of day's max = dawn transition


def get_sky_confidence(solar_ratio: float, humidity: float, 
                       dp_depression: float, p_curvature: float,
                       trend_3h: float, expected_clear_sky: float,
                       hour: int = None) -> float:
    """
    v8.4 FIX: Season-aware dawn detection using dynamic threshold
    """
    is_morning = hour is not None and MORNING_HOURS_START <= hour < MORNING_HOURS_END
    
    # NIGHT MODE (expected_clear_sky < 25)
    if expected_clear_sky < 25:
        confidence = 0.50
        
        if trend_3h > 0.3:
            confidence += 0.20
        elif trend_3h > 0:
            confidence += 0.10
        
        if humidity > 85:
            confidence -= 0.05
        elif humidity < 70:
            confidence += 0.08
        
        if dp_depression > 12:
            confidence += 0.15
        elif dp_depression > 10:
            confidence += 0.10
        elif dp_depression > 8:
            confidence += 0.05
        
        # FIX v8.4: Morning bonus - expect clear morning after night
        if is_morning and confidence >= 0.50:
            confidence += 0.15
        
        return max(0.0, min(0.90, confidence))
    
    # FIX v8.4: DAWN TRANSITION - Dynamic threshold based on expected solar
    # Calculate dynamic dawn limit (40% of expected = dawn)
    # This works for ALL seasons automatically
    max_expected = get_expected_clear_sky_solar(37.94, 23.75, 
        datetime.now().replace(hour=12, minute=0))
    dawn_threshold = max_expected * DAWN_SOLAR_RATIO
    
    if expected_clear_sky < dawn_threshold:
        confidence = 0.60
        
        if expected_clear_sky > dawn_threshold * 0.5:  # Sun is rising
            if solar_ratio > 0.3:
                confidence += 0.12
            elif solar_ratio > 0.1:
                confidence += 0.06
        
        if trend_3h > 0.5:
            confidence += 0.15
        elif trend_3h > 0.2:
            confidence += 0.10
        elif trend_3h > 0:
            confidence += 0.05
        
        if is_morning:
            confidence += 0.10
        
        if dp_depression > 10:
            confidence += 0.08
        
        return max(0.0, min(0.90, confidence))
    
    # DAY MODE (normal solar conditions)
    if solar_ratio <= 0 or solar_ratio > 1.5:
        return 0.0
    
    solar_score = max(0, min(1, (solar_ratio - 0.35) / 0.45))
    humidity_score = max(0, min(1, (80 - humidity) / 30))
    
    if dp_depression > 12: dryness_bonus = 0.15
    elif dp_depression > 10: dryness_bonus = 0.08
    elif dp_depression < 6: dryness_bonus = -0.10
    else: dryness_bonus = 0.0
    
    if p_curvature > 0: stability_score = 0.1
    elif p_curvature > -0.2: stability_score = 0.05
    else: stability_score = -0.15
    
    confidence = (0.40 * solar_score + 0.20 * humidity_score + 
                  0.25 * 0.5 + 0.15 * (0.5 + stability_score))
    confidence += dryness_bonus
    
    return max(0.0, min(1.0, confidence))




def is_sky_clear(solar_ratio: float, humidity: float, 
                 rain_prob: float, p_curvature: float, 
                 dp_depression: float,
                 trend_3h: float = 0.0,
                 expected_clear_sky: float = 100.0,
                 hour: int = None) -> tuple[bool, float]:
    """
    v8.3 FIX: Added hour parameter for morning detection
    """
    sky_confidence = get_sky_confidence(
        solar_ratio, humidity, dp_depression, 
        p_curvature, trend_3h, expected_clear_sky, hour
    )
    
    rain_threshold = 25
    if dp_depression > 12: rain_threshold = 40
    elif dp_depression > 10: rain_threshold = 32
    
    risk = 0
    if rain_prob >= rain_threshold: risk += 1
    if p_curvature < -0.25: risk += 1
    
    # FIX v8.3: Lower threshold for morning hours
    is_morning = hour is not None and MORNING_HOURS_START <= hour < MORNING_HOURS_END
    confidence_threshold = 0.55 if is_morning else 0.65
    
    sky_clear = (sky_confidence > confidence_threshold and risk < 2)
    
    return sky_clear, sky_confidence




# ============================================================
# PRIMARY LABEL with HYSTERESIS (Rain as EVENT, not STATE)
# ============================================================
def get_primary_label(sky_clear: bool, sky_confidence: float, 
                      rain_prob: float, current_state: str,
                      hour: int = None) -> str:
    """
    v8.3 FIX: Reduced hysteresis thresholds for faster morning recovery
    """
    is_morning = hour is not None and MORNING_HOURS_START <= hour < MORNING_HOURS_END
    
    # RAIN EVENT (overlay, not state transition)
    if rain_prob > 75:
        return "Καταιγίδες"
    if rain_prob > 55:
        return "Βροχές"
    
    # FIX v8.3: CLEAR WEATHER with ADJUSTED HYSTERESIS
    if current_state == "Καλός καιρός":
        # Need significant drop to leave "Καλός"
        if sky_confidence < 0.35:
            if 0.35 <= sky_confidence <= 0.65:
                return "Πιθανή συννεφιά"
            return "Συννεφιά"
        return "Καλός καιρός"
    
    if current_state == "Πιθανή συννεφιά":
        # Need strong signal to go to "Καλός"
        if sky_confidence > 0.70:
            return "Καλός καιρός"
        if sky_confidence < 0.30:
            return "Συννεφιά"
        return "Πιθανή συννεφιά"
    
    if current_state == "Συννεφιά":
        # FIX v8.3: Lower threshold for morning recovery
        if is_morning:
            # During morning hours, be more aggressive about clearing
            if sky_confidence > 0.60:  # Was 0.75
                return "Καλός καιρός"
            if sky_confidence > 0.45:  # Was 0.50
                return "Πιθανή συννεφιά"
        else:
            # Normal daytime thresholds
            if sky_confidence > 0.70:  # Was 0.75
                return "Καλός καιρός"
            if sky_confidence > 0.50:  # Was 0.50
                return "Πιθανή συννεφιά"
        return "Συννεφιά"
    
    # Default (first run or unknown state)
    if sky_clear:
        return "Καλός καιρός"
    if 0.35 <= sky_confidence <= 0.65:
        return "Πιθανή συννεφιά"
    return "Συννεφιά"




def get_atmospheric_context(score: float, regime: str) -> str:
    if regime == "converging":
        return "Σύγκλιση"
    elif regime == "improving":
        return "Σταθεροποίηση"
    elif score > 60:
        return "Έντονη αστάθεια"
    elif regime == "convective":
        return "Τάση αναπτύξεων"
    elif score > 40:
        return "Θερμική δραστηριότητα"
    else:
        return "Σταθερές συνθήκες"




def forecast_text(sky_clear: bool, sky_confidence: float, score: float, 
                  rain_prob: float, regime: str, p_curvature: float, 
                  solar: float, humidity: float, current_state: str,
                  hour: int = None) -> tuple[str, str]:
    """
    v8.3 FIX: Added hour parameter
    """
    primary = get_primary_label(sky_clear, sky_confidence, rain_prob, current_state, hour)
    atmosphere = get_atmospheric_context(score, regime)
    return primary, atmosphere




# ============================================================
# GEO AUTO CONFIG (HA)
# ============================================================
def get_geo():
    try:
        elev = float(hass.config.elevation)
    except:
        elev = 210.0
    
    try:
        lat = float(state.get("zone.home.latitude"))
        lon = float(state.get("zone.home.longitude"))
        return lat, lon, elev
    except:
        return 37.94, 23.75, elev




# ============================================================
# EMA SMOOTHER
# ============================================================
def ema_smooth(current: float, previous: float | None, alpha: float = 0.25) -> float:
    if previous is None:
        return current
    return alpha * current + (1 - alpha) * previous




# ============================================================
# MAIN LOOP - Every 2 minutes
# ============================================================
@time_trigger("period(now, 2min)")
def run():
    global pressure_history, temp_history, hum_history
    global wind_history, solar_history
    global last_score, last_rain, last_dp_depression
    global current_regime, regime_start_time, last_regime_transition
    global sky_confidence_persistence, sky_streak_clear, sky_streak_cloudy
    global last_state_change_time, last_primary_state
    
    _ensure_storage()
    
    try:
        p_raw = float(state.get(PRESSURE_SENSOR))
        t = float(state.get(TEMP_SENSOR))
        h = float(state.get(HUM_SENSOR))
        w_speed = float(state.get(WIND_SPEED_SENSOR))
        w_dir = float(state.get(WIND_DIR_SENSOR))
        solar_raw = float(state.get(SOLAR_SENSOR))
    except:
        return
    
    w_speed = w_speed * 3.6 if WIND_SPEED_IS_MS else w_speed
    
    now = datetime.now()
    hour = now.hour
    lat, lon, elev = get_geo()
    bearing = sea_bearing(lat, lon)
    p = p_raw
    
    # Append new readings
    pressure_history.append((now, p))
    temp_history.append((now, t))
    hum_history.append((now, h))
    wind_history.append((now, w_speed))
    solar_history.append((now, solar_raw))
    
    # 24-hour rolling window
    cutoff = now - timedelta(hours=24)
    pressure_history = [x for x in pressure_history if x[0] >= cutoff]
    temp_history = [x for x in temp_history if x[0] >= cutoff]
    hum_history = [x for x in hum_history if x[0] >= cutoff]
    wind_history = [x for x in wind_history if x[0] >= cutoff]
    solar_history = [x for x in solar_history if x[0] >= cutoff]
    
    # Physics layer
    dp_depression = dewpoint_depression(t, h)
    dp = t - dp_depression
    p_trend_3h = pressure_trend_3h(pressure_history, now, p)
    p_curvature = pressure_curvature(pressure_history, now, p)
    
    # v8.5: Solar position (NOAA SPA)
    solar_position = get_solar_position_accurate(lat, lon, now)
    blocking_angle = _get_local_horizon_blocking(lat, lon, solar_position["azimuth"])
    
    # Solar normalization
    expected_solar = get_expected_clear_sky_solar(lat, lon, now)
    solar_ratio = solar_raw / expected_solar if expected_solar > 0 else 0
    
    breeze = False
    if 3.0 <= w_speed <= 28.0:
        breeze = is_sea_breeze(w_dir, bearing)
    
    # Dynamics layer (regime)
    new_regime, new_start_time, new_transition = detect_regime_hysteresis(
        p_trend_3h, p_curvature, h, solar_raw, hour,
        current_regime, regime_start_time, last_regime_transition,
        now,
        stability_window_min=REGIME_STABILITY_WINDOW,
        cooldown_min=REGIME_COOLDOWN
    )
    current_regime = new_regime
    regime_start_time = new_start_time
    last_regime_transition = new_transition
    
    regime_duration = 0
    if regime_start_time:
        regime_duration = (now - regime_start_time).total_seconds() / 3600
    
    # Interpretation layer
    raw_score_val = score_enhanced(p, h, w_speed, p_trend_3h, p_curvature, breeze)
    raw_rain_val = rain_probability(raw_score_val, h, dp_depression, p_curvature, current_regime)
    
    smoothed_score = ema_smooth(raw_score_val, last_score, SMOOTHING_FACTOR)
    smoothed_rain = ema_smooth(raw_rain_val, last_rain, SMOOTHING_FACTOR)
    
    # Acceleration (Phase 1 - Observer only)
    accel = get_pressure_acceleration(pressure_history, now, p)
    accel_interpretation = interpret_acceleration(accel)
    
    # Sky fusion - v8.3: Pass hour parameter
    sky_clear, sky_confidence = is_sky_clear(
        solar_ratio, h, smoothed_rain, p_curvature, 
        dp_depression, p_trend_3h, expected_solar, hour
    )
    
    # v8.2: Persistence updated to 0.4/0.6 (was 0.3/0.7)
    if sky_confidence_persistence is None:
        sky_confidence_persistent = sky_confidence
    else:
        sky_confidence_persistent = 0.4 * sky_confidence + 0.6 * sky_confidence_persistence
    
    sky_confidence_persistence = sky_confidence_persistent
    
    if sky_confidence_persistent > 0.65:
        sky_streak_clear += 1
        sky_streak_cloudy = 0
    elif sky_confidence_persistent < 0.35:
        sky_streak_cloudy += 1
        sky_streak_clear = 0
    
    if sky_streak_clear >= 3 and sky_confidence_persistent > 0.5:
        sky_clear_final = True
    elif sky_streak_cloudy >= 3 and sky_confidence_persistent < 0.6:
        sky_clear_final = False
    else:
        sky_clear_final = sky_clear
    
    # ============================================================
    # DWELL TIME CHECK (Anti-micro-flip)
    # ============================================================
    current_primary = last_primary_state if last_primary_state else "Καλός καιρός"
    
    # Get proposed state - v8.3: Pass hour parameter
    proposed_primary, fc_atmosphere = forecast_text(
        sky_clear_final, 
        sky_confidence_persistent,
        smoothed_score, 
        smoothed_rain,
        current_regime,
        p_curvature,
        solar_raw,
        h,
        current_primary,
        hour
    )
    
    # FIX v8.3: Reduced dwell time for morning hours
    is_morning = MORNING_HOURS_START <= hour < MORNING_HOURS_END
    effective_dwell = 10 if is_morning else MIN_STATE_DWELL_TIME
    
    # Apply dwell time check
    if last_state_change_time is not None:
        dwell_minutes = (now - last_state_change_time).total_seconds() / 60
        if dwell_minutes < effective_dwell:
            # Block micro-flip, keep current state
            proposed_primary = last_primary_state
    
    # Update state change tracking
    if proposed_primary != last_primary_state:
        last_state_change_time = now
        last_primary_state = proposed_primary
    
    fc_primary = proposed_primary
    
    last_score = smoothed_score
    last_rain = smoothed_rain
    last_dp_depression = dp_depression
    
    # Output
    state.set(
        "sensor.zambretti_enhanced_pro_8_4",
        value=fc_primary,
        new_attributes={
            # === Core Forecast ===
            "forecast_primary": fc_primary,
            "forecast_atmosphere": fc_atmosphere,
            
            # === Pressure Data ===
            "pressure_mslp": round(p, 1),
            "trend_3h": round(p_trend_3h, 2),
            "pressure_curvature": round(p_curvature, 3),
            
            # === Acceleration Shadow Signal (Phase 1) ===
            "acceleration_valid": accel["valid"],
            "acceleration_magnitude": accel["magnitude"],
            "acceleration_coherence": accel["coherence"],
            "acceleration_direction_consistency": accel["direction_consistency"],
            "acceleration_quality": round(
                accel["coherence"] * accel["direction_consistency"], 3
            ) if accel["valid"] else 0.0,
            "acceleration_interpretation": accel_interpretation,
            "acceleration_trend_1h": accel["trend_1h"],
            "acceleration_trend_3h": accel["trend_3h"],
            "acceleration_trend_6h": accel["trend_6h"],
            "acceleration_raw_magnitude": accel["raw_magnitude"],
            
            # === Temperature & Humidity ===
            "temperature": round(t, 1),
            "humidity": round(h, 1),
            "dewpoint": round(dp, 1),
            "dp_depression": round(dp_depression, 1),
            
            # === Wind Data ===
            "wind_speed_kmh": round(w_speed, 1),
            "wind_dir": w_dir,
            "sea_breeze": breeze,
            "sea_bearing": bearing,
            
            # === Solar Data ===
            "solar_radiation": round(solar_raw, 1),
            "solar_ratio": round(solar_ratio, 2),
            "expected_clear_sky": round(expected_solar, 0),
            
            # v8.5: Solar Position Data (NOAA SPA)
            "sun_elevation": round(solar_position["elevation"], 1),
            "sun_azimuth": round(solar_position["azimuth"], 1),
            "mountain_blocking": round(blocking_angle, 1),
            
            # === Sky State ===
            "sky_clear": sky_clear_final,
            "sky_confidence": round(sky_confidence, 2),
            # v8.3: New telemetry for debugging
            "sky_confidence_raw": round(sky_confidence, 3),
            "sky_confidence_persistent": round(sky_confidence_persistent, 3),
            
            # === Rain (EVENT, not STATE) ===
            "rain_probability": round(smoothed_rain, 1),
            "rain_event": smoothed_rain > 55,
            
            # === Scoring ===
            "score": round(smoothed_score, 1),
            
            # === Regime ===
            "weather_regime": current_regime,
            "regime_duration_h": round(regime_duration, 1),
            
            # === Stability Metrics ===
            "dwell_time_min": round(
                (now - last_state_change_time).total_seconds() / 60 
                if last_state_change_time else 0, 1
            ),
            
            # === Location ===
            "lat": lat,
            "lon": lon,
            "elevation": elev,
            
            # === Version ===
            "version": "8.10",
            
            # === Timestamp ===
            "timestamp": now.isoformat()
        }
    )