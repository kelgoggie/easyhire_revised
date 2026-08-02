"""Iloilo City barangay → district mapping for the analytics dashboard.

Iloilo City is administratively split into 7 districts (Arevalo, City Proper,
Jaro, La Paz, Lapuz, Mandurriao, Molo). Barangay names in the DB come from
mixed sources — free-text addresses, seed data that already uses district
names, PSGC-loaded proper barangay names — so we normalise before looking up.

Note on ambiguity: several barangay names (Buhang, San Isidro, San Jose,
Loboc, Luna, Sto. Niño, …) exist in multiple districts. We pick the most
common / primary assignment for each. Good enough for a bar chart aggregating
15+ rows into 7 buckets; not a substitute for a PSGC-level district lookup.
"""
import re


DISTRICTS = ['Arevalo', 'City Proper', 'Jaro', 'La Paz', 'Lapuz', 'Mandurriao', 'Molo']

# Normalised (lowercased, punctuation-lite) barangay/address token → district.
BARANGAY_TO_DISTRICT = {
    # ─── District names themselves ─────────────────────────────────────
    'arevalo': 'Arevalo',
    'villa arevalo': 'Arevalo',
    'city proper': 'City Proper',
    'iloilo city proper': 'City Proper',
    'jaro': 'Jaro',
    'la paz': 'La Paz',
    'lapaz': 'La Paz',
    'lapuz': 'Lapuz',
    'mandurriao': 'Mandurriao',
    'molo': 'Molo',

    # ─── Arevalo barangays ─────────────────────────────────────────────
    'arevalo proper': 'Arevalo',
    'bito-on': 'Arevalo',
    'calaparan': 'Arevalo',
    'dulonan': 'Arevalo',
    'mohon': 'Arevalo',
    'quezon': 'Arevalo',
    'santa cruz': 'Arevalo',
    'sta cruz': 'Arevalo',
    'santa filomena': 'Arevalo',
    'sta filomena': 'Arevalo',
    'santo domingo': 'Arevalo',
    'sto domingo': 'Arevalo',
    'sooc': 'Arevalo',
    'tanza-baybay': 'Arevalo',
    'tanza baybay': 'Arevalo',
    'tanza-esperanza': 'Arevalo',
    'tanza esperanza': 'Arevalo',
    'yulo drive': 'Arevalo',

    # ─── City Proper barangays ─────────────────────────────────────────
    'aduana': 'City Proper',
    'baldoza': 'City Proper',
    'concepcion-montes': 'City Proper',
    'concepcion montes': 'City Proper',
    'danao': 'City Proper',
    'delgado-jalandoni-bagumbayan': 'City Proper',
    'flores': 'City Proper',
    'gen. hughes': 'City Proper',
    'gen hughes': 'City Proper',
    'general hughes': 'City Proper',
    'gloria': 'City Proper',
    'hipodromo': 'City Proper',
    'inday': 'City Proper',
    'jalandoni-wilson': 'City Proper',
    'jalandoni wilson': 'City Proper',
    'kahirupan': 'City Proper',
    'kauswagan': 'City Proper',        # also exists in Molo
    'legaspi de la rama': 'City Proper',
    'liberation': 'City Proper',
    'loboc': 'City Proper',            # also La Paz / Lapuz
    'malipayon-delgado': 'City Proper',
    'malipayon delgado': 'City Proper',
    'maria clara': 'City Proper',
    'mabolo-delgado': 'City Proper',
    'muelle loney-montes': 'City Proper',
    'muelle loney': 'City Proper',
    'nonoy': 'City Proper',
    'ortiz': 'City Proper',
    'osmena': 'City Proper',
    'osmeña': 'City Proper',
    'president roxas': 'City Proper',
    'rima-rizal': 'City Proper',
    'rizal estanzuela': 'City Proper',
    'rizal ibarra': 'City Proper',
    'rizal palapala i': 'City Proper',
    'rizal palapala ii': 'City Proper',
    'roxas village': 'City Proper',
    'san agustin': 'City Proper',
    'san felipe': 'City Proper',
    'san jose': 'City Proper',         # ambiguous, defaulting
    'san pedro': 'City Proper',        # ambiguous
    'san roque': 'City Proper',        # ambiguous
    'santa rosa': 'City Proper',
    'sta rosa': 'City Proper',
    'timawa': 'City Proper',
    'zamora-melliza': 'City Proper',

    # ─── Jaro barangays ────────────────────────────────────────────────
    'aganan': 'Jaro',
    'anilaw': 'Jaro',
    'balabago': 'Jaro',
    'balantang': 'Jaro',
    'bangkerohan': 'Jaro',
    'benedicto': 'Jaro',
    'buhang': 'Jaro',                  # ambiguous (also Mandurriao)
    'buhang taft north': 'Jaro',
    'buntatala': 'Jaro',
    'camalig': 'Jaro',
    'cubay': 'Jaro',
    'cuartero': 'Jaro',
    'democracia': 'Jaro',
    'desamparados': 'Jaro',
    'dungon a': 'Jaro',
    'dungon b': 'Jaro',
    'el 98 castilla': 'Jaro',
    'fajardo': 'Jaro',
    'javellana': 'Jaro',
    'jibao-an': 'Jaro',
    'jibaoan': 'Jaro',
    'laguda': 'Jaro',
    'lanit': 'Jaro',
    'libertad-sta. isabel': 'Jaro',
    'libertad sta isabel': 'Jaro',
    'lopez jaena norte': 'Jaro',
    'lopez jaena sur': 'Jaro',
    'luna': 'Jaro',                    # ambiguous
    'macarthur': 'Jaro',               # ambiguous
    'magsaysay': 'Jaro',
    'mansaya': 'Jaro',
    'montinola': 'Jaro',
    'our lady of lourdes': 'Jaro',
    'quintin salas': 'Jaro',
    'sambag': 'Jaro',
    'san isidro': 'Jaro',              # ambiguous
    'san vicente': 'Jaro',
    'simon ledesma': 'Jaro',
    'tabuc suba': 'Jaro',              # ambiguous
    'tabucan': 'Jaro',
    'tacas': 'Jaro',
    'taft north': 'Jaro',
    'taft south': 'Jaro',
    'tap-oc': 'Jaro',
    'tapoc': 'Jaro',
    'ticud': 'Jaro',
    'yulo-arroyo': 'Jaro',
    'yulo arroyo': 'Jaro',
    'sto niño norte': 'Jaro',
    'sto nino norte': 'Jaro',

    # ─── La Paz barangays ──────────────────────────────────────────────
    'la paz proper': 'La Paz',
    'lapaz proper': 'La Paz',
    'bantud': 'La Paz',
    'burgos-mabini-plaza': 'La Paz',
    'burgos mabini plaza': 'La Paz',
    'caingin': 'La Paz',
    'divinagracia': 'La Paz',
    'gustilo': 'La Paz',
    'hinactacan': 'La Paz',
    'ingore': 'La Paz',
    'jereos': 'La Paz',
    'magdalo': 'La Paz',
    'magsaysay village': 'La Paz',
    'nabitasan': 'La Paz',
    'our lady of fatima': 'La Paz',
    'punong': 'La Paz',
    'railway': 'La Paz',
    'rizal': 'La Paz',
    'san nicolas': 'La Paz',
    'santo nino sur': 'La Paz',
    'sto niño sur': 'La Paz',
    'sto nino sur': 'La Paz',
    'trece de marzo': 'La Paz',

    # ─── Mandurriao barangays ──────────────────────────────────────────
    'airport': 'Mandurriao',
    'bakhaw': 'Mandurriao',
    'bolilao': 'Mandurriao',
    'calahunan': 'Mandurriao',
    'guzman-jesena': 'Mandurriao',
    'guzman jesena': 'Mandurriao',
    'hibao-an norte': 'Mandurriao',
    'hibaoan norte': 'Mandurriao',
    'hibao-an sur': 'Mandurriao',
    'hibaoan sur': 'Mandurriao',
    'navais': 'Mandurriao',
    'oso': 'Mandurriao',
    'phhc': 'Mandurriao',
    'san rafael': 'Mandurriao',

    # ─── Molo barangays ────────────────────────────────────────────────
    'bonifacio': 'Molo',
    'calumpang': 'Molo',
    'compania': 'Molo',
    'east baluarte': 'Molo',
    'east timawa': 'Molo',
    'habog-habog salvacion': 'Molo',
    'habog habog salvacion': 'Molo',
    'infante': 'Molo',
    'katilingban': 'Molo',
    'molo boulevard': 'Molo',
    'north fundidor': 'Molo',
    'north san jose': 'Molo',
    'poblacion': 'Molo',
    'san antonio': 'Molo',
    'san juan': 'Molo',
    'south baluarte': 'Molo',
    'south fundidor': 'Molo',
    'south san jose': 'Molo',
    'west habog-habog': 'Molo',
    'west habog habog': 'Molo',
    'west timawa': 'Molo',

    # ─── Lapuz barangays ───────────────────────────────────────────────
    'alalasan lapuz': 'Lapuz',
    'don esteban-lapuz': 'Lapuz',
    'don esteban lapuz': 'Lapuz',
    'jalandoni estate-lapuz': 'Lapuz',
    'jalandoni estate lapuz': 'Lapuz',
    'lapuz norte': 'Lapuz',
    'lapuz sur': 'Lapuz',
    'loboc-lapuz': 'Lapuz',
    'loboc lapuz': 'Lapuz',
    'obrero-lapuz': 'Lapuz',
    'obrero lapuz': 'Lapuz',
    'progreso-lapuz': 'Lapuz',
    'progreso lapuz': 'Lapuz',
    'punong-lapuz': 'Lapuz',
    'punong lapuz': 'Lapuz',
    'sinikway': 'Lapuz',
    'bangkerohan lapuz': 'Lapuz',
}


