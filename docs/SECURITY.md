# Política de Segurança — MOGGED-VPN

## Princípios de Segurança Adotados

1. **Execução Segura de Subprocessos:**
   - Nenhum subprocesso é invocado com `shell=True`.
   - Parâmetros são repassados como listas tipadas, inviabilizando injeções de comando.
2. **Prevenção de Ataques SSRF / Pivoting Interno:**
   - Todo servidor obtido via API é submetido à validação rigorosa de IP.
   - Qualquer endereço pertencente a RFC 1918 (redes privadas 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), Loopback (127.0.0.0/8), CGNAT (100.64.0.0/10) ou endpoints de metadados de nuvem (169.254.169.254) é descartado antes do socket connect.
3. **Integridade de Binários e Prevenção de DLL Hijacking:**
   - Todos os binários na pasta `bin/` possuem hashes SHA-256 fixados em manifesto e validados em tempo constante via `hmac.compare_digest`.
4. **Proteção de Dados Locais via Windows DPAPI:**
   - As preferências e históricos salvos localmente são criptografados com a chave nativa da conta de usuário do Windows (`CryptProtectData`).
5. **Mitigação de Vazamento de Dados (Leak Prevention):**
   - Diretiva `block-outside-dns` do OpenVPN ativa no Windows WFP.
   - Kill Switch via Windows Firewall isola o tráfego do Discord caso a VPN caia.
6. **Redaction Automático em Logs:**
   - O sistema de logs remove automaticamente endereços IP públicos, chaves criptográficas, certificados e nomes de usuário de caminhos do sistema operacional.
