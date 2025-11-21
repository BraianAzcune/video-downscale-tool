"""Valores recomendados y logica de evaluacion rapida para un video individual.

Este script define umbrales basicos para las metricas mas utiles cuando se
quiere juzgar si el peso de un video es razonable. La idea es reutilizar estas
reglas dentro de la tooling que mostrara la fila de "valores sugeridos" y la
fila de "valores del video", coloreando cada celda segun el resultado.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Mapping, Optional, Tuple, Union, Literal

Number = float
Rango = Tuple[Number, Number]
Comparacion = Literal["maximo", "minimo", "rango"]


@dataclass(frozen=True)
class Evaluacion:
    """Resultado estandarizado para una metrica."""

    clave: str
    valor: Optional[Number]
    recomendado: str
    ok: Optional[bool]
    diferencia_pct: Optional[Number]
    detalle: str


@dataclass(frozen=True)
class ReglaMetrica:
    """Describe la regla de negocio de una metrica en la tooling."""

    clave: str
    descripcion: str
    unidad: str
    comparacion: Comparacion
    recomendado: Union[Number, Rango]

    def evaluar(self, valor: Optional[Number]) -> Evaluacion:
        recomendado_txt = self.formato_recomendado()

        if valor is None:
            return Evaluacion(
                clave=self.clave,
                valor=None,
                recomendado=recomendado_txt,
                ok=None,
                diferencia_pct=None,
                detalle="sin dato",
            )

        if self.comparacion == "maximo":
            limite = float(self.recomendado)
            ok = valor <= limite
            diff_pct = _calc_diff_pct(valor, limite) if not ok and limite > 0 else 0.0
            detalle = (
                "dentro del maximo esperado"
                if ok
                else f"supera el maximo en {diff_pct:.1f}%"
            )
            return Evaluacion(self.clave, valor, recomendado_txt, ok, diff_pct, detalle)

        if self.comparacion == "minimo":
            limite = float(self.recomendado)
            ok = valor >= limite
            diff_pct = _calc_diff_pct(valor, limite) if not ok and limite > 0 else 0.0
            detalle = (
                "cumple el minimo esperado"
                if ok
                else f"queda {diff_pct:.1f}% por debajo del minimo"
            )
            return Evaluacion(self.clave, valor, recomendado_txt, ok, diff_pct, detalle)

        # comparacion == "rango"
        minimo, maximo = self._as_rango()
        if minimo <= valor <= maximo:
            return Evaluacion(
                self.clave,
                valor,
                recomendado_txt,
                True,
                0.0,
                "dentro del rango objetivo",
            )

        if valor < minimo:
            diff_pct = _calc_diff_pct(valor, minimo) if minimo > 0 else None
            detalle = (
                "por debajo del rango"
                if diff_pct is None
                else f"{diff_pct:.1f}% por debajo del minimo"
            )
            return Evaluacion(self.clave, valor, recomendado_txt, False, diff_pct, detalle)

        diff_pct = _calc_diff_pct(valor, maximo) if maximo > 0 else None
        detalle = (
            "por encima del rango"
            if diff_pct is None
            else f"{diff_pct:.1f}% por encima del maximo"
        )
        return Evaluacion(self.clave, valor, recomendado_txt, False, diff_pct, detalle)

    def formato_recomendado(self) -> str:
        if self.comparacion == "rango":
            minimo, maximo = self._as_rango()
            return f"{_fmt(minimo)} - {_fmt(maximo)} {self.unidad}".strip()

        operador = "<=" if self.comparacion == "maximo" else ">="
        return f"{operador} {_fmt(float(self.recomendado))} {self.unidad}".strip()

    def _as_rango(self) -> Rango:
        assert self.comparacion == "rango", "la regla no es de rango"
        minimo, maximo = self.recomendado  # type: ignore[misc]
        return float(minimo), float(maximo)


def _fmt(valor: Number) -> str:
    if valor.is_integer():
        return str(int(valor))
    return f"{valor:.2f}"


def _calc_diff_pct(valor: Number, referencia: Number) -> Optional[Number]:
    if referencia == 0:
        return None
    return abs(valor - referencia) / referencia * 100


def _resolver_bucket_key(bucket_id: str | None) -> Optional[str]:
    if not bucket_id:
        return None
    bucket_key = bucket_id.lower()
    if bucket_key in _HEURISTICAS_POR_BUCKET:
        return bucket_key
    base = bucket_key.split("/")[0]
    return base if base in _HEURISTICAS_POR_BUCKET else None


# Reglas base (se aplican a cualquier video si no hay una entrada especifica).
_HEURISTICAS_DEFAULT: Dict[str, ReglaMetrica] = {
    "mb_por_minuto": ReglaMetrica(
        clave="mb_por_minuto",
        descripcion="Peso relativo (MB/min)",
        unidad="MB/min",
        comparacion="rango",
        recomendado=(1.0, 8.0),
    ),
    "bits_por_pixel_frame": ReglaMetrica(
        clave="bits_por_pixel_frame",
        descripcion="Bits por pixel por frame (eficiencia del video)",
        unidad="bppf",
        comparacion="rango",
        recomendado=(0.02, 0.12),
    ),
    "kbps_total": ReglaMetrica(
        clave="kbps_total",
        descripcion="Bitrate total legible",
        unidad="kbps",
        comparacion="rango",
        recomendado=(500, 8000),
    ),
    "audio_share_pct": ReglaMetrica(
        clave="audio_share_pct",
        descripcion="Porcentaje de bitrate aportado por el audio",
        unidad="%",
        comparacion="maximo",
        recomendado=40,
    ),
    "ratio_vs_promedio_bucket": ReglaMetrica(
        clave="ratio_vs_promedio_bucket",
        descripcion="Relacion frente al bucket",
        unidad="x",
        comparacion="rango",
        recomendado=(0.7, 1.3),
    ),
}


_HEURISTICAS_POR_BUCKET: Dict[str, Dict[str, ReglaMetrica]] = {
    "360p@30": {
        "mb_por_minuto": replace(
            _HEURISTICAS_DEFAULT["mb_por_minuto"], recomendado=(0.8, 2.5)
        ),
        "kbps_total": replace(
            _HEURISTICAS_DEFAULT["kbps_total"], recomendado=(400, 1200)
        ),
        "bits_por_pixel_frame": replace(
            _HEURISTICAS_DEFAULT["bits_por_pixel_frame"], recomendado=(0.015, 0.06)
        ),
    },
    "480p@30": {
        "mb_por_minuto": replace(
            _HEURISTICAS_DEFAULT["mb_por_minuto"], recomendado=(1.2, 3.5)
        ),
        "kbps_total": replace(
            _HEURISTICAS_DEFAULT["kbps_total"], recomendado=(700, 2000)
        ),
        "bits_por_pixel_frame": replace(
            _HEURISTICAS_DEFAULT["bits_por_pixel_frame"], recomendado=(0.02, 0.08)
        ),
    },
    "720p@30": {
        "mb_por_minuto": replace(
            _HEURISTICAS_DEFAULT["mb_por_minuto"], recomendado=(2.0, 5.0)
        ),
        "kbps_total": replace(
            _HEURISTICAS_DEFAULT["kbps_total"], recomendado=(1200, 3500)
        ),
        "bits_por_pixel_frame": replace(
            _HEURISTICAS_DEFAULT["bits_por_pixel_frame"], recomendado=(0.03, 0.1)
        ),
    },
    "1080p@30": {
        "mb_por_minuto": replace(
            _HEURISTICAS_DEFAULT["mb_por_minuto"], recomendado=(3.5, 8.5)
        ),
        "kbps_total": replace(
            _HEURISTICAS_DEFAULT["kbps_total"], recomendado=(2500, 6000)
        ),
        "bits_por_pixel_frame": replace(
            _HEURISTICAS_DEFAULT["bits_por_pixel_frame"], recomendado=(0.04, 0.12)
        ),
    },
    "1080p@60": {
        "mb_por_minuto": replace(
            _HEURISTICAS_DEFAULT["mb_por_minuto"], recomendado=(5.0, 10.0)
        ),
        "kbps_total": replace(
            _HEURISTICAS_DEFAULT["kbps_total"], recomendado=(3500, 8000)
        ),
        "bits_por_pixel_frame": replace(
            _HEURISTICAS_DEFAULT["bits_por_pixel_frame"], recomendado=(0.05, 0.14)
        ),
    },
    "2160p@30": {
        "mb_por_minuto": replace(
            _HEURISTICAS_DEFAULT["mb_por_minuto"], recomendado=(8.0, 20.0)
        ),
        "kbps_total": replace(
            _HEURISTICAS_DEFAULT["kbps_total"], recomendado=(8000, 20000)
        ),
        "bits_por_pixel_frame": replace(
            _HEURISTICAS_DEFAULT["bits_por_pixel_frame"], recomendado=(0.06, 0.16)
        ),
    },
}


def obtener_reglas(bucket_id: str | None = None) -> Dict[str, ReglaMetrica]:
    """Retornar las reglas aplicables para el bucket indicado (o las default)."""
    reglas = dict(_HEURISTICAS_DEFAULT)
    bucket_key = _resolver_bucket_key(bucket_id)
    if bucket_key:
        reglas.update(_HEURISTICAS_POR_BUCKET[bucket_key])
    return reglas


def evaluar_metricas(
    metricas: Mapping[str, Optional[Number]],
    bucket_id: str | None = None,
) -> Dict[str, Evaluacion]:
    """Evaluar un set de metricas contra las reglas del bucket."""
    reglas = obtener_reglas(bucket_id)
    return {clave: regla.evaluar(metricas.get(clave)) for clave, regla in reglas.items()}


if __name__ == "__main__":
    # Ejemplo rapido para validar la logica sin depender del resto del proyecto.
    demo_metricas = {
        "mb_por_minuto": 3.1,
        "bits_por_pixel_frame": 0.018,
        "kbps_total": 1850,
        "audio_share_pct": 37,
        "ratio_vs_promedio_bucket": 1.25,
    }
    resultados = evaluar_metricas(demo_metricas, bucket_id="480p@30/H264")
    for clave, evaluacion in resultados.items():
        estado = "SIN DATO" if evaluacion.ok is None else ("OK" if evaluacion.ok else "WARN")
        print(
            f"{clave:25s} | estado={estado:8s} | valor={evaluacion.valor} | recomendado={evaluacion.recomendado} | detalle={evaluacion.detalle}"
        )
