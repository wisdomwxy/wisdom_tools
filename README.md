# wisdom_tool

A small collection of **command-line Python utilities** for everyday media conversion: **PDF to SVG** and **video to GIF**. Each tool is self-contained under its own folder.

## Requirements

- **Python** 3.10+ recommended  
- **Conda** (optional): create or use an environment such as `wisdom_tools`  
- **FFmpeg**: required by MoviePy for video decoding (install system-wide or via conda: `conda install -c conda-forge ffmpeg`)

Install Python dependencies:

```bash
conda activate wisdom_tools
pip install -r requirements.txt
```

On Windows PowerShell, chain commands with `;`:

```powershell
conda activate wisdom_tools; pip install -r requirements.txt
```

---

## Pdf2Svg (`Pdf2Svg/pdf2svg.py`)

Convert **PDF pages to SVG** using [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`). Output is vector-oriented; you can tune DPI and page selection.

**Features**

- One or multiple PDF inputs; output directory is created if missing  
- Page selection: `all`, comma-separated pages (`1,3,5`), ranges (`1-5`), or mixed (`1-3,7,10-12`)  
- `--dpi` for render scale (default 72, relative to PDF’s 72 pt user space)  
- By default text is drawn as paths; use `--no-text-as-path` for smaller files with `<text>` (viewer must have fonts)

**Examples**

```bash
python Pdf2Svg/pdf2svg.py document.pdf -o ./out
python Pdf2Svg/pdf2svg.py document.pdf -o ./out --dpi 150
python Pdf2Svg/pdf2svg.py a.pdf b.pdf -o ./out --pages 1-3,7
python Pdf2Svg/pdf2svg.py doc.pdf -o ./out --no-text-as-path
```

Help: `python Pdf2Svg/pdf2svg.py -h`

---

## Video2Gif (`Video2Gif/video2gif.py`)

Convert **common video formats** to **animated GIF** using [MoviePy](https://zulko.github.io/moviepy/) 2.x and [Pillow](https://python-pillow.org/) for palette quantization and smaller files.

**Features**

- Inputs: files or directories (scans for `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`, `.wmv`, `.flv`, `.m4v`)  
- Trim with `--start`, `--end`, or `--duration` (times as seconds or `MM:SS` / `HH:MM:SS`)  
- Resize: `--scale`, `--width`, and/or `--height`  
- `--fps` for output frame rate; `--colors` (2–256) to limit palette size  
- Batch mode: multiple inputs with `-o` pointing to a directory  
- Progress via `tqdm` (disable with `--no-progress`)

**Examples**

```bash
python Video2Gif/video2gif.py demo.mp4
python Video2Gif/video2gif.py demo.mp4 -o out.gif
python Video2Gif/video2gif.py demo.mp4 --start 5 --end 12 -o clip.gif
python Video2Gif/video2gif.py demo.mp4 --width 320 --fps 12 --colors 128 -o lite.gif
python Video2Gif/video2gif.py ./videos/ -o ./gifs/
```

Help: `python Video2Gif/video2gif.py -h`

---

## Project layout

```
wisdom_tool/
├── README.md
├── requirements.txt
├── Pdf2Svg/
│   └── pdf2svg.py
└── Video2Gif/
    └── video2gif.py
```

---

