fix: Bind server to 0.0.0.0 and revert debug changes

- Changed WebSocket server host binding from "localhost" to "0.0.0.0" in `example_browserclient/server.py` to allow connections from outside the Docker container. This resolves the "did not receive a valid HTTP response" error during WebSocket handshake and the "Empty reply from server" error during HTTP health checks when accessed via port mapping.
- Reverted temporary debugging changes that commented out recorder initialization, HTML modification, and health check logic.