"""Resume parser supporting PDFs and image-based resumes (JPG / PNG / HEIC).

Pipeline:
  1. Detect the upload's content type from the bytes (magic numbers).
  2. PDF → pdfplumber first; if that yields almost no text, OCR the rendered
     pages with pytesseract (image-based / scanned PDFs).
  3. Image → register HEIF, decode with Pillow, OCR with pytesseract.
  4. Pull out structured fields with regex + keyword heuristics on the text.

OCR gracefully no-ops when Tesseract isn't available — the parser still
returns a clean ``ok=False`` error instead of crashing the request.
"""

from __future__ import annotations

import io
import re
from typing import Optional

import pdfplumber


# ── Regex patterns ────────────────────────────────────────────────────
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Philippine mobile: 09XXXXXXXXX  or  +63 9XX XXX XXXX  or  639XXXXXXXXX
PHONE_RE = re.compile(
    r'(?:\+?63|0)\s*9\d{2}[\s\-]?\d{3}[\s\-]?\d{4}'
)

# Year ranges like "2018 - 2022", "2020-Present", "Jan 2019 – Mar 2022"
YEAR_RANGE_RE = re.compile(
    r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4})\s*[\-–to]+\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4}|Present|present|Current|current)',
    re.IGNORECASE,
)

DEGREE_KEYWORDS = [
    ('doctorate',    [r'\bph\.?d\.?', r'\bdoctorate', r'\bdoctoral']),
    ('master',       [r'\bm\.?a\.?\b', r'\bm\.?s\.?\b', r"\bmaster'?s?", r'\bmba\b']),
    ('bachelor',     [r"\bbachelor'?s?", r'\bb\.?s\.?\b', r'\bb\.?a\.?\b', r'\babs\b']),
    ('associate',    [r'\bassociate\b']),
    ('vocational',   [r'\btesda\b', r'\bvocational', r'\bnc\s*[ii]+\b']),
    ('senior_high',  [r'\bsenior high', r'\bshs\b', r'\b(?:abm|stem|humss|gas|tvl|sports|arts)\s+strand']),
    ('junior_high',  [r'\bjunior high', r'\bjhs\b', r'\bhigh school']),
    ('elementary',   [r'\belementary']),
]

# Leading bullet glyphs or numbering tokens on a line. Matches up to one
# bullet/number prefix + surrounding whitespace so we can strip it cleanly.
# Bullets covered:  • ● ‣ ▪ ◦ · *  plus -  – —  used as list markers.
# Numbering covered:  1.  1)  (1)  a.  i.  with the trailing space.
_BULLET_RE = re.compile(
    r'^\s*(?:'
        r'[•●‣▪◦·∙⁃*]'   # glyph bullets
        r'|[-–—]'                                                 # dash bullets
        r'|\(?\d{1,2}\)'                                          # 1)  (1)
        r'|\d{1,2}\.'                                             # 1.
        r'|\(?[a-z]\)'                                            # a)  (a)
        r'|[a-z]\.'                                               # a.
        r'|[ivxlcdm]+\.'                                          # roman numerals
    r')\s+',
    re.IGNORECASE,
)


def _strip_bullet(line: str) -> str:
    """Drop a leading bullet/number marker from a line. Idempotent."""
    return _BULLET_RE.sub('', line, count=1).strip()


# Lines starting with an action verb almost always belong in the
# description, not in the Position/Company columns. Common resume verbs.
_DESC_VERB_RE = re.compile(
    r'^\s*(?:'
    r'oversaw|led|managed|developed|designed|built|created|implemented|maintained|'
    r'collaborated|coordinated|conducted|performed|supervised|provided|delivered|'
    r'achieved|increased|reduced|improved|established|trained|mentored|analyzed|'
    r'researched|wrote|presented|negotiated|directed|organized|planned|prepared|'
    r'reviewed|assisted|handled|processed|tracked|monitored|optimized|drove|'
    r'spearheaded|launched|owned|shipped|grew|scaled|streamlined|automated|'
    r'reported|served|worked|responsible|ensure[ds]?|support(?:ed)?'
    r')\b',
    re.IGNORECASE,
)


