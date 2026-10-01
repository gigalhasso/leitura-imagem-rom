from __future__ import annotations

import re
import shutil
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Literal

from edit_drop_count import (
    DropCountLayoutError,
    inspect_drop_count,
    patch_drop_count,
    write_atomically,
    write_with_backup,
)
from psx_iso import PsxIso


APP_NAME = "Yu-Gi-Oh! FM Drop Editor"
DROP_OPTIONS = (1, 5, 15)
DROP_SUFFIX_RE = re.compile(r"\s*\(Drop\s*x(?:1|5|15)\)$", re.IGNORECASE)
CUE_FILE_RE = re.compile(r'^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+BINARY\s*$', re.IGNORECASE)


class UnsupportedInputError(ValueError):
    pass


@dataclass(frozen=True)
class InputTarget:
    selected_path: Path
    data_path: Path
    kind: Literal["wa_mrg", "disc_image"]
    current_count: int
    format_label: str
    cue_path: Path | None = None


@dataclass(frozen=True)
class SaveResult:
    output_path: Path
    count: int
    changed_bytes: int
    changed_sectors: int | None = None
    backup_path: Path | None = None
    cue_path: Path | None = None


def _read_text(path: Path) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Nao foi possivel decodificar o CUE: {path}")


def resolve_cue(cue_path: Path) -> Path:
    text, _ = _read_text(cue_path)
    matches = []
    for line in text.splitlines():
        match = CUE_FILE_RE.match(line)
        if match:
            matches.append(match.group(1) or match.group(2))
    if len(matches) != 1:
        raise ValueError(
            f"O CUE precisa apontar para exatamente uma imagem BINARY; encontrei {len(matches)}."
        )
    image_path = (cue_path.parent / matches[0]).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Imagem referenciada pelo CUE nao encontrada: {image_path}")
    return image_path


def find_companion_cue(image_path: Path) -> Path | None:
    candidates = [
        path
        for path in image_path.parent.iterdir()
        if path.is_file() and path.suffix.casefold() == ".cue" and path.stem.casefold() == image_path.stem.casefold()
    ]
    return candidates[0] if len(candidates) == 1 else None


def add_drop_suffix(path: Path, count: int) -> Path:
    base = DROP_SUFFIX_RE.sub("", path.stem).rstrip()
    return path.with_name(f"{base} (Drop x{count}){path.suffix}")


def inspect_input(selected_path: Path) -> InputTarget:
    selected_path = selected_path.expanduser().resolve()
    if not selected_path.is_file():
        raise FileNotFoundError(f"Arquivo nao encontrado: {selected_path}")

    cue_path: Path | None = None
    data_path = selected_path
    if selected_path.suffix.casefold() == ".cue":
        cue_path = selected_path
        data_path = resolve_cue(selected_path)

    image_error: Exception | None = None
    try:
        with PsxIso(data_path) as iso:
            entry = iso.find_file("DATA/WA_MRG.MRG")
            wa_mrg = iso.read_file(entry.lba, entry.size)
            state = inspect_drop_count(wa_mrg)
            layout = iso.layout
        if cue_path is None:
            cue_path = find_companion_cue(data_path)
        raw_label = (
            "RAW Mode 2/Form 1 (2352 bytes/setor)"
            if layout.sector_size == 2352
            else "ISO 2048 bytes/setor"
        )
        return InputTarget(
            selected_path=selected_path,
            data_path=data_path,
            kind="disc_image",
            current_count=state.count,
            format_label=f"Imagem de disco - {raw_label}",
            cue_path=cue_path,
        )
    except (DropCountLayoutError, FileNotFoundError):
        raise
    except Exception as error:
        image_error = error

    try:
        data = data_path.read_bytes()
        state = inspect_drop_count(data)
        return InputTarget(
            selected_path=selected_path,
            data_path=data_path,
            kind="wa_mrg",
            current_count=state.count,
            format_label="WA_MRG.MRG extraido",
        )
    except Exception as wa_error:
        raise UnsupportedInputError(
            "Formato nao reconhecido ou patch multidrop Ghost ausente. "
            f"Imagem: {image_error}. WA_MRG: {wa_error}"
        ) from wa_error


