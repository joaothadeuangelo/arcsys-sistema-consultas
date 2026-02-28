let tempoLeitura = 5; 
let timerInterval;

window.onload = function() {
    // 1. VERIFICAÇÃO DE MANUTENÇÃO
    if (window.SISTEMA_EM_MANUTENCAO) {
        document.querySelector('.container').style.display = 'none';
        document.getElementById('modalAviso').style.display = 'none';
        document.getElementById('modalManutencao').style.display = 'flex';
        return; 
    }

    // 2. DISPARA O TIMER DO ANÚNCIO (E LIBERA AUTOMATICAMENTE)
    const btn = document.getElementById('btnAceitarModal');

    timerInterval = setInterval(() => {
        if (tempoLeitura > 0) {
            btn.innerText = `⏳ EXIBINDO ANÚNCIO... (${tempoLeitura}s)`;
            tempoLeitura--;
        } else {
            clearInterval(timerInterval);
            // O tempo acabou, libera o botão direto!
            btn.disabled = false;
            btn.classList.remove('bloqueado');
            btn.classList.add('liberado');
            btn.innerText = "ENTRAR NO SISTEMA GRATUITO";
        }
    }, 1000);
}

function fecharModal() {
    document.getElementById('modalAviso').style.display = 'none';
}

// ==========================================
// FUNÇÕES DE LÓGICA E APRESENTAÇÃO
// ==========================================
let textoPuro = "";
let loaderInterval;

const frasesTroll = [
    "Hackeando os servidores do Detran... 🕵️‍♂️",
    "Procurando multas que você não pagou... 💸",
    "Acordando o estagiário pra buscar a placa... 😴",
    "Subornando um despachante... 🤫",
    "Calculando o IPVA atrasado (é muito)... 📉",
    "Perguntando pro frentista do posto... ⛽",
    "Descobrindo se é carro de leilão... 🔨",
    "Calma aí apressado, a internet tá lenta... 🐢",
    "Quase lá, não aperta F5 pelo amor de Deus... 🚨"
];

