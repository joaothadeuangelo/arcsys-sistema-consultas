// ==========================================
// MÓDULO 1: CONSULTA DE PLACA
// ==========================================

// 1. TRATAMENTO EM TEMPO REAL (Impede caracteres inválidos e força maiúscula)
const placaInputField = document.getElementById('placaInput');
let timerCooldownPlaca = null;

function extrairSegundosCooldownPlaca(mensagem) {
    const match = String(mensagem || '').match(/(\d+)\s*segundos?/i);
    return match ? parseInt(match[1], 10) : 0;
}

function iniciarCooldownVisualPlaca(segundos, btn, textoOriginal) {
    if (!btn || !Number.isFinite(segundos) || segundos <= 0) return;

    if (timerCooldownPlaca) {
        clearInterval(timerCooldownPlaca);
        timerCooldownPlaca = null;
    }

    let restante = segundos;
    btn.disabled = true;
    btn.textContent = `Aguarde ${restante}s...`;

    timerCooldownPlaca = setInterval(() => {
        restante -= 1;
        if (restante <= 0) {
            clearInterval(timerCooldownPlaca);
            timerCooldownPlaca = null;
            btn.disabled = false;
            btn.textContent = textoOriginal;
            return;
        }
        btn.textContent = `Aguarde ${restante}s...`;
    }, 1000);
}

if (placaInputField) {
    placaInputField.addEventListener('input', function () {
        this.value = this.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    });
}

// ==========================================
// RENDERIZADOR JSON → CARDS PROFISSIONAIS
// (UX limpa em 4 blocos semânticos)
// ==========================================

// Badges de status
const CAMPOS_STATUS_POSITIVO = ["NAO", "NÃO", "NORMAL", "NADA CONSTA", "SEM RESTRICAO", "SEM RESTRIÇÃO"];
const CAMPOS_STATUS_NEGATIVO = ["SIM", "ROUBO", "FURTO", "ALIENACAO", "ALIENAÇÃO", "RESTRICAO", "RESTRIÇÃO"];

function classificarBadge(chave, valor) {
    const upper = String(valor).toUpperCase().trim();
    if (CAMPOS_STATUS_POSITIVO.includes(upper)) return "success";
    for (const termo of CAMPOS_STATUS_NEGATIVO) {
        if (upper.includes(termo) && !upper.startsWith("SEM ")) return "danger";
    }
    return null;
}

function normalizarValor(chave, valor) {
    if (typeof valor === "boolean") {
        return valor ? "SIM" : "NÃO";
    }
    return String(valor);
}

function obterPrimeiroValor(dados, chaves) {
    for (const chave of chaves) {
        if (Object.prototype.hasOwnProperty.call(dados, chave)) {
            const valor = dados[chave];
            if (valor !== null && valor !== undefined && valor !== "") {
                return valor;
            }
        }
    }
    return null;
}

function formatarDataBR(valor) {
    if (valor === null || valor === undefined || valor === "") return "Não informado";
    const texto = String(valor).trim();
    const match = texto.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return texto;
    return `${match[3]}/${match[2]}/${match[1]}`;
}

function valorOuNaoInformado(valor) {
    if (valor === null || valor === undefined || valor === "") return "Não informado";
    return normalizarValor("", valor);
}

function normalizarRestricao(valor) {
    if (valor === null || valor === undefined || valor === "") return "";
    const texto = String(valor).trim();
    const textoUpper = texto.toUpperCase();
    if (textoUpper === "SEM RESTRICAO" || textoUpper === "SEM RESTRIÇÃO" || textoUpper === "00") return "";
    return texto.replace(/_/g, " ");
}

