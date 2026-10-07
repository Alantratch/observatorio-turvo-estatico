import { useEffect, useState } from "react";
import type { SocialData } from "./types";
import { loadSocial } from "./data";
import {
  SocialSummary,
  CadunicoOverview,
  IncomeProfile,
  RegistrationQuality,
  BolsaFamiliaSection,
  BpcSection,
  SuasNetwork,
  SocialServices,
  SocialComparison,
  SocialMethodology,
} from "./SocialSections";
import "./social.css";
export default function SocialAssistancePage() {
  const [data, setData] = useState<SocialData>(),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    setData(undefined);
    setError("");
    loadSocial(c.signal)
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => c.abort();
  }, [retry]);
  if (error)
    return (
      <section className="panel" role="alert">
        <h2>Assistência Social não carregou</h2>
        <p>{error}</p>
        <button onClick={() => setRetry((r) => r + 1)}>Tentar novamente</button>
      </section>
    );
  if (!data)
    return (
      <div role="status" className="loading">
        Carregando dados de Assistência Social…
        <div className="skeleton" />
      </div>
    );
  return (
    <div className="social-page">
      <SocialSummary data={data} />
      <CadunicoOverview data={data} />
      <IncomeProfile data={data} />
      <RegistrationQuality data={data} />
      <BolsaFamiliaSection data={data} />
      <BpcSection data={data} />
      <SuasNetwork data={data} />
      <SocialServices data={data} />
      <SocialComparison data={data} />
      <SocialMethodology data={data} />
    </div>
  );
}
