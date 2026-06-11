"""
TypeRush LAN - WebSocket Bridge
Menjembatani browser (WebSocket) dengan server TCP.
Jalankan: python ws_bridge.py
Butuh: pip install websockets
"""

import asyncio
import websockets
import socket
import json
import threading

TCP_HOST = "127.0.0.1"
TCP_PORT = 5000
WS_PORT  = 5001


async def bridge(websocket):
    addr = websocket.remote_address
    print(f"[WS] Client terhubung dari {addr}")

    # Buka koneksi TCP ke server
    try:
        reader, writer = await asyncio.open_connection(TCP_HOST, TCP_PORT)
    except ConnectionRefusedError:
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"Server TypeRush tidak aktif di {TCP_HOST}:{TCP_PORT}"
        }))
        return

    async def ws_to_tcp():
        """Teruskan pesan dari browser ke TCP server."""
        try:
            async for message in websocket:
                writer.write((message + "\n").encode())
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    async def tcp_to_ws():
        """Teruskan pesan dari TCP server ke browser."""
        buffer = ""
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer += chunk.decode()
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        await websocket.send(line)
        except Exception:
            pass

    await asyncio.gather(ws_to_tcp(), tcp_to_ws())
    print(f"[WS] Client {addr} terputus.")


async def main():
    print("=" * 45)
    print("   TypeRush LAN — WebSocket Bridge")
    print(f"   WS Port  : {WS_PORT}")
    print(f"   TCP Host : {TCP_HOST}:{TCP_PORT}")
    print("=" * 45)
    print(f"[*] Bridge aktif di ws://0.0.0.0:{WS_PORT}\n")

    async with websockets.serve(bridge, "0.0.0.0", WS_PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Bridge dihentikan.")
