from rich.console import Console, Group
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.live import Live
from rich.panel import Panel
from random import randint, choice
from time import sleep, time

console = Console()

# Estados y colores usados
status_colors = {
    "pending": "grey23",
    "active": "white",
    "success": "green",
    "warning": "yellow",
    "error": "red",
}

# Estado final aleatorio sin "critical"
def get_final_status():
    return choice(["success", "warning", "error"])

# Dibuja un cuadrado coloreado
def status_block(color):
    return f"[{color}]■[/]"

# Cantidad de tareas
NUM_TAREAS = 100
estados = ["pending"] * NUM_TAREAS
start_time = time()

# Barra de progreso individual
progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(bar_width=None),
    TextColumn("{task.percentage:>3.0f}%"),
    TimeRemainingColumn(),
)

task_id = None
finalizado = False

# Renderiza la vista completa
def render(actual_index):
    # 1️⃣ Línea de cuadrados
    linea_cuadrados = "".join(
        status_block(
            status_colors[estados[i]] if i != actual_index else status_colors["active"]
        )
        for i in range(NUM_TAREAS)
    )
    header = Panel(linea_cuadrados, title="Progreso General", expand=False)

    # 2️⃣ Línea resumen
    resumen = Table.grid(padding=(0, 2))
    resumen.add_column(justify="left")
    resumen.add_column(justify="right")

    tiempo_total = int(time() - start_time)
    tiempo_fmt = f"{tiempo_total // 60:02}:{tiempo_total % 60:02}"

    conteo = {
        "success": estados.count("success"),
        "warning": estados.count("warning"),
        "error": estados.count("error"),
        "pending": estados.count("pending"),
    }

    resumen.add_row("🕒 Tiempo transcurrido:", tiempo_fmt)
    resumen.add_row("✅ Completadas (verde):", str(conteo["success"]))
    resumen.add_row("⚠️  Advertencias (amarillo):", str(conteo["warning"]))
    resumen.add_row("🟥 Errores (rojo):", str(conteo["error"]))
    resumen.add_row("⬜ Pendientes:", str(conteo["pending"]))

    panel_resumen = Panel(resumen, title="Resumen", expand=False)

    # 3️⃣ Línea final: barra o mensaje
    if finalizado:
        linea_final = Panel("[bold green]✔ Todos los procesos finalizaron[/bold green]", expand=False)
    elif actual_index < NUM_TAREAS:
        linea_final = progress
    else:
        linea_final = ""

    return Group(header, panel_resumen, linea_final)

# Proceso principal
with Live(render(0), refresh_per_second=10, console=console) as live:
    for i in range(NUM_TAREAS):
        estados[i] = "active"
        task_id = progress.add_task(f"Tarea {i+1}", total=100)

        while not progress.finished:
            progress.update(task_id, advance=randint(2, 5))
            live.update(render(i))
            sleep(0.05)

        estados[i] = get_final_status()
        progress.remove_task(task_id)
        live.update(render(i + 1))

    finalizado = True
    live.update(render(NUM_TAREAS))
