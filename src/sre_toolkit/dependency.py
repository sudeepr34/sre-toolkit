"""Service dependency graph and blast-radius analysis.

When a service fails, the first question in an incident is "what else
breaks?" This builds a dependency graph from a JSON mapping and answers
it: direct and transitive dependencies, dependents, the full blast
radius, and dependency cycles that make failures circular.
"""
from __future__ import annotations


class ServiceGraph:
    """Directed graph: edge A -> B means A depends on B."""

    def __init__(self, edges: dict):
        self.edges: dict[str, set] = {}
        for service, deps in edges.items():
            self.edges.setdefault(service, set())
            for dep in deps:
                self.edges[service].add(dep)
                self.edges.setdefault(dep, set())

    def services(self) -> list:
        return sorted(self.edges)

    def dependencies(self, service: str) -> list:
        """Direct dependencies of a service."""
        self._require(service)
        return sorted(self.edges[service])

    def dependents(self, service: str) -> list:
        """Services that directly depend on this one."""
        self._require(service)
        return sorted(
            s for s, deps in self.edges.items() if service in deps
        )

    def transitive_dependencies(self, service: str) -> list:
        """All services this one depends on, directly or indirectly."""
        self._require(service)
        seen: set = set()
        stack = list(self.edges[service])
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.edges[current] - seen)
        return sorted(seen)

    def blast_radius(self, service: str) -> list:
        """All services that break if this one fails (transitive dependents)."""
        self._require(service)
        reverse: dict[str, set] = {s: set() for s in self.edges}
        for src, deps in self.edges.items():
            for dep in deps:
                reverse[dep].add(src)
        seen: set = set()
        stack = list(reverse[service])
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(reverse[current] - seen)
        return sorted(seen)

    def find_cycles(self) -> list:
        """Each cycle found, as an ordered list ending where it started."""
        cycles = []
        color: dict[str, str] = {}
        path: list = []

        def visit(node: str) -> None:
            color[node] = "grey"
            path.append(node)
            for dep in sorted(self.edges[node]):
                if color.get(dep) == "grey":
                    start = path.index(dep)
                    cycles.append(path[start:] + [dep])
                elif color.get(dep) is None:
                    visit(dep)
            path.pop()
            color[node] = "black"

        for service in sorted(self.edges):
            if color.get(service) is None:
                visit(service)
        return cycles

    def _require(self, service: str) -> None:
        if service not in self.edges:
            raise ValueError(
                f"unknown service {service!r}; known: {', '.join(self.services())}"
            )

    def service_markdown(self, service: str) -> str:
        self._require(service)
        deps = self.dependencies(service)
        dependents = self.dependents(service)
        transitive = self.transitive_dependencies(service)
        blast = self.blast_radius(service)
        lines = [f"# Dependency report: {service}", ""]
        lines.append(f"- Direct dependencies ({len(deps)}): {', '.join(deps) or 'none'}")
        lines.append(f"- Direct dependents ({len(dependents)}): {', '.join(dependents) or 'none'}")
        lines.append(f"- Transitive dependencies ({len(transitive)}): {', '.join(transitive) or 'none'}")
        lines.append("")
        lines.append(f"## Blast radius ({len(blast)} services)")
        if blast:
            for affected in blast:
                lines.append(f"- {affected}")
        else:
            lines.append("Nothing else depends on this service.")
        return "\n".join(lines) + "\n"

    def full_markdown(self) -> str:
        lines = ["# Dependency graph", ""]
        lines.append("| Service | Deps | Dependents | Blast radius |")
        lines.append("| ------- | ---- | ---------- | ------------ |")
        for service in self.services():
            lines.append(
                f"| {service} | {len(self.dependencies(service))} "
                f"| {len(self.dependents(service))} "
                f"| {len(self.blast_radius(service))} |"
            )
        lines.append("")
        cycles = self.find_cycles()
        if cycles:
            lines.append("## Cycles detected")
            for cycle in cycles:
                lines.append(f"- {' -> '.join(cycle)}")
        else:
            lines.append("No dependency cycles.")
        return "\n".join(lines) + "\n"


def graph_from_json(data: dict) -> ServiceGraph:
    return ServiceGraph({str(k): list(v) for k, v in data.items()})
