"""
TypeRush LAN - CLI Client
Antarmuka terminal untuk bermain TypeRush LAN.
Revisi:
- bisa main lagi tanpa menutup program
- tampilan terminal dirapikan
"""

import socket
import threading
import json
import time
import os

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    print("\033[38;5;180m" + """
████████╗██╗   ██╗██████╗ ███████╗██████╗ ██╗   ██╗███████╗██╗  ██╗
╚══██╔══╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██║   ██║██╔════╝██║  ██║
   ██║    ╚████╔╝ ██████╔╝█████╗  ██████╔╝██║   ██║███████╗███████║
   ██║     ╚██╔╝  ██╔═══╝ ██╔══╝  ██╔══██╗██║   ██║╚════██║██╔══██║
   ██║      ██║   ██║     ███████╗██║  ██║╚██████╔╝███████║██║  ██║
   ╚═╝      ╚═╝   ╚═╝     ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
""" + "\033[0m")
    print("\033[90mGame adu cepat mengetik berbasis LAN · CLI Mode\033[0m\n")


def print_sep(char="─", width=68):
    print("\033[90m" + char * width + "\033[0m")


def print_leaderboard(data: list):
    print()
    print_sep("═")
    print("\033[93m  🏆 LEADERBOARD AKHIR\033[0m")
    print_sep("═")
    medals = ["🥇", "🥈", "🥉"]
    for entry in data:
        rank = entry["rank"]
        medal = medals[rank - 1] if rank <= 3 else f"#{rank}"
        print(
            f"  {medal:<3} {entry['name']:<15} "
            f"Skor: \033[92m{entry['score']:<5}\033[0m  "
            f"Akurasi: \033[96m{entry['accuracy']}%\033[0m  "
            f"Waktu: \033[93m{entry['elapsed']}s\033[0m  "
            f"WPM: \033[95m{entry.get('wpm', 0)}\033[0m"
        )
    print_sep("═")
    print()


class TypeRushClient:
    def __init__(self):
        self.conn = None
        self.name = ""
        self.sentence = ""
        self.game_started = threading.Event()
        self.game_done = threading.Event()
        self.buffer = ""
        self.closed = False

    def connect(self, host: str, port: int) -> bool:
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((host, port))
            return True
        except ConnectionRefusedError:
            print(f"\033[91m[!] Tidak bisa terhubung ke {host}:{port}. Pastikan server sudah berjalan.\033[0m")
            return False

    def send(self, message: dict):
        try:
            self.conn.sendall((json.dumps(message) + "\n").encode())
        except Exception as e:
            print(f"\033[91m[!] Gagal mengirim data: {e}\033[0m")

    def listen(self):
        while not self.closed:
            try:
                chunk = self.conn.recv(4096).decode()
                if not chunk:
                    break
                self.buffer += chunk
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        self.handle_message(msg)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                break
        self.game_done.set()

    def handle_message(self, msg: dict):
        mtype = msg.get("type")

        if mtype == "error":
            print(f"\n\033[91m[✗] {msg['message']}\033[0m")
            self.game_done.set()

        elif mtype == "joined":
            print(f"\033[92m[✓] {msg['message']}\033[0m")

        elif mtype == "info":
            print(f"\033[90m[i] {msg['message']}\033[0m")

        elif mtype == "start":
            self.sentence = msg["sentence"]
            self.game_started.set()

        elif mtype == "ack":
            print(f"\n\033[90m[i] {msg['message']}\033[0m")

        elif mtype == "leaderboard":
            print_leaderboard(msg["data"])
            self.game_done.set()

    def play(self):
        clear()
        print_banner()

        host_input = input(f"Server IP [\033[96m{SERVER_HOST}\033[0m]: ").strip()
        host = host_input if host_input else SERVER_HOST
        print_sep()

        while True:
            name = input("Nama pemain: ").strip()
            if name:
                self.name = name
                break
            print("\033[91mNama tidak boleh kosong.\033[0m")

        print_sep()
        print(f"Menghubungkan ke \033[96m{host}:{SERVER_PORT}\033[0m...")

        if not self.connect(host, SERVER_PORT):
            return

        self.send({"type": "login", "name": self.name})
        listener = threading.Thread(target=self.listen, daemon=True)
        listener.start()

        print("\n\033[93mMenunggu pemain lain bergabung...\033[0m")
        self.game_started.wait()

        clear()
        print_banner()
        print_sep()
        print("\033[93m⏱ GAME DIMULAI! Ketik kalimat di bawah ini:\033[0m")
        print_sep()
        print(f"\n\033[97m{self.sentence}\033[0m\n")
        print_sep()

        start_time = time.time()
        try:
            typed = input("Ketikanmu: ")
        except KeyboardInterrupt:
            typed = ""

        elapsed = round(time.time() - start_time, 3)
        self.send({"type": "result", "typed": typed, "elapsed": elapsed})

        correct = sum(a == b for a, b in zip(typed, self.sentence))
        local_acc = round((correct / max(len(self.sentence), 1)) * 100, 1)

        print(f"\n\033[90mWaktu   : {elapsed:.2f} detik\033[0m")
        print(f"\033[90mAkurasi : {local_acc}% (preview lokal)\033[0m")

        self.game_done.wait()
        self.close()

    def close(self):
        self.closed = True
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass


def main():
    while True:
        client = TypeRushClient()
        client.play()
        again = input("Main lagi? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("Terima kasih sudah bermain TypeRush LAN!")
            break


if __name__ == "__main__":
    main()
