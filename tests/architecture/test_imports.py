# ruff: noqa: SIM102, SIM108, RUF005
import ast
from pathlib import Path


def get_amberclaw_imports(file_path: Path) -> set[str]:
    """Parse a python file using AST and return internal amberclaw module imports."""
    internal_imports = set()
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return internal_imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("amberclaw"):
                    internal_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("amberclaw"):
                internal_imports.add(node.module)

    return internal_imports


def build_import_graph(src_dir: Path) -> dict[str, set[str]]:
    """Build a graph mapping package names to imported amberclaw package names."""
    graph = {}
    for py_file in src_dir.rglob("*.py"):
        rel = py_file.relative_to(src_dir).with_suffix("")
        mod_parts = tuple(rel.parts)
        if mod_parts[-1] == "__init__":
            mod_parts = mod_parts[:-1]

        if not mod_parts:
            mod_name = "amberclaw"
        else:
            mod_name = "amberclaw." + ".".join(mod_parts)

        imports = get_amberclaw_imports(py_file)
        graph[mod_name] = imports

    return graph


def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Detect cycles in the directed import graph using DFS."""
    cycles = []
    visited = set()
    rec_stack = set()
    path = []

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            # Resolve neighbor to known graph node key
            matched_key = None
            for key in graph:
                if neighbor == key or neighbor.startswith(key + "."):
                    matched_key = key
                    break

            if matched_key:
                if matched_key not in visited:
                    dfs(matched_key)
                elif matched_key in rec_stack:
                    cycle_start = path.index(matched_key)
                    cycles.append(path[cycle_start:] + [matched_key])

        path.pop()
        rec_stack.remove(node)

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node)

    return cycles


def test_zero_circular_imports():
    src_dir = Path(__file__).parent.parent.parent / "src" / "amberclaw"
    assert src_dir.exists()

    graph = build_import_graph(src_dir)
    cycles = detect_cycles(graph)

    assert not cycles, f"Circular imports detected in amberclaw codebase: {cycles}"


def test_layer_dependency_rules():
    src_dir = Path(__file__).parent.parent.parent / "src" / "amberclaw"
    graph = build_import_graph(src_dir)

    forbidden_rules = {
        "amberclaw.config": {
            "amberclaw.agent",
            "amberclaw.api",
            "amberclaw.governance",
            "amberclaw.web",
            "amberclaw.tui",
            "amberclaw.cli",
        },
        "amberclaw.core": {
            "amberclaw.api",
            "amberclaw.cli",
            "amberclaw.tui",
            "amberclaw.web",
            "amberclaw.channels",
        },
        "amberclaw.bus": {
            "amberclaw.agent",
            "amberclaw.api",
            "amberclaw.cli",
            "amberclaw.tui",
            "amberclaw.web",
            "amberclaw.channels",
        },
        "amberclaw.security": {
            "amberclaw.agent",
            "amberclaw.api",
            "amberclaw.cli",
            "amberclaw.tui",
            "amberclaw.web",
            "amberclaw.channels",
        },
        "amberclaw.memory": {
            "amberclaw.agent",
            "amberclaw.api",
            "amberclaw.cli",
            "amberclaw.tui",
            "amberclaw.web",
            "amberclaw.channels",
        },
        "amberclaw.providers": {
            "amberclaw.agent",
            "amberclaw.api",
            "amberclaw.cli",
            "amberclaw.tui",
            "amberclaw.web",
            "amberclaw.channels",
        },
        "amberclaw.terminal": {
            "amberclaw.agent",
            "amberclaw.api",
            "amberclaw.cli",
            "amberclaw.tui",
            "amberclaw.web",
            "amberclaw.channels",
        },
    }

    for mod_name, imports in graph.items():
        for prefix, forbidden_set in forbidden_rules.items():
            if mod_name == prefix or mod_name.startswith(prefix + "."):
                for imp in imports:
                    for forbidden in forbidden_set:
                        assert not (
                            imp == forbidden or imp.startswith(forbidden + ".")
                        ), (
                            f"Architecture violation: {mod_name} imports higher-level module {imp}"
                        )
