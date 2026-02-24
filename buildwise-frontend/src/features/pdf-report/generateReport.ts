import type { StrategyComparison, EnergyResult } from "@/api/client";
import {
  STRATEGY_LABELS,
  STRATEGY_DESCRIPTIONS,
} from "@/constants/strategies";

/* ─── Types ─── */
type jsPDFType = import("jspdf").jsPDF;
type AutoTableFn = (doc: jsPDFType, options: object) => void;

export interface ReportOptions {
  comparison: StrategyComparison;
  allStrategies: EnergyResult[];
  chartContainer: HTMLDivElement;
}

/* ─── Layout constants ─── */
const PW = 210; // A4 width mm
const PH = 297; // A4 height mm
const ML = 15; // margin left
const MR = 15;
const MT = 20;
const MB = 20;
const CW = PW - ML - MR; // content width = 180mm

const BLUE = "#2563EB";
const DARK = "#1F2937";
const GRAY = "#6B7280";
const LIGHT = "#F3F4F6";
const GREEN = "#059669";

/* ─── Main export ─── */
export async function generateReport(opts: ReportOptions): Promise<void> {
  const { comparison, allStrategies, chartContainer } = opts;

  // Lazy-load libraries
  const [{ default: jsPDF }, html2canvasModule, { autoTable }] = await Promise.all([
    import("jspdf"),
    import("html2canvas"),
    import("jspdf-autotable"), // v5: named export, not prototype patch
  ]);
  const html2canvas = html2canvasModule.default;

  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

  // Capture all charts as images
  const charts = await captureCharts(chartContainer, html2canvas);

  // Build pages
  drawCover(doc, comparison, allStrategies);

  doc.addPage();
  drawSummary(doc, comparison, allStrategies, charts.eui);

  if (charts.breakdown || charts.radar) {
    doc.addPage();
    drawAnalysis(doc, charts.breakdown, charts.radar);
  }

  if (charts.cost || charts.monthly) {
    doc.addPage();
    drawCostMonthly(doc, charts.cost, charts.monthly);
  }

  doc.addPage();
  drawTable(doc, comparison, allStrategies, autoTable as AutoTableFn);

  // Footer on every page
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    drawPageFooter(doc, i, totalPages, allStrategies.some((s) => s.is_mock));
  }

  // Save
  const dateStr = new Date().toISOString().slice(0, 10);
  const safeName = comparison.building_name.replace(/[^a-zA-Z0-9_-]/g, "-");
  doc.save(`BuildWise-Report-${safeName}-${dateStr}.pdf`);
}

/* ─── Chart capture ─── */
interface ChartImages {
  eui: string | null;
  breakdown: string | null;
  cost: string | null;
  radar: string | null;
  monthly: string | null;
}

async function captureCharts(
  container: HTMLDivElement,
  html2canvas: (el: HTMLElement, opts?: object) => Promise<HTMLCanvasElement>,
): Promise<ChartImages> {
  const keys = ["eui", "breakdown", "cost", "radar", "monthly"] as const;
  const images: ChartImages = { eui: null, breakdown: null, cost: null, radar: null, monthly: null };

  for (const key of keys) {
    const el = container.querySelector(`[data-chart="${key}"]`) as HTMLElement | null;
    if (!el) continue;
    const canvas = await html2canvas(el, {
      scale: 2,
      backgroundColor: "#ffffff",
      logging: false,
      useCORS: true,
    });
    images[key] = canvas.toDataURL("image/png");
  }

  return images;
}

/* ─── Helpers ─── */
function addImage(doc: jsPDFType, dataUrl: string, x: number, y: number, maxW: number, maxH: number): number {
  // Get image natural size from dataUrl to maintain aspect ratio
  const img = new Image();
  img.src = dataUrl;
  const aspect = img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : 700 / 300;
  let w = maxW;
  let h = w / aspect;
  if (h > maxH) {
    h = maxH;
    w = h * aspect;
  }
  doc.addImage(dataUrl, "PNG", x, y, w, h);
  return h;
}

