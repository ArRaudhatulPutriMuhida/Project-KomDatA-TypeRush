"""
TypeRush LAN - Server
Mengelola room, soal, skor, dan leaderboard untuk semua client.
Revisi:
- game bisa dimainkan lagi tanpa restart server
- soal random dari banyak kalimat dan menghindari pengulangan berturut-turut
- room otomatis reset saat semua pemain keluar / reload
- handling disconnect lebih aman
"""

import socket
import threading
import json
import time
import random
import difflib

HOST = "0.0.0.0"
PORT = 5000
MAX_PLAYERS = 2

SENTENCES = [
    "Belajar pemrograman membutuhkan ketekunan dan latihan setiap hari",
    "Komunikasi data adalah fondasi dari semua jaringan komputer modern",
    "Python adalah bahasa pemrograman yang mudah dipelajari oleh pemula",
    "Server dan client bekerja sama untuk mengirimkan data melalui jaringan",
    "Kecepatan mengetik dapat ditingkatkan dengan latihan yang konsisten",
    "Jaringan lokal memungkinkan beberapa perangkat terhubung satu sama lain",
    "Algoritma yang baik membuat program berjalan lebih cepat dan efisien",
    "Setiap karakter yang dikirim melalui jaringan membutuhkan bandwidth",
    "Multiplayer game memerlukan sinkronisasi data yang akurat dan cepat",
    "Universitas Syiah Kuala menghasilkan lulusan teknologi yang berkualitas",
    "Antarmuka yang rapi membuat pengalaman bermain terasa lebih nyaman",
    "Setiap solusi digital yang baik lahir dari masalah yang nyata",
    "Koneksi yang stabil sangat penting dalam sistem client server",
    "Data yang dikirim harus dijaga ketepatan dan kecepatannya",
    "Berpikir logis membantu programmer menyelesaikan masalah dengan efektif",
    "Akurasi dan kecepatan adalah kunci utama dalam permainan mengetik",
    "Pengalaman pengguna yang menarik dapat membuat aplikasi lebih disukai",
    "Sebuah game sederhana tetap bisa menunjukkan konsep jaringan yang kuat",
]


def calculate_accuracy(original: str, typed: str) -> float:
    ratio = difflib.SequenceMatcher(None, original, typed).ratio()
    return round(ratio * 100, 2)


def calculate_score(original: str, typed: str, accuracy: float, elapsed: float) -> tuple[int, float]:
    if elapsed <= 0:
        return 0, 0.0

    word_count = max(len(original.split()), 1)
    wpm = round((word_count / elapsed) * 60, 2)
    completion_bonus = 1.0 if typed.strip() == original.strip() else min(len(typed) / max(len(original), 1), 1.0)
    score = int((accuracy * 6) + (wpm * 12) + (completion_bonus * 120))
    return max(score, 0), wpm


class GameRoom:
    def __init__(self):
        self.players: dict[str, dict] = {}
        self.sentence: str = ""
        self.state: str = "waiting"          # waiting | playing | finished
        self.lock = threading.Lock()
        self.start_time: float = 0
        self.last_sentence: str = ""

    def add_player(self, name: str, conn: socket.socket, addr) -> bool:
        with self.lock:
            if len(self.players) >= MAX_PLAYERS:
                return False
            if name in self.players:
                return False
            self.players[name] = {"conn": conn, "addr": addr, "result": None}
            return True

    def remove_player(self, name: str):
        with self.lock:
            existed = name in self.players
            self.players.pop(name, None)
            remaining_names = list(self.players.keys())
            remaining_count = len(self.players)
            should_reset = remaining_count == 0
            if should_reset:
                self._reset_unlocked()
            elif self.state in {"playing", "finished"}:
                # Jika ada yang keluar saat game berlangsung / selesai,
                # siapkan room kembali untuk ronde baru pemain berikutnya.
                for pdata in self.players.values():
                    pdata["result"] = None
                self.state = "waiting"
                self.sentence = ""
                self.start_time = 0
        return existed, remaining_names, remaining_count, should_reset

    def _reset_unlocked(self):
        self.players.clear()
        self.sentence = ""
        self.state = "waiting"
        self.start_time = 0

    def ready_to_start(self) -> bool:
        return len(self.players) >= MAX_PLAYERS and self.state == "waiting"

    def all_submitted(self) -> bool:
        with self.lock:
            return len(self.players) == MAX_PLAYERS and all(p["result"] is not None for p in self.players.values())

    def choose_sentence(self) -> str:
        choices = [s for s in SENTENCES if s != self.last_sentence] or SENTENCES
        chosen = random.choice(choices)
        self.last_sentence = chosen
        return chosen

    def start_round(self) -> str:
        with self.lock:
            self.state = "playing"
            self.sentence = self.choose_sentence()
            self.start_time = time.time()
            for pdata in self.players.values():
                pdata["result"] = None
            return self.sentence

    def get_leaderboard(self) -> list[dict]:
        board = []
        with self.lock:
            for name, data in self.players.items():
                if data["result"]:
                    r = data["result"]
                    board.append({
                        "name": name,
                        "accuracy": r["accuracy"],
                        "elapsed": r["elapsed"],
                        "score": r["score"],
                        "wpm": r["wpm"],
                    })
        board.sort(key=lambda x: (-x["score"], x["elapsed"]))
        for i, entry in enumerate(board):
            entry["rank"] = i + 1
        return board


