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
    let html = texto
        // Deixa os rótulos (ex: Placa:, Chassi:) com uma classe suave
        .replace(/\*\*(.*?)\*\*/g, '<span class="data-label">$1</span>')
        .replace(/\n/g, '<br>');

    // MÁGICA DOS BADGES (AGORA SÓ PARA O QUE REALMENTE IMPORTA)
    html = html.replace(/`(.*?)`/g, function(match, conteudo) {
        let textUpper = conteudo.trim().toUpperCase();
        
        // Status Positivos
        if (['NÃO', 'NAO', 'SEM RESTRICAO', 'SEM RESTRIÇÃO', 'NORMAL'].includes(textUpper)) {
            return `<span class="badge badge-success">✅ ${conteudo}</span>`;
        }
        // Alertas Vermelhos
        else if (['SIM', 'COM RESTRICAO', 'COM RESTRIÇÃO', 'ROUBO E FURTO', 'ROUBO/FURTO'].includes(textUpper)) {
            return `<span class="badge badge-danger">🚨 ${conteudo}</span>`;
        }
        // Neutros
        else if (['SEM INFORMAÇÃO', 'SEM INFORMACAO', 'NÃO APLICAVEL', 'NãO APLICAVEL', 'NAO APLICAVEL'].includes(textUpper)) {
            return `<span class="badge badge-warning">⚠️ ${conteudo}</span>`;
        }
        // DADOS COMUNS (Placa, Chassi, Cor): Texto limpo, sem caixota em volta!
        else {
            return `<span class="data-value">${conteudo}</span>`;
        }
    });

    // Títulos de Seção: Linha sutil por baixo em vez de um bloco azulão
    html = html.replace(/•\s*<span class="data-label">([A-ZÍÁÉÓÚÇ\s/]+)<\/span>/g, '<div class="section-title">$1</div>');
    html = html.replace(/•\s*([A-ZÍÁÉÓÚÇ\s/]{10,})(<br>|$)/g, '<div class="section-title">$1</div>$2'); 
    
    // Extrema Faxina: Tira aquelas bolinhas "•" soltas pra limpar a tela de vez
    html = html.replace(/•\s*/g, '');

    return html;
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