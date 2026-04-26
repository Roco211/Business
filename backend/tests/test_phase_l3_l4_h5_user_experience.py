from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP_TSX = ROOT.parent / "apps" / "h5" / "src" / "App.tsx"


def read_app() -> str:
    return APP_TSX.read_text(encoding="utf-8")


def extract_block(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_public_navigation_hides_developer_acceptance_and_technical_terms():
    source = read_app()
    nav_block = extract_block(source, "const navItems", "]\n")

    forbidden_terms = [
        "trial-acceptance",
        "试运行验收",
        "验收",
        "Phase",
        "readiness",
        "preflight",
        "Docker",
        "Redis",
        "PostgreSQL",
        "CORS",
        "/api/v2",
    ]
    for term in forbidden_terms:
        assert term not in nav_block
    assert not re.search(r"K\d", nav_block)


def test_owner_only_diagnostics_entry_exists_outside_public_navigation():
    source = read_app()
    topbar_block = extract_block(source, "function TopBar", "function NotificationCenter")

    assert "系统诊断" in topbar_block
    assert "auth.roleKey === 'owner'" in topbar_block
    assert "onDiagnostics" in topbar_block
    assert "setPage('trial-acceptance')" in source


def test_access_denied_copy_is_product_facing_not_engineering_facing():
    source = read_app()
    access_block = extract_block(source, "function AccessDenied", "function TopBar")

    forbidden_terms = ["RBAC", "前端", "后端", "接口", "403", "permission_denied"]
    for term in forbidden_terms:
        assert term not in access_block
    assert "当前角色无权限" in access_block