def _copy_cue(source_cue: Path, destination_image: Path) -> Path:
    text, encoding = _read_text(source_cue)
    replaced = 0
    output_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if CUE_FILE_RE.match(line.rstrip("\r\n")) and replaced == 0:
            newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            output_lines.append(f'FILE "{destination_image.name}" BINARY{newline}')
            replaced += 1
        else:
            output_lines.append(line)
    if replaced != 1:
        raise ValueError("Nao foi possivel atualizar a linha FILE do CUE.")
    destination_cue = destination_image.with_suffix(".cue")
    destination_cue.write_text("".join(output_lines), encoding=encoding)
    return destination_cue


def _image_backup_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.drop-count.bak{path.suffix}")


def _ensure_image_backup(path: Path) -> tuple[Path, bool]:
    backup = _image_backup_path(path)
    if backup.exists():
        if not backup.is_file() or backup.stat().st_size != path.stat().st_size:
            raise ValueError(f"Backup existente invalido: {backup}")
        inspect_input(backup)
        return backup, False
    shutil.copy2(path, backup)
    return backup, True


def _replace_wa_in_image(image_path: Path, wa_mrg: bytes, expected_count: int) -> int:
    with PsxIso(image_path, writable=True) as iso:
        _, changed_sectors = iso.replace_file("DATA/WA_MRG.MRG", wa_mrg)
    verified = inspect_input(image_path)
    if verified.current_count != expected_count:
        raise RuntimeError(
            f"Verificacao falhou: esperado x{expected_count}, lido x{verified.current_count}"
        )
    return changed_sectors


