import { useState } from "react";
import type { SocialData } from "./types";
import { reference, cell, narrative } from "./data";
import {
  Section,
  MetricCard,
  MetricTable,
  Trend,
  Bars,
  Metadata,
  Downloads,
} from "./SocialComponents";
export function SocialSummary({ data }: { data: SocialData }) {
  const labels = [
    "Famílias no Cadastro Único",
    "Pessoas no Cadastro Único",
    "Famílias no Bolsa Família",
    "Bolsa Família · valor mensal",
    "BPC · benefícios",
  ];
  return (
    <>
      <div className="section-title">
        <h2>Assistência Social em números</h2>
        <span>Estatísticas municipais agregadas</span>
      </div>
      <div className="social-summary">
        {data.summary.map((m, i) => (
          <MetricCard key={i} metric={m} title={labels[i]} />
        ))}
      </div>
      <div className="social-context">
        <p>{narrative(data)}</p>
        <p>
          Cadastro, benefícios, rede e atendimentos são universos distintos. Uma
          mesma pessoa ou família pode aparecer em mais de uma base.
        </p>
      </div>
      <nav
        aria-label="Seções de Assistência Social"
        className="social-anchor-nav"
      >
        {[
          ["social-cad", "Cadastro Único"],
          ["social-income", "Renda"],
          ["social-quality", "Qualidade cadastral"],
          ["social-bf", "Bolsa Família"],
          ["social-bpc", "BPC"],
          ["social-suas", "Rede SUAS"],
          ["social-services", "Serviços"],
          ["social-perspective", "Perspectiva"],
          ["social-method", "Metodologia"],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() =>
              document
                .getElementById(id)
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            {label}
          </button>
        ))}
      </nav>
    </>
  );
}
export function CadunicoOverview({ data }: { data: SocialData }) {
  const [unit, setUnit] = useState<"families" | "people">("families");
  const c = data.cadunico;
  return (
    <Section
      id="social-cad"
      kicker="01 · CADASTRO E TERRITÓRIO"
      title="Cadastro Único"
      note="Registro administrativo de famílias e pessoas. Inscrição não significa recebimento automático de benefício."
    >
      <div className="social-two">
        <MetricCard title="Famílias cadastradas" metric={c.families} />
        <MetricCard title="Pessoas cadastradas" metric={c.people} />
      </div>
      <label className="social-filter">
        Unidade do histórico
        <select
          value={unit}
          onChange={(e) => setUnit(e.target.value as typeof unit)}
        >
          <option value="families">Famílias cadastradas</option>
          <option value="people">Pessoas cadastradas</option>
        </select>
      </label>
      <Trend
        title={
          unit === "families"
            ? "Evolução das famílias cadastradas"
            : "Evolução das pessoas cadastradas"
        }
        unit={c[unit].unit}
        points={c.series.map((p) => ({
          reference: p.reference,
          metric: p[unit],
        }))}
        breakAt={c.methodologyBreaks[0]?.reference}
      />
    </Section>
  );
}
export function IncomeProfile({ data }: { data: SocialData }) {
  const [unit, setUnit] = useState<"families" | "people">("families");
  const c = data.cadunico;
  return (
    <Section
      id="social-income"
      kicker="02 · RETRATO DA VULNERABILIDADE SOCIAL"
      title="Perfil de renda"
      note={`Faixas administrativas publicadas pelo MDS · ${reference(c.reference)}. Cadastro não é pesquisa de pobreza de toda a população.`}
    >
      <label className="social-filter">
        Unidade do perfil de renda
        <select
          value={unit}
          onChange={(e) => setUnit(e.target.value as typeof unit)}
        >
          <option value="families">Famílias por faixa de renda</option>
          <option value="people">Pessoas por faixa de renda</option>
        </select>
      </label>
      <Bars
        title={
          unit === "families"
            ? "Famílias por faixa de renda per capita"
            : "Pessoas por faixa de renda per capita"
        }
        rows={c.income.map((r) => ({ label: r.label, metric: r[unit] }))}
        unit={c[unit].unit}
      />
      <details className="social-meta">
        <summary>Definições das faixas e período</summary>
        <p>{c.incomeDefinition.note}</p>
        <p>
          Referência das categorias: {reference(c.incomeDefinition.reference)}.
          As regras podem mudar; não aplicamos esses limites para reclassificar
          históricos.
        </p>
        <a href={c.incomeDefinition.url} target="_blank" rel="noreferrer">
          Definições oficiais do MDS
        </a>
      </details>
    </Section>
  );
}
export function RegistrationQuality({ data }: { data: SocialData }) {
  const q = data.cadunico.registrationQuality;
  return (
    <Section
      id="social-quality"
      kicker="03 · QUALIDADE DO CADASTRO"
      title="Atualização cadastral"
      note="Indicadores de qualidade administrativa, sem exposição ou julgamento de famílias."
    >
      <div className="social-three">
        <MetricCard
          title="Famílias com cadastro atualizado"
          metric={q.updated}
        />
        <MetricCard
          title="Percentual atualizado · oficial"
          metric={q.updatedPercent}
        />
        <MetricCard
          title="Diferença entre total e atualizados"
          metric={q.notUpdated}
        />
      </div>
      <p className="source">
        A diferença é um cálculo do Observatório na mesma referência. Não mede
        inclusões ou atualizações realizadas recentemente.
      </p>
    </Section>
  );
}
export function BolsaFamiliaSection({ data }: { data: SocialData }) {
  const [metric, setMetric] = useState<
    "families" | "transferredValue" | "averageBenefit"
  >("families");
  const b = data.bolsaFamilia;
  const labels = {
    families: "Famílias beneficiárias",
    transferredValue: "Valor mensal transferido",
    averageBenefit: "Benefício médio oficial",
  };
  return (
    <Section
      id="social-bf"
      kicker="04 · TRANSFERÊNCIA FEDERAL DE RENDA"
      title="Bolsa Família"
      note={`Competência: ${reference(b.reference)}. Recursos transferidos às famílias pelo programa federal.`}
    >
      <div className="social-two">
        <MetricCard title="Pessoas beneficiárias" metric={b.people} />
        <MetricCard
          title="Benefício médio publicado pelo MDS"
          metric={b.averageBenefit}
        />
      </div>
      <p className="social-callout">
        Em {reference(b.reference)}, {cell(b.families)} famílias receberam Bolsa
        Família, com {cell(b.transferredValue)} transferidos no mês.
      </p>
      <label className="social-filter">
        Indicador do histórico Bolsa Família
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value as typeof metric)}
        >
          {Object.entries(labels).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <Trend
        title={labels[metric]}
        points={b.series.map((p) => ({
          reference: p.reference,
          metric: p[metric],
        }))}
        unit={b[metric].unit}
      />
      <p className="source">{b.methodology}</p>
      <Metadata metric={b.averageBenefit} />
    </Section>
  );
}
export function BpcSection({ data }: { data: SocialData }) {
  const b = data.bpc;
  return (
    <Section
      id="social-bpc"
      kicker="05 · BENEFÍCIO ASSISTENCIAL"
      title="Benefício de Prestação Continuada"
      note={`Referência: ${reference(b.reference)} · Fonte Pagadora. O BPC tem públicos e regras próprios, separados do Bolsa Família.`}
    >
      <Bars
        title="Benefícios BPC por público"
        unit="benefícios"
        rows={[
          { label: "Pessoa idosa", metric: b.elderly },
          { label: "Pessoa com deficiência", metric: b.disabled },
        ]}
      />
      <MetricTable
        rows={[
          { label: "Total de benefícios BPC", metric: b.total },
          { label: "Valor · pessoa idosa", metric: b.elderlyValue },
          { label: "Valor · pessoa com deficiência", metric: b.disabledValue },
          { label: "Valor total mensal BPC", metric: b.transferredValue },
        ]}
      />
      <Trend
        title="Evolução dos benefícios BPC · Fonte Pagadora"
        unit="benefícios"
        points={b.series.map((p) => ({
          reference: p.reference,
          metric: p.total,
        }))}
      />
      <p className="source">{b.methodology}</p>
    </Section>
  );
}
export function SuasNetwork({ data }: { data: SocialData }) {
  const s = data.suas;
  return (
    <Section
      id="social-suas"
      kicker="06 · PROTEÇÃO SOCIAL NO TERRITÓRIO"
      title="Rede de Assistência Social"
      note={`CadSUAS: extração em ${reference(s.cadSuasReference)}. Censo SUAS: edição anual ${s.reference}. Cada base tem universo próprio.`}
    >
      <h3>Unidades cadastradas · CadSUAS</h3>
      <div className="social-network-counts">
        {Object.values(s.cadSuasCounts).map((m) => (
          <div key={m.indicator}>
            <strong>{cell(m)}</strong>
            <span>{m.indicator}</span>
            <small>{reference(m.reference)}</small>
          </div>
        ))}
      </div>
      <MetricTable
        rows={Object.entries(s.cadSuasCounts).map(([, metric]) => ({
          label: metric.indicator,
          metric,
        }))}
      />
      <h3>Equipamentos respondentes ao Censo SUAS {s.reference}</h3>
      <div className="social-two">
        {s.units.map((u) => (
          <article className="social-equipment" key={u.type + u.id}>
            <span className="eyebrow">
              {u.type === "cras"
                ? "Proteção social básica"
                : u.type === "creas"
                  ? "Proteção social especial"
                  : "Equipamento socioassistencial"}
            </span>
            <h3>{u.institutionName}</h3>
            <p>
              {u.institutionalAddress || "Endereço institucional não informado"}
            </p>
            <p className="source">
              Identificador oficial: {u.id}
              <br />
              {u.situation}
            </p>
            {u.services.length > 0 && (
              <p>
                Serviço informado no Censo: <b>{u.services.join(", ")}</b>.
              </p>
            )}
            <a
              href={data.sources.find((s) => s.id === u.sourceId)?.url}
              target="_blank"
              rel="noreferrer"
            >
              Arquivo oficial · {u.reference}
            </a>
          </article>
        ))}
      </div>
      <details className="social-meta">
        <summary>Cobertura das respostas ao Censo SUAS</summary>
        <MetricTable
          rows={Object.values(s.censusCounts).map((metric) => ({
            label: metric.indicator,
            metric,
          }))}
        />
      </details>
      <p className="source">{s.note}</p>
      <p className="notice">
        Mapa da rede: coordenadas institucionais não confirmadas nesta
        exportação. Nenhum beneficiário é localizado no mapa.
      </p>
    </Section>
  );
}
export function SocialServices({ data }: { data: SocialData }) {
  const [metric, setMetric] = useState<
    "accompaniedFamilies" | "newFamilies" | "individualAttendances"
  >("accompaniedFamilies");
  const s = data.services;
  const labels = {
    accompaniedFamilies: "Famílias acompanhadas pelo PAIF",
    newFamilies: "Novas famílias em acompanhamento PAIF",
    individualAttendances: "Atendimentos particularizados no CRAS",
  };
  const latest = [...s.paif]
    .reverse()
    .find((p) => p.accompaniedFamilies.status === "real");
  return (
    <Section
      id="social-services"
      kicker="07 · ATENDIMENTO DO SUAS"
      title="Serviços socioassistenciais"
      note="PAIF: Serviço de Proteção e Atendimento Integral à Família. PAEFI: Serviço de Proteção e Atendimento Especializado a Famílias e Indivíduos. A oferta de serviço e o número de atendimentos são informações diferentes."
    >
      {latest && (
        <>
          <p className="social-callout">
            No RMA de {reference(latest.reference)}, foram informadas{" "}
            {cell(latest.accompaniedFamilies)} famílias em acompanhamento pelo
            PAIF. Formulários válidos: {latest.reportingUnits} unidade(s).
          </p>
          <label className="social-filter">
            Indicador RMA CRAS
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as typeof metric)}
            >
              {Object.entries(labels).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <Trend
            title={labels[metric]}
            points={s.paif.map((p) => ({
              reference: p.reference,
              metric: p[metric],
            }))}
            unit={
              metric === "individualAttendances" ? "atendimentos" : "famílias"
            }
          />
        </>
      )}
      <p className="source">{s.note}</p>
      <div className="notice">
        Atendimentos PAEFI: indisponíveis.{" "}
        {s.paefi.note.replace("[PENDENTE] ", "")}
      </div>
      <p>
        As unidades do Censo informam PAIF no CRAS e PAEFI no CREAS. Essa
        identificação de oferta não implica contagem de famílias atendidas em
        2026.
      </p>
    </Section>
  );
}
export function SocialComparison({ data }: { data: SocialData }) {
  const [metric, setMetric] = useState<
    "peoplePer100" | "people" | "families" | "cras"
  >("peoplePer100");
  const labels = {
    peoplePer100: "Pessoas no CadÚnico por 100 habitantes",
    people: "Pessoas cadastradas · absoluto",
    families: "Famílias cadastradas · absoluto",
    cras: "CRAS respondentes ao Censo · absoluto",
  };
  return (
    <Section
      id="social-perspective"
      kicker="08 · CONTEXTO MUNICIPAL"
      title="Turvo em perspectiva"
      note="Turvo, Pitanga, Laranjal e Guarapuava. Ordem fixa por território, sem ranking de pobreza."
    >
      <label className="social-filter">
        Indicador da comparação
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value as typeof metric)}
        >
          {Object.entries(labels).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </label>
      <Bars
        title={labels[metric]}
        rows={data.comparisons.map((r) => ({
          label: r.municipalityName,
          metric: r[metric],
        }))}
        unit={data.comparisons[0][metric].unit}
      />
      {metric === "peoplePer100" && (
        <>
          <p className="social-callout">
            Cálculo do Observatório: pessoas cadastradas ÷ população IBGE
            estimada × 100. Cadastro mensal e estimativa de 1º de julho do mesmo
            ano; a proporção é aproximada.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Município</th>
                  <th>Pessoas no CadÚnico</th>
                  <th>População IBGE</th>
                  <th>Referências</th>
                </tr>
              </thead>
              <tbody>
                {data.comparisons.map((r) => (
                  <tr key={r.municipalityCode}>
                    <th scope="row">{r.municipalityName}</th>
                    <td>
                      {r.peoplePer100.numerator?.toLocaleString("pt-BR") ?? "—"}
                    </td>
                    <td>
                      {r.peoplePer100.denominator?.toLocaleString("pt-BR") ??
                        "—"}
                    </td>
                    <td>
                      {reference(r.peoplePer100.numeratorReference ?? "")} /{" "}
                      {r.peoplePer100.denominatorReference}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Metadata metric={data.comparisons[0].peoplePer100} />
        </>
      )}
      <p className="source">
        CadÚnico também depende de cobertura, atualização, políticas e
        elegibilidade. Mais inscrições não significam automaticamente mais
        pobreza. Não calculamos famílias beneficiárias por habitante como
        cobertura familiar.
      </p>
    </Section>
  );
}
export function SocialMethodology({ data }: { data: SocialData }) {
  return (
    <Section
      id="social-method"
      kicker="09 · INFORMAÇÃO ABERTA E RESPONSÁVEL"
      title="Fontes e metodologia"
    >
      <Downloads />
      <h3>Privacidade e proteção de dados</h3>
      <p>{data.privacy.policy}</p>
      <p>
        “Indisponível” representa ausência não confirmada; “suprimido” protege
        uma célula pequena. Nenhum dos dois significa zero. O BPC usa supressão
        complementar quando necessário.
      </p>
      <h3>Limites e próximos indicadores</h3>
      <div className="social-pending">
        {data.privacy.unavailable.map((u) => (
          <details key={u.id}>
            <summary>{u.title} · indisponível</summary>
            <p>{u.note.replace("[PENDENTE] ", "")}</p>
            <a href={u.url} target="_blank" rel="noreferrer">
              Referência oficial
            </a>
          </details>
        ))}
      </div>
      <h3>Fontes desta publicação</h3>
      <div className="social-pending">
        {data.sources.map((s) => (
          <details key={s.id}>
            <summary>
              {s.title} · {reference(s.reference)}
              {s.id.includes("population-")
                ? " · IBGE " + s.id.replace("population-", "")
                : ""}
            </summary>
            <p>
              {s.agency} · coleta{" "}
              {new Date(s.collectedAt).toLocaleDateString("pt-BR", {
                timeZone: "UTC",
              })}
            </p>
            <p>{s.methodology}</p>
            <a href={s.url} target="_blank" rel="noreferrer">
              Consultar fonte estruturada
            </a>
          </details>
        ))}
      </div>
      <p>
        Veja também <a href="#economy">Economia</a> e{" "}
        <a href="#employment">Trabalho e Emprego</a>. A comparação entre
        indicadores municipais não estabelece causalidade.
      </p>
    </Section>
  );
}
