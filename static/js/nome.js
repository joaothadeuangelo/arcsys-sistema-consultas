const nomeInputField = document.getElementById('nomeBuscaInput');
if (nomeInputField) {
    nomeInputField.addEventListener('input', function () {
        this.value = this.value.replace(/\s+/g, ' ').trimStart();
    });
}

let resultadosNomeAtuais = [];

function normalizarTextoFiltro(valor) {
    return String(valor || '')
        .toLowerCase()
        .replace(/\*|`/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

function aplicarFiltroResultadosNome() {
    const filtroInput = document.getElementById('filtroResultadoNome');
    const lista = document.getElementById('resultadoNomeLista');
    const avisoVazio = document.getElementById('resultadoNomeFiltroVazio');
    if (!filtroInput || !lista || !avisoVazio) return;

    const termo = normalizarTextoFiltro(filtroInput.value);
    const cards = lista.querySelectorAll('.result-card');
    let visiveis = 0;

    cards.forEach((card) => {
        const textoBusca = normalizarTextoFiltro(card.getAttribute('data-search') || '');
        const mostrar = !termo || textoBusca.includes(termo);
        card.style.display = mostrar ? '' : 'none';
        if (mostrar) visiveis += 1;
    });

    avisoVazio.style.display = visiveis === 0 && cards.length > 0 ? 'block' : 'none';
}

function montarTextoCopiarResultado(dados) {
    return [
        `Nome: ${dados.nome}`,
        `CPF: ${dados.cpf}`,
        `Sexo: ${dados.sexo}`,
        `Nascimento: ${dados.data_nascimento}`,
        `Nome da Mae: ${dados.nome_mae}`,
        `Situacao: ${dados.situacao}`
    ].join('\n');
}

async function copiarResultadoNome(index, btn) {
    const dados = resultadosNomeAtuais[index];
    if (!dados) return;

    try {
        await navigator.clipboard.writeText(montarTextoCopiarResultado(dados));
        const original = btn.innerHTML;
        btn.innerHTML = '✅ Copiado';
        setTimeout(() => {
            btn.innerHTML = original;
        }, 1400);
    } catch (_) {
        btn.innerHTML = '⚠️ Falha';
        setTimeout(() => {
            btn.innerHTML = '📋 Copiar';
        }, 1400);
    }
}

function renderizarResultadosNome(resultados = []) {
    const lista = document.getElementById('resultadoNomeLista');
    if (!lista) return;

    if (!Array.isArray(resultados) || !resultados.length) {
        resultadosNomeAtuais = [];
        lista.innerHTML = "<div class='nome-card-vazio'>Nenhum resultado encontrado.</div>";
        return;
    }

    let html = '';
    resultadosNomeAtuais = [];

    resultados.forEach((item, index) => {
        let nomeLimpo = item.nome ? item.nome.replace(/[*`]/g, '').trim() : '-';
        let cpfLimpo = item.cpf ? item.cpf.replace(/[*`]/g, '').trim() : '-';
        let sexoLimpo = item.sexo ? item.sexo.replace(/[*`]/g, '').trim() : '-';
        let nascLimpo = item.data_nascimento ? item.data_nascimento.replace(/[*`]/g, '').trim() : '-';
        let maeLimpo = item.nome_mae ? item.nome_mae.replace(/[*`]/g, '').trim() : '-';
        let situacaoLimpa = item.situacao ? item.situacao.replace(/[*`]/g, '').trim() : '-';

        nomeLimpo = nomeLimpo.replace(/\s+/g, ' ');
        cpfLimpo = cpfLimpo.replace(/\s+/g, ' ');
        sexoLimpo = sexoLimpo.replace(/\s+/g, ' ');
        nascLimpo = nascLimpo.replace(/\s+/g, ' ');
        maeLimpo = maeLimpo.replace(/\s+/g, ' ');
        situacaoLimpa = situacaoLimpa.replace(/\s+/g, ' ');

        resultadosNomeAtuais.push({
            nome: nomeLimpo,
            cpf: cpfLimpo,
            sexo: sexoLimpo,
            data_nascimento: nascLimpo,
            nome_mae: maeLimpo,
            situacao: situacaoLimpa
        });

        html += `
   <div class="result-card" data-search="${nomeLimpo} ${cpfLimpo} ${nascLimpo}">
       <div class="nome-resultado-head">
           <div class="nome-head-info">
               <span class="nome-resultado-indice">#${index + 1}</span>
               <h4 class="nome-resultado-titulo">${nomeLimpo}</h4>
           </div>
           <button class="result-card-copy btn-copy" data-index="${index}">📋 Copiar</button>
       </div>

       <div class="nome-resultado-grid">
           <div class="nome-campo">
               <span class="nome-label">CPF</span>
               <span class="nome-valor">${cpfLimpo}</span>
           </div>
           <div class="nome-campo">
               <span class="nome-label">Sexo</span>
               <span class="nome-valor">${sexoLimpo}</span>
           </div>
           <div class="nome-campo">
               <span class="nome-label">Nascimento</span>
               <span class="nome-valor">${nascLimpo}</span>
           </div>
           <div class="nome-campo">
               <span class="nome-label">Mae</span>
               <span class="nome-valor">${maeLimpo}</span>
           </div>
           <div class="nome-campo nome-campo-full">
               <span class="nome-label">Situacao</span>
               <span class="nome-valor">${situacaoLimpa}</span>
           </div>
       </div>
   </div>
        `;
    });

    lista.innerHTML = html;

    aplicarFiltroResultadosNome();
}

document.getElementById('resultadoNomeLista')?.addEventListener('click', function (event) {
    const botao = event.target.closest('.btn-copy');
    if (!botao) return;

    const index = Number(botao.getAttribute('data-index'));
    if (Number.isNaN(index)) return;

    copiarResultadoNome(index, botao);
});

document.getElementById('filtroResultadoNome')?.addEventListener('input', aplicarFiltroResultadosNome);

async function fazerConsultaNome() {
    const input = document.getElementById('nomeBuscaInput');
    const btn = document.getElementById('btnConsultarNome');
    const loader = document.getElementById('loader');
    const resultContainer = document.getElementById('resultadoContainer');
    const resultMeta = document.getElementById('resultadoNomeMeta');
    const filtroInput = document.getElementById('filtroResultadoNome');
    const avisoVazio = document.getElementById('resultadoNomeFiltroVazio');

    const nome = (input?.value || '').trim();

    if (nome.length < 3) {
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 400);
        resultMeta.innerHTML = "<div class='badge badge-danger' style='font-size: 1em; padding: 12px; display: block; text-align: center;'>❌ Digite ao menos 3 caracteres.</div>";
        resultContainer.style.display = 'block';
        return;
    }

    const turnstileResponse = document.querySelector('[name="cf-turnstile-response"]')?.value;
    if (!turnstileResponse) {
        resultMeta.innerHTML = "<div class='badge badge-danger' style='font-size: 1em; padding: 12px; display: block; text-align: center;'>🤖 Por favor, valide o captcha.</div>";
        resultContainer.style.display = 'block';
        return;
    }

    btn.disabled = true;
    resultContainer.style.display = 'none';
    loader.style.display = 'block';
    limparAcoesDinamicas();
    if (filtroInput) filtroInput.value = '';
    if (avisoVazio) avisoVazio.style.display = 'none';

    loader.innerHTML = `
        <div class="loader-content">
            <div class="spinner"></div>
            Localizando registros por nome, aguarde...
        </div>`;

    try {
        const response = await fetch(`/api/consultar/nome/${encodeURIComponent(nome)}`, {
            method: 'GET',
            headers: {
                'X-Turnstile-Token': turnstileResponse
            }
        });

        const data = await response.json();

        if (response.status === 404 || data.status === 'not_found') {
            const aviso = data.message || 'Nenhum resultado encontrado para este termo.';
            resultMeta.innerHTML = `<div class='badge badge-warning' style='font-size: 1em; padding: 12px; display: block; text-align: center; white-space: pre-wrap;'>⚠️ ${aviso}</div>`;
            renderizarResultadosNome([]);
            btn.disabled = false;
            resultContainer.style.display = 'block';
            return;
        }

        if (data.sucesso) {
            const total = Array.isArray(data.resultados) ? data.resultados.length : 0;
            const fonte = (data.fonte || 'chat').toUpperCase();
            const cache = data.cache ? " <span class='cache-aviso'>⚡ Cache</span>" : '';
            resultMeta.innerHTML = `<div class='nome-resumo-head'>Resultados: <strong>${total}</strong> | Fonte: <strong>${fonte}</strong>${cache}</div>`;
            renderizarResultadosNome(data.resultados || []);
            injetarAcoesResultado(document.getElementById('resultadoNomeLista'), false);

            if (!data.cache) {
                iniciarCooldown(120, 'btnConsultarNome', 'Consultar Nome');
            } else {
                btn.disabled = false;
            }
        } else {
            const erro = data.erro || 'Não foi possível consultar este nome.';
            resultMeta.innerHTML = `<div class='badge badge-danger' style='font-size: 1em; padding: 12px; display: block; text-align: center; white-space: pre-wrap;'>❌ ${erro}</div>`;
            renderizarResultadosNome([]);
            btn.disabled = false;
        }

        resultContainer.style.display = 'block';
    } catch (_) {
        resultMeta.innerHTML = "<div class='badge badge-danger' style='font-size: 1em; padding: 12px; display: block; text-align: center;'>❌ Erro de conexão com o servidor.</div>";
        renderizarResultadosNome([]);
        resultContainer.style.display = 'block';
        btn.disabled = false;
    } finally {
        loader.style.display = 'none';
        if (typeof turnstile !== 'undefined') {
            turnstile.reset();
        }
    }
}

document.getElementById('nomeBuscaInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !document.getElementById('btnConsultarNome').disabled) {
        fazerConsultaNome();
    }
});
