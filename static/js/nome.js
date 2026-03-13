const nomeInputField = document.getElementById('nomeBuscaInput');
if (nomeInputField) {
    nomeInputField.addEventListener('input', function () {
        this.value = this.value.replace(/\s+/g, ' ').trimStart();
    });
}

function renderizarResultadosNome(resultados = []) {
    const lista = document.getElementById('resultadoNomeLista');
    if (!lista) return;

    if (!Array.isArray(resultados) || !resultados.length) {
        lista.innerHTML = "<div class='nome-card-vazio'>Nenhum resultado encontrado.</div>";
        return;
    }

    lista.innerHTML = resultados.map((item, index) => {
        const nome = item.nome || '-';
        const cpf = item.cpf || '-';
        const sexo = item.sexo || '-';
        const dataNascimento = item.data_nascimento || '-';
        const nomeMae = item.nome_mae || '-';
        const situacao = item.situacao || '-';

        return `
            <div class="nome-resultado-card">
                <div class="nome-resultado-head">
                    <span class="nome-resultado-indice">#${index + 1}</span>
                    <span class="nome-resultado-titulo">${nome}</span>
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
}

async function fazerConsultaNome() {
    const input = document.getElementById('nomeBuscaInput');
    const btn = document.getElementById('btnConsultarNome');
    const loader = document.getElementById('loader');
    const resultContainer = document.getElementById('resultadoContainer');
    const resultMeta = document.getElementById('resultadoNomeMeta');

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
