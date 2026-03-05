// ==========================================
// MÓDULO 3: CONSULTA DE DADOS (CPF / SISREG)
// ==========================================

// 1. TRATAMENTO EM TEMPO REAL (Impede letras e formata)
const cpfDadosInputField = document.getElementById('cpfDadosInput');
if (cpfDadosInputField) {
    cpfDadosInputField.addEventListener('input', function (e) {
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
    
    // 💡 NOVO: Seleciona o botão de copiar do HTML
    const btnCopiar = document.getElementById('btn-copiar');

    // Validação de Segurança
    if (cpfInput.length !== 11) {
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 400);
        
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ CPF Inválido!<br>O CPF precisa ter exatamente 11 números.</div>`;
        resultContainer.style.display = 'block';
        if (btnCopiar) btnCopiar.style.display = 'none'; // Esconde o botão no erro
        return;
    }

    // 🛡️ VERIFICAÇÃO DO CLOUDFLARE TURNSTILE
    // Pega a resposta invisível gerada pelo widget
    const turnstileResponse = document.querySelector('[name="cf-turnstile-response"]')?.value;
    
    if (!turnstileResponse) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">🤖 Por favor, valide o captcha.</div>`;
        resultContainer.style.display = 'block';
        if (btnCopiar) btnCopiar.style.display = 'none'; // Esconde o botão no erro
        return;
    }

    btn.disabled = true;
    resultContainer.style.display = 'none';
    loader.style.display = 'block';

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

        if (data.sucesso) {
            textoPuro = data.dados; 
            let htmlFormatado = formatarTexto(data.dados);
            
            if (data.cache) {
                resultBox.innerHTML = "<span class='cache-aviso'>⚡ Recuperado do Banco de Dados</span><br>" + htmlFormatado;
                btn.disabled = false; 
            } else {
                resultBox.innerHTML = htmlFormatado;
                iniciarCooldown(120, 'btnConsultarDadosCPF', 'Consultar Dados');
            }
            if (btnCopiar) btnCopiar.style.display = 'block'; // SÓ MOSTRA O BOTÃO SE DER SUCESSO
            
        } else {
            textoPuro = data.erro || data.dados;
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${textoPuro}</div>`;
            btn.disabled = false; 
            if (btnCopiar) btnCopiar.style.display = 'none'; // Esconde o botão no erro
        }
        
        resultContainer.style.display = 'block';
    } catch (error) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">❌ Erro de conexão com o servidor. Tente novamente em instantes.</div>`;
        resultContainer.style.display = 'block';
        btn.disabled = false; 
        if (btnCopiar) btnCopiar.style.display = 'none'; // Esconde o botão no erro
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
document.getElementById('cpfDadosInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarDadosCPF').disabled) {
        fazerConsultaDadosCPF();
    }
});