# Fixtures institucionais CNES

Recortes reais coletados em 07/10/2026 dos ZIPs oficiais identificados em `public/data/health.json` (URLs, publicação e SHA-256). `cnes.json` inclui Turvo/PR, cada comparador, Turvo/SC como controle negativo, SUS ambulatorial, unidade móvel, propriedade privada com gestão municipal e registro desativado. `beds.json` contém Hospital Bom Pastor nas competências 202607/202608; `types.json` transcreve a tabela oficial [Tipos CNES](https://cnes2.datasus.gov.br/Mod_Ind_Unidade.asp?VEstado=00).

Removidos CNPJ, razão social, telefone e e-mail dos recortes. Não há pacientes nem profissionais. Fixtures pequenas não são usadas como fonte dos dados publicados. Testes de normalização usam esses recortes; controles de publicação exigem arquivo nacional completo e volumes mínimos adicionais.
