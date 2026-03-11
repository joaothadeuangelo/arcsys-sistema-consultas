// ==========================================
// MÓDULO 1: CONSULTA DE PLACA
// ==========================================

// 1. TRATAMENTO EM TEMPO REAL (Impede caracteres inválidos e força maiúscula)
const placaInputField = document.getElementById('placaInput');
if (placaInputField) {
    placaInputField.addEventListener('input', function (e) {
        this.value = this.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    });
}

// ==========================================
// RENDERIZADOR JSON → CARDS PROFISSIONAIS
// ==========================================

// Mapeamento de chaves técnicas → rótulos legíveis
const LABELS_PLACA = {
    placa: "Placa",
    marcaModelo: "Marca / Modelo",
    cor: "Cor",
    anoFabricacao: "Ano Fabricação",
    anoModelo: "Ano Modelo",
    chassi: "Chassi",
    motor: "Motor",
    combustivel: "Combustível",
    potencia: "Potência",
    cilindradas: "Cilindradas",
    capacidadePassageiros: "Passageiros",
    tipoVeiculo: "Tipo de Veículo",
    especieVeiculo: "Espécie",
    carroceria: "Carroceria",
    nacionalidade: "Nacionalidade",
    municipio: "Município",
    uf: "UF",
    situacaoVeiculo: "Situação do Veículo",
    codigoSituacao: "Código Situação",
    indicadorRemarcacaoChassi: "Remarcação Chassi",
    indicadorRouboFurto: "Roubo / Furto",
    restricao1: "Restrição 1",
    restricao2: "Restrição 2",
    restricao3: "Restrição 3",
    restricao4: "Restrição 4",
    dataEmplacamento: "Data Emplacamento",
    dataLimiteRestricaoTributaria: "Limite Restrição Tributária",
    dataAtualizacao: "Última Atualização",
    renavam: "RENAVAM",
    codigoMarcaModelo: "Cód. Marca/Modelo",
    codigoMunicipio: "Cód. Município",
    codigoCor: "Cód. Cor",
    codigoTipoVeiculo: "Cód. Tipo Veículo",
    codigoEspecieVeiculo: "Cód. Espécie",
    codigoCarroceria: "Cód. Carroceria",
    codigoCombustivel: "Cód. Combustível",
    codigoNacionalidade: "Cód. Nacionalidade",
    cmt: "CMT (kg)",
    pbt: "PBT (kg)",
    eixos: "Eixos",
    procedencia: "Procedência",
    linha: "Linha",
    categoriaMontagem: "Categoria Montagem"
};

// Agrupamento semântico dos campos
const SECOES_PLACA = [
    {
        titulo: "Dados do Veículo",
        campos: ["placa", "marcaModelo", "cor", "anoFabricacao", "anoModelo", "tipoVeiculo", "especieVeiculo", "carroceria", "combustivel", "potencia", "cilindradas", "capacidadePassageiros", "nacionalidade", "procedencia", "categoriaMontagem", "linha"]
    },
    {
        titulo: "Identificação",
        campos: ["chassi", "motor", "renavam", "indicadorRemarcacaoChassi"]
    },
    {
        titulo: "Registro",
        campos: ["municipio", "uf", "dataEmplacamento", "dataAtualizacao"]
    },
    {
        titulo: "Situação Legal",
        campos: ["situacaoVeiculo", "indicadorRouboFurto", "restricao1", "restricao2", "restricao3", "restricao4", "dataLimiteRestricaoTributaria"]
    },
    {
        titulo: "Dados Técnicos",
        campos: ["cmt", "pbt", "eixos", "codigoMarcaModelo", "codigoMunicipio", "codigoCor", "codigoTipoVeiculo", "codigoEspecieVeiculo", "codigoCarroceria", "codigoCombustivel", "codigoNacionalidade", "codigoSituacao"]
    }
];

// Campos cujo valor merece badge de status
const CAMPOS_STATUS_POSITIVO = ["NAO", "NÃO", "NORMAL", "NADA CONSTA", "SEM RESTRICAO", "SEM RESTRIÇÃO"];
const CAMPOS_STATUS_NEGATIVO = ["SIM", "ROUBO", "FURTO", "ALIENACAO", "ALIENAÇÃO", "RESTRICAO", "RESTRIÇÃO"];

function classificarBadge(chave, valor) {
    const upper = String(valor).toUpperCase().trim();
    if (CAMPOS_STATUS_POSITIVO.includes(upper)) return "success";
    // Só marca como perigo se NÃO começar com "SEM "
    for (const termo of CAMPOS_STATUS_NEGATIVO) {
        if (upper.includes(termo) && !upper.startsWith("SEM ")) return "danger";
    }
    return null;
}