function formatarTexto(texto) {
    let linhas = texto.split('\n');
    let htmlFinal = '<div class="relatorio-wrapper">';
    let inSection = false;

    linhas.forEach(linha => {
        let l = linha.trim();
        if (!l) return; // Pula linhas em branco vazias

        // Limpa o bullet point inicial do bot, se houver
        if (l.startsWith('•')) l = l.substring(1).trim();

        // 1. Título Geral (Consulta Completa)
        if (l.includes('🕵️')) {
            htmlFinal += `<div class="relatorio-header">${l.replace(/\*\*/g, '')}</div>`;
            return;
        }

        // 2. Criação dos Cartões (Seções) - Identifica se é título (tudo maiúsculo sem ":")
        if ((l.startsWith('**') && l.endsWith('**') && !l.includes(':')) || (l.match(/^[A-ZÍÁÉÓÚÇ\s/]+$/) && l.length > 4 && !l.includes(':'))) {
            if (inSection) htmlFinal += '</div></div>'; // Fecha o cartão anterior
            let titulo = l.replace(/\*\*/g, '').trim();
            htmlFinal += `<div class="relatorio-section">
                            <div class="section-title">${titulo}</div>
                            <div class="section-body">`;
            inSection = true;
            return;
        }

        // 3. Criação das Linhas de Dados (Chave: Valor)
        if (l.includes(':')) {
            if (!inSection) {
                htmlFinal += `<div class="relatorio-section"><div class="section-body">`;
                inSection = true;
            }

            let partes = l.split(':');
            let label = partes[0].replace(/\*\*/g, '').trim();
            let rawValue = partes.slice(1).join(':').trim(); // O valor real após os ":"

            let cleanValue = rawValue.replace(/`/g, '').replace(/\*\*/g, '').trim();
            let upperValue = cleanValue.toUpperCase();
            let valHtml = '';

            // Inteligência das Etiquetas (Badges)
            if (['NÃO', 'NAO', 'SEM RESTRICAO', 'SEM RESTRIÇÃO', 'NORMAL', 'NADA CONSTA'].includes(upperValue)) {
                valHtml = `<span class="badge badge-success">✅ ${cleanValue}</span>`;
            }
            else if (upperValue === 'SIM' || upperValue.includes('RESTRICAO') || upperValue.includes('RESTRIÇÃO') || upperValue.includes('ROUBO') || upperValue.includes('FURTO') || upperValue.includes('ALIENACAO')) {
                // Se tiver a palavra restrição, mas NÃO for "Sem restrição"
                if (!upperValue.includes('SEM ')) {
                    valHtml = `<span class="badge badge-danger">🚨 ${cleanValue}</span>`;
                } else {
                    valHtml = `<span class="data-value">${cleanValue}</span>`;
                }
            }
            else if (['SEM INFORMAÇÃO', 'SEM INFORMACAO', 'NÃO APLICAVEL', 'NãO APLICAVEL', 'NAO APLICAVEL'].includes(upperValue)) {
                valHtml = `<span class="badge badge-warning">⚠️ ${cleanValue}</span>`;
            } else {
                valHtml = `<span class="data-value">${cleanValue}</span>`; // Valor comum em fonte de máquina
            }

            htmlFinal += `<div class="data-row">
                            <div class="row-label">${label}</div>
                            <div class="row-value">${valHtml}</div>
                          </div>`;
        }
    });

    if (inSection) htmlFinal += '</div></div>'; // Garante que o último cartão feche
    htmlFinal += '</div>';

    return htmlFinal;
}

function iniciarCooldown(segundos) {
    const btn = document.getElementById('btnConsultar');
    let tempoRestante = segundos;
    btn.disabled = true;

    const intervalo = setInterval(() => {
        btn.innerText = `Aguarde ${tempoRestante}s`;
        tempoRestante--;

        if (tempoRestante < 0) {
            clearInterval(intervalo);
            btn.innerText = "Consultar";
            btn.disabled = false;
        }
    }, 1000);
}

async function fazerConsulta() {
    const input = document.getElementById('placaInput');
    const placa = input.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    input.value = placa; 

    const btn = document.getElementById('btnConsultar');
    const resultContainer = document.getElementById('resultadoContainer');
    const resultBox = document.getElementById('resultado');
    const loader = document.getElementById('loader');

    const regexPlaca = /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/;

    if (!regexPlaca.test(placa)) {
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 400);
        
        resultBox.innerHTML = `
            <strong>⚠️ Placa Inválida.</strong><br><br>
            Não inventa moda! Utilize um formato válido no Brasil:<br><br>
            Padrão Antigo: <span class='destaque-codigo'>ABC1234</span><br>
            Padrão Mercosul: <span class='destaque-codigo'>ABC1D23</span>
        `;
        resultContainer.style.display = 'block';
        return; 
    }

    btn.disabled = true;
    resultContainer.style.display = 'none';
    loader.style.display = 'block';

    let fraseIndex = 0;
    loader.innerText = frasesTroll[0];
    loaderInterval = setInterval(() => {
        fraseIndex = (fraseIndex + 1) % frasesTroll.length;
        loader.innerText = frasesTroll[fraseIndex];
    }, 2500);

    try {
        const response = await fetch(`/api/consultar/${placa}`);
        const data = await response.json();

        if (data.sucesso) {
            textoPuro = data.dados; 
            
            if (data.cache) {
                resultBox.innerHTML = "<span class='cache-aviso'>⚡ Recuperado do Banco de Dados</span><br>" + formatarTexto(data.dados);
                btn.disabled = false;
            } else {
                resultBox.innerHTML = formatarTexto(data.dados);
                iniciarCooldown(60);
            }
        } else {
            textoPuro = data.dados;
            resultBox.innerHTML = `<strong>Erro:</strong> ${formatarTexto(data.dados)}`;
            btn.disabled = false;
        }
        
        resultContainer.style.display = 'block';
    } catch (error) {
        resultBox.innerHTML = "Erro de conexão com o servidor. O sistema pode estar offline.";
        resultContainer.style.display = 'block';
        btn.disabled = false;
    } finally {
        clearInterval(loaderInterval);
        loader.style.display = 'none';
        loader.innerText = "Processando requisição... ⏳"; 
    }
}

// ==========================================
// FUNÇÃO DE FAXINA PARA A ÁREA DE TRANSFERÊNCIA
// ==========================================
function limparTextoParaCopiar(texto) {
    let textoLimpo = texto
        .replace(/\*\*/g, '') 
        .replace(/`/g, '')    
        .replace(/\n{3,}/g, '\n\n') 
        .trim(); 

    textoLimpo += "\n\n━━━━━━━━━━━━━━━━━━━━━━\n🔍 Consulta realizada via ARCSYS";
    
    return textoLimpo;
}

function copiarTexto() {
    const textoFormatado = limparTextoParaCopiar(textoPuro);

    navigator.clipboard.writeText(textoFormatado).then(() => {
        const btnCopiar = document.querySelector('.btn-copiar');
        const textoOriginal = btnCopiar.innerText;
        btnCopiar.innerText = "✅ Relatório Copiado Limpo!";
        btnCopiar.style.backgroundColor = "#27ae60";
        
        setTimeout(() => {
            btnCopiar.innerText = textoOriginal;
            btnCopiar.style.backgroundColor = "#2b5278";
        }, 2000);
    }).catch(err => {
        alert("Erro ao copiar: " + err);
    });
}

document.getElementById('placaInput').addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultar').disabled) {
        fazerConsulta();
    }
});