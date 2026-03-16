// ==========================================
// MÓDULO 2: CONSULTA DE CNH (CPF)
// ==========================================

// 1. TRATAMENTO EM TEMPO REAL (Impede letras e formata)
const cpfInputField = document.getElementById('cpfInput');
if (cpfInputField) {
    cpfInputField.addEventListener('input', function () {
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
async function fazerConsultaCNH() {
    const input = document.getElementById('cpfInput');
    const cpfInput = input.value; 
    const btn = document.getElementById('btnConsultarCNH');
    const resultContainer = document.getElementById('resultadoContainer');
    const resultBox = document.getElementById('resultado');
    const loader = document.getElementById('loader');

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
            Processando sua consulta, por favor aguarde...
        </div>`;

    try {
        // 🛡️ ENVIANDO O TOKEN PARA O SERVIDOR NO HEADER
        const response = await fetch(`/api/consultar_cnh/${cpfInput}`, {
            method: 'GET',
            headers: {
                'X-Turnstile-Token': turnstileResponse
            }
        });
        
        const data = await response.json();

        if (data.sucesso) {
            textoPuro = data.dados; 
            let htmlFormatado = formatarTexto(data.dados);
            
            if (data.foto) {
                htmlFormatado = `
                    <div style="text-align: center; margin-bottom: 25px; animation: fadeIn 0.5s ease;">
                        <img src="${data.foto}" alt="Foto CNH" style="max-width: 250px; width: 100%; border-radius: 12px; border: 3px solid #5288c1; box-shadow: 0 10px 25px rgba(0,0,0,0.4);">
                        <div style="color: #8aa3ba; font-size: 0.8em; margin-top: 10px; text-transform: uppercase; letter-spacing: 1px;">Registro Fotográfico Localizado</div>
                    </div>
                    ${htmlFormatado}
                `;
            }
            
            if (data.cache) {
                resultBox.innerHTML = "<span class='cache-aviso'>⚡ Recuperado do Banco de Dados</span><br>" + htmlFormatado;
                btn.disabled = false; 
            } else {
                resultBox.innerHTML = htmlFormatado;
                iniciarCooldown(120, 'btnConsultarCNH', 'Consultar CNH');
            }
            injetarAcoesResultado(resultBox, true);
            
        } else {
            textoPuro = data.erro || data.dados;
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${textoPuro}</div>`;
            btn.disabled = false; 
        }
        
        resultContainer.style.display = 'block';
    } catch (_) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">❌ Erro de conexão com o servidor. O bot pode estar dormindo.</div>`;
        resultContainer.style.display = 'block';
        btn.disabled = false; 
    } finally {
        // Encerramento limpo
        loader.style.display = 'none';
        
        // 🛡️ RESET DO CLOUDFLARE PARA A PRÓXIMA CONSULTA
        if (typeof turnstile !== 'undefined') {
            turnstile.reset();
        }
    }
}

// 3. EVENTO DE TECLADO (ENTER)
document.getElementById('cpfInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarCNH').disabled) {
        fazerConsultaCNH();
    }
});