function drawLogo(doc: jsPDFType, x: number, y: number, size: number) {
  // Simple lightning bolt icon
  doc.setFillColor(BLUE);
  doc.roundedRect(x, y, size, size, 3, 3, "F");
  // Draw a simplified "⚡" with lines
  const cx = x + size / 2;
  const cy = y + size / 2;
  const s = size * 0.3;
  doc.setDrawColor("#ffffff");
  doc.setLineWidth(0.8);
  doc.line(cx + s * 0.1, cy - s, cx - s * 0.3, cy + s * 0.1);
  doc.line(cx - s * 0.3, cy + s * 0.1, cx + s * 0.3, cy + s * 0.1);
  doc.line(cx + s * 0.3, cy + s * 0.1, cx - s * 0.1, cy + s);
}

function hrLine(doc: jsPDFType, y: number) {
  doc.setDrawColor(LIGHT);
  doc.setLineWidth(0.3);
  doc.line(ML, y, PW - MR, y);
}

/* ─── Page 1: Cover ─── */
function drawCover(doc: jsPDFType, comp: StrategyComparison, all: EnergyResult[]) {
  // Background accent bar
  doc.setFillColor(BLUE);
  doc.rect(0, 0, PW, 6, "F");

  // Logo + brand
  drawLogo(doc, ML, 30, 16);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.setTextColor(DARK);
  doc.text("BuildWise", ML + 22, 42);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(GRAY);
  doc.text("Building Energy Simulation Platform", ML + 22, 49);

  // Divider
  hrLine(doc, 60);

  // Report title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(28);
  doc.setTextColor(DARK);
  doc.text("Building Energy", ML, 85);
  doc.text("Analysis Report", ML, 97);

  // Building info
  doc.setFontSize(12);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(GRAY);
  const infoY = 120;
  const info = [
    ["Building", comp.building_name],
    ["Type", comp.building_type.replace(/_/g, " ")],
    ["City", comp.climate_city],
    ["Strategies", `${all.length} (baseline + M0–M8)`],
    ["Period", comp.period_type === "1year" ? "Full Year" : comp.period_type ?? "Full Year"],
    ["Generated", new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })],
  ];

  info.forEach(([label, value], i) => {
    const y = infoY + i * 12;
    doc.setFont("helvetica", "normal");
    doc.setTextColor(GRAY);
    doc.text(label, ML, y);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(DARK);
    doc.text(value, ML + 40, y);
  });

  // Recommendation highlight
  if (comp.recommended_strategy) {
    const best = all.find((s) => s.strategy === comp.recommended_strategy);
    if (best) {
      const boxY = infoY + info.length * 12 + 10;
      doc.setFillColor("#F0FDF4");
      doc.roundedRect(ML, boxY, CW, 30, 3, 3, "F");
      doc.setDrawColor("#BBF7D0");
      doc.roundedRect(ML, boxY, CW, 30, 3, 3, "S");

      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.setTextColor(GREEN);
      doc.text("RECOMMENDED STRATEGY", ML + 6, boxY + 10);

      doc.setFontSize(14);
      doc.setTextColor(DARK);
      doc.text(
        STRATEGY_LABELS[comp.recommended_strategy] ?? comp.recommended_strategy,
        ML + 6,
        boxY + 22,
      );

      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.setTextColor(GRAY);
      doc.text(
        `${best.savings_pct?.toFixed(1) ?? "0"}% energy savings · ${best.annual_savings_krw ? `${(best.annual_savings_krw / 10000).toFixed(0)}만원/yr cost savings` : ""}`,
        ML + 80,
        boxY + 22,
      );
    }
  }

  // Mock disclaimer
  if (all.some((s) => s.is_mock)) {
    doc.setFontSize(8);
    doc.setTextColor("#B45309");
    doc.text(
      "Note: These results are demo-mode approximations, not actual EnergyPlus outputs.",
      ML,
      PH - MB - 10,
    );
  }

  // Footer line
  doc.setFontSize(8);
  doc.setTextColor(GRAY);
  doc.text("Confidential — BuildWise Energy Report", ML, PH - MB);
}

