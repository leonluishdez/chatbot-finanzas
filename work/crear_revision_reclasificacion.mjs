import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "/Users/luisleon/Documents/Codex/2026-09-15/referenced-chatgpt-conversation-this-is-an/outputs";
const data = JSON.parse(await fs.readFile("work/grupos_por_revisar.json", "utf8"));
const rows = data.filas;
const rubros = [
  "Ahorro y retiro",
  "Comida a domicilio",
  "Comisiones e intereses",
  "Compras de terceros",
  "Compras personales",
  "Educación",
  "Entretenimiento",
  "Hogar",
  "Préstamos y deudas",
  "Regalos",
  "Restaurantes y comida",
  "Salud y cuidado personal",
  "Seguros y protección",
  "Servicios y compromisos familiares",
  "Sin identificar",
  "Supermercado",
  "Suscripciones",
  "Reembolsos recibidos",
  "Transporte",
  "Viajes",
  "Vivienda y servicios",
];

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Revisión");
const catalogo = workbook.worksheets.add("Rubros");
sheet.showGridLines = false;
catalogo.showGridLines = false;

sheet.getRange("A1:E1").merge();
sheet.getRange("A1").values = [["Revisión de rubros pendientes"]];
sheet.getRange("A2:E2").merge();
sheet.getRange("A2").values = [[`Cada fila reúne movimientos con la misma descripción. Elige un rubro en la columna D; no cambies las demás columnas. ${data.sinDescripcion} movimientos sin descripción quedaron fuera porque no es seguro clasificarlos en bloque.`]];
sheet.getRange("A4:E4").values = [["Descripción", "Movimientos", "Cuentas", "Rubro elegido", "Nota"]];
sheet.getRangeByIndexes(4, 0, rows.length, 5).values = rows.map((row) => [
  row.descripcion,
  row.movimientos,
  row.cuentas,
  row.rubro_propuesto,
  row.nota,
]);

catalogo.getRange("A1").values = [["Rubros disponibles"]];
catalogo.getRangeByIndexes(1, 0, rubros.length, 1).values = rubros.map((rubro) => [rubro]);

sheet.getRange("A1:E1").format = {
  fill: "#17324D",
  font: { bold: true, color: "#FFFFFF", size: 14 },
  horizontalAlignment: "left",
  verticalAlignment: "center",
};
sheet.getRange("A2:E2").format = {
  font: { italic: true, color: "#4A5568", size: 10 },
  wrapText: true,
  verticalAlignment: "center",
};
sheet.getRange("A4:E4").format = {
  fill: "#244A68",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#D9E2F3" },
};
sheet.getRangeByIndexes(4, 0, rows.length, 5).format = {
  verticalAlignment: "center",
  borders: { preset: "insideHorizontal", style: "thin", color: "#E2E8F0" },
};
sheet.getRangeByIndexes(4, 3, rows.length, 1).format = { fill: "#FFF2CC" };
sheet.getRangeByIndexes(4, 1, rows.length, 1).setNumberFormat("#,##0");
sheet.getRange("A:A").format.columnWidth = 34;
sheet.getRange("B:B").format.columnWidth = 12;
sheet.getRange("C:C").format.columnWidth = 24;
sheet.getRange("D:D").format.columnWidth = 30;
sheet.getRange("E:E").format.columnWidth = 34;
sheet.getRange("A1:E1").format.rowHeight = 28;
sheet.getRange("A2:E2").format.rowHeight = 34;
sheet.getRange("A4:E4").format.rowHeight = 24;
sheet.getRangeByIndexes(4, 3, rows.length, 1).dataValidation = {
  rule: { type: "list", formula1: `Rubros!$A$2:$A$${rubros.length + 1}` },
};
sheet.freezePanes.freezeRows(4);

catalogo.getRange("A1").format = {
  fill: "#244A68",
  font: { bold: true, color: "#FFFFFF" },
};
catalogo.getRange("A:A").format.columnWidth = 34;

workbook.recalculate();
const check = await workbook.inspect({
  kind: "table",
  range: "Revisión!A1:E10",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 5,
});
console.log(check.ndjson);
const preview = await workbook.render({ sheetName: "Revisión", range: "A1:E18", scale: 1.5 });
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(`${outputDir}/revision-rubros-pendientes.png`, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/revision-rubros-pendientes.xlsx`);
