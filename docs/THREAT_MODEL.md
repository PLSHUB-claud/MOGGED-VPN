# Modelo de Ameaças (Threat Model) — MOGGED-VPN

## 1. Ativos Protegidos
- **Endereço IP Real do Usuário:** Protegido contra vazamento durante streaming de tela e voz no Discord.
- **Integridade da Máquina do Usuário:** Protegida contra execução de código malicioso via adulteração de binários locais ou injeção de parâmetros em subprocessos.
- **Rede Local do Usuário (LAN):** Protegida contra pivoting ou varredura forçada (SSRF) por servidores maliciosos listados na API pública.
- **Privacidade de Resolução DNS:** Protegida contra interceptação pelo Provedor de Internet (ISP) através de diretivas de DNS seguro e bloqueio de consultas externas.

## 2. Atores de Ameaça (Threat Actors)
- **Operador de Servidor VPN Malicioso:** Um voluntário da rede VPN Gate que tente forçar rotas locais, escaneamento de rede ou tráfego malformado.
  - *Mitigação:* `route-nopull` no modo Discord, sanitização de diretivas OVPN e descarte rigoroso de IPs da RFC 1918.
- **Atacante Local (Man-in-the-Machine / Usuário Sem Privilégios):** Tentativa de ler preferências ou dados salvos em disco.
  - *Mitigação:* Criptografia DPAPI no escopo do usuário atual e ACLs nativas em `%LOCALAPPDATA%`.
- **Man-in-the-Middle (MitM) na Rede:** Tentativa de interceptar a lista de servidores ou injetar binários adulterados em downloads de atualização.
  - *Mitigação:* Requisições estritamente HTTPS (TLS 1.2+), verificação obrigatória de hash SHA-256 e assinatura digital Authenticode.

## 3. Limitações e Riscos Residuais
- A rede pública do VPN Gate é operada por voluntários ao redor do mundo. O tráfego de saída do nó VPN pode ser monitorado pelo operador do nó de saída, razão pela qual o MOGGED-VPN é indicado primordialmente para contornar restrições de streaming do Discord, e não para anonimato contra adversários com recursos estatais.
