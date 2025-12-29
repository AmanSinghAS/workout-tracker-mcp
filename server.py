from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("workout-tracker-mcp")

@mcp.tool()
def hello_world() -> str:
    """Returns a hello world greeting."""
    return "Hello, World!"

if __name__ == "__main__":
    mcp.run()
