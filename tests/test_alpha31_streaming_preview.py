from __future__ import annotations

from web_ui_quality.experience_preview import _ai_workspace


def test_ai_workspace_batches_stream_dom_updates_on_animation_frames() -> None:
    _, script = _ai_workspace("记录")

    assert "requestAnimationFrame" in script
    assert "renderPending" in script
    assert "streamTimer=window.setInterval(pushStreamChunk,8)" in script
    assert "textContent=streamOutput.slice(0,streamIndex)" in script
    assert "textContent=output.slice(0,++i)" not in script


def test_ai_workspace_cancellation_clears_timer_and_pending_frame() -> None:
    _, script = _ai_workspace("记录")

    assert "function stopStream()" in script
    assert "clearInterval(streamTimer)" in script
    assert "cancelScheduledStreamFrame()" in script
    assert "用户已中断，可继续或重试" in script
    assert "if(!streaming)return" in script


def test_ai_workspace_keeps_input_available_while_streaming() -> None:
    body, script = _ai_workspace("记录")

    assert 'textarea id="prompt"' in body
    assert "$('prompt').disabled" not in script
    assert "$('prompt').value=''" in script


def test_ai_workspace_empty_prompt_keeps_actionable_feedback() -> None:
    _, script = _ai_workspace("记录")

    assert "if(!text)return;" not in script
    assert "if(!text){toast('请输入任务描述');return}" in script
