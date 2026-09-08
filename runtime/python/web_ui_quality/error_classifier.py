"""Root-cause error classification and user-facing recovery advice."""
from __future__ import annotations

import re
from typing import Any, Mapping


_ERROR_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "category": "POLICY_BLOCKED",
        "patterns": (r"ERR_BLOCKED_BY_ADMINISTRATOR", r"blocked by administrator", r"blockedbyclient"),
        "message": "当前运行环境或浏览器策略阻止访问该页面。",
        "actions": ("检查 Codex、沙箱或浏览器网络权限", "允许访问目标地址或本地 loopback 地址", "更换为当前环境可访问的测试地址"),
    },
    {
        "category": "CONNECTION_REFUSED",
        "patterns": (r"ERR_CONNECTION_REFUSED", r"connection refused", r"ECONNREFUSED"),
        "message": "目标服务没有接受连接，项目可能尚未启动或端口不正确。",
        "actions": ("启动项目的本地服务", "确认页面端口和 URL", "检查服务是否只监听了其他网络接口"),
    },
    {
        "category": "DNS_FAILURE",
        "patterns": (r"ERR_NAME_NOT_RESOLVED", r"name or service not known", r"ENOTFOUND", r"dns"),
        "message": "目标域名无法解析。",
        "actions": ("检查域名拼写", "确认 DNS 或网络连接", "改用可解析的测试地址"),
    },
    {
        "category": "TLS_FAILURE",
        "patterns": (r"ERR_CERT", r"certificate", r"SSL", r"TLS"),
        "message": "HTTPS 证书或 TLS 配置阻止了页面访问。",
        "actions": ("检查测试环境证书", "使用有效的 HTTPS 地址", "仅在可信测试环境中显式允许证书错误"),
    },
    {
        "category": "AUTH_REQUIRED",
        "patterns": (r"HTTP\s*401", r"HTTP\s*403", r"unauthori[sz]ed", r"forbidden", r"authentication required", r"login required"),
        "message": "页面需要登录或当前身份没有访问权限。",
        "actions": ("提供测试登录态或测试账号", "确认账号具备目标页面权限", "避免使用生产账号进行自动交互"),
    },
    {
        "category": "NAVIGATION_TIMEOUT",
        "patterns": (r"TimeoutError", r"timed out", r"timeout .* exceeded", r"navigation timeout"),
        "message": "页面在限定时间内没有完成可验证的加载。",
        "actions": ("确认服务稳定并可访问", "检查页面是否卡在长请求或无限加载", "为明确的异步就绪条件增加等待规则"),
    },
    {
        "category": "PAGE_CRASHED",
        "patterns": (r"page crashed", r"renderer process crashed", r"Target closed", r"crash"),
        "message": "浏览器页面或渲染进程崩溃。",
        "actions": ("检查页面运行时错误和内存占用", "减少测试页面中的超大资源", "在干净的浏览器上下文中重试"),
    },
    {
        "category": "BROWSER_PROVIDER_MISSING",
        "patterns": (r"PLAYWRIGHT_UNAVAILABLE", r"playwright.*missing", r"executable doesn't exist", r"browser.*not found"),
        "message": "真实浏览器能力当前不可用。",
        "actions": ("安装或绑定 Playwright Browser Provider", "安装 Chromium 浏览器运行时", "先执行源码级检查并保留真实渲染未验证边界"),
    },
)


def _http_classification(status: int | None) -> dict[str, Any] | None:
    if status == 404:
        return {"category": "HTTP_NOT_FOUND", "message": "目标页面返回 404，当前路径不存在。", "actions": ["检查页面路径和路由", "确认启动的是正确项目", "使用实际可访问的页面 URL"]}
    if status is not None and 500 <= status <= 599:
        return {"category": "HTTP_SERVER_ERROR", "message": f"目标页面返回 HTTP {status} 服务端错误。", "actions": ["检查服务端日志", "确认依赖服务和环境变量", "修复服务错误后重新验证页面"]}
    if status in {401, 403}:
        return {"category": "AUTH_REQUIRED", "message": f"目标页面返回 HTTP {status}，需要登录或权限。", "actions": ["提供测试登录态或测试账号", "确认账号具备页面权限", "不要用修改前端路由来绕过权限"]}
    if status is not None and not 200 <= status < 300:
        return {"category": "HTTP_RESPONSE_ERROR", "message": f"目标页面返回 HTTP {status}，不能作为有效页面验收。", "actions": ["检查目标 URL 和服务响应", "确认重定向与测试环境配置", "恢复有效响应后重新验证"]}
    return None


def classify_runtime_error(*, error: str | None = None, http_status: int | None = None) -> dict[str, Any]:
    raw = str(error or "").strip()
    http = _http_classification(http_status)
    if http:
        return {**http, "rawError": raw or None, "httpStatus": http_status, "sourceCodeChangeSuggested": False}
    for definition in _ERROR_DEFINITIONS:
        if any(re.search(pattern, raw, flags=re.IGNORECASE) for pattern in definition["patterns"]):
            return {
                "category": definition["category"],
                "userMessage": definition["message"],
                "recoveryActions": list(definition["actions"]),
                "rawError": raw or None,
                "httpStatus": http_status,
                "sourceCodeChangeSuggested": False,
            }
    return {
        "category": "UNKNOWN_RUNTIME_FAILURE",
        "userMessage": "页面验证失败，但当前信息不足以可靠判断根因。",
        "recoveryActions": ["查看原始错误和技术日志", "确认项目服务、网络和浏览器能力", "修复运行环境后按相同条件重试"],
        "rawError": raw or None,
        "httpStatus": http_status,
        "sourceCodeChangeSuggested": False,
    }


def classify_record(record: Mapping[str, Any]) -> dict[str, Any] | None:
    if record.get("status") != "FAIL":
        return None
    raw = record.get("errorMessage") or record.get("error") or ""
    status = record.get("httpStatus")
    try:
        http_status = int(status) if status is not None else None
    except (TypeError, ValueError):
        http_status = None
    return classify_runtime_error(error=str(raw), http_status=http_status)


__all__ = ["classify_record", "classify_runtime_error"]
