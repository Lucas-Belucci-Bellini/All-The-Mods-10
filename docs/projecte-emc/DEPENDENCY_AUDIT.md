# ProjectE Integration — auditoria de dependências

**Repositório:** `Lucas-Belucci-Bellini/All-The-Mods-10`  
**Branch:** `work/projecte-emc-balancing`  
**Minecraft:** 1.21.1 / NeoForge 21.1.259  
**Versões no modlist:** ProjectE 1.1.0, ProjectE Integration 8.4.0, Project Expansion 1.0.6, AutoEMC 2.1.1.

## Resposta resumida

Até aqui, **não encontrei evidência de que os mods de conteúdo do ATM10 precisem do ProjectE Integration para funcionar**. Ele é um addon de integração do ProjectE: sua função publicada é adicionar mapeadores/conversões de receitas de outros mods, não fornecer os próprios mods suportados.

**Correção após inspeção do log real:** AutoEMC 2.1.1 declara ProjectE Integration como dependência obrigatória. `logs/latest.log` registra `Mod ID: 'projecteintegration', Requested by: 'autoemc', Expected range: '[8.3.1,)', Actual version: '[MISSING]'` e depois `Mod autoemc requires projecteintegration 8.3.1 or above`. O relatório `crash-reports/crash-2026-10-17_02.30.42-fml.txt` confirma que a inicialização falhou por essa dependência ausente. Portanto, **não podemos remover ProjectE Integration enquanto AutoEMC 2.1.1 continuar instalado**. O fato de haver conversões e baselines embutidos no TOML não elimina a dependência declarada no metadata do JAR.

## Evidência verificada

1. `logs/modlist.txt` registra 543 mods e uma entrada `projecteintegration` (ProjectE-Integration 8.4.0), além de `projecte`, `projectexpansion` e `autoemc`. O modlist demonstra que estão instalados, mas não contém a lista das dependências declaradas pelos JARs.
2. O `manifest.json` do pacote base ATM10 v8.3 contém ProjectE (CurseForge project ID 238222, `required: true`) e não contém ProjectE Integration (ID 313402) nem AutoEMC (ID 1595011). Isso mostra que o pacote ATM10 original não os declara como arquivos do pack. Como a instância é modificada, o manifesto base sozinho não prova as dependências dos addons adicionados.
3. A [página oficial de ProjectE Integration no CurseForge](https://www.curseforge.com/minecraft/mc-mods/projecte-integration) descreve o mod como suporte/conversões para receitas de outros mods. A página de relações lista os mods suportados como dependências **opcionais** do ProjectE Integration, o que significa que os mods suportados não precisam dele apenas para existir.
4. O log efetivo da instância resolve a dúvida sobre o JAR instalado: NeoForge lista `projecteintegration` como dependência obrigatória requisitada pelo `autoemc` com versão mínima 8.3.1. A falha aparece em `logs/latest.log` e no relatório de crash citado acima.
5. Em `config/autoemc-common.toml`, a configuração da instância usa `useBundledProjectEMappingConversions = true` e `useProjectEIntegrationBaselines = true`; os comentários indicam que parte das conversões e dos valores-base está incorporada no próprio AutoEMC. Isso sugere que ele possui dados embutidos, mas não prova a ausência de uma dependência declarada no metadata do JAR.

## Conclusão operacional

- **Mods de conteúdo do ATM10:** não há evidência encontrada de dependência obrigatória do ProjectE Integration.
- **ProjectE:** a função descrita do Integration é adicionar conversões; a instalação base do ATM10 declara ProjectE, não ProjectE Integration.
- **AutoEMC 2.1.1:** dependência obrigatória de ProjectE Integration >= 8.3.1 confirmada pelo log de inicialização.
- **Não remover definitivamente ainda.** Fazer o teste em uma cópia da instância.

## Procedimento seguro para confirmar

1. Duplicar a instância e o mundo; nunca usar o save principal para diagnóstico inicial.
2. Primeiro teste isolado: em uma cópia, manter ProjectE, Project Expansion, ProjectE Integration e Ice and Fire CE, mas desativar apenas AutoEMC. Isso verifica se o ProjectE mapeia EMC mesmo sem AutoEMC, enquanto o Integration continua presente.
3. Segundo teste em outra cópia: manter ProjectE, Project Expansion e Ice and Fire CE, mas desativar **ProjectE Integration e AutoEMC juntos**. Não remover o próprio ProjectE.
4. Em cada teste, abrir um mundo de teste e verificar se pedra, terra e diamante exibem EMC e podem ser aprendidos na Transmutation Table; guardar `latest.log` e o log de debug correspondentes.
5. Se o primeiro teste falhar e o segundo funcionar, a presença do Integration fica fortemente implicada. Se ambos falharem, investigar o erro original do ProjectE e testar separadamente a hipótese de incompatibilidade com Immersive Engineering.

**Limite da evidência:** a tentativa de 17/10/2026 não testou EMC com o ProjectE funcionando, porque `logs/instance_audit.txt` registra a remoção de ProjectE Integration e também do próprio ProjectE; a execução falhou porque AutoEMC ficou instalado sem sua dependência. A matriz de testes acima deve ser feita numa cópia da instância.
