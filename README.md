# 🎧 AI DJ Studio v2.0

**Professional AI-Powered DJ Software for Windows**  
Built for AMD Ryzen 7840HS · Radeon 780M · Windows 10/11

---

## ⬇️ Download the Windows Installer

> **Click the Actions tab above → click the latest green ✅ run → scroll down to Artifacts → click to download**

| File | What it is |
|---|---|
| `AI-DJ-Studio-Setup-exe` | **Recommended** — full Windows installer with Start Menu, desktop icon, uninstaller |
| `AI-DJ-Studio-Portable-zip` | No install needed — extract and double-click `AIDJStudio.exe` |
| `AIDJStudio-exe-only` | Just the raw EXE file |

---

## 🎵 Features

| Tab | What it does |
|---|---|
| 🎤 **DJ Styles** | 10 legendary DJs — Funk Master Flex, Tiësto, Jazzy Jeff, Grandmaster Flash, DJ Khaled, Avicii, DJ Premier, Calvin Harris, Deadmau5, DJ Snake |
| 🔍 **Search Songs** | Search YouTube, download as MP3 |
| 📂 **Library** | All your tracks with BPM, key, Camelot wheel |
| 🎚 **Mix Studio** | Two decks, beatmatching, adjustable crossfade |
| 🤖 **Auto-Mix AI** | Add 5+ songs → AI mixes them automatically |
| 📊 **Visualizer** | Animated spectrum in 3 modes, 5 colour palettes |
| 💾 **Playlists** | Save, load, export, import playlist files |
| ⚔️ **Battle Mode** | Two DJ styles compete head-to-head |

---

## 🚀 After Installing

1. **Install FFmpeg** — open Command Prompt and run:
   ```
   winget install ffmpeg
   ```
2. Launch **AI DJ Studio** from your Start Menu or desktop
3. Go to **🎤 DJ Styles** and pick your DJ
4. Go to **🔍 Search Songs** and find some music
5. Hit **🤖 Auto-Mix** and let the AI DJ do its thing!

See `FFMPEG_SETUP.txt` (inside the app folder) for detailed FFmpeg instructions.

---

## 🔄 How the Build Works

This repository uses **GitHub Actions** to automatically build the Windows `.exe` every time code is pushed. The build runs on Microsoft's free Windows Server 2022 cloud machines.

Build time: ~15–20 minutes  
Cost: Free (uses GitHub's free tier)

---

## ⚠️ Important Note

AI DJ Studio is for mixing music you own or have rights to use.  
Please respect copyright and YouTube's terms of service.

---

*AI DJ Studio v2.0 · Built with Python · Tkinter · Librosa · FFmpeg · PyInstaller*
