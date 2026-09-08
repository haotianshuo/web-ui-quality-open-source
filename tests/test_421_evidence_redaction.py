from pathlib import Path
import json

from web_ui_quality.evidence_redaction import REDACTED, mask_sensitive_dom_for_screenshot, redact_structure, redact_text
from web_ui_quality.browser_experience import persist_experience_evidence


def test_text_redaction_removes_credentials_jwt_query_secrets_and_pii():
    raw='Bearer supersecrettoken token=abc12345 user=person@example.com phone=+1 415 555 1212 https://x.test/a?access_token=verysecret'
    out=redact_text(raw)
    assert 'supersecrettoken' not in out
    assert 'abc12345' not in out
    assert 'person@example.com' not in out
    assert '415 555 1212' not in out
    assert 'verysecret' not in out
    assert REDACTED in out


def test_structure_redaction_replaces_sensitive_keys_before_persistence(tmp_path):
    dom={'nodes':[{'name':'person@example.com','sessionToken':'SECRET_SESSION','text':'call +44 20 7946 0958'}]}
    geometry={'visual':{'elements':[{'text':'Bearer VERYSECRET12345'}]}}
    refs=persist_experience_evidence(tmp_path,label='mobile',viewport={'width':390,'height':844},dom_snapshot=dom,geometry=geometry)
    persisted=(tmp_path/refs['domRef']).read_text(encoding='utf-8')+(tmp_path/refs['geometryRef']).read_text(encoding='utf-8')
    assert 'SECRET_SESSION' not in persisted
    assert 'person@example.com' not in persisted
    assert 'VERYSECRET12345' not in persisted
    assert '[REDACTED]' in persisted


def test_screenshot_mask_is_best_effort_and_never_requires_ocr():
    class Page:
        def evaluate(self, script):
            assert 'data-wuq-sensitive' in script
            return 4
    assert mask_sensitive_dom_for_screenshot(Page()) == 4
