"""
Zambretti Enhanced Pro v8.8 - FIXED Solar Position
Χρήση datetime.now() για σωστή ώρα
"""

import math
from datetime import datetime, timedelta

def get_solar_position_fixed(lat: float, lon: float, dt: datetime) -> dict:
    """
    Διορθωμένος υπολογισμός θέσης ήλιου
    Χρησιμοποιεί datetime.now() για σωστή ώρα
    """
    # Μετατροπή σε UTC (Greece = UTC+3 θερινή ώρα)
    utc_offset = 3  # ώρες
    utc_dt = dt - timedelta(hours=utc_offset)
    
    # Julian Day
    year = utc_dt.year
    month = utc_dt.month
    day = utc_dt.day + utc_dt.hour/24.0 + utc_dt.minute/1440.0 + utc_dt.second/86400.0
    
    if month <= 2:
        year -= 1
        month += 12
    
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    JD = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
    
    # Days since J2000.0
    n = JD - 2451545.0
    
    # Solar Mean Anomaly
    M = math.radians((357.5291 + 0.98560028 * n) % 360)
    
    # Equation of Center
    C = (1.9148 * math.sin(M) + 0.0200 * math.sin(2*M) + 0.0003 * math.sin(3*M))
    
    # Ecliptic Longitude
    L = math.radians((280.4606 + 0.9856474 * n + C + 180) % 360)
    
    # Obliquity of Ecliptic
    obl = math.radians(23.4393 - 0.0000004 * n)
    
    # Right Ascension
    RA = math.atan2(math.cos(obl) * math.sin(L), math.cos(L))
    
    # Declination
    decl = math.asin(math.sin(obl) * math.sin(L))
    
    # Greenwich Mean Sidereal Time
    GMST = math.radians((280.4606 + 360.9856474 * n) % 360)
    
    # Local Sidereal Time
    LST = GMST + math.radians(lon)
    
    # Hour Angle
    HA = LST - RA
    
    # Συντεταγμένες σε radians
    lat_rad = math.radians(lat)
    
    # Solar Zenith Angle
    cos_zenith = (math.sin(lat_rad) * math.sin(decl) + 
                   math.cos(lat_rad) * math.cos(decl) * math.cos(HA))
    cos_zenith = max(-1, min(1, cos_zenith))
    zenith = math.degrees(math.acos(cos_zenith))
    elevation = 90 - zenith
    
    # Solar Azimuth (από Βορρά προς Ανατολή)
    sin_az = -math.cos(decl) * math.sin(HA) / math.sin(math.radians(zenith))
    cos_az = (math.sin(decl) - math.sin(lat_rad) * cos_zenith) / \
             (math.cos(lat_rad) * math.sin(math.radians(zenith)))
    
    sin_az = max(-1, min(1, sin_az))
    cos_az = max(-1, min(1, cos_az))
    
    azimuth = math.degrees(math.acos(cos_az))
    
    # Διόρθωση για afternoon
    if math.degrees(HA) > 0:
        azimuth = 360 - azimuth
    
    return {
        "elevation": elevation,
        "azimuth": azimuth % 360,
        "declination": math.degrees(decl),
        "is_above_horizon": elevation > 0
    }


# ==================== ΤΕΣΤ ====================
if __name__ == "__main__":
    lat, lon = 37.938, 23.767
    
    print("=== ΤΕΣΤ ΔΙΟΡΘΩΜΕΝΟΥ ΑΛΓΟΡΙΘΜΟΥ ===")
    print(f"Συντεταγμένες: {lat}°, {lon}°")
    print("")
    
    # Τεστ σε διάφορες ώρες
    for hour in [10, 11, 12, 13, 14, 15]:
        for minute in [0, 30]:
            dt = datetime(2026, 6, 16, hour, minute)
            result = get_solar_position_fixed(lat, lon, dt)
            az_dir = "Β" if 315 <= result['azimuth'] < 45 else \
                     "Α" if 45 <= result['azimuth'] < 135 else \
                     "Ν" if 135 <= result['azimuth'] < 225 else \
                     "Δ" if 225 <= result['azimuth'] < 315 else "?"
            marker = " ◄◄◄" if hour == 12 and minute == 16 else ""
            print(f"{hour:02d}:{minute:02d} Local - Elev: {result['elevation']:5.1f}° | Az: {result['azimuth']:6.1f}° ({az_dir}){marker}")
    
    print("")
    print("=== ΣΥΓΚΡΙΣΗ ===")
    dt_now = datetime(2026, 6, 16, 12, 16)
    result = get_solar_position_fixed(lat, lon, dt_now)
    print(f"12:16 Local: Elev={result['elevation']:.1f}°, Az={result['azimuth']:.1f}°")
    print(f"Άλλες εφαρμογές: Elev≈65.9°, Az≈120.8°")
    
    diff_elev = abs(result['elevation'] - 65.9)
    diff_az = abs(result['azimuth'] - 120.8)
    
    print(f"Διαφορά: Elev={diff_elev:.1f}°, Az={diff_az:.1f}°")
    
    if diff_elev < 5 and diff_az < 10:
        print("✓ ΣΩΣΤΟ!")
    else:
        print("✗ ΛΑΘΟΣ!")
