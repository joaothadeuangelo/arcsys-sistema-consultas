function escaparHtml(valor) {
        return String(valor)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function normalizarNomeModulo(nome) {
        const mapa = {
            placa: 'Placa',
            cnh: 'CNH',
            cpf: 'CPF',
            comparador: 'Face'
        };
        const chave = (nome || '').toLowerCase();
        return mapa[chave] || nome;
    }

    function aplicarStatusCircuitBreaker(led, falhas) {
        if (!led) return;

        led.classList.remove('status-operacional', 'status-instavel', 'status-offline');

        if (falhas >= 3) {
            led.classList.add('status-offline');
            led.title = 'Fora do ar';
            return;
        }

        if (falhas > 0) {
            led.classList.add('status-instavel');
            led.title = 'Instabilidade';
            return;
        }

        led.classList.add('status-operacional');
        led.title = 'Operacional';
    }

    const seriesErro24h = {
        global: Array(24).fill(0),
        placa: Array(24).fill(0),
        cnh: Array(24).fill(0),
        cpf: Array(24).fill(0),
        nome: Array(24).fill(0),
        comparador: Array(24).fill(0)
    };
    let serieDataRef = new Date().toDateString();

    function resetarSeriesSeVirouDia() {
        const hoje = new Date().toDateString();
        if (hoje === serieDataRef) return;
        serieDataRef = hoje;
        Object.keys(seriesErro24h).forEach((modulo) => {
            seriesErro24h[modulo] = Array(24).fill(0);
        });
    }

    function registrarFalhaHora(modulo, valor) {
        resetarSeriesSeVirouDia();
        const serie = seriesErro24h[modulo];
        if (!serie) return;
        const hora = new Date().getHours();
        serie[hora] = Number(valor || 0);
    }

    function desenharSparkline(modulo) {
        const svg = document.getElementById(`spark-${modulo}`);
        const serie = seriesErro24h[modulo];
        if (!svg || !serie) return;

        const largura = 120;
        const altura = 28;
        const maximo = Math.max(...serie, 1);
        const passo = largura / Math.max(serie.length - 1, 1);
        const pontos = serie.map((valor, idx) => {
            const x = idx * passo;
            const y = altura - ((Number(valor || 0) / maximo) * (altura - 4)) - 2;
            return `${x.toFixed(2)},${y.toFixed(2)}`;
        }).join(' ');

        const cor = maximo >= 3 ? '#ef4444' : (maximo > 0 ? '#f59e0b' : '#2ecc71');
        svg.innerHTML = `<polyline points="${pontos}" fill="none" stroke="${cor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></polyline>`;
    }

    function desenharSparklinesIniciais() {
        ['global', 'placa', 'cnh', 'cpf', 'nome', 'comparador'].forEach((modulo) => {
            desenharSparkline(modulo);
        });
    }

    function atualizarKpiModulos() {
        const total = document.querySelectorAll('.modulo-item').length;
        const ativos = document.querySelectorAll('.switch-link.on').length;
        const alvo = document.getElementById('kpiModulosOn');
        if (alvo) alvo.textContent = `${ativos}/${total}`;
    }

    function sincronizarRuntimeInicial() {
        document.querySelectorAll('.modulo-item').forEach((item) => {
            const modulo = item.getAttribute('data-modulo');
            const runtime = document.getElementById(`runtime-${modulo}`);
            const toggle = item.querySelector('.switch-link');
            if (!runtime || !toggle) return;
            runtime.textContent = toggle.classList.contains('on') ? '● Pronto' : '● Desligado';
        });
    }

    function atualizarKpiFalhasAtivas(falhasPlaca, falhasCnh) {
        const totalFalhas = Number(falhasPlaca || 0) + Number(falhasCnh || 0);
        const alvo = document.getElementById('kpiFalhasAtivas');
        if (alvo) alvo.textContent = String(totalFalhas);

        const statusPlaca = document.getElementById('runtime-placa');
        const statusCnh = document.getElementById('runtime-cnh');
        if (statusPlaca) statusPlaca.textContent = falhasPlaca >= 3 ? '● Offline' : (falhasPlaca > 0 ? '● Instável' : '● Pronto');
        if (statusCnh) statusCnh.textContent = falhasCnh >= 3 ? '● Offline' : (falhasCnh > 0 ? '● Instável' : '● Pronto');
    }

    async function fetchCircuitBreakerStatus() {
        const ledPlaca = document.getElementById('led-status-placa');
        const ledCnh = document.getElementById('led-status-cnh');

        try {
            const response = await fetch(`/api/admin/status-circuit-breaker?t=${Date.now()}`, {
                method: 'GET',
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error('Falha ao consultar status do circuit breaker.');
            }

            const data = await response.json();
            const falhasPlaca = Number(data?.placa || 0);
            const falhasCnh = Number(data?.cnh || 0);

            registrarFalhaHora('placa', falhasPlaca);
            registrarFalhaHora('cnh', falhasCnh);
            desenharSparkline('placa');
            desenharSparkline('cnh');
            atualizarKpiFalhasAtivas(falhasPlaca, falhasCnh);

            aplicarStatusCircuitBreaker(ledPlaca, falhasPlaca);
            aplicarStatusCircuitBreaker(ledCnh, falhasCnh);
        } catch (_) {
            // Em falha de comunicação, mantém estado atual dos LEDs para não gerar falso negativo.
        }
    }

    async function carregarTelemetria() {
        const btn = document.getElementById('btnAttTelemetria');
        const campoVisitantes = document.getElementById('valorVisitantesUnicos');
        const listaModulos = document.getElementById('listaUsoModulos');
        const status = document.getElementById('statusTelemetria');

        btn.innerText = '⏳ Atualizando...';
        btn.disabled = true;

        try {
            const response = await fetch('./api/telemetria/resumo', {
                method: 'GET',
                credentials: 'include'
            });

            let data;
            try {
                data = await response.json();
            } catch (_) {
                throw new Error('Resposta inválida da API de telemetria.');
            }

            if (!data.sucesso || !data.resumo) {
                throw new Error(data.erro || 'Falha ao carregar resumo de telemetria.');
            }

            const resumo = data.resumo;
            const total = Number(resumo.total_visitas_unicas || 0);
            campoVisitantes.textContent = total.toLocaleString('pt-BR');

            const uso = resumo.uso_modulos || {};
            const entradas = Object.entries(uso).sort((a, b) => Number(b[1]) - Number(a[1]));
            const totalConsultasHoje = entradas.reduce((acc, item) => acc + Number(item[1] || 0), 0);
            const kpiConsultas = document.getElementById('kpiConsultasHoje');
            if (kpiConsultas) {
                kpiConsultas.textContent = totalConsultasHoje.toLocaleString('pt-BR');
            }

            if (!entradas.length) {
                listaModulos.innerHTML = "<li><span class='modulo-nome-telemetria'>Sem uso registrado hoje</span><span class='modulo-uso-telemetria'>0</span></li>";
            } else {
                listaModulos.innerHTML = entradas.map(([modulo, qtd]) => {
                    const nomeSeguro = escaparHtml(normalizarNomeModulo(modulo));
                    const qtdFormatada = Number(qtd || 0).toLocaleString('pt-BR');
                    return `<li><span class='modulo-nome-telemetria'>${nomeSeguro}</span><span class='modulo-uso-telemetria'>${qtdFormatada}</span></li>`;
                }).join('');
            }

            const agora = new Date();
            status.textContent = `Atualizado em ${agora.toLocaleTimeString('pt-BR')}`;
        } catch (error) {
            status.textContent = 'Erro ao carregar telemetria. Tente novamente.';
            listaModulos.innerHTML = "<li><span class='modulo-nome-telemetria'>Falha ao buscar dados</span><span class='modulo-uso-telemetria'>--</span></li>";
            campoVisitantes.textContent = '--';
        } finally {
            btn.innerText = '🔄 Atualizar Telemetria';
            btn.disabled = false;
        }
    }

    async function carregarStatusContas() {
        const btn = document.getElementById('btnAttContas');
        const grid = document.getElementById('gridContasTelegram');
        
        btn.innerText = "⏳ Testando...";
        btn.disabled = true;
        grid.innerHTML = "<div class='sessao-line' style='padding: 6px 0;'>Testando conexão de todas as sessões na nuvem. Isso pode levar alguns segundos...</div>";

        try {
            const response = await fetch("./api/status_contas", {
                method: 'GET',
                credentials: 'include'
            });

            let data;
            try {
                data = await response.json();
            } catch (_) {
                throw new Error('Resposta não-JSON do endpoint de status.');
            }

            if (data.sucesso) {
                grid.innerHTML = ''; // Limpa a grid
                let operantes = 0;
                
                data.contas.forEach(conta => {
                    const card = document.createElement('div');
                    card.className = 'sessao-card';
                    card.style.borderLeftColor = conta.cor;

                    if ((conta.status || '').toLowerCase().includes('oper')) {
                        operantes += 1;
                    }
                    
                    let detalhesHtml = `<p class="sessao-line"><strong>Arquivo:</strong> ${conta.sessao}</p>`;
                    
                    if (conta.nome) {
                        detalhesHtml += `<p class="sessao-line"><strong>Nome:</strong> ${conta.nome}</p>`;
                        detalhesHtml += `<p class="sessao-line"><strong>Tel:</strong> ${conta.telefone}</p>`;
                    }
                    
                    if (conta.detalhe) {
                        detalhesHtml += `<p class="sessao-erro"><strong>Erro:</strong> ${conta.detalhe}</p>`;
                    }

                    card.innerHTML = `
                        <div class="sessao-head">
                            <span class="sessao-status" style="color: ${conta.cor};">
                                ${conta.icone} ${conta.status}
                            </span>
                        </div>
                        ${detalhesHtml}
                    `;
                    grid.appendChild(card);
                });

                const kpiSessoes = document.getElementById('kpiSessoesOn');
                if (kpiSessoes) {
                    kpiSessoes.textContent = `${operantes}/${data.contas.length}`;
                }
            } else {
                grid.innerHTML = `<div class='sessao-line' style='color: #e74c3c;'>❌ Erro: ${data.erro}</div>`;
            }
        } catch (error) {
            grid.innerHTML = `<div class='sessao-line' style='color: #e74c3c;'>❌ Erro de comunicação com o servidor. A API pode estar reiniciando.</div>`;
        } finally {
            btn.innerText = "🔄 Atualizar Radar";
            btn.disabled = false;
        }
    }

    // Carrega automaticamente assim que o painel admin for aberto
    document.addEventListener('DOMContentLoaded', function() {
        atualizarKpiModulos();
        sincronizarRuntimeInicial();
        desenharSparklinesIniciais();
        carregarStatusContas();
        carregarTelemetria();
        fetchCircuitBreakerStatus();

        // Atualização periódica do radar (2 min) e telemetria (45s)
        setInterval(carregarStatusContas, 120000);
        setInterval(carregarTelemetria, 45000);
        setInterval(fetchCircuitBreakerStatus, 15000);
    });

