FROM nytimes/blender:4.2-cpu

# Install blender-mcp addon dependencies
RUN pip install --no-cache-dir websockets

# Copy MCP addon
COPY addon.py /root/.config/blender/4.2/scripts/addons/blender_mcp_addon.py

# Copy building generation scripts
COPY blender_scripts/ /opt/blender_scripts/

EXPOSE 9876

# Start Blender headless with MCP server
CMD ["blender", "--background", "--python", "/opt/blender_scripts/start_mcp_server.py"]
