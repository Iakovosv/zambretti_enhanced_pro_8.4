# 🌦️ Zambretti Enhanced Pro v8.7

**Προηγμένο σύστημα πρόβλεψης καιρού για Home Assistant με αισθητήρα Ecowitt GW2000A**

Βασισμένο στον αλγόριθμο Zambretti με πρόσθετα χαρακτηριστικά:
- Ανίχνευση θαλάσσιας αύρας
- Υπολογισμός σημείου δρόσου
- Ανάλυση τάσης πίεσης (curvature, acceleration)
- Fusion αισθητήρα ηλιακής ακτινοβολίας
- Αυτόματη ανίχνευση καιρικού καθεστώτος (regime detection)

---

## 📋 Περιεχόμενα

- [Χαρακτηριστικά](#-χαρακτηριστικά)
- [Απαιτήσεις](#-απαιτήσεις)
- [Εγκατάσταση](#-εγκατάσταση)
- [Διαμόρφωση](#-διαμόρφωση)
- [Αισθητήρες Εξόδου](#-αισθητήρες-εξόδου)
- [Αλγόριθμος](#-αλγόριθμος)
- [Changelog](#-changelog)
- [Συνεισφορά](#-συνεισφορά)
- [Άδεια](#-άδεια)

---

## ✨ Χαρακτηριστικά

### 🌡️ Φυσικές Μετρήσεις
- **Σχετική Πίεση**: Χρήση πίεσης αισθητήρα (όχι MSLP) για ακρίβεια
- **Θερμοκρασία/Υγρασία**: Υπολογισμός σημείου δρόσου (Magnus-Tetens Buck 1981)
- **Ηλιακή Ακτινοβολία**: Κανονικοποίηση βάσει γεωγραφικού πλάτους/μήκους

### 📊 Ανάλυση Τάσεων
- **3-ωρη τάση πίεσης**: Βασικός δείκτης μεταβολής καιρού
- **Πίεση Curvature**: Ανίχνευση επιτάχυνσης/επιβράδυνσης
- **Pressure Acceleration (Phase 1)**: Σκιώδες σήμα για μελλοντική χρήση

### 🌊 Θαλάσσια Αύρα
- Αυτόματη ανίχνευση για Αττική και Κυκλάδες
- Προσαρμοσμένη κατεύθυνση ανέμου ανά περιοχή

### 🎯 Ανίχνευση Καθεστώτος
- **Converging**: Σύγκλιση αέριων μαζών → πιθανές βροχές
- **Improving**: Βελτίωση καιρού
- **Convective**: Θερμική αστάθεια (9:00-19:00)
- **Humid Stable**: Υγρές σταθερές συνθήκες
- **Normal**: Κανονικές συνθήκες

### ☀️ Ηλιακός Υπολογισμός (v8.7)
- **NOAA Solar Position Algorithm**: Ακριβής υπολογισμός θέσης ήλιου
- **SRTM-Style Horizon Profile**: Πλήρες προφίλ ορίζοντα βάσει θέσης ήλιου
- **Αυτόματος υπολογισμός αποκλεισμού**: Μόνο όταν ο ήλιος είναι πίσω από βουνό
- **Ελληνική Βάση Βουνών**: 10+ βουνά σε όλη την Ελλάδα
- **Δυναμικό κατώφλι αυγής**: 40% της μέγιστης ηλιακής ακτινοβολίας

### 🔄 Hysteresis & Anti-Micro-Flip
- Ελάχιστος χρόνος παραμονής κατάστασης (25 λεπτά)
- Cooldown μεταξύ αλλαγών κατάστασης
- Αντιστροφή ορίων για αποφυγή ταλάντωσης

---

## 📋 Απαιτήσεις

### Υλικό
- **Home Assistant** (2024.1 ή νεότερο)
- **Ecowitt GW2000A** (ή συμβατός αισθητήρας)
- **WiFi Gateway** (π.χ. GW1000, WH2650)

### Home Assistant Configuration
```yaml
# configuration.yaml
homeassistant:
  packages:
    zambretti: !include zambretti_enhanced_pro_8_3.yaml
```

---

## 🔧 Εγκατάσταση

### Βήμα 1: Αντιγραφή Αρχείου
Αντιγράψτε το `zambretti_enhanced_pro_8_3.yaml` στον φάκελο `config/packages/`

### Βήμα 2: Διαμόρφωση Αισθητήρων
Ενημερώστε τα entity IDs στο αρχείο αν χρειάζεται:
```yaml
sensor:
  - platform: template
    sensors:
      zambretti_enhanced_pro_8_2:
        value_template: "{{ states('sensor.zambretti_enhanced_pro_8_2') }}"
        attribute_templates:
          # ... τα attributes
```

### Βήμα 3: Επανεκκίνηση
```bash
ha core restart
```

---

## ⚙️ Διαμόρφωση

### Αισθητήρες Εισόδου
```python
PRESSURE_SENSOR = "sensor.gw2000a_relative_pressure"
TEMP_SENSOR = "sensor.gw2000a_outdoor_temperature"
HUM_SENSOR = "sensor.gw2000a_humidity"
WIND_SPEED_SENSOR = "sensor.gw2000a_wind_speed"
WIND_DIR_SENSOR = "sensor.gw2000a_wind_direction"
SOLAR_SENSOR = "sensor.gw2000a_solar_radiation"
```

### Παράμετροι Λογικής
```python
# Ώρες πρωινού (για morning boost)
MORNING_HOURS_START = 5   # 5:00 π.μ.
MORNING_HOURS_END = 9     # 9:00 π.μ.

# Όριο αυγής (W/m²)
DAWN_UPPER_LIMIT = 400

# Χρόνοι σταθερότητας
REGIME_STABILITY_WINDOW = 30  # λεπτά
REGIME_COOLDOWN = 20          # λεπτά
MIN_STATE_DWELL_TIME = 25      # λεπτά

# Hysteresis
STATE_UPPER_HYSTERESIS = 48
STATE_LOWER_HYSTERESIS = 38

# Smoothing
SMOOTHING_FACTOR = 0.25
```

---

## 📊 Αισθητήρες Εξόδου

### Κύριος Αισθητήρας
```
sensor.zambretti_enhanced_pro_8_2
```

### Attributes

| Attribute | Περιγραφή | Μονάδα |
|-----------|-----------|--------|
| `forecast_primary` | Κύρια πρόβλεψη | - |
| `forecast_atmosphere` | Ατμοσφαιρικές συνθήκες | - |
| `pressure_mslp` | Πίεση | hPa |
| `trend_3h` | Τάση 3 ωρών | hPa |
| `pressure_curvature` | Καμπυλότητα πίεσης | hPa/h |
| `temperature` | Θερμοκρασία | °C |
| `humidity` | Υγρασία | % |
| `dewpoint` | Σημείο δρόσου | °C |
| `dp_depression` | Κατάθλιψη δρόσου | °C |
| `wind_speed_kmh` | Ταχύτητα ανέμου | km/h |
| `wind_dir` | Διεύθυνση ανέμου | ° |
| `sea_breeze` | Ανίχνευση αύρας | true/false |
| `solar_radiation` | Ηλιακή ακτινοβολία | W/m² |
| `solar_ratio` | Λόγος ηλιακής/αναμενόμενης | - |
| `sky_clear` | Καθαρός ουρανός | true/false |
| `sky_confidence` | Εμπιστοσύνη ουρανού | 0-1 |
| `rain_probability` | Πιθανότητα βροχής | % |
| `weather_regime` | Καθεστώς καιρού | - |
| `version` | Έκδοση κώδικα | - |
| `timestamp` | Χρονοσημαντήρα | ISO |

---

## 🧮 Αλγόριθμος

### Ροή Επεξεργασίας

```
┌─────────────┐
│   Sensors   │
└──────┬──────┘
       ▼
┌─────────────┐
│  Physics    │ ← Dewpoint, Pressure Trend, Curvature
└──────┬──────┘
       ▼
┌─────────────┐
│  Dynamics   │ ← Regime Detection with Hysteresis
└──────┬──────┘
       ▼
┌─────────────┐
│Interpretation│ ← Scoring, Rain Probability
└──────┬──────┘
       ▼
┌─────────────┐
│ Sky Fusion  │ ← Solar + Humidity + Pressure
└──────┬──────┘
       ▼
┌─────────────┐
│  Primary    │ ← Hysteresis + Dwell Time
│   Label     │
└─────────────┘
```

### Τύποι

**Σημείο Δρόσου (Magnus-Tetens)**
```
γ = ln(RH/100) + (A·T) / (B + T)
Td = (B·γ) / (A - γ)
```

**Τάση Πίεσης 3-ωρη**
```
ΔP = P_current - P_3h_ago
```

**Πιθανότητα Βροχής**
```
P_rain = min(100, score × 1.1 × modifiers)
```

---

## 📝 Changelog

### v8.7 (2024-06-15)
#### Διόρθωση Horizon Profile
- **Ακριβής έλεγχος κατεύθυνσης**: Ο αποκλεισμός εφαρμόζεται ΜΟΝΟ όταν ο ήλιος είναι προς την κατεύθυνση του βουνού
- **Spread angle**: Κάθε βουνό έχει "spread" που καθορίζει σε ποιες κατευθύνσεις επηρεάζει
- **Παράδειγμα**: Υμηττός (spread=20°) → Μπλοκάρει μόνο όταν ο ήλιος είναι στα 122°-162°

### v8.6 (2024-06-15)
#### Αυτόματη Τοπογραφία
- **Αυτόματος υπολογισμός αποκλεισμού**: Βασίζεται σε lat/lon/elevation από το HA

#### Νέα Attributes
- `sun_elevation`: Πραγματικό ύψος ήλιου (°)
- `sun_azimuth`: Αζιμούθιο ήλιου (°)
- `mountain_blocking`: Γωνία αποκλεισμού από βουνά (°)

### v8.4 (2024-06-15)
#### Διόρθωση Εποχών
- **Dynamic Dawn Threshold**: Αντικαταστάθηκε το fixed `DAWN_UPPER_LIMIT=400` με δυναμικό υπολογισμό
- **DAWN_SOLAR_RATIO = 0.40**: Κατώφλι αυγής = 40% της μέγιστης ηλιακής ακτινοβολίας της ημέρας
- Λειτουργεί πλέον σωστά σε **ΧΕΙΜΩΝΑ**, **ΑΝΟΙΞΗ**, **ΚΑΛΟΚΑΙΡΙ**, **ΦΘΙΝΟΠΩΡΟ**

### v8.3 (2024-06-15)
#### Διορθώσεις
- **Dawn/Night Detection**: Βελτιωμένη ανίχνευση καθαρού ουρανού τις πρωινές ώρες
- **Morning Boost**: +0.10 bonus για ώρες 5:00-9:00
- **Hysteresis Thresholds**: Μειωμένα για πρωί (0.60 αντί 0.75)
- **Night Logic**: Χρήση pressure trend αντί για υγρασία
- **Reduced Humidity Penalty**: -0.05 αντί -0.12 για υγρασία >85%

### v8.2 (2024-06-10)
- Calibrated για Ελλάδα
- Βελτιωμένη λογική dewpoint depression
- Προσαρμοσμένα thresholds

### v8.1
- Προσθήκη Pressure Acceleration (Phase 1)
- Βελτιωμένο regime detection

### v8.0
- Αρχική έκδοση με Zambretti enhancement

---

## 🤝 Συνεισφορά

1. Fork το repository
2. Δημιουργία feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit αλλαγών (`git commit -m 'Add AmazingFeature'`)
4. Push στο branch (`git push origin feature/AmazingFeature`)
5. Άνοιγμα Pull Request

---

## 📄 Άδεια

Διανέμεται υπό την MIT License. Δείτε το αρχείο `LICENSE` για λεπτομέρειες.

---

## 👤 Συγγραφέας

**Iakovosv** - [GitHub Profile](https://github.com/Iakovosv)

---

## 🙏 Ευχαριστίες

- Βασισμένο στον αλγόριθμο [Zambretti](https://en.wikipedia.org/wiki/Zambretti_forecaster)
- Magnus-Tetens formula (Buck 1981)
- Κοινότητα Home Assistant για την υποστήριξη

---

⭐ Αν σας φάνηκε χρήσιμο, αφήστε ένα αστέρι στο repo!