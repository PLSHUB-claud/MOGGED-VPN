# Arquitetura do MOGGED-VPN

## Visão Geral
O **MOGGED-VPN** é uma solução de VPN para Windows 10/11 focada em contornar bloqueios regionais de compartilhamento de tela e streaming de voz/vídeo no Discord (Go Live), além de suportar navegação segura para todo o sistema operacional.

## Componentes

```
mogged/
├── app.py                  # Ponto de entrada, Single Instance Mutex e elevação UAC
├── constants.py            # Constantes globais do sistema e timeouts
├── exceptions.py           # Hierarquia de exceções MoggedError com redaction
├── logging_config.py       # Logger estruturado com redaction de IPs/tokens e rotação em %LOCALAPPDATA%
├── security/
│   └── binary_verify.py    # Validação SHA-256 e Authenticode para binários em tempo constante
├── storage/
│   └── secure_store.py     # Armazenamento protegido por DPAPI com suporte a backup atômico
├── network/
│   ├── vpn_backend.py      # Interface abstrata ABC para backends
│   ├── openvpn_backend.py  # Backend OpenVPN com driver Wintun e liberação garantida
│   ├── wireguard_backend.py# Backend WireGuard para túneis modernos
│   ├── vpn_manager.py      # Orquestrador com failover concorrente e delay para Wintun
│   ├── server_fetcher.py   # Consulta de servidores via HTTPS estrito e parse seguro de CSV
│   ├── server_validator.py # Rejeição estrita de IPs RFC 1918, CGNAT e metadados de nuvem
│   ├── kill_switch.py      # Bloqueio fail-closed via Windows Firewall (netsh)
│   ├── dns_manager.py      # Diretivas block-outside-dns e flushdns automático
│   └── split_tunnel.py     # Roteamento exclusivo do Discord via CIDRs e domínios dinâmicos
├── discord/
│   ├── paths.py            # Descoberta de binários oficiais do Discord
│   └── process_manager.py  # Encerramento gracioso WM_CLOSE e reinicialização segura
├── updates/
│   └── updater.py          # Verificação de releases GitHub com validação SHA-256 e semver
└── ui/
    ├── main_window.py      # Interface Tkinter com Canvas customizado e visual glossy
    └── tray.py             # Ícone e menu de contexto no System Tray
```

## Fluxo de Conexão
1. **Validação de Binários:** O aplicativo verifica a integridade SHA-256 do `openvpn.exe` e `wintun.dll`.
2. **Seleção de Servidor:** Consulta de servidores públicos via HTTPS (`vpngate.net`), filtrando qualquer IP privado ou reservado.
3. **Isolamento de Processo:** Qualquer instância anterior é encerrada por PID com espera de até 4s pelo kernel para liberação do driver Wintun.
4. **Montagem da Configuração:** Configuração efêmera em arquivo temporário com `mkstemp()`.
5. **Monitoramento e Failover:** Em caso de falha de handshake no candidato inicial, o sistema aguarda um delay seguro e tenta os servidores de contingência.
