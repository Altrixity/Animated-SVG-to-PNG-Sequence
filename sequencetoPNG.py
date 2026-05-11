import asyncio
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from playwright.async_api import async_playwright


# ---------------- SVG SIZE PARSER ----------------
def get_svg_size(svg_content):

    viewbox = re.search(r'viewBox="([\d\.\s\-]+)"', svg_content)

    if viewbox:
        parts = list(map(float, viewbox.group(1).split()))
        return int(parts[2]), int(parts[3])

    width = re.search(r'width="([\d\.]+)', svg_content)
    height = re.search(r'height="([\d\.]+)', svg_content)

    if width and height:
        return int(float(width.group(1))), int(float(height.group(1)))

    return 512, 512


# ---------------- APP ----------------
class SVGExporterApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Animated SVG → PNG Sequence")
        self.root.geometry("500x400")  # fixed size

        self.svg_path = None
        self.out_dir = None

        # ---------------- UI ----------------
        tk.Button(root, text="Load SVG", command=self.load_svg).pack(pady=5)
        self.svg_label = tk.Label(root, text="No SVG loaded")
        self.svg_label.pack()

        tk.Button(root, text="Select Output Folder", command=self.load_folder).pack(pady=5)
        self.folder_label = tk.Label(root, text="No folder selected")
        self.folder_label.pack()

        # name input
        tk.Label(root, text="Export Name").pack()
        self.name_entry = tk.Entry(root)
        self.name_entry.insert(0, "")
        self.name_entry.pack()

        # fps
        tk.Label(root, text="FPS").pack()
        self.fps_entry = tk.Entry(root)
        self.fps_entry.insert(0, "10")
        self.fps_entry.pack()

        # duration
        tk.Label(root, text="Duration (seconds)").pack()
        self.duration_entry = tk.Entry(root)
        self.duration_entry.insert(0, "5")
        self.duration_entry.pack()

        # quality scale
        tk.Label(root, text="Scale (quality multiplier)").pack()
        self.scale_entry = tk.Entry(root)
        self.scale_entry.insert(0, "2")
        self.scale_entry.pack()

        self.status = tk.Label(root, text="")
        self.status.pack(pady=10)

        tk.Button(root, text="Export PNG Sequence", command=self.start_export).pack(pady=10)

    # ---------------- FILE PICKERS ----------------
    def load_svg(self):
        self.svg_path = filedialog.askopenfilename(filetypes=[("SVG files", "*.svg")])
        if self.svg_path:
            self.svg_label.config(text=os.path.basename(self.svg_path))

    def load_folder(self):
        self.out_dir = filedialog.askdirectory()
        if self.out_dir:
            self.folder_label.config(text=self.out_dir)

    # ---------------- START EXPORT ----------------
    def start_export(self):
        if not self.svg_path or not self.out_dir:
            messagebox.showerror("Error", "Load SVG and output folder first")
            return

        threading.Thread(target=self.run_async, daemon=True).start()

    def run_async(self):
        try:
            asyncio.run(self.export_frames())
        except Exception as e:
            self.update_status(f"Error: {e}")
            print(e)

    def update_status(self, text):
        self.status.config(text=text)
        self.root.update_idletasks()

    # ---------------- EXPORT CORE ----------------
    async def export_frames(self):

        fps = int(self.fps_entry.get())
        duration = int(self.duration_entry.get())
        scale = int(self.scale_entry.get())
        name = self.name_entry.get().strip() or "frame"

        total_frames = fps * duration

        self.update_status(f"Exporting {total_frames} frames...")

        async with async_playwright() as p:

            browser = await p.chromium.launch()
            page = await browser.new_page()

            with open(self.svg_path, "r", encoding="utf-8") as f:
                svg_content = f.read()

            width, height = get_svg_size(svg_content)

            html = f"""
            <html>
            <head>
            <style>
                body {{
                    margin: 0;
                    background: transparent;
                    overflow: hidden;
                }}
                svg {{
                    width: {width}px;
                    height: {height}px;
                    transform: scale({scale});
                    transform-origin: top left;
                }}
            </style>
            </head>
            <body>
                {svg_content}
            </body>
            </html>
            """

            await page.set_content(html)

            await page.evaluate("""
                () => {
                    document.body.style.background = "transparent";
                    document.documentElement.style.background = "transparent";
                }
            """)

            await page.set_viewport_size({
                "width": width,
                "height": height
            })

            svg = await page.query_selector("svg")

            if not svg:
                self.update_status("ERROR: No SVG found")
                return

            await page.wait_for_timeout(300)

            step = 1 / fps

            for i in range(total_frames):

                await page.evaluate(f"""
                    () => {{
                        const svg = document.querySelector('svg');
                        if (svg && svg.setCurrentTime) {{
                            svg.setCurrentTime({i * step});
                        }}
                    }}
                """)

                out_path = os.path.join(
                    self.out_dir,
                    f"{name}_{i:04d}.png"
                )

                await svg.screenshot(
                    path=out_path,
                    omit_background=True
                )

                self.update_status(f"Frame {i+1}/{total_frames}")

            await browser.close()

        self.update_status("DONE!")
        messagebox.showinfo("Done", "Export complete!")


# ---------------- SAFE ENTRY POINT ----------------
if __name__ == "__main__":
    print("Launching SVG Exporter UI...")
    root = tk.Tk()
    app = SVGExporterApp(root)
    root.mainloop()