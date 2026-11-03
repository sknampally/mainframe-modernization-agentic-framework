"""Local-only synthetic MCP server for transport tests; never contacts AWS."""
import json
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

server = MCPServer('offline-transport-fixture')

@server.tool()
def get_status() -> dict:
    return {'content': [{'type': 'text', 'text': json.dumps({'success': True,
                'data': {'connected': True, 'fixture': True}})}], 'isError': False}

@server.tool()
def echo_required(value: str) -> dict:
    return {'success': True, 'data': {'echo': value}}

@server.tool()
def reject_create() -> dict:
    raise ValueError('Synthetic validation rejection; no creation occurred')

if __name__ == '__main__':
    server.run(transport='stdio')
