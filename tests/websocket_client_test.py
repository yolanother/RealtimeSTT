import asyncio
import websockets
import os
import argparse

async def test_websocket_connection(uri):
    """
    Attempts to connect to the specified WebSocket server URI.

    Args:
        uri (str): The WebSocket server URI (e.g., "ws://localhost:9050").
    """
    print(f"Attempting to connect to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Successfully connected to {uri}")
            # Optionally, send a test message and check response
            # await websocket.send("Hello Server!")
            # response = await websocket.recv()
            # print(f"Received response: {response}")
            await websocket.close(reason="Test complete")
            print("Connection closed.")
            return True
    except ConnectionRefusedError:
        print(f"Connection refused: Is the server running at {uri}?")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test WebSocket connection to RealtimeSTT server.")
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host address of the WebSocket server."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv('BROWSERCLIENT_PORT', 9050)),
        help="Port number of the WebSocket server."
    )
    args = parser.parse_args()

    server_uri = f"ws://{args.host}:{args.port}"

    connection_successful = asyncio.run(test_websocket_connection(server_uri))

    if not connection_successful:
        exit(1) # Exit with error code if connection failed