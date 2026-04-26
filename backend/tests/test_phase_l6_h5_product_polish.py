from pathlib import Path


APP_TSX = Path(__file__).resolve().parents[2] / "apps" / "h5" / "src" / "App.tsx"


def _source() -> str:
    return APP_TSX.read_text(encoding="utf-8")


def _block(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_public_login_and_navigation_use_product_copy_not_engineering_copy():
    source = _source()
    login = _block(source, "function LoginScreen", "function AccessDenied")
    nav = _block(source, "const navItems", "]\n")

    forbidden_terms = [
        "Commercial Console",
        "Phase",
        "readiness",
        "preflight",
        "Docker",
        "Redis",
        "PostgreSQL",
        "CORS",
        "/api/v2",
        "RBAC",
        "permission_denied",
        "403",
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
    ]
    public_source = login + "\n" + nav
    for term in forbidden_terms:
        assert term not in public_source

    assert "AI 五金店大管家" in login
    assert "工作台" in nav
    assert "系统诊断" not in nav


def test_coming_soon_route_uses_business_labels_not_internal_phase_numbers():
    source = _source()
    roadmap = _block(source, "const moduleRoadmap", "function ComingSoon")

    for phase_label in ["F1", "F2", "F3", "F4", "F5", "Phase", "K1", "L1"]:
        assert phase_label not in roadmap

    assert "已开放" in roadmap
    assert "后续开放" in roadmap


def test_owner_diagnostics_is_owner_only_and_uses_product_wording():
    source = _source()
    top_bar = _block(source, "function TopBar", "function SkeletonHome")
    diagnostics = _block(source, "function CommercialTrialAcceptancePage", "const moduleRoadmap")

    assert "auth.roleKey === 'owner'" in top_bar
    assert "系统诊断" in top_bar
    for term in ["Docker", "Redis", "PostgreSQL", "CORS", "/api/v2", "RBAC", "permission_denied", "403"]:
        assert term not in diagnostics

    assert "上线体检" in diagnostics
    assert "数据保护" in diagnostics