def _looks_like_description(line: str) -> bool:
    """Heuristic: does this line read like a bullet/description rather than
    a Title-Cased job header? Used to avoid putting 'Oversaw daily activities.'
    into the Position field."""
    s = (line or '').strip()
    if not s:
        return False
    if _DESC_VERB_RE.match(s):
        return True
    # Sentence-shaped: ends with a period and is moderately long.
    if s.endswith('.') and len(s.split()) > 5:
        return True
    return False


# Strong "company-ness" signals — corporate suffixes, school/agency words.
_COMPANY_HINT_RE = re.compile(
    r'\b(?:inc\.?|llc|ltd\.?|corp\.?|co\.|company|university|college|school|'
    r'center|centre|hospital|clinic|institute|agency|bureau|department|dept\.?|'
    r'foundation|solutions|systems|services|group|holdings|technologies|labs?)\b',
    re.IGNORECASE,
)


def _split_position_company(line: str) -> tuple[str, str]:
    """Split a single line into (position, company) using common separators.

    Resume formats we handle:
      'Software Engineer | Google'          ->  ('Software Engineer', 'Google')
      'Software Engineer at Google'         ->  ('Software Engineer', 'Google')
      'Software Engineer - Google'          ->  ('Software Engineer', 'Google')
      'Client Specialist, Rainbow Care, AR' ->  ('Client Specialist', 'Rainbow Care, AR')

    Returns the line as position with empty company if no separator looks
    convincing — never invents company text.
    """
    s = line.strip()
    if not s:
        return '', ''
    for sep in (' | ', ' — ', ' – ', ' · ', ' at ', ' @ '):
        if sep in s:
            left, _, right = s.partition(sep)
            return left.strip(), right.strip()
    # ' - ' is risky (often a date dash), so only split if the right side
    # also looks like a company name.
    if ' - ' in s:
        left, _, right = s.partition(' - ')
        if _COMPANY_HINT_RE.search(right) or _COMPANY_HINT_RE.search(left):
            return left.strip(), right.strip()
    # Comma-separated "Title, Company, Location" — split on first comma.
    if ',' in s:
        head, _, rest = s.partition(',')
        if rest.strip():
            return head.strip(), rest.strip()
    return s, ''


SECTION_HEADERS = {
    'experience':  re.compile(r'\b(work\s+)?experience\b|\bemployment(\s+history)?\b|\bprofessional\s+experience\b', re.I),
    'education':   re.compile(r'\beducation(al)?\s*(background)?\b|\bacademic\s+history\b', re.I),
    'skills':      re.compile(r'\b(technical\s+)?skills\b|\bcompetencies\b|\bproficiencies\b', re.I),
    'certifications': re.compile(r'\bcertifications?\b|\blicen[cs]es?\b|\bawards\b', re.I),
    'summary':     re.compile(r'\b(profile|summary|objective|about(\s+me)?|bio)\b', re.I),
}


# ── File-type detection ───────────────────────────────────────────────
def _detect_kind(file_bytes: bytes) -> str:
    """Sniff the upload's actual type from its first bytes. Returns
    'pdf', 'image', or 'unknown'. Don't trust the filename — users
    rename things and content-type sniffing is the safe option."""
    if not file_bytes:
        return 'unknown'
    head = file_bytes[:16]
    if head.startswith(b'%PDF'):
        return 'pdf'
    # JPEG / PNG / GIF
    if head.startswith(b'\xff\xd8\xff'):
        return 'image'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image'
    # HEIC / HEIF (ISO BMFF — `ftyp` box with HEIC brand at offset 4)
    if len(head) >= 12 and head[4:8] == b'ftyp':
        brand = head[8:12].lower()
        if brand in (b'heic', b'heix', b'hevc', b'hevx', b'mif1', b'msf1', b'heim', b'heis'):
            return 'image'
    return 'unknown'


# ── OCR helpers ───────────────────────────────────────────────────────
def _tesseract_ok() -> bool:
    """True only if pytesseract and the Tesseract binary are both usable."""
    try:
        import pytesseract  # type: ignore
        pytesseract.get_tesseract_version()  # raises if binary not on PATH
        return True
    except Exception:
        return False


def _ocr_pdf(file_bytes: bytes) -> Optional[str]:
    """Render PDF pages to images and OCR them. Needs pdf2image + Poppler."""
    if not _tesseract_ok():
        return None
    try:
        from pdf2image import convert_from_bytes  # type: ignore
        import pytesseract  # type: ignore
    except Exception:
        return None
    try:
        images = convert_from_bytes(file_bytes, dpi=200, first_page=1, last_page=3)
        return '\n\n'.join(pytesseract.image_to_string(img) for img in images)
    except Exception:
        return None


