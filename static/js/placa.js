// ==========================================
// MÓDULO 1: CONSULTA DE PLACA
// ==========================================

// 1. TRATAMENTO EM TEMPO REAL (Impede caracteres inválidos e força maiúscula)
const placaInputField = document.getElementById('placaInput');
if (placaInputField) {
    placaInputField.addEventListener('input', function (e) {
        // Remove tudo que não for letra ou número e converte para CAIXA ALTA
        this.value = this.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    });
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

    // Validação de Segurança
    if (!regexPlaca.test(placa)) {
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 400);
        
        // Ajustado para usar o Card Vermelho padrão do sistema
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

    btn.disabled = true;
    resultContainer.style.display = 'none';
    loader.style.display = 'block';

    // Injeta o spinner HTML animado e a frase profissional
    loader.innerHTML = `
        <div class="loader-content">
            <div class="spinner"></div> 
            Processando sua consulta, por favor aguarde...
        </div>`;

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
                iniciarCooldown(120, 'btnConsultarPlaca', 'Consultar');
            }
        } else {
            textoPuro = data.erro || data.dados;
            resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center; white-space: pre-wrap;">❌ ${textoPuro}</div>`;
            btn.disabled = false;
        }
        
        resultContainer.style.display = 'block';
    } catch (error) {
        resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">❌ Erro de conexão com o servidor. O sistema pode estar offline.</div>`;
        resultContainer.style.display = 'block';
        btn.disabled = false;
    } finally {
        // Encerramento limpo
        loader.style.display = 'none';
    }
}

// 3. EVENTO DE TECLADO (ENTER)
document.getElementById('placaInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarPlaca').disabled) {
        fazerConsulta();
    }
});