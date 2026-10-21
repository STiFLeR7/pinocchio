"""Module dependency graph + package inventory — deterministic Python-structure facts."""

from __future__ import annotations

from nexus_repository.graph import module_graph, package_inventory
from tests.unit.nexus_repository.fixtures import make_repo


def test_package_inventory_lists_top_level_packages(tmp_path) -> None:
    inv = package_inventory(make_repo(tmp_path))
    assert set(inv.packages) == {"pkg_a", "pkg_b"}


def test_module_graph_extracts_intra_repo_edges(tmp_path) -> None:
    root = make_repo(tmp_path)
    graph = module_graph(root, package_inventory(root))
    # pkg_a imports pkg_b (both intra-repo); os is external → not an edge
    assert ("pkg_a", "pkg_b") in graph.edges
    assert all(src in graph.nodes and dst in graph.nodes for src, dst in graph.edges)
    assert not any("os" in edge for edge in graph.edges)


def test_module_graph_is_deterministic(tmp_path) -> None:
    root = make_repo(tmp_path)
    inv = package_inventory(root)
    assert module_graph(root, inv) == module_graph(root, inv)
