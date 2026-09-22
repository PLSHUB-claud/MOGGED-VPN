# Política de Privacidade — MOGGED-VPN

## Princípio Fundamental
O MOGGED-VPN adota política de **Zero Telemetria**. Nenhum dado de navegação, endereço IP, estatística de uso, identificador de dispositivo ou telemetria é coletado ou transmitido para servidores dos desenvolvedores.

## Tratamento de Dados
1. **Dados em Disco:** Preferências do usuário (servidores favoritos, modo selecionado) são armazenadas localmente em `%LOCALAPPDATA%\MoggedVPN` e protegidas com criptografia DPAPI do Windows.
2. **Logs de Diagnóstico:** Registros de conexão são mantidos em arquivos locais rotativos com limite máximo de 5MB. Endereços IP públicos, tokens e certificados são mascarados pelo sistema de redaction antes de qualquer gravação em disco.
3. **Comunicações de Rede:**
   - Consulta à API do VPN Gate via HTTPS para listar nós públicos.
   - Consulta opcional a serviços canários de IP (`api.ipify.org`, `icanhazip.com`) estritamente para exibir ao usuário o endereço de saída ativo na interface.
