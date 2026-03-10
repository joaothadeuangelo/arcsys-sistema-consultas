// ==========================================
// VARIÁVEIS GLOBAIS E UTILITÁRIOS
// ==========================================
let tempoLeitura = 5; 
let timerInterval;
let textoPuro = "";



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
    if (!btn) return; // Se o botão não estiver na tela atual, ignora silenciosamente

    // Limpa o timer anterior para não duplicar se clicar rápido
    if (btn.dataset.cooldownTimer) clearInterval(btn.dataset.cooldownTimer);

    let endTime;
    if (segundos > 0) {
        // Nova consulta: define o tempo de fim e salva na memória do navegador
        endTime = Date.now() + (segundos * 1000);
        localStorage.setItem(`timer_${btnId}`, endTime);
    } else {
        // Recuperando da memória (quando o usuário recarrega ou volta pra página)
        endTime = localStorage.getItem(`timer_${btnId}`);
    }

    if (!endTime) return; // Não tem timer ativo, vida que segue

    function atualizarRelogio() {
        const agora = Date.now();
        const restante = Math.ceil((endTime - agora) / 1000);

        if (restante > 0) {
            btn.disabled = true;
            btn.innerText = `Aguarde ${restante}s`;
        } else {
            // Acabou o tempo! Limpa a memória e libera o botão
            clearInterval(btn.dataset.cooldownTimer);
            btn.disabled = false;
            btn.innerText = textoOriginal;
            localStorage.removeItem(`timer_${btnId}`);
        }
    }

    atualizarRelogio(); // Chama a primeira vez instantaneamente
    
    // Se ainda tiver tempo na conta, inicia o loop do relógio
    if (btn.disabled) {
        btn.dataset.cooldownTimer = setInterval(atualizarRelogio, 1000);
    }
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
        const btnCopiar = document.querySelector('.btn-copiar-action');
        if (!btnCopiar) return;
        const textoOriginal = btnCopiar.innerHTML;
        btnCopiar.innerHTML = "✅ Copiado!";
        
        setTimeout(() => {
            btnCopiar.innerHTML = textoOriginal;
        }, 2000);
    }).catch(err => {
        alert("Erro ao copiar: " + err);
    });
}

// ==========================================
// BARRA DE AÇÕES NO TOPO DO RESULTADO
// ==========================================
function injetarAcoesResultado(resultBox, mostrarCopiar = true) {
    // Remove barra anterior se existir (evita duplicação)
    const barraExistente = resultBox.querySelector('.result-actions-header');
    if (barraExistente) barraExistente.remove();

    const barra = document.createElement('div');
    barra.className = 'result-actions-header';

    // Botão VOLTAR
    barra.innerHTML = `
        <a href="/" class="btn-action btn-voltar-action">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="19" y1="12" x2="5" y2="12"></line>
                <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            Voltar
        </a>
        ${mostrarCopiar ? '<button class="btn-action btn-copiar-action" onclick="copiarTexto()">📋 Copiar Relatório</button>' : ''}
    `;

    // Insere no TOPO da div de resultado
    resultBox.prepend(barra);
}

// ==========================================
// RECUPERAÇÃO DE COOLDOWN AO CARREGAR A TELA
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // Passamos "0" porque não queremos adicionar tempo, só checar se já existe um salvo!
    iniciarCooldown(0, 'btnConsultarPlaca', 'Consultar');
    iniciarCooldown(0, 'btnConsultarCNH', 'Consultar CNH');
    iniciarCooldown(0, 'btnConsultarDadosCPF', 'Consultar Dados');
});