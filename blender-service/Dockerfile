FROM nytimes/blender:latest

# Copy building generation scripts (MCP server runs via --python flag)
COPY blender_scripts/ /opt/blender_scripts/

EXPOSE 9876

# Start Blender headless with MCP server
CMD ["blender", "--background", "--python", "/opt/blender_scripts/start_mcp_server.py"]
