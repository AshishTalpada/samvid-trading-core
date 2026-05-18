import ast
import logging
import os

logger = logging.getLogger(__name__)


def _is_type_checking_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Name)
        and test.id == "TYPE_CHECKING"
        or isinstance(test, ast.Attribute)
        and test.attr == "TYPE_CHECKING"
    )


def _collect_imports_from_stmt(node: ast.stmt) -> list[str]:
    imports = []
    if isinstance(node, ast.Import):
        imports.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imports.append(node.module)
    elif _is_type_checking_guard(node):
        return []
    return imports


def find_imports(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError as exc:
            logger.warning("Skipping unparsable file %s: %s", filepath, exc)
            return []

    imports = []
    for node in tree.body:
        imports.extend(_collect_imports_from_stmt(node))
    return imports


def build_graph(src_dir):
    graph = {}
    for filename in os.listdir(src_dir):
        if filename.endswith(".py"):
            module_name = filename[:-3]
            filepath = os.path.join(src_dir, filename)
            deps = find_imports(filepath)
            # Filter for local deps
            local_deps = []
            for d in deps:
                # Check if it's a local module
                d_base = d.split(".")[0]
                if os.path.exists(os.path.join(src_dir, d_base + ".py")):
                    local_deps.append(d_base)
            graph[module_name] = set(local_deps)
    return graph


def find_cycle(graph):
    visited = set()
    path = []

    def visit(node):
        if node in path:
            cycle = path[path.index(node) :] + [node]
            return cycle
        if node in visited:
            return None

        visited.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            cycle = visit(neighbor)
            if cycle:
                return cycle
        path.pop()
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


if __name__ == "__main__":
    src_dir = "src"
    graph = build_graph(src_dir)
    cycle = find_cycle(graph)
    if cycle:
        print(f"CYCLE_DETECTED: {' -> '.join(cycle)}")
    else:
        print("NO_CYCLES_DETECTED")
