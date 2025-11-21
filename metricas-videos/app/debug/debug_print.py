# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownLambdaType=false, reportReturnType=false, reportGeneralTypeIssues=false

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable

def debug_print(obj: Any, max_items: int = 3) -> None:
    """Imprime un objeto o una lista de objetos en formato JSON legible."""
    
    def convertir(item):
        if is_dataclass(item) and not isinstance(item, type):
            return asdict(item)
        if isinstance(item, (str, int, float, bool)) or item is None:
            return item
        if isinstance(item, dict):
            return item
        if hasattr(item, "__dict__"):
            return vars(item)
        return str(item)
    
    # Si es lista o tupla → mostrar primeros N
    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes, dict)):
        lista = list(obj)
        subset = lista[:max_items]
        salida = [convertir(i) for i in subset]
    else:
        salida = convertir(obj)
    
    print(json.dumps(salida, indent=2, default=str))
