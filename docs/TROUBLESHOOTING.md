# Guia de Troubleshooting — Mogged VPN

Documento tecnico para diagnostico e resolucao de problemas de conexao, latencia e rotas no Mogged VPN.

---

## 1. Falha de Handshake ou Erro de Conexao
### Causa
O servidor remoto pode ter sido desligado pelo operador voluntario do VPNGate, ou a porta UDP utilizada esta bloqueada pelo provedor de internet (CGNAT ou firewall corporativo).

### Solucao Automatica do Mogged VPN
- O `ServerManager` executa health check por TCP handshake em tempo real nos candidatos antes de iniciar o processo de conexao.
- O timeout de tentativa foi otimizado para 10 segundos (anteriormente 25 segundos).
- Caso o primeiro no falhe, o sistema aplica backoff exponencial (1s, 2s, 4s) e tenta ate 3 servidores diferentes.
- Apos 3 falhas consecutivas, o servidor e isolado temporariamente em blacklist local.

### Acao Manual Recomendada
- Toque no botao de atualizar servidores no dock da interface para buscar a lista mais recente diretamente via HTTPS.
- Alterne o pais selecionado para uma regiao com maior quantidade de nos ativos (ex: JP, US).

---

## 2. Bloqueio de Portas e Fragmentacao de Pacotes (MTU)
### Sintoma
A VPN conecta, mas sites ou chamadas de voz travam ou demoram para carregar.

### Configuracao Aplicada
- O motor OpenVPN utiliza `mssfix 1360` e `tun-mtu 1500`. Isso evita a fragmentacao de pacotes TCP sobre redes PPPoE, 4G e 5G.
- As diretivas de buffer `sndbuf 524288` e `rcvbuf 524288` estao ativas para evitar descarte de pacotes em alta taxa de transferencia.

---

## 3. Prevencao de Vazamento de DNS e IPv6
### Sintoma
Sites detectam o IP real atraves de consultas DNS paralelas ou IPv6.

### Protecao Implementada
- Windows: Diretiva `block-outside-dns` ativada nativamente no OpenVPN, impedindo consultas fora do adaptador VPN.
- DNS Seguro: Forcado uso dos servidores Cloudflare DNS (`1.1.1.1` e `1.0.0.1`).
- Bloqueio IPv6: A diretiva `block-ipv6` desativa rotas IPv6 durante a sessao ativa da VPN, evitando qualquer vazamento via pilha dupla.
- Ao desconectar, o comando `ipconfig /flushdns` e executado automaticamente para limpar entradas residuais.

---

## 4. Permissoes do Sistema no Windows
### Requisito
O Mogged VPN necessita de privilegios administrativos para configurar o driver de rede Wintun e as tabelas de rotas do Windows.

### Tratamento
- O aplicativo detecta automaticamente o nivel de execucao (`is_admin()`).
- Caso iniciado como usuario comum, solicita elevacao transparente via UAC (`ShellExecuteW` com verbo `runas`).
- O instalador oficial `MoggedVPN_Setup.exe` inclui a flag `--uac-admin`.
