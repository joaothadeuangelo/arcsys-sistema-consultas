// ==========================================
// MÓDULO 3: CONSULTA DE DADOS (CPF / SISREG)
// ==========================================

// 1. TRATAMENTO EM TEMPO REAL (Impede letras e formata)
const cpfDadosInputField = document.getElementById('cpfDadosInput');
let timerCooldownCPF = null;

function extrairSegundosCooldownCPF(mensagem) {
    const match = String(mensagem || '').match(/(\d+)\s*segundos?/i);
    return match ? parseInt(match[1], 10) : 0;
}

function iniciarCooldownVisualCPF(segundos, btn, textoOriginal) {
    if (!btn || !Number.isFinite(segundos) || segundos <= 0) return;

    if (timerCooldownCPF) {
        clearInterval(timerCooldownCPF);
        timerCooldownCPF = null;
    }

    let restante = segundos;
    btn.disabled = true;
    btn.textContent = `Aguarde ${restante}s...`;

    timerCooldownCPF = setInterval(() => {
        restante -= 1;
        if (restante <= 0) {
            clearInterval(timerCooldownCPF);
            timerCooldownCPF = null;
            btn.disabled = false;
            btn.textContent = textoOriginal;
            return;
        }
        btn.textContent = `Aguarde ${restante}s...`;
    }, 1000);
}

if (cpfDadosInputField) {
    cpfDadosInputField.addEventListener('input', function () {
        // Arranca tudo que não for número (letras, pontos, traços, espaços)
        let value = this.value.replace(/\D/g, '');
        
        // Garante que não passe de 11 números (mesmo que ele cole um texto gigante)
        if (value.length > 11) {
            value = value.slice(0, 11);
        }
        
        // Devolve o valor limpo para o campo
        this.value = value;
    });
}

// 2. FUNÇÃO PRINCIPAL DE CONSULTA
async function fazerConsultaDadosCPF() {
    const input = document.getElementById('cpfDadosInput');
    const cpfInput = input.value; 
    const btn = document.getElementById('btnConsultarDadosCPF');
    const resultContainer = document.getElementById('resultadoContainer');
    const resultBox = document.getElementById('resultado');
    const loader = document.getElementById('loader');
    const textoOriginalBotao = btn.textContent;
    let preservarEstadoBotao = false;

    // 🛡️ VALIDAÇÃO MATEMÁTICA DO CPF (PRIORIDADE #1 — ANTES DE TUDO)
    if (!validarCPF(cpfInput)) {
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 400);
        loader.style.display = 'none';
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ CPF Inválido!<br>Verifique os números informados.</div>`;
        resultContainer.style.display = 'block';
        return;
    }

    // 🛡️ VERIFICAÇÃO DO CLOUDFLARE TURNSTILE
    // Pega a resposta invisível gerada pelo widget
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

    // Injeta o spinner HTML animado e a frase profissional
    loader.innerHTML = `
        <div class="loader-content">
            <div class="spinner"></div> 
            Buscando dados no sistema, por favor aguarde...
        </div>`;

    try {
        // 🛡️ ENVIANDO O TOKEN PARA O SERVIDOR NO HEADER
        const response = await fetch(`/api/consultar_dados_cpf/${cpfInput}`, {
            method: 'GET',
            headers: {
                'X-Turnstile-Token': turnstileResponse
            }
        });
        
        const data = await response.json();

        if (response.status === 429) {
            const mensagem429 = data.erro || 'Aguarde alguns segundos para consultar novamente.';
            const segundos = extrairSegundosCooldownCPF(mensagem429);
            if (segundos > 0) {
                iniciarCooldownVisualCPF(segundos, btn, textoOriginalBotao);
                preservarEstadoBotao = true;
            }
            textoPuro = mensagem429;
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${mensagem429}</div>`;
            resultContainer.style.display = 'block';
            return;
        }

        if (data.sucesso) {
            textoPuro = data.dados; 
            let htmlFormatado = formatarTexto(data.dados);
            
            if (data.cache) {
                resultBox.innerHTML = "<span class='cache-aviso'>⚡ Recuperado do Banco de Dados</span><br>" + htmlFormatado;
                btn.disabled = false; 
            } else {
                resultBox.innerHTML = htmlFormatado;
                iniciarCooldown(120, 'btnConsultarDadosCPF', 'Consultar Dados');
                preservarEstadoBotao = true;
            }
            injetarAcoesResultado(resultBox, true);
            
        } else {
            textoPuro = data.erro || data.dados;
            const segundos = extrairSegundosCooldownCPF(textoPuro);
            if (segundos > 0) {
                iniciarCooldownVisualCPF(segundos, btn, textoOriginalBotao);
                preservarEstadoBotao = true;
            }
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${textoPuro}</div>`;
            if (!preservarEstadoBotao) {
                btn.disabled = false;
            }
        }
        
        resultContainer.style.display = 'block';
    } catch (_) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">❌ Erro de conexão com o servidor. Tente novamente em instantes.</div>`;
        resultContainer.style.display = 'block';
        btn.disabled = false; 
    } finally {
        // Encerramento limpo
        loader.style.display = 'none';

        if (!preservarEstadoBotao) {
            btn.disabled = false;
            btn.textContent = textoOriginalBotao;
        }
        
        // 🛡️ RESET DO CLOUDFLARE PARA A PRÓXIMA CONSULTA
        if (typeof turnstile !== 'undefined') {
            turnstile.reset();
        }
    }
}

// 3. EVENTO DE TECLADO (ENTER)
document.getElementById('cpfDadosInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarDadosCPF').disabled) {
        fazerConsultaDadosCPF();
    }
});