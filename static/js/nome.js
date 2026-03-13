const nomeInputField = document.getElementById('nomeBuscaInput');
if (nomeInputField) {
    nomeInputField.addEventListener('input', function () {
        this.value = this.value.replace(/\s+/g, ' ').trimStart();
    });
}

let resultadosNomeAtuais = [];

function limparTextoNome(valor) {
    return String(valor || '-')
        .replace(/\*|`/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

function escaparHtml(valor) {
    return String(valor || '-')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function normalizarResultadoNome(item = {}) {
    return {
        nome: limparTextoNome(item.nome),
        cpf: limparTextoNome(item.cpf),
        sexo: limparTextoNome(item.sexo),
        data_nascimento: limparTextoNome(item.data_nascimento),
        nome_mae: limparTextoNome(item.nome_mae),
        situacao: limparTextoNome(item.situacao)
    };
}

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

function montarTextoCopiarResultado(item) {
    const dados = normalizarResultadoNome(item);
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
    const item = resultadosNomeAtuais[index];
    if (!item) return;

    try {
        await navigator.clipboard.writeText(montarTextoCopiarResultado(item));
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

    resultadosNomeAtuais = resultados.map(normalizarResultadoNome);

    lista.innerHTML = resultadosNomeAtuais.map((item, index) => {
        const nome = escaparHtml(item.nome);
        const cpf = escaparHtml(item.cpf);
        const sexo = escaparHtml(item.sexo);
        const dataNascimento = escaparHtml(item.data_nascimento);
        const nomeMae = escaparHtml(item.nome_mae);
        const situacao = escaparHtml(item.situacao);
        const searchPayload = escaparHtml(`${item.nome} ${item.cpf} ${item.data_nascimento}`);

        return `
            <div class="result-card" data-search="${searchPayload}">
                <div class="nome-resultado-head result-card-head">
                    <div class="nome-head-info">
                        <span class="nome-resultado-indice">#${index + 1}</span>
                        <span class="nome-resultado-titulo">${nome}</span>
                    </div>
                    <button class="result-card-copy" data-index="${index}" type="button">📋 Copiar</button>
                </div>
                <div class="nome-resultado-grid">
                    <div class="nome-campo"><span class="nome-label">CPF</span><span class="nome-valor">${cpf}</span></div>
                    <div class="nome-campo"><span class="nome-label">Sexo</span><span class="nome-valor">${sexo}</span></div>
                    <div class="nome-campo"><span class="nome-label">Nascimento</span><span class="nome-valor">${dataNascimento}</span></div>
                    <div class="nome-campo"><span class="nome-label">Mãe</span><span class="nome-valor">${nomeMae}</span></div>
                    <div class="nome-campo nome-campo-full"><span class="nome-label">Situação</span><span class="nome-valor">${situacao}</span></div>
                </div>
            </div>
        `;
    }).join('');

    aplicarFiltroResultadosNome();
}

document.getElementById('resultadoNomeLista')?.addEventListener('click', function (event) {
    const botao = event.target.closest('.result-card-copy');
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
    } catch (error) {
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
