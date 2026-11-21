"""ICAO 9303 TD1 (ID card 3x30) and TD3 (Passport 2x44) MRZ parser with strict check-digit validation (§6.4)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.engines.recognition.types import Field

_NUMERIC_FIX = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "B": "8", "S": "5", "Z": "2"})
_ALPHA_FIX = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"})


def _mrz_char_value(ch: str) -> int:
    if ch == "<":
        return 0
    if "0" <= ch <= "9":
        return ord(ch) - ord("0")
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    return 0


def mrz_check_digit(field: str) -> str:
    """ICAO 9303 Mod-10 check digit with repeating weights 7, 3, 1."""
    weights = (7, 3, 1)
    total = sum(_mrz_char_value(ch) * weights[i % 3] for i, ch in enumerate(field.upper()))
    return str(total % 10)


def _clean_mrz_line(raw: str) -> str:
    s = raw.upper().strip()
    s = s.replace("«", "<").replace("‹", "<").replace(" ", "")
    # Replace OCR 'K' runs surrounded by '<' inside filler zones
    s = re.sub(r"(?<=<)K+(?=<|$)", lambda m: "<" * len(m.group(0)), s)
    s = re.sub(r"[^A-Z0-9<]", "<", s)
    return s


def _fix_numeric_field(s: str) -> str:
    return "".join(ch if ch == "<" else ch.translate(_NUMERIC_FIX) for ch in s)


def _fix_alpha_field(s: str) -> str:
    return "".join(ch if ch == "<" else ch.translate(_ALPHA_FIX) for ch in s)


def _parse_mrz_date(yymmdd: str, *, is_expiry: bool = False, today: date | None = None) -> date | None:
    clean = _fix_numeric_field(yymmdd)
    if not re.fullmatch(r"\d{6}", clean):
        return None
    yy, mm, dd = int(clean[:2]), int(clean[2:4]), int(clean[4:6])
    ref_yy = (today or date.today()).year % 100
    year = (2000 + yy) if is_expiry else ((1900 + yy) if yy > ref_yy else (2000 + yy))
    try:
        return date(year, mm, dd)
    except ValueError:
        return None


def _parse_names(name_block: str) -> tuple[str, str]:
    alpha = _fix_alpha_field(name_block)
    parts = alpha.split("<<", 1)
    surname = re.sub(r"\s+", " ", parts[0].replace("<", " ")).strip()
    given = re.sub(r"\s+", " ", parts[1].replace("<", " ")).strip() if len(parts) > 1 else ""
    return surname, given


def parse_mrz(raw_text: str, *, today: date | None = None) -> dict[str, Any]:
    """Auto-detect and parse ICAO 9303 TD3 (2x44) or TD1 (3x30) MRZ with full check-digit validation."""
    cleaned_lines = [_clean_mrz_line(ln) for ln in raw_text.splitlines() if "<" in ln and len(ln.strip()) >= 26]

    td3_lines = [ln for ln in cleaned_lines if 42 <= len(ln) <= 46]
    td1_lines = [ln for ln in cleaned_lines if 28 <= len(ln) <= 32]

    if len(td3_lines) >= 2:
        return parse_mrz_td3("\n".join(td3_lines[-2:]), today=today)
    if len(td1_lines) >= 3:
        return parse_mrz_td1("\n".join(td1_lines[-3:]), today=today)

    return {
        "valid": False,
        "format": None,
        "error": "mrz_not_found",
        "warnings": ["rec.warn.mrz_not_found"],
        "checks": {},
        "fields": {},
        "confidences": {},
        "typed_fields": [],
    }


def _finalize_mrz(
    *,
    fmt: str,
    doc_type: str,
    issuing_state: str,
    surname: str,
    given_names: str,
    doc_number: str,
    nationality: str,
    dob: date | None,
    sex: str,
    expiry: date | None,
    checks: dict[str, bool],
) -> dict[str, Any]:
    failures = [k for k, ok in checks.items() if not ok]
    # Spec §6.4: >= 2 check digit failures -> reject and ask for retake
    if len(failures) >= 2:
        return {
            "valid": False,
            "format": fmt,
            "error": "mrz_checksum_failed",
            "warnings": ["rec.warn.mrz_checksum"],
            "checks": checks,
            "fields": {},
            "confidences": {},
            "typed_fields": [],
        }

    warnings = ["rec.warn.mrz_checksum"] if len(failures) == 1 else []
    full_name = f"{surname} {given_names}".strip()

    def _conf(check_key: str | None) -> tuple[float, bool]:
        if check_key and not checks.get(check_key, True):
            return 0.65, True
        return 0.99, False

    c_doc, nc_doc = _conf("docNumber")
    c_dob, nc_dob = _conf("dob")
    c_exp, nc_exp = _conf("expiry")
    c_comp = 0.72 if not checks.get("composite", True) else 0.99

    typed_fields = [
        Field(key="documentType", value=doc_type, display=doc_type, confidence=0.99, source="rule"),
        Field(key="issuingState", value=issuing_state, display=issuing_state, confidence=0.99, source="rule"),
        Field(key="surname", value=surname, display=surname, confidence=min(0.99, c_comp), source="rule", needs_confirm=c_comp < 0.75),
        Field(key="givenNames", value=given_names, display=given_names, confidence=min(0.99, c_comp), source="rule", needs_confirm=c_comp < 0.75),
        Field(key="fullName", value=full_name, display=full_name, confidence=min(0.99, c_comp), source="rule", needs_confirm=c_comp < 0.75),
        Field(key="documentNumber", value=doc_number, display=doc_number, confidence=c_doc, source="rule", needs_confirm=nc_doc),
        Field(key="nationality", value=nationality, display=nationality, confidence=0.99, source="rule"),
        Field(key="dob", value=dob, display=dob.isoformat() if dob else "", confidence=c_dob, source="rule", needs_confirm=nc_dob or dob is None),
        Field(key="sex", value=sex, display=sex, confidence=0.99, source="rule"),
        Field(key="expiry", value=expiry, display=expiry.isoformat() if expiry else "", confidence=c_exp, source="rule", needs_confirm=nc_exp or expiry is None),
    ]

    flat_fields = {
        "documentType": doc_type,
        "issuingState": issuing_state,
        "surname": surname,
        "givenNames": given_names,
        "fullName": full_name,
        "documentNumber": doc_number,
        "nationality": nationality,
        "dob": dob.isoformat() if dob else None,
        "sex": sex,
        "expiry": expiry.isoformat() if expiry else None,
    }
    confs = {f.key: f.confidence for f in typed_fields}

    return {
        "valid": len(failures) == 0,
        "partial_warn": len(failures) == 1,
        "format": fmt,
        "error": "mrz_checksum_failed" if failures else None,
        "warnings": warnings,
        "checks": checks,
        "fields": flat_fields,
        "confidences": confs,
        "typed_fields": typed_fields,
    }


def parse_mrz_td3(raw_text: str, *, today: date | None = None) -> dict[str, Any]:
    """Parse ICAO 9303 TD3 (2 lines x 44 chars) passport MRZ."""
    candidates = [_clean_mrz_line(ln) for ln in raw_text.splitlines() if len(_clean_mrz_line(ln)) >= 40 and "<" in ln]
    if len(candidates) < 2:
        return {"valid": False, "format": "TD3", "error": "mrz_not_found", "warnings": ["rec.warn.mrz_not_found"], "checks": {}, "fields": {}, "confidences": {}, "typed_fields": []}

    line1 = candidates[-2][:44].ljust(44, "<")
    line2 = candidates[-1][:44].ljust(44, "<")

    doc_type = line1[0:2].replace("<", "")
    issuing_state = _fix_alpha_field(line1[2:5]).replace("<", "")
    surname, given_names = _parse_names(line1[5:44])

    doc_num_raw = line2[0:9]
    doc_num_cd = _fix_numeric_field(line2[9])
    nationality = _fix_alpha_field(line2[10:13]).replace("<", "")
    dob_raw = _fix_numeric_field(line2[13:19])
    dob_cd = _fix_numeric_field(line2[19])
    sex = line2[20] if line2[20] in ("M", "F") else "X"
    exp_raw = _fix_numeric_field(line2[21:27])
    exp_cd = _fix_numeric_field(line2[27])
    opt_raw = line2[28:42]
    opt_cd = _fix_numeric_field(line2[42])
    comp_cd = _fix_numeric_field(line2[43])

    composite_str = doc_num_raw + doc_num_cd + dob_raw + dob_cd + exp_raw + exp_cd + opt_raw + opt_cd
    checks = {
        "docNumber": mrz_check_digit(doc_num_raw) == doc_num_cd,
        "dob": mrz_check_digit(dob_raw) == dob_cd,
        "expiry": mrz_check_digit(exp_raw) == exp_cd,
        "optional": (opt_cd == "<" and opt_raw == "<" * 14) or (mrz_check_digit(opt_raw) == opt_cd),
        "composite": mrz_check_digit(composite_str) == comp_cd,
    }

    return _finalize_mrz(
        fmt="TD3",
        doc_type=doc_type,
        issuing_state=issuing_state,
        surname=surname,
        given_names=given_names,
        doc_number=doc_num_raw.replace("<", ""),
        nationality=nationality,
        dob=_parse_mrz_date(dob_raw, is_expiry=False, today=today),
        sex=sex,
        expiry=_parse_mrz_date(exp_raw, is_expiry=True, today=today),
        checks=checks,
    )


def parse_mrz_td1(raw_text: str, *, today: date | None = None) -> dict[str, Any]:
    """Parse ICAO 9303 TD1 (3 lines x 30 chars) ID card MRZ."""
    candidates = [_clean_mrz_line(ln) for ln in raw_text.splitlines() if 26 <= len(_clean_mrz_line(ln)) <= 34 and "<" in ln]
    if len(candidates) < 3:
        return {"valid": False, "format": "TD1", "error": "mrz_not_found", "warnings": ["rec.warn.mrz_not_found"], "checks": {}, "fields": {}, "confidences": {}, "typed_fields": []}

    l1 = candidates[-3][:30].ljust(30, "<")
    l2 = candidates[-2][:30].ljust(30, "<")
    l3 = candidates[-1][:30].ljust(30, "<")

    doc_type = l1[0:2].replace("<", "")
    issuing_state = _fix_alpha_field(l1[2:5]).replace("<", "")
    doc_num_raw = l1[5:14]
    doc_num_cd = _fix_numeric_field(l1[14])
    opt1 = l1[15:30]

    dob_raw = _fix_numeric_field(l2[0:6])
    dob_cd = _fix_numeric_field(l2[6])
    sex = l2[7] if l2[7] in ("M", "F") else "X"
    exp_raw = _fix_numeric_field(l2[8:14])
    exp_cd = _fix_numeric_field(l2[14])
    nationality = _fix_alpha_field(l2[15:18]).replace("<", "")
    opt2 = l2[18:29]
    comp_cd = _fix_numeric_field(l2[29])

    surname, given_names = _parse_names(l3)
    composite_str = doc_num_raw + doc_num_cd + opt1 + dob_raw + dob_cd + exp_raw + exp_cd + opt2

    checks = {
        "docNumber": mrz_check_digit(doc_num_raw) == doc_num_cd,
        "dob": mrz_check_digit(dob_raw) == dob_cd,
        "expiry": mrz_check_digit(exp_raw) == exp_cd,
        "composite": mrz_check_digit(composite_str) == comp_cd,
    }

    return _finalize_mrz(
        fmt="TD1",
        doc_type=doc_type,
        issuing_state=issuing_state,
        surname=surname,
        given_names=given_names,
        doc_number=doc_num_raw.replace("<", ""),
        nationality=nationality,
        dob=_parse_mrz_date(dob_raw, is_expiry=False, today=today),
        sex=sex,
        expiry=_parse_mrz_date(exp_raw, is_expiry=True, today=today),
        checks=checks,
    )
