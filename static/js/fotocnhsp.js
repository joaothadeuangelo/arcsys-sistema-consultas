// ==========================================
// MODULO FOTO CNH SP
// ==========================================

const cpfFotoCnhSpInput = document.getElementById('cpfFotoCnhSpInput');
const btnConsultarFotoCnhSp = document.getElementById('btnConsultarFotoCnhSp');
const fotoResultadoCnhSp = document.getElementById('fotoResultadoCnhSp');
const dadosResultadoCnhSp = document.getElementById('dadosResultadoCnhSp');
const btnBaixarFotoCnhSp = document.getElementById('btnBaixarFotoCnhSp');
const resultadoContainerFotoCnhSp = document.getElementById('resultadoContainer');
const loaderFotoCnhSp = document.getElementById('loader');

let fotoObjectUrlAtual = null;
let timerCooldownFotoCnhSp = null;
const CHAVE_COOLDOWN_FOTOCNHSP = 'cooldown_fotocnhsp';

function extrairSegundosCooldownFotoCnhSp(mensagem) {
    const match = String(mensagem || '').match(/(\d+)\s*segundos?/i);
    return match ? parseInt(match[1], 10) : 0;
}

function iniciarCooldownVisualFotoCnhSp(segundos, btn, textoOriginal) {
    if (!btn || !Number.isFinite(segundos) || segundos <= 0) return;

    if (timerCooldownFotoCnhSp) {
        clearInterval(timerCooldownFotoCnhSp);
        timerCooldownFotoCnhSp = null;
    }

    let restante = segundos;
    btn.disabled = true;
    btn.textContent = `Aguarde ${restante}s...`;

    timerCooldownFotoCnhSp = setInterval(() => {
        restante -= 1;
        if (restante <= 0) {
            clearInterval(timerCooldownFotoCnhSp);
            timerCooldownFotoCnhSp = null;
            btn.disabled = false;
            btn.textContent = textoOriginal;
            localStorage.removeItem(CHAVE_COOLDOWN_FOTOCNHSP);
            return;
        }
        btn.textContent = `Aguarde ${restante}s...`;
    }, 1000);
}

function iniciarCooldownPersistenteFotoCnhSp(segundos, btn, textoOriginal) {
    if (!btn || !Number.isFinite(segundos) || segundos <= 0) return;
    const fimCooldown = Date.now() + (segundos * 1000);
    localStorage.setItem(CHAVE_COOLDOWN_FOTOCNHSP, String(fimCooldown));
    iniciarCooldownVisualFotoCnhSp(segundos, btn, textoOriginal);
}

function restaurarCooldownFotoCnhSp() {
    if (!btnConsultarFotoCnhSp) return;

    const valorSalvo = localStorage.getItem(CHAVE_COOLDOWN_FOTOCNHSP);
    if (!valorSalvo) return;

    const fimCooldown = Number(valorSalvo);
    if (!Number.isFinite(fimCooldown)) {
        localStorage.removeItem(CHAVE_COOLDOWN_FOTOCNHSP);
        return;
    }

    const restanteMs = fimCooldown - Date.now();
    if (restanteMs <= 0) {
        localStorage.removeItem(CHAVE_COOLDOWN_FOTOCNHSP);
        return;
    }

    const segundosRestantes = Math.ceil(restanteMs / 1000);
    iniciarCooldownVisualFotoCnhSp(segundosRestantes, btnConsultarFotoCnhSp, 'Consultar');
}

if (resultadoContainerFotoCnhSp) {
    resultadoContainerFotoCnhSp.style.display = 'none';
}

if (cpfFotoCnhSpInput) {
    cpfFotoCnhSpInput.addEventListener('input', function () {
        let value = this.value.replace(/\D/g, '');
        if (value.length > 11) {
            value = value.slice(0, 11);
        }
        this.value = value;
    });
}

function limparResultadoFotoCnhSp() {
    if (fotoObjectUrlAtual) {
        URL.revokeObjectURL(fotoObjectUrlAtual);
        fotoObjectUrlAtual = null;
    }

    if (fotoResultadoCnhSp) {
        fotoResultadoCnhSp.removeAttribute('src');
        fotoResultadoCnhSp.style.display = 'none';
    }

    if (btnBaixarFotoCnhSp) {
        btnBaixarFotoCnhSp.style.display = 'none';
    }

    if (dadosResultadoCnhSp) {
        const msgAntiga = dadosResultadoCnhSp.querySelector('.foto-cnhsp-msg');
        if (msgAntiga) {
            msgAntiga.remove();
        }
    }
}

function mostrarErroFotoCnhSp(mensagem) {
    if (!dadosResultadoCnhSp || !resultadoContainerFotoCnhSp) return;

    const msgAntiga = dadosResultadoCnhSp.querySelector('.foto-cnhsp-msg');
    if (msgAntiga) {
        msgAntiga.remove();
    }

    const msg = document.createElement('div');
    msg.className = 'foto-cnhsp-msg badge badge-danger';
    msg.style.fontSize = '1.05em';
    msg.style.padding = '15px';
    msg.style.display = 'block';
    msg.style.textAlign = 'center';
    msg.style.whiteSpace = 'pre-wrap';
    msg.textContent = `❌ ${mensagem}`;
    dadosResultadoCnhSp.appendChild(msg);

    resultadoContainerFotoCnhSp.style.display = 'block';
}

