let tempoLeitura = 5; 
let timerInterval;

window.onload = function() {
    // 1. VERIFICAÇÃO DE MANUTENÇÃO SEMPRE VEM PRIMEIRO
    if (window.SISTEMA_EM_MANUTENCAO) {
        document.querySelector('.container').style.display = 'none';
        document.getElementById('modalAviso').style.display = 'none';
        document.getElementById('modalManutencao').style.display = 'flex';
        return; 
    }

    // 2. SE O SISTEMA ESTIVER ON, DISPARA O TIMER DAS REGRAS IMEDIATAMENTE
    const btn = document.getElementById('btnAceitarModal');
    const checkbox = document.getElementById('checkPromessa');

    timerInterval = setInterval(() => {
        if (tempoLeitura > 0) {
            btn.innerText = `LENDO AS REGRAS... (${tempoLeitura}s)`;
            tempoLeitura--;
        } else {
            clearInterval(timerInterval);
            btn.innerText = "MARQUE A CAIXINHA ACIMA ⬆️";
            checkbox.disabled = false;
        }
    }, 1000);
}

function verificarCheckbox() {
    const btn = document.getElementById('btnAceitarModal');
    const checkbox = document.getElementById('checkPromessa');
    
    if (checkbox.checked && tempoLeitura <= 0) {
        btn.disabled = false;
        btn.classList.remove('bloqueado');
        btn.classList.add('liberado');
        btn.innerText = "LI, ACEITO E NÃO VOU ENCHER O SACO";
    } else {
        btn.disabled = true;
        btn.classList.remove('liberado');
        btn.classList.add('bloqueado');
        btn.innerText = "MARQUE A CAIXINHA ACIMA ⬆️";
    }
}

function fecharModal() {
    document.getElementById('modalAviso').style.display = 'none';
}

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
    return texto
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`(.*?)`/g, '<span class="destaque-codigo">$1</span>')
        .replace(/\n/g, '<br>');
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
        .replace(/\*\*/g, '') // Remove todos os asteriscos de negrito
        .replace(/`/g, '')    // Remove todas as crases de código
        .replace(/\n{3,}/g, '\n\n') // Tira o excesso de linhas em branco (deixa no máximo 1)
        .trim(); // Arranca espaços sobrando no começo e no fim

    // Adiciona uma assinatura elegante no final do texto copiado
    textoLimpo += "\n\n━━━━━━━━━━━━━━━━━━━━━━\n🔍 Consulta realizada via ARCANGELO SYSTEM";
    
    return textoLimpo;
}

function copiarTexto() {
    // Passa o texto puro pela faxina antes de mandar pro clipboard
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