def _ocr_image(file_bytes: bytes) -> Optional[str]:
    """Decode an image (JPG/PNG/HEIC) and OCR it. Returns None if OCR is
    unavailable on this host."""
    if not _tesseract_ok():
        return None
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
        # HEIC needs the optional pillow-heif registration step.
        try:
            from pillow_heif import register_heif_opener  # type: ignore
            register_heif_opener()
        except Exception:
            pass
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode not in ('L', 'RGB'):
            img = img.convert('RGB')
        return pytesseract.image_to_string(img)
    except Exception:
        return None


def _extract_text(file_bytes: bytes, kind: str) -> tuple[str, Optional[str]]:
    """Return (text, error). Empty text + populated error means we
    couldn't get anything useful; the caller should surface the error."""
    if kind == 'pdf':
        text = ''
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                chunks = []
                for page in pdf.pages:
                    chunks.append(page.extract_text() or '')
                text = '\n'.join(chunks).strip()
        except Exception:
            text = ''

        # Looks image-based (scanned PDF). Try OCR if available.
        if len(text) < 80:
            ocr_text = _ocr_pdf(file_bytes)
            if ocr_text and len(ocr_text) > len(text):
                return ocr_text, None
            if not text:
                return '', (
                    "This PDF looks like a scanned image, and OCR isn't "
                    "available on this server. Try uploading a text-based "
                    "PDF, or paste your details into the form manually."
                )
        return text, None

    if kind == 'image':
        ocr_text = _ocr_image(file_bytes)
        if not ocr_text or len(ocr_text.strip()) < 40:
            return '', (
                "Couldn't read enough text from this photo. Try a "
                "sharper, well-lit image — or upload a PDF instead."
            )
        return ocr_text, None

    return '', "Unsupported file type. Upload a PDF or a photo (JPG / PNG / HEIC)."


# ── Section / field extraction ────────────────────────────────────────
def _split_sections(text: str) -> dict[str, str]:
    """Partition the raw text into named sections by looking for header lines."""
    sections: dict[str, list[str]] = {}
    lines = text.splitlines()
    current_key: str = '_top'
    sections[current_key] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            sections[current_key].append('')
            continue
        matched: Optional[str] = None
        if len(stripped) <= 60:
            for key, pat in SECTION_HEADERS.items():
                if pat.search(stripped):
                    matched = key
                    break
        if matched:
            current_key = matched
            sections.setdefault(current_key, [])
        else:
            sections[current_key].append(line)

    return {k: '\n'.join(v).strip() for k, v in sections.items()}


def _find_skills(text: str, known: list[str]) -> list[str]:
    """Pick up any known skill name appearing in the text (whole-word, case-insensitive)."""
    if not known:
        return []
    found = []
    lower = text.lower()
    for skill in known:
        s = skill.strip()
        if not s:
            continue
        pat = r'(?<![\w])' + re.escape(s.lower()) + r'(?![\w])'
        if re.search(pat, lower):
            found.append(s)
    return found[:25]


def _find_education_level(line: str) -> Optional[str]:
    lower = line.lower()
    for level, patterns in DEGREE_KEYWORDS:
        for pat in patterns:
            if re.search(pat, lower):
                return level
    return None


def _extract_education(section_text: str) -> list[dict]:
    entries = []
    seen_levels = set()
    for line in section_text.splitlines():
        line = _strip_bullet(line)
        if len(line) < 4:
            continue
        level = _find_education_level(line)
        if not level:
            continue
        years = re.findall(r'\b(?:19|20)\d{2}\b', line)
        year_started = int(years[0]) if years else None
        year_ended   = int(years[-1]) if len(years) > 1 else None
        # Strip year tokens for the rest of the line.
        rest = re.sub(r'\b(?:19|20)\d{2}\b', '', line).strip(' -–|,')
        if level in seen_levels:
            continue
        seen_levels.add(level)
        entries.append({
            'level': level,
            'course': rest[:200],
            'institution': '',
            'year_started': year_started,
            'year_ended': year_ended,
        })
    return entries[:5]