/* ─── Page 2: Summary + EUI Chart ─── */
function drawSummary(
  doc: jsPDFType,
  comp: StrategyComparison,
  all: EnergyResult[],
  euiImg: string | null,
) {
  let y = MT;

  // Section title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(DARK);
  doc.text("Executive Summary", ML, y);
  y += 4;
  hrLine(doc, y);
  y += 10;

  // Summary cards as a row of boxes
  const best = comp.recommended_strategy
    ? all.find((s) => s.strategy === comp.recommended_strategy)
    : null;
  const baseline = comp.baseline;

  const cards = [
    {
      label: "Recommended",
      value: best ? (STRATEGY_LABELS[best.strategy] ?? best.strategy) : "N/A",
      color: GREEN,
    },
    {
      label: "Energy Savings",
      value: best?.savings_pct ? `${best.savings_pct.toFixed(1)}%` : "N/A",
      color: BLUE,
    },
    {
      label: "Cost Savings",
      value: best?.annual_savings_krw
        ? `${(best.annual_savings_krw / 10000).toFixed(0)}만원/yr`
        : "N/A",
      color: GREEN,
    },
    {
      label: "Strategies",
      value: `${all.length}`,
      color: DARK,
    },
  ];

  const cardW = (CW - 9) / 4; // 4 cards with 3mm gap
  cards.forEach((card, i) => {
    const cx = ML + i * (cardW + 3);
    doc.setFillColor(LIGHT);
    doc.roundedRect(cx, y, cardW, 22, 2, 2, "F");

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(GRAY);
    doc.text(card.label, cx + 4, y + 8);

    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(card.color);
    doc.text(card.value, cx + 4, y + 17);
  });
  y += 30;

  // Recommendation reason
  if (comp.recommendation_reason) {
    doc.setFont("helvetica", "italic");
    doc.setFontSize(9);
    doc.setTextColor(GRAY);
    const lines = doc.splitTextToSize(comp.recommendation_reason, CW);
    doc.text(lines, ML, y);
    y += lines.length * 4 + 6;
  }

  // Baseline vs Best comparison
  if (baseline && best) {
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(DARK);
    doc.text(
      `Baseline EUI: ${baseline.eui_kwh_m2.toFixed(1)} kWh/m²  →  Best: ${best.eui_kwh_m2.toFixed(1)} kWh/m²  (Δ ${(baseline.eui_kwh_m2 - best.eui_kwh_m2).toFixed(1)} kWh/m²)`,
      ML,
      y,
    );
    y += 10;
  }

  // EUI Chart
  if (euiImg) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(DARK);
    doc.text("Energy Use Intensity (EUI) Comparison", ML, y);
    y += 6;
    addImage(doc, euiImg, ML, y, CW, 90);
  }
}

/* ─── Page 3: Analysis charts ─── */
function drawAnalysis(doc: jsPDFType, breakdownImg: string | null, radarImg: string | null) {
  let y = MT;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(DARK);
  doc.text("Detailed Analysis", ML, y);
  y += 4;
  hrLine(doc, y);
  y += 10;

  if (breakdownImg) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(DARK);
    doc.text("Energy Breakdown by End-Use (MWh)", ML, y);
    y += 6;
    const h = addImage(doc, breakdownImg, ML, y, CW, 90);
    y += h + 12;
  }

  if (radarImg) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(DARK);
    doc.text("Strategy Profile (% of Baseline)", ML, y);
    y += 2;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(GRAY);
    doc.text("Lower values indicate better performance. 100% = baseline level.", ML, y + 4);
    y += 10;
    addImage(doc, radarImg, ML, y, CW, 100);
  }
}

/* ─── Page 4: Cost + Monthly ─── */
function drawCostMonthly(doc: jsPDFType, costImg: string | null, monthlyImg: string | null) {
  let y = MT;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(DARK);
  doc.text("Cost & Monthly Profile", ML, y);
  y += 4;
  hrLine(doc, y);
  y += 10;

  if (costImg) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(DARK);
    doc.text("Annual Energy Cost (만원/year)", ML, y);
    y += 6;
    const h = addImage(doc, costImg, ML, y, CW, 90);
    y += h + 12;
  }

  if (monthlyImg) {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.setTextColor(DARK);
    doc.text("Monthly Energy Profile", ML, y);
    y += 6;
    addImage(doc, monthlyImg, ML, y, CW, 100);
  }
}

