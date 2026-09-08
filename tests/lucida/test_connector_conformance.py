from lucida.connector_conformance import (
    render_connector_conformance,
    run_connector_conformance,
)


def test_all_three_connector_boundaries_pass_offline_conformance():
    report = run_connector_conformance()

    assert report["status"] == "PASS"
    assert set(report["connectors"]) == {"adobe", "multi_xio", "resolume"}
    assert report["connectors"]["adobe"]["transport"] == "adobe"
    assert set(report["connectors"]["adobe"]["sources"]) == {"xio", "vizz", "pupila"}
    assert all(
        source_report["replay_status"] == "PASS"
        for source_report in report["connectors"]["adobe"]["sources"].values()
    )
    assert report["connectors"]["multi_xio"]["source"] == "XIO"
    assert report["connectors"]["resolume"]["surface_id"] == "RESOLUME"
    assert report["safety"] == {
        "proposal_only": True,
        "external_side_effects": False,
        "hosts_opened": False,
        "sockets_opened": False,
        "raw_content_forwarded": False,
    }


def test_connector_conformance_is_deterministic_and_preserves_ownership():
    first = run_connector_conformance()
    second = run_connector_conformance()

    assert first == second
    assert first["ownership"]["multi_xio"].startswith("capture")
    assert first["ownership"]["resolume"].startswith("visual")
    rendered = render_connector_conformance(first)
    assert '"external_side_effects": false' in rendered
    assert '"raw_content_forwarded": false' in rendered
