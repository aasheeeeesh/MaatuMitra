"""JWT tests (no database). Unsigned, tampered, alg-none, expired, wrong-aud/iss tokens never authenticate."""

import base64
import json
import time
import uuid

import jwt
import pytest

from m5_backend.app.auth import AuthError, issue_token, verify_token
from m5_backend.app.directory import load_directory


def _b64(obj) -> str:
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def directory():
    return load_directory()


@pytest.fixture(scope="module")
def nurse(directory):
    return directory.by_key("N1")


def test_valid_token_roundtrip(settings_nodb, directory, nurse):
    tok = issue_token(settings_nodb, nurse)
    p = verify_token(settings_nodb, tok, directory)
    assert p.user_id == nurse.id
    assert p.role == "nurse"
    assert p.facility_id == nurse.facility_id


def test_header_alg_is_hs256_and_short_expiry(settings_nodb, nurse):
    tok = issue_token(settings_nodb, nurse)
    assert jwt.get_unverified_header(tok)["alg"] == "HS256"
    claims = jwt.decode(tok, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] <= 900
    for c in ("sub", "role", "fid", "iss", "aud", "exp", "iat", "jti"):
        assert c in claims


def test_alg_none_rejected(settings_nodb, directory, nurse):
    claims = jwt.decode(issue_token(settings_nodb, nurse), options={"verify_signature": False})
    for alg in ("none", "None", "NONE"):
        tok = f"{_b64({'alg': alg, 'typ': 'JWT'})}.{_b64(claims)}."
        with pytest.raises(AuthError):
            verify_token(settings_nodb, tok, directory)


def test_tampered_payload_rejected(settings_nodb, directory, nurse):
    tok = issue_token(settings_nodb, nurse)
    h, _p, s = tok.split(".")
    claims = jwt.decode(tok, options={"verify_signature": False})
    claims["role"] = "physician"
    with pytest.raises(AuthError):
        verify_token(settings_nodb, f"{h}.{_b64(claims)}.{s}", directory)


def test_flipped_signature_rejected(settings_nodb, directory, nurse):
    tok = issue_token(settings_nodb, nurse)
    h, p, s = tok.split(".")
    s2 = ("A" if s[0] != "A" else "B") + s[1:]
    with pytest.raises(AuthError):
        verify_token(settings_nodb, f"{h}.{p}.{s2}", directory)


def test_wrong_key_rejected(settings_nodb, directory, nurse):
    other = settings_nodb.replace(jwt_signing_key="0" * 64)
    tok = issue_token(other, nurse)
    with pytest.raises(AuthError):
        verify_token(settings_nodb, tok, directory)


def test_expired_rejected(settings_nodb, directory, nurse):
    tok = issue_token(settings_nodb, nurse, now=time.time() - 3600)
    with pytest.raises(AuthError):
        verify_token(settings_nodb, tok, directory)


def test_wrong_audience_and_issuer_rejected(settings_nodb, directory, nurse):
    for change in ({"jwt_audience": "someone-else"}, {"jwt_issuer": "evil-issuer"}):
        tok = issue_token(settings_nodb.replace(**change), nurse)
        with pytest.raises(AuthError):
            verify_token(settings_nodb, tok, directory)


def test_hs256_vs_rs256_confusion_rejected(settings_nodb, directory, nurse):
    claims = jwt.decode(issue_token(settings_nodb, nurse), options={"verify_signature": False})
    tok = jwt.encode(claims, settings_nodb.jwt_signing_key, algorithm="HS512")
    with pytest.raises(AuthError):
        verify_token(settings_nodb, tok, directory)


@pytest.mark.parametrize("missing", ["sub", "role", "fid", "exp", "iss", "aud"])
def test_missing_required_claim_rejected(settings_nodb, directory, nurse, missing):
    claims = jwt.decode(issue_token(settings_nodb, nurse), options={"verify_signature": False})
    claims.pop(missing)
    tok = jwt.encode(claims, settings_nodb.jwt_signing_key, algorithm="HS256")
    with pytest.raises(AuthError):
        verify_token(settings_nodb, tok, directory)


def test_role_not_matching_directory_rejected(settings_nodb, directory, nurse):
    # Even a correctly SIGNED token whose role disagrees with the directory is refused.
    claims = jwt.decode(issue_token(settings_nodb, nurse), options={"verify_signature": False})
    claims["role"] = "physician"
    tok = jwt.encode(claims, settings_nodb.jwt_signing_key, algorithm="HS256")
    with pytest.raises(AuthError):
        verify_token(settings_nodb, tok, directory)


def test_unknown_sub_and_bad_role_rejected(settings_nodb, directory, nurse):
    for change in ({"sub": str(uuid.uuid4())}, {"role": "admin"}, {"sub": "1"}):
        claims = jwt.decode(issue_token(settings_nodb, nurse), options={"verify_signature": False})
        claims.update(change)
        tok = jwt.encode(claims, settings_nodb.jwt_signing_key, algorithm="HS256")
        with pytest.raises(AuthError):
            verify_token(settings_nodb, tok, directory)


@pytest.mark.parametrize("junk", ["", "abc", "a.b.c", "x" * 5000, "Bearer abc", "' OR 1=1 --"])
def test_garbage_rejected(settings_nodb, directory, junk):
    with pytest.raises(AuthError):
        verify_token(settings_nodb, junk, directory)


def test_signing_key_must_be_strong(settings_nodb, nurse):
    with pytest.raises(ValueError):
        issue_token(settings_nodb.replace(jwt_signing_key="short"), nurse)