def save_drop_count(
    target: InputTarget,
    count: int,
    mode: Literal["copy", "replace"],
    destination: Path | None = None,
) -> SaveResult:
    if count not in DROP_OPTIONS:
        raise ValueError(f"Quantidade nao suportada pela interface: {count}")
    if mode not in ("copy", "replace"):
        raise ValueError(f"Modo de salvamento invalido: {mode}")

    if target.kind == "wa_mrg":
        original = target.data_path.read_bytes()
        patched, _ = patch_drop_count(original, count)
        changed_bytes = sum(left != right for left, right in zip(original, patched))
        if mode == "copy":
            if destination is None:
                raise ValueError("O destino da copia nao foi informado.")
            destination = destination.resolve()
            if destination == target.data_path:
                raise ValueError("A copia precisa ter um caminho diferente do original.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            write_atomically(destination, patched)
            output_path = destination
            backup_path = None
        else:
            output_path = target.data_path
            backup_path, _ = write_with_backup(output_path, patched)

        saved = inspect_input(output_path)
        if saved.current_count != count:
            raise RuntimeError("A verificacao do WA_MRG salvo falhou.")
        return SaveResult(output_path, count, changed_bytes, backup_path=backup_path)

    with PsxIso(target.data_path) as iso:
        entry = iso.find_file("DATA/WA_MRG.MRG")
        original_wa = iso.read_file(entry.lba, entry.size)
    patched_wa, _ = patch_drop_count(original_wa, count)
    changed_bytes = sum(left != right for left, right in zip(original_wa, patched_wa))

    cue_output: Path | None = None
    backup_path: Path | None = None
    if mode == "copy":
        if destination is None:
            raise ValueError("O destino da copia nao foi informado.")
        output_path = destination.resolve()
        if output_path == target.data_path:
            raise ValueError("A copia precisa ter um caminho diferente do original.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target.data_path, output_path)
        try:
            changed_sectors = _replace_wa_in_image(output_path, patched_wa, count)
            if target.cue_path is not None:
                cue_output = _copy_cue(target.cue_path, output_path)
        except Exception:
            output_path.unlink(missing_ok=True)
            if cue_output is not None:
                cue_output.unlink(missing_ok=True)
            raise
    else:
        output_path = target.data_path
        backup_path, _ = _ensure_image_backup(output_path)
        try:
            changed_sectors = _replace_wa_in_image(output_path, patched_wa, count)
        except Exception:
            try:
                _replace_wa_in_image(output_path, original_wa, target.current_count)
            except Exception:
                pass
            raise

    return SaveResult(
        output_path=output_path,
        count=count,
        changed_bytes=changed_bytes,
        changed_sectors=changed_sectors,
        backup_path=backup_path,
        cue_path=cue_output,
    )


class DropEditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.target: InputTarget | None = None
        self.file_var = tk.StringVar(value="Nenhum arquivo selecionado")
        self.format_var = tk.StringVar(value="-")
        self.current_var = tk.StringVar(value="-")
        self.count_var = tk.IntVar(value=15)
        self.mode_var = tk.StringVar(value="copy")
        self.status_var = tk.StringVar(value="Selecione um arquivo para comecar.")

        root.title(APP_NAME)
        root.geometry("680x480")
        root.minsize(620, 440)
        root.configure(background="#f3f5f8")
        self._build_style()
        self._build_ui()

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20), foreground="#172033")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#5d687d")
        style.configure("Info.TLabel", font=("Segoe UI Semibold", 10), foreground="#24324a")
        style.configure("Action.TButton", font=("Segoe UI Semibold", 11), padding=(16, 10))
        style.configure("Choice.TRadiobutton", font=("Segoe UI Semibold", 11), padding=8)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Altere com seguranca a quantidade de cartas recebidas por duelo.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 18))

        file_frame = ttk.LabelFrame(outer, text="1. Arquivo", padding=14)
        file_frame.pack(fill="x")
        ttk.Label(file_frame, textvariable=self.file_var, wraplength=540).grid(
            row=0, column=0, sticky="w"
        )
        self.select_button = ttk.Button(file_frame, text="Selecionar...", command=self._select_file)
        self.select_button.grid(row=0, column=1, padx=(12, 0))
        file_frame.columnconfigure(0, weight=1)
        ttk.Label(file_frame, text="Formato:", style="Info.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(file_frame, textvariable=self.format_var).grid(row=1, column=0, sticky="w", padx=(72, 0), pady=(10, 0))
        ttk.Label(file_frame, text="Drop atual:", style="Info.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Label(file_frame, textvariable=self.current_var).grid(row=2, column=0, sticky="w", padx=(82, 0), pady=(4, 0))

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=14)
        count_frame = ttk.LabelFrame(options, text="2. Nova quantidade", padding=12)
        count_frame.pack(side="left", fill="both", expand=True, padx=(0, 7))
        for count in DROP_OPTIONS:
            ttk.Radiobutton(
                count_frame,
                text=f"{count}x",
                value=count,
                variable=self.count_var,
                style="Choice.TRadiobutton",
            ).pack(side="left", expand=True)

        mode_frame = ttk.LabelFrame(options, text="3. Salvamento", padding=12)
        mode_frame.pack(side="left", fill="both", expand=True, padx=(7, 0))
        ttk.Radiobutton(mode_frame, text="Salvar como copia", value="copy", variable=self.mode_var).pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="Substituir original", value="replace", variable=self.mode_var).pack(anchor="w", pady=(5, 0))
        ttk.Label(mode_frame, text="Ao substituir, um backup e criado.", style="Subtitle.TLabel").pack(anchor="w", pady=(5, 0))

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(2, 8))
        ttk.Label(outer, textvariable=self.status_var, style="Subtitle.TLabel", wraplength=620).pack(anchor="w")
        self.apply_button = ttk.Button(
            outer, text="Aplicar alteracao", style="Action.TButton", command=self._apply, state="disabled"
        )
        self.apply_button.pack(anchor="e", pady=(16, 0))

    def _set_busy(self, busy: bool, status: str) -> None:
        self.status_var.set(status)
        state = "disabled" if busy else "normal"
        self.select_button.configure(state=state)
        self.apply_button.configure(state="disabled" if busy or self.target is None else "normal")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _run_background(self, status: str, work, on_success) -> None:
        self._set_busy(True, status)

        def runner() -> None:
            try:
                result = work()
            except Exception as error:
                self.root.after(0, lambda error=error: self._on_error(error))
            else:
                self.root.after(0, lambda: on_success(result))

        threading.Thread(target=runner, daemon=True).start()

    def _on_error(self, error: Exception) -> None:
        self._set_busy(False, f"Erro: {error}")
        messagebox.showerror(APP_NAME, str(error), parent=self.root)

    def _select_file(self) -> None:
        chosen = filedialog.askopenfilename(
            parent=self.root,
            title="Selecione a imagem ou WA_MRG.MRG",
            filetypes=[
                ("Formatos suportados", "*.iso *.bin *.cue *.mrg"),
                ("Imagens de disco", "*.iso *.bin *.cue"),
                ("WA_MRG.MRG", "*.mrg"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not chosen:
            return
        path = Path(chosen)
        self._run_background("Analisando arquivo...", lambda: inspect_input(path), self._loaded)

    def _loaded(self, target: InputTarget) -> None:
        self.target = target
        self.file_var.set(str(target.selected_path))
        self.format_var.set(target.format_label)
        self.current_var.set(f"{target.current_count}x")
        self.count_var.set(15 if target.current_count != 15 else 5)
        self._set_busy(False, "Arquivo compativel. Escolha a quantidade e o modo de salvamento.")

    def _apply(self) -> None:
        if self.target is None:
            return
        target = self.target
        count = self.count_var.get()
        mode = self.mode_var.get()
        destination: Path | None = None
        if mode == "copy":
            suggested = add_drop_suffix(target.data_path, count)
            chosen = filedialog.asksaveasfilename(
                parent=self.root,
                title="Salvar copia",
                initialdir=str(suggested.parent),
                initialfile=suggested.name,
                defaultextension=target.data_path.suffix,
                filetypes=[("Mesmo formato do original", f"*{target.data_path.suffix}"), ("Todos", "*.*")],
            )
            if not chosen:
                return
            destination = Path(chosen)
        else:
            if not messagebox.askyesno(
                APP_NAME,
                f"Substituir o original por Drop x{count}?\n\nUm backup sera criado antes da alteracao.",
                parent=self.root,
            ):
                return

        self._run_background(
            "Copiando e validando; isso pode levar alguns segundos...",
            lambda: save_drop_count(target, count, mode, destination),
            self._saved,
        )

    def _saved(self, result: SaveResult) -> None:
        details = [
            f"Drop alterado para x{result.count}.",
            f"Arquivo: {result.output_path}",
            f"Bytes de configuracao alterados: {result.changed_bytes}",
        ]
        if result.changed_sectors is not None:
            details.append(f"Setores da imagem alterados: {result.changed_sectors}")
        if result.cue_path is not None:
            details.append(f"CUE criado: {result.cue_path}")
        if result.backup_path is not None:
            details.append(f"Backup: {result.backup_path}")
        text = "\n".join(details)
        self.target = inspect_input(result.output_path)
        self.file_var.set(str(result.output_path))
        self.format_var.set(self.target.format_label)
        self.current_var.set(f"{self.target.current_count}x")
        self._set_busy(False, "Alteracao concluida e verificada.")
        messagebox.showinfo(APP_NAME, text, parent=self.root)


def self_test(paths: list[str]) -> int:
    try:
        if not paths:
            raise ValueError("Informe ao menos um arquivo para o self-test.")
        for value in paths:
            target = inspect_input(Path(value))
            if target.current_count not in DROP_OPTIONS:
                raise AssertionError(f"Contagem inesperada: {target.current_count}")
        return 0
    except Exception:
        return 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        return self_test(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--gui-smoke-test":
        root = tk.Tk()
        root.withdraw()
        DropEditorApp(root)
        root.update_idletasks()
        root.update()
        root.destroy()
        return 0
    root = tk.Tk()
    DropEditorApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
