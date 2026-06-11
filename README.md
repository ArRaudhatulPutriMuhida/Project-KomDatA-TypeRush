Anggota:
Ar Raudhatul Putri Muhida (2408107010082)
Silvia Putri (2408107010086)
Nayla Khansa Livya (2408107010098)


# TypeRush LAN 🎯

Game adu cepat mengetik berbasis multiplayer LAN menggunakan arsitektur **client-server TCP**.
Project mata kuliah **Komunikasi Data** — Universitas Syiah Kuala.

## Revisi terbaru
- Tampilan web dibuat lebih rapi dan aesthetic dengan nuansa **earth tone**.
- Setelah satu ronde selesai, game **bisa dimainkan lagi** tanpa perlu restart server.
- Kalimat soal sekarang **acak dari banyak pilihan**, bukan hanya terasa satu soal terus.
- Versi CLI juga ditambah opsi **main lagi**.
- Leaderboard menampilkan skor, akurasi, waktu, dan WPM.

## File utama
- `server.py` → server TCP utama
- `client_cli.py` → client CLI
- `ws_bridge.py` → jembatan WebSocket untuk web
- `index.html` → client web

## Cara menjalankan

### 1) Jalankan server
```bash
python server.py
```

### 2) Jalankan client CLI
Buka 2 terminal berbeda:
```bash
python client_cli.py
```

### 3) Jalankan client web
Install dependensi jika belum ada:
```bash
pip install websockets
```
Jalankan bridge:
```bash
python ws_bridge.py
```
Lalu buka `index.html` di 2 tab atau 2 perangkat berbeda.

## Port
- Server utama: TCP `5000`
- WebSocket bridge: `5001`

## Catatan
Jika bermain melalui jaringan LAN, gunakan IP komputer server saat mengisi host pada client.