function construirResumoPlaca(dados) {
    const placaMercosul = obterPrimeiroValor(dados, ["placa_mercosul"]);
    const placaAntiga = obterPrimeiroValor(dados, ["placa_antiga"]);
    const marcaModelo = obterPrimeiroValor(dados, ["descricaoMarcaModelo"]);
    const cor = obterPrimeiroValor(dados, ["descricaoCor"]);
    const anoFabricacao = obterPrimeiroValor(dados, ["anoFabricacao"]);
    const anoModelo = obterPrimeiroValor(dados, ["anoModelo"]);
    const chassi = obterPrimeiroValor(dados, ["chassi"]);
    const renavam = obterPrimeiroValor(dados, ["codigoRenavam"]);
    const motor = obterPrimeiroValor(dados, ["numeroMotor"]);
    const tipoVeiculo = obterPrimeiroValor(dados, ["descricaoTipoVeiculo"]);
    const especie = obterPrimeiroValor(dados, ["descricaoEspecieVeiculo"]);
    const combustivel = obterPrimeiroValor(dados, ["descricaoCombustivel"]);
    const procedencia = obterPrimeiroValor(dados, ["procedencia"]);
    const nomeProprietario = obterPrimeiroValor(dados, ["nomeProprietario"]);
    const documentoProprietario = obterPrimeiroValor(dados, ["numeroIdentificacaoProprietario"]);
    const situacao = obterPrimeiroValor(dados, ["situacao"]);
    const rouboFurto = obterPrimeiroValor(dados, ["indicadorRouboFurto"]);
    const municipio = obterPrimeiroValor(dados, ["descricaoMunicipioEmplacamento", "municipio"]);
    const uf = obterPrimeiroValor(dados, ["ufJurisdicao", "uf"]);
    const anoLicenciamento = obterPrimeiroValor(dados, ["anoExercicioLicenciamentoPago", "anoLicenciamentoPago", "anoLicenciamento", "exercicioLicenciamento"]);
    const emissaoCrlv = obterPrimeiroValor(dados, ["dataEmissaoCRLV", "dataEmissaoCrlv", "data Emissao C R L V"]);

    const municipioUf = (municipio && uf)
        ? `${String(municipio).toUpperCase()} - ${String(uf).toUpperCase()}`
        : (municipio ? String(municipio).toUpperCase() : (uf ? String(uf).toUpperCase() : "Não informado"));

    const tipoEspecie = (tipoVeiculo && especie)
        ? `${tipoVeiculo} / ${especie}`
        : valorOuNaoInformado(tipoVeiculo || especie);

    const anoFabModelo = (anoFabricacao && anoModelo)
        ? `${anoFabricacao}/${anoModelo}`
        : valorOuNaoInformado(anoFabricacao || anoModelo);

    const restricoes = [
        normalizarRestricao(obterPrimeiroValor(dados, ["descricaoRestricao1", "restricao1"])),
        normalizarRestricao(obterPrimeiroValor(dados, ["descricaoRestricao2", "restricao2"])),
        normalizarRestricao(obterPrimeiroValor(dados, ["descricaoRestricao3", "restricao3"])),
        normalizarRestricao(obterPrimeiroValor(dados, ["descricaoRestricao4", "restricao4"]))
    ].filter(Boolean);

    return {
        veiculo: {
            placaMercosul: valorOuNaoInformado(placaMercosul),
            placaAntiga: valorOuNaoInformado(placaAntiga),
            marcaModelo: valorOuNaoInformado(marcaModelo),
            cor: valorOuNaoInformado(cor),
            anoFabModelo,
            chassi: valorOuNaoInformado(chassi),
            renavam: valorOuNaoInformado(renavam),
            motor: valorOuNaoInformado(motor),
            tipoEspecie,
            combustivel: valorOuNaoInformado(combustivel),
            procedencia: valorOuNaoInformado(procedencia)
        },
        proprietario: {
            nome: valorOuNaoInformado(nomeProprietario),
            documento: valorOuNaoInformado(documentoProprietario)
        },
        legal: {
            situacao: valorOuNaoInformado(situacao),
            rouboFurto: valorOuNaoInformado(rouboFurto),
            restricoes
        },
        registro: {
            municipioUf,
            anoLicenciamento: valorOuNaoInformado(anoLicenciamento),
            emissaoCrlv: formatarDataBR(emissaoCrlv)
        }
    };
}