_STREET_SUFFIX = re.compile(
    r'\s+(?:street|st\.?|avenue|ave\.?|road|rd\.?|drive|dr\.?|blvd\.?|boulevard|highway|hwy\.?|lane|ln\.?|purok|zone)$',
    re.IGNORECASE,
)


def _normalise(raw):
    """Lowercase, strip city suffix, strip street suffix, strip stray punctuation."""
    if not raw:
        return ''
    s = str(raw).strip().lower()
    # Drop trailing ", Iloilo City" / ", Iloilo" so 'Molo, Iloilo City' → 'molo'
    s = re.sub(r',\s*iloilo(\s+city)?\s*$', '', s)
    s = _STREET_SUFFIX.sub('', s).strip()
    # Collapse repeated whitespace
    s = re.sub(r'\s+', ' ', s)
    # Strip leading/trailing periods and commas
    s = s.strip('.,')
    return s


def resolve_district(raw):
    """Map a barangay/address string to one of the 7 Iloilo City districts.

    Order of resolution:
      1. Exact match on the normalised full string.
      2. District-name substring match ('molo boulevard' → Molo).
      3. First-token exact match (helpful when the raw value is
         'Jaro, Iloilo City' or 'La Paz Proper Purok 5').
      4. Fallback: 'Other' — surfaces non-Iloilo-City rows without breaking
         the aggregation.
    """
    n = _normalise(raw)
    if not n:
        return 'Other'

    if n in BARANGAY_TO_DISTRICT:
        return BARANGAY_TO_DISTRICT[n]

    # District names in the middle of a longer string ('Molo Boulevard').
    # Ordered longest-first so 'la paz' beats 'jaro' when both would match.
    for key in ('city proper', 'la paz', 'lapaz', 'villa arevalo',
                'arevalo', 'mandurriao', 'jaro', 'molo', 'lapuz'):
        if key in n:
            return {'lapaz': 'La Paz', 'la paz': 'La Paz'}.get(key, key.title())

    # First token — 'jaro proper', 'molo boulevard' after suffix strip, etc.
    first = n.split(' ', 1)[0]
    if first in BARANGAY_TO_DISTRICT:
        return BARANGAY_TO_DISTRICT[first]

    return 'Other'
