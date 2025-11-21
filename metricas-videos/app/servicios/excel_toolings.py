"""Funciones auxiliares para agregar herramientas accionables al Excel generado."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, TYPE_CHECKING, Any

from app.dominio.dtos import VideoAnaliticaDTO

if TYPE_CHECKING:
    from xlsxwriter.workbook import Workbook as WorkbookType
    from xlsxwriter.worksheet import Worksheet as WorksheetType
    from xlsxwriter.format import Format as FormatType
else:
    WorkbookType = Any  # type: ignore[misc]
    WorksheetType = Any  # type: ignore[misc]
    FormatType = Any  # type: ignore[misc]

_SHEET_TOOLINGS = "Toolings"
_BTN_CELL = "B4"


def agregar_funcionalidades_al_archivo(
    *,
    workbook: WorkbookType,
    formats: dict[str, FormatType],
    output_path: Path,
    outlier_paths: Sequence[str],
) -> None:
    """Agregar la hoja de toolings y scripts auxiliares."""
    hoja: WorksheetType = workbook.add_worksheet(_SHEET_TOOLINGS)
    hoja.freeze_panes(5, 0)

    hoja.write(0, 0, "Automatizaciones para outliers", formats["header"])
    hoja.write(
        1,
        0,
        "Se genera un script de PowerShell para mover los videos marcados como outliers hacia la carpeta Descargas del usuario actual.",
    )

    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    ps1_path = output_dir / "move_outliers.ps1"
    _generar_script_powershell(ps1_path, outlier_paths)

    if outlier_paths:
        hoja.write(
            3,
            0,
            "Haz clic en el botón para ejecutar el script y mover los archivos a Descargas.",
        )
    else:
        hoja.write(
            3,
            0,
            "No se detectaron outliers en esta corrida; generamos un script con una ruta de ejemplo para que lo ajustes y muevas los archivos que necesites.",
            formats["texto"],
        )
    hoja.insert_textbox(
        _BTN_CELL,
        "Mover videos a Descargas",
        {
            "url": ps1_path.resolve().as_uri(),
            "font": {"color": "#FFFFFF", "bold": True},
            "fill": {"color": "#2E7D32"},
            "line": {"color": "#1B5E20"},
            "align": {"horizontal": "center", "vertical": "middle"},
            "width": 260,
            "height": 40,
        },
    )

    if outlier_paths:
        hoja.write(6, 0, "Archivos outlier incluidos en el script:", formats["header"])
        hoja.write(7, 0, "archivo.ruta (origen del archivo)", formats["header"])

        for idx, ruta in enumerate(outlier_paths, start=8):
            hoja.write(idx, 0, ruta)

        hoja.write(len(outlier_paths) + 9, 0, f"Script PowerShell: {ps1_path}", formats["texto"])
    else:
        hoja.write(6, 0, f"Script PowerShell generado: {ps1_path}", formats["texto"])

    hoja.set_column(0, 0, 80)


def _generar_script_powershell(ps1_path: Path, rutas: Sequence[str] | None = None) -> None:
    rutas = list(rutas) if rutas else [r"C:\ruta\de\ejemplo\video.mp4"]
    ps1_lines = [
        "# Lista de archivos a mover (puede tener caracteres Unicode)",
        "$files = @(",
    ]
    for ruta in rutas:
        escaped = ruta.replace("\\", "\\\\").replace('"', '`"')
        ps1_lines.append(f'    "{escaped}"')
    ps1_lines.append(")")
    ps1_lines.extend(
        [
            "",
            "# Destino",
            '$dest = Join-Path $env:USERPROFILE "Downloads"',
            "",
            "foreach ($f in $files) {",
            "    # 1) Remueve invisibles comunes",
            '    $clean = $f.Trim() -replace "[\\u200B-\\u200D\\uFEFF]", ""',
            "",
            "    # 2) Normaliza Unicode (por si la carpeta fue creada con otra forma)",
            "    $clean = $clean.Normalize([Text.NormalizationForm]::FormC)",
            "",
            "    # 3) Prefijo \\\\?\\ para evitar problemas de normalización/MAX_PATH",
            '    $pref = if ($clean -like "\\\\?\\*") { $clean } else { "\\\\?\\$clean" }',
            "",
            "    # 4) Verificación fuerte con Get-Item",
            "    try {",
            "        $item = Get-Item -LiteralPath $pref -ErrorAction Stop",
            '        Write-Host "Moviendo $($item.FullName) -> $dest"',
            "        Move-Item -LiteralPath $item.FullName -Destination $dest -Force",
            "    }",
            "    catch {",
            '        Write-Warning "No se encontró o no se pudo acceder: $clean"',
            '        Write-Warning ("Detalle: " + $_.Exception.Message)',
            "",
            "        # Diagnóstico extra: imprime código Unicode de cada char",
            '        Write-Host "Debug chars:"',
            '        $chars = $clean.ToCharArray() | ForEach-Object { "{0} U+{1:X4}" -f $_, [int][char]$_ }',
            '        $chars -join " | " | Write-Host',
            "    }",
            "}",
        ]
    )
    ps1_path.write_text("\n".join(ps1_lines) + "\n", encoding="utf-8")