function renderizarDadosPlaca(dados) {
    if (typeof dados === "string") {
        // Fallback para cache legado (texto formatado antigo)
        return formatarTexto(dados);
    }

    let html = '<div class="relatorio-wrapper">';
    html += '<div class="relatorio-header">CONSULTA DE PLACA</div>';

    // Rastreia quais chaves foram renderizadas para não perder nenhum campo novo da API
    const chavesRenderizadas = new Set();

    for (const secao of SECOES_PLACA) {
        const linhas = [];
        for (const campo of secao.campos) {
            const valor = dados[campo];
            if (valor === null || valor === undefined || valor === "") continue;
            chavesRenderizadas.add(campo);

            const label = LABELS_PLACA[campo] || campo.replace(/([A-Z])/g, ' $1').trim();
            const valorStr = String(valor);
            const tipoBadge = classificarBadge(campo, valorStr);

            let valorHtml;
            if (tipoBadge === "success") {
                valorHtml = `<span class="badge badge-success">✅ ${valorStr}</span>`;
            } else if (tipoBadge === "danger") {
                valorHtml = `<span class="badge badge-danger">🚨 ${valorStr}</span>`;
            } else {
                valorHtml = `<span class="data-value">${valorStr}</span>`;
            }

            linhas.push(`<div class="data-row"><div class="row-label">${label}</div><div class="row-value">${valorHtml}</div></div>`);
        }

        if (linhas.length === 0) continue;
        html += `<div class="relatorio-section"><div class="section-title">${secao.titulo}</div><div class="section-body">${linhas.join('')}</div></div>`;
    }

    // Campos extras que a API pode retornar e que não estão mapeados
    const camposExtras = [];
    for (const [chave, valor] of Object.entries(dados)) {
        if (chavesRenderizadas.has(chave)) continue;
        if (valor === null || valor === undefined || valor === "") continue;
        if (typeof valor === "object") continue; // Ignora objetos aninhados por segurança
        chavesRenderizadas.add(chave);

        const label = LABELS_PLACA[chave] || chave.replace(/([A-Z])/g, ' $1').trim();
        camposExtras.push(`<div class="data-row"><div class="row-label">${label}</div><div class="row-value"><span class="data-value">${String(valor)}</span></div></div>`);
    }

    if (camposExtras.length > 0) {
        html += `<div class="relatorio-section"><div class="section-title">Outros Dados</div><div class="section-body">${camposExtras.join('')}</div></div>`;
    }

    html += '</div>';
    return html;
}

// Gera texto limpo do JSON para a função de copiar
function gerarTextoPlaca(dados) {
    if (typeof dados === "string") return dados;
    let linhas = ["CONSULTA DE PLACA", ""];
    for (const [chave, valor] of Object.entries(dados)) {
        if (valor === null || valor === undefined || valor === "" || typeof valor === "object") continue;
        const label = LABELS_PLACA[chave] || chave.replace(/([A-Z])/g, ' $1').trim();
        linhas.push(`${label}: ${valor}`);
    }
    linhas.push("", "━━━━━━━━━━━━━━━━━━━━━━", "Consulta realizada via ARCSYS");
    return linhas.join("\n");
}

// 2. FUNÇÃO PRINCIPAL DE CONSULTA
async function fazerConsulta() {
    const input = document.getElementById('placaInput');
    const placa = input.value; 

    const btn = document.getElementById('btnConsultarPlaca'); 
    const resultContainer = document.getElementById('resultadoContainer');
    const resultBox = document.getElementById('resultado');
    const loader = document.getElementById('loader');

    const regexPlaca = /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/;

    // Validação de Segurança (Formato da Placa)
    if (!regexPlaca.test(placa)) {
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 400);
        
        resultBox.innerHTML = `
            <div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">
                ❌ Placa Inválida!<br><br>
                Utilize um formato válido no Brasil:<br>
                Padrão Antigo: <span class='destaque-codigo'>ABC1234</span><br>
                Padrão Mercosul: <span class='destaque-codigo'>ABC1D23</span>
            </div>
        `;
        resultContainer.style.display = 'block';
        return; 
    }

    // Verificação do Cloudflare Turnstile
    const turnstileResponse = document.querySelector('[name="cf-turnstile-response"]')?.value;
    
    if (!turnstileResponse) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">🤖 Por favor, valide o captcha.</div>`;
        resultContainer.style.display = 'block';
        return;
    }

    btn.disabled = true;
    resultContainer.style.display = 'none';
    loader.style.display = 'block';
    limparAcoesDinamicas();

    loader.innerHTML = `
        <div class="loader-content">
            <div class="spinner"></div> 
            Processando sua consulta, por favor aguarde...
        </div>`;

    try {
        const response = await fetch(`/api/consultar/${placa}`, {
            method: 'GET',
            headers: {
                'X-Turnstile-Token': turnstileResponse
            }
        });
        
        const data = await response.json();

        if (data.sucesso) {
            // Armazena texto limpo para cópia
            textoPuro = gerarTextoPlaca(data.dados);
            
            if (data.cache) {
                resultBox.innerHTML = "<span class='cache-aviso'>⚡ Recuperado do Banco de Dados</span><br>" + renderizarDadosPlaca(data.dados);
                btn.disabled = false;
            } else {
                resultBox.innerHTML = renderizarDadosPlaca(data.dados);
                iniciarCooldown(120, 'btnConsultarPlaca', 'Consultar');
            }
            injetarAcoesResultado(resultBox, true);
        } else {
            textoPuro = data.erro || "";
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${data.erro || "Erro desconhecido."}</div>`;
            btn.disabled = false;
        }
        
        resultContainer.style.display = 'block';
    } catch (error) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">❌ Erro de conexão com o servidor. O sistema pode estar offline.</div>`;
        resultContainer.style.display = 'block';
        btn.disabled = false;
    } finally {
        loader.style.display = 'none';
        if (typeof turnstile !== 'undefined') {
            turnstile.reset();
        }
    }
}

// 3. EVENTO DE TECLADO (ENTER)
document.getElementById('placaInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarPlaca').disabled) {
        fazerConsulta();
    }
});