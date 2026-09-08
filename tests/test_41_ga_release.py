from __future__ import annotations
import json
from pathlib import Path
from web_ui_quality.phase1_shadow import adaptive_runtime_status
from web_ui_quality.release_info import PACKAGE_STAGE,PACKAGE_VERSION,KERNEL_VERSION,KERNEL_BASE_VERSION
ROOT=Path(__file__).resolve().parents[1]

def test_420_identity_is_explicit_and_separate_from_kernel_lineage():
    assert PACKAGE_VERSION=='4.3.0'
    assert KERNEL_VERSION=='4.2.3'
    assert PACKAGE_STAGE == '4.3.0-stable'
    assert KERNEL_BASE_VERSION=='4.0.0-rc.1'
    plugin=json.loads((ROOT/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    assert plugin['version']==PACKAGE_VERSION

def test_420_does_not_activate_research_adaptive_paths():
    status=adaptive_runtime_status()
    assert status['authoritative'] is False
    assert status['mayChangeWriteAuthority'] is False
    assert status['maySetClaimStatus'] is False
    assert status['mayChangeGuidance'] is False
    assert status['mayChangeExploration'] is False

def test_historical_411_unmeasured_claims_are_not_promoted_to_420():
    assert not (ROOT/'GA-RELEASE-STATUS.json').exists()
    composite=json.loads((ROOT/'COMPOSITE-RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
    assert composite['realCodexHostQualification']=='NOT_MEASURED'