room = GameRoom()


def broadcast(message: dict, exclude: str | None = None):
    data = json.dumps(message) + "\n"
    with room.lock:
        items = list(room.players.items())
    for name, player in items:
        if name == exclude:
            continue
        try:
            player["conn"].sendall(data.encode())
        except Exception:
            pass


def send_to(conn: socket.socket, message: dict):
    try:
        conn.sendall((json.dumps(message) + "\n").encode())
    except Exception:
        pass


def recv_json_line(conn: socket.socket) -> dict | None:
    buffer = ""
    while True:
        chunk = conn.recv(1024).decode()
        if not chunk:
            return None
        buffer += chunk
        if "\n" in buffer:
            line, _ = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                return None
            return json.loads(line)
        # fallback jika client lama kirim tanpa newline
        text = buffer.strip()
        if text.startswith("{") and text.endswith("}"):
            return json.loads(text)


def handle_client(conn: socket.socket, addr):
    print(f"[+] Koneksi dari {addr}")
    player_name = None
    buffer = ""

    try:
        raw_msg = recv_json_line(conn)
        if not raw_msg or raw_msg.get("type") != "login":
            send_to(conn, {"type": "error", "message": "Kirim login terlebih dahulu"})
            conn.close()
            return

        player_name = raw_msg.get("name", "").strip()
        if not player_name:
            send_to(conn, {"type": "error", "message": "Nama tidak boleh kosong"})
            conn.close()
            return

        if not room.add_player(player_name, conn, addr):
            current_count = len(room.players)
            if current_count >= MAX_PLAYERS:
                send_to(conn, {"type": "error", "message": f"Room penuh ({MAX_PLAYERS} pemain)"})
            else:
                send_to(conn, {"type": "error", "message": "Nama sudah digunakan"})
            conn.close()
            return

        print(f"[+] {player_name} bergabung. ({len(room.players)}/{MAX_PLAYERS})")
        send_to(conn, {
            "type": "joined",
            "message": f"Selamat datang, {player_name}! Menunggu pemain lain...",
            "max_players": MAX_PLAYERS,
        })
        broadcast({"type": "info", "message": f"{player_name} bergabung ke room. ({len(room.players)}/{MAX_PLAYERS})"}, exclude=player_name)

        if room.ready_to_start():
            sentence = room.start_round()
            start_msg = {
                "type": "start",
                "sentence": sentence,
                "message": "Permainan dimulai! Ketik kalimat di bawah ini:",
            }
            broadcast(start_msg)
            print(f"[>] Game dimulai. Soal: '{sentence}'")

        while True:
            chunk = conn.recv(4096).decode()
            if not chunk:
                break
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "result":
                    typed = msg.get("typed", "")
                    elapsed = float(msg.get("elapsed", 0) or 0)
                    accuracy = calculate_accuracy(room.sentence, typed)
                    score, wpm = calculate_score(room.sentence, typed, accuracy, elapsed)

                    with room.lock:
                        if player_name in room.players:
                            room.players[player_name]["result"] = {
                                "typed": typed,
                                "elapsed": round(elapsed, 2),
                                "accuracy": accuracy,
                                "score": score,
                                "wpm": wpm,
                            }
                    print(f"[<] {player_name} selesai — {elapsed:.2f}s, {accuracy}% akurasi, skor {score}")
                    send_to(conn, {"type": "ack", "message": "Hasil diterima, menunggu pemain lain..."})
                    broadcast({"type": "info", "message": f"{player_name} sudah selesai!"}, exclude=player_name)

                    if room.all_submitted():
                        with room.lock:
                            room.state = "finished"
                        leaderboard = room.get_leaderboard()
                        print("[=] Semua pemain selesai. Leaderboard:")
                        for entry in leaderboard:
                            print(f"    #{entry['rank']} {entry['name']} — skor {entry['score']}, {entry['accuracy']}%, {entry['elapsed']}s")
                        broadcast({"type": "leaderboard", "data": leaderboard})

    except Exception as e:
        print(f"[!] Error dari {addr}: {e}")
    finally:
        if player_name:
            existed, remaining_names, remaining_count, should_reset = room.remove_player(player_name)
            if existed:
                print(f"[-] {player_name} keluar.")
                if remaining_count > 0:
                    broadcast({"type": "info", "message": f"{player_name} keluar dari room. Menunggu pemain baru..."})
                if should_reset:
                    print("[*] Room di-reset. Siap untuk permainan berikutnya.")
        conn.close()



def main():
    print("=" * 45)
    print("   TypeRush LAN — Server")
    print(f"   Host : {HOST}  Port : {PORT}")
    print(f"   Maks : {MAX_PLAYERS} pemain per room")
    print("=" * 45)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[*] Server aktif, menunggu koneksi...\n")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[*] Server dihentikan.")
    finally:
        server.close()


if __name__ == "__main__":
    main()
