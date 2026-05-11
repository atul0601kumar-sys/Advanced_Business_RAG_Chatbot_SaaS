from __future__ import annotations

from time import perf_counter

import pytest


@pytest.mark.performance
def test_auth_me_and_analytics_respond_quickly_for_small_fixture_set(api_client, auth_headers, seeded_workspace):
    start = perf_counter()
    me_response = api_client.get("/api/v1/auth/me", headers=auth_headers)
    me_elapsed = perf_counter() - start

    start = perf_counter()
    analytics_response = api_client.get(
        f"/api/v1/analytics/overview?workspace_id={seeded_workspace.workspace_id}",
        headers=auth_headers,
    )
    analytics_elapsed = perf_counter() - start

    assert me_response.status_code == 200
    assert analytics_response.status_code == 200
    assert me_elapsed < 1.0
    assert analytics_elapsed < 1.5
