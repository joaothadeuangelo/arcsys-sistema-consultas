// ==========================================
// VARIÁVEIS GLOBAIS E UTILITÁRIOS
// ==========================================
let tempoLeitura = 5; 
let timerInterval;
let textoPuro = "";

// ==========================================
// VALIDADOR MATEMÁTICO DE CPF (FRONT-END)
// ==========================================
function validarCPF(cpf) {
    // 1. Limpa pontuação e espaços
    cpf = String(cpf).replace(/\D/g, '');

    // 2. Deve ter exatamente 11 dígitos
    if (cpf.length !== 11) return false;

    // 3. Bloqueia sequências repetidas (000... a 999...)
    if (/^(\d)\1{10}$/.test(cpf)) return false;

    // 4. Cálculo do 1º dígito verificador
    let soma = 0;
    for (let i = 0; i < 9; i++) soma += Number(cpf[i]) * (10 - i);
    let digito1 = (soma * 10) % 11;
    if (digito1 === 10) digito1 = 0;
    if (digito1 !== Number(cpf[9])) return false;

    // 5. Cálculo do 2º dígito verificador
    soma = 0;
    for (let i = 0; i < 10; i++) soma += Number(cpf[i]) * (11 - i);
    let digito2 = (soma * 10) % 11;
    if (digito2 === 10) digito2 = 0;
    if (digito2 !== Number(cpf[10])) return false;

    return true;
}



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
    const linkAcessoGratis = document.getElementById('btnAceitarModal');

    // Verifica na memória do navegador se o usuário JÁ fechou o modal hoje
    if (!sessionStorage.getItem('avisoFechado')) {
        // Se NÃO fechou, mostra o modal e inicia o timer
        if (modalAviso && linkAcessoGratis) {
            modalAviso.style.display = 'flex'; // Torna visível
            linkAcessoGratis.classList.add('locked');
            linkAcessoGratis.classList.remove('unlocked');
            linkAcessoGratis.innerText = `Liberando acesso gratuito em ${tempoLeitura}s...`;
            
            timerInterval = setInterval(() => {
                if (tempoLeitura > 0) {
                    linkAcessoGratis.innerText = `Liberando acesso gratuito em ${tempoLeitura}s...`;
                    tempoLeitura--;
                } else {
                    clearInterval(timerInterval);
                    linkAcessoGratis.classList.remove('locked');
                    linkAcessoGratis.classList.add('unlocked');
                    linkAcessoGratis.innerText = "Nao quero ajuda profissional. Acessar sistema gratuito.";
                    linkAcessoGratis.onclick = fecharModal;
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
        const btnCopiar = document.querySelector('#dynamic-actions .btn-action-dynamic');
        if (!btnCopiar) return;
        const textoOriginal = btnCopiar.innerHTML;
        btnCopiar.innerHTML = "✅ Copiado!";
        setTimeout(() => { btnCopiar.innerHTML = textoOriginal; }, 2000);
    }).catch(err => {
        alert("Erro ao copiar: " + err);
    });
}

// ==========================================
// AÇÕES DINÂMICAS NO TOPO DO MÓDULO
// ==========================================
function injetarAcoesResultado(resultBox, mostrarCopiar = true) {
    const container = document.getElementById('dynamic-actions');
    if (!container) return;
    container.innerHTML = '';

    if (mostrarCopiar) {
        const btn = document.createElement('button');
        btn.className = 'btn-action-dynamic';
        btn.onclick = copiarTexto;
        btn.innerHTML = '📋 Copiar Relatório';
        container.appendChild(btn);
    }
}

function limparAcoesDinamicas() {
    const container = document.getElementById('dynamic-actions');
    if (container) container.innerHTML = '';
}

// ==========================================
// RECUPERAÇÃO DE COOLDOWN AO CARREGAR A TELA
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // Passamos "0" porque não queremos adicionar tempo, só checar se já existe um salvo!
    iniciarCooldown(0, 'btnConsultarPlaca', 'Consultar');
    iniciarCooldown(0, 'btnConsultarCNH', 'Consultar CNH');
    iniciarCooldown(0, 'btnConsultarDadosCPF', 'Consultar Dados');
    iniciarCooldown(0, 'btnConsultarNome', 'Consultar Nome');
});