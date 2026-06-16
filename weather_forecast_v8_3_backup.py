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
    Ακριβής υπολογισμός θέσης ήλιου (NOAA SPA)
    """
    JD = _calculate_julian_date(dt)
    n = JD - 2451545.0
    Jstar = n - lon / 360.0
    M = (357.5291 + 0.98560028 * Jstar) % 360
    Mrad = math.radians(M)
    
    C = 1.9148 * math.sin(Mrad) + 0.0200 * math.sin(2*Mrad) + 0.0003 * math.sin(3*Mrad)
    L = (M + C + 180 + 102.9372) % 360
    Lrad = math.radians(L)
    obliquity = 23.4393 - 0.0000004 * n
    obliquity_rad = math.radians(obliquity)
    
    ra = math.atan2(math.cos(obliquity_rad) * math.sin(Lrad), math.cos(Lrad))
    declination = math.asin(math.sin(obliquity_rad) * math.sin(Lrad))
    
    GMST = (280.4606 + 360.9856474 * (JD - 2451545.0)) % 360
    LST = (GMST + lon) % 360
    ha = math.radians(LST - math.degrees(ra))
    
    lat_rad = math.radians(lat)
    cos_zenith = (math.sin(lat_rad) * math.sin(declination) + 
                  math.cos(lat_rad) * math.cos(declination) * math.cos(ha))
    zenith = math.degrees(math.acos(max(-1, min(1, cos_zenith))))
    elevation = 90 - zenith
    
    try:
        cos_az = (math.sin(declination) - math.sin(lat_rad) * cos_zenith) / \
                 (math.cos(lat_rad) * math.sin(math.radians(max(0.1, 90 - elevation))))
        cos_az = max(-1, min(1, cos_az))
        az = math.degrees(math.acos(cos_az))
        if ha > 0:
            az = 360 - az
    except:
        az = 0
    
    return {
        "elevation": elevation,
        "azimuth": az % 360,
        "zenith": zenith,
        "declination": math.degrees(declination),
        "is_above_horizon": elevation > 0
    }


def _get_local_horizon_blocking(lat: float, lon: float, azimuth: float) -> float:
    """
    v8.7: Πλήρες SRTM-style horizon profile
    Υπολογίζει τον αποκλεισμό βάσει θέσης ήλιου (αζιμούθιο)
    Επιστρέφει γωνία αποκλεισμού σε μοίρες (0 αν ο ήλιος δεν είναι πίσω από βουνό)
    """
    # Βάση δεδομένων Ελληνικών βουνών
    MOUNTAINS_DB = [
        # (lat, lon, height, name, spread_degrees)
        (37.915, 23.78, 1026, "Υμηττός", 20),
        (38.05, 23.73, 1410, "Πάρνηθα", 25),
        (38.0, 23.57, 487, "Αιγάλεω", 15),
        (40.55, 22.95, 1201, "Χορτιάτης", 18),
        (38.22, 21.72, 1926, "Παναχαϊκό", 22),
        (38.28, 21.78, 719, "Άρτεμις", 12),
        (40.0, 22.35, 2918, "Όλυμπος", 35),
        (40.2, 20.9, 2520, "Γράμμος", 28),
        (35.27, 24.93, 2456, "Ψηλορείτης", 18),
        (35.40, 24.0, 2452, "Λευκά Όρη", 20),
    ]
    
    max_blocking = 0.0
    
    for mountain in MOUNTAINS_DB:
        m_lat, m_lon, height, name, spread = mountain
        
        # Υπολογισμός απόστασης (Haversine)
        R = 6371
        dlat = math.radians(m_lat - lat)
        dlon = math.radians(m_lon - lon)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat)) * math.cos(math.radians(m_lat)) * math.sin(dlon/2)**2
        distance = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        if distance > 100 or distance < 1:  # Εκτός εμβέλειας ή πάνω στο βουνό
            continue
        
        # Υπολογισμός αζιμουθίου προς το βουνό
        dlon_r = math.radians(m_lon - lon)
        lat_r = math.radians(lat)
        m_lat_r = math.radians(m_lat)
        x = math.sin(dlon_r) * math.cos(m_lat_r)
        y = math.cos(lat_r) * math.sin(m_lat_r) - math.sin(lat_r) * math.cos(m_lat_r) * math.cos(dlon_r)
        mountain_az = (math.degrees(math.atan2(x, y)) + 360) % 360
        
        # ΕΛΕΓΧΟΣ: Ο ήλιος πρέπει να είναι προς την κατεύθυνση του βουνού
        az_diff = abs(azimuth - mountain_az)
        if az_diff > 180:
            az_diff = 360 - az_diff
        
        # Μόνο αποκλεισμός αν ο ήλιος είναι κοντά στο βουνό (±spread)
        if az_diff > spread:
            continue
        
        # Υπολογισμός γωνίας αποκλεισμού
        base_angle = math.degrees(math.atan(height / (distance * 1000)))
        
        # Μείωση αν ο ήλιος είναι στο άκρο του spread
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
            "version": "8.7",
            
            # === Timestamp ===
            "timestamp": now.isoformat()
        }
    )