def _extract_experiences(section_text: str) -> list[dict]:
    entries = []
    lines = [_strip_bullet(l) for l in section_text.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        m = YEAR_RANGE_RE.search(lines[i])
        if not m:
            i += 1
            continue

        year_start = int(m.group(2))
        end_raw = m.group(3)
        is_current = end_raw.lower() in ('present', 'current')
        year_end = None if is_current else int(end_raw)

        # ── Pick a header line (Position + Company candidate) ─────
        # Prefer:
        #   1. Same-line residue (date appears in the header line itself)
        #   2. The line(s) ABOVE the date that don't look like description bullets
        #   3. As a last resort, line BELOW the date (for "date-first" formats)
        # We skip description-y candidates but keep them so they end up in desc.
        header_candidates = []
        same_line_residue = YEAR_RANGE_RE.sub('', lines[i]).strip(' -|,·')
        if same_line_residue:
            header_candidates.append(same_line_residue)
        for offset in (1, 2):
            if i - offset >= 0:
                header_candidates.append(lines[i - offset])

        header = ''
        misplaced_desc = []
        for cand in header_candidates:
            cand = (cand or '').strip()
            if not cand:
                continue
            if _looks_like_description(cand):
                misplaced_desc.append(cand)
                continue
            header = cand
            break

        # Fall back: look BELOW the date for "date-first" resumes. We
        # only do this if nothing above worked AND the next line doesn't
        # look like a bullet.
        consumed_below = 0
        if not header and i + 1 < len(lines):
            below = lines[i + 1].strip()
            if below and not _looks_like_description(below) and not YEAR_RANGE_RE.search(below):
                header = below
                consumed_below = 1

        position, company = _split_position_company(header) if header else ('', '')

        # ── Description: lines AFTER the date until the next date range ─
        desc_lines = list(misplaced_desc)
        j = i + 1 + consumed_below
        while j < len(lines) and j < i + 10 and not YEAR_RANGE_RE.search(lines[j]):
            # Stop early if the NEXT line is a date range — then THIS line is
            # the next entry's header, not part of our description.
            if j + 1 < len(lines) and YEAR_RANGE_RE.search(lines[j + 1]) \
               and not _looks_like_description(lines[j]):
                break

            cleaned = _strip_bullet(lines[j])
            # The line just AFTER the date might be a Company on its own
            # (e.g. "Title \n Date \n Company \n bullets"). If we have a
            # position but no company yet, treat it as company iff short and
            # not description-y.
            if j == i + 1 + consumed_below and position and not company and cleaned \
               and not _looks_like_description(cleaned) and len(cleaned) <= 80:
                company = cleaned
            elif cleaned:
                desc_lines.append(cleaned)
            j += 1

        entries.append({
            'position':     position[:200],
            'company':      company[:200],
            'year_started': year_start,
            'year_ended':   year_end,
            'is_current':   is_current,
            # Newline-joined so multi-bullet descriptions render as a list
            # under whitespace-pre-line in the textarea.
            'description':  '\n'.join(desc_lines)[:600],
        })
        i = j
    return entries[:6]


# ── Public entry point ────────────────────────────────────────────────
def parse_resume(file_bytes: bytes, known_skills: Optional[list[str]] = None) -> dict:
    """Parse a resume upload and return form-ready fields.

    Returns ``{'ok': False, 'error': '...'}`` on any handled failure, or
    ``{'ok': True, ...fields...}`` on success.
    """
    kind = _detect_kind(file_bytes)
    text, error = _extract_text(file_bytes, kind)
    if error:
        return {'ok': False, 'error': error}
    if not text:
        return {'ok': False, 'error': "Couldn't read any text from this file. Try a different upload or fill in fields manually."}

    sections = _split_sections(text)

    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)

    summary = sections.get('summary') or sections.get('_top', '')
    summary = re.sub(r'\s+', ' ', summary).strip()[:280]

    skills = _find_skills(sections.get('skills', '') or text, known_skills or [])
    education = _extract_education(sections.get('education', ''))
    experiences = _extract_experiences(sections.get('experience', ''))

    return {
        'ok': True,
        'kind': kind,                         # surfaces in JSON so the client can confirm
        'email': email_match.group(0) if email_match else '',
        'phone': re.sub(r'[\s\-]', '', phone_match.group(0)) if phone_match else '',
        'bio': summary,
        'skills': skills,
        'education': education,
        'experiences': experiences,
        'raw_chars': len(text),
    }
