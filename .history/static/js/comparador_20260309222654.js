// ==========================================
// MÓDULO 4: COMPARADOR FACIAL EM LOTE
// ==========================================

let resultadosGlobais = [];
let paginaAtual = 1;
const itensPorPagina = 20;

const inputBase = document.getElementById('inputBase');
const inputLote = document.getElementById('inputLote');

if (inputBase) inputBase.addEventListener('change', handleBaseUpload);
if (inputLote) inputLote.addEventListener('change', handleLoteUpload);

function handleBaseUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(event) {
        document.getElementById('defaultBase').style.display = 'none';
        document.getElementById('previewBase').style.display = 'flex';
        document.getElementById('previewBase').style.flexDirection = 'column';
        document.getElementById('previewBase').style.alignItems = 'center';
        document.getElementById('imgPreviewBase').src = event.target.result;
    }
    reader.readAsDataURL(file);
}

function handleLoteUpload(e) {
    const files = e.target.files;
    const total = files.length;
    if (total === 0) return;

    if (total > 250) {
        exibirErro("⚠️ Limite de segurança excedido! Selecione no máximo 250 fotos por lote.");
        e.target.value = ''; 
        return;
    }

    document.getElementById('defaultLote').style.display = 'none';
    document.getElementById('previewLote').style.display = 'flex';
    document.getElementById('previewLote').style.flexDirection = 'column';
    document.getElementById('previewLote').style.alignItems = 'center';

    const containerMiniaturas = document.getElementById('miniaturasLote');
    containerMiniaturas.innerHTML = ''; 
    const maxThumbnails = 4; 

    for (let i = 0; i < Math.min(total, maxThumbnails); i++) {
        const reader = new FileReader();
        reader.onload = function(event) {
            const img = document.createElement('img');
            img.src = event.target.result;
            img.className = 'miniatura-lote';
            containerMiniaturas.appendChild(img);
        }
        reader.readAsDataURL(files[i]);
    }

    const badge = document.getElementById('badgeMaisFotos');
    if (total > maxThumbnails) {
        badge.innerText = `+${total - maxThumbnails}`;
        badge.style.display = 'block';
    } else {
        badge.style.display = 'none';
    }
    document.getElementById('txtArquivosSelecionados').innerText = `Arquivos selecionados: ${total}`;
}

async function iniciarComparacao() {
    const fileBase = inputBase.files[0];
    const filesLote = inputLote.files;
    
    const btn = document.getElementById('btnComparar');
    const resultContainer = document.getElementById('resultadoContainer');
    const resultBox = document.getElementById('resultado');
    const loader = document.getElementById('loader');

    if (!fileBase || filesLote.length === 0) {
        exibirErro("⚠️ Você precisa selecionar a Imagem Base e pelo menos uma imagem para o Lote.");
        return;
    }

    const turnstileResponse = document.querySelector('[name="cf-turnstile-response"]')?.value;
    if (!turnstileResponse) {
        exibirErro("🤖 Por favor, valide o captcha.");
        return;
    }

    btn.disabled = true;
    resultContainer.style.display = 'none';
    loader.style.display = 'block';
    
    loader.innerHTML = `
        <div class="loader-content">
            <div class="spinner"></div> 
            <span id="textoLoader">Enviando imagens para o servidor seguro...</span>
        </div>`;

    const formData = new FormData();
    formData.append('imagem_base', fileBase);
    for (let i = 0; i < filesLote.length; i++) {
        formData.append('imagens_lote', filesLote[i]); 
    }

    try {
        const response = await fetch('/api/comparar_facial', {
            method: 'POST',
            headers: { 'X-Turnstile-Token': turnstileResponse },
            body: formData
        });

        const data = await response.json();

        if (data.sucesso) {
            if (data.resultados && data.resultados.task_id) {
                document.getElementById('textoLoader').innerHTML = `Processando biometria...<br><span style="font-size: 0.8em; color: #5288c1;">Isso pode levar alguns segundos.</span>`;
                verificarStatusFila(data.resultados.task_id, btn, loader, resultContainer, resultBox);
            } else {
                exibirErro(`❌ O servidor parceiro não retornou o ID da fila.`);
                loader.style.display = 'none';
                btn.disabled = false;
            }
        } else {
            exibirErro(data.erro); 
            loader.style.display = 'none';
            btn.disabled = false;
        }

    } catch (error) {
        exibirErro("❌ O servidor principal não respondeu a tempo.");
        loader.style.display = 'none';
        btn.disabled = false;
    } 
}

async function verificarStatusFila(taskId, btn, loader, resultContainer, resultBox) {
    try {
        const response = await fetch(`/api/comparar_facial/status/${taskId}`);
        const data = await response.json();

        if (data.sucesso) {
            if (data.concluido) {
                loader.style.display = 'none';
                btn.disabled = false;
                prepararDados(data.dados, resultContainer);
            } else {
                setTimeout(() => verificarStatusFila(taskId, btn, loader, resultContainer, resultBox), 3000);
            }
        } else {
            exibirErro(`❌ ${data.erro}`);
            loader.style.display = 'none';
            btn.disabled = false;
        }
    } catch (e) {
        exibirErro("❌ Falha de conexão ao checar o status.");
        loader.style.display = 'none';
        btn.disabled = false;
    }
}

