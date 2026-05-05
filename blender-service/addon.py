"""Blender MCP addon — minimal placeholder.

The actual MCP server logic is in blender_scripts/start_mcp_server.py
which runs via --python flag in headless mode.  This addon file exists
for potential Blender GUI integration in the future.
"""

bl_info = {
    "name": "BuildWise MCP Server",
    "author": "BuildWise",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "category": "System",
    "description": "MCP TCP server for AI-powered building generation",
}


def register():
    pass


def unregister():
    pass
