from context_engine.api.routes import api_router, health_router


def test_phase_one_router_excludes_deferred_wiki_and_observability_routes() -> None:
    paths = {route.path for route in api_router.routes}

    assert not any(path.startswith("/wiki") or path.startswith("/admin/wiki") for path in paths)
    assert "/admin/audit-events" not in paths
    assert not any("/diagnostics/" in path for path in paths)


def test_phase_one_health_routes_remain_registered() -> None:
    paths = {route.path for route in health_router.routes}

    assert {"/health/live", "/health/ready"} <= paths


def test_phase_one_chat_turn_replay_and_cancel_routes_remain_registered() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/conversations/{conversationId}/turns/{turnId}/events" in paths
    assert "/conversations/{conversationId}/turns/{turnId}:cancel" in paths
