"""Real MCP v2 stdio server used by RKJO end-to-end tests."""

from mcp.server import MCPServer


mcp = MCPServer("RKJO Test Education Server")


@mcp.tool()
def search_courses(query: str) -> list[str]:
    """Return deterministic course matches for an education search query."""
    normalized_query = query.strip().lower()
    catalog = [
        "Biotechnology Fundamentals",
        "Applied Bioinformatics",
        "Agricultural Biotechnology",
        "Data Science for Life Sciences",
    ]

    if not normalized_query:
        return []

    return [
        course
        for course in catalog
        if normalized_query in course.lower()
    ]


if __name__ == "__main__":
    mcp.run()
