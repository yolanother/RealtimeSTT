import asyncio
import websockets
import pyaudio
import json
import argparse
import os
import threading
import queue
import sys

# --- Configuration ---
CHUNK_SIZE = 1024
FORMAT = pyaudio.paInt16  # 16-bit PCM
CHANNELS = 1
RATE = 16000  # Sample rate expected by the server after resampling
WEBSOCKET_URI_TEMPLATE = "ws://{host}:{port}"
# --- End Configuration ---

audio_queue = queue.Queue()
stop_event = threading.Event()
websocket_connection = None # Global variable to hold the connection

def audio_callback(in_data, frame_count, time_info, status):
    """Callback function for PyAudio stream."""
    if not stop_event.is_set():
        audio_queue.put(in_data)
    return (in_data, pyaudio.paContinue)

async def receive_transcriptions(websocket):
    """Receives messages from the WebSocket and prints transcriptions."""
    print("--- Listening for transcriptions ---")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get('type') == 'realtime':
                    print(f"\rReal-time: {data.get('text', '')}", end='', flush=True)
                elif data.get('type') == 'fullSentence':
                    print(f"\nFinal:     {data.get('text', '')}", flush=True)
                else:
                    print(f"\n[Unknown Message Type]: {data}", flush=True)
            except json.JSONDecodeError:
                print(f"\n[Received Non-JSON]: {message}", flush=True)
            except Exception as e:
                print(f"\n[Error processing received message]: {e}", flush=True)
    except websockets.exceptions.ConnectionClosedOK:
        print("\n--- Server closed connection normally ---")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\n--- Server connection closed unexpectedly: {e} ---")
    except Exception as e:
        print(f"\n--- Error receiving transcriptions: {e} ---")
    finally:
        print("\n--- Transcription listener stopped ---")
        stop_event.set() # Signal audio sending to stop

async def send_audio(websocket):
    """Reads audio from queue and sends it over WebSocket."""
    print("--- Sending audio ---")
    global websocket_connection
    websocket_connection = websocket # Store the connection globally
    try:
        while not stop_event.is_set():
            try:
                # Get audio chunk from queue (blocking with timeout)
                chunk = audio_queue.get(timeout=0.1)

                # Prepare metadata
                metadata = {"sampleRate": RATE}
                metadata_json = json.dumps(metadata).encode('utf-8')
                metadata_length = len(metadata_json).to_bytes(4, byteorder='little')

                # Send metadata length, metadata, and audio chunk
                await websocket.send(metadata_length + metadata_json + chunk)

            except queue.Empty:
                # If queue is empty, yield control to allow receiving messages
                await asyncio.sleep(0.01)
                continue
            except websockets.exceptions.ConnectionClosed:
                print("\n--- Connection closed while sending audio ---")
                break
            except Exception as e:
                print(f"\n--- Error sending audio: {e} ---")
                stop_event.set() # Stop on error
                break
    finally:
        print("\n--- Audio sending stopped ---")
        stop_event.set() # Ensure stop is signaled

async def main(uri):
    """Main function to handle audio stream and WebSocket communication."""
    p = pyaudio.PyAudio()
    stream = None
    websocket = None

    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK_SIZE,
                        stream_callback=audio_callback)

        print(f"Attempting to connect to {uri}...")
        async with websockets.connect(uri, ping_interval=10, ping_timeout=5) as websocket:
            print(f"Successfully connected to {uri}")
            print("--- Speak into microphone (Ctrl+C to stop) ---")

            # Run sender and receiver concurrently
            receiver_task = asyncio.create_task(receive_transcriptions(websocket))
            sender_task = asyncio.create_task(send_audio(websocket))

            # Wait for either task to complete (or be cancelled)
            done, pending = await asyncio.wait(
                [receiver_task, sender_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel any pending tasks
            for task in pending:
                task.cancel()
            # Ensure cancelled tasks are awaited
            if pending:
                await asyncio.wait(pending)

    except ConnectionRefusedError:
        print(f"Connection refused: Is the server running at {uri}?")
    except websockets.exceptions.InvalidStatusCode as e:
         print(f"Connection failed: Server returned status {e.status_code}. Is it the correct endpoint?")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print("\n--- Cleaning up ---")
        stop_event.set() # Signal threads/tasks to stop
        if websocket_connection and websocket_connection.state == websockets.protocol.State.OPEN: # Check state using correct enum path
             print("Closing WebSocket connection...")
             await websocket_connection.close(reason="Client shutting down")
        if stream and stream.is_active():
            print("Stopping audio stream...")
            stream.stop_stream()
        if stream:
            print("Closing audio stream...")
            stream.close()
        if p:
            print("Terminating PyAudio...")
            p.terminate()
        print("--- Cleanup complete ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test RealtimeSTT server with live microphone audio.")
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host address of the WebSocket server."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv('RTSTT_PORT', 9050)), # Use RTSTT_PORT like docker-compose
        help="Port number of the WebSocket server on the host."
    )
    args = parser.parse_args()

    server_uri = WEBSOCKET_URI_TEMPLATE.format(host=args.host, port=args.port)

    try:
        asyncio.run(main(server_uri))
    except KeyboardInterrupt:
        print("\n--- Interrupted by user (Ctrl+C) ---")
    finally:
        # Ensure stop event is set even if main loop is interrupted early
        stop_event.set()
        print("--- Exiting ---")