function renderizarLinha(label, valor, badgeForce = null) {
    const vazio = (valor === "Não informado");
    let valorHtml;

    if (vazio) {
        valorHtml = '<span class="badge badge-warning">⚠️ Não informado</span>';
    } else {
        const tipoBadge = badgeForce || classificarBadge(label, valor);
        if (tipoBadge === "success") {
            valorHtml = `<span class="badge badge-success">✅ ${valor}</span>`;
        } else if (tipoBadge === "danger") {
            valorHtml = `<span class="badge badge-danger">🚨 ${valor}</span>`;
        } else {
            valorHtml = `<span class="data-value">${valor}</span>`;
        }
    }

    return `<div class="data-row"><div class="row-label">${label}</div><div class="row-value">${valorHtml}</div></div>`;
}

function renderizarDadosPlaca(dados) {
    if (typeof dados === "string") {
        return formatarTexto(dados);
    }

    const resumo = construirResumoPlaca(dados);
    let html = '<div class="relatorio-wrapper">';
    html += '<div class="relatorio-header">CONSULTA DE PLACA</div>';

    const linhasVeiculo = [
        renderizarLinha("Placa Mercosul", resumo.veiculo.placaMercosul),
        renderizarLinha("Placa Antiga", resumo.veiculo.placaAntiga),
        renderizarLinha("Marca/Modelo", resumo.veiculo.marcaModelo),
        renderizarLinha("Cor", resumo.veiculo.cor),
        renderizarLinha("Ano Fab/Modelo", resumo.veiculo.anoFabModelo),
        renderizarLinha("Chassi", resumo.veiculo.chassi),
        renderizarLinha("RENAVAM", resumo.veiculo.renavam),
        renderizarLinha("Motor", resumo.veiculo.motor),
        renderizarLinha("Tipo/Espécie", resumo.veiculo.tipoEspecie),
        renderizarLinha("Combustível", resumo.veiculo.combustivel),
        renderizarLinha("Procedência", resumo.veiculo.procedencia)
    ];

    const linhasProprietario = [
        renderizarLinha("Nome do Proprietário", resumo.proprietario.nome),
        renderizarLinha("Documento (CPF/CNPJ)", resumo.proprietario.documento)
    ];

    const linhasLegal = [
        renderizarLinha("Situação", resumo.legal.situacao),
        renderizarLinha("Roubo/Furto", resumo.legal.rouboFurto)
    ];
    if (resumo.legal.restricoes.length > 0) {
        for (const restricao of resumo.legal.restricoes) {
            linhasLegal.push(renderizarLinha("Restrição", restricao, "danger"));
        }
    } else {
        linhasLegal.push(renderizarLinha("Restrições", "Sem restrições", "success"));
    }

    const linhasRegistro = [
        renderizarLinha("Município/UF", resumo.registro.municipioUf),
        renderizarLinha("Ano Licenciamento Pago", resumo.registro.anoLicenciamento),
        renderizarLinha("Emissão CRLV", resumo.registro.emissaoCrlv)
    ];

    html += `<div class="relatorio-section"><div class="section-title">🚗 DADOS DO VEÍCULO</div><div class="section-body">${linhasVeiculo.join('')}</div></div>`;
    html += `<div class="relatorio-section"><div class="section-title">👤 DADOS DO PROPRIETÁRIO</div><div class="section-body">${linhasProprietario.join('')}</div></div>`;
    html += `<div class="relatorio-section"><div class="section-title">🚨 SITUAÇÃO LEGAL E RESTRIÇÕES</div><div class="section-body">${linhasLegal.join('')}</div></div>`;
    html += `<div class="relatorio-section"><div class="section-title">📄 REGISTRO E LICENCIAMENTO</div><div class="section-body">${linhasRegistro.join('')}</div></div>`;

    html += '</div>';
    return html;
}