async function consultarFotoCnhSp() {
    if (!cpfFotoCnhSpInput || !btnConsultarFotoCnhSp) return;

    const cpfLimpo = cpfFotoCnhSpInput.value.replace(/\D/g, '');

    if (!validarCPF(cpfLimpo)) {
        cpfFotoCnhSpInput.classList.add('shake');
        setTimeout(() => cpfFotoCnhSpInput.classList.remove('shake'), 400);
        limparResultadoFotoCnhSp();
        mostrarErroFotoCnhSp('CPF inválido. Verifique os números informados.');
        return;
    }

    const turnstileResponse = document.querySelector('[name="cf-turnstile-response"]')?.value;
    if (!turnstileResponse) {
        limparResultadoFotoCnhSp();
        mostrarErroFotoCnhSp('Por favor, valide o captcha.');
        return;
    }

    const textoOriginalBotao = btnConsultarFotoCnhSp.textContent;
    let preservarEstadoBotao = false;
    btnConsultarFotoCnhSp.disabled = true;
    btnConsultarFotoCnhSp.textContent = 'Carregando...';

    if (resultadoContainerFotoCnhSp) {
        resultadoContainerFotoCnhSp.style.display = 'none';
    }

    limparResultadoFotoCnhSp();

    if (loaderFotoCnhSp) {
        loaderFotoCnhSp.style.display = 'block';
        loaderFotoCnhSp.innerHTML = `
            <div class="loader-content">
                <div class="spinner"></div>
                Buscando foto no sistema, por favor aguarde...
            </div>`;
    }

    try {
        const response = await fetch(`/api/consultar_fotocnhsp/${cpfLimpo}`, {
            method: 'GET',
            headers: {
                'X-Turnstile-Token': turnstileResponse
            }
        });

        if (response.ok) {
            const blob = await response.blob();
            fotoObjectUrlAtual = URL.createObjectURL(blob);

            iniciarCooldownPersistenteFotoCnhSp(120, btnConsultarFotoCnhSp, textoOriginalBotao);
            preservarEstadoBotao = true;

            if (fotoResultadoCnhSp) {
                fotoResultadoCnhSp.src = fotoObjectUrlAtual;
                fotoResultadoCnhSp.style.display = 'block';
            }

            if (btnBaixarFotoCnhSp) {
                btnBaixarFotoCnhSp.style.display = 'block';
            }

            if (dadosResultadoCnhSp) {
                const msgAntiga = dadosResultadoCnhSp.querySelector('.foto-cnhsp-msg');
                if (msgAntiga) {
                    msgAntiga.remove();
                }

                const ok = document.createElement('div');
                ok.className = 'foto-cnhsp-msg badge badge-success';
                ok.style.fontSize = '1em';
                ok.style.padding = '12px';
                ok.style.display = 'block';
                ok.style.textAlign = 'center';
                ok.style.marginBottom = '10px';
                ok.textContent = '✅ Foto localizada com sucesso.';

                const meta = document.createElement('div');
                meta.className = 'foto-cnhsp-msg';
                meta.style.textAlign = 'center';
                meta.style.color = '#8aa3ba';
                meta.style.fontSize = '0.92em';
                meta.innerHTML = `CPF consultado: <strong>${cpfLimpo}</strong>`;

                dadosResultadoCnhSp.appendChild(ok);
                dadosResultadoCnhSp.appendChild(meta);
            }

            if (resultadoContainerFotoCnhSp) {
                resultadoContainerFotoCnhSp.style.display = 'block';
            }
            return;
        }

        let mensagemErro = 'Foto não encontrada ou indisponível no momento.';
        try {
            const payloadErro = await response.json();
            if (payloadErro && typeof payloadErro.erro === 'string' && payloadErro.erro.trim()) {
                mensagemErro = payloadErro.erro.trim();
            }
        } catch (_) {
            // Mantem mensagem padrao caso o backend nao devolva JSON.
        }

        if (response.status === 429) {
            const segundos = extrairSegundosCooldownFotoCnhSp(mensagemErro);
            if (segundos > 0) {
                iniciarCooldownPersistenteFotoCnhSp(segundos, btnConsultarFotoCnhSp, textoOriginalBotao);
                preservarEstadoBotao = true;
            }
            mostrarErroFotoCnhSp(mensagemErro);
            return;
        }

        mostrarErroFotoCnhSp(mensagemErro);
    } catch (_) {
        mostrarErroFotoCnhSp('Erro de conexão com o servidor. Tente novamente em instantes.');
    } finally {
        if (!preservarEstadoBotao) {
            btnConsultarFotoCnhSp.disabled = false;
            btnConsultarFotoCnhSp.textContent = textoOriginalBotao;
        }

        if (loaderFotoCnhSp) {
            loaderFotoCnhSp.style.display = 'none';
        }

        if (typeof turnstile !== 'undefined') {
            turnstile.reset();
        }
    }
}

if (btnConsultarFotoCnhSp) {
    btnConsultarFotoCnhSp.addEventListener('click', consultarFotoCnhSp);
}

if (cpfFotoCnhSpInput) {
    cpfFotoCnhSpInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && btnConsultarFotoCnhSp && !btnConsultarFotoCnhSp.disabled) {
            consultarFotoCnhSp();
        }
    });
}

if (btnBaixarFotoCnhSp) {
    btnBaixarFotoCnhSp.addEventListener('click', function () {
        if (!fotoObjectUrlAtual || !cpfFotoCnhSpInput) return;

        const cpfLimpo = cpfFotoCnhSpInput.value.replace(/\D/g, '').slice(0, 11);
        const link = document.createElement('a');
        link.href = fotoObjectUrlAtual;
        link.download = `foto_cnh_${cpfLimpo || 'consulta'}.jpg`;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
    });
}

document.addEventListener('DOMContentLoaded', restaurarCooldownFotoCnhSp);
