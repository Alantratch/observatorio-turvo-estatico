import type { SocialData, SocialMetric } from "./types";
export function reference(value: string) {
  if (/^\d{6}$/.test(value))
    return new Intl.DateTimeFormat("pt-BR", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(new Date(`${value.slice(0, 4)}-${value.slice(4)}-01T12:00:00Z`));
  if (/^\d{4}-\d{2}-\d{2}$/.test(value))
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeZone: "UTC",
    }).format(new Date(value + "T12:00:00Z"));
  return value;
}
export function number(value: number | null, unit = "") {
  if (value === null) return "—";
  if (unit === "R$")
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 2,
    }).format(value);
  return (
    new Intl.NumberFormat("pt-BR", {
      maximumFractionDigits: unit === "%" || unit.includes("por 100") ? 2 : 0,
    }).format(value) + (unit === "%" ? "%" : "")
  );
}
export function cell(metric: SocialMetric) {
  return metric.status === "suppressed"
    ? "Suprimido"
    : metric.status === "unavailable"
      ? "Indisponível"
      : number(metric.value, metric.unit);
}
export function parseSocial(data: SocialData): SocialData {
  if (
    data.schemaVersion !== 1 ||
    data.municipality?.code !== "4127965" ||
    data.municipality?.state !== "PR" ||
    !Array.isArray(data.summary) ||
    !Array.isArray(data.sources) ||
    !Array.isArray(data.suas?.units) ||
    !Array.isArray(data.cadunico?.income)
  )
    throw Error(
      "O arquivo não corresponde ao módulo Assistência Social de Turvo/PR.",
    );
  const check = (obj: unknown): void => {
    if (Array.isArray(obj)) {
      obj.forEach(check);
      return;
    }
    if (obj && typeof obj === "object") {
      const c = obj as Record<string, unknown>;
      if ("unit" in c && "value" in c) {
        if (
          !["real", "derived", "unavailable", "suppressed"].includes(
            String(c.status),
          )
        )
          throw Error("Status de indicador inválido.");
        if (
          ["real", "derived"].includes(String(c.status)) &&
          (typeof c.value !== "number" ||
            !Number.isFinite(c.value) ||
            c.value < 0)
        )
          throw Error("Valor social inválido.");
        if (
          ["unavailable", "suppressed"].includes(String(c.status)) &&
          c.value !== null
        )
          throw Error("Ausência/supressão inválida.");
      }
      Object.values(c).forEach(check);
    }
  };
  check(data);
  return data;
}
export async function loadSocial(signal?: AbortSignal): Promise<SocialData> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/social.json`, {
    signal,
  });
  if (!response.ok)
    throw Error("Não foi possível carregar os dados de Assistência Social.");
  return parseSocial(await response.json());
}
export function narrative(data: SocialData) {
  const c = data.cadunico;
  if (c.families.value === null || c.people.value === null)
    return "O Cadastro Único está sem informação confirmada para esta referência.";
  return `Em ${reference(c.reference)}, Turvo tinha ${number(c.families.value)} famílias e ${number(c.people.value)} pessoas inscritas no Cadastro Único. Esses são dois universos de contagem distintos.`;
}