/* ─── Page 5+: Strategy Table ─── */
function drawTable(doc: jsPDFType, comp: StrategyComparison, all: EnergyResult[], autoTable: AutoTableFn) {
  let y = MT;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(DARK);
  doc.text("Strategy Comparison Table", ML, y);
  y += 4;
  hrLine(doc, y);
  y += 8;

  const head = [["Strategy", "EUI\n(kWh/m²)", "Total\n(MWh)", "HVAC\n(MWh)", "Savings\n(%)", "Cost\n(만원/yr)", "Cost Savings\n(만원/yr)"]];

  const body = all.map((s) => [
    STRATEGY_LABELS[s.strategy] ?? s.strategy,
    s.eui_kwh_m2.toFixed(1),
    (s.total_energy_kwh / 1000).toFixed(1),
    s.hvac_energy_kwh != null ? (s.hvac_energy_kwh / 1000).toFixed(1) : "-",
    s.savings_pct != null ? `${s.savings_pct.toFixed(1)}%` : "-",
    s.annual_cost_krw != null ? (s.annual_cost_krw / 10000).toFixed(0) : "-",
    s.annual_savings_krw != null && s.annual_savings_krw > 0
      ? (s.annual_savings_krw / 10000).toFixed(0)
      : "-",
  ]);

  // Use jspdf-autotable v5: autoTable(doc, options) function call
  autoTable(doc, {
    startY: y,
    head,
    body,
    theme: "grid",
    headStyles: {
      fillColor: [37, 99, 235], // BLUE
      textColor: 255,
      fontSize: 8,
      fontStyle: "bold",
      halign: "center",
    },
    bodyStyles: {
      fontSize: 9,
      textColor: [31, 41, 55], // DARK
      halign: "center",
    },
    columnStyles: {
      0: { halign: "left", fontStyle: "bold" },
    },
    alternateRowStyles: {
      fillColor: [249, 250, 251], // LIGHT
    },
    margin: { left: ML, right: MR },
    didParseCell: (data: { row: { index: number }; cell: { styles: { fillColor: number[]; textColor: number[]; fontStyle: string } } }) => {
      const rowIdx = data.row.index;
      const strategy = all[rowIdx]?.strategy;
      if (strategy === comp.recommended_strategy) {
        data.cell.styles.fillColor = [236, 253, 245]; // green-50
        data.cell.styles.textColor = [5, 150, 105]; // GREEN
        data.cell.styles.fontStyle = "bold";
      }
    },
  });

  // Strategy descriptions below table
  // v5: lastAutoTable is still available on doc as a side-effect
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let afterTableY = ((doc as any).lastAutoTable?.finalY ?? (doc as any).previousAutoTable?.finalY ?? y + 80) + 10;

  // Check if we need a new page for descriptions
  if (afterTableY > PH - MB - 60) {
    doc.addPage();
    afterTableY = MT;
  }

  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(DARK);
  doc.text("Strategy Descriptions", ML, afterTableY);
  afterTableY += 6;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(GRAY);

  all.forEach((s) => {
    const label = STRATEGY_LABELS[s.strategy] ?? s.strategy;
    const desc = STRATEGY_DESCRIPTIONS[s.strategy] ?? "";
    if (!desc) return;

    if (afterTableY > PH - MB - 10) {
      doc.addPage();
      afterTableY = MT;
    }

    doc.setFont("helvetica", "bold");
    doc.setTextColor(DARK);
    doc.text(`${label}:`, ML, afterTableY);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(GRAY);
    doc.text(desc, ML + 35, afterTableY);
    afterTableY += 5;
  });
}

/* ─── Page footer ─── */
function drawPageFooter(doc: jsPDFType, page: number, total: number, isMock: boolean) {
  const y = PH - 8;

  doc.setDrawColor(LIGHT);
  doc.setLineWidth(0.2);
  doc.line(ML, y - 4, PW - MR, y - 4);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7);
  doc.setTextColor(GRAY);

  doc.text("BuildWise — Building Energy Simulation Platform", ML, y);

  if (isMock) {
    doc.setTextColor("#B45309");
    doc.text("DEMO MODE", PW / 2, y, { align: "center" });
  }

  doc.setTextColor(GRAY);
  doc.text(`Page ${page} of ${total}`, PW - MR, y, { align: "right" });
}
