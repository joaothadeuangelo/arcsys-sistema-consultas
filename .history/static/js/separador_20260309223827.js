// ==========================================
// MÓDULO 4: SEPARADOR DE CPF (Inteligência Nativa e Blindada)
// ==========================================

// Motor Matemático 100% Offline e Instantâneo
function isCpfValido(cpf) {
    cpf = cpf.replace(/[^\d]+/g, '');
    if (cpf.length !== 11 || /^(\d)\1+$/.test(cpf)) return false;
    
    let soma = 0, resto;
    for (let i = 1; i <= 9; i++) soma += parseInt(cpf.substring(i - 1, i)) * (11 - i);
    resto = (soma * 10) % 11;
    if ((resto === 10) || (resto === 11)) resto = 0;
    if (resto !== parseInt(cpf.substring(9, 10))) return false;
    
    soma = 0;
    for (let i = 1; i <= 10; i++) soma += parseInt(cpf.substring(i - 1, i)) * (12 - i);
    resto = (soma * 10) % 11;
    if ((resto === 10) || (resto === 11)) resto = 0;
    if (resto !== parseInt(cpf.substring(10, 11))) return false;
    
    return true;
}

function processarCPFs() {
    const textoInput = document.getElementById('textoEntrada').value;
    const btn = document.getElementById('btnExtrair');
    
    if (!textoInput.trim()) {
        alert("Cole algum texto para extrair!");
        return;
    }

    btn.innerText = "⏳ Processando...";
    btn.disabled = true;

    // Pequeno delay para a interface não travar com textos gigantescos
    setTimeout(() => {
        // Busca Inteligente: Procura APENAS o padrão pontuado (000.000.000-00)
        // Isso ignora completamente números lisos (como N° Registro CNH, RG ou Telefones)
        const regexBusca = /\d{3}\.\d{3}\.\d{3}-\d{2}/g;
        const candidatos = textoInput.match(regexBusca) || [];

        // O 'Set' serve para não deixar CPFs repetidos na lista final
        let cpfsLimpados = new Set();

        candidatos.forEach(candidato => {
            let limpo = candidato.replace(/\D/g, ''); // Arranca pontos e traços
            if (isCpfValido(limpo)) {
                cpfsLimpados.add(limpo);
            }
        });

        const arrayFinal = Array.from(cpfsLimpados);

        if (arrayFinal.length === 0) {
            alert("Nenhum CPF válido foi encontrado. Certifique-se de que os CPFs no texto possuem a pontuação correta (xxx.xxx.xxx-xx).");
            btn.innerText = "Extrair e Limpar CPFs";
            btn.disabled = false;
            return;
        }

        // Esconde o Input e mostra o Resultado
        document.getElementById('boxInput').style.display = 'none';
        document.getElementById('boxResultado').style.display = 'block';
        
        document.getElementById('textoSaida').value = arrayFinal.join('\n');
        document.getElementById('contadorResultados').innerText = `✅ ${arrayFinal.length} CPF(s) válido(s) extraído(s)`;

        // Injeta ações dinâmicas no nav header
        const dynActions = document.getElementById('dynamic-actions');
        if (dynActions) {
            dynActions.innerHTML = `
                <button class="btn-action-dynamic" onclick="copiarCPFs()">📋 Copiar Lista</button>
                <button class="btn-action-dynamic" onclick="baixarTXT()">💾 Baixar .txt</button>
            `;
        }
        
        btn.innerText = "Extrair e Limpar CPFs";
        btn.disabled = false;
    }, 100);
}

function copiarCPFs() {
    const textoSaida = document.getElementById('textoSaida');
    textoSaida.select();
    document.execCommand('copy');
    alert("✅ Lista de CPFs copiada para a área de transferência!");
}

function baixarTXT() {
    const texto = document.getElementById('textoSaida').value;
    const blob = new Blob([texto], { type: "text/plain;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "CPFs_Extraidos_ARCSYS.txt";
    link.click();
}

function limparTudo() {
    document.getElementById('textoEntrada').value = '';
    document.getElementById('textoSaida').value = '';
    document.getElementById('boxResultado').style.display = 'none';
    document.getElementById('boxInput').style.display = 'block';
}