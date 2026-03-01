// ==========================================
// VARIÁVEIS GLOBAIS E UTILITÁRIOS
// ==========================================
let tempoLeitura = 5; 
let timerInterval;
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

// ==========================================
// INICIALIZAÇÃO E MODAIS (COM MEMÓRIA DE SESSÃO)
// ==========================================
window.onload = function() {
    // 1. VERIFICAÇÃO DE MANUTENÇÃO (Prioridade Máxima)
    if (window.SISTEMA_EM_MANUTENCAO) {
        document.querySelector('.container').style.display = 'none';
        document.getElementById('modalAviso').style.display = 'none';
        document.getElementById('modalManutencao').style.display = 'flex';
        return; 
    }

    // 2. LÓGICA DO MODAL DE AVISO
    const modalAviso = document.getElementById('modalAviso');
    const btn = document.getElementById('btnAceitarModal');

    // Verifica na memória do navegador se o usuário JÁ fechou o modal hoje
    if (!sessionStorage.getItem('avisoFechado')) {
        // Se NÃO fechou, mostra o modal e inicia o timer
        if (modalAviso && btn) {
            modalAviso.style.display = 'flex'; // Torna visível
            
            timerInterval = setInterval(() => {
                if (tempoLeitura > 0) {
                    btn.innerText = `⏳ EXIBINDO ANÚNCIO... (${tempoLeitura}s)`;
                    tempoLeitura--;
                } else {
                    clearInterval(timerInterval);
                    btn.disabled = false;
                    btn.classList.remove('bloqueado');
                    btn.classList.add('liberado');
                    btn.innerText = "ENTRAR NO SISTEMA GRATUITO 🚀";
                }
            }, 1000);
        }
    } else {
        // Se já fechou antes, garante que continue escondido
        if (modalAviso) modalAviso.style.display = 'none';
    }
}

function fecharModal() {
    document.getElementById('modalAviso').style.display = 'none';
    // SALVA NA MEMÓRIA: Marca o modal como visto para não encher o saco nas outras páginas
    sessionStorage.setItem('avisoFechado', 'true');
}

// ... (Daqui pra baixo o global.js continua normal, com o formatarTexto, etc) ...
// ==========================================
// FORMATAÇÃO E COOLDOWN
// ==========================================
function formatarTexto(texto) {
    let linhas = texto.split('\n');
    let htmlFinal = '<div class="relatorio-wrapper">';
    let inSection = false;

    linhas.forEach(linha => {
        let l = linha.trim();
        if (!l) return;

        if (l.startsWith('•')) l = l.substring(1).trim();

        if (l.includes('🕵️')) {
            htmlFinal += `<div class="relatorio-header">${l.replace(/\*\*/g, '')}</div>`;
            return;
        }

        if ((l.startsWith('**') && l.endsWith('**') && !l.includes(':')) || (l.match(/^[A-ZÍÁÉÓÚÇ\s/]+$/) && l.length > 4 && !l.includes(':'))) {
            if (inSection) htmlFinal += '</div></div>';
            let titulo = l.replace(/\*\*/g, '').trim();
            htmlFinal += `<div class="relatorio-section"><div class="section-title">${titulo}</div><div class="section-body">`;
            inSection = true;
            return;
        }

        if (l.includes(':')) {
            if (!inSection) {
                htmlFinal += `<div class="relatorio-section"><div class="section-body">`;
                inSection = true;
            }

            let partes = l.split(':');
            let label = partes[0].replace(/\*\*/g, '').trim();
            let rawValue = partes.slice(1).join(':').trim();

            let cleanValue = rawValue.replace(/`/g, '').replace(/\*\*/g, '').trim();
            let upperValue = cleanValue.toUpperCase();
            let valHtml = '';

            if (['NÃO', 'NAO', 'SEM RESTRICAO', 'SEM RESTRIÇÃO', 'NORMAL', 'NADA CONSTA'].includes(upperValue)) {
                valHtml = `<span class="badge badge-success">✅ ${cleanValue}</span>`;
            } else if (upperValue === 'SIM' || upperValue.includes('RESTRICAO') || upperValue.includes('RESTRIÇÃO') || upperValue.includes('ROUBO') || upperValue.includes('FURTO') || upperValue.includes('ALIENACAO')) {
                if (!upperValue.includes('SEM ')) {
                    valHtml = `<span class="badge badge-danger">🚨 ${cleanValue}</span>`;
                } else {
                    valHtml = `<span class="data-value">${cleanValue}</span>`;
                }
            } else if (['SEM INFORMAÇÃO', 'SEM INFORMACAO', 'NÃO APLICAVEL', 'NãO APLICAVEL', 'NAO APLICAVEL'].includes(upperValue)) {
                valHtml = `<span class="badge badge-warning">⚠️ ${cleanValue}</span>`;
            } else {
                valHtml = `<span class="data-value">${cleanValue}</span>`;
            }

            htmlFinal += `<div class="data-row"><div class="row-label">${label}</div><div class="row-value">${valHtml}</div></div>`;
        }
    });

    if (inSection) htmlFinal += '</div></div>';
    htmlFinal += '</div>';

    return htmlFinal;
}

function iniciarCooldown(segundos, btnId, textoOriginal) {
    const btn = document.getElementById(btnId);
    let tempoRestante = segundos;
    btn.disabled = true;

    const intervalo = setInterval(() => {
        btn.innerText = `Aguarde ${tempoRestante}s`;
        tempoRestante--;

        if (tempoRestante < 0) {
            clearInterval(intervalo);
            btn.innerText = textoOriginal;
            btn.disabled = false;
        }
    }, 1000);
}

// ==========================================
// FUNÇÕES DE ÁREA DE TRANSFERÊNCIA
// ==========================================
function limparTextoParaCopiar(texto) {
    let textoLimpo = texto.replace(/\*\*/g, '').replace(/`/g, '').replace(/\n{3,}/g, '\n\n').trim(); 
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