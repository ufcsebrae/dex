import './index.css';
import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import { Activity, HelpCircle, BarChart3 } from 'lucide-react';

interface RegistroMensal {
  nm_unidade: string;
  vl_ano: number;
  vl_mes: number;
  planejado: number;
  executado: number;
}

interface RegistroNatureza {
  nm_unidade: string;
  vl_ano: number;
  Descricao_Natureza_Orcamentaria: string;
  planejado: number;
  executado: number;
}

interface RegistroProjeto {
  nm_unidade: string;
  nm_iniciativa: string;
  vl_ano: number;
  planejado: number;
  executado: number;
}

interface ApiResponse {
  mensal: RegistroMensal[];
  natureza: RegistroNatureza[];
  projeto: RegistroProjeto[];
}

interface CoberturaDados {
  unidade: string;
  ano: number;
  despesa: number;
  receita: number;
  resultado_liquido: number;
  indice_cobertura: number;
}

const NOMES_MESES: { [key: number]: string } = {
  1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
  7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
};

export default function App() {
  const [dados, setDados] = useState<ApiResponse | null>(null);
  const [dadosCobertura, setDadosCobertura] = useState<CoberturaDados[]>([]);
  const [loading, setLoading] = useState(true);
  const [paginaAtiva, setPaginaAtiva] = useState<number>(1); // 1, 2 ou 3
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string>('');

  useEffect(() => {
    const fetchDados = fetch('http://127.0.0.1:8081/api/planejado-executado').then(res => res.json());
    const fetchCobertura = fetch('http://127.0.0.1:8081/api/cobertura').then(res => res.json());

    Promise.all([fetchDados, fetchCobertura])
      .then(([data, cobertura]) => {
        if (data && !data.error && data.mensal) {
          setDados(data);
          const unidades = [...new Set(data.mensal.map((r: any) => r.nm_unidade))].sort();
          if (unidades.length > 0) {
            setUnidadeSelecionada(unidades[0] as string);
          }
        }
        if (cobertura && !cobertura.error) {
          setDadosCobertura(cobertura);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Erro ao carregar dados locais:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-200">
        <Activity className="h-8 w-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  // --- BLINDAGEM DE VARIÁVEIS ---
  const dadosMensal = dados?.mensal || [];
  const dadosNatureza = dados?.natureza || [];
  const dadosProjeto = dados?.projeto || [];
  const listaUnidades = [...new Set(dadosMensal.map(r => r.nm_unidade))].sort();

  // --- PÁGINA 1: EVOLUÇÃO MENSAL ---
  const dadosDaUnidadeMensal = dadosMensal.filter(r => r.nm_unidade === unidadeSelecionada);
  const prepararDadosMensal = (ano: number) => {
    const registrosAno = dadosDaUnidadeMensal.filter(r => r.vl_ano === ano);
    const mesesUnicos = [...new Set(registrosAno.map(r => r.vl_mes))].sort((a, b) => a - b);
    return mesesUnicos.map(mes => {
      const reg = registrosAno.find(r => r.vl_mes === mes);
      return {
        name: NOMES_MESES[mes] || `Mês ${mes}`,
        Planejado: Math.round(reg?.planejado || 0),
        Executado: Math.round(reg?.executado || 0)
      };
    });
  };

  const dados2025 = prepararDadosMensal(2025);
  const dados2026 = prepararDadosMensal(2026);

  // --- PÁGINA 1: TABELA DETALHADA POR PROJETO ---
  const dadosDaUnidadeProjeto = dadosProjeto.filter(r => r.nm_unidade === unidadeSelecionada);
  const mapaProjetos: { [nome: string]: { [ano: string]: { p: number, e: number } } } = {};
  dadosDaUnidadeProjeto.forEach(r => {
    const proj = r.nm_iniciativa;
    const ano = r.vl_ano.toString();
    if (!mapaProjetos[proj]) {
      mapaProjetos[proj] = { "2025": { p: 0, e: 0 }, "2026": { p: 0, e: 0 } };
    }
    mapaProjetos[proj][ano] = { p: r.planejado, e: r.executado };
  });
  const listaProjetosUnificados = Object.keys(mapaProjetos).sort();

  // --- PÁGINA 2: NATUREZAS (EXECUÇÃO DE 2025 X 2026) ---
  const dadosDaUnidadeNatureza = dadosNatureza.filter(r => r.nm_unidade === unidadeSelecionada);
  const todasNaturezas = [...new Set(dadosDaUnidadeNatureza.map(r => r.Descricao_Natureza_Orcamentaria))].sort();
  const dadosNaturezasAgrupadas = todasNaturezas.map(natureza => {
    const reg2025 = dadosDaUnidadeNatureza.find(r => r.Descricao_Natureza_Orcamentaria === natureza && r.vl_ano === 2025);
    const reg2026 = dadosDaUnidadeNatureza.find(r => r.Descricao_Natureza_Orcamentaria === natureza && r.vl_ano === 2026);

    const executado2025 = Math.round(Number(reg2025?.executado) || 0);
    const executado2026 = Math.round(Number(reg2026?.executado) || 0);
    let delta = 0;
    if (executado2025 > 0) {
      delta = ((executado2026 - executado2025) / executado2025) * 100;
    } else if (executado2026 > 0) {
      delta = 100.0;
    }
    return {
      name: natureza.length > 20 ? natureza.substring(0, 20) + "..." : natureza,
      fullName: natureza,
      "Executado 2025": executado2025,
      "Executado 2026": executado2026,
      delta: delta
    };
  }).sort((a, b) => b["Executado 2025"] - a["Executado 2025"]);

  const maximoGlobalHaltere = Math.max(
    ...dadosNaturezasAgrupadas.map(r => Number(r["Executado 2025"]) || 0),
    ...dadosNaturezasAgrupadas.map(r => Number(r["Executado 2026"]) || 0),
    1
  );

  // --- PÁGINA 3: DADOS DE AUTOSSUFICIÊNCIA DA UNIDADE SELECIONADA POR ANO ---
  const registrosUnidadeCobertura = dadosCobertura.filter(r => r.unidade === unidadeSelecionada);
  const r2025 = registrosUnidadeCobertura.find(r => r.ano === 2025) || { unidade: '', ano: 2025, despesa: 0, receita: 0, resultado_liquido: 0, indice_cobertura: 0 };
  const r2026 = registrosUnidadeCobertura.find(r => r.ano === 2026) || { unidade: '', ano: 2026, despesa: 0, receita: 0, resultado_liquido: 0, indice_cobertura: 0 };

  // Gráfico 1: Comparação YoY da Unidade Selecionada (Despesa vs Receita)
  const dadosGraficoFocadoBarras = [
    {
      name: "Ano 2025 (Q1)",
      Despesa: Math.round(r2025.despesa),
      Receita: Math.round(r2025.receita)
    },
    {
      name: "Ano 2026 (Q1)",
      Despesa: Math.round(r2026.despesa),
      Receita: Math.round(r2026.receita)
    }
  ];

  // Gráfico 2: Comparação YoY do Índice de Cobertura %
  const dadosGraficoFocadoPercentual = [
    {
      name: "Ano 2025",
      Cobertura: parseFloat(r2025.indice_cobertura.toFixed(2))
    },
    {
      name: "Ano 2026",
      Cobertura: parseFloat(r2026.indice_cobertura.toFixed(2))
    }
  ];

  // Agrupamento consolidado das Unidades para a Tabela de Ranking Geral comparando os anos
  const mapaUnidadesRanking: { [unidade: string]: { [ano: string]: number } } = {};
  dadosCobertura.forEach(r => {
    const uni = r.unidade;
    const ano = r.ano.toString();
    if (!mapaUnidadesRanking[uni]) {
      mapaUnidadesRanking[uni] = { "2025": 0, "2026": 0 };
    }
    mapaUnidadesRanking[uni][ano] = r.indice_cobertura;
  });

  const listaUnidadesRankingOrdenadas = Object.keys(mapaUnidadesRanking).sort((a, b) => {
    const cobA = mapaUnidadesRanking[a]["2026"] || 0;
    const cobB = mapaUnidadesRanking[b]["2026"] || 0;
    return cobB - cobA; // Ordena pelo ano mais recente (2026)
  });

  // --- FORMATAÇÕES FINANCEIRAS ---
  const formatadorMoeda = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', minimumFractionDigits: 2
  });

  const formatarEixoY = (value: number) => {
    if (value >= 1_000_000) return `R$ ${(value / 1_000_000).toFixed(1).replace('.', ',')}M`;
    if (value >= 1_000) return `R$ ${(value / 1_000).toFixed(0)}k`;
    return `R$ ${value}`;
  };

  const renderizarTagVariacao = (valor: number) => {
    if (valor > 0) {
      return (
        <span className="inline-flex rounded-md px-2 py-0.5 text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
          +{valor.toFixed(1)}%
        </span>
      );
    }
    if (valor < 0) {
      return (
        <span className="inline-flex rounded-md px-2 py-0.5 text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          {valor.toFixed(1)}%
        </span>
      );
    }
    return (
      <span className="inline-flex rounded-md px-2 py-0.5 text-xs font-bold bg-slate-800 text-slate-400">
        0.0%
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 p-8 text-slate-100 font-sans selection:bg-emerald-500/30">

      {/* Header */}
      <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800 pb-6 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-500 bg-clip-text text-transparent">
            DEX Portal — Orçamento vs Execução
          </h1>
          <p className="text-sm text-slate-400">Acompanhamento unificado e análise integrada do PPA (2025 e 2026)</p>
        </div>
        {/* Abas */}
        <div className="flex rounded-lg bg-slate-900 p-1 border border-slate-800 shrink-0">
          <button
            onClick={() => setPaginaAtiva(1)}
            className={`rounded-md px-4 py-2 text-xs font-semibold transition-all ${paginaAtiva === 1 ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-100'}`}
          >
            Página 1: Evolução Mensal
          </button>
          <button
            onClick={() => setPaginaAtiva(2)}
            className={`rounded-md px-4 py-2 text-xs font-semibold transition-all ${paginaAtiva === 2 ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-100'}`}
          >
            Página 2: Análise de Naturezas
          </button>
          <button
            onClick={() => setPaginaAtiva(3)}
            className={`rounded-md px-4 py-2 text-xs font-semibold transition-all ${paginaAtiva === 3 ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-100'}`}
          >
            Página 3: Autossuficiência (Q1)
          </button>
        </div>
      </div>

      {/* Filtro Principal */}
      <div className="mb-6 flex justify-between items-center bg-slate-900/40 border border-slate-800 p-4 rounded-xl font-sans">
        <span className="text-sm text-slate-300 font-medium font-sans">Unidade Organizacional Selecionada</span>
        <select
          value={unidadeSelecionada}
          onChange={(e) => setUnidadeSelecionada(e.target.value)}
          className="rounded-lg border border-slate-800 bg-slate-950 px-4 py-2 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none transition-all cursor-pointer font-sans"
        >
          {listaUnidades.map((unidade) => (
            <option key={unidade} value={unidade}>{unidade}</option>
          ))}
        </select>
      </div>

      {!dados ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center">
          <HelpCircle className="h-12 w-12 text-slate-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-slate-300">Carregando estrutura de dados...</h3>
          <p className="text-slate-500 text-sm mt-1">Sincronizando os dados de fechamento com o painel.</p>
        </div>
      ) : (
        <>
          {/* --- PÁGINA 1: EVOLUÇÃO MENSAL E TABELA DETALHADA --- */}
          {paginaAtiva === 1 && (
            <div className="flex flex-col gap-8 animate-fadeIn">
              {/* Gráficos de Linha */}
              <div className="grid gap-6 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                  <h2 className="text-lg font-semibold mb-4 text-slate-200">Ano 2025 — Evolução Mensal do PPA</h2>
                  <div className="h-[250px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={dados2025} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                        <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={formatarEixoY} />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }} formatter={(v: any) => [formatadorMoeda.format(v)]} />
                        <Legend verticalAlign="top" height={36} />
                        <Line type="monotone" dataKey="Planejado" name="Planejado" stroke="#06b6d4" strokeWidth={3} dot={false} />
                        <Line type="monotone" dataKey="Executado" name="Executado" stroke="#10b981" strokeWidth={3} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                  <h2 className="text-lg font-semibold mb-4 text-slate-200">Ano 2026 — Evolução Mensal do PPA</h2>
                  <div className="h-[250px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={dados2026} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                        <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={formatarEixoY} />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }} formatter={(v: any) => [formatadorMoeda.format(v)]} />
                        <Legend verticalAlign="top" height={36} />
                        <Line type="monotone" dataKey="Planejado" name="Planejado" stroke="#06b6d4" strokeWidth={3} dot={false} />
                        <Line type="monotone" dataKey="Executado" name="Executado" stroke="#10b981" strokeWidth={3} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
              {/* Tabela Detalhada por Projeto */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                <h2 className="text-lg font-semibold mb-4 text-slate-200">Demonstrativo Detalhado por Projeto / Iniciativa</h2>
                <div className="rounded-xl border border-slate-800 bg-slate-900/30 overflow-hidden">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-900/80 text-slate-400 border-b border-slate-800 font-semibold uppercase tracking-wider">
                        <th className="p-3">Nome do Projeto (Iniciativa)</th>
                        <th className="p-3 text-right">Planejado 2025</th>
                        <th className="p-3 text-right">Executado 2025</th>
                        <th className="p-3 text-right">Planejado 2026</th>
                        <th className="p-3 text-right">Executado 2026</th>
                        <th className="p-3 text-center">Var. Planejado %</th>
                        <th className="p-3 text-center">Var. Executado %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {listaProjetosUnificados.map(projeto => {
                        const anos = mapaProjetos[projeto] || {};
                        const p25 = anos["2025"]?.p || 0;
                        const e25 = anos["2025"]?.e || 0;
                        const p26 = anos["2026"]?.p || 0;
                        const e26 = anos["2026"]?.e || 0;
                        let varPlanejado = 0;
                        if (p25 > 0) varPlanejado = ((p26 - p25) / p25) * 100;
                        else if (p26 > 0) varPlanejado = 100.0;
                        let varExecutado = 0;
                        if (e25 > 0) varExecutado = ((e26 - e25) / e25) * 100;
                        else if (e26 > 0) varExecutado = 100.0;
                        return (
                          <tr key={projeto} className="hover:bg-slate-900/30 transition-colors">
                            <td className="p-3 font-medium text-slate-300 truncate max-w-[250px]" title={projeto}>{projeto}</td>
                            <td className="p-3 text-right text-cyan-400 font-mono">{formatadorMoeda.format(p25)}</td>
                            <td className="p-3 text-right text-emerald-400 font-mono">{formatadorMoeda.format(e25)}</td>
                            <td className="p-3 text-right text-cyan-400 font-mono">{formatadorMoeda.format(p26)}</td>
                            <td className="p-3 text-right text-emerald-400 font-mono">{formatadorMoeda.format(e26)}</td>
                            <td className="p-3 text-center">{renderizarTagVariacao(varPlanejado)}</td>
                            <td className="p-3 text-center">{renderizarTagVariacao(varExecutado)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
          {/* --- PÁGINA 2: ANÁLISE DE NATUREZAS --- */}
          {paginaAtiva === 2 && (
            <div className="flex flex-col gap-8 animate-fadeIn">
              {/* Grouped Bar Chart por Natureza */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-slate-200">Grouped Bar Chart — Executado 2025 vs 2026</h2>
                  <BarChart3 className="h-5 w-5 text-cyan-400" />
                </div>
                <div className="h-[320px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dadosNaturezasAgrupadas} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                      <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={formatarEixoY} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                        labelFormatter={(label: any, items: any[]) => `Natureza: ${items[0]?.payload?.fullName || label}`}
                        formatter={(v: any) => [formatadorMoeda.format(v)]}
                      />
                      <Legend verticalAlign="top" height={36} />
                      <Bar dataKey="Executado 2025" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Executado 2026" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              {/* Gráfico de Haltere (Dumbbell Chart) */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
                <div className="mb-6 flex justify-between items-center">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-200 font-sans">Gráfico de Haltere — Variação Real de Gasto (2025 vs 2026)</h2>
                    <p className="text-xs text-slate-500 mt-0.5">Visão unificada em escala proporcional e linhas de referência vertical</p>
                  </div>
                  <div className="flex gap-4 text-xs font-semibold">
                    <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-cyan-500 block" /> 2025</span>
                    <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-emerald-500 block" /> 2026</span>
                  </div>
                </div>
                <div className="relative flex flex-col gap-6 pt-2 pb-6">
                  {/* LINHAS DE GRADE DE FUNDO */}
                  <div className="absolute inset-0 flex pointer-events-none" style={{ left: '25%', right: '8%' }}>
                    <div className="w-1/4 border-r border-slate-800/40 border-dashed h-full" />
                    <div className="w-1/4 border-r border-slate-800/40 border-dashed h-full" />
                    <div className="w-1/4 border-r border-slate-800/40 border-dashed h-full" />
                    <div className="w-1/4 border-r border-slate-800/40 border-dashed h-full" />
                  </div>
                  {dadosNaturezasAgrupadas.map(r => {
                    const val2025 = Number(r["Executado 2025"]) || 0;
                    const val2026 = Number(r["Executado 2026"]) || 0;

                    const pos2025 = maximoGlobalHaltere > 0 ? (val2025 / maximoGlobalHaltere) * 100 : 0;
                    const pos2026 = maximoGlobalHaltere > 0 ? (val2026 / maximoGlobalHaltere) * 100 : 0;
                    return (
                      <div key={r.fullName} className="flex items-center justify-between gap-4 relative z-10 h-8">
                        <div className="w-1/4 pr-4 truncate">
                          <span className="text-xs font-semibold text-slate-300 block" title={r.fullName}>{r.fullName}</span>
                          <span className="text-[9px] text-slate-500 block">Var: {r.delta > 0 ? `+${r.delta.toFixed(1)}%` : `${r.delta.toFixed(1)}%`}</span>
                        </div>
                        <div className="flex-1 h-full flex items-center relative px-2">
                          <div className="w-full h-1 bg-slate-800/60 rounded relative">
                            <div
                              className="absolute h-1 bg-slate-500 rounded"
                              style={{
                                left: `${Math.min(pos2025, pos2026)}%`,
                                right: `${100 - Math.max(pos2025, pos2026)}%`
                              }}
                            />
                            <div
                              className="absolute h-3 w-3 rounded-full bg-cyan-500 border border-slate-950 -top-1 shadow-md cursor-help"
                              style={{ left: `calc(${pos2025}% - 6px)` }}
                              title={`2025: ${formatadorMoeda.format(val2025)}`}
                            />
                            <div
                              className="absolute h-3 w-3 rounded-full bg-emerald-500 border border-slate-950 -top-1 shadow-md cursor-help"
                              style={{ left: `calc(${pos2026}% - 6px)` }}
                              title={`2026: ${formatadorMoeda.format(val2026)}`}
                            />
                          </div>
                        </div>
                        <div className="w-24 text-right">
                          <span className={`inline-flex rounded-md px-2.5 py-0.5 text-xs font-bold ${r.delta > 0 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : r.delta < 0 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400'}`}>
                            {r.delta > 0 ? `+${r.delta.toFixed(1)}%` : `${r.delta.toFixed(1)}%`}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                  <div className="flex text-[10px] text-slate-500 border-t border-slate-800/80 pt-2 mt-2" style={{ marginLeft: '25%', marginRight: '8%' }}>
                    <span className="w-1/4 text-left">R$ 0</span>
                    <span className="w-1/4 text-center">{formatarEixoY(maximoGlobalHaltere * 0.25)}</span>
                    <span className="w-1/4 text-center">{formatarEixoY(maximoGlobalHaltere * 0.5)}</span>
                    <span className="w-1/4 text-center">{formatarEixoY(maximoGlobalHaltere * 0.75)}</span>
                    <span className="w-1/4 text-right">{formatarEixoY(maximoGlobalHaltere)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* --- PÁGINA 3: AUTOSSUFICIÊNCIA E COBERTURA ANO A ANO DA UNIDADE SELECIONADA (Q1) --- */}
      {paginaAtiva === 3 && (
        <div className="flex flex-col gap-8 animate-fadeIn">

          {/* 1. Cards de Saúde Financeira da Unidade Selecionada */}
          <div className="grid gap-6 md:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm">
              <span className="text-xs font-medium text-slate-400 uppercase">Despesa Acumulada Q1</span>
              <div className="text-2xl font-bold text-rose-400 mt-2">
                <span className="text-xs text-slate-500 block">2025: {formatadorMoeda.format(r2025.despesa)}</span>
                <span className="text-sm block mt-1">2026: {formatadorMoeda.format(r2026.despesa)}</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm">
              <span className="text-xs font-medium text-slate-400 uppercase">Receita Acumulada Q1</span>
              <div className="text-2xl font-bold text-emerald-400 mt-2">
                <span className="text-xs text-slate-500 block">2025: {formatadorMoeda.format(r2025.receita)}</span>
                <span className="text-sm block mt-1">2026: {formatadorMoeda.format(r2026.receita)}</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm">
              <span className="text-xs font-medium text-slate-400 uppercase">Resultado Líquido</span>
              <div className="text-2xl font-bold text-slate-300 mt-2">
                <span className="text-xs text-slate-500 block">2025: {formatadorMoeda.format(r2025.resultado_liquido)}</span>
                <span className="text-sm block mt-1">2026: {formatadorMoeda.format(r2026.resultado_liquido)}</span>
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 backdrop-blur-sm">
              <span className="text-xs font-medium text-slate-400 uppercase">Índice de Cobertura</span>
              <div className="text-xl font-bold text-indigo-400 mt-2">
                <span className="text-xs text-slate-500 block">2025: {r2025.indice_cobertura.toFixed(2)}%</span>
                <span className="text-sm block mt-1">2026: {r2026.indice_cobertura.toFixed(2)}%</span>
              </div>
              <div className="w-full mt-3">
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(r2026.indice_cobertura, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* 2. Comparativo Unidade Selecionada vs Média Geral do Sebrae SP */}
          <div className="grid gap-6 md:grid-cols-2">

            {/* Gráfico 1: Despesa vs Receita */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
              <h2 className="text-lg font-semibold mb-4 text-slate-200">Comparativo YoY de Despesa vs Receita (Primeiro Tri)</h2>
              <div className="h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dadosGraficoFocadoBarras} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={11} tickLine={false} tickFormatter={formatarEixoY} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }} formatter={(v: any) => [formatadorMoeda.format(v)]} />
                    <Legend />
                    <Bar dataKey="Despesa" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Receita" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Gráfico 2: Autossuficiência */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
              <h2 className="text-lg font-semibold mb-4 text-slate-200">Suficiência Orçamentária — Comparativo com a Média (%)</h2>
              <div className="h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dadosGraficoFocadoPercentual} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} />
                    <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }} formatter={(v: any) => [`${v}%`, "Autossuficiência"]} />
                    <Legend />
                    <Bar dataKey="Cobertura" name="Autossuficiência %" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* 3. Tabela Completa de Ranking com Destaque Dinâmico */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
            <h2 className="text-lg font-semibold mb-4 text-slate-200">Ranking Completo de Autossuficiência — Sebrae SP (Q1)</h2>
            <div className="rounded-xl border border-slate-800 bg-slate-900/30 overflow-hidden">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-900/80 text-slate-400 border-b border-slate-800 font-semibold uppercase tracking-wider">
                    <th className="p-3">Posição</th>
                    <th className="p-3">Unidade Organizacional</th>
                    <th className="p-3 text-center">Grau de Cobertura 2025</th>
                    <th className="p-3 text-center">Grau de Cobertura 2026</th>
                    <th className="p-3 text-center">Variação Real %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50 font-sans">
                  {listaUnidadesRankingOrdenadas.map((unidade, index) => {
                    const isSelected = unidade === unidadeSelecionada;
                    const cobA = mapaUnidadesRanking[unidade]["2025"] || 0;
                    const cobB = mapaUnidadesRanking[unidade]["2026"] || 0;
                    const deltaRanking = cobA > 0 ? cobB - cobA : 0;
                    return (
                      <tr
                        key={unidade}
                        className={`transition-colors ${isSelected
                          ? 'bg-cyan-500/10 border-l-4 border-cyan-400 hover:bg-cyan-500/15'
                          : 'hover:bg-slate-900/30'
                        }`}
                      >
                        <td className="p-3 font-semibold text-slate-400">{index + 1}º</td>
                        <td className={`p-3 font-medium ${isSelected ? 'text-cyan-300 font-bold' : 'text-slate-300'} truncate max-w-[250px]`}>{unidade}</td>
                        <td className="p-3 text-center text-cyan-400 font-mono font-semibold">{cobA.toFixed(2)}%</td>
                        <td className="p-3 text-center text-emerald-400 font-mono font-bold">{cobB.toFixed(2)}%</td>
                        <td className="p-3 text-center">{renderizarTagVariacao(deltaRanking)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
