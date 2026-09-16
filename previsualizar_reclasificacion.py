"""Genera un reporte de reclasificación sin modificar Google Sheets."""

from clasificacion import crear_vista_previa
from sheets import obtener_movimientos


def main():
    vista = crear_vista_previa(obtener_movimientos())
    print("VISTA PREVIA DE RECLASIFICACIÓN")
    print("Modo: sólo lectura; no se modificarán filas.")
    print(f"Filas analizadas: {vista['total']}")
    print("\nPor confianza:")
    for confianza, cantidad in vista["por_confianza"].items():
        print(f"- {confianza}: {cantidad}")
    print("\nPropuesta por rubro:")
    for categoria, cantidad in vista["por_categoria"].items():
        print(f"- {categoria}: {cantidad}")


if __name__ == "__main__":
    main()
