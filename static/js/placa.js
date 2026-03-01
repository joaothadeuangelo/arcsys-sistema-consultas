// ==========================================
// MÓDULO 1: CONSULTA DE PLACA
// ==========================================
async function fazerConsulta() {
    const input = document.getElementById('placaInput');
    const placa = input.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
    input.value = placa; 

    const btn = document.getElementById('btnConsultarPlaca'); 
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
        clearInterval(loaderInterval);
        loader.style.display = 'none';
        loader.innerText = "Processando requisição... ⏳"; 
    }
}

// Evento de "Enter" no teclado
document.getElementById('placaInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarPlaca').disabled) {
        fazerConsulta();
    }
});