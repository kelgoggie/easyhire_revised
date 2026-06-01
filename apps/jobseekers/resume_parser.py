"""Lightweight resume PDF parser.

Strategy:
  1. Use pdfplumber to extract text from the PDF.
  2. If pdfplumber returns very little text (likely an image-based PDF),
     fall back to OCR via pytesseract + pdf2image, but only if both are
     importable AND the system Tesseract binary is callable. Otherwise we
     simply return whatever pdfplumber gave us.
  3. Pull out structured fields with regex + keyword heuristics.
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
    ('associate',    [r'\bassociate'r'\b']),
    ('vocational',   [r'\btesda\b', r'\bvocational', r'\bnc\s*[ii]+\b']),
    ('senior_high',  [r'\bsenior high', r'\bshs\b', r'\b(?:abm|stem|humss|gas|tvl|sports|arts)\s+strand']),
    ('junior_high',  [r'\bjunior high', r'\bjhs\b', r'\bhigh school']),
    ('elementary',   [r'\belementary']),
]

SECTION_HEADERS = {
    'experience':  re.compile(r'\b(work\s+)?experience\b|\bemployment(\s+history)?\b|\bprofessional\s+experience\b', re.I),
    'education':   re.compile(r'\beducation(al)?\s*(background)?\b|\bacademic\s+history\b', re.I),
    'skills':      re.compile(r'\b(technical\s+)?skills\b|\bcompetencies\b|\bproficiencies\b', re.I),
    'certifications': re.compile(r'\bcertifications?\b|\blicen[cs]es?\b|\bawards\b', re.I),
    'summary':     re.compile(r'\b(profile|summary|objective|about(\s+me)?|bio)\b', re.I),
}


def _try_ocr(file_bytes: bytes) -> Optional[str]:
    """Run OCR only if pdf2image, pytesseract, AND a Tesseract binary are
    actually available. Returns None on any failure."""
    try:
        from pdf2image import convert_from_bytes  # type: ignore
        import pytesseract  # type: ignore
        pytesseract.get_tesseract_version()  # raises if binary not on PATH
    except Exception:
        return None
    try:
        images = convert_from_bytes(file_bytes, dpi=200, first_page=1, last_page=3)
        return '\n\n'.join(pytesseract.image_to_string(img) for img in images)
    except Exception:
        return None


def _extract_text(file_bytes: bytes) -> str:
    """Pull text out of the PDF. Returns '' if nothing usable was found."""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            chunks = []
            for page in pdf.pages:
                text = page.extract_text() or ''
                chunks.append(text)
            text = '\n'.join(chunks).strip()
    except Exception:
        text = ''

    # If very little text was extracted, attempt OCR
    if len(text) < 80:
        ocr_text = _try_ocr(file_bytes)
        if ocr_text and len(ocr_text) > len(text):
            text = ocr_text
    return text


def _split_sections(text: str) -> dict[str, str]:
    """Partition the raw text into named sections by looking for header lines."""
    sections: dict[str, str] = {}
    lines = text.splitlines()
    current_key: Optional[str] = '_top'
    sections[current_key] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            sections[current_key].append('')
            continue
        # Header detection: short line, mostly bare keyword
        matched = None
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
        # whole-word match; allow + and # for things like "C++" / "C#"
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
    """Best-effort education entries. One entry per line that mentions a degree."""
    entries = []
    seen_levels = set()
    for line in section_text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        level = _find_education_level(line)
        if not level:
            continue
        years = re.findall(r'\b(19|20)\d{2}\b', line)
        year_started = int(years[0] + years[0]) if False else (int(line[line.find(years[0]):line.find(years[0])+4]) if years else None)
        year_ended = (int(line[line.rfind(years[-1]):line.rfind(years[-1])+4]) if len(years) > 1 else None)
        # course/institution: strip year tokens
        rest = re.sub(r'\b(19|20)\d{2}\b', '', line).strip(' -–|,')
        entry = {
            'level': level,
            'course': rest[:200],
            'institution': '',
            'year_started': year_started,
            'year_ended': year_ended,
        }
        # Dedup by level
        if level in seen_levels:
            continue
        seen_levels.add(level)
        entries.append(entry)
    return entries[:5]


def _extract_experiences(section_text: str) -> list[dict]:
    """Best-effort experience entries. We treat each year-range hit as a potential job."""
    entries = []
    lines = [l.strip() for l in section_text.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        m = YEAR_RANGE_RE.search(lines[i])
        if m:
            year_start = int(m.group(2))
            end_raw = m.group(3)
            is_current = end_raw.lower() in ('present', 'current')
            year_end = None if is_current else int(end_raw)

            # Heuristic: the position is the line above; company is on the same or next
            position = lines[i - 1] if i > 0 else lines[i]
            company = lines[i + 1] if i + 1 < len(lines) else ''
            # Strip the date range from these lines if they contain it
            position = YEAR_RANGE_RE.sub('', position).strip(' -|,')
            company = YEAR_RANGE_RE.sub('', company).strip(' -|,')

            # Take the next 1–4 lines as description until the next date range
            desc_lines = []
            j = i + 2
            while j < len(lines) and j < i + 8 and not YEAR_RANGE_RE.search(lines[j]):
                desc_lines.append(lines[j])
                j += 1

            entries.append({
                'position': position[:200],
                'company': company[:200],
                'year_started': year_start,
                'year_ended': year_end,
                'is_current': is_current,
                'description': ' '.join(desc_lines)[:600],
            })
            i = j
        else:
            i += 1
    return entries[:6]


def parse_resume(file_bytes: bytes, known_skills: Optional[list[str]] = None) -> dict:
    """Parse a resume PDF and return a dict of fields the resume form expects."""
    text = _extract_text(file_bytes)
    if not text:
        return {
            'ok': False,
            'error': "Couldn't read any text from this PDF. Try a different file or fill in fields manually.",
        }

    sections = _split_sections(text)

    # Email + phone — scan the whole document, not just header sections
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)

    # Bio: prefer an explicit summary section; otherwise first 240 chars of top
    summary = sections.get('summary') or sections.get('_top', '')
    summary = re.sub(r'\s+', ' ', summary).strip()[:280]

    skills = _find_skills(sections.get('skills', '') or text, known_skills or [])
    education = _extract_education(sections.get('education', ''))
    experiences = _extract_experiences(sections.get('experience', ''))

    return {
        'ok': True,
        'email': email_match.group(0) if email_match else '',
        'phone': re.sub(r'[\s\-]', '', phone_match.group(0)) if phone_match else '',
        'bio': summary,
        'skills': skills,
        'education': education,
        'experiences': experiences,
        'raw_chars': len(text),
    }
