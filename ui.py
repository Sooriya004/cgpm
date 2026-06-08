from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from renamer import plan_renames, rename_files_with_prefix


class FileRenamerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("File Renamer")
        self.geometry("760x560")
        self.minsize(700, 500)

        self.folder_var = tk.StringVar()
        self.source_prefix_var = tk.StringVar()
        self.target_prefix_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.time_var = tk.StringVar(value="Elapsed: 00:00:00 | ETA: --:--:--")
        self.progress_var = tk.DoubleVar(value=0)

        self._worker_queue: queue.Queue[tuple] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._current_total = 0
        self._last_elapsed = 0.0

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.folder_var, width=60).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8)
        )
        ttk.Button(container, text="Browse", command=self._browse_folder).grid(row=1, column=2, sticky="ew")

        ttk.Label(container, text="Current prefix").grid(row=2, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(container, textvariable=self.source_prefix_var).grid(row=3, column=0, columnspan=3, sticky="ew")

        ttk.Label(container, text="New prefix").grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(container, textvariable=self.target_prefix_var).grid(row=5, column=0, columnspan=3, sticky="ew")

        button_row = ttk.Frame(container)
        button_row.grid(row=6, column=0, columnspan=3, sticky="ew", pady=12)
        self.preview_button = ttk.Button(button_row, text="Preview", command=self._preview)
        self.preview_button.pack(side="left")
        self.rename_button = ttk.Button(button_row, text="Rename", command=self._rename)
        self.rename_button.pack(side="left", padx=8)

        ttk.Label(container, textvariable=self.status_var).grid(row=7, column=0, sticky="w")
        self.progress_bar = ttk.Progressbar(container, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(6, 2))
        ttk.Label(container, textvariable=self.time_var).grid(row=9, column=0, sticky="w")

        ttk.Label(container, text="Preview / status").grid(row=10, column=0, sticky="w", pady=(12, 0))
        self.output = tk.Text(container, height=16, wrap="word")
        self.output.grid(row=11, column=0, columnspan=3, sticky="nsew", pady=(6, 0))

        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=0)
        container.columnconfigure(2, weight=0)
        container.rowconfigure(11, weight=1)

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _log(self, message: str) -> None:
        self.output.insert("end", f"{message}\n")
        self.output.see("end")

    def _clear_output(self) -> None:
        self.output.delete("1.0", "end")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.preview_button.configure(state=state)
        self.rename_button.configure(state=state)

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        if seconds is None:
            return "--:--:--"
        total_seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _preview(self) -> None:
        self._clear_output()
        try:
            plan = plan_renames(
                self.folder_var.get(),
                self.source_prefix_var.get(),
                self.target_prefix_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Preview failed", str(exc))
            return

        if not plan.items:
            self._log("No matching files found.")
            return

        self.status_var.set(f"Previewing {len(plan.items)} file(s)")
        for item in plan.items:
            self._log(f"{item.source.name} -> {item.destination.name}")

    def _rename(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            messagebox.showinfo("Busy", "A rename operation is already running.")
            return

        self._clear_output()
        try:
            plan = plan_renames(
                self.folder_var.get(),
                self.source_prefix_var.get(),
                self.target_prefix_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Rename failed", str(exc))
            return

        if not plan.items:
            self._log("No matching files found.")
            return

        self.progress_var.set(0)
        self._current_total = len(plan.items)
        self._last_elapsed = 0.0
        self.progress_bar.configure(maximum=max(1, self._current_total))
        self.status_var.set("Starting rename...")
        self.time_var.set("Elapsed: 00:00:00 | ETA: calculating...")
        self._set_busy(True)

        self._worker_thread = threading.Thread(
            target=self._run_worker,
            args=(
                self.folder_var.get(),
                self.source_prefix_var.get(),
                self.target_prefix_var.get(),
            ),
            daemon=True,
        )
        self._worker_thread.start()
        self.after(100, self._poll_worker_queue)

    def _run_worker(self, folder: str, source_prefix: str, target_prefix: str) -> None:
        def progress_callback(done: int, total: int, item, elapsed: float, eta: float | None) -> None:
            self._worker_queue.put(("progress", done, total, item, elapsed, eta))

        try:
            result = rename_files_with_prefix(
                folder,
                source_prefix,
                target_prefix,
                progress_callback=progress_callback,
            )
        except Exception as exc:
            self._worker_queue.put(("error", str(exc)))
            return

        self._worker_queue.put(("done", result))

    def _poll_worker_queue(self) -> None:
        while True:
            try:
                message = self._worker_queue.get_nowait()
            except queue.Empty:
                break

            kind = message[0]
            if kind == "progress":
                _, done, total, item, elapsed, eta = message
                self._last_elapsed = elapsed
                self.progress_var.set(done)
                self.status_var.set(f"Processing {done}/{total} file(s)")
                self.time_var.set(
                    f"Elapsed: {self._format_duration(elapsed)} | ETA: {self._format_duration(eta)}"
                )
                self._log(f"{item.source.name} -> {item.destination.name}")
            elif kind == "done":
                _, result = message
                self.progress_var.set(self._current_total)
                self.status_var.set("Complete")
                self.time_var.set(
                    f"Elapsed: {self._format_duration(self._last_elapsed)} | ETA: 00:00:00"
                )
                self._log("Rename complete.")
                self._log(f"Planned: {len(result.planned)}")
                self._log(f"Renamed: {len(result.renamed)}")
                for error in result.errors:
                    self._log(f"ERROR: {error}")
                self._set_busy(False)
                self._worker_thread = None
                return
            elif kind == "error":
                _, error_message = message
                messagebox.showerror("Rename failed", error_message)
                self.status_var.set("Failed")
                self.time_var.set("Elapsed: --:--:-- | ETA: --:--:--")
                self._set_busy(False)
                self._worker_thread = None
                return

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self.after(100, self._poll_worker_queue)
        else:
            self._set_busy(False)
            self._worker_thread = None


def run() -> None:
    app = FileRenamerApp()
    app.mainloop()