function prepararDados(dadosJson, resultContainer) {
    try {
        resultadosGlobais = dadosJson.chunk.results;

        if (!resultadosGlobais || resultadosGlobais.length === 0) {
            exibirErro("❌ A comparação foi concluída, mas nenhuma similaridade foi encontrada.");
            return;
        }

        resultadosGlobais.sort((a, b) => b.similarity - a.similarity);

        paginaAtual = 1; 
        renderizarPaginaAtual(); 
        
        resultContainer.style.display = 'block';
        if (typeof turnstile !== 'undefined') turnstile.reset();

    } catch (e) {
        exibirErro("❌ Falha ao processar os dados da tabela.");
    }
}

function renderizarPaginaAtual() {
    const resultBox = document.getElementById('resultado');
    const totalPaginas = Math.ceil(resultadosGlobais.length / itensPorPagina);
    
    const inicio = (paginaAtual - 1) * itensPorPagina;
    const fim = inicio + itensPorPagina;
    const itensDestaPagina = resultadosGlobais.slice(inicio, fim);

    // 🎯 HTML LIMPO! Sem tags <style>
    let htmlTabela = `
        <table class="arcsys-table">
            <thead>
                <tr>
                    <th>Imagem</th>
                    <th>Nome do Arquivo</th>
                    <th>Similaridade</th>
                </tr>
            </thead>
            <tbody>
    `;

    itensDestaPagina.forEach(item => {
        const nome = item.name;
        const porcentagem = item.similarity;
        const imgSrc = resgatarImagemLocal(nome); 
        
        let classeBadge = 'badge-porcentagem';
        if (porcentagem < 50) classeBadge += ' badge-baixo';

        htmlTabela += `
            <tr>
                <td><img src="${imgSrc}" class="img-match" alt="Face" loading="lazy"></td>
                <td class="nome-arquivo">${nome}</td>
                <td><span class="${classeBadge}">${porcentagem}%</span></td>
            </tr>
        `;
    });

    htmlTabela += `</tbody></table>`;

    let htmlPaginacao = `<div class="paginacao-container">`;
    htmlPaginacao += `<button class="btn-paginacao" onclick="mudarPagina(${paginaAtual - 1})" ${paginaAtual === 1 ? 'disabled' : ''}>⬅️ Anterior</button>`;
    htmlPaginacao += `<span class="paginacao-info">Página ${paginaAtual} de ${totalPaginas} <br><small style="font-size: 0.8em; color: #5288c1;">(${resultadosGlobais.length} resultados totais)</small></span>`;
    htmlPaginacao += `<button class="btn-paginacao" onclick="mudarPagina(${paginaAtual + 1})" ${paginaAtual === totalPaginas ? 'disabled' : ''}>Próxima ➡️</button>`;
    htmlPaginacao += `</div>`;

    resultBox.innerHTML = `
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="color: #2ecc71; font-weight: bold; font-size: 1.3em;">✅ Processamento Concluído!</span>
        </div>
        ${htmlTabela}
        ${totalPaginas > 1 ? htmlPaginacao : ''}
    `;
    injetarAcoesResultado(resultBox, false);
}

function mudarPagina(novaPagina) {
    const totalPaginas = Math.ceil(resultadosGlobais.length / itensPorPagina);
    if (novaPagina >= 1 && novaPagina <= totalPaginas) {
        paginaAtual = novaPagina;
        renderizarPaginaAtual();
        document.getElementById('resultadoContainer').scrollIntoView({ behavior: 'smooth' });
    }
}

function resgatarImagemLocal(nomeDoServidor) {
    const filesLote = document.getElementById('inputLote').files;
    
    for (let i = 0; i < filesLote.length; i++) {
        if (filesLote[i].name === nomeDoServidor) return URL.createObjectURL(filesLote[i]);
    }
    for (let i = 0; i < filesLote.length; i++) {
        if (filesLote[i].name.toLowerCase() === nomeDoServidor.toLowerCase()) return URL.createObjectURL(filesLote[i]);
    }
    const normalizar = (str) => str.toLowerCase().replace(/[^a-z0-9.]/g, '');
    const nomeNorm = normalizar(nomeDoServidor);
    for (let i = 0; i < filesLote.length; i++) {
        if (normalizar(filesLote[i].name) === nomeNorm) return URL.createObjectURL(filesLote[i]);
    }
    
    return 'data:image/svg+xml;charset=UTF-8,%3Csvg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="%238aa3ba" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"%3E%3Cpath d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"%3E%3C/path%3E%3Ccircle cx="12" cy="7" r="4"%3E%3C/circle%3E%3C/svg%3E';
}

function exibirErro(msg) {
    const resultBox = document.getElementById('resultado');
    const resultContainer = document.getElementById('resultadoContainer');
    
    let icone = msg.includes('⏳') ? '' : '❌ ';
    if(msg.startsWith('❌') || msg.startsWith('⚠️') || msg.startsWith('🤖') || msg.startsWith('⏳')) icone = '';

    resultBox.innerHTML = `<div class="badge badge-danger" style="font-size: 1.1em; padding: 15px; display: block; text-align: center;">${icone}${msg}</div>`;
    resultContainer.style.display = 'block';
}