// Gera texto limpo do JSON para a função de copiar
function gerarTextoPlaca(dados) {
    if (typeof dados === "string") return dados;
    const resumo = construirResumoPlaca(dados);
    const linhas = [
        "CONSULTA DE PLACA",
        "",
        "🚗 DADOS DO VEÍCULO",
        `Placa Mercosul: ${resumo.veiculo.placaMercosul}`,
        `Placa Antiga: ${resumo.veiculo.placaAntiga}`,
        `Marca/Modelo: ${resumo.veiculo.marcaModelo}`,
        `Cor: ${resumo.veiculo.cor}`,
        `Ano Fab/Modelo: ${resumo.veiculo.anoFabModelo}`,
        `Chassi: ${resumo.veiculo.chassi}`,
        `RENAVAM: ${resumo.veiculo.renavam}`,
        `Motor: ${resumo.veiculo.motor}`,
        `Tipo/Espécie: ${resumo.veiculo.tipoEspecie}`,
        `Combustível: ${resumo.veiculo.combustivel}`,
        `Procedência: ${resumo.veiculo.procedencia}`,
        "",
        "👤 DADOS DO PROPRIETÁRIO",
        `Nome do Proprietário: ${resumo.proprietario.nome}`,
        `Documento (CPF/CNPJ): ${resumo.proprietario.documento}`,
        "",
        "🚨 SITUAÇÃO LEGAL E RESTRIÇÕES",
        `Situação: ${resumo.legal.situacao}`,
        `Roubo/Furto: ${resumo.legal.rouboFurto}`
    ];

    if (resumo.legal.restricoes.length > 0) {
        for (const restricao of resumo.legal.restricoes) {
            linhas.push(`Restrição: ${restricao}`);
        }
    } else {
        linhas.push("Restrições: Sem restrições");
    }

    linhas.push(
        "",
        "📄 REGISTRO E LICENCIAMENTO",
        `Município/UF: ${resumo.registro.municipioUf}`,
        `Ano Licenciamento Pago: ${resumo.registro.anoLicenciamento}`,
        `Emissão CRLV: ${resumo.registro.emissaoCrlv}`
    );

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
    const textoOriginalBotao = btn.textContent;
    let preservarEstadoBotao = false;

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

        if (response.status === 429) {
            const mensagem429 = data.erro || 'Aguarde alguns segundos para consultar novamente.';
            const segundos = extrairSegundosCooldownPlaca(mensagem429);
            if (segundos > 0) {
                iniciarCooldownVisualPlaca(segundos, btn, textoOriginalBotao);
                preservarEstadoBotao = true;
            }
            textoPuro = mensagem429;
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${mensagem429}</div>`;
            resultContainer.style.display = 'block';
            return;
        }

        if (data.sucesso) {
            // Armazena texto limpo para cópia
            textoPuro = gerarTextoPlaca(data.dados);
            
            if (data.cache) {
                resultBox.innerHTML = "<span class='cache-aviso'>⚡ Recuperado do Banco de Dados</span><br>" + renderizarDadosPlaca(data.dados);
                btn.disabled = false;
            } else {
                resultBox.innerHTML = renderizarDadosPlaca(data.dados);
                iniciarCooldown(120, 'btnConsultarPlaca', 'Consultar');
                preservarEstadoBotao = true;
            }
            injetarAcoesResultado(resultBox, true);
        } else {
            textoPuro = data.erro || "";
            const segundos = extrairSegundosCooldownPlaca(textoPuro);
            if (segundos > 0) {
                iniciarCooldownVisualPlaca(segundos, btn, textoOriginalBotao);
                preservarEstadoBotao = true;
            }
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${data.erro || "Erro desconhecido."}</div>`;
            if (!preservarEstadoBotao) {
                btn.disabled = false;
            }
        }
        
        resultContainer.style.display = 'block';
    } catch (_) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">❌ Erro de conexão com o servidor. O sistema pode estar offline.</div>`;
        resultContainer.style.display = 'block';
        btn.disabled = false;
    } finally {
        loader.style.display = 'none';

        if (!preservarEstadoBotao) {
            btn.disabled = false;
            btn.textContent = textoOriginalBotao;